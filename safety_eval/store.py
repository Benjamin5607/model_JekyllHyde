"""Shared guidelines store for chat, MCP, and CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from safety_eval.guidelines import CommunityGuidelines, load_guidelines

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_GUIDELINES = DATA_DIR / "community_guidelines.md"
ACTIVE_GUIDELINES = DATA_DIR / "active_guidelines.md"
ACTIVE_META = DATA_DIR / "active_guidelines.meta.json"


@dataclass
class StoredGuidelines:
    title: str
    text: str
    source: str
    updated_at: str

    def to_guidelines(self) -> CommunityGuidelines:
        ACTIVE_GUIDELINES.write_text(self.text, encoding="utf-8")
        return load_guidelines(ACTIVE_GUIDELINES)


class GuidelinesStore:
    """Cross-process guidelines via active_guidelines.md + meta file."""

    def __init__(self, default_path: Path | None = None):
        self.default_path = default_path or DEFAULT_GUIDELINES
        self._title = "Community Guidelines"
        self._text = ""
        self._source = str(self.default_path)
        self._updated_at = ""
        self._loaded_mtime: float = 0.0
        if ACTIVE_GUIDELINES.exists() and ACTIVE_META.exists():
            self._reload_from_disk()
        elif self.default_path.exists():
            self.load_file(self.default_path)

    def _write_meta(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE_META.write_text(
            json.dumps(
                {
                    "title": self._title,
                    "source": self._source,
                    "updated_at": self._updated_at,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _reload_from_disk(self) -> None:
        if not ACTIVE_GUIDELINES.exists():
            return
        mtime = ACTIVE_GUIDELINES.stat().st_mtime
        if mtime <= self._loaded_mtime and self._text:
            return
        self._text = ACTIVE_GUIDELINES.read_text(encoding="utf-8")
        self._loaded_mtime = mtime
        if ACTIVE_META.exists():
            meta = json.loads(ACTIVE_META.read_text(encoding="utf-8"))
            self._title = meta.get("title", self._title)
            self._source = meta.get("source", self._source)
            self._updated_at = meta.get("updated_at", self._updated_at)
        else:
            loaded = load_guidelines(ACTIVE_GUIDELINES)
            self._title = loaded.title
            self._updated_at = datetime.now(UTC).isoformat()

    @property
    def text(self) -> str:
        self._reload_from_disk()
        return self._text

    @property
    def title(self) -> str:
        self._reload_from_disk()
        return self._title

    def snapshot(self) -> StoredGuidelines:
        self._reload_from_disk()
        return StoredGuidelines(
            title=self._title,
            text=self._text,
            source=self._source,
            updated_at=self._updated_at,
        )

    def set_text(self, text: str, *, title: str = "Custom Guidelines", source: str = "mcp") -> StoredGuidelines:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Guidelines text cannot be empty.")
        self._text = cleaned
        self._title = title
        self._source = source
        self._updated_at = datetime.now(UTC).isoformat()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE_GUIDELINES.write_text(cleaned, encoding="utf-8")
        self._loaded_mtime = ACTIVE_GUIDELINES.stat().st_mtime
        self._write_meta()
        return self.snapshot()

    def load_file(self, path: str | Path) -> StoredGuidelines:
        path = Path(path)
        loaded = load_guidelines(path)
        return self.set_text(loaded.text, title=loaded.title, source=str(path.resolve()))

    def has_mcp_guidelines(self) -> bool:
        """True only when guidelines were pushed via MCP (not default file / platform)."""
        snap = self.snapshot()
        return snap.source == "mcp" and bool(snap.text.strip())

    def active_path(self) -> Path:
        self._reload_from_disk()
        if not ACTIVE_GUIDELINES.exists() and self._text:
            ACTIVE_GUIDELINES.write_text(self._text, encoding="utf-8")
            self._write_meta()
        return ACTIVE_GUIDELINES if ACTIVE_GUIDELINES.exists() else self.default_path


_store: GuidelinesStore | None = None


def get_guidelines_store() -> GuidelinesStore:
    global _store
    if _store is None:
        _store = GuidelinesStore()
    return _store
