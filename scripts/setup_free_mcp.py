#!/usr/bin/env python3
"""Merge free no-key MCP servers into .cursor/mcp.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_JSON = ROOT / ".cursor" / "mcp.json"
CONFIG = ROOT / "config" / "verification_providers.yaml"


def main() -> None:
    import yaml

    with CONFIG.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    existing: dict = {"mcpServers": {}}
    if MCP_JSON.exists():
        existing = json.loads(MCP_JSON.read_text(encoding="utf-8"))

    servers = existing.setdefault("mcpServers", {})

    # Keep jekyll-hyde as primary
    servers["jekyll-hyde"] = {
        "command": "python",
        "args": ["-m", "safety_eval.mcp.server"],
        "cwd": str(ROOT).replace("\\", "/"),
    }

    for name, spec in (cfg.get("mcp_servers") or {}).items():
        servers[name] = {
            "command": spec["command"],
            "args": spec.get("args", []),
        }

    MCP_JSON.parent.mkdir(parents=True, exist_ok=True)
    MCP_JSON.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {MCP_JSON} with {len(servers)} MCP servers:")
    for n in servers:
        print(f"  - {n}")


if __name__ == "__main__":
    main()
