"""Reddit adapter: use the public about.json endpoint."""
from __future__ import annotations

from typing import Dict, Optional
from .base import _require_requests, canonical_fields

def fetch(username: str) -> Dict:
    _require_requests()
    import requests
    import os

    url = f"https://www.reddit.com/user/{username}/about.json"
    ua = os.environ.get("REDDIT_USER_AGENT", "kite/0.1 (by /u/yourname)")
    headers = {"User-Agent": ua}

    # If a bearer token is supplied via REDDIT_TOKEN use the OAuth endpoint
    token = os.environ.get("REDDIT_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        # use the oauth subdomain which accepts Bearer tokens
        url = f"https://oauth.reddit.com/user/{username}/about"

    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 404:
        raise RuntimeError("not found")
    resp.raise_for_status()
    j = resp.json()
    data_raw = j.get("data", {})

    data: Dict[str, Optional[str]] = {
        "display_name": data_raw.get("subreddit", {}).get("title") if data_raw.get("subreddit") else None,
        "bio": data_raw.get("subreddit", {}).get("public_description") if data_raw.get("subreddit") else None,
        "created_utc": data_raw.get("created_utc"),
        "link_karma": data_raw.get("link_karma"),
        "comment_karma": data_raw.get("comment_karma"),
    }

    return canonical_fields("Reddit", username, f"https://www.reddit.com/user/{username}", data)
