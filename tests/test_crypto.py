"""Tests for key derivation and AES-256-GCM encryption."""

import inspect

import pytest

from app import crypto
from app.crypto import (
    CryptoError,
    DecryptionError,
    decrypt_data,
    derive_key,
    encrypt_data,
    generate_salt,
)

PASSWORD = "correct horse battery staple 42"


def _key(salt=None):
    return derive_key(PASSWORD, salt or generate_salt())


class TestKeyDerivation:
    def test_returns_256_bit_key(self):
        assert len(_key()) == crypto.KEY_BYTES

    def test_deterministic_for_same_inputs(self):
        salt = generate_salt()
        assert derive_key(PASSWORD, salt) == derive_key(PASSWORD, salt)

    def test_different_salt_changes_key(self):
        k1 = derive_key(PASSWORD, generate_salt())
        k2 = derive_key(PASSWORD, generate_salt())
        assert k1 != k2

    def test_different_password_changes_key(self):
        salt = generate_salt()
        assert derive_key(PASSWORD, salt) != derive_key(PASSWORD + "x", salt)

    def test_rejects_empty_password(self):
        with pytest.raises(CryptoError):
            derive_key("", generate_salt())

    def test_rejects_short_salt(self):
        with pytest.raises(CryptoError):
            derive_key(PASSWORD, b"short")

    def test_argon2id_and_no_weak_hashes(self):
        source = inspect.getsource(crypto)
        assert "Argon2Type.ID" in source
        for weak in ("md5", "sha1", "sha256", "blake2"):
            assert weak not in source.lower()


class TestSaltGeneration:
    def test_length_and_type(self):
        salt = generate_salt()
        assert isinstance(salt, bytes)
        assert len(salt) == crypto.SALT_BYTES

    def test_salts_are_unique(self):
        salts = {generate_salt() for _ in range(200)}
        assert len(salts) == 200


class TestEncryption:
    def test_roundtrip(self):
        key = _key()
        plaintext = b"GitHub payload \xf0\x9f\x94\x90"
        assert decrypt_data(encrypt_data(plaintext, key), key) == plaintext

    def test_empty_plaintext_roundtrip(self):
        key = _key()
        assert decrypt_data(encrypt_data(b"", key), key) == b""

    def test_blob_contains_nonce_ciphertext_tag(self):
        key = _key()
        blob = encrypt_data(b"hello", key)
        assert len(blob) == crypto.NONCE_BYTES + 5 + crypto.GCM_TAG_BYTES

    def test_same_plaintext_produces_different_ciphertext(self):
        key = _key()
        a = encrypt_data(b"identical data", key)
        b = encrypt_data(b"identical data", key)
        assert a != b  # unique random nonce per operation

    def test_nonces_are_unique(self):
        key = _key()
        nonces = {encrypt_data(b"x", key)[: crypto.NONCE_BYTES] for _ in range(500)}
        assert len(nonces) == 500

    def test_wrong_key_fails_authentication(self):
        blob = encrypt_data(b"secret", _key())
        with pytest.raises(DecryptionError):
            decrypt_data(blob, _key())

    def test_tampered_ciphertext_fails(self):
        key = _key()
        blob = bytearray(encrypt_data(b"secret payload", key))
        blob[crypto.NONCE_BYTES + 1] ^= 0x01
        with pytest.raises(DecryptionError):
            decrypt_data(bytes(blob), key)

    def test_tampered_nonce_fails(self):
        key = _key()
        blob = bytearray(encrypt_data(b"secret payload", key))
        blob[0] ^= 0xFF
        with pytest.raises(DecryptionError):
            decrypt_data(bytes(blob), key)

    def test_truncated_blob_fails(self):
        key = _key()
        with pytest.raises(DecryptionError):
            decrypt_data(b"too short", key)

    def test_invalid_key_length_rejected(self):
        with pytest.raises(CryptoError):
            encrypt_data(b"data", b"sixteen bytes!!!")

    def test_encrypt_text_helpers(self):
        key = _key()
        assert crypto.decrypt_text(crypto.encrypt_text("ünïcödé", key), key) == "ünïcödé"
