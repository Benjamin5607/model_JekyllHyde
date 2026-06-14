"""Build single-file install archive for end-user download."""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIST = ROOT / "dist"

RELEASE_VERSION = "1.0.0"
RELEASE_NAME = f"JekyllHyde-{RELEASE_VERSION}-win64"
APP_ZIP_NAME = f"JekyllHyde-{RELEASE_VERSION}-app.zip"
MODEL_PART_PREFIX = f"JekyllHyde-{RELEASE_VERSION}-model.part"
GITHUB_MAX_PART_BYTES = 1_900_000_000  # GitHub release asset limit ~2 GB

INCLUDE_DIRS_APP = (
    "safety_eval",
    "training",
    "scripts",
    "config",
    "data",
)

INCLUDE_DIRS_FULL = INCLUDE_DIRS_APP + ("models/merged/jekyll-hyde",)

INCLUDE_FILES = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "requirements.txt",
)

EXCLUDE_GLOBS = (
    "__pycache__",
    ".pytest_cache",
    "data/archive",
    "data/learning/interactions.jsonl",
    "data/learning/rejected.jsonl",
    "secrets",
    ".git",
)

# Already compressed / huge — store without re-compressing (much faster)
STORE_SUFFIXES = {".safetensors", ".bin", ".pt", ".pth", ".onnx"}


def release_info() -> dict:
    return {
        "version": RELEASE_VERSION,
        "name": RELEASE_NAME,
        "filename_full": f"{RELEASE_NAME}.zip",
        "filename_app": APP_ZIP_NAME,
        "model_parts_prefix": MODEL_PART_PREFIX,
        "published": datetime.now(UTC).isoformat(),
    }


def _should_skip(rel: str) -> bool:
    rel_norm = rel.replace("\\", "/").lower()
    return any(x in rel_norm for x in EXCLUDE_GLOBS)


def _compress_type(path: Path) -> int:
    if path.suffix.lower() in STORE_SUFFIXES:
        return zipfile.ZIP_STORED
    if path.name == "tokenizer.json" and path.stat().st_size > 5_000_000:
        return zipfile.ZIP_STORED
    return zipfile.ZIP_DEFLATED


def _build_zip(zip_path: Path, include_dirs: tuple[str, ...], root_prefix: str) -> dict:
    if zip_path.exists():
        zip_path.unlink()
    manifest: dict = {**release_info(), "files": [], "total_uncompressed_bytes": 0}
    file_count = 0

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        def add_file(abs_path: Path, arcname: str) -> None:
            nonlocal file_count
            if _should_skip(arcname):
                return
            ctype = _compress_type(abs_path)
            size = abs_path.stat().st_size
            zf.write(abs_path, arcname, compress_type=ctype)
            manifest["files"].append({"path": arcname, "bytes": size})
            manifest["total_uncompressed_bytes"] += size
            file_count += 1
            if file_count % 25 == 0 or size > 100_000_000:
                print(f"  [{file_count}] {arcname} ({size / (1024**2):.1f} MB)", flush=True)

        for name in INCLUDE_FILES:
            p = ROOT / name
            if p.exists():
                add_file(p, f"{root_prefix}/{name}")

        for rel_dir in include_dirs:
            base = ROOT / rel_dir
            if not base.exists():
                print(f"WARN: missing {rel_dir}", flush=True)
                continue
            for fp in sorted(base.rglob("*")):
                if fp.is_file():
                    arc = f"{root_prefix}/{rel_dir}/{fp.relative_to(base).as_posix()}"
                    add_file(fp, arc)

        for script in ("install.ps1", "install.bat", "INSTALL.txt"):
            sp = ROOT / "scripts" / "release" / script
            if sp.exists():
                add_file(sp, f"{root_prefix}/{script}")

        manifest["file_count"] = file_count
        zf.writestr(f"{root_prefix}/manifest.json", json.dumps(manifest, indent=2))

    manifest["zip_bytes"] = zip_path.stat().st_size
    return manifest


def split_model_for_github(out_dir: Path) -> list[Path]:
    """Split model.safetensors into <=1.9GB parts for GitHub Releases."""
    model = ROOT / "models" / "merged" / "jekyll-hyde" / "model.safetensors"
    if not model.exists():
        return []
    parts: list[Path] = []
    idx = 0
    with model.open("rb") as src:
        while True:
            chunk = src.read(GITHUB_MAX_PART_BYTES)
            if not chunk:
                break
            part_path = out_dir / f"{MODEL_PART_PREFIX}{idx:02d}"
            part_path.write_bytes(chunk)
            parts.append(part_path)
            print(f"  model part {idx}: {part_path.name} ({len(chunk)/(1024**2):.1f} MB)", flush=True)
            idx += 1
    return parts


def build_install_archive(*, output_dir: Path | None = None, full: bool = True) -> Path:
    """Create install archives for local (full) and GitHub (app + model parts)."""
    out_dir = output_dir or DIST
    out_dir.mkdir(parents=True, exist_ok=True)

    app_zip = out_dir / APP_ZIP_NAME
    print(f"Building {APP_ZIP_NAME} ...", flush=True)
    app_manifest = _build_zip(app_zip, INCLUDE_DIRS_APP, RELEASE_NAME)

    print("Splitting model for GitHub ...", flush=True)
    model_parts = split_model_for_github(out_dir)

    full_zip = out_dir / f"{RELEASE_NAME}.zip"
    if full:
        print(f"Building {full_zip.name} (local all-in-one) ...", flush=True)
        full_manifest = _build_zip(full_zip, INCLUDE_DIRS_FULL, RELEASE_NAME)
    else:
        full_manifest = {}

    release_manifest = {
        **release_info(),
        "app_zip_bytes": app_zip.stat().st_size,
        "full_zip_bytes": full_zip.stat().st_size if full_zip.exists() else 0,
        "model_parts": [p.name for p in model_parts],
        "model_part_bytes": [p.stat().st_size for p in model_parts],
        "app": app_manifest,
        "full": full_manifest,
    }
    meta_path = out_dir / f"{RELEASE_NAME}.manifest.json"
    meta_path.write_text(json.dumps(release_manifest, indent=2), encoding="utf-8")
    return full_zip if full_zip.exists() else app_zip


def main() -> None:
    print(f"Building {RELEASE_NAME}.zip ...", flush=True)
    path = build_install_archive()
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Built: {path} ({size_mb:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
