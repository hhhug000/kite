"""Adapters package: per-site profile fetchers.

Each adapter exposes a `fetch(username)` function that returns a dict
with canonical profile fields or raises an exception on error.
"""

from .github import fetch as github_fetch
from .reddit import fetch as reddit_fetch
from .gitlab import fetch as gitlab_fetch
from .stackexchange import fetch as stackexchange_fetch
from .youtube import fetch as youtube_fetch
from .keybase import fetch as keybase_fetch

__all__ = [
	"github_fetch",
	"reddit_fetch",
	"gitlab_fetch",
	"stackexchange_fetch",
	"youtube_fetch",
	"keybase_fetch",
]
