"""Build single-file install archive for end-user download."""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIST = ROOT / "dist"

RELEASE_VERSION = "1.0.0"
RELEASE_NAME = f"JekyllHyde-{RELEASE_VERSION}-win64"

INCLUDE_DIRS = (
    "safety_eval",
    "training",
    "scripts",
    "config",
    "data",
    "models/merged/jekyll-hyde",
)

INCLUDE_FILES = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
)

EXCLUDE_GLOBS = (
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.pytest_cache/**",
    "data/archive/**",
    "data/learning/interactions.jsonl",
    "data/learning/rejected.jsonl",
    "secrets/**",
    "**/.git/**",
)


def release_info() -> dict:
    return {
        "version": RELEASE_VERSION,
        "name": RELEASE_NAME,
        "filename": f"{RELEASE_NAME}.zip",
        "published": datetime.now(UTC).isoformat(),
    }


def _should_skip(rel: str) -> bool:
    rel_norm = rel.replace("\\", "/")
    for pat in EXCLUDE_GLOBS:
        pat_norm = pat.replace("\\", "/").replace("**/", "")
        if pat_norm.endswith("/**"):
            prefix = pat_norm[:-3]
            if rel_norm.startswith(prefix):
                return True
        elif pat_norm in rel_norm:
            return True
    return False


def build_install_archive(*, output_dir: Path | None = None) -> Path:
    """Create max-compression ZIP with app + merged model."""
    out_dir = output_dir or DIST
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{RELEASE_NAME}.zip"
    manifest = {
        **release_info(),
        "files": [],
        "total_bytes": 0,
    }

    compress = zipfile.ZIP_DEFLATED
    kwargs: dict = {"compression": compress, "compresslevel": 9}
    with zipfile.ZipFile(zip_path, "w", **kwargs) as zf:
        def add_file(abs_path: Path, arcname: str) -> None:
            if _should_skip(arcname):
                return
            zf.write(abs_path, arcname)
            manifest["files"].append(arcname)
            manifest["total_bytes"] += abs_path.stat().st_size

        for name in INCLUDE_FILES:
            p = ROOT / name
            if p.exists():
                add_file(p, f"{RELEASE_NAME}/{name}")

        for rel_dir in INCLUDE_DIRS:
            base = ROOT / rel_dir
            if not base.exists():
                continue
            for fp in base.rglob("*"):
                if fp.is_file():
                    arc = f"{RELEASE_NAME}/{rel_dir}/{fp.relative_to(base).as_posix()}"
                    add_file(fp, arc)

        # Bundled installer scripts
        for script in ("install.ps1", "install.bat", "INSTALL.txt"):
            sp = ROOT / "scripts" / "release" / script
            if sp.exists():
                add_file(sp, f"{RELEASE_NAME}/{script}")

        manifest_json = json.dumps(manifest, indent=2)
        zf.writestr(f"{RELEASE_NAME}/manifest.json", manifest_json)

    meta_path = out_dir / f"{RELEASE_NAME}.manifest.json"
    meta_path.write_text(json.dumps({**manifest, "zip_bytes": zip_path.stat().st_size}, indent=2), encoding="utf-8")
    return zip_path


def main() -> None:
    path = build_install_archive()
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Built: {path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
