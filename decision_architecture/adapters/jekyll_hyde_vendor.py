"""Optional adapter: use vendor/model_JekyllHyde duel when installed on PYTHONPATH."""

from __future__ import annotations

from pathlib import Path
from typing import Any


VENDOR_ROOT = Path(__file__).resolve().parents[4] / "vendor" / "model_JekyllHyde"


def vendor_available() -> bool:
    return (VENDOR_ROOT / "safety_eval").is_dir()


def try_import_jekyll_hyde() -> dict[str, Any]:
    """
    Soft-link to the existing dual-persona product.

    Decision Architecture stays dependency-light; GPU / LoRA stacks live in vendor.
    """
    if not vendor_available():
        return {"available": False, "path": str(VENDOR_ROOT)}
    import sys

    root = str(VENDOR_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from safety_eval.jekyll_hyde import HYDE, JEKYLL, TAGLINE
        from safety_eval.platform.persona import JEKYLL_PERSONA, HYDE_PERSONA

        return {
            "available": True,
            "path": root,
            "jekyll": JEKYLL,
            "hyde": HYDE,
            "tagline": TAGLINE,
            "jekyll_persona_prompt": JEKYLL_PERSONA[:120],
            "hyde_persona_prompt": HYDE_PERSONA[:120],
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "path": root, "error": str(exc)}
