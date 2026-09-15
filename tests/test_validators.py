"""Tests for input validation."""

import pytest

from app import validators
from app.validators import (
    passwords_match,
    sanitize_url,
    validate_category,
    validate_entry_title,
    validate_master_password,
    validate_username,
    validate_website,
)


class TestMasterPassword:
    def test_empty_is_rejected(self):
        assert validate_master_password("")

    def test_too_short_is_rejected(self):
        assert validate_master_password("Ab3!")

    def test_common_weak_password_rejected(self):
        assert validate_master_password("password")
        assert validate_master_password("passwordpassword")
        assert validate_master_password("1234567890")

    def test_sequence_rejected(self):
        assert validate_master_password("abcdefghijklmnopstu")

    def test_strong_passphrase_accepted(self):
        assert validate_master_password("Violet-Horizon-42-cafe!!") == []
        assert validate_master_password("Seventeen orange lamps glow 7") == []

    def test_mismatch(self):
        assert not passwords_match("abc123456", "abc123457")
        assert passwords_match("abc123456", "abc123456")

    def test_matching_requires_nonempty(self):
        assert not passwords_match("", "")


class TestTitle:
    def test_empty_title_invalid(self):
        assert validate_entry_title("")
        assert validate_entry_title("   ")

    def test_valid_title(self):
        assert validate_entry_title("GitHub") == []

    def test_overlong_title(self):
        assert validate_entry_title("x" * 500)


class TestWebsite:
    @pytest.mark.parametrize(
        "url",
        ["https://github.com", "http://localhost:8080/app", "https://a.b.c/d?e=1#f"],
    )
    def test_valid_urls(self, url):
        assert validate_website(url) == []

    @pytest.mark.parametrize(
        "url",
        ["javascript:alert(1)", "file:///C:/Windows", "data:text/html,x", "ftp://x.com", "mailto:a@b.c"],
    )
    def test_dangerous_or_wrong_scheme_urls_rejected(self, url):
        assert validate_website(url)

    def test_empty_website_allowed(self):
        assert validate_website("") == []
        assert validate_website("   ") == []

    def test_bare_domain_normalized_to_https(self):
        assert sanitize_url("github.com") == "https://github.com"

    def test_urls_with_shell_injection_never_execute(self):
        # A URL with a command injected would be rejected outright, and
        # nothing here is ever passed to a shell (only the OS browser opens).
        assert sanitize_url("https://x; rm -rf /") is None

    def test_url_with_credentials_rejected(self):
        assert validate_website("https://admin:passwd@evil.example/")


class TestOtherFields:
    def test_username_normal_ok(self):
        assert validate_username("user@example.com") == []

    def test_username_length_limit(self):
        assert validate_username("u" * 400)

    def test_category_limit(self):
        assert validate_category("Personal") == []
        assert validate_category("c" * 200)

    def test_control_characters_rejected(self):
        assert validate_username("bad\x00user")
