"""Tests for vault creation, unlock, and backoff."""

import os

import pytest

from app import auth as auth_mod
from app.auth import (
    AuthManager,
    TooManyAttemptsError,
    VaultAlreadyExistsError,
    VaultNotFoundError,
    WrongMasterPasswordError,
)
from app.database import Database
from app import utils

GOOD = "Nebula-Tide-92-mango!!"
BAD = "Nebula-Tide-92-mango?"


@pytest.fixture()
def manager(tmp_path):
    db = Database(tmp_path / "auth-vault.db")
    db.connect()
    manager = AuthManager(db)
    yield manager
    utils.clear_registered_secrets()
    db.close()


class TestVaultCreation:
    def test_create_returns_key(self, manager):
        key = manager.create_vault(GOOD)
        assert isinstance(key, bytes) and len(key) == 32

    def test_cannot_create_twice(self, manager):
        manager.create_vault(GOOD)
        with pytest.raises(VaultAlreadyExistsError):
            manager.create_vault("anything else 9999!!")

    def test_unlock_correct_password(self, manager):
        created = manager.create_vault(GOOD)
        assert manager.unlock(GOOD) == created

    def test_persisted_across_reopen(self, tmp_path):
        db = Database(tmp_path / "reopen.db")
        db.connect()
        AuthManager(db).create_vault(GOOD)
        db.close()
        db2 = Database(tmp_path / "reopen.db")
        db2.connect()
        assert AuthManager(db2).unlock(GOOD)


class TestWrongPassword:
    def test_incorrect_password_rejected(self, manager):
        manager.create_vault(GOOD)
        with pytest.raises(WrongMasterPasswordError):
            manager.unlock(BAD)
        assert manager.failed_attempts == 1

    def test_no_vault_raises(self, manager):
        with pytest.raises(VaultNotFoundError):
            manager.unlock(GOOD)

    def test_tampered_verifier_rejected(self, manager):
        manager.create_vault(GOOD)
        meta = manager.db.get_metadata()
        tampered = bytearray(meta["verifier"])
        tampered[len(tampered) // 2] ^= 0xFF
        manager.db._db.execute(
            "UPDATE vault_metadata SET verifier = ? WHERE id = 1",
            (bytes(tampered),),
        )
        manager.db._db.commit()
        with pytest.raises(WrongMasterPasswordError):
            manager.unlock(GOOD)


class TestBruteForceBackoff:
    def test_first_two_attempts_have_no_delay(self, manager):
        manager.create_vault(GOOD)
        assert manager.seconds_until_next_attempt() == 0.0
        with pytest.raises(WrongMasterPasswordError):
            manager.unlock(BAD)  # attempt 1 failed
        assert manager.seconds_until_next_attempt() == 0.0  # attempt 2 is free
        with pytest.raises(WrongMasterPasswordError):
            manager.unlock(BAD)  # attempt 2 failed
        assert manager.failed_attempts == 2
        # the third attempt now carries a short delay, capped in the future.
        assert 0 < manager.seconds_until_next_attempt() <= 2.0

    def _three_failures_start(self, manager):
        manager.create_vault(GOOD)
        for _ in range(2):
            with pytest.raises(WrongMasterPasswordError):
                manager.unlock(BAD)

    def test_third_blocked_attempt_waits(self, manager):
        self._three_failures_start(manager)
        assert manager.seconds_until_next_attempt() > 0
        with pytest.raises(TooManyAttemptsError) as err:
            manager.unlock(GOOD)
        assert err.value.wait_seconds > 0

    def test_delays_increase_then_cap(self, manager):
        delays = []
        for attempts in range(0, 8):
            manager.failed_attempts = attempts
            delays.append(manager.next_attempt_delay())
        assert delays[0] == 0.0
        assert delays[1] == 0.0
        assert all(delays[i] <= delays[i + 1] for i in range(len(delays) - 1))
        assert delays[2] > 0
        assert max(delays) <= auth_mod._MAX_BACKOFF_SECONDS

    def test_success_resets_backoff(self, manager):
        manager.create_vault(GOOD)
        with pytest.raises(WrongMasterPasswordError):
            manager.unlock(BAD)
        with pytest.raises(WrongMasterPasswordError):
            manager.unlock("wrong wrong wrong!!")
        key = None
        manager._lockout_until = 0  # simulate the waiting period elapsing
        key = manager.unlock(GOOD)
        assert key
        assert manager.failed_attempts == 0
        assert manager.seconds_until_next_attempt() == 0

    def test_backoff_is_session_only(self, tmp_path):
        db = Database(tmp_path / "session.db")
        db.connect()
        m = AuthManager(db)
        m.create_vault(GOOD)
        with pytest.raises(WrongMasterPasswordError):
            m.unlock(BAD)
        with pytest.raises(WrongMasterPasswordError):
            m.unlock(BAD)
        # the third attempt is throttled within this session...
        with pytest.raises(TooManyAttemptsError):
            m.unlock(BAD)
        # ...but a fresh application session starts with a clean slate.
        fresh = AuthManager(db)
        assert fresh.failed_attempts == 0
        assert fresh.unlock(GOOD)
        db.close()
