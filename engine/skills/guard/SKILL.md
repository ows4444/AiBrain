---
name: guard
description: >-
  Scan for credentials, other people's private data and confidential work; check what is safe to publish. Use for /guard, "privacy", "secrets", "can I publish", before sharing. Report only.
argument-hint: "[publish | export]"
---

# Guard

Run the guard on $ARGUMENTS (`publish` for the publish check, `export` to write opted-in pages to `motor/export/`). Report only, except export.

A mature brain is one of the most revealing documents about a person, and it
sits in a folder that gets synced, committed and backed up. Every copy is
another place it exists.

## Core rule

Find and report. Never quote a credential; name the file and the type. Delete
nothing without an instruction naming what to remove.

## Modes

**Privacy** (default). Start from `brain check --guard`: it scans every file
in the brain for credentials (keys, tokens, private keys, passwords in
connection strings; these fail the check) and personal data (email addresses,
phone numbers; listed), by file, kind and line, never the value. The
`scan_secrets` hook already stops a credential written through Write or Edit.
Then look for what patterns cannot see: credentials in `.obsidian/plugins/`;
other people's private information; material under NDA or employer
restriction; the git remote's visibility.
Redaction after encoding is unreliable: say which concept pages and links
would need removing too.

**Publish.** Only pages with `publish: true`, never "everything not excluded".
Follow their links: a public page linking to a private one leaks its title or
breaks. Scan the set for the privacy categories above and for frontmatter not
meant to be public (`input:` paths, tags). Report; the owner runs the build.
To hand pages to a build, `brain export --published` (or page
names) writes them to `motor/export/`, turns links to unexported pages into
plain text and drops brain-only frontmatter. It stops and lists the titles of
unexported pages that would leave as that text; `--keep-titles` lets them
through, on the owner's word only. If asked to publish everything, ask what to do about the private material.

## Output

```
Critical: <credentials: remove and rotate>
High: <other people's private information>
Review: <owner decides>
Repo visibility: <public | private | no remote>
Publish: <n> pages | links to private pages <n> | verdict
```

Log `brain log guard <mode> --result "<n> critical, <n> high, <n> to review"`,
never naming what was found.

Err toward flagging: a false positive costs ten seconds, a leak is permanent.
