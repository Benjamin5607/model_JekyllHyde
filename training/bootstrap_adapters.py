"""Bootstrap jekyll-lora / hyde-lora from legacy single adapter when missing."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY = ROOT / "models" / "adapters" / "jekyll-hyde-lora"
ADAPTER_DIRS = {
    "jekyll": ROOT / "models" / "adapters" / "jekyll-lora",
    "hyde": ROOT / "models" / "adapters" / "hyde-lora",
}


def adapter_ready(path: Path) -> bool:
    return (path / "adapter_config.json").exists()


def bootstrap_dual_adapters() -> dict[str, str]:
    """Copy legacy adapter into missing persona dirs. Returns status per persona."""
    status: dict[str, str] = {}
    if not adapter_ready(LEGACY):
        for name, path in ADAPTER_DIRS.items():
            status[name] = "ready" if adapter_ready(path) else "missing"
        return status

    for name, dest in ADAPTER_DIRS.items():
        if adapter_ready(dest):
            status[name] = "ready"
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(LEGACY, dest)
        status[name] = "bootstrapped"
    return status


def main() -> None:
    result = bootstrap_dual_adapters()
    for persona, state in result.items():
        print(f"{persona}: {state}")


if __name__ == "__main__":
    main()
