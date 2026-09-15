"""Vault creation / unlock and session brute-force backoff.

The master password is never persisted. A random 16-byte Argon2id salt and a
verifier (a known sentinel encrypted with the derived key) are stored instead:
correctness of a candidate password is proven by a successful AES-GCM
authentication, not by comparing any stored password hash.

Backoff applies within an application session only (per the requirement to
lock users out of nothing) and never exceeds 15 seconds between attempts.
"""

from __future__ import annotations

import hmac
import time

from .crypto import DecryptionError, decrypt_data, derive_key, encrypt_data, generate_salt
from .database import Database, DatabaseError
from .utils import get_logger, utc_now_iso

log = get_logger("auth")

VERIFY_SENTINEL = b"password-manager:verify:v1"

# Wait enforced *before* the next attempt, indexed by number of failures so
# far: attempts 1-2 free, then short delay, then longer, capped.
_ATTEMPT_DELAYS_SECONDS = (0.0, 0.0, 2.0, 5.0, 10.0, 15.0)
_MAX_BACKOFF_SECONDS = 15.0


class AuthError(Exception):
    pass


class VaultAlreadyExistsError(AuthError):
    pass


class VaultNotFoundError(AuthError):
    pass


class WrongMasterPasswordError(AuthError):
    """Raised for an incorrect password or a corrupted vault record."""


class TooManyAttemptsError(AuthError):
    def __init__(self, wait_seconds: float) -> None:
        super().__init__("Too many failed attempts.")
        self.wait_seconds = wait_seconds


class AuthManager:
    def __init__(self, database: Database | None = None) -> None:
        self.db = database or Database()
        self.db.connect()
        self.failed_attempts = 0
        self._lockout_until = 0.0

    # -- helpers -----------------------------------------------------------
    @property
    def vault_exists(self) -> bool:
        return self.db.vault_exists()

    def seconds_until_next_attempt(self) -> float:
        remaining = self._lockout_until - time.monotonic()
        return remaining if remaining > 0 else 0.0

    def next_attempt_delay(self) -> float:
        index = min(self.failed_attempts, len(_ATTEMPT_DELAYS_SECONDS) - 1)
        return _ATTEMPT_DELAYS_SECONDS[index]

    def reset_backoff(self) -> None:
        self.failed_attempts = 0
        self._lockout_until = 0.0

    def _register_for_redaction(self, master_password: str) -> None:
        from . import utils

        utils.register_secret(master_password)

    def _record_failure(self) -> None:
        self.failed_attempts += 1
        delay = self.next_attempt_delay()
        if delay > 0:
            self._lockout_until = time.monotonic() + delay
        log.info("Unlock attempt rejected (attempt %d).", self.failed_attempts)
        raise WrongMasterPasswordError("Incorrect master password.")

    # -- operations ---------------------------------------------------------
    def create_vault(self, master_password: str) -> bytes:
        """Create a fresh vault. Returns the derived encryption key."""
        if self.vault_exists:
            raise VaultAlreadyExistsError("A vault already exists.")
        self._register_for_redaction(master_password)
        salt = generate_salt()
        key = derive_key(master_password, salt)
        try:
            verifier = encrypt_data(VERIFY_SENTINEL, key)
        except Exception:  # pragma: no cover - defensive
            key = b""
            raise
        try:
            self.db.create_vault(salt, verifier, utc_now_iso())
        except DatabaseError:
            key = b""
            raise
        self.failed_attempts = 0
        log.info("Vault created: %d entries.", self.db.entry_count())
        return key

    def unlock(self, master_password: str) -> bytes:
        """Verify the master password. Returns the encryption key or raises."""
        remaining = self.seconds_until_next_attempt()
        if remaining > 0:
            raise TooManyAttemptsError(remaining)

        metadata = self.db.get_metadata()
        if metadata is None:
            raise VaultNotFoundError("No vault was found.")

        self._register_for_redaction(master_password)
        try:
            key = derive_key(master_password, metadata["salt"])
        except Exception:
            log.error("Key derivation failed.")
            raise AuthError("Unable to unlock the vault.") from None

        try:
            stored = decrypt_data(metadata["verifier"], key)
        except DecryptionError:
            key = b""
            self._record_failure()
            return b""  # unreachable

        if not hmac.compare_digest(stored, VERIFY_SENTINEL):
            key = b""
            stored = b""
            self._record_failure()
            return b""  # unreachable

        self.reset_backoff()
        log.info("Vault unlocked.")
        return key
