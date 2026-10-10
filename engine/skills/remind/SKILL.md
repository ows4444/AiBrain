---
name: remind
description: >-
  Record "remind me to X when Y" (a date or an event), list what is due, close reminders. Use for /remind, "remind me", "don't let me forget", "what was I going to do". Not for decisions (decide).
argument-hint: "<what> when <date | event> | list | done <what>"
---

# Remind

Handle $ARGUMENTS: add a reminder, list them, or close one.

Prospective memory is remembering to do something later, triggered by a time
or by an event. The briefing checks the dates; `/ingest` checks every new
input against the events.

## Core rule

One line per reminder in `hippocampus/intentions.md`, under `## Open`:
`- <what to do> when <YYYY-MM-DD or an event>`. A reminder is closed by
ending its line with `(done)` or `(dropped)`, never by deleting it.

## Modes

**Add.** Turn the owner's words into one line. The `when` part is a date
(`2026-11-01`; "next Friday" becomes the date, read back for a yes) or an
event something could be seen to report ("a rival cuts prices", "the paper
is published"), in the words a source would use: `brain fit` marks it for
an input that holds them. "Later" or "sometime" gets a follow-up question. Log
`brain log remind "<what>" --result hippocampus/intentions.md`.

**List.** `brain introspect --remind`: what is due (date passed) and what is
waiting on an event.

**Close.** Add `(done)` or `(dropped)` to the end of the line. Log
`brain log remind "done <what>" --result hippocampus/intentions.md`.

## Output

```
Reminder: <what> | when: <date or event> | <added | done | dropped>
Due: <n> | waiting on events: <n>
```

A reminder that keeps being re-dated is a goal or a task in disguise: say so
once, and offer `/focus`.
