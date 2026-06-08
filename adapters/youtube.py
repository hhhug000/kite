"""YouTube adapter using the oEmbed endpoint for channel/user handles."""
from __future__ import annotations

from typing import Dict, Optional
from .base import _require_requests, canonical_fields


def fetch(username: str) -> Dict:
    _require_requests()
    import requests

    # Try the modern @username format
    probe = f"https://www.youtube.com/@{username}"
    oembed = f"https://www.youtube.com/oembed?url={probe}&format=json"
    headers = {"User-Agent": "kite/0.1"}
    resp = requests.get(oembed, headers=headers, timeout=10)
    if resp.status_code == 404:
        raise RuntimeError("not found")
    resp.raise_for_status()
    j = resp.json()

    data: Dict[str, Optional[str]] = {
        "display_name": j.get("author_name"),
        "author_url": j.get("author_url"),
        "thumbnail_url": j.get("thumbnail_url"),
        "title": j.get("title"),
    }

    return canonical_fields("YouTube", username, j.get("author_url") or probe, data)
