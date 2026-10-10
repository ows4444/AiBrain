"""Check the brain for broken wikilinks, schema problems, index drift, orphans and stubs.

Usage:
    brain check [--json] [--guard]

Links resolve by file name, then title, then alias, the way Obsidian does.
Links to pages listed under the index's `## Gaps` are reported as gaps, not
broken, and so are links to pages that faded to dormant/. Links in the owner's Goals (OWNER.md) are checked too, and so are
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
with its hash, so an edited input fails either way. An input the owner had
removed with `brain forget` is marked in the fingerprints and does not fail.
Exits 1 on a broken link, a schema problem, an ambiguous name, an unknown
relation, such an observation or such a change, so it can gate a commit;
this also catches pages written by shell commands, which skip the hook.
Unknown log operations, log lines that are read as nothing (a malformed or
impossible date), recall and rehearse lines naming a page that is neither here
nor in dormant/ (`brain log` refuses these as they are written; history may
hold them for pages since merged), open decisions with untagged lines, possible
near-duplicate pages and undated facts (a count or a status in the present
tense, on a concept, entity or insight, with no date and no pointer) are
reported but do not fail. A line in hippocampus/tuning.md that names no
threshold, or gives one a value outside its range, is a schema problem of that
page, and fails; so is a line under `## Traits` in CHARACTER.md that names no
trait or gives one a value outside 0 to 1. `tuning` in the result is the
thresholds this brain holds at another value than the engine's, by an
override or by a trait.
--guard also scans every file for credentials (fails) and personal data
(listed), naming the file, kind and line, never the value.
Reads only; never modifies anything.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fingerprint import fingerprint_problems, forgotten  # noqa: E402
from secret_scan import scan_tree  # noqa: E402
from vaultlib import (CHARACTER_FILE, Tuning, Vault, character_problems, owner_file, parse_frontmatter,  # noqa: E402
                      summary_problems, unread_lines)

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
    gone = forgotten(root)
    for line in git("status", "--porcelain", "--", "senses"):
        state, path = line[:2], line[3:].strip('"')
        if "D" in state and path in gone:
            continue  # the owner had it removed (brain forget); the fingerprints say so
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


# The sections of the text report, in order: the key of the result, its heading, how one entry is written.
# A heading that names a threshold is a function of the brain's thresholds (`tuning` in the result).
SECTIONS = (
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
    ("undated", "facts that go out of date, with no date or pointer (/maintain: restamp, point or move)",
     lambda x: f"{x['page']}: {x['line'] if len(x['line']) <= 120 else x['line'][:117] + '...'}"),
    ("log", "log lines with an unknown operation", str),
    ("log_unread", "log lines read as nothing (they do not parse, or their date does not exist)", str),
    ("log_unresolved", "recall lines naming a page that is not here (it strengthens nothing)",
     lambda x: f"{x['line']}  (not a page: {', '.join(x['names'])})"),
    ("gaps", "known gaps (listed in the index)", lambda g: f"[[{g}]]"),
    ("to_dormant", "links to pages that faded to dormant/", str),
    ("not_in_index", "pages missing from the index (`brain index` lists them)", str),
    ("orphans", "orphans", str),
    ("stubs", lambda t: f"stubs (<{t.stub_words} words, no links)", str),
    ("no_summary", "pages without a summary (recall cannot say what they hold)", str),
)
FAILING = ("broken", "schema", "ambiguous", "relations", "claims", "history", "secrets")  # any of these: exit 1


def arguments(ap):
    ap.add_argument("--guard", action="store_true")


def character(root):
    """The character page's problems as one row of `schema`, or none: a trait it does not know, a value out of range."""
    path = os.path.join(root, CHARACTER_FILE)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as fh:
        problems = character_problems(fh.read())
    return [{"page": CHARACTER_FILE, "problems": problems}] if problems else []


def run(root, args):
    vault = Vault(root)
    pages = vault.knowledge
    edges = vault.knowledge_edges()
    clashes, unused = vault.ambiguous_names()
    found = scan_tree(vault.root) if args.guard else []
    return {
        "pages": len(pages),
        "links": len(edges),
        "avg_degree": round(2 * len(edges) / len(pages), 2) if pages else 0,
        "broken": [{"page": p.rel, "target": t} for p, t in vault.broken]
                  + [{"page": f"{owner_file(root)} > Goals > {g}", "target": t} for g, t in vault.goal_link_problems()],
        "ambiguous": [{"name": n, "pages": [p.rel for p in ps]} for n, ps in clashes.items()],
        "shared_names": [{"name": n, "pages": [p.rel for p in ps]} for n, ps in unused.items()],
        "schema": [{"page": p.rel, "problems": probs} for p, probs in vault.schema_problems()] + character(root),
        "relations": [{"page": p.rel, "relation": r} for p, r in vault.relation_problems()],
        "claims": [{"page": p.rel, "claim": c} for p, c in vault.claim_link_problems()],
        "history": history_problems(vault.root) + fingerprint_problems(vault.root),
        "secrets": [f"{x['path']}:{x['line']}: {x['kind']}" for x in found if x["severity"] == "critical"],
        "personal": [f"{x['path']}:{x['line']}: {x['kind']}" for x in found if x["severity"] == "personal"],
        "untagged": [p.rel for p in vault.untagged_open()],
        "near_duplicates": [{"pages": [a.rel, b.rel], "score": s, "why": why}
                            for a, b, s, why in vault.near_duplicates()],
        "undated": [{"page": p.rel, "line": line} for p, line in vault.undated_facts()],
        "log": vault.log_problems(),
        "log_unread": unread_lines(vault.root),
        "log_unresolved": [{"line": line, "names": lost} for line, lost in vault.log_unresolved()],
        # One entry per gap, spelled as the index's Gaps section lists it.
        "gaps": sorted({t.lower(): t for p, t in sorted(vault.gaps, key=lambda g: g[0].type == "index")}.values(),
                       key=str.lower),
        "to_dormant": sorted({f"{p.rel} -> [[{t}]]" for p, t in vault.faded}),
        "not_in_index": [p.rel for p in vault.missing_from_index()],
        "orphans": sorted(p.rel for p in vault.orphans()),
        "stubs": sorted(p.rel for p in vault.stubs()),
        "no_summary": sorted(p.rel for p in vault.knowledge if summary_problems(p.text)),
        "tuning": vault.tuning.changed(),
    }


def render(result, args):
    out = [f"pages: {result['pages']}", f"links: {result['links']} (avg degree {result['avg_degree']})"]
    tuning = Tuning(result["tuning"])
    for key, label, fmt in SECTIONS:
        if key in ("secrets", "personal") and not args.guard:
            continue
        items = result[key]
        out.append(f"{label(tuning) if callable(label) else label}: {len(items)}")
        out += [f"  {fmt(item)}" for item in items[:LIMIT]]
        if len(items) > LIMIT:
            out.append(f"  ... {len(items) - LIMIT} more (use --json)")
    return "\n".join(out)


def exit_code(result):
    return 1 if any(result[k] for k in FAILING) else 0
