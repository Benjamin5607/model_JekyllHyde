"""Capture platform UI screenshots for README (requires server on :8080)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
BASE = "http://127.0.0.1:8080"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE, wait_until="networkidle", timeout=120_000)

        # Wait for model status (online or loading banner)
        for _ in range(60):
            text = page.locator("#statusText").inner_text(timeout=2000)
            if "연결" not in text and "Connecting" not in text:
                break
            time.sleep(2)
        time.sleep(1)

        def shot(name: str) -> None:
            path = OUT / name
            page.screenshot(path=str(path), full_page=False)
            print(f"  saved {path.relative_to(ROOT)}")

        shot("01-platform-chat.png")

        for mode, fname in (
            ("jekyll", "02-mode-jekyll.png"),
            ("hyde", "03-mode-hyde.png"),
            ("duel", "04-mode-duel.png"),
        ):
            page.locator(f'.seg-btn[data-mode="{mode}"]').click()
            time.sleep(0.6)
            shot(fname)

        page.locator('.seg-btn[data-mode="chat"]').click()
        page.locator("#openSettings").click()
        time.sleep(0.5)
        shot("05-settings-mcp-learning.png")

        # Optional: quick chat if model online
        status = page.locator("#statusText").inner_text()
        if "온라인" in status or "online" in status.lower():
            page.locator("#closeSettings").click()
            page.locator("#input").fill("Who are you? Brief intro in English.")
            page.locator("#send").click()
            page.locator("#typing").wait_for(state="visible", timeout=10_000)
            try:
                page.locator("#typing").wait_for(state="hidden", timeout=180_000)
            except Exception:
                pass
            time.sleep(1)
            shot("06-chat-response.png")

        browser.close()

    print(f"Done -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
