#!/usr/bin/env python3
"""PreToolUse: the policy page says what the brain may do with nobody there, so only the owner writes it.

hippocampus/policy.md is read by `brain act` each time an action is asked for
(lib/vault_policy.py). A run that could write the page could allow itself
anything, so the page is the owner's to change, by hand, in their own editor.
This hook refuses a Write, Edit, MultiEdit or NotebookEdit of it, and a shell
command that would change, replace or remove it, and says what to do instead:
show the owner the line.

The shell check is best-effort, as protect_senses' is: it catches the common
ways a shell changes a file (rm, mv, sed -i, >, tee, cp onto it). A command
that hides the name is not seen here. `git diff` shows any change to the page
before it is committed, and a run nobody watches is given no shell to begin with.

Needs nothing but the standard library and shared.py beside it, like the other
walls over what must not be undone or given away. Runs on its own, or as one
of gate.py's walls.
"""
import os
import re

import shared

POLICY = os.path.join("hippocampus", "policy.md")
MESSAGE = ("Blocked: hippocampus/policy.md says what this brain may do with nobody there, and only the owner writes "
           "it, by hand. Show them the line to add under `## Allowed` (`- <action> (why)`; `brain act` lists the "
           "actions) and why; `brain check` will read what they wrote.")
PAGE = r"(?:\./|[\w./-]*/)?(?<![\w.-])policy\.md(?![\w.-])"
# Each pattern stays on one line so prose in a heredoc does not trip it.
CHANGES = [re.compile(p, re.I | re.M) for p in (
    rf"(?:^|[\s;&|(])(?:rm|unlink|truncate|shred)\s[^|;&\n]*{PAGE}",
    rf"(?:^|[\s;&|(])(?:sed|perl|ruby)\s+(?:-\S*\s+)*-i\S*[^|;&\n]*{PAGE}",
    rf"(?:^|[\s;&|(])(?:cp|mv|rsync|install|ditto|ln)\s[^|;&\n]*{PAGE}",
    rf"(?:^|[\s\d&])>>?\s*{PAGE}",
    rf"(?:^|[\s;&|(])tee\b(?:\s+-\S+)*\s+{PAGE}",
)]


def check(data):
    """The wall: a Verdict when the call would write the policy page, or a shell command would change it."""
    tool, args = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    if tool == "Bash":
        command = str(args.get("command", ""))
        return shared.block("protect_policy", "policy", MESSAGE) if any(p.search(command) for p in CHANGES) else None
    path = args.get("file_path") or args.get("notebook_path") or ""
    # macOS and Windows file systems are case-insensitive: Hippocampus/Policy.md is hippocampus/policy.md.
    if not path or shared.fold(shared.from_root(path)) != POLICY:
        return None
    return shared.block("protect_policy", "policy", MESSAGE)


if __name__ == "__main__":
    shared.main(("protect_policy", check))
