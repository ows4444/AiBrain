#!/usr/bin/env python3
"""Record a hash of every input in senses/, so "never edited after it lands" holds without git.

Usage:
    brain fingerprint [--json]

Appends `DATE <sha256> <path>` to hippocampus/fingerprints.md for each file in
senses/ that has no line yet (README.md and dotfiles excepted). `/ingest` runs
it after an input lands. `brain check` compares every recorded input with its
hash: changed or removed fails, in or out of a git repository, committed or
not. A file recorded once is never re-recorded, so a changed input cannot be
blessed by running this again: the owner restores it, or accepts the change
by moving the edited copy in as a new input. The only writer of that file.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

FINGERPRINTS = os.path.join("hippocampus", "fingerprints.md")
LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}) ([0-9a-f]{64}) (.+)$")
# `DATE forgotten <path>`: the owner had this input removed (brain forget). Its hash line stays above it.
FORGOTTEN = re.compile(r"^(\d{4}-\d{2}-\d{2}) forgotten (.+)$")
HEADER = """---
title: Fingerprints
type: fingerprints
---

# Fingerprints

A SHA-256 hash of every file in `senses/`, recorded when it is encoded, one
line each: `YYYY-MM-DD <sha256> <path>`. Written only by `brain fingerprint`
(which `/ingest` runs) and, as `YYYY-MM-DD forgotten <path>`, by `brain forget`; `brain check` fails when an input no longer matches
its hash, with or without git. Append only; never edit a previous line.
"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def inputs(root):
    """Root-relative paths (with /) of every input file in senses/, sorted."""
    out = []
    for dirpath, dirnames, files in os.walk(os.path.join(root, "senses")):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for f in sorted(files):
            if f.startswith(".") or f == "README.md":
                continue
            out.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    return out


def recorded(root):
    """{path: sha256} from fingerprints.md; the first record of a path is the one that counts."""
    path = os.path.join(root, FINGERPRINTS)
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m, gone = LINE.match(line.rstrip("\n")), FORGOTTEN.match(line.rstrip("\n"))
            if m:
                out.setdefault(m.group(3), m.group(2))
            elif gone:
                out.pop(gone.group(2), None)  # a file that lands there again later is a new input
    return out


def forgotten(root):
    """Paths the owner had removed with `brain forget`, from the fingerprints."""
    path = os.path.join(root, FINGERPRINTS)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        return {m.group(2) for m in (FORGOTTEN.match(line.rstrip("\n")) for line in fh) if m}


def fingerprint_problems(root):
    """What changed in senses/ against its recorded hashes: removed or changed inputs."""
    problems = []
    for rel, digest in sorted(recorded(root).items()):
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            problems.append(f"{rel}: input removed since it was fingerprinted")
        elif sha256(full) != digest:
            problems.append(f"{rel}: input changed since it was fingerprinted")
    return problems


def unrecorded(root):
    known = recorded(root)
    return [rel for rel in inputs(root) if rel not in known]


def record(root, today=None):
    """Append a line for each unrecorded input; return the paths recorded."""
    new = unrecorded(root)
    if not new:
        return []
    path = os.path.join(root, FINGERPRINTS)
    day = (today or datetime.date.today()).isoformat()
    exists = os.path.exists(path)
    with open(path, "a+", encoding="utf-8") as fh:
        fh.seek(0)
        text = fh.read()
        lead = "" if not text or text.endswith("\n") else "\n"
        fh.write((HEADER if not exists else lead) + "".join(f"{day} {sha256(os.path.join(root, r))} {r}\n"
                                                             for r in new))
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not os.path.isdir(args.root):
        sys.exit(f"not a directory: {args.root}")
    new = record(args.root)
    if args.json:
        print(json.dumps({"recorded": new}, indent=2))
    else:
        print(f"fingerprinted {len(new)} input{'s' * (len(new) != 1)}" + "".join(f"\n  {r}" for r in new))


if __name__ == "__main__":
    main()
