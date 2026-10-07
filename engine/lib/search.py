#!/usr/bin/env python3
"""Find pages: by their words (search), or by words and then association (recall).

Usage:
    brain search QUERY... [--type TYPE ...] [--dormant] [--limit N] [--json]
    brain recall QUERY... [--project NAME] [--hops N] [--dormant] [--limit N] [--all] [--json]

search  BM25 over title (x3), aliases (x2), body and summary (x0.5). Replaces grepping the
        brain: same words, ranked, stop words and simple suffixes ignored.
recall  search hits seed an activation that spreads along links (typed links
        and pairs recalled together before carry more), so pages one or two
        links from the words can come back. Each page shows how it was
        reached, its confidence (sources behind it) and flags: disputed,
        contradicted, stale (ask the owner whether it still holds), generated,
        dormant. --project biases toward the pages a project links to.
        It stops where the match stops: rows scoring under 0.4 of the best
        are cut, and when the best page holds too little of the question it
        says so in one line and lists nothing. --all turns both off; use it
        before concluding that no page answers.
held    both also list ideas held on an episode (named by a source, no page
        yet) that the question names: the idea's one line, its episode and
        how many sources name it. An answer may use the line, citing the
        episode and saying how many sources it rests on.

Reads only, apart from the search cache (.cache/, see `brain cache`). It never writes the log: the skill that answers from these pages
logs `DATE recall <question> -> [[page]], ...` for the pages that contributed.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import PAGE_TYPES, RECALL_FLOOR, SPREAD_HOPS, Vault  # noqa: E402


def search_rows(vault, query, types=None, dormant=False, limit=10):
    return [{"page": p.rel, "title": p.title, "type": p.type, "score": round(s, 3), "summary": p.summary}
            for p, s in vault.search(query, types=types, dormant=dormant, limit=limit)]


def recall_rows(vault, query, project=None, limit=10, hops=SPREAD_HOPS, dormant=False, everything=False):
    rows = vault.recall(query, project=project, limit=limit, hops=hops, dormant=dormant,
                        floor=0.0 if everything else RECALL_FLOOR, abstain=not everything)
    return [{"page": r["page"].rel, "title": r["page"].title, "type": r["page"].type, "score": r["score"],
             "summary": r["page"].summary,
             "hop": r["hop"], "from": r["from"].rel, "confidence": r["confidence"], "flags": r["flags"]}
            for r in rows]


def held_rows(vault, query):
    return [{"name": h["name"], "note": h["note"], "episodes": [p.rel for p in h["episodes"]], "sources": h["sources"]}
            for h in vault.held_ideas(query)]


def print_held(held):
    if held:
        print("held ideas (no page yet; cite the episode and say how many sources):")
    for h in held:
        note = f" - {h['note']}" if h["note"] else ""
        print(f"  {h['name']}{note}  [{', '.join(h['episodes'])}; {h['sources']} source{'s' * (h['sources'] != 1)}]")


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
    ap.add_argument("--all", action="store_true", dest="everything",
                    help="recall: every row, however weak, and no abstaining")
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
            rows = recall_rows(vault, query, args.project, args.limit, args.hops, args.dormant, args.everything)
        except ValueError as e:
            sys.exit(str(e))
    # recall found words but too little of the question: name the pages, list nothing
    weak = ([p.rel for p, _ in vault.search(query, dormant=args.dormant, limit=3)]
            if args.mode == "recall" and not rows and not args.everything else [])
    held = held_rows(vault, query)
    if args.json:
        print(json.dumps(dict({"query": query, "mode": args.mode, "results": rows}, **({"weak": weak} if weak else {}),
                              **({"held": held} if held else {})), indent=2))
        return
    if weak:
        print(f'recall: no confident match for "{query}"; its words barely reach {", ".join(weak)} (--all lists them)')
        print_held(held)
        return
    if not rows:
        print(f'{args.mode}: nothing matches "{query}"' + ("" if args.dormant else " (try --dormant)"))
        print_held(held)
        return
    print(f'{args.mode}: "{query}"' + (f"  [project {args.project}]" if args.project else ""))
    for r in rows:
        line = f"  {r['score']:>7.3f}  {r['page']}"
        line += f"\n           {r['summary'] or '(no summary: open the page to judge it)'}"
        if args.mode == "recall":
            how = "hit" if r["hop"] == 0 else f"{r['hop']} hop{'s' * (r['hop'] > 1)} from {r['from']}"
            conf = f"{r['confidence']['level']}: {r['confidence']['why']}" if r["confidence"] else "dormant"
            line += f"\n           {how}; {conf}" + (f"; {', '.join(r['flags'])}" if r["flags"] else "")
        print(line)
    if args.mode == "recall" and not args.everything and len(rows) < args.limit:
        print("  weaker matches are cut (--all lists them)")
    print_held(held)
    stale = [r["page"] for r in rows if "stale" in r.get("flags", [])]
    if stale:
        print("ask the owner whether these still hold: " + ", ".join(stale))


if __name__ == "__main__":
    main()
