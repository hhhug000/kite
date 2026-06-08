#!/usr/bin/env python3
"""Runner to fetch profiles for a list of usernames using adapters.

Usage:
  python fetch_profiles.py alice
  python fetch_profiles.py --file usernames.txt --out results.jsonl
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from adapters import github_fetch, reddit_fetch, gitlab_fetch


ADAPTERS = [github_fetch, reddit_fetch, gitlab_fetch]


def _run_one(adapter, username):
    try:
        return adapter(username)
    except Exception as e:
        return {"site": getattr(adapter, "__name__", "adapter"), "username": username, "error": str(e)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("user", nargs="*", help="usernames to fetch")
    p.add_argument("--file", help="file with newline-separated usernames")
    p.add_argument("--out", help="output JSONL file (default stdout)")
    p.add_argument("--workers", type=int, default=6)
    args = p.parse_args()

    names: List[str] = []
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            names.extend([l.strip() for l in f if l.strip()])
    names.extend(args.user or [])
    if not names:
        print("No usernames provided")
        raise SystemExit(2)

    out_f = open(args.out, "w", encoding="utf-8") if args.out else None

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = []
        for username in names:
            for adapter in ADAPTERS:
                futures.append(ex.submit(_run_one, adapter, username))

        for f in as_completed(futures):
            res = f.result()
            line = json.dumps(res, ensure_ascii=False)
            if out_f:
                out_f.write(line + "\n")
            else:
                print(line)

    if out_f:
        out_f.close()


if __name__ == "__main__":
    main()
