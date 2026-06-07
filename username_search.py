import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote

__all__ = [
    "load_site_list",
    "filter_to_high_signal",
    "check_site",
    "run_username_checks",
]

USER_AGENT = "username-search/1.0"
TIMEOUT = 8


def http_get(url, timeout=TIMEOUT, headers=None):
    """Fetch a URL and return (status, body) or (None, error_string)."""
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    try:
        req = Request(url, headers=hdrs)
        with urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.code, None
    except (URLError, socket.timeout) as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


# Curated high-signal site names used for a quick sweep.
HIGH_SIGNAL_SITES = [
    "GitHub", "GitLab", "Reddit", "Twitter", "Instagram", "TikTok",
    "YouTube", "Twitch", "Steam", "Pinterest", "Medium", "Dev.to",
    "HackerNews", "Hacker News", "Keybase", "AUR", "Stack Overflow",
    "LinkedIn", "Facebook", "Spotify", "SoundCloud", "Last.fm",
    "DeviantArt", "Behance", "Dribbble", "Vimeo", "Telegram",
    "Discord", "Mastodon", "Bluesky",
]


def filter_to_high_signal(sites):
    """Return only sites whose name matches a curated high-signal list.

    sites: list of dicts with a `name` key.
    """
    out = []
    for s in sites:
        name = s.get("name", "").lower()
        for q in HIGH_SIGNAL_SITES:
            if q.lower() in name:
                out.append(s)
                break
    return out


def load_site_list(path):
    """Load a local JSON file containing a `sites` array and return that list.

    The function will NOT attempt any network access. The JSON format is
    expected to be compatible with common username-site datasets: a top-level
    object containing a `sites` array where each site is a mapping with keys
    like `name`, `uri_check`, `uri_pretty`, `e_code`, `e_string`, `m_string`.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sites = data.get("sites", [])

    # Backwards-compat: if `sites` is a mapping (old `data.json` format),
    # convert it into a list of site dicts with fields the rest of this
    # module expects (e.g. `name`, `uri_check`, `uri_pretty`, `e_code`,
    # `e_string`, `m_string`). This keeps `kite.py` usable with either
    # the converted `sites.json` or the original `data.json`.
    if isinstance(sites, dict):
        out = []
        for name, conf in sites.items():
            # prefer probe URL when available
            uri_check = conf.get("urlProbe") or conf.get("url")
            if not uri_check:
                continue
            uri_check = uri_check.replace("{username}", "{account}")
            uri_pretty = (conf.get("url") or uri_check).replace("{username}", "{account}")

            # presence/absence strings (different keys used across datasets)
            pres = None
            for key in ("presenseStrs", "presenceStrs", "presense", "presence"):
                if key in conf and conf.get(key):
                    pres = conf.get(key)
                    break
            absn = None
            for key in ("absenceStrs", "absence", "absenceStr"):
                if key in conf and conf.get(key):
                    absn = conf.get(key)
                    break

            e_string = ""
            if pres:
                if isinstance(pres, list) and pres:
                    e_string = pres[0]
                elif isinstance(pres, str):
                    e_string = pres

            m_string = ""
            if absn:
                if isinstance(absn, list) and absn:
                    m_string = absn[0]
                elif isinstance(absn, str):
                    m_string = absn

            site = {
                "name": name,
                "uri_check": uri_check,
                "uri_pretty": uri_pretty,
                "e_code": conf.get("e_code") or 200,
                "e_string": e_string,
                "m_string": m_string,
            }
            # preserve headers, strip_bad_char and other helpful fields
            if conf.get("headers"):
                site["headers"] = conf.get("headers")
            if conf.get("strip_bad_char"):
                site["strip_bad_char"] = conf.get("strip_bad_char")
            if conf.get("tags"):
                site["cat"] = ",".join(conf.get("tags")) if isinstance(conf.get("tags"), list) else str(conf.get("tags"))
            out.append(site)
        return out

    return sites


def check_site(site, username, http_get_fn=None):
    """Check a single site definition for the presence of a username.

    Returns a tuple: (name, pretty_url, found (bool), status)
    """
    http_get_fn = http_get_fn or http_get
    name = site.get("name", "?")
    # Build URLs using the {account} placeholder
    url = site.get("uri_check", "").replace("{account}", quote(username, safe=""))
    pretty = site.get("uri_pretty", site.get("uri_check", "")).replace(
        "{account}", quote(username, safe=""))

    # Optionally strip disallowed characters if site specifies them
    bad = site.get("strip_bad_char", "")
    if bad:
        clean_u = "".join(c for c in username if c not in bad)
        if clean_u != username:
            url = site.get("uri_check", "").replace("{account}", quote(clean_u, safe=""))
            pretty = site.get("uri_pretty", site.get("uri_check", "")).replace(
                "{account}", quote(clean_u, safe=""))

    headers = site.get("headers", {})
    status, body = http_get_fn(url, headers=headers)

    e_code = site.get("e_code")
    e_string = site.get("e_string", "")
    m_string = site.get("m_string", "")

    found = False
    if status == e_code and body is not None:
        if e_string and e_string in body:
            if not m_string or m_string not in body:
                found = True

    return name, pretty, bool(found), status


def run_username_checks(username, sites, max_workers=20, quick=False, http_get_fn=None, progress_callback=None):
    """Run checks across a list of site definitions concurrently.

    Returns a list of result dicts similar to other search utilities:
      {"site": name, "username": username, "url": pretty_url, "exists": bool, "status_code": status}

    If `progress_callback` is provided it will be called with events:
      - {"event":"init", "total": N}
      - {"event":"start", "site": site_name, "url": url}
      - {"event":"done", "site": site_name, "result": result_dict}
    """
    if quick:
        sites = filter_to_high_signal(sites)

    http_get_fn = http_get_fn or http_get

    total = len(sites)
    if progress_callback:
        try:
            progress_callback({"event": "init", "total": total})
        except Exception:
            pass

    results = []

    def _worker(site):
        name, pretty, found, status = check_site(site, username, http_get_fn=http_get_fn)
        return {"site": name, "username": username, "url": pretty, "exists": found, "status_code": status, "category": site.get("cat")}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_worker, s): s for s in sites}
        for f in as_completed(futs):
            site = futs[f]
            try:
                if progress_callback:
                    try:
                        progress_callback({"event": "start", "site": site.get("name", "?"), "url": site.get("uri_pretty", site.get("uri_check"))})
                    except Exception:
                        pass

                res = f.result()
                results.append(res)
            except Exception as e:
                results.append({"site": site.get("name", "?"), "username": username, "url": "", "exists": None, "error": str(e)})
            finally:
                if progress_callback:
                    try:
                        progress_callback({"event": "done", "site": site.get("name", "?"), "result": results[-1]})
                    except Exception:
                        pass

    return results
