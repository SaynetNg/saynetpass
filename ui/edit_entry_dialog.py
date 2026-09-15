"""Edit dialog: pre-filled EntryDialog that re-encrypts on save."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.models import Entry

from .add_entry_dialog import EntryDialog


class EditEntryDialog(EntryDialog):
    def __init__(
        self,
        categories: list[str],
        entry: Entry,
        parent: QWidget | None = None,
        *,
        settings=None,
    ) -> None:
        super().__init__(categories, parent, settings=settings, entry=entry)
