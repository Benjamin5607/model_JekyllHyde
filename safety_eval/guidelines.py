"""Community guidelines loading and parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GuidelineSection:
    id: str
    title: str
    body: str


@dataclass(frozen=True)
class CommunityGuidelines:
    title: str
    text: str
    source_path: str
    sections: tuple[GuidelineSection, ...]

    def section_titles(self) -> list[str]:
        return [s.title for s in self.sections]

    def get_section(self, title: str) -> GuidelineSection | None:
        lowered = title.lower()
        for section in self.sections:
            if section.title.lower() == lowered or section.id.lower() == lowered:
                return section
        return None


def load_guidelines(path: str | Path) -> CommunityGuidelines:
    path = Path(path)
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Guidelines file is empty: {path}")

    title = path.stem.replace("_", " ").title()
    title_match = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()

    sections = _parse_sections(raw)
    return CommunityGuidelines(
        title=title,
        text=raw,
        source_path=str(path.resolve()),
        sections=tuple(sections),
    )


def _parse_sections(text: str) -> list[GuidelineSection]:
    pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    sections: list[GuidelineSection] = []
    for index, match in enumerate(matches):
        section_title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        section_id = re.sub(r"[^a-z0-9]+", "-", section_title.lower()).strip("-")
        sections.append(GuidelineSection(id=section_id, title=section_title, body=body))

    return sections
