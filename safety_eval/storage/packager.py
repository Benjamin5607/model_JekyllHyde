"""Build single-file install archive for end-user download."""

from __future__ import annotations

import gzip
import json
import threading
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIST = ROOT / "dist"

RELEASE_VERSION = "1.1.0"
RELEASE_NAME = f"JekyllHyde-{RELEASE_VERSION}-win64"
APP_ZIP_NAME = f"JekyllHyde-{RELEASE_VERSION}-app.zip"
MODEL_PART_PREFIX = f"JekyllHyde-{RELEASE_VERSION}-model.part"
GITHUB_MAX_PART_BYTES = 1_900_000_000
COMPRESS_LEVEL = 9
PROGRESS_EVERY_SEC = 3.0

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


def release_info() -> dict:
    return {
        "version": RELEASE_VERSION,
        "name": RELEASE_NAME,
        "compresslevel": COMPRESS_LEVEL,
        "filename_full": f"{RELEASE_NAME}.zip",
        "filename_app": APP_ZIP_NAME,
        "model_parts_prefix": MODEL_PART_PREFIX,
        "published": datetime.now(UTC).isoformat(),
    }


def _should_skip(rel: str) -> bool:
    rel_norm = rel.replace("\\", "/").lower()
    return any(x in rel_norm for x in EXCLUDE_GLOBS)


def _fmt_bytes(n: int) -> str:
    if n >= 1024**3:
        return f"{n / 1024**3:.2f} GB"
    return f"{n / 1024**2:.1f} MB"


def _progress_loop(label: str, total: int, state: dict, stop: threading.Event) -> None:
    start = state["start"]
    while not stop.wait(PROGRESS_EVERY_SEC):
        done = state.get("done", 0)
        elapsed = time.time() - start
        pct = 100.0 * done / total if total else 0.0
        rate = done / elapsed / (1024**2) if elapsed > 0 else 0.0
        extra = ""
        if "zip_bytes" in state:
            extra = f" | archive {_fmt_bytes(state['zip_bytes'])}"
        print(
            f"   [{label}] {pct:5.1f}% | {_fmt_bytes(done)}/{_fmt_bytes(total)}"
            f" | {rate:.1f} MB/s | {elapsed:.0f}s{extra}",
            flush=True,
        )


def _gzip_chunk_with_progress(data: bytes, dest: Path, *, label: str) -> None:
    total = len(data)
    print(f"\n>> Gzip {label} ({_fmt_bytes(total)}) level={COMPRESS_LEVEL} ...", flush=True)
    state = {"done": 0, "start": time.time()}
    stop = threading.Event()
    reporter = threading.Thread(target=_progress_loop, args=(label, total, state, stop), daemon=True)
    reporter.start()

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with gzip.open(tmp, "wb", compresslevel=COMPRESS_LEVEL) as gz:
        step = 4 * 1024 * 1024
        for i in range(0, total, step):
            gz.write(data[i : i + step])
            state["done"] = min(i + step, total)

    stop.set()
    reporter.join(timeout=1.0)
    tmp.replace(dest)
    elapsed = time.time() - state["start"]
    print(f"   Done {dest.name}: {_fmt_bytes(dest.stat().st_size)} in {elapsed:.0f}s", flush=True)


def _add_file_to_zip_with_progress(
    zf: zipfile.ZipFile,
    abs_path: Path,
    arcname: str,
    *,
    zip_path: Path,
) -> None:
    size = abs_path.stat().st_size
    if size < 50_000_000:
        zf.write(abs_path, arcname, compress_type=zipfile.ZIP_DEFLATED)
        return

    print(f"\n>> ZIP deflate {abs_path.name} ({_fmt_bytes(size)}) level={COMPRESS_LEVEL} ...", flush=True)
    state: dict = {"done": 0, "start": time.time(), "zip_bytes": 0}
    stop = threading.Event()

    def report() -> None:
        while not stop.wait(PROGRESS_EVERY_SEC):
            if zip_path.exists():
                state["zip_bytes"] = zip_path.stat().st_size
            done = state.get("done", 0)
            elapsed = time.time() - state["start"]
            pct = 100.0 * done / size if size else 0.0
            rate = done / elapsed / (1024**2) if elapsed > 0 else 0.0
            print(
                f"   [{abs_path.name}] {pct:5.1f}% | {_fmt_bytes(done)}/{_fmt_bytes(size)}"
                f" | {rate:.1f} MB/s | archive {_fmt_bytes(state.get('zip_bytes', 0))}"
                f" | {elapsed:.0f}s",
                flush=True,
            )

    reporter = threading.Thread(target=report, daemon=True)
    reporter.start()

    import zlib

    zip_info = zipfile.ZipInfo(arcname)
    zip_info.compress_type = zipfile.ZIP_DEFLATED
    zip_info.file_size = size

    compressor = zlib.compressobj(COMPRESS_LEVEL, zlib.DEFLATED, -15)
    step = 4 * 1024 * 1024
    with zf.open(zip_info, "w") as dest, abs_path.open("rb") as src:
        while True:
            chunk = src.read(step)
            if not chunk:
                tail = compressor.flush()
                if tail:
                    dest.write(tail)
                break
            dest.write(compressor.compress(chunk))
            state["done"] = state.get("done", 0) + len(chunk)

    stop.set()
    reporter.join(timeout=1.0)
    elapsed = time.time() - state["start"]
    print(f"   Done {abs_path.name} in {elapsed:.0f}s", flush=True)


