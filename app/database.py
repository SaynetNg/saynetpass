"""SQLite access layer.

Every query is parameterized; SQL is never constructed from user input.
The database only ever stores encrypted blobs plus non-sensitive metadata.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config
from .utils import get_logger

log = get_logger("database")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_metadata (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    version    INTEGER NOT NULL,
    salt       BLOB    NOT NULL,
    verifier   BLOB    NOT NULL,
    created_at TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kind           TEXT    NOT NULL,
    encrypted_data BLOB    NOT NULL,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_kind ON entries(kind);
"""


class DatabaseError(Exception):
    """User-safe database error. Details are logged, never exposed."""


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else config.VAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None

    # -- lifecycle ---------------------------------------------------------
    def connect(self) -> None:
        if self._conn is not None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        except sqlite3.Error as exc:
            log.error("Failed to open vault database: %s", type(exc).__name__)
            raise DatabaseError("Unable to open the vault database.") from exc

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                log.error("Failed to close vault database cleanly.")
            finally:
                self._conn = None

    @property
    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DatabaseError("The vault database is not open.")
        return self._conn

    # -- vault metadata ----------------------------------------------------
    def get_metadata(self) -> dict | None:
        try:
            row = self._db.execute(
                "SELECT id, version, salt, verifier, created_at "
                "FROM vault_metadata WHERE id = 1"
            ).fetchone()
        except sqlite3.Error as exc:
            log.error("Metadata read failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to read the vault database.") from exc
        if row is None:
            return None
        return {
            "version": int(row["version"]),
            "salt": bytes(row["salt"]),
            "verifier": bytes(row["verifier"]),
            "created_at": str(row["created_at"]),
        }

    def vault_exists(self) -> bool:
        return self.get_metadata() is not None

    def create_vault(self, salt: bytes, verifier: bytes, created_at: str) -> None:
        try:
            self._db.execute(
                "INSERT INTO vault_metadata (id, version, salt, verifier, created_at) "
                "VALUES (1, ?, ?, ?, ?)",
                (config.DB_VERSION, salt, verifier, created_at),
            )
            self._db.commit()
        except sqlite3.IntegrityError as exc:
            self._db.rollback()
            raise DatabaseError("A vault already exists.") from exc
        except sqlite3.Error as exc:
            self._db.rollback()
            log.error("Vault creation failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to create the vault.") from exc

    # -- entries -----------------------------------------------------------
    def add_entry(
        self, kind: str, encrypted_data: bytes, created_at: str, updated_at: str
    ) -> int:
        try:
            cursor = self._db.execute(
                "INSERT INTO entries (kind, encrypted_data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (kind, encrypted_data, created_at, updated_at),
            )
            self._db.commit()
            return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            self._db.rollback()
            log.error("Entry insert failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to save the entry.") from exc

    def update_entry(self, entry_id: int, encrypted_data: bytes, updated_at: str) -> bool:
        try:
            cursor = self._db.execute(
                "UPDATE entries SET encrypted_data = ?, updated_at = ? WHERE id = ?",
                (encrypted_data, updated_at, entry_id),
            )
            self._db.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as exc:
            self._db.rollback()
            log.error("Entry update failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to save changes.") from exc

    def delete_entry(self, entry_id: int) -> bool:
        try:
            cursor = self._db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
            self._db.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as exc:
            self._db.rollback()
            log.error("Entry delete failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to delete the entry.") from exc

    def fetch_entries(self) -> list[sqlite3.Row]:
        try:
            return list(
                self._db.execute(
                    "SELECT id, kind, encrypted_data, created_at, updated_at "
                    "FROM entries ORDER BY id"
                )
            )
        except sqlite3.Error as exc:
            log.error("Entry fetch failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to read vault entries.") from exc

    def entry_count(self) -> int:
        try:
            return int(
                self._db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            )
        except sqlite3.Error as exc:
            log.error("Entry count failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to read the vault database.") from exc

    # -- encrypted backup / restore (the file stays encrypted either way) --
    def backup_to(self, destination: str | Path) -> None:
        try:
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(destination)) as target:
                self._db.backup(target)
        except sqlite3.Error as exc:
            log.error("Backup failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to create the backup.") from exc

    def restore_from(self, source: str | Path) -> None:
        """Replace current contents with another (encrypted) vault database."""
        src_path = Path(source)
        if not src_path.is_file():
            raise DatabaseError("The selected backup file was not found.")
        try:
            with sqlite3.connect(str(src_path), uri=False) as origin:
                row = origin.execute(
                    "SELECT salt FROM vault_metadata WHERE id = 1"
                ).fetchone()
                if row is None:
                    raise DatabaseError("That file is not a valid encrypted vault.")
                origin.backup(self._db)
            self._db.commit()
        except DatabaseError:
            raise
        except sqlite3.Error as exc:
            log.error("Restore failed: %s", type(exc).__name__)
            raise DatabaseError("Unable to restore that backup.") from exc
