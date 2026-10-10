#!/usr/bin/env python3
"""PreToolUse: the log is append-only, and `brain log` is the one way a line gets into it.

hippocampus/log.md is the only record of what the brain was used for: recall
strength, pair weights, rehearsal dates and fading are all read from it. A
line typed into it by hand can misspell a page, which then strengthens
nothing, or change a line already there. This hook refuses any Write, Edit or
MultiEdit of that file and names the command that writes a line after checking
it. Shell commands are not seen here: `brain check` fails on a line changed or
removed since the last commit, and lists a line that names no page.

Self-contained, like protect_senses and protect_expected: no imports to break.
"""
import contextlib
import json
import os
import sys

START = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))


def brain_root(start):
    """The nearest folder at or above `start` holding cortex/ and hippocampus/, else `start`.

    A session opened in prefrontal/<name>/ is still inside its brain (vaultlib.find_brain, kept import-free here).
    """
    here = start
    while True:
        if all(os.path.isdir(os.path.join(here, d)) for d in ("cortex", "hippocampus")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return start
        here = parent


ROOT = brain_root(START)
LOG = os.path.join("hippocampus", "log.md")
MESSAGE = ("Blocked: hippocampus/log.md is append-only and is never written by hand. Run "
           "`brain log <operation> <what> --pages <page> ... --result <text>` (CLAUDE.md > Log): it checks the "
           "operation and every page name, sets the date and appends the line.")


def main():
    if not all(os.path.isdir(os.path.join(ROOT, d)) for d in ("cortex", "hippocampus")):
        sys.exit(0)  # not a brain: the plugin may be enabled in other projects
    try:
        data = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    tool, args = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    path = args.get("file_path", "")
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(START, path))
    rel = os.path.relpath(full, ROOT)
    # macOS and Windows file systems are case-insensitive: Hippocampus/Log.md is hippocampus/log.md.
    where = rel.lower() if sys.platform == "darwin" else os.path.normcase(rel)
    if tool not in ("Write", "Edit", "MultiEdit") or not path or where != LOG:
        sys.exit(0)
    print(MESSAGE, file=sys.stderr)
    with contextlib.suppress(Exception):  # the log must not add a way to fail
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
        from errlog import note
        note("protect_log", "log", MESSAGE)
    sys.exit(2)


if __name__ == "__main__":
    main()
