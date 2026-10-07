#!/usr/bin/env python3
"""Every memory page and project page must carry valid frontmatter. Silent on success.

Checks the contract in CLAUDE.md > Page contracts (vaultlib.schema_problems).

    PreToolUse (--pre)  Write, Edit, MultiEdit: works out the text the tool
                        would leave and blocks it when that text has a problem
                        the page did not have before, so a bad page never
                        lands. A page that is already broken can still be
                        edited, one fix at a time.
    PostToolUse         the file as written: catches anything the first
                        pass could not see (an Edit whose old text was not found).

A page with text and no `summary:` is blocked on the first pass only, and
only when the write is what leaves it so: a new page, or a scaffold whose
sections are being filled. Pages from before the field existed stay editable;
`brain check` lists them.

Pages written another way are caught by `brain check`, which /commit runs.
"""
import json
import os
import sys

START = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from vaultlib import (MEMORY_DIRS, PROJECTS_DIR, find_brain, fold_case, is_brain, schema_problems,  # noqa: E402
                      summary_problems, tag_vocabulary)

# The brain may be above the folder the session started in (prefrontal/<name>/).
ROOT = find_brain(START) or START


def text_after(tool, args, before):
    """The page text the tool would leave behind (as protect_expected works it out)."""
    if tool == "Write":
        return args.get("content", "")
    edits = args.get("edits") if tool == "MultiEdit" else [args]
    text = before
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def target(path):
    """(full path, rel, project?) when the path is a page this hook checks, else None."""
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(START, path))
    parts = os.path.relpath(full, os.path.realpath(ROOT)).split(os.sep)
    # Cortex/ is cortex/ where the file system ignores case; the page is checked either way.
    parts[0] = fold_case(parts[0])
    rel = os.sep.join(parts)
    # A folder's README is documentation, not a page: Vault skips it too.
    in_memory = parts[0] in MEMORY_DIRS and fold_case(rel).endswith(".md") and parts[-1] != "README.md"
    is_project = len(parts) == 3 and parts[0] == PROJECTS_DIR and parts[2] == "CLAUDE.md"
    return (full, rel, is_project) if in_memory or is_project else None


def problems_in(text, rel, is_project):
    parts = rel.split(os.sep)
    return schema_problems(text, tag_vocabulary(ROOT), page_type="project" if is_project else None,
                           stem=parts[1] if is_project else os.path.splitext(parts[-1])[0], rel=rel)


def main():
    if not is_brain(ROOT):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    args = data.get("tool_input", {}) or {}
    found = target(args.get("file_path", ""))
    if not found:
        sys.exit(0)
    full, rel, is_project = found
    pre = "--pre" in sys.argv[1:]
    if pre:
        tool = data.get("tool_name", "")
        if tool not in ("Write", "Edit", "MultiEdit"):
            sys.exit(0)
        before = ""
        if os.path.exists(full):
            with open(full, encoding="utf-8", errors="replace") as fh:
                before = fh.read()
        was = set(problems_in(before, rel, is_project)) if before else set()
        after = text_after(tool, args, before)
        problems = [p for p in problems_in(after, rel, is_project) if p not in was]
        if not is_project and not (before and summary_problems(before)):
            problems += summary_problems(after)
    else:
        if not os.path.exists(full):
            sys.exit(0)
        with open(full, encoding="utf-8", errors="replace") as fh:
            problems = problems_in(fh.read(), rel, is_project)
    if problems:
        lead = f"Blocked before writing {rel}" if pre else rel
        print(f"{lead}: " + "; ".join(problems) + ". See CLAUDE.md > Page contracts.", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
