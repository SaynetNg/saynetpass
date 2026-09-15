"""Input validation. All failures produce user-safe messages."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import config
from .utils import evaluate_password_strength

MAX_TITLE_LEN = 120
MAX_USERNAME_LEN = 300
MAX_PASSWORD_LEN = 512
MAX_NOTES_LEN = 20000
ALLOWED_URL_SCHEMES = ("http", "https")


def validate_master_password(password: str) -> list[str]:
    """Policy check for a new master password. Empty list means valid."""
    errors: list[str] = []
    if not password:
        return ["A master password is required."]
    if len(password) < config.MIN_MASTER_PASSWORD_LENGTH:
        errors.append(
            f"The master password must be at least {config.MIN_MASTER_PASSWORD_LENGTH} characters long."
        )
    strength = evaluate_password_strength(password)
    if strength.score < config.MIN_MASTER_PASSWORD_SCORE:
        errors.append(
            "The master password is too weak. Use a longer passphrase with mixed "
            "characters, or generate a random one."
        )
    return errors


def passwords_match(password: str, confirmation: str) -> bool:
    return bool(password) and password == confirmation


def validate_entry_title(title: str) -> list[str]:
    errors: list[str] = []
    if not title.strip():
        errors.append("A title is required.")
    elif len(title) > MAX_TITLE_LEN:
        errors.append(f"The title must be at most {MAX_TITLE_LEN} characters.")
    return errors


def validate_text_field(value: str, max_len: int, name: str) -> list[str]:
    if len(value) > max_len:
        return [f"{name} must be at most {max_len} characters."]
    if any(ord(ch) < 32 and ch not in "\n\t\r" for ch in value):
        return [f"{name} contains invalid characters."]
    return []


def validate_username(username: str) -> list[str]:
    return validate_text_field(username, MAX_USERNAME_LEN, "The username")


def validate_password_field(password: str) -> list[str]:
    return validate_text_field(password, MAX_PASSWORD_LEN, "The password")


def validate_notes(notes: str) -> list[str]:
    return validate_text_field(notes, MAX_NOTES_LEN, "The notes")


_DANGEROUS_SCHEMES = {
    "javascript", "vbscript", "data", "file", "blob", "about", "jar", "feed",
    "view-source", "resource", "chrome", "ms-msdt", "ms-htmlfile", "search-ms",
    "ftp", "mailto", "tel", "ldap", "ldaps", "sftp", "smb", "ws", "wss", "gopher",
}

_SLASH_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*)://")
_BARE_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):")


def _looks_like_host_port(text: str) -> bool:
    m = _BARE_SCHEME_RE.match(text)
    if not m:
        return False
    return bool(re.match(r"^\d+", text[m.end():]))


def _candidate(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    m = _SLASH_SCHEME_RE.match(url)
    if m:
        scheme = m.group(1).lower()
        return url if scheme in ALLOWED_URL_SCHEMES else ""
    m = _BARE_SCHEME_RE.match(url)
    if m:
        scheme = m.group(1).lower()
        if scheme in _DANGEROUS_SCHEMES or not _looks_like_host_port(url):
            return ""
    return "https://" + url


def sanitize_url(raw: str) -> str | None:
    """Return a safe absolute http(s) URL or None if it cannot be one."""
    candidate = _candidate(raw or "")
    if not candidate:
        return None
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    if parsed.scheme not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        return None
    if any(ord(ch) <= 32 for ch in candidate) or "@" in parsed.netloc:
        return None
    return candidate


def validate_website(website: str) -> list[str]:
    if not website.strip():
        return []
    if sanitize_url(website) is None:
        return [
            "The website must be a valid http:// or https:// URL "
            "(other schemes such as file: or javascript: are rejected)."
        ]
    return []


def validate_category(category: str) -> list[str]:
    return validate_text_field(category, 60, "The category")
