"""Platform UI preferences — language, MCP toggles (persisted locally)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
PREFS_PATH = ROOT / "config" / "platform_prefs.yaml"

UI_LANGUAGES: dict[str, str] = {
    "ko": "한국어",
    "en": "English",
    "ja": "日本語",
    "zh": "中文",
}

JEKYLL_HYDE_MCP_TOOLS: list[dict[str, str]] = [
    {"name": "set_guidelines", "desc": "Set community guidelines (Markdown text)"},
    {"name": "get_guidelines", "desc": "Read active guidelines"},
    {"name": "append_guidelines", "desc": "Append a guideline section"},
    {"name": "chat_with_model", "desc": "Chat with Jekyll/Hyde toggles"},
    {"name": "run_duel_verification", "desc": "Hyde↔Jekyll duel + free API verify"},
    {"name": "verify_text", "desc": "Run verification providers on text"},
    {"name": "analyze_stocks", "desc": "Stock analysis + quant context"},
    {"name": "scan_market_region", "desc": "Regional market scan"},
    {"name": "get_market_weather", "desc": "Global index snapshot"},
    {"name": "list_verification_providers", "desc": "List enabled verification APIs"},
    {"name": "learning_status", "desc": "Continuous learning stats"},
    {"name": "run_continuous_learning", "desc": "Curate feedback + optional retrain"},
    {"name": "delegate_workforce_brief", "desc": "Manager-Worker: enqueue data workers"},
    {"name": "workforce_status", "desc": "Poll workforce job status"},
    {"name": "manager_approve_workforce", "desc": "Manager LLM verdict on worker bundle"},
    {"name": "run_workforce_brief", "desc": "Full delegate → workers → manager pipeline"},
    {"name": "list_workforce_workers", "desc": "List data-only worker types"},
]

DEFAULT_PREFS: dict[str, Any] = {
    "ui_language": "en",
    "mcp": {
        "jekyll_hyde": True,
        "external": {},
    },
    "verification": {},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_prefs() -> dict[str, Any]:
    if not PREFS_PATH.exists():
        return dict(DEFAULT_PREFS)
    with PREFS_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULT_PREFS, data)


def save_prefs(prefs: dict[str, Any]) -> dict[str, Any]:
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = _deep_merge(DEFAULT_PREFS, prefs)
    with PREFS_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, allow_unicode=True, sort_keys=False)
    return merged


def get_ui_language() -> str:
    lang = load_prefs().get("ui_language", "en")
    return lang if lang in UI_LANGUAGES else "en"


def set_ui_language(lang: str) -> str:
    if lang not in UI_LANGUAGES:
        lang = "en"
    prefs = load_prefs()
    prefs["ui_language"] = lang
    save_prefs(prefs)
    return lang


def provider_enabled_override(name: str) -> bool | None:
    overrides = load_prefs().get("verification", {})
    if name in overrides:
        return bool(overrides[name])
    return None


def set_provider_enabled(name: str, enabled: bool) -> None:
    prefs = load_prefs()
    prefs.setdefault("verification", {})[name] = enabled
    save_prefs(prefs)


def external_mcp_enabled(name: str, default: bool = True) -> bool:
    prefs = load_prefs()
    ext = prefs.get("mcp", {}).get("external", {})
    if name in ext:
        return bool(ext[name])
    return default


def set_external_mcp_enabled(name: str, enabled: bool) -> None:
    prefs = load_prefs()
    prefs.setdefault("mcp", {}).setdefault("external", {})[name] = enabled
    save_prefs(prefs)


def jekyll_hyde_mcp_enabled() -> bool:
    return bool(load_prefs().get("mcp", {}).get("jekyll_hyde", True))


def set_jekyll_hyde_mcp(enabled: bool) -> None:
    prefs = load_prefs()
    prefs.setdefault("mcp", {})["jekyll_hyde"] = enabled
    save_prefs(prefs)


def cursor_mcp_snippet() -> dict[str, Any]:
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = ROOT / ".venv-train" / "Scripts" / "python.exe"
    command = str(py) if py.exists() else "python"
    root_s = str(ROOT).replace("\\", "/")
    return {
        "jekyll-hyde": {
            "command": command,
            "args": ["-m", "safety_eval.mcp.server"],
            "cwd": root_s,
        }
    }


def full_cursor_mcp_config() -> dict[str, Any]:
    from safety_eval.verification.registry import list_mcp_servers

    cfg: dict[str, Any] = {}
    if jekyll_hyde_mcp_enabled():
        cfg.update(cursor_mcp_snippet())
    for s in list_mcp_servers():
        name = s["name"]
        if external_mcp_enabled(name, default=True):
            cfg[name] = {"command": s["command"], "args": s.get("args", [])}
    return {"mcpServers": cfg}
