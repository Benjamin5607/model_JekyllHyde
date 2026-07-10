"""Privacy filters for continuous learning — PII masking and secret redaction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"

_MASK = "[REDACTED]"

# PII / secret patterns (extend via config/privacy_keywords.txt)
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone_kr", re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")),
    ("phone_intl", re.compile(r"\+\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")),
    ("ssn_us", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("rrn_kr", re.compile(r"\b\d{6}-[1-4]\d{6}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("api_key", re.compile(r"\b(?:sk|pk|api|ghp|gho|xox)[-_][A-Za-z0-9]{16,}\b", re.I)),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", re.I)),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("wallet", re.compile(r"\b0x[a-fA-F0-9]{40}\b")),
]

_SECRET_KEYWORDS = (
    "confidential", "internal only", "nda", "trade secret", "기밀", "대외비",
    "비밀번호", "password", "passwd", "api_key", "secret_key", "private key",
    "mnemonic", "seed phrase", "고객정보", "주민등록",
)


def _load_privacy_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("privacy", {})


def _extra_keywords(cfg: dict[str, Any]) -> tuple[str, ...]:
    kw_file = cfg.get("keywords_file", "config/privacy_keywords.txt")
    path = ROOT / kw_file
    extra: list[str] = list(cfg.get("extra_keywords", []))
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                extra.append(line)
    return tuple(extra)


@dataclass
class PrivacyReport:
    redactions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"redactions": self.redactions, "count": len(self.redactions)}


def mask_text(text: str, *, cfg: dict[str, Any] | None = None) -> tuple[str, PrivacyReport]:
    """Mask PII and lines containing secret keywords."""
    cfg = cfg or _load_privacy_cfg()
    if not cfg.get("enabled", True):
        return text, PrivacyReport()

    report = PrivacyReport()
    out = text

    if cfg.get("mask_pii", True):
        for label, pat in _PII_PATTERNS:
            if pat.search(out):
                report.redactions.append(label)
                out = pat.sub(_MASK, out)

    keywords = _SECRET_KEYWORDS + _extra_keywords(cfg)
    if cfg.get("mask_secret_keywords", True):
        lines = out.splitlines()
        masked_lines: list[str] = []
        for line in lines:
            low = line.lower()
            if any(kw in low for kw in keywords):
                report.redactions.append("secret_keyword_line")
                masked_lines.append(_MASK)
            else:
                masked_lines.append(line)
        out = "\n".join(masked_lines)

    return out, report


def sanitize_record(rec: dict[str, Any], *, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a copy of a training record with user/assistant text masked."""
    cfg = cfg or _load_privacy_cfg()
    if not cfg.get("enabled", True):
        return rec

    out = dict(rec)
    messages = []
    total_redactions: list[str] = []

    for msg in rec.get("messages", []):
        m = dict(msg)
        content = str(m.get("content") or "")
        masked, rep = mask_text(content, cfg=cfg)
        if rep.redactions:
            total_redactions.extend(rep.redactions)
        m["content"] = masked
        messages.append(m)
    out["messages"] = messages

    for key in ("user", "assistant"):
        if key in out and out[key]:
            masked, rep = mask_text(str(out[key]), cfg=cfg)
            if rep.redactions:
                total_redactions.extend(rep.redactions)
            out[key] = masked

    if total_redactions:
        meta = dict(out.get("meta") or {})
        meta["privacy_redactions"] = sorted(set(total_redactions))
        out["meta"] = meta
    return out


def sanitize_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Batch sanitize; returns (records, redacted_count)."""
    cfg = _load_privacy_cfg()
    if not cfg.get("enabled", True):
        return records, 0
    out: list[dict[str, Any]] = []
    redacted = 0
    for rec in records:
        clean = sanitize_record(rec, cfg=cfg)
        if (clean.get("meta") or {}).get("privacy_redactions"):
            redacted += 1
        out.append(clean)
    return out, redacted
