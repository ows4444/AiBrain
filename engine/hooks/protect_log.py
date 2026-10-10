#!/usr/bin/env python3
"""PreToolUse: the log is append-only, and `brain log` is the one way a line gets into it.

hippocampus/log.md is the only record of what the brain was used for: recall
strength, pair weights, rehearsal dates and fading are all read from it. A
line typed into it by hand can misspell a page, which then strengthens
nothing, or change a line already there. This hook refuses any Write, Edit or
MultiEdit of that file and names the command that writes a line after checking
it. Shell commands are not seen here: `brain check` fails on a line changed or
removed since the last commit, and lists a line that names no page.

Needs nothing but the standard library and shared.py beside it, like
protect_senses and protect_expected: no import of the engine's to break. Runs
on its own, or as one of gate.py's walls.
"""
import os

import shared

LOG = os.path.join("hippocampus", "log.md")
MESSAGE = ("Blocked: hippocampus/log.md is append-only and is never written by hand. Run "
           "`brain log <operation> <what> --pages <page> ... --result <text>` (CLAUDE.md > Log): it checks the "
           "operation and every page name, sets the date and appends the line.")


def check(data):
    """The wall: a Verdict when the call is a Write, Edit or MultiEdit of the log."""
    tool, args = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    path = args.get("file_path", "")
    # macOS and Windows file systems are case-insensitive: Hippocampus/Log.md is hippocampus/log.md.
    if tool not in shared.WRITES or not path or shared.fold(shared.from_root(path)) != LOG:
        return None
    return shared.block("protect_log", "log", MESSAGE)


if __name__ == "__main__":
    shared.main(("protect_log", check))
