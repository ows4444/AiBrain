---
name: export
description: >-
  Hand chosen pages to the outside: check them for secrets and private data, then write clean copies to motor/export/. Use for /export, "export these pages", "send X to". Not for drafting (write).
argument-hint: "<page> ... | published"
---

# Export

Export $ARGUMENTS: the pages named, or with `published` every page marked `publish: true`.

What leaves the brain cannot be called back. An export is a copy made on
purpose, of pages chosen one by one, after someone looked.

## Core rule

Nothing leaves that was not chosen and checked. Never "everything", and
never a credential.

## Workflow

1. **Choose.** The pages the owner named, or `published`. Asked for the
   whole brain: ask which pages, and what to do about the private ones.
2. **Guard.** Hand the chosen pages to the `gatekeeper` agent. It reads
   them in a clean context, with none of this session's reasons for sharing
   them: `brain check --guard` for credentials and personal data, then each
   page for what a pattern cannot see (other people's private information,
   material under NDA or an employer's restriction, titles that would leak).
   Show the owner its verdict before exporting. On `stop`, stop: fix the
   page at the source, or leave it out.
3. **Export.** `brain export <page> ...` or `brain export --published`
   writes clean copies to `motor/export/`: brain-only frontmatter dropped,
   links to pages outside the export made plain text. It refuses, writing
   nothing, when a chosen page holds what looks like a credential, and it
   stops on the titles of unexported pages that would leave as plain text:
   list them, and pass `--keep-titles` only on the owner's word. It lists
   personal data in what was exported: put each to the owner.
4. **Log** `brain log guard export --result "<n> pages to motor/export/, <n>
   to review"`, never naming what was found.

## Output

```
Exported: <n> pages -> motor/export/
Refused: <none | file, kind and line of a credential: remove and rotate it>
Review: <personal data and private material the owner decides on, or none>
```
