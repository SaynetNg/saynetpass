"""Data models and the in-memory vault session.

`Vault` is the unlocked working set: encrypted rows are decrypted once at
unlock time and every write re-encrypts the full sensitive payload with a
fresh nonce before it reaches SQLite.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from . import config
from .crypto import CryptoError, decrypt_data, encrypt_data
from .database import Database
from .utils import get_logger, utc_now_iso

log = get_logger("models")

KIND_LOGIN = "login"
KIND_NOTE = "note"
ENTRY_KINDS = (KIND_LOGIN, KIND_NOTE)


class VaultError(Exception):
    pass


@dataclass
class Entry:
    id: int
    kind: str = KIND_LOGIN
    title: str = ""
    username: str = ""
    password: str = ""
    website: str = ""
    category: str = "Personal"
    notes: str = ""
    favorite: bool = False
    created_at: str = ""
    updated_at: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "username": self.username,
            "password": self.password,
            "website": self.website,
            "category": self.category,
            "notes": self.notes,
            "favorite": self.favorite,
        }

    def encrypted_blob(self, key: bytes) -> bytes:
        return encrypt_data(json.dumps(self.payload()).encode("utf-8"), key)

    @classmethod
    def from_row(cls, row: sqlite3.Row, key: bytes) -> "Entry":
        data = json.loads(decrypt_data(bytes(row["encrypted_data"]), key).decode("utf-8"))
        kind = str(data.get("kind") or row["kind"] or KIND_LOGIN)
        if kind not in ENTRY_KINDS:
            kind = KIND_LOGIN
        return cls(
            id=int(row["id"]),
            kind=kind,
            title=str(data.get("title", "")),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
            website=str(data.get("website", "")),
            category=str(data.get("category", "Personal")),
            notes=str(data.get("notes", "")),
            favorite=bool(data.get("favorite", False)),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @property
    def is_note(self) -> bool:
        return self.kind == KIND_NOTE

    def preview(self) -> str:
        if self.is_note:
            flat = " ".join(self.notes.split())
            return (flat[:80] + "…") if len(flat) > 80 else (flat or "Empty note")
        return self.username or (self.website or "No username")

    def __repr__(self) -> str:  # never leaks the password
        return f"<Entry #{self.id} {self.title!r} {self.kind}>"


class Vault:
    """An unlocked vault session holding decrypted entries in memory."""

    def __init__(self, database: Database, key: bytes) -> None:
        self._db = database
        self._key: bytes | None = bytes(key) if key else None
        self.entries: list[Entry] = []
        self._load()

    @property
    def is_locked(self) -> bool:
        return self._key is None

    def _load(self) -> None:
        assert self._key is not None
        loaded: list[Entry] = []
        for row in self._db.fetch_entries():
            try:
                loaded.append(Entry.from_row(row, self._key))
            except (CryptoError, ValueError, KeyError) as exc:
                log.error("Entry %s failed verification while loading.", dict(row).get("id"))
                raise VaultError(
                    "The vault could not be decrypted correctly."
                ) from exc
        self.entries = loaded

    # -- CRUD ------------------------------------------------------------
    def create_entry(
        self,
        title: str,
        *,
        kind: str = KIND_LOGIN,
        username: str = "",
        password: str = "",
        website: str = "",
        category: str = "Personal",
        notes: str = "",
        favorite: bool = False,
    ) -> Entry:
        if self._key is None:
            raise VaultError("The vault is locked.")
        if kind not in ENTRY_KINDS:
            kind = KIND_LOGIN
        now = utc_now_iso()
        note_only = kind == KIND_NOTE
        entry = Entry(
            id=0,
            kind=kind,
            title=title.strip(),
            username="" if note_only else username,
            password="" if note_only else password,
            website="" if note_only else website,
            category=category or "Personal",
            notes=notes,
            favorite=bool(favorite),
            created_at=now,
            updated_at=now,
        )
        entry.id = self._db.add_entry(
            entry.kind, entry.encrypted_blob(self._key), entry.created_at, entry.updated_at
        )
        self.entries.append(entry)
        return entry

    def update_entry(self, entry: Entry, **changes: Any) -> Entry:
        if self._key is None:
            raise VaultError("The vault is locked.")
        if entry.id <= 0:
            raise VaultError("Unknown entry.")
        forbidden = {"id", "created_at", "kind"}
        for name, value in changes.items():
            if name in forbidden:
                continue
            if not hasattr(entry, name):
                raise ValueError(f"Unknown entry field: {name}")
            setattr(entry, name, value)
        if entry.is_note:
            entry.username = ""
            entry.password = ""
            entry.website = ""
        entry.updated_at = utc_now_iso()
        if not self._db.update_entry(entry.id, entry.encrypted_blob(self._key), entry.updated_at):
            raise VaultError("Unable to save password.")
        return entry

    def delete_entry(self, entry_id: int) -> bool:
        if self._key is None:
            raise VaultError("The vault is locked.")
        existed = self._db.delete_entry(entry_id)
        self.entries = [e for e in self.entries if e.id != entry_id]
        return existed

    def set_favorite(self, entry: Entry, favorite: bool) -> Entry:
        return self.update_entry(entry, favorite=bool(favorite))

    # -- queries (over decrypted session data only) ----------------------
    def by_id(self, entry_id: int) -> Entry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    def favorite_entries(self) -> list[Entry]:
        return [e for e in self.entries if e.favorite]

    def categories_present(self) -> list[str]:
        present = {e.category for e in self.entries if e.category}
        merged = list(config.DEFAULT_CATEGORIES)
        merged.extend(sorted(c for c in present if c not in merged))
        return merged

    def search(self, term: str) -> list[Entry]:
        needle = term.strip().casefold()
        if not needle:
            return list(self.entries)
        results = []
        for entry in self.entries:
            haystack = " ".join(
                (entry.title, entry.username, entry.website, entry.category, entry.notes)
            ).casefold()
            if needle in haystack:
                results.append(entry)
        return results

    # -- locking -----------------------------------------------------------
    def lock(self) -> None:
        """Drop the key reference and all decrypted data from the session.

        Python cannot guarantee that bytes already allocated are erased from
        RAM; this is a best-effort reduction of the exposure window and is
        documented as a limitation.
        """
        self.entries = []
        self._key = None
