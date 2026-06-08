"""Minimal CLI front-end (right-aligned logo and simple menu)."""

import shutil
import threading
import re
from typing import Dict
from username_search import load_site_list, run_username_checks
from adapters import (
    github_fetch,
    reddit_fetch,
    gitlab_fetch,
    stackexchange_fetch,
    youtube_fetch,
    keybase_fetch,
)
from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed


LOGO_LINES = [
    "██╗  ██╗██╗████████╗███████╗",
    "██║ ██╔╝██║╚══██╔══╝██╔════╝",
    "█████╔╝ ██║   ██║   █████╗  ",
    "██╔═██╗ ██║   ██║   ██╔══╝  ",
    "██║  ██╗██║   ██║   ███████╗",
    "╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝"
]


def _term_width(default: int = 80) -> int:
    w = shutil.get_terminal_size((default, 20)).columns
    return max(40, min(78, w - 4))


def _print_banner(width: int) -> None:
    # Deprecated: use _print_connected_box instead for attached menu
    _print_connected_box(width, ["1) Search username", "2) Exit"])  # type: ignore


def _print_menu_box(width: int) -> None:
    """Print the menu options inside a simple box under the banner."""
    options = ["1) Search username", "2) Exit"]
    if width < 10:
        width = 10
    inner = width - 4
    # keep for compatibility; print a standalone menu box
    print("┌" + "─" * (width - 2) + "┐")
    for opt in options:
        print("│ " + opt.ljust(inner) + " │")
    print("└" + "─" * (width - 2) + "┘")


def _print_connected_box(width: int, options: list[str], extra_lines: list[str] | None = None, logo_override: list[str] | None = None) -> None:
    """Print one connected box with logo, title, separator, then options, no gap.

    The box layout:
    ┌────────┐
    │ logo   │
    │ ...    │
    ├────────┤
    │ title  │
    ├────────┤
    │ opt1   │
    │ opt2   │
    └────────┘
    """
    if width < 10:
        width = 10
    inner = width - 4
    print("┌" + "─" * (width - 2) + "┐")
    logo_lines = logo_override if logo_override is not None else LOGO_LINES

    # helpers to handle ANSI/OSC escape sequences so padding/truncation
    # is based on visible width rather than raw string length.
    _ansi_csi = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
    _ansi_osc = re.compile(r"\x1b\].*?\x1b\\")

    def _visible_len(s: str) -> int:
        s2 = _ansi_osc.sub('', s)
        s2 = _ansi_csi.sub('', s2)
        return len(s2)

    def _print_box_line(text: str) -> None:
        vis = _visible_len(text)
        if vis > inner:
            # naive truncate while preserving escape sequences at the end
            trimmed = text
            # remove one char at a time until visible length fits
            while _visible_len(trimmed) > inner and trimmed:
                trimmed = trimmed[:-1]
            print("│ " + trimmed + " │")
        else:
            pad = inner - vis
            print("│ " + text + (" " * pad) + " │")

    for l in logo_lines:
        _print_box_line(l)
    # separator between logo and title
    print("├" + "─" * (width - 2) + "┤")
    print("│ " + "Known Identity Traversal Engine".ljust(inner) + " │")
    # separator between title and options
    print("├" + "─" * (width - 2) + "┤")

    for opt in options:
        _print_box_line(opt)

    # optional extra section (separate area beneath options)
    if extra_lines:
        for item in extra_lines:
            # support either plain strings or tuples (text, align)
            align = "left"
            text = item
            if isinstance(item, tuple) or isinstance(item, list):
                text, align = item[0], item[1]

            if align == "right":
                # right-align based on visible length
                vis = _visible_len(text)
                pad = inner - vis
                if pad > 0:
                    print("│ " + (" " * pad) + text + " │")
                else:
                    # truncate if needed
                    trimmed = text
                    while _visible_len(trimmed) > inner and trimmed:
                        trimmed = trimmed[:-1]
                    print("│ " + trimmed + " │")
            elif align == "center":
                # center based on visible width
                vis = _visible_len(text)
                if vis >= inner:
                    trimmed = text
                    while _visible_len(trimmed) > inner and trimmed:
                        trimmed = trimmed[:-1]
                    print("│ " + trimmed + " │")
                else:
                    left = (inner - vis) // 2
                    right = inner - vis - left
                    print("│ " + (" " * left) + text + (" " * right) + " │")
            else:
                _print_box_line(str(text))

    print("└" + "─" * (width - 2) + "┘")


