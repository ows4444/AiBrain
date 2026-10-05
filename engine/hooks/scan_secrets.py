#!/usr/bin/env python3
"""PostToolUse: a credential written into the brain is reported at once, never repeated.

Runs on every Write or Edit to senses/, inbox/, cortex/, prefrontal/ or
hippocampus/. Reports critical findings only (keys, tokens, private keys,
passwords in connection strings): personal data is too common in real input
to stop for, and `brain check --guard` lists it. The file is already written;
the message tells Claude to name the file and kind to the owner, never the
value. Copies made by shell commands are not seen; `brain check --guard` is.
"""
import json
import os
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from secret_scan import scan_file  # noqa: E402
from vaultlib import is_brain  # noqa: E402

WATCHED = ("senses", "inbox", "cortex", "prefrontal", "hippocampus")


def main():
    if not is_brain(ROOT):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    path = (data.get("tool_input", {}) or {}).get("file_path", "")
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(ROOT, path))
    rel = os.path.relpath(full, os.path.realpath(ROOT))
    if rel.split(os.sep)[0] not in WATCHED or not os.path.isfile(full):
        sys.exit(0)
    found = scan_file(full, personal=False)
    if found:
        where = ", ".join(f"{kind} on line {n}" for kind, _, n in found[:5])
        print(f"{rel}: possible credential ({where}). Do not quote it anywhere. Tell the owner the file and "
              "the kind, so they remove it at the source and rotate it; run /guard for the full scan.",
              file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
