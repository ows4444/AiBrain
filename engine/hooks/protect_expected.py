#!/usr/bin/env python3
"""PreToolUse: once a decision is made, what the owner expected is never rewritten.

A decision page records `## Expected` before the outcome is known; the gap
between that and `## Outcome` is the only thing /decide learns from. This hook
blocks a Write or Edit that would change a non-empty `## Expected` on a page
whose status on disk is `decided` or `reviewed`. Filling in an empty section is
allowed. So is nothing that takes the status back from `decided` or `reviewed`:
reopening the page would unfreeze the section. Shell edits are not seen; `brain
check` cannot see history either, so this wall is the check. Self-contained,
like protect_senses: no imports to break.
"""
import json
import os
import re
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
DECISIONS = os.path.join("cortex", "decisions", "")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
# Quotes are legal YAML and the schema check strips them, so the wall must too.
STATUS = re.compile(r"^status:\s*[\"']?(\w+)", re.M)
FROZEN = ("decided", "reviewed")
EXPECTED = re.compile(r"^## Expected\s*\n(.*?)(?=^## |\Z)", re.S | re.M)


def expected(text):
    m = EXPECTED.search(text)
    return " ".join(m.group(1).split()) if m else ""

def status_of(text):
    """The status in the frontmatter only: a `status:` line in the body is prose."""
    front = FRONTMATTER.match(text)
    m = STATUS.search(front.group(1)) if front else None
    return m.group(1) if m else None


def after(tool, args, before):
    """The page text the tool would leave behind."""
    if tool == "Write":
        return args.get("content", "")
    edits = args.get("edits") if tool == "MultiEdit" else [args]
    text = before
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def main():
    if not all(os.path.isdir(os.path.join(ROOT, d)) for d in ("cortex", "hippocampus")):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    tool, args = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    path = args.get("file_path", "")
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(START, path))
    rel = os.path.relpath(full, ROOT)
    # macOS and Windows file systems are case-insensitive: Cortex/Decisions/ is cortex/decisions/.
    where = rel.lower() if sys.platform == "darwin" else os.path.normcase(rel)
    if tool not in ("Write", "Edit", "MultiEdit") or not where.startswith(DECISIONS):
        sys.exit(0)
    if not os.path.isfile(full):
        sys.exit(0)
    with open(full, encoding="utf-8", errors="replace") as fh:
        before = fh.read()
    status = status_of(before)
    if status not in FROZEN:
        sys.exit(0)
    left = after(tool, args, before)
    if status_of(left) not in FROZEN:
        print(f"Blocked: {rel} is {status}; a decision is never reopened, since that would unfreeze "
              "its ## Expected. Record a change of mind as a new decision that links this one.", file=sys.stderr)
        sys.exit(2)
    was = expected(before)
    if was and expected(left) != was:
        print(f"Blocked: {rel} is {status}, and its ## Expected was written before the outcome was "
              "known. It is never rewritten; put what you learned under ## Outcome or ## Lessons.",
              file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
