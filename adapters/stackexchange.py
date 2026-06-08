"""StackExchange adapter (StackOverflow)."""
from __future__ import annotations

from typing import Dict, Optional
import time
from .base import _require_requests, canonical_fields


def fetch(username: str) -> Dict:
    """Search StackOverflow users by display name using the StackExchange API.

    This uses the `inname` parameter and picks the best match (exact
    case-insensitive match if present, otherwise the first result).
    """
    _require_requests()
    import requests

    url = f"https://api.stackexchange.com/2.3/users?inname={username}&site=stackoverflow&pagesize=10"
    headers = {"User-Agent": "kite/0.1"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    j = resp.json()
    items = j.get("items", [])
    if not items:
        raise RuntimeError("not found")

    # try to prefer exact display_name match (case-insensitive)
    picked = None
    uname_lower = username.lower()
    for it in items:
        if it.get("display_name", "").lower() == uname_lower:
            picked = it
            break
    if picked is None:
        picked = items[0]

    creation = None
    if picked.get("creation_date"):
        try:
            creation = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(picked.get("creation_date")))
        except Exception:
            creation = None

    data: Dict[str, Optional[str]] = {
        "display_name": picked.get("display_name"),
        "reputation": picked.get("reputation"),
        "profile_image": picked.get("profile_image"),
        "location": picked.get("location"),
        "creation_date": creation,
    }

    return canonical_fields("StackOverflow", username, f"https://stackoverflow.com/users/{picked.get('user_id')}", data)
