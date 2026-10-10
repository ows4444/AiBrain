"""The search cache: what it holds, and rebuilding or clearing it.

Usage:
    brain cache            where it is, how many pages it holds, its size
    brain cache --rebuild  start it over and fill it from every page (dormant/ too)
    brain cache --clear    delete it; the next search rebuilds what it needs
    brain cache --json

The cache only saves time: search gives the same results without it, and
BRAIN_CACHE=0 turns it off. See vault_cache.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_cache  # noqa: E402
from commands import Refused  # noqa: E402
from vaultlib import Vault, tuning_of  # noqa: E402


def arguments(ap):
    action = ap.add_mutually_exclusive_group()
    action.add_argument("--rebuild", action="store_true")
    action.add_argument("--clear", action="store_true")


def run(root, args):
    """What the cache holds; after --clear, only where it was and what was done."""
    if args.clear:
        return {"path": vault_cache.cache_path(root),
                "result": "cleared" if vault_cache.clear(root) else "nothing to clear"}
    note = ""
    if args.rebuild:
        if not vault_cache.enabled():
            raise Refused("cache: off (BRAIN_CACHE=0); nothing rebuilt")
        vault_cache.clear(root)
        vault = Vault(root)
        pool = [p for p in vault.knowledge if p.type != "project"] + vault.dormant_pages
        vault._term_frequencies_many(pool)
        vault._term_cache.close()
        note = f"rebuilt from {len(pool)} pages"
    # Opened under the brain's own key: under another, the rows would read as stale and be emptied.
    cache = vault_cache.TermCache(root, tuning_of(root).cache_key) if vault_cache.enabled() else None
    stats = cache.stats() if cache else {"path": vault_cache.cache_path(root), "enabled": False}
    if cache:
        cache.close()
    if note:
        stats["result"] = note
    return stats


def render(stats, args):
    if "enabled" not in stats:
        return f"cache: {stats['result']} ({stats['path']})"
    if not stats["enabled"]:
        return f"cache: off (BRAIN_CACHE=0); {stats['path']} is not used"
    if not stats["open"]:
        return f"cache: cannot open {stats['path']}; search runs without it"
    out = [f"cache: {stats['path']}", f"  pages {stats['pages']}, {stats['bytes'] / 1024:.0f} KiB, version {stats['version']}"]
    if "result" in stats:
        out.append(f"  {stats['result']}")
    return "\n".join(out)
