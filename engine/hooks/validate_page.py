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

CHARACTER.md, at the brain's root, is no memory page and has no frontmatter:
only the traits under its `## Traits` are checked (a name that is no trait, a
value outside 0 to 1), as an override in tuning.md is. Its prose is the owner's.

A page with text and no `summary:` is blocked on the first pass only, and
only when the write is what leaves it so: a new page, or a scaffold whose
sections are being filled. Pages from before the field existed stay editable;
`brain check` lists them.

Pages written another way are caught by `brain check`, which /commit runs.

The contract itself is the engine's library (vaultlib), loaded only once the
call is known to name a page. If the library cannot be loaded, this wall has
raised: shared.py logs it, blocks the write when it goes into cortex/decisions/
and lets it through anywhere else, where `brain check` still catches the page.
Runs on its own (`--pre` for the first pass), or as two of gate.py's walls.
"""
import os
import sys

import shared
from shared import CHARACTER_FILE, MEMORY_DIRS, PROJECTS_DIR, ROOT, fold


def library():
    """The engine's library, where the page contract is written down once."""
    sys.path.insert(0, shared.LIB)
    import vaultlib
    return vaultlib


def target(path):
    """(full path, rel, project?) when the path is a page this hook checks, else None."""
    full = shared.full_path(path)
    parts = os.path.relpath(full, ROOT).split(os.sep)
    if len(parts) == 1 and fold(parts[0]) == fold(CHARACTER_FILE):
        return full, CHARACTER_FILE, False  # no memory page: only the traits it names are checked
    # Cortex/ is cortex/ where the file system ignores case; the page is checked either way.
    parts[0] = fold(parts[0])
    rel = os.sep.join(parts)
    # A folder's README is documentation, not a page: Vault skips it too.
    in_memory = parts[0] in MEMORY_DIRS and fold(rel).endswith(".md") and parts[-1] != "README.md"
    is_project = len(parts) == 3 and parts[0] == PROJECTS_DIR and parts[2] == "CLAUDE.md"
    return (full, rel, is_project) if in_memory or is_project else None


def problems_in(lib, text, rel, is_project):
    if rel == CHARACTER_FILE:
        return lib.character_problems(text)
    parts = rel.split(os.sep)
    return lib.schema_problems(text, lib.tag_vocabulary(ROOT), page_type="project" if is_project else None,
                               stem=parts[1] if is_project else os.path.splitext(parts[-1])[0], rel=rel)


def verdict(rel, problems, lead):
    if not problems:
        return None
    return shared.block("validate_page", "schema", f"{lead}: " + "; ".join(problems) + ". See CLAUDE.md > Page contracts.",
                        detail=f"{rel}: " + "; ".join(problems))


def before(data):
    """The first pass (PreToolUse): a Verdict when the write would leave a problem the page did not have."""
    tool, args = data.get("tool_name", ""), data.get("tool_input", {}) or {}
    found = target(args.get("file_path", ""))
    if not found or tool not in shared.WRITES:
        return None
    full, rel, is_project = found
    lib = library()
    was_text = ""
    if os.path.exists(full):
        with open(full, encoding="utf-8", errors="replace") as fh:
            was_text = fh.read()
    was = set(problems_in(lib, was_text, rel, is_project)) if was_text else set()
    after = shared.text_after(tool, args, was_text)
    problems = [p for p in problems_in(lib, after, rel, is_project) if p not in was]
    if not is_project and rel != CHARACTER_FILE and not (was_text and lib.summary_problems(was_text)):
        problems += lib.summary_problems(after)
    return verdict(rel, problems, f"Blocked before writing {rel}")


def written(data):
    """The second pass (PostToolUse): a Verdict when the file as written breaks the contract."""
    found = target((data.get("tool_input", {}) or {}).get("file_path", ""))
    if not found or not os.path.exists(found[0]):
        return None
    full, rel, is_project = found
    with open(full, encoding="utf-8", errors="replace") as fh:
        return verdict(rel, problems_in(library(), fh.read(), rel, is_project), rel)


if __name__ == "__main__":
    shared.main(("validate_page", before if "--pre" in sys.argv[1:] else written))
