"""GitLab adapter: use public GitLab API to resolve user by username."""
from __future__ import annotations

from typing import Dict, Optional
from .base import _require_requests, canonical_fields

def fetch(username: str) -> Dict:
    _require_requests()
    import requests

    # GitLab offers a users endpoint to search by username
    url = f"https://gitlab.com/api/v4/users?username={username}"
    headers = {"User-Agent": "kite/0.1"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    arr = resp.json()
    if not arr:
        raise RuntimeError("not found")
    u = arr[0]
    data: Dict[str, Optional[str]] = {
        "display_name": u.get("name"),
        "username": u.get("username"),
        "avatar_url": u.get("avatar_url"),
        "web_url": u.get("web_url"),
        "created_at": u.get("created_at"),
    }
    return canonical_fields("GitLab", username, u.get("web_url") or f"https://gitlab.com/{username}", data)
