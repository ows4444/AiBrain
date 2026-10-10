"""Forget one source: what rests on an input, and, on the owner's yes, its removal.

Usage:
    brain forget SOURCE [--yes] [--json]

SOURCE is a file in senses/ or the name of an episode. Without --yes it writes
nothing and lists what rests on that input:
    the input (and the image it was transcribed from), the episodes written
    from it, the pages that cite those episodes with the lines that do, and
    for each concept and entity how many sources it has now and would have
    after, with what that means: it stays, it becomes `emerging`, it falls
    back to a held idea, or it has no source left.

With --yes (the owner's, never the model's: the senses guard asks them before
this runs) it does the part that needs no judgement, in this order: the log
line, a `forgotten` line in the fingerprints, then the episodes, the input and
their index lines are removed (and the listing rewritten, as `brain index` does). What is left is for /forget: the citing pages
now hold a broken link each, which `brain check` lists until each citation,
and any claim that rested only on it, is taken out by hand.

This is the only way an input leaves senses/. The fingerprint line of the
input stays, so the brain knows it once held it and that it was removed on
purpose. Git history still holds the file until the owner removes it there.
"""
import contextlib
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from fingerprint import FINGERPRINTS  # noqa: E402
from index import NoMarkers, rebuild  # noqa: E402
from vaultlib import LINK, LOG_PATH, SALIENT, Vault, as_list, parse_frontmatter  # noqa: E402

INDEX = os.path.join("hippocampus", "index.md")
JUDGED = ("concept", "entity", "insight")


def inputs_of(page):
    return [str(i).removeprefix("./") for i in as_list(page.fields.get("input")) if i]


def find(vault, source):
    """(input path relative to the brain, or None; the episodes resting on it)."""
    rel = os.path.relpath(os.path.realpath(os.path.join(vault.root, source)), os.path.realpath(vault.root))
    rel = rel.replace(os.sep, "/")
    episodes = vault.of_type("episode")
    if rel.startswith("senses/") and os.path.isfile(os.path.join(vault.root, rel)):
        return rel, [p for p in episodes if rel in inputs_of(p)]
    page = vault.resolve(source)
    if page is None or page.type != "episode":
        return None, []
    held = inputs_of(page)
    if not held:
        return None, [page]  # an episode with no input (an /explore page): only the page goes
    return held[0], [p for p in episodes if held[0] in inputs_of(p)]


def asset_of(root, rel):
    """The image an input was transcribed from, if it says so and the image is there."""
    with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
        fields = parse_frontmatter(fh.read())[0] or {}
    asset = str(fields.get("transcribed_from") or "")
    path = os.path.normpath(os.path.join("senses", asset)).replace(os.sep, "/") if asset else ""
    return path if path.startswith("senses/") and os.path.isfile(os.path.join(root, path)) else None


def verdict(vault, page, gone):
    before = vault.evidence_for(page)
    after = [p for p in before if p not in gone]
    n_before = len({vault.source_of(p) for p in before})
    n_after = len({vault.source_of(p) for p in after})
    if n_after == n_before:
        what = "stays: no source is lost"
    elif n_after == 0:
        what = "no source left: remove the page, or keep it only if the owner says what it now rests on"
    elif page.type != "concept":
        what = "stays, on fewer sources"
    elif n_after >= 2:
        what = "stays established"
    elif any(p.salience >= SALIENT for p in after):
        what = "becomes emerging: one salient episode is left"
    else:
        what = (f"falls under the two-source bar: back to a candidate on [[{after[0].stem}]], "
                "and the page is removed")
    return {"sources_before": n_before, "sources_after": n_after, "what": what}


