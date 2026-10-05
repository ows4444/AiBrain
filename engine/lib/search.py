#!/usr/bin/env python3
"""Find pages: by their words (search), or by words and then association (recall).

Usage:
    brain search QUERY... [--type TYPE ...] [--dormant] [--limit N] [--json]
    brain recall QUERY... [--project NAME] [--hops N] [--dormant] [--limit N] [--json]

search  BM25 over title (x3), aliases (x2) and body. Replaces grepping the
        brain: same words, ranked, stop words and simple suffixes ignored.
recall  search hits seed an activation that spreads along links (typed links
        and pairs recalled together before carry more), so pages one or two
        links from the words can come back. Each page shows how it was
        reached, its confidence (sources behind it) and flags: disputed,
        contradicted, stale (ask the owner whether it still holds), generated,
        dormant. --project biases toward the pages a project links to.

Reads only, apart from the search cache (.cache/, see `brain cache`). It never writes the log: the skill that answers from these pages
logs `DATE recall <question> -> [[page]], ...` for the pages that contributed.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import PAGE_TYPES, SPREAD_HOPS, Vault  # noqa: E402


def search_rows(vault, query, types=None, dormant=False, limit=10):
    return [{"page": p.rel, "title": p.title, "type": p.type, "score": round(s, 3)}
            for p, s in vault.search(query, types=types, dormant=dormant, limit=limit)]


def recall_rows(vault, query, project=None, limit=10, hops=SPREAD_HOPS, dormant=False):
    rows = vault.recall(query, project=project, limit=limit, hops=hops, dormant=dormant)
    return [{"page": r["page"].rel, "title": r["page"].title, "type": r["page"].type, "score": r["score"],
             "hop": r["hop"], "from": r["from"].rel, "confidence": r["confidence"], "flags": r["flags"]}
            for r in rows]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="brain search|recall")
    ap.add_argument("mode", choices=("search", "recall"))
    ap.add_argument("query", nargs="+")
    ap.add_argument("--root", default=".")
    ap.add_argument("--type", action="append", choices=PAGE_TYPES, dest="types")
    ap.add_argument("--dormant", action="store_true")
    ap.add_argument("--project")
    ap.add_argument("--hops", type=int, default=SPREAD_HOPS)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        sys.exit(f"not a directory: {args.root}")
    vault = Vault(args.root)
    query = " ".join(args.query)
    if args.mode == "search":
        rows = search_rows(vault, query, args.types, args.dormant, args.limit)
    else:
        try:
            rows = recall_rows(vault, query, args.project, args.limit, args.hops, args.dormant)
        except ValueError as e:
            sys.exit(str(e))
    if args.json:
        print(json.dumps({"query": query, "mode": args.mode, "results": rows}, indent=2))
        return
    if not rows:
        print(f'{args.mode}: nothing matches "{query}"' + ("" if args.dormant else " (try --dormant)"))
        return
    print(f'{args.mode}: "{query}"' + (f"  [project {args.project}]" if args.project else ""))
    for r in rows:
        line = f"  {r['score']:>7.3f}  {r['page']}"
        if args.mode == "recall":
            how = "hit" if r["hop"] == 0 else f"{r['hop']} hop{'s' * (r['hop'] > 1)} from {r['from']}"
            conf = f"{r['confidence']['level']}: {r['confidence']['why']}" if r["confidence"] else "dormant"
            line += f"\n           {how}; {conf}" + (f"; {', '.join(r['flags'])}" if r["flags"] else "")
        print(line)
    stale = [r["page"] for r in rows if "stale" in r.get("flags", [])]
    if stale:
        print("ask the owner whether these still hold: " + ", ".join(stale))


if __name__ == "__main__":
    main()
