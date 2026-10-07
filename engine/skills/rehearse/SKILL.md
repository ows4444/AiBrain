---
name: rehearse
description: >-
  Spaced retrieval practice from the owner's concept and insight pages: ask what is due, grade against the pages. Use for /rehearse, "quiz me", "test me", "explain it back", flashcards.
argument-hint: "[topic]"
---

# Rehearse

Rehearse $ARGUMENTS, or the pages that are due.

Retrieval practice beats rereading, and spacing beats cramming. Each
successful recall pushes a page's next review further out (1, 3, 7, 14, 30,
60, 120 days); a miss starts the page over at one day. Only these lines move
the schedule: a page the model read for `/ask` was not recalled by the owner.

## Core rule

Questions come from the pages, at the depth they record, never from general
knowledge. Grade against the page, not against what is true.

## Workflow

1. **Pick:** `brain introspect --due`, or the topic asked for. Five pages at
   most; the list already puts pages the owner's goals depend on first, then
   the more salient, then the pages the owner misses most (it shows the miss
   rate once a page has three rehearsals).
2. **Ask** two kinds of question: recall of what the page states, and
   application to a new case. For "explain it back", ask the owner to explain
   the topic from memory instead.
3. **Withhold answers** until attempted.
4. **Grade** against the page. A right answer the page contradicts is a page
   problem worth surfacing.
5. **Log** the pages answered well: `DATE recall rehearse -> [[page]], ...`,
   and the pages answered badly: `DATE rehearse missed -> [[page]], ...`. A
   miss comes back tomorrow. A page problem is neither: do not log that page.

## Output

```
<n> questions from <n> pages
1. ...
[after answers]
Solid: <pages> | Shaky: <pages to reread> | Page problems: <pages>
```

A page that cannot produce an application question records the source's
wording, not an understanding of it. Say so.