def _box_height(num_options: int, extra_lines: list[str] | None, logo_lines_count: int) -> int:
    """Return how many terminal lines the connected box will print."""
    extra = len(extra_lines) if extra_lines else 0
    # exact lines printed by _print_connected_box:
    # top border (1)
    # logo lines (logo_lines_count)
    # separator between logo and title (1)
    # title line (1)
    # separator between title and options (1)
    # option lines (num_options)
    # extra lines (extra)
    # bottom border (1)
    return 1 + logo_lines_count + 1 + 1 + 1 + num_options + extra + 1



def main() -> None:
    width = _term_width()

    while True:
        # Print the connected box (logo + title + options) once and then
        # update it in-place using cursor movement so terminal history isn't flooded.
        extra_lines: list[str] = []
        _print_connected_box(width, ["1) Search username", "2) Exit", "3) Fetch profiles"], extra_lines=extra_lines)
        last_height = _box_height(3, extra_lines, len(LOGO_LINES))
        choice = input("Select an option (1-2): ").strip().lower()


        if choice in ("1", "s", "search"):
            username = input("Enter username: ").strip()
            if not username:
                print("No username entered.")
                continue

            # Run the search and show results in the extra section of the box
            # Live visualization: update the existing box in-place.
            status_lock = threading.Lock()
            found: list[str] = []
            scanned = 0
            total = None
            current = ""
            def progress_cb(ev: Dict) -> None:
                nonlocal scanned, total, current, last_height, found
                with status_lock:
                    if ev.get("event") == "init":
                        total = ev.get("total")
                    elif ev.get("event") == "start":
                        current = ev.get("site")
                    elif ev.get("event") == "done":
                        res = ev.get("result", {})
                        scanned += 1
                        if res.get("exists") is True:
                            site = res.get("site")
                            found.append(site)

                    # Build display: left-align 'Scanning: sitename' and right-align counter
                    inner = width - 4
                    left_text = f"Scanning: {current}"
                    right_text = f"({scanned}/{total if total is not None else '?'})"

                    # Truncate left_text if needed to make space for right_text
                    available = inner - len(right_text)
                    if available <= 0:
                        # not enough space for left_text; show only right_text aligned right
                        scan_line = right_text.rjust(inner)
                    else:
                        if len(left_text) > available:
                            # truncate and add ellipsis
                            truncated = left_text[: max(0, available - 1)]
                            if len(truncated) < len(left_text):
                                truncated = truncated.rstrip() + "…"
                            left_text = truncated
                        # compose line: left_text then right_text padded to the right
                        scan_line = left_text.ljust(available) + right_text

                    display_lines = [f"Username: {username}", scan_line]

                    # move cursor up to the top of the previous box and overwrite it
                    print(f"\x1b[{last_height}A", end="")
                    _print_connected_box(width, ["1) Search username", "2) Exit"], extra_lines=display_lines)
                    # update last_height in case box size changed
                    last_height = _box_height(2, display_lines, len(LOGO_LINES))

            try:
                # load local site definitions and run username checks with progress events
                sites = load_site_list("wnm-example.json")
                results = run_username_checks(username, sites, max_workers=20, quick=False, progress_callback=progress_cb)
            except RuntimeError as e:
                extra = [f"Username: {username}", f"Error: {e}"]
                # overwrite box with error
                print(f"\x1b[{last_height}A", end="")
                _print_connected_box(width, ["1) Search username", "2) Exit"], extra_lines=extra)
                input("\nPress Enter to continue...")
                continue

            # search completed: render final box showing found sites grouped by category
            final_lines: list[str]
            # prefer authoritative results from the worker output rather than the
            # incremental `found` list; group results by `category` and show clickable links
            hits = [r for r in results if r.get("exists")]
            if hits:
                grouped: dict[str, list[tuple[str, str]]] = {}
                for r in hits:
                    cat = r.get("category") or "uncategorised"
                    grouped.setdefault(cat, []).append((r.get("site"), r.get("url")))

                lines = [f"Username: {username}", "Found:"]
                # OSC 8 hyperlink template: ESC ] 8 ;; URL ESC \ text ESC ] 8 ;; ESC \\ 
                for cat in sorted(grouped.keys()):
                    lines.append(f"[{cat}]")
                    for site, url in grouped[cat]:
                        if url:
                            # create terminal hyperlink when supported
                            link = f"\x1b]8;;{url}\x1b\\{site}\x1b]8;;\x1b\\"
                            lines.append(f"- {link}")
                        else:
                            lines.append(f"- {site}")
                # After reporting hits, run any available adapters for detected sites
                # adapter mapping: key -> function
                adapter_map = {
                    "github": github_fetch,
                    "reddit": reddit_fetch,
                    "gitlab": gitlab_fetch,
                }

                # run only adapters that correspond to detected hit sites
                hit_site_names = [r.get("site", "").lower() for r in hits]
                to_run = []
                # mapping of substring -> adapter function
                substr_map = [
                    ("github", github_fetch),
                    ("gitlab", gitlab_fetch),
                    ("reddit", reddit_fetch),
                    ("youtube", youtube_fetch),
                    ("stack", stackexchange_fetch),
                    ("stackoverflow", stackexchange_fetch),
                    ("keybase", keybase_fetch),
                ]

                seen = set()
                for s in hit_site_names:
                    for substr, fn in substr_map:
                        if substr in s and fn not in seen:
                            to_run.append((substr, fn))
                            seen.add(fn)

                if to_run:
                    # run adapters concurrently
                    lines.append("")
                    lines.append("Fetched profiles:")
                    with ThreadPoolExecutor(max_workers=len(to_run)) as ex:
                        futs = {ex.submit(fn, username): key for key, fn in to_run}
                        for f in _as_completed(futs):
                            key = futs[f]
                            try:
                                r = f.result()
                            except Exception as e:
                                lines.append(f"- {key}: ERROR: {e}")
                                continue
                            # r expected to be canonical dict from adapters.base.canonical_fields
                            site = r.get("site") or key
                            url = r.get("url") or r.get("data", {}).get("web_url") or r.get("data", {}).get("avatar_url")
                            display = r.get("data", {}).get("display_name") or ""
                            if url:
                                link = f"\x1b]8;;{url}\x1b\\{site}\x1b]8;;\x1b\\"
                                if display:
                                    lines.append(f"- {link} ({display})")
                                else:
                                    lines.append(f"- {link}")
                            else:
                                lines.append(f"- {site} ({display})")

                final_lines = lines
            else:
                final_lines = [f"Username: {username}", "No matches found"]

            # overwrite previous box with final results
            print(f"\x1b[{last_height}A", end="")
            _print_connected_box(width, ["1) Search username", "2) Exit"], extra_lines=final_lines)
            input("\nPress Enter to continue...")
        elif choice in ("2", "q", "exit"):
            print("Goodbye!")
            break
        elif choice in ("3", "f", "fetch"):
            username = input("Enter username to fetch profiles for: ").strip()
            if not username:
                print("No username entered.")
                continue

            # fetch profiles concurrently using adapters
            adapters = [github_fetch, reddit_fetch, gitlab_fetch]
            results = []
            with ThreadPoolExecutor(max_workers=6) as ex:
                futs = {ex.submit(adapter, username): adapter for adapter in adapters}
                for f in _as_completed(futs):
                    try:
                        res = f.result()
                    except Exception as e:
                        adapter = futs[f]
                        res = {"site": getattr(adapter, "__name__", "adapter"), "username": username, "error": str(e)}
                    results.append(res)

            # build final lines grouped by site (and show clickable links when available)
            final_lines: list[str]
            if results:
                lines = [f"Username: {username}", "Profiles:"]
                for r in results:
                    site = r.get("site") or r.get("adapter")
                    if r.get("error"):
                        lines.append(f"- {site}: ERROR: {r.get('error')}")
                        continue
                    url = r.get("url") or r.get("data", {}).get("web_url") or r.get("data", {}).get("avatar_url")
                    display = r.get("data", {}).get("display_name") or ""
                    if url:
                        link = f"\x1b]8;;{url}\x1b\\{site}\x1b]8;;\x1b\\"
                        if display:
                            lines.append(f"- {link} ({display})")
                        else:
                            lines.append(f"- {link}")
                    else:
                        lines.append(f"- {site} ({display})")
                final_lines = lines
            else:
                final_lines = [f"Username: {username}", "No profiles found"]

            # overwrite previous box with final results
            print(f"\x1b[{last_height}A", end="")
            _print_connected_box(width, ["1) Search username", "2) Exit", "3) Fetch profiles"], extra_lines=final_lines)
            input("\nPress Enter to continue...")
        else:
            print("Invalid selection — please choose 1 or 2.")


if __name__ == "__main__":
    main()
