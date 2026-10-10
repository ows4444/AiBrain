"""Bring a page back from dormant/: the way back that fading did not have.

Usage:
    brain restore NAME [--dry-run] [--json]

NAME is the faded page's file name, title or alias. The page goes back to the
folder of its type in cortex/, under its own file name, and the index is
rewritten so that it lists it. One line is logged first, as for any move:
`DATE HH:MM maintain restore <name> -> [[name]], back from dormant/ to <path>`.
Its text is not touched, and `updated:` stays: nobody edited it.

From then on a link to it is a link again (`brain check` stops listing it as
faded), search and recall return it without --dormant, and it is rehearsed
and counted like any page. Unlinked and unused, it will be proposed for
fading again, so link it from where it is needed.

Refused, with nothing moved: no page of that name in dormant/, two that answer
to it, a page of that name already in cortex/, or a page whose type has no
folder there. --dry-run says what would move and where.
"""
import contextlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import log  # noqa: E402
from commands import Refused  # noqa: E402
from index import NoMarkers, rebuild  # noqa: E402
from vaultlib import Vault  # noqa: E402

FOLDER = {"concept": "concepts", "entity": "entities", "insight": "insights", "decision": "decisions",
          "episode": "episodes"}


def restore(root, name, dry_run=False, today=None):
    """Log the move, move the page, rewrite the index; {page, was, line, restored}. Raises Refused."""
    vault = Vault(root, today=today)
    wanted = name.strip().lower()
    faded = [p for p in vault.dormant_pages if wanted in {p.stem.lower(), p.title.lower(), *(a.lower() for a in p.aliases)}]
    if not faded:
        raise Refused(f"no page named '{name}' in dormant/ (`brain search \"{name}\" --dormant` finds what is there)")
    if len(faded) > 1:
        raise Refused(f"'{name}' is the name of {len(faded)} pages in dormant/: {', '.join(p.rel for p in faded)}; "
                      "give the file name of one")
    page = faded[0]
    if page.type not in FOLDER:
        raise Refused(f"{page.rel} has type '{page.type}', which has no folder in cortex/: set its `type:` first")
    to = os.path.join("cortex", FOLDER[page.type], page.stem + ".md")
    if vault.resolve(page.stem) is not None or os.path.exists(os.path.join(root, to)):
        raise Refused(f"a page named '{page.stem}' is already in cortex/: `/maintain merge` the two, or rename one")
    line = log.write(root, "maintain", f"restore {page.stem}", [page.stem], f"back from dormant/ to {to}",
                     dry_run=dry_run, today=today)["line"]
    if not dry_run:
        os.makedirs(os.path.dirname(os.path.join(root, to)), exist_ok=True)
        os.replace(page.path, os.path.join(root, to))
        with contextlib.suppress(NoMarkers):  # an index kept wholly by hand is the owner's to bring up to date
            rebuild(root, today=today)
    return {"page": to, "was": page.rel, "line": line, "restored": not dry_run}


def arguments(ap):
    ap.add_argument("name")
    ap.add_argument("--dry-run", action="store_true")


def run(root, args):
    try:
        return restore(root, args.name, args.dry_run)
    except Refused as why:
        raise Refused(f"brain restore: {why}") from None


def render(result, args):
    done = "restored" if result["restored"] else "would restore"
    return f"{done}: {result['was']} -> {result['page']}\n  logged: {result['line']}" if result["restored"] else \
        f"{done}: {result['was']} -> {result['page']} (dry run, nothing moved)"
