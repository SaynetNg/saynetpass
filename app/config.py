"""Application configuration: paths, constants, persisted user settings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "saynet.ng Password Manager"
APP_VERSION = "1.0.0"
DB_VERSION = 1

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VAULT_DB_PATH = DATA_DIR / "vault.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
LOG_PATH = DATA_DIR / "app.log"

DEFAULT_CATEGORIES = [
    "Personal",
    "Work",
    "Finance",
    "Social",
    "Development",
    "Shopping",
    "Other",
]

AUTO_LOCK_CHOICES_MINUTES = [0, 1, 5, 10, 30]

MIN_MASTER_PASSWORD_LENGTH = 10
MIN_MASTER_PASSWORD_SCORE = 45


@dataclass
class Settings:
    theme: str = "dark"
    auto_lock_minutes: int = 5
    clipboard_timeout_seconds: int = 30
    generator_length: int = 20
    generator_uppercase: bool = True
    generator_lowercase: bool = True
    generator_digits: bool = True
    generator_symbols: bool = True
    generator_exclude_ambiguous: bool = False


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def load_settings(path: Path | None = None) -> Settings:
    path = path or SETTINGS_PATH
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return Settings()
    known = {f.name: f for f in fields(Settings)}
    values = {}
    for key, value in raw.items():
        field = known.get(key)
        if field is None:
            continue
        expected = getattr(Settings(), key)
        try:
            if isinstance(expected, bool):
                values[key] = bool(value)
            elif isinstance(expected, int):
                values[key] = int(value)
            else:
                values[key] = str(value)
        except (TypeError, ValueError):
            continue
    return Settings(**values)


def save_settings(settings: Settings, path: Path | None = None) -> bool:
    path = path or SETTINGS_PATH
    try:
        ensure_data_dir()
        path.write_text(json.dumps(asdict(settings), indent=2), "utf-8")
        return True
    except OSError:
        return False
