"""Tests for the SQLite layer and the Vault session over it."""

import pytest

from app.crypto import derive_key, encrypt_data, generate_salt
from app.database import Database, DatabaseError
from app.models import KIND_NOTE, Entry, Vault, VaultError

PASSWORD = "vault test passphrase 7!!"


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test-vault.db")
    database.connect()
    yield database
    database.close()


@pytest.fixture()
def salt():
    return generate_salt()


@pytest.fixture()
def key(salt):
    return derive_key(PASSWORD, salt)


class TestVaultMetadata:
    def test_fresh_database_has_no_vault(self, db):
        assert db.get_metadata() is None
        assert not db.vault_exists()

    def test_create_vault_stores_salt_and_verifier(self, db, salt, key):
        verifier = encrypt_data(b"sentinel", key)
        db.create_vault(salt, verifier, "2026-01-01T00:00:00+00:00")
        meta = db.get_metadata()
        assert meta is not None
        assert meta["salt"] == salt
        assert meta["verifier"] == verifier
        assert meta["version"] == 1
        assert db.vault_exists()

    def test_cannot_create_two_vaults(self, db, salt, key):
        db.create_vault(salt, encrypt_data(b"x", key), "now")
        with pytest.raises(DatabaseError):
            db.create_vault(salt, encrypt_data(b"x", key), "now")


class TestEntryRows:
    def test_add_retrieve_update_delete(self, db, key):
        blob = encrypt_data(b'{"title": "GitHub"}', key)
        entry_id = db.add_entry("login", blob, "2026-01-01", "2026-01-01")
        rows = db.fetch_entries()
        assert len(rows) == 1
        assert rows[0]["id"] == entry_id
        assert bytes(rows[0]["encrypted_data"]) == blob

        blob2 = encrypt_data(b'{"title": "GitHub2"}', key)
        assert db.update_entry(entry_id, blob2, "2026-02-02")
        assert bytes(db.fetch_entries()[0]["encrypted_data"]) == blob2
        assert db.fetch_entries()[0]["updated_at"] == "2026-02-02"

        assert db.delete_entry(entry_id)
        assert db.fetch_entries() == []
        assert not db.delete_entry(entry_id)  # second delete: not found
        assert not db.update_entry(999999, blob, "x")  # unknown id

    def test_entry_count(self, db, key):
        blob = encrypt_data(b"a", key)
        assert db.entry_count() == 0
        db.add_entry("login", blob, "c", "u")
        db.add_entry("note", blob, "c", "u")
        assert db.entry_count() == 2


class TestBackupRestore:
    def test_backup_and_restore_roundtrip(self, db, salt, key, tmp_path):
        db.create_vault(salt, encrypt_data(b"s", key), "now")
        db.add_entry("login", encrypt_data(b"payload", key), "c", "u")
        backup = tmp_path / "backup.db"
        db.backup_to(backup)

        other = Database(tmp_path / "other.db")
        other.connect()
        other.restore_from(backup)
        assert other.vault_exists()
        assert other.entry_count() == 1
        row = other.fetch_entries()[0]
        from app.crypto import decrypt_data

        assert decrypt_data(bytes(row["encrypted_data"]), key) == b"payload"
        with pytest.raises(DatabaseError):
            other.restore_from(tmp_path / "missing.db")
        not_a_vault = tmp_path / "junk.db"
        import sqlite3

        with sqlite3.connect(not_a_vault) as c:
            c.execute("CREATE TABLE junk_table (x)")
        with pytest.raises(DatabaseError):
            other.restore_from(not_a_vault)
        other.close()


class TestVaultSession:
    def _vault(self, db, key):
        return Vault(db, key)

    def test_crud_roundtrip(self, db, key):
        vault = self._vault(db, key)
        entry = vault.create_entry(
            "GitHub", username="user@example.com", password="s3cr3t!",
            website="https://github.com", category="Development", favorite=True,
        )
        assert entry.id > 0
        assert vault.by_id(entry.id) is entry
        assert len(vault.entries) == 1

        vault.update_entry(entry, password="rotated!", favorite=False)
        assert entry.password == "rotated!"
        assert entry.updated_at != entry.created_at

        vault.set_favorite(entry, True)
        assert vault.favorite_entries() == [entry]

        vault.delete_entry(entry.id)
        assert vault.entries == []
        assert db.entry_count() == 0

    def test_notes_entry_ignores_login_fields(self, db, key):
        vault = self._vault(db, key)
        note = vault.create_entry(
            "WiFi", kind=KIND_NOTE, password="ignored", username="ignored",
            website="ignored", notes="Router admin stuff",
        )
        assert note.is_note
        assert note.password == ""
        assert note.username == ""
        assert note.website == ""

    def test_search_and_categories(self, db, key):
        vault = self._vault(db, key)
        vault.create_entry("GitHub", username="dev@corp.io", category="Development")
        vault.create_entry("Bank", category="Finance", notes="Checking account")
        assert [e.title for e in vault.search("git")] == ["GitHub"]
        assert [e.title for e in vault.search("checking")] == ["Bank"]
        assert len(vault.search("")) == 2
        assert "Development" in vault.categories_present()
        assert "Finance" in vault.categories_present()

    def test_persistence_survives_reload(self, db, key):
        vault = self._vault(db, key)
        vault.create_entry("Reloaded", password="persisted-pw", favorite=True)
        reloaded = Vault(db, key)
        assert reloaded.entries[0].title == "Reloaded"
        assert reloaded.entries[0].password == "persisted-pw"
        assert reloaded.entries[0].favorite

    def test_lock_drops_data_and_key(self, db, key):
        vault = self._vault(db, key)
        vault.create_entry("Sealed", password="x")
        vault.lock()
        assert vault.is_locked
        assert vault.entries == []
        with pytest.raises(VaultError):
            vault.create_entry("Nope")

    def test_wrong_key_cannot_load(self, db, key):
        vault = self._vault(db, key)
        vault.create_entry("Secret", password="topsecret")
        wrong = derive_key("definitely the wrong password", generate_salt())
        with pytest.raises(VaultError):
            Vault(db, wrong)

    def test_rejects_unknown_field_on_update(self, db, key):
        vault = self._vault(db, key)
        entry = vault.create_entry("X")
        with pytest.raises(VaultError):
            Vault(db, b"0" * 31)  # invalid length key
        with pytest.raises(ValueError):
            vault.update_entry(entry, nonexisting_field="boom")

    def test_entry_repr_has_no_password(self, key):
        entry = Entry(id=1, title="GitHub", password="supersecretpw")
        assert "supersecretpw" not in repr(entry)
