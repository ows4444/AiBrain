#!/usr/bin/env python3
"""Check the brain for broken wikilinks, schema problems, index drift, orphans and stubs.

Usage:
    brain check [--json] [--guard]

Links resolve by file name, then title, then alias, the way Obsidian does.
Links to pages listed under the index's `## Gaps` are reported as gaps, not
broken, and so are links to pages that faded to dormant/. Links in the Owner section's Goals are checked too, and so are
project pages in prefrontal/. A file name two pages share fails, and so does a
title or alias two pages share once a link uses it: that link reaches whichever
loads first. A shared title no link uses is listed, not failed. Typed links must use
a relation from CLAUDE.md > Rules, and log lines
an operation from CLAUDE.md > Log. An observation on a decision must not rest
on an /explore episode alone. In a git repository, an input in senses/ changed
or removed since the last commit fails, and so does a line changed or removed
in the log, the metrics or the fingerprints: all are append-only, and the
hooks cannot see a shell edit. So is a frozen `## Expected` on a decided or
reviewed decision rewritten since the last commit, or such a page reopened.
Without git, every input fingerprinted by `brain fingerprint` is compared
with its hash, so an edited input fails either way.
Exits 1 on a broken link, a schema problem, an ambiguous name, an unknown
relation, such an observation or such a change, so it can gate a commit;
this also catches pages written by shell commands, which skip the hook.
Unknown log operations, open decisions with untagged lines and possible
near-duplicate pages are reported but do not fail.
--guard also scans every file for credentials (fails) and personal data
(listed), naming the file, kind and line, never the value.
Reads only; never modifies anything.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fingerprint import fingerprint_problems  # noqa: E402
from secret_scan import scan_tree  # noqa: E402
from vaultlib import STUB_WORDS, Vault, parse_frontmatter  # noqa: E402

LIMIT = 40
APPEND_ONLY = ("hippocampus/log.md", "hippocampus/metrics.md", "hippocampus/fingerprints.md")
FROZEN = ("decided", "reviewed")
EXPECTED = re.compile(r"^## Expected\s*\n(.*?)(?=^## |\Z)", re.S | re.M)


def expected_of(text):
    m = EXPECTED.search(text)
    return " ".join(m.group(1).split()) if m else ""


def status_of(text):
    return (parse_frontmatter(text)[0] or {}).get("status")


def history_problems(root):
    """What changed since the last commit that never should: inputs, append-only lines, frozen expectations.

    Empty outside a git repository or before the first commit: there is nothing to compare with.
    """
    def run(*args):
        try:
            r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout if r.returncode == 0 else None

    def git(*args):
        return (run(*args) or "").splitlines()

    if not git("rev-parse", "--verify", "HEAD"):
        return []
    problems = []
    for line in git("status", "--porcelain", "--", "senses"):
        state, path = line[:2], line[3:].strip('"')
        if set(state) & set("MDR") and not path.endswith("senses/README.md"):
            problems.append(f"{path}: input {'removed' if 'D' in state else 'changed'} since the last commit")
    for line in git("diff", "HEAD", "--numstat", "--", *APPEND_ONLY):
        _, removed, path = line.split("\t", 2)
        if removed not in ("0", "-"):
            problems.append(f"{path}: {removed} lines changed or removed since the last commit; it is append-only")
    # The protect_expected hook guards the Edit and Write tools; this is the same
    # wall for everything else (a shell edit, another editor), against the last commit.
    # Paths from the repository root, so a brain kept in a subfolder of a repository works too.
    top = (run("rev-parse", "--show-toplevel") or "").strip() or root
    for name in git("ls-tree", "-r", "--name-only", "--full-name", "HEAD", "--", "cortex/decisions"):
        before = run("show", f"HEAD:{name}")
        if not before or status_of(before) not in FROZEN:
            continue
        full = os.path.join(top, name)
        path = os.path.relpath(os.path.realpath(full), os.path.realpath(root)).replace(os.sep, "/")
        if not os.path.isfile(full):
            problems.append(f"{path}: a {status_of(before)} decision was removed since the last commit")
            continue
        with open(full, encoding="utf-8", errors="replace") as fh:
            after = fh.read()
        if status_of(after) not in FROZEN:
            problems.append(f"{path}: a {status_of(before)} decision was reopened since the last commit")
        elif expected_of(before) and expected_of(after) != expected_of(before):
            problems.append(f"{path}: its frozen ## Expected was rewritten since the last commit")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--guard", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.exit(f"not a directory: {args.root}")
    vault = Vault(args.root)
    pages = vault.knowledge
    edges = vault.knowledge_edges()
    clashes, unused = vault.ambiguous_names()
    found = scan_tree(vault.root) if args.guard else []

    result = {
        "pages": len(pages),
        "links": len(edges),
        "avg_degree": round(2 * len(edges) / len(pages), 2) if pages else 0,
        "broken": [{"page": p.rel, "target": t} for p, t in vault.broken]
                  + [{"page": f"CLAUDE.md > Goals > {g}", "target": t} for g, t in vault.goal_link_problems()],
        "ambiguous": [{"name": n, "pages": [p.rel for p in ps]} for n, ps in clashes.items()],
        "shared_names": [{"name": n, "pages": [p.rel for p in ps]} for n, ps in unused.items()],
        "schema": [{"page": p.rel, "problems": probs} for p, probs in vault.schema_problems()],
        "relations": [{"page": p.rel, "relation": r} for p, r in vault.relation_problems()],
        "claims": [{"page": p.rel, "claim": c} for p, c in vault.claim_link_problems()],
        "history": history_problems(vault.root) + fingerprint_problems(vault.root),
        "secrets": [f"{x['path']}:{x['line']}: {x['kind']}" for x in found if x["severity"] == "critical"],
        "personal": [f"{x['path']}:{x['line']}: {x['kind']}" for x in found if x["severity"] == "personal"],
        "untagged": [p.rel for p in vault.untagged_open()],
        "near_duplicates": [{"pages": [a.rel, b.rel], "score": s, "why": why}
                            for a, b, s, why in vault.near_duplicates()],
        "log": vault.log_problems(),
        # One entry per gap, spelled as the index's Gaps section lists it.
        "gaps": sorted({t.lower(): t for p, t in sorted(vault.gaps, key=lambda g: g[0].type == "index")}.values(),
                       key=str.lower),
        "to_dormant": sorted({f"{p.rel} -> [[{t}]]" for p, t in vault.faded}),
        "not_in_index": [p.rel for p in vault.missing_from_index()],
        "orphans": sorted(p.rel for p in vault.orphans()),
        "stubs": sorted(p.rel for p in vault.stubs()),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"pages: {result['pages']}")
        print(f"links: {result['links']} (avg degree {result['avg_degree']})")
        for key, label, fmt in (
            ("broken", "broken links", lambda b: f"{b['page']} -> [[{b['target']}]]"),
            ("schema", "schema problems", lambda x: f"{x['page']}: {'; '.join(x['problems'])}"),
            ("ambiguous", "names more than one page answers to", lambda x: f"{x['name']}: {', '.join(x['pages'])}"),
            ("shared_names", "titles or aliases pages share, no link uses them yet",
             lambda x: f"{x['name']}: {', '.join(x['pages'])}"),
            ("relations", "unknown typed-link relations", lambda x: f"{x['page']}: ({x['relation']}::)"),
            ("claims", "observations resting only on /explore episodes", lambda x: f"{x['page']}: {x['claim']}"),
            ("history", "inputs, append-only lines or frozen expectations changed", str),
            ("secrets", "possible credentials (remove at the source, rotate)", str),
            ("personal", "personal data (the owner decides)", str),
            ("untagged", "open decisions with untagged lines (tag them before deciding)", str),
            ("near_duplicates", "possible near-duplicates (/maintain merge, if they are one idea)",
             lambda x: f"{' ~ '.join(x['pages'])}  ({x['why']})"),
            ("log", "log lines with an unknown operation", str),
            ("gaps", "known gaps (listed in the index)", lambda g: f"[[{g}]]"),
            ("to_dormant", "links to pages that faded to dormant/", str),
            ("not_in_index", "pages missing from the index", str),
            ("orphans", "orphans", str),
            ("stubs", f"stubs (<{STUB_WORDS} words, no links)", str),
        ):
            if key in ("secrets", "personal") and not args.guard:
                continue
            items = result[key]
            print(f"{label}: {len(items)}")
            for item in items[:LIMIT]:
                print(f"  {fmt(item)}")
            if len(items) > LIMIT:
                print(f"  ... {len(items) - LIMIT} more (use --json)")

    failing = ("broken", "schema", "ambiguous", "relations", "claims", "history", "secrets")
    sys.exit(1 if any(result[k] for k in failing) else 0)


if __name__ == "__main__":
    main()
