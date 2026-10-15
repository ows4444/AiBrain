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
4. **Grade** the answers on each page against that page, one of three:
   - `fully`: the answer held what the page states, and the application
     question, where one was asked, was answered from it;
   - `partly`: recalled, with a gap: a part missing or wrong, a hint needed,
     or the recall right and the application not;
   - `missed`: the answer did not hold what the page states, or none came.
   Grade what was answered, not how sure the owner sounded. A right answer
   the page contradicts is a page problem worth surfacing.
5. **Log** one line a grade, naming its pages:
   `brain log recall rehearse fully --pages <page> ...`,
   `brain log recall rehearse partly --pages <page> ...`,
   `brain log rehearse missed --pages <page> ...`.
   `fully` and `partly` both push the page's next review out; a miss comes
   back tomorrow. The grade is kept for the intervals fitted to it later. A
   page problem is none of the three: do not log that page.

## Output

```
<n> questions from <n> pages
1. ...
[after answers]
Fully: <pages> | Partly: <pages> | Missed: <pages to reread> | Page problems: <pages>
```

A page that cannot produce an application question records the source's
wording, not an understanding of it. Say so.
