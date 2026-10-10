"""Keep one line for later: a note in inbox/, where /ingest finds it.

Usage:
    brain capture TEXT ... [--json]

Writes TEXT, as it was given, to inbox/<today>-<slug>.md; the slug is its first
words, and a second note of the same words on the same day gets `-2`. That is
all it does: no page, no link, no log line. /ingest moves inbox notes into
senses/ and encodes them, and logs them then; until then the briefing and the
status line count them. A line that holds what looks like a credential is
refused and nothing is written.
"""
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from secret_scan import scan_text  # noqa: E402

INBOX = "inbox"
SLUG_WORDS, SLUG_CHARS = 6, 48  # of the note's first words, in its file name


def slug(text):
    words = re.findall(r"[a-z0-9]+", text.lower())[:SLUG_WORDS]
    return "-".join(words)[:SLUG_CHARS].strip("-") or "note"


def capture(root, text, today=None):
    """Write the note; {note, bytes}. Raises Refused for an empty line or one that holds a credential."""
    text = text.strip()
    if not text:
        raise Refused("nothing to capture: give the line to keep")
    found = scan_text(text, personal=False)
    if found:
        raise Refused(f"the line holds a possible credential ({found[0][0]}), which is not repeated here; "
                      "nothing was written")
    day = (today or datetime.date.today()).isoformat()
    folder = os.path.join(root, INBOX)
    os.makedirs(folder, exist_ok=True)
    name, n = f"{day}-{slug(text)}", 1
    while os.path.exists(os.path.join(folder, f"{name}{'' if n == 1 else f'-{n}'}.md")):
        n += 1
    rel = os.path.join(INBOX, f"{name}{'' if n == 1 else f'-{n}'}.md")
    with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return {"note": rel, "bytes": len(text.encode("utf-8")) + 1}


def arguments(ap):
    ap.add_argument("text", nargs="+")


def run(root, args):
    try:
        return capture(root, " ".join(args.text))
    except Refused as why:
        raise Refused(f"brain capture: {why}") from None


def render(result, args):
    return f"captured: {result['note']} (/ingest encodes it)"
