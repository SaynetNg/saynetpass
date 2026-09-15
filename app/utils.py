"""Shared helpers: time, paths, secret-safe logging, password-strength analysis."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from . import config

SECRET_PLACEHOLDER = "[redacted]"

_STRENGTH_LEVELS = ("Very Weak", "Weak", "Fair", "Strong", "Very Strong")

_COMMON_PASSWORDS = {
    "password", "passwort", "123456", "12345678", "123456789", "12345", "1234567",
    "qwerty", "qwerty123", "abc123", "111111", "000000", "iloveyou", "admin",
    "letmein", "welcome", "monkey", "dragon", "master", "sunshine", "princess",
    "football", "baseball", "soccer", "hockey", "superman", "batman", "trustno1",
    "hello", "charlie", "donald", "password1", "password123", "qwertyuiop",
    "zaq12wsx", "passw0rd", "p@ssword", "p@ssw0rd", "changeme", "secret",
    "whatever", "starwars", "michael", "jennifer", "jordan", "hunter2", "buster",
    "ginger", "summer", "winter", "banana", "tinkle", "1q2w3e4r", "1qaz2wsx",
    "123qwe", "qazwsx", "killer", "money", "test", "guest", "root", "toor",
}

_DICTIONARY_PARTS = (
    "password", "passwort", "login", "admin", "welcome", "master", "secret",
    "dragon", "monkey", "shadow", "sunshine", "princess", "superman", "batman",
    "trustno", "letmein", "football", "baseball", "hunter", "guitar", "pocket",
)

_SEQUENCE_SOURCES = (
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)

_RE_TRIPLE = re.compile(r"(.)\1\1")
_RE_DOUBLE_PAIR = re.compile(r"(.{1,2})\1\1")
_RE_NUMERIC_RUN = re.compile(r"\d{5,}")
_RE_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passphrase|master_password|secret|token|api[_-]?key|"
    r"private[_-]?key|encryption[_-]?key)\b(\s*[=:]\s*)(\S+)"
)


@dataclass(frozen=True)
class PasswordStrength:
    score: int
    level: int
    label: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def monotonic() -> float:
    return time.monotonic()


def _contains_sequence(value: str) -> bool:
    for source in _SEQUENCE_SOURCES:
        for start in range(len(source) - 3):
            fragment = source[start : start + 4]
            if fragment in value or fragment[::-1] in value:
                return True
    return False


def evaluate_password_strength(password: str) -> PasswordStrength:
    """Advisory heuristic strength estimate (not a cryptographic guarantee).

    Considers length, character-class diversity, unique-character ratio,
    keyboard/dictionary sequences, repeats, and a small common-password list.
    """
    n = len(password)
    if n == 0:
        return PasswordStrength(0, 0, _STRENGTH_LEVELS[0])

    lowered = password.lower()
    classes = sum(
        bool(re.search(cls, password))
        for cls in (r"[A-Z]", r"[a-z]", r"[0-9]", r"[^A-Za-z0-9]")
    )

    if n >= 24:
        length_score = 5
    elif n >= 18:
        length_score = 4
    elif n >= 14:
        length_score = 3
    elif n >= 10:
        length_score = 2
    elif n >= 6:
        length_score = 1
    else:
        length_score = 0

    raw = length_score + max(0, classes - 1)
    if classes >= 3 and n >= 12 and len(set(password)) * 2 >= n + 2:
        raw += 1
    if lowered in _COMMON_PASSWORDS:
        raw = 0
    if lowered in _DICTIONARY_PARTS:
        raw -= 2
    if any(word in lowered for word in _DICTIONARY_PARTS if len(word) > 4):
        raw -= 2
    if _contains_sequence(password):
        raw -= 2
    if _RE_TRIPLE.search(password):
        raw -= 1
    if _RE_DOUBLE_PAIR.search(password):
        raw -= 1
    if _RE_NUMERIC_RUN.search(password):
        raw -= 1
    if classes <= 1:
        raw -= 1

    score = max(0, min(8, raw)) * 14

    if n < 6:
        score = min(score, 30)
    elif n < 10:
        score = min(score, 39)
    elif n < 12:
        score = min(score, 59)
    elif n < 16:
        score = min(score, 74)
    if n >= 24 and classes >= 4:
        score = max(score, 80)

    if score >= 80:
        level = 4
    elif score >= 60:
        level = 3
    elif score >= 40:
        level = 2
    elif score >= 20:
        level = 1
    else:
        level = 0
    return PasswordStrength(score, level, _STRENGTH_LEVELS[level])


def redact(text: str) -> str:
    """Scrub registered secrets and password-looking assignments from text."""
    result = text
    _redact_registered(result)  # ensures a debug helper never crashes logging
    return _scrub(result)


_SECRET_VALUES: set[str] = set()


def _scrub(text: str) -> str:
    text = _RE_SENSITIVE_ASSIGNMENT.sub(
        lambda m: m.group(1) + m.group(2) + SECRET_PLACEHOLDER, text
    )
    for secret in _SECRET_VALUES:
        if secret:
            text = text.replace(secret, SECRET_PLACEHOLDER)
    return text


def _redact_registered(text: str) -> str:
    return _scrub(text)


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            try:
                record.msg = record.getMessage()
            except Exception:  # pragma: no cover - defensive
                pass
            record.args = ()
        record.msg = _scrub(str(record.msg))
        return True


def register_secret(value: str) -> None:
    """Register a plaintext value that must never appear in logs."""
    if value and len(value) >= 3:
        _SECRET_VALUES.add(value)


def clear_registered_secrets() -> None:
    _SECRET_VALUES.clear()


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("password_manager")
    if logger.handlers:
        return logger
    logger.setLevel(level)
    logger.addFilter(_RedactFilter())
    try:
        config.ensure_data_dir()
        handler: logging.Handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler.addFilter(_RedactFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str = "core") -> logging.Logger:
    logger = logging.getLogger(f"password_manager.{name}")
    if not logging.getLogger("password_manager").handlers:
        configure_logging()
    return logger


def detect_system_theme() -> str:
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value else "dark"
    except Exception:
        return "light"


def resolve_theme(theme: str) -> str:
    if theme == "system":
        return detect_system_theme()
    return "light" if theme == "light" else "dark"
