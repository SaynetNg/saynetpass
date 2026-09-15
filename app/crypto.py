"""Cryptographic primitives.

Key derivation: Argon2id (memory-hard, side-channel-resistant) with a
per-vault random salt. Encryption: AES-256-GCM authenticated encryption.

Every encryption operation generates a fresh random 12-byte nonce internally,
so nonces are unique per message. Encrypted blob layout:

    nonce (12 bytes) || ciphertext || authentication tag (16 bytes)

No custom cryptography is implemented here; everything wraps vetted defaults
from `argon2-cffi` and the `cryptography` package.
"""

from __future__ import annotations

import secrets

from argon2.low_level import Type as Argon2Type
from argon2.low_level import hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32
GCM_TAG_BYTES = 16

# OWASP-aligned Argon2id parameters.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST_KIB = 64 * 1024  # 64 MiB
ARGON2_PARALLELISM = 1


class CryptoError(Exception):
    """Base class for cryptographic failures."""


class DecryptionError(CryptoError):
    """Raised when authentication fails or input is malformed."""


def generate_salt() -> bytes:
    return secrets.token_bytes(SALT_BYTES)


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from the master password using Argon2id."""
    if not isinstance(master_password, str) or not master_password:
        raise CryptoError("A master password is required.")
    if len(salt) < SALT_BYTES:
        raise CryptoError("Invalid KDF salt.")
    return hash_secret_raw(
        secret=master_password.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        parallelism=ARGON2_PARALLELISM,
        hash_len=KEY_BYTES,
        type=Argon2Type.ID,
    )


def encrypt_data(data: bytes, key: bytes) -> bytes:
    """Encrypt with AES-256-GCM. A fresh random nonce is generated per call."""
    if len(key) != KEY_BYTES:
        raise CryptoError("Invalid encryption key.")
    if not isinstance(data, bytes):
        raise CryptoError("Only bytes can be encrypted.")
    nonce = secrets.token_bytes(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, data, None)


def decrypt_data(blob: bytes, key: bytes) -> bytes:
    """Decrypt an `encrypt_data` blob; raises DecryptionError on any failure."""
    if len(key) != KEY_BYTES:
        raise CryptoError("Invalid encryption key.")
    if not isinstance(blob, (bytes, bytearray)) or len(blob) < NONCE_BYTES + GCM_TAG_BYTES:
        raise DecryptionError("Encrypted data is malformed.")
    blob = bytes(blob)
    nonce, payload = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
    try:
        return AESGCM(key).decrypt(nonce, payload, None)
    except InvalidTag as exc:
        raise DecryptionError("Authentication failed.") from exc


def encrypt_text(text: str, key: bytes) -> bytes:
    return encrypt_data(text.encode("utf-8"), key)


def decrypt_text(blob: bytes, key: bytes) -> str:
    return decrypt_data(blob, key).decode("utf-8")
