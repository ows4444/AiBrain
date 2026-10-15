---
name: capture
description: >-
  Keep a thought, link or quote for later without stopping the work: one note in inbox/, encoded at the next /ingest. Use for /capture, "note this", "jot this down", "save this for later".
argument-hint: "<the line to keep>"
---

# Capture

Keep $ARGUMENTS for later, in the owner's words, and go back to what was being done.

## Core rule

A note is the owner's line as they gave it. Capturing does not read it, link
it or judge it: `/ingest` does that, when they choose to.

## Workflow

1. `brain capture "<the line>"` writes it to `inbox/<date>-<slug>.md` and
   prints the path. Nothing else changes: no page, no index entry, and no
   log line. The note is logged when `/ingest` moves it into `senses/` and
   encodes it; until then the briefing counts it under Inbox.
2. Keep their words. Do not summarise, complete, translate or correct the
   line; an address stays an address, a half thought stays half.
3. One thought a note. Several given at once: one `brain capture` each.
4. Nothing to keep was given: ask what to capture. Never make the line up
   from the conversation: for that there is `/ingest session`, which shows
   a draft first.
5. It refuses a line that holds what looks like a credential. Say so, with
   the kind it named and never the value, and write nothing another way.

## Output

```
Captured: inbox/<date>-<slug>.md
```
