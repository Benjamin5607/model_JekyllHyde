"""Load secrets/.env into os.environ (gitignored)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
_ENV = ROOT / "secrets" / ".env"
_LOADED = False


def load_secrets() -> bool:
    global _LOADED
    if _LOADED or not _ENV.exists():
        return _LOADED
    for line in _ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and val and key not in os.environ:
            os.environ[key] = val
    _LOADED = True
    return True


load_secrets()
