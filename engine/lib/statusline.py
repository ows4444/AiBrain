"""brain statusline: the queues and the context fill, on one line.

For Claude Code's status line (`statusLine` in the brain's
`.claude/settings.json`, command `brain statusline`). Claude Code runs it after
each reply and shows what it prints under the prompt; none of it enters the
context, so the owner sees the queues all session at no cost in tokens.

    brain | senses 0 | sleep 0 | rehearse 2 | context 5%

`senses` is input not yet encoded, `sleep` the episodes and decisions awaiting
consolidation, `rehearse` the pages due. Inbox notes, reminders due and
decisions to review are added only when there are any. `context` is how full
the context window is, from the JSON Claude Code passes on stdin; run by hand,
with no stdin, the line ends before it. A caller that leaves stdin open and
sends nothing (a shell tool, a script) gets the line without it after a short
wait, not a hang.

`--bar` is the form for Claude Code's own row: short, quiet and on the right.

    🧠 🔁 2 · 🧩 64%

Only what needs the owner is shown: a count above zero (👀 senses, 📥 inbox,
💤 sleep, 🔁 rehearse, ⏰ reminders, 🧭 decisions) and the context fill once
it reaches CONTEXT_SHOWN. Nothing to show prints nothing, and the row is
empty. The line is pushed to the right edge with spaces, from the `COLUMNS`
Claude Code sets. Skills and scripts read the plain form, which never changes.

It never fails loudly: a status line that prints a traceback is worse than none.
A crash leaves one line in the error log (`brain errors`) and prints nothing.
`--json` gives the six counts, `context` (the fill, or null) and the `line`.
"""
import json
import os
import select
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errlog import note  # noqa: E402
from vaultlib import Vault  # noqa: E402


STDIN_WAIT = 0.5  # seconds to wait for Claude Code's JSON before printing without it
CONTEXT_SHOWN = 60  # the bar shows the context fill from this percentage up
MARGIN = 4          # cells kept free at the right edge, which Claude Code pads itself
ICONS = {"senses": "👀", "inbox": "📥", "sleep": "💤", "rehearse": "🔁", "reminders": "⏰", "decisions": "🧭"}


def context_fill(payload):
    """The context window's fill as a whole percentage, or None when Claude Code did not say."""
    window = payload.get("context_window") if isinstance(payload, dict) else None
    used = window.get("used_percentage") if isinstance(window, dict) else None
    return round(used) if isinstance(used, (int, float)) else None


def counts(root):
    vault = Vault(root)
    inbox = os.path.join(root, "inbox")
    notes = [f for f in (os.listdir(inbox) if os.path.isdir(inbox) else []) if not f.startswith(".") and f != "README.md"]
    return {"senses": len(vault.unencoded()), "sleep": len(vault.unconsolidated()),
            "rehearse": len(vault.due_for_rehearsal()), "inbox": len(notes),
            "reminders": len(vault.due_intentions()), "decisions": len(vault.decisions_due())}


def line(found, fill=None):
    parts = [f"{label} {found[label]}" for label in ("senses", "sleep", "rehearse")]
    parts += [f"{label} {found[label]}" for label in ("inbox", "reminders", "decisions") if found[label]]
    if fill is not None:
        parts.append(f"context {fill}%")
    return "brain | " + " | ".join(parts)


def cells(text):
    """How many terminal cells `text` takes: an emoji takes two."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def bar(found, fill=None, columns=0):
    """The short form: only what needs the owner, at the right edge; "" when nothing does."""
    parts = [f"{icon} {found[label]}" for label, icon in ICONS.items() if found[label]]
    if fill is not None and fill >= CONTEXT_SHOWN:
        parts.append(f"🧩 {fill}%")
    if not parts:
        return ""
    text = "🧠 " + " · ".join(parts)
    return " " * max(0, columns - MARGIN - cells(text)) + text


def sent():
    """What Claude Code passed on stdin, or {}: nothing came within STDIN_WAIT, or it was not JSON."""
    if not sys.stdin.isatty() and select.select([sys.stdin], [], [], STDIN_WAIT)[0]:
        try:
            return json.load(sys.stdin)
        except ValueError:
            pass
    return {}


def arguments(ap):
    ap.add_argument("--bar", action="store_true")


def run(root, args):
    try:
        fill = context_fill(sent())
        found = counts(root)
        columns = os.environ.get("COLUMNS", "")
        text = bar(found, fill, int(columns) if columns.isdigit() else 0) if args.bar else line(found, fill)
        return dict(found, context=fill, line=text)
    except Exception:  # noqa: BLE001  see the docstring
        note("statusline", "error", root=root)
        return {"line": ""}


def render(result, args):
    return result["line"]