def _build_zip(zip_path: Path, include_dirs: tuple[str, ...], root_prefix: str) -> dict:
    if zip_path.exists():
        zip_path.unlink()

    manifest: dict = {
        **release_info(),
        "files": [],
        "total_uncompressed_bytes": 0,
        "compression": f"zip-deflate-level-{COMPRESS_LEVEL}",
    }
    file_count = 0

    print(f"\n=== Building {zip_path.name} (compresslevel={COMPRESS_LEVEL}) ===", flush=True)

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=COMPRESS_LEVEL,
    ) as zf:
        def add_file(abs_path: Path, arcname: str) -> None:
            nonlocal file_count
            if _should_skip(arcname):
                return
            size = abs_path.stat().st_size
            if size >= 50_000_000:
                _add_file_to_zip_with_progress(zf, abs_path, arcname, zip_path=zip_path)
            else:
                zf.write(abs_path, arcname, compress_type=zipfile.ZIP_DEFLATED)
                if file_count % 25 == 0:
                    print(f"  [{file_count}] {arcname}", flush=True)
            manifest["files"].append({"path": arcname, "bytes": size})
            manifest["total_uncompressed_bytes"] += size
            file_count += 1

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
    print(f"\n=== {zip_path.name} complete: {_fmt_bytes(manifest['zip_bytes'])} ===\n", flush=True)
    return manifest


def split_model_gzip_parts(out_dir: Path) -> list[Path]:
    """Split model.safetensors and gzip each part at level 9 with progress."""
    model = ROOT / "models" / "merged" / "jekyll-hyde" / "model.safetensors"
    if not model.exists():
        print("WARN: model.safetensors missing", flush=True)
        return []

    parts: list[Path] = []
    idx = 0
    total_size = model.stat().st_size
    print(f"\n=== Model split + gzip (level {COMPRESS_LEVEL}, total {_fmt_bytes(total_size)}) ===", flush=True)

    with model.open("rb") as src:
        while True:
            chunk = src.read(GITHUB_MAX_PART_BYTES)
            if not chunk:
                break
            part_path = out_dir / f"{MODEL_PART_PREFIX}{idx:02d}.gz"
            _gzip_chunk_with_progress(chunk, part_path, label=f"model.part{idx:02d}")
            parts.append(part_path)
            idx += 1

    return parts


def build_install_archive(*, output_dir: Path | None = None, full: bool = True) -> Path:
    out_dir = output_dir or DIST
    out_dir.mkdir(parents=True, exist_ok=True)

    app_zip = out_dir / APP_ZIP_NAME
    app_manifest = _build_zip(app_zip, INCLUDE_DIRS_APP, RELEASE_NAME)

    model_parts = split_model_gzip_parts(out_dir)

    full_zip = out_dir / f"{RELEASE_NAME}.zip"
    full_manifest: dict = {}
    if full:
        full_manifest = _build_zip(full_zip, INCLUDE_DIRS_FULL, RELEASE_NAME)

    release_manifest = {
        **release_info(),
        "app_zip_bytes": app_zip.stat().st_size,
        "full_zip_bytes": full_zip.stat().st_size if full_zip.exists() else 0,
        "model_parts_gz": [p.name for p in model_parts],
        "model_part_bytes": [p.stat().st_size for p in model_parts],
        "app": app_manifest,
        "full": full_manifest,
    }
    meta_path = out_dir / f"{RELEASE_NAME}.manifest.json"
    meta_path.write_text(json.dumps(release_manifest, indent=2), encoding="utf-8")
    return full_zip if full_zip.exists() else app_zip


def main() -> None:
    t0 = time.time()
    print(f"Jekyll & Hyde release packager — compresslevel={COMPRESS_LEVEL}", flush=True)
    path = build_install_archive()
    elapsed = time.time() - t0
    print(f"ALL DONE: {path} ({_fmt_bytes(path.stat().st_size)}) in {elapsed / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
