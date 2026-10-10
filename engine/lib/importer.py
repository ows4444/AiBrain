"""Bring notes kept in another tool into senses/, one input a note. An Obsidian vault is the first source.

Usage:
    brain import obsidian VAULT [--dry-run] [--json]

Every Markdown note of the vault becomes one input, copied byte for byte to
senses/obsidian/<the vault's folder name>/<the note's path in the vault>.
Nothing is encoded: the notes wait in senses/ as any input does, and /ingest
takes them from there (a vault is an archive: it is triaged, ten at a time).

It never overwrites, and a second run adds nothing. What it leaves out:
    already there   the same note, unchanged since it was imported
    changed since   the note was edited at the source after its import. An
                    input is never edited, so the new text is not brought in:
                    the note is listed. To keep the new version, save it
                    there under another name and import again
    same as         its text is already an input under another path
    forgotten       the owner had this input removed (brain forget), by its
                    path or by its text: an import does not bring it back
    README.md       senses/ reads no file of that name as an input, so it
                    would land and never be encoded: rename it at the source
    empty           a note with no text
Also left out: `.obsidian/`, `.trash/` and other hidden folders, the brain
itself when it is kept inside the vault, and whatever is not Markdown.
Attachments are counted, not copied: put the ones that carry an argument into
senses/assets/ by hand. Two vaults whose folders share a name land in one
folder; a note at the same path in both is listed as changed, never replaced.

VAULT must not be inside this brain. --dry-run says what would be imported
and writes nothing.
"""
import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from fingerprint import forgotten, forgotten_hashes, inputs, sha256  # noqa: E402

UNREAD = "README.md"  # in any folder of senses/, the note on the folder and never an input


def obsidian(vault, brain):
    """([(a note's path in the vault, its full path)] for each Markdown note by path, how many other files there are)."""
    notes, others = [], 0
    for folder, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and os.path.realpath(os.path.join(folder, d)) != brain)
        for name in sorted(f for f in files if not f.startswith(".")):
            path = os.path.join(folder, name)
            if name.lower().endswith(".md"):
                notes.append((os.path.relpath(path, vault).replace(os.sep, "/"), path))
            else:
                others += 1
    return sorted(notes), others


SOURCES = {"obsidian": obsidian}


def text_of(path):
    """(the sha256 of a note, whether it holds no text)."""
    with open(path, "rb") as fh:
        data = fh.read()
    return hashlib.sha256(data).hexdigest(), not data.strip()


def bring_in(root, source, where, dry_run=False):
    """Copy what is new. Raises Refused for a folder that is not there or is inside the brain.

    {source, from, into, imported, already, changed, duplicates, forgotten, not_inputs, empty, attachments, written}:
    `imported` and `changed` are paths from the brain's root, the other lists paths in the source.
    """
    where, brain = os.path.realpath(where), os.path.realpath(root)
    if not os.path.isdir(where):
        raise Refused(f"not a folder: {where}")
    if os.path.commonpath([where, brain]) == brain:
        raise Refused("that folder is inside this brain: an import brings notes in from somewhere else")
    notes, others = SOURCES[source](where, brain)
    into = f"senses/{source}/{os.path.basename(where)}"
    held = {sha256(os.path.join(root, rel)): rel for rel in inputs(root)}  # every input here, by its text
    gone, gone_text = forgotten(root), forgotten_hashes(root)
    found = {"imported": [], "already": 0, "changed": [], "duplicates": [], "forgotten": [], "not_inputs": [], "empty": 0}
    for rel, path in notes:
        to = f"{into}/{rel}"
        digest, blank = text_of(path)
        if os.path.exists(os.path.join(root, to)):
            if sha256(os.path.join(root, to)) == digest:
                found["already"] += 1
            else:
                found["changed"].append(to)
        elif to in gone or digest in gone_text:
            found["forgotten"].append(rel)
        elif os.path.basename(rel) == UNREAD:
            found["not_inputs"].append(rel)
        elif blank:
            found["empty"] += 1
        elif digest in held:
            found["duplicates"].append({"note": rel, "same_as": held[digest]})
        else:
            found["imported"].append(to)
            held[digest] = to
            if not dry_run:
                os.makedirs(os.path.dirname(os.path.join(root, to)), exist_ok=True)
                shutil.copyfile(path, os.path.join(root, to))
    return dict(found, source=source, into=into, attachments=others, written=not dry_run, **{"from": where})


def arguments(ap):
    ap.add_argument("source", choices=sorted(SOURCES))
    ap.add_argument("path", help="where the notes are: for obsidian, the vault's folder")
    ap.add_argument("--dry-run", action="store_true")


def run(root, args):
    try:
        return bring_in(root, args.source, args.path, args.dry_run)
    except Refused as why:
        raise Refused(f"brain import: {why}") from None


def render(r, args):
    n = len(r["imported"])
    out = [f"import {r['source']}: {n} notes -> {r['into']}/" + ("" if r["written"] else " (dry run, nothing written)"),
           f"  left out: {r['already']} already there, {len(r['changed'])} changed since their import, "
           f"{len(r['duplicates'])} the same as another input, {len(r['forgotten'])} forgotten, "
           f"{len(r['not_inputs'])} named {UNREAD}, {r['empty']} empty; {r['attachments']} other files not copied"]
    if r["changed"]:
        out.append("  changed at the source since their import (an input is never edited, so not brought in again):")
        out += [f"    {path}" for path in r["changed"]]
    out += [f"  the same as {d['same_as']}: {d['note']}" for d in r["duplicates"]]
    out += [f"  forgotten on the owner's word, not brought back: {note}" for note in r["forgotten"]]
    out += [f"  not read as an input under that name (rename it at the source): {note}" for note in r["not_inputs"]]
    if n and r["written"]:
        out.append("  /ingest encodes them: nothing is memory until then")
    return "\n".join(out)
