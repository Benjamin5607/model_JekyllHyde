"""Shared HTTP client settings for free APIs."""

from __future__ import annotations

import httpx

DEFAULT_HEADERS = {
    "User-Agent": "JekyllHyde/1.0 (moderation-research; +https://github.com/)",
    "Accept": "application/json",
}
TIMEOUT = 8.0


def client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers=DEFAULT_HEADERS, follow_redirects=True)
