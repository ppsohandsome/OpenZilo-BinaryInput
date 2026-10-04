from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtWidgets import QWidget

from zilo_ring.state import StoreSnapshot


class AppPage(Protocol):
    page_id: str
    title: str
    subtitle: str

    def refresh(self, snapshot: StoreSnapshot) -> None: ...


@dataclass(frozen=True, slots=True)
class PageEntry:
    page_id: str
    title: str
    subtitle: str
    widget: QWidget


class PageRegistry:
    def __init__(self) -> None:
        self._entries: list[PageEntry] = []

    def register(self, page: QWidget) -> PageEntry:
        page_id = str(getattr(page, "page_id"))
        if any(entry.page_id == page_id for entry in self._entries):
            raise ValueError(f"Duplicate page id: {page_id}")
        entry = PageEntry(
            page_id=page_id,
            title=str(getattr(page, "title")),
            subtitle=str(getattr(page, "subtitle", "")),
            widget=page,
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> tuple[PageEntry, ...]:
        return tuple(self._entries)
