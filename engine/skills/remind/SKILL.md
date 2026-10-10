---
name: remind
description: >-
  Record "remind me to X when Y" (a date, time, repeat or event), list what is due, close reminders. Use for /remind, "remind me", "every Monday", "don't let me forget". Not for decisions (decide).
argument-hint: "<what> when <date [time] | every ... | event> | list | done <what>"
---

# Remind

Handle $ARGUMENTS: add a reminder, list them, or close one.

Prospective memory is remembering to do something later, triggered by a time
or by an event. The briefing and `brain tend --check` say what has come due;
`brain fit` holds every new input against the events.

## Core rule

One line per reminder in `hippocampus/intentions.md`, under `## Open`:
`- <what to do> when <when>`. A reminder is closed by ending its line with
`(done ...)` or `(dropped ...)`, never by deleting it. The page hook refuses
a `when` that could never come (`2026-02-30`, `every fortnight`).

## Modes

**Add.** Turn the owner's words into one line. The `when` part is one of:

- a day, `2026-11-01`, or a minute of one, `2026-11-01 10:00` ("next Friday
  at ten" becomes the date and time, read back for a yes);
- a repeat: `every day`, `every monday` (any weekday), `every month` (its
  first day), each with a time or without (`every monday 09:00`);
- an event something could be seen to report ("a rival cuts prices", "the
  paper is published"), in the words a source would use: `brain fit` marks
  it for an input that holds them. It cannot start with `every`.

"Later" or "sometime" gets a follow-up question. Log
`brain log remind "<what>" --result hippocampus/intentions.md`, with `<what>`
in the words of the line: a repeat is counted from that log line.

**List.** `brain introspect --remind`: what is due and since when, what waits
on an event, what repeats and its next round, and how the closed ones ended.

**Close.** Ask what happened, in one line. End the line with
`(done <today>: <what happened>)` or `(dropped <today>: <why>)`. A repeat is
different: leave its line as it is, since it comes round again, and end it
only with `(dropped ...)` when the owner wants it gone. Either way log
`brain log remind "done <what>" --result hippocampus/intentions.md`, in the
words of the line: for a repeat that log line is what says it was done.

## Output

```
Reminder: <what> | when: <date, repeat or event> | <added | done | dropped>
Due: <n> | waiting on events: <n> | repeating: <n>
```

A reminder that keeps being re-dated is a goal or a task in disguise: say so
once, and offer `/focus`.
