"""Rewrite the listing of hippocampus/index.md from the pages: by type, one line a page, its summary.

Usage:
    brain index [--dry-run] [--json]

The index is the map read before any search. Its listing only repeats what
the pages say (each line is a page's `summary:`), so it is written from them,
between two marker lines:

    <!-- brain index: the listing below is written by `brain index`; do not edit it by hand -->
    ...
    <!-- brain index: end of the listing -->

Everything outside them is left exactly as it is: the heading, `## Gaps`
(pages linked that do not exist yet, kept by hand) and any section the owner
adds, such as pages grouped by theme. Between them: a section for each page
type, in the order concepts, entities, insights, decisions, episodes; each
page as `- [[file-name]] - its summary`, by file name; a type with no page
says so. A page whose type is none of the five is listed last under its own
heading, so no page is ever missing from the index; `brain check` says what is
wrong with it. Pages in dormant/ are not listed.

Run it whenever pages were added, renamed, removed or moved; the skills say
when. It prints what it added and removed. --dry-run prints that and writes
nothing. An index without the two marker lines is not touched: the message
says where to put them. A brain with no index gets the template's. The new
index takes the old one's place in one step (files.write_whole), so a run that
dies, or two at once, never leave it short.

What stands outside the listing is the owner's down to the byte: one that is
no UTF-8 is read and written back as it is, and stops nothing.
"""
import os

from files import write_whole
from names import some
from refusal import Refused
from vaultlib import LINK, Vault, system_path

INDEX = system_path("index")
TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "brain", INDEX)
START = "<!-- brain index: the listing below is written by `brain index`; do not edit it by hand -->"
END = "<!-- brain index: end of the listing -->"
HEADINGS = {"concept": "Concepts", "entity": "Entities", "insight": "Insights", "decision": "Decisions",
            "episode": "Episodes"}
OTHER = "Other pages (not one of the five types: see `brain check`)"
EMPTY = "_Nothing yet._"
SHOWN = 8  # names printed of what was added or removed
AS_IT_IS = "surrogateescape"  # how the index is read and written: a byte that is no UTF-8 comes back as it was


class NoMarkers(Exception):
    """The index has no place marked for the listing; it was not touched."""


def line(page):
    return f"- [[{page.stem}]]" + (f" - {page.summary}" if page.summary else "")


def listing(vault):
    """The text between the markers: a section for each type, each page on a line with its summary."""
    groups = {kind: [] for kind in HEADINGS}
    for page in vault.knowledge:
        groups.setdefault(page.type if page.type in HEADINGS else OTHER, []).append(page)
    blocks = []
    for kind, pages in groups.items():
        rows = [line(p) for p in sorted(pages, key=lambda p: (p.stem, p.rel))] or [EMPTY]
        blocks.append(f"## {HEADINGS.get(kind, OTHER)}\n\n" + "\n".join(rows))
    return "\n\n".join(blocks)


def split(text):
    """(what is before the listing, the listing, what is after it), the marker lines kept outside; or NoMarkers."""
    lines = text.splitlines(keepends=True)
    marks = [i for i, row in enumerate(lines) if row.strip() in (START, END)]
    if len(marks) != 2 or lines[marks[0]].strip() != START or lines[marks[1]].strip() != END:
        raise NoMarkers(f"{INDEX} has no place marked for the listing. Put these two lines around the sections that "
                        f"list pages (above `## Gaps`), then run `brain index` again:\n{START}\n{END}")
    first, last = marks
    return "".join(lines[:first + 1]), "".join(lines[first + 1:last]), "".join(lines[last:])


def rebuild(root, dry_run=False, today=None):
    """Rewrite the listing from the pages; {listed, added, removed, changed, written}. Raises NoMarkers."""
    path = os.path.join(root, INDEX)
    with open(path if os.path.exists(path) else TEMPLATE, encoding="utf-8", errors=AS_IT_IS) as fh:
        text = fh.read()
    before, old, after = split(text)
    vault = Vault(root, today=today)
    new = "\n" + listing(vault) + "\n\n"
    was = {t.strip().lower() for t in LINK.findall(old)}
    now = [p.stem for p in vault.knowledge]
    changed = new != old or not os.path.exists(path)
    if changed and not dry_run:
        write_whole(path, before + new + after, errors=AS_IT_IS)
    return {"listed": len(now), "added": sorted(s for s in now if s.lower() not in was),
            "removed": sorted(was - {s.lower() for s in now}), "changed": changed, "written": changed and not dry_run}


def render(result, args):
    if not result["changed"]:
        return f"index: up to date ({result['listed']} pages listed)"
    parts = [f"index: {result['listed']} pages listed" if result["written"]
             else f"index: would list {result['listed']} pages (dry run, nothing written)"]
    parts += [f"added {some(result['added'], SHOWN)}"] if result["added"] else []
    parts += [f"removed {some(result['removed'], SHOWN)}"] if result["removed"] else []
    parts += ["the lines changed, not the pages listed"] if not result["added"] and not result["removed"] else []
    return "; ".join(parts)


def arguments(ap):
    ap.add_argument("--dry-run", action="store_true")


def run(root, args):
    try:
        return rebuild(root, args.dry_run)
    except NoMarkers as why:
        raise Refused(f"brain index: {why}") from None
