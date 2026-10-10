"""What waits in inbox/, sorted before any of it lands in senses/, where nothing is edited again.

Usage:
    brain inbox [--json]

Reads every note in inbox/ and writes nothing. Each is one of:
    ready       text this brain does not hold: /ingest may move it into senses/ and encode it
    duplicate   its text is already an input, or an earlier note here: by its hash, as the fingerprints go
    forgotten   its text is an input the owner had removed (brain forget)
    secret      it holds what looks like a credential: the kind and the line, never the value
    empty       no text
    not text    a PDF or an image, which `brain extract` reads (else the model does); or a
                folder, a recording, text that is not UTF-8: nothing here reads those
A ready note that holds an email address or a phone number says so: it may
still be encoded, and the owner should know before it is.

This is the half a rule can decide. Whether a ready note can be understood
without the owner, or is a task and not something to remember, is a reading:
the `scout` agent's, which starts from this list.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import READERS  # noqa: E402
from fingerprint import forgotten_hashes, inputs, sha256  # noqa: E402
from secret_scan import TEXT_LIMIT, scan_text  # noqa: E402

INBOX = "inbox"
WHY = {"duplicate": "the same as {same_as}",
       "forgotten": "an input removed on the owner's word",
       "empty": "no text"}


def waiting(root):
    """The notes in inbox/, by name: what the briefing and the status line count."""
    folder = os.path.join(root, INBOX)
    return sorted(f for f in (os.listdir(folder) if os.path.isdir(folder) else [])
                  if not f.startswith(".") and f != "README.md")


def text_of(path):
    """A note's text; "" for a file that is not UTF-8 text, or is too large to be a note."""
    if os.path.getsize(path) > TEXT_LIMIT:
        return ""
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        return "" if b"\0" in data else data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def sort(root):
    """One row a note, by name: {note, kind, bytes} and what the kind needs said (same_as, found, personal, reader)."""
    held = {sha256(os.path.join(root, rel)): rel for rel in inputs(root)}  # every input here, by its content
    gone, rows = forgotten_hashes(root), []
    for name in waiting(root):
        rel, path = f"{INBOX}/{name}", os.path.join(root, INBOX, name)
        if os.path.isdir(path):
            rows.append({"note": rel, "kind": "not_text", "bytes": 0, "reader": None})
            continue
        row, digest, text = {"note": rel, "bytes": os.path.getsize(path)}, sha256(path), text_of(path)
        found = scan_text(text)
        secrets = [{"kind": kind, "line": line} for kind, severity, line in found if severity == "critical"]
        if not row["bytes"] or (text and not text.strip()):
            row["kind"] = "empty"
        elif secrets:  # before anything else: a credential is the one thing that must not land
            row.update(kind="secret", found=secrets)
        elif digest in gone:
            row["kind"] = "forgotten"
        elif digest in held:
            row.update(kind="duplicate", same_as=held[digest])
        elif not text:
            row.update(kind="not_text", reader=READERS.get(os.path.splitext(name)[1].lower(), (None,))[0])
        else:
            row.update(kind="ready", personal=[{"kind": kind, "line": line} for kind, _, line in found])
        held.setdefault(digest, rel)
        rows.append(row)
    return rows


def arguments(ap):
    pass


def run(root, args):
    rows = sort(root)
    return {"notes": rows, "ready": [row["note"] for row in rows if row["kind"] == "ready"]}


def said(found):
    return ", ".join(f"{f['kind']} on line {f['line']}" for f in found)


def note_line(row):
    kind = row["kind"]
    if kind == "ready":
        return f"  ready      {row['note']}" + (f" (personal: {said(row['personal'])})" if row["personal"] else "")
    if kind == "secret":
        return (f"  secret     {row['note']}: {said(row['found'])}. Not for senses/, where nothing is edited again: "
                "take the value out first")
    if kind == "not_text":
        return f"  not text   {row['note']}: " + (
            f"a PDF or an image: `brain extract` reads it where `{row['reader']}` is installed, else the model does"
            if row["reader"] else "nothing here reads it: say what it is, or bring it in as text")
    return f"  {kind:<10} {row['note']}: " + WHY[kind].format(**row)


def render(result, args):
    if not result["notes"]:
        return "inbox: nothing waiting"
    return "\n".join([f"inbox: {len(result['notes'])} notes, {len(result['ready'])} ready for /ingest",
                      *map(note_line, result["notes"])])
