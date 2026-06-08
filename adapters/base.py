"""Common helpers for adapters."""
from __future__ import annotations

import time
from typing import Dict, Optional

try:
    import requests
except Exception:  # pragma: no cover - instruct user to install
    requests = None


def _require_requests():
    if requests is None:
        raise RuntimeError("This adapter requires the 'requests' package. Install with: pip install -r requirements.txt")


def canonical_fields(site: str, username: str, url: str, data: Dict[str, Optional[str]]) -> Dict:
    """Return a canonical profile dict with provenance."""
    out = {
        "site": site,
        "username": username,
        "url": url,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": data,
    }
    return out
