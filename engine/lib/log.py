"""Write one line to the log: the one way a procedure records an operation or a recall.

Usage:
    brain log OP [WHAT ...] [--pages NAME ...] [--result TEXT] [--dry-run] [--json]

    brain log recall "how long should the gap between sessions be" --pages spacing-effect cepeda-2006
    brain log recall "what is the capital of Australia"          no page answered: `-> none`
    brain log recall rehearse --pages spacing-effect             the owner recalled it
    brain log rehearse missed --pages forgetting-curve           the owner did not
    brain log ingest senses/2026-10-09-note.md --result "1 episode, 2 candidates, 4 links"
    brain log decide "weekly review" --pages weekly-review --result "review 2027-01-09"

Appends `DATE <operation> <what> -> <result>` to hippocampus/log.md. The
result is the pages as [[links]], then --result; `none` when there is neither.
WHAT comes before --pages. Nothing is written unless all of this holds:
    the operation is one of CLAUDE.md > Log
    every name under --pages, and every [[link]] typed in WHAT or --result, is
        a page here or in dormant/. An unknown name is refused with the closest
        one: a misspelt page in a recall line strengthens nothing, and no check
        would say so until much later
    a rehearsal line (`recall rehearse`, `rehearse missed`) names a page
    the line holds no credential
The date is today's, set here. WHAT is put on one line; for `recall` it is the
question as it was asked, cut at 120 characters. A page is written by its file
name, whatever name it was given by. Log before a page is removed, renamed or
moved, while its name still resolves. --dry-run prints the line and writes
nothing.
"""
import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from secret_scan import scan_text  # noqa: E402
from vaultlib import (LINK, LOG_LINE, LOG_PATH, OPS, Event, Vault, is_rehearsal_miss,  # noqa: E402
                      is_rehearsal_pass)

QUESTION_MAX = 120
HEADER = "---\ntitle: Log\ntype: log\n---\n\n# Log\n\n"


def one_line(text):
    return " ".join(str(text).split())


def page_name(vault, name):
    """How a link to this page is written: its file name, or the name given when the page is in dormant/."""
    link = LINK.fullmatch(name.strip())
    name = (link.group(1) if link else name).strip()
    page = vault.resolve(name)
    if page is not None:
        return page.stem
    if name.lower() in vault.dormant_names:
        return name
    close = difflib.get_close_matches(name.lower(), sorted(vault.names), n=1)
    raise Refused(f"no page named '{name}'" + (f" (closest: {vault.names[close[0]].stem})" if close else ""))


def compose(vault, op, what="", pages=(), result=""):
    """(the line, the pages it names after the arrow), or Refused: the line breaks a rule of the log."""
    if op not in OPS:
        raise Refused(f"'{op}' is not an operation of the log; one of: {', '.join(OPS)}")
    # An arrow in the question would be read as the start of the result.
    what = one_line(what).replace("->", "→")
    if op == "recall":
        what = what[:QUESTION_MAX].rstrip()
    names = []
    for given in pages:
        name = page_name(vault, given)
        if name not in names:
            names.append(name)
    result = one_line(result)
    for typed in LINK.findall(what + " " + result):
        page_name(vault, typed)
    as_read = Event("", None, op, "", what, [], True)  # the engine decides what a rehearsal line is
    if (is_rehearsal_pass(as_read) or is_rehearsal_miss(as_read)) and not names:
        raise Refused("a rehearsal line names the pages rehearsed: give --pages")
    after = ", ".join([f"[[{n}]]" for n in names] + ([result] if result else [])) or "none"
    line = " ".join(part for part in (vault.today.isoformat(), op, what, "->", after) if part)
    found = scan_text(line, personal=False)
    if found:
        raise Refused(f"the line holds a possible credential ({found[0][0]}), which is not repeated here")
    return line, names


def lead(existing):
    """What goes before the line: the end of a line left open, and a blank line under prose."""
    out = "" if existing.endswith("\n") else "\n"
    last = existing.rstrip().rsplit("\n", 1)[-1]
    if not LOG_LINE.match(last.strip()) and not existing.endswith("\n\n"):
        out += "\n"  # the first line stands apart from the text above it
    return out


def append(root, line):
    """Add the line to the log: one write, at the end. A log that is missing or empty gets its heading first."""
    path = os.path.join(root, LOG_PATH)
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            existing = fh.read()
    blank = not existing.strip()
    with open(path, "w" if blank else "a", encoding="utf-8") as fh:
        fh.write((HEADER if blank else lead(existing)) + line + "\n")


def write(root, op, what="", pages=(), result="", dry_run=False, today=None):
    """Check the line and write it; {line, pages, written}. Raises Refused, having written nothing."""
    line, names = compose(Vault(root, today=today), op, what, pages, result)
    if not dry_run:
        append(root, line)
    return {"line": line, "pages": names, "written": not dry_run}


def arguments(ap):
    ap.add_argument("op")
    ap.add_argument("what", nargs="*")
    ap.add_argument("--pages", nargs="*", default=[])
    ap.add_argument("--result", default="")
    ap.add_argument("--dry-run", action="store_true")


def run(root, args):
    try:
        return write(root, args.op, " ".join(args.what), args.pages, args.result, args.dry_run)
    except Refused as why:
        raise Refused(f"brain log: {why}; nothing was written") from None


def render(result, args):
    return ("logged: " if result["written"] else "would log: ") + result["line"]
