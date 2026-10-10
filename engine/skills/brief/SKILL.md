---
name: brief
description: >-
  A short cited summary of one person, project or topic from the pages: what it is, what is known, what is open. Use for /brief, "brief me on X", "what do I have on X". Not for a question (ask).
argument-hint: "<person | project | topic>"
---

# Brief

Brief the owner on $ARGUMENTS in under ten lines, every line cited.

A brief is `ask` with the question fixed: what is this, what do I know about
it, what is still open. It is what one reads before a meeting or before
picking a project up again.

## Core rule

As in `ask`: every line names the page it came from, and nothing from outside
the pages gets in without being labelled outside knowledge. A subject the
pages do not cover gets one sentence saying so, not a brief.

## Workflow

1. **Recall:** `brain recall "<the subject>"`; for a project in
   `prefrontal/`, add `--project <name>` and read its page too. An entity's
   own page comes first. Read the summaries, open what bears on the subject,
   the lines under `read first` before the rest of a page.
2. **Write** the brief in the shape below. Most supported first; a claim's
   confidence as `brain recall` gives it; `disputed`, `contradicted` and
   `stale` said where they apply. A contradicted row names the pages that
   say the opposite: read them, and give both sides. Dates as the pages give them.
3. **Check** it when it holds numbers or quotations: pass it to
   `brain ground -` on stdin, and for each line it lists cite the page, label
   the sentence outside knowledge, or take it out.
4. **Log the recall,** always: `brain log recall "brief <the subject>"
   --pages <page> <page>` (the pages the brief rests on; none: leave
   `--pages` out).

## Output

```
<Subject>: <what or who it is, in one sentence> [[page]]
Known:
- <claim> [[page]] (<confidence>)
- ... three to five lines
Open: <disputed or contradicted claims, stale pages, questions the pages raise; or none>
Decisions and projects: <[[decision]] (status), [[project]]; or none>
Read: <pages>
Not covered: <what one would expect here and the pages do not hold>
```
