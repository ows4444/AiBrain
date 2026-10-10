---
name: restore
description: >-
  Bring a faded page back from dormant/ into cortex/ and the index. Use for /restore, "bring back X", "undo the fade", or when a dormant page turns out to be needed. Not for inputs removed by forget.
argument-hint: "<page>"
---

# Restore

Bring $ARGUMENTS back from `dormant/`.

A page fades when nothing uses it. Being asked for again is the best sign it
was worth keeping, and until now nothing moved one back.

## Core rule

The move is logged before it is made, and the page comes back as it was:
restoring does not rewrite it.

## Workflow

1. **Find it** when the name is not certain: `brain search "<words>" --dormant`.
2. **Show the move:** `brain restore <page> --dry-run` names where it will
   go (the folder of its type in `cortex/`). It refuses, and says why, when
   no such page is in `dormant/`, when two answer to the name, or when a
   page of that name is already in `cortex/` (then it is a merge: `/maintain`).
3. **Restore** when the owner asked for this page, or says yes: `brain
   restore <page>`. It writes the log line itself (`maintain restore <page>`),
   moves the file and rewrites the index: do not also run `brain log` for
   the move, or move the file by hand.
4. **Check:** `brain check` no longer lists links to it under pages that
   faded. Say which pages link it again.
5. **Give it a reason to stay.** A restored page that nothing links or
   recalls is proposed for fading again. If a question brought it back, answer
   it and log that as usual: `brain log recall "<the question>" --pages
   <page>`. Otherwise name the page or project that should link it, and offer
   to add the link.

## Output

```
Restored: dormant/<file> -> cortex/<folder>/<file>
Linked from: <pages, or none yet>
```
