#!/usr/bin/env python3
"""The search cache: what it holds, and rebuilding or clearing it.

Usage:
    brain cache            where it is, how many pages it holds, its size
    brain cache --rebuild  start it over and fill it from every page (dormant/ too)
    brain cache --clear    delete it; the next search rebuilds what it needs
    brain cache --json

The cache only saves time: search gives the same results without it, and
BRAIN_CACHE=0 turns it off. See vault_cache.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_cache  # noqa: E402
from vaultlib import Vault  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(prog="brain cache")
    ap.add_argument("root")
    action = ap.add_mutually_exclusive_group()
    action.add_argument("--rebuild", action="store_true")
    action.add_argument("--clear", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    note = ""
    if args.clear:
        note = "cleared" if vault_cache.clear(args.root) else "nothing to clear"
        out = {"path": vault_cache.cache_path(args.root), "result": note}
        print(json.dumps(out, indent=2) if args.json else f"cache: {note} ({out['path']})")
        return 0
    if args.rebuild:
        if not vault_cache.enabled():
            sys.exit("cache: off (BRAIN_CACHE=0); nothing rebuilt")
        vault_cache.clear(args.root)
        vault = Vault(args.root)
        pool = [p for p in vault.knowledge if p.type != "project"] + vault.dormant_pages
        vault._term_frequencies_many(pool)
        vault._term_cache.close()
        note = f"rebuilt from {len(pool)} pages"
    cache = vault_cache.TermCache(args.root) if vault_cache.enabled() else None
    stats = cache.stats() if cache else {"path": vault_cache.cache_path(args.root), "enabled": False}
    if cache:
        cache.close()
    if note:
        stats["result"] = note
    if args.json:
        print(json.dumps(stats, indent=2))
        return 0
    if not stats["enabled"]:
        print(f"cache: off (BRAIN_CACHE=0); {stats['path']} is not used")
        return 0
    if not stats["open"]:
        print(f"cache: cannot open {stats['path']}; search runs without it")
        return 0
    print(f"cache: {stats['path']}")
    print(f"  pages {stats['pages']}, {stats['bytes'] / 1024:.0f} KiB, version {stats['version']}")
    if note:
        print(f"  {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
