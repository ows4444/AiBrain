---
name: import
description: >-
  Bring notes kept in another tool (an Obsidian vault) into senses/, one input a note, then hand them to ingest. Use for /import, "import my vault", "bring in old notes". Not for a file or URL (ingest).
argument-hint: "obsidian <vault folder>"
---

# Import

Import $ARGUMENTS into `senses/`, then hand the notes to `/ingest`.

Notes kept elsewhere are input like any other: they land as they are, and
become memory only when they are encoded, a few at a time, by someone reading
them.

## Core rule

An import copies and never rewrites: one input a note, byte for byte, nothing
overwritten. It encodes nothing itself.

## Workflow

1. **Pick the importer** by where the notes are. `obsidian`: a vault's
   folder. No importer for the source: say so and stop; exported files can
   still go into `senses/` by hand.
2. **Look first:** `brain import <source> <folder> --dry-run` lists how many
   notes would land and where (`senses/<source>/<folder name>/`), and what it
   leaves out: notes already imported, notes changed since (an input is never
   edited), text that is already an input, what the owner had forgotten, a
   note named `README.md`, empty notes, attachments. Tell the owner the
   numbers and get a yes: a vault can be hundreds of inputs.
3. **Import:** `brain import <source> <folder>`. Running it again adds
   nothing.
4. **Privacy first:** `brain check --guard` over what landed, before any of
   it is encoded. A vault is years of unfiltered notes: name the files and
   kinds it finds, never the values.
5. **Hand off to `/ingest`:** more than twenty notes is an archive, and
   `ingest` says how: triage into encode, keep in `senses/`, or leave out;
   oldest first, ten a batch, each batch to the `encoder` agent, a go-ahead
   between batches.
6. **Log** the import itself, once: `brain log ingest "import <source>
   <folder name>" --result "<n> inputs landed in senses/<source>/<folder
   name>, none encoded yet"`. Each batch of `/ingest` then logs its own lines.

## Output

```
Imported: <n> notes -> senses/<source>/<folder name>/
Left out: <n> already there, <n> changed since, <n> duplicates, <n> forgotten, <n> empty, <n> attachments
Guard: <none | files and kinds>
Next: /ingest, <n> waiting
```
