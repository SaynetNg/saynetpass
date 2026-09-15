"""Dedicated security-regression tests (spec section 37).

Written specifically to catch classic password-manager mistakes: plaintext
storage, key/secret leakage into the database or logs, nonce reuse, weak or
downgraded KDF work factors, and SQL string interpolation.
"""

import inspect
import re
from pathlib import Path

import pytest

from app import crypto, database, models, password_generator, utils
from app.auth import AuthManager
from app.crypto import DecryptionError, decrypt_data, derive_key, encrypt_data, generate_salt
from app.database import Database

Vault = models.Vault

MASTER = "Saffron-Lantern-77-vault!"
PASSWORD_VALUE = "Xk9#UNIQUEpw-4481-melt"
USERNAME_VALUE = "unique-user-4481@example.com"
NOTE_VALUE = "Recovery-code-XYZ-9931"
TITLE_VALUE = "Security Site 4481"


@pytest.fixture()
def secured(tmp_path):
    db = Database(tmp_path / "security.db")
    db.connect()
    key = AuthManager(db).create_vault(MASTER)
    vault = Vault(db, key)
    vault.create_entry(
        TITLE_VALUE,
        username=USERNAME_VALUE,
        password=PASSWORD_VALUE,
        website="https://example.com",
        category="Finance",
        notes=NOTE_VALUE,
    )
    yield db, key
    db.close()


def _raw_bytes(db: Database) -> bytes:
    return Path(db.path).read_bytes()


class TestSecretsNeverStored:
    def test_master_password_not_in_database_file(self, secured):
        db, _ = secured
        assert MASTER.encode("utf-8") not in _raw_bytes(db)
        # UTF-16 form as well, in case anything ever encoded text differently.
        assert MASTER.encode("utf-16-le") not in _raw_bytes(db)

    def test_derived_key_not_in_database_file(self, secured):
        db, key = secured
        raw = _raw_bytes(db)
        assert key not in raw
        assert bytes(key) not in raw

    def test_entry_fields_are_not_stored_in_plaintext(self, secured):
        db, _ = secured
        raw = _raw_bytes(db)
        for secret in (PASSWORD_VALUE, USERNAME_VALUE, NOTE_VALUE, TITLE_VALUE):
            assert secret.encode("utf-8") not in raw

    def test_settings_file_stores_no_secret_material(self, tmp_path):
        from app.config import Settings, save_settings

        path = tmp_path / "settings.json"
        save_settings(Settings(), path)
        content = path.read_text("utf-8").lower()
        for forbidden in ("salt", "key", "verifier", "password"):
            assert forbidden not in content


class TestEncryptionProperties:
    def test_same_plaintext_twice_produces_different_ciphertext(self):
        key = derive_key("work factor 55!!", generate_salt())
        a = encrypt_data(b"identical payload", key)
        b = encrypt_data(b"identical payload", key)
        assert a != b
        assert decrypt_data(a, key) == decrypt_data(b, key) == b"identical payload"

    def test_tampered_ciphertext_fails_authentication(self, secured):
        db, key = secured
        row = db.fetch_entries()[0]
        blob = bytearray(bytes(row["encrypted_data"]))
        blob[len(blob) // 2] ^= 0x01
        with pytest.raises(DecryptionError):
            decrypt_data(bytes(blob), key)

    def test_tampered_record_cannot_load_vault(self, tmp_path):
        db = Database(tmp_path / "tamper.db")
        db.connect()
        key = AuthManager(db).create_vault(MASTER)
        Vault(db, key).create_entry("Target", password="payload-1234")
        row = db.fetch_entries()[0]
        blob = bytearray(bytes(row["encrypted_data"]))
        blob[-1] ^= 0x80
        db._db.execute(
            "UPDATE entries SET encrypted_data = ? WHERE id = ?",
            (bytes(blob), row["id"]),
        )
        db._db.commit()
        with pytest.raises(models.VaultError):
            Vault(db, key)
        db.close()

    def test_wrong_master_password_cannot_decrypt_vault(self, secured):
        db, _ = secured
        wrong_key = derive_key("not the real password 99!!", generate_salt())
        with pytest.raises(models.VaultError):
            Vault(db, wrong_key)


class TestKDFHardening:
    def test_argon2id_work_factor_not_downgraded(self):
        source = inspect.getsource(crypto)
        assert "Argon2Type.ID" in source
        assert crypto.ARGON2_MEMORY_COST_KIB >= 64 * 1024  # KiB
        assert crypto.ARGON2_TIME_COST >= 2
        assert crypto.KEY_BYTES == 32

    def test_only_authenticated_cipher_modes(self):
        source = inspect.getsource(crypto)
        assert "AESGCM" in source
        lowered = source.lower()
        assert "modes." not in lowered
        for weak in ("ecb", "cbc", "ofb", "cfb", "ctr"):
            assert weak not in lowered


class TestRandomnessSource:
    def test_generator_imports_secrets_never_random(self):
        source = inspect.getsource(password_generator)
        assert "import secrets" in source
        assert not re.search(r"(^|\n)\s*(import\s+random|from\s+random\b)", source)

    def test_salts_nonrepeating(self):
        assert len({generate_salt() for _ in range(50)}) == 50


class TestParameterizedSQL:
    def test_no_interpolated_sql_in_database_module(self):
        source = inspect.getsource(database)
        assert not re.search(r"execute(?:many)?\(\s*f['\"]", source)
        assert ".format(" not in source
        assert not re.search(r"execute\([^)]*%s", source)
        assert re.search(r"execute\([\s\S]*?\?[\s\S]*?\)", source)

    def test_sql_statements_never_embed_variables(self):
        source = inspect.getsource(database)
        fragments = re.findall(r"['\"]\s*([A-Z][A-Za-z, ()=_*?.\-%+]*?)\s*['\"]", source)
        for sql in fragments:
            if sql.strip().upper().startswith(
                ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "PRAGMA")
            ):
                assert "{" not in sql


class TestLogSafety:
    def test_registered_secrets_are_redacted(self):
        utils.register_secret(PASSWORD_VALUE)
        try:
            line = utils.redact(f"failed lookup for {PASSWORD_VALUE}")
            assert PASSWORD_VALUE not in line
            assert utils.SECRET_PLACEHOLDER in line
        finally:
            utils.clear_registered_secrets()

    def test_assignment_style_secrets_are_redacted(self):
        line = utils.redact("master_password: DefinitelySecret99!")
        assert "DefinitelySecret99!" not in line

    def test_source_contains_no_logging_of_secret_arguments(self):
        package_dir = Path(models.__file__).parent
        call_re = re.compile(
            r"\b(log|logger|logging)\.(debug|info|warning|error|critical|exception|log)"
            r"\(([^)\n]*)\)",
        )
        literal_re = re.compile(r"""(?:[rbuf]*['"][^'"]*['"])""")
        offenders = []
        for path in package_dir.glob("*.py"):
            if path.name == "utils.py":
                continue
            for call in call_re.finditer(path.read_text("utf-8")):
                residue = literal_re.sub("", call.group(3))
                if re.search(r"\b(master|password|secret|token|key)\w*", residue, re.I):
                    offenders.append((path.name, residue.strip()))
        assert offenders == []
