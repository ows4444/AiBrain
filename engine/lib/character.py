"""Who this brain is to its owner: what it holds to, and how it speaks.

Usage:
    brain character [--json]

Prints what CHARACTER.md says, the file at the brain's root that the wake-up
briefing opens every session with: its lines under their headings, without
the title and the note below it. `/character` writes it with the owner. A
brain without the file says so: it speaks as the rules of CLAUDE.md alone
have it speak.

The rules come first. A line of this page is how to speak, and what to lean
toward where the rules leave room. None of them can unmake a rule, and the
walls do not read the file: what they refuse, they refuse whatever it says.

Reads only. Another host asks for it through `brain mcp`, so that it answers
for this brain in the same voice.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_model import CHARACTER_FILE, character_lines  # noqa: E402


def said(lines):
    """The briefing's block and this command's text: a heading line, then the page's lines; [] when there are none."""
    return [f"Character ({CHARACTER_FILE}; the rules of CLAUDE.md come first):"] + ["  " + line for line in lines] if lines else []


def arguments(ap):
    pass


def run(root, args):
    return {"file": CHARACTER_FILE, "lines": character_lines(root)}


def render(result, args):
    return "\n".join(said(result["lines"])) or (f"character: this brain has no {result['file']}, or it says nothing yet. "
                                                "`/character` writes it with the owner")
