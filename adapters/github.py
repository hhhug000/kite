"""GitHub adapter: use public GitHub API to fetch profile data."""
from __future__ import annotations

from typing import Dict, Optional
from .base import _require_requests, canonical_fields

def fetch(username: str, token: Optional[str] = None) -> Dict:
    """Fetch GitHub profile via `https://api.github.com/users/{username}`.

    If `token` is provided it will be used as a Bearer token to increase rate limits.
    The adapter also checks the `GITHUB_TOKEN` env var when `token` is not supplied.
    """
    _require_requests()
    import requests
    import os

    # allow token via env for convenience
    token = token or os.environ.get("GITHUB_TOKEN")

    url = f"https://api.github.com/users/{username}"
    headers = {"User-Agent": "kite/0.1 (+https://github.com/hhhug000/kite)"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 404:
        raise RuntimeError("not found")
    resp.raise_for_status()
    j = resp.json()

    data: Dict[str, Optional[str]] = {
        "display_name": j.get("name"),
        "bio": j.get("bio"),
        "location": j.get("location"),
        "email": j.get("email"),
        "avatar_url": j.get("avatar_url"),
        "created_at": j.get("created_at"),
        "public_repos": j.get("public_repos"),
        "followers": j.get("followers"),
    }

    return canonical_fields("GitHub", username, f"https://github.com/{username}", data)
