#!/usr/bin/env python3
"""PostToolUse: a credential written into the brain is reported at once, never repeated.

Runs on every Write or Edit to a folder `brain check --guard` scans: senses/,
inbox/, cortex/, prefrontal/, hippocampus/, dormant/ and motor/, where a draft
for outside the brain is written. Reports critical findings only (keys, tokens,
private keys, passwords in connection strings): personal data is too common in
real input to stop for, and `brain check --guard` lists it. The file is already
written; the message tells Claude to name the file and kind to the owner, never
the value. Copies made by shell commands are not seen; `brain check --guard` is.

The patterns are the engine's library (secret_scan), loaded only once the call
is known to name a watched file. Runs on its own, or as one of gate.py's walls.
"""
import os
import sys

import shared

# The library's SCANNED, kept here so that a write anywhere else loads nothing: a test holds the two equal.
WATCHED = ("senses", "inbox", "cortex", "prefrontal", "hippocampus", "dormant", "motor")


def check(data):
    """The wall: a Verdict when the file just written holds what looks like a credential."""
    path = (data.get("tool_input", {}) or {}).get("file_path", "")
    full, rel = shared.full_path(path), shared.from_root(path)
    if shared.fold(rel.split(os.sep)[0]) not in WATCHED or not os.path.isfile(full):
        return None
    sys.path.insert(0, shared.LIB)
    from secret_scan import scan_file
    found = scan_file(full, personal=False)
    if not found:
        return None
    where = ", ".join(f"{kind} on line {n}" for kind, _, n in found[:5])
    return shared.block("scan_secrets", "secret",
                        f"{rel}: possible credential ({where}). Do not quote it anywhere. Tell the owner the file and "
                        "the kind, so they remove it at the source and rotate it; run /guard for the full scan.",
                        detail=f"{rel}: {where}")


if __name__ == "__main__":
    shared.main(("scan_secrets", check))