def report(vault, source):
    rel, episodes = find(vault, source)
    if rel is None and not episodes:
        return None
    gone = set(episodes)
    citing = {}
    for a, b in vault.edges:
        if b in gone and a not in gone and (a.type == "project" or not a.is_system):
            citing.setdefault(a, set()).add(b)
    pages = []
    for page in sorted(citing, key=lambda p: p.rel):
        lines = [line.strip() for line in page.text.splitlines()
                 if any(vault.resolve(t.strip()) in gone for t in LINK.findall(line))]
        row = {"page": page.rel, "lines": lines}
        if page.type in JUDGED:
            row.update(verdict(vault, page, gone))
        pages.append(row)
    others = sorted({i for p in episodes for i in inputs_of(p)} - {rel})
    return {"input": rel, "asset": asset_of(vault.root, rel) if rel else None,
            "episodes": [p.rel for p in episodes],
            "candidates": sorted({name for p in episodes for name, _ in p.candidate_notes}),
            "citing": pages,
            "other_inputs": others}


def apply(vault, found, now):
    """Log, mark the fingerprint, then remove. Returns the files removed. `now` dates the log line."""
    root = vault.root
    today = now.strftime("%Y-%m-%d")
    removed = [f for f in [found["input"], found["asset"], *found["episodes"]] if f]
    what = found["input"] or found["episodes"][0]
    with open(os.path.join(root, LOG_PATH), "a", encoding="utf-8") as fh:
        fh.write(f"{now:%Y-%m-%d %H:%M} forget {what} -> {len(found['episodes'])} episodes and "
                 f"{sum(1 for f in (found['input'], found['asset']) if f)} input files removed on the owner's yes; "
                 f"{len(found['citing'])} pages cited them\n")
    marks = [f for f in (found["input"], found["asset"]) if f]
    if marks:
        with open(os.path.join(root, FINGERPRINTS), "a", encoding="utf-8") as fh:
            fh.write("".join(f"{today} forgotten {f}\n" for f in marks))
    gone = {vault.resolve(os.path.splitext(os.path.basename(e))[0]) for e in found["episodes"]}
    index = os.path.join(root, INDEX)
    if os.path.isfile(index):
        with open(index, encoding="utf-8") as fh:
            lines = fh.read().splitlines(keepends=True)
        kept = [line for line in lines if not any(vault.resolve(t.strip()) in gone for t in LINK.findall(line))]
        if kept != lines:
            with open(index, "w", encoding="utf-8") as fh:
                fh.write("".join(kept))
    for f in removed:
        os.remove(os.path.join(root, f))
    if os.path.isfile(index):
        with contextlib.suppress(NoMarkers):  # an index kept wholly by hand has lost its lines above already
            rebuild(root)
    return removed


def arguments(ap):
    ap.add_argument("source")
    ap.add_argument("--yes", action="store_true")


def run(root, args):
    vault = Vault(root)
    found = report(vault, args.source)
    if found is None:
        raise Refused(f"forget: {args.source} is neither a file in senses/ nor an episode")
    if args.yes:
        found["removed"] = apply(vault, found, datetime.datetime.now())
    return found


def render(found, args):
    done = "removed" in found
    out = [("forgotten" if done else "would forget") + f": {found['input'] or '(no input file)'}"]
    if found["asset"]:
        out.append(f"  and the image it was transcribed from: {found['asset']}")
    out.append(f"episodes written from it: {len(found['episodes'])}")
    out += [f"  {e}" for e in found["episodes"]]
    if found["candidates"]:
        out.append(f"ideas held only as candidates there, which go with it: {', '.join(found['candidates'])}")
    if found["other_inputs"]:
        out.append("other inputs of those episodes, which stay and count as unencoded again: "
                   + ", ".join(found["other_inputs"]))
    out.append(f"pages citing those episodes: {len(found['citing'])}")
    for row in found["citing"]:
        tail = f"  sources {row['sources_before']} -> {row['sources_after']}: {row['what']}" if "what" in row else ""
        out.append(f"  {row['page']}{tail}")
        out += [f"      {line if len(line) <= 140 else line[:137] + '...'}" for line in row["lines"]]
    if done:
        out.append("left to do by hand: take each citation above out of its page, with any claim that rested only on it; "
                   "`brain check` lists them as broken links until then")
        out.append("git history still holds the removed files")
    else:
        out.append("nothing was changed; --yes removes the input and its episodes (the owner is asked first)")
    return "\n".join(out)
