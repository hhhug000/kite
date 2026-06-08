"""Keybase adapter using Keybase public lookup API."""
from __future__ import annotations

from typing import Dict, Optional
from .base import _require_requests, canonical_fields


def fetch(username: str) -> Dict:
    _require_requests()
    import requests

    url = f"https://keybase.io/_/api/1.0/user/lookup.json?username={username}"
    headers = {"User-Agent": "kite/0.1"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    j = resp.json()
    them = j.get("them", [])
    if not them:
        raise RuntimeError("not found")
    user = them[0]
    profile = user.get("profile", {})

    data: Dict[str, Optional[str]] = {
        "display_name": profile.get("full_name") or user.get("basics", {}).get("username"),
        "bio": profile.get("bio"),
        "location": profile.get("location"),
        "avatar_url": profile.get("pictures", [{}])[0].get("url") if profile.get("pictures") else None,
    }

    return canonical_fields("Keybase", username, f"https://keybase.io/{username}", data)
