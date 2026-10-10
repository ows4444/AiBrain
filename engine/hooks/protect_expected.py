#!/usr/bin/env python3
"""PreToolUse: once a decision is made, what the owner expected is never rewritten.

A decision page records `## Expected` before the outcome is known; the gap
between that and `## Outcome` is the only thing /decide learns from. This hook
blocks a Write or Edit that would change a non-empty `## Expected` on a page
whose status on disk is `decided` or `reviewed`. Filling in an empty section is
allowed. So is nothing that takes the status back from `decided` or `reviewed`:
reopening the page would unfreeze the section. Shell edits are not seen; `brain
check` cannot see history either, so this wall is the check. Needs nothing but
the standard library and shared.py beside it, like protect_senses: no import
of the engine's to break. Runs on its own, or as one of gate.py's walls.
"""
import os

import shared
from shared import expected_of, status_of

DECISIONS = os.path.join("cortex", "decisions", "")
FROZEN = ("decided", "reviewed")


def refuse(message):
    return shared.block("protect_expected", "expected", message)


def check(data):
    """The wall: a Verdict when the call would rewrite a frozen `## Expected`, or reopen the decision that froze it."""
    tool, args = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    path = args.get("file_path", "")
    full, rel = shared.full_path(path), shared.from_root(path)
    # macOS and Windows file systems are case-insensitive: Cortex/Decisions/ is cortex/decisions/.
    if tool not in shared.WRITES or not shared.fold(rel).startswith(DECISIONS):
        return None
    if not os.path.isfile(full):
        return None
    with open(full, encoding="utf-8", errors="replace") as fh:
        before = fh.read()
    status = status_of(before)
    if status not in FROZEN:
        return None
    left = shared.text_after(tool, args, before)
    if status_of(left) not in FROZEN:
        return refuse(f"Blocked: {rel} is {status}; a decision is never reopened, since that would unfreeze "
                      "its ## Expected. Record a change of mind as a new decision that links this one.")
    was = expected_of(before)
    if was and expected_of(left) != was:
        return refuse(f"Blocked: {rel} is {status}, and its ## Expected was written before the outcome was "
                      "known. It is never rewritten; put what you learned under ## Outcome or ## Lessons.")
    return None


if __name__ == "__main__":
    shared.main(("protect_expected", check))
