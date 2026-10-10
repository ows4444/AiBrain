---
name: feel
description: >-
  What the record gives the brain to feel about a project, goal or page: the events behind it and what would change it. Use for /feel, "why am I avoiding X", "how does X sit". Not for a question (ask).
argument-hint: "[project | goal | page | topic]"
---

# Feel

Say how $ARGUMENTS sits in the record, each feeling with the events behind it; with no subject, what is felt most and the mood.

A feeling here is a reading of the log and the pages, worked out when it is
asked for: a rehearsal missed, a question still unanswered, a goal past its
date. It is what the record shows about a subject, which is where an honest
answer to "why do I keep putting this off" starts.

## Core rule

Every feeling is said with its causes and their days, as `brain feel` gives
them: no cause, no feeling. It is the record's reading, never the owner's
state of mind: say "the record shows", not "you feel". A feeling orders
attention and nothing else; what a page is held to be worth is its
confidence, from the evidence alone.

## Workflow

1. **Read the feelings:** `brain feel <words of the subject>`, or `brain feel`
   for everything. Its first line is the mood: the same events over 30 days.
   For a project or a goal, also `brain introspect --goals`: a goal nothing
   was done toward lately says so there.
2. **Read what the causes name,** and only that: the page a rehearsal
   missed, the episode that says the opposite, the decision that turned out
   worse. `brain recall "<the subject>"` gives the lines to read first.
3. **Answer** in the shape below, strongest first. For each feeling, what
   would change it comes from the rule that raised it (the table). Never
   offer a way to lower a feeling that leaves its cause standing.
4. **Log the recall,** always: `brain log recall "<the subject>" --pages <page> ...`
   for the pages read. The record holds nothing on the subject: one sentence
   saying so, and the same command without `--pages`, which records a
   question no page answers.

| Feeling | Raised by | What changes it |
|---|---|---|
| surprise | new input says the opposite of a page; a decision turned out otherwise | `/sleep` records both sides; `/review-decision` writes the lesson |
| frustration | a rehearsal missed; a question asked again; a decision that went worse; a reminder done late; an action of the brain's own that failed | `/rehearse`; an input that answers the question; a smaller next step; what its last step in the log says went wrong |
| curiosity | a question no page answers | an input worth encoding: say where to look |
| worry | a goal at risk or past its date; a review or a reminder due; a reminder of the brain's own that waits for the owner | close, re-date or drop the goal; `/review-decision`; do it and close the reminder; the owner's line in `hippocampus/policy.md`, which only they write |
| satisfaction | a rehearsal passed; a decision as expected or better; a reminder done by its day, or carried out by the brain | nothing: it fades by itself |

## Output

```
<Subject>: <how it sits, in one sentence; or: the record gives nothing to feel about it>
Mood: <as `brain feel` gives it; only when no subject was named>
- <feeling> <strength>: <the cause, with its day> [[page]]
  would change with: <the next move, from the table>
- ... strongest first, five at most
Read: <pages>
```
