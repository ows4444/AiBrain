---
name: review-decision
description: >-
  Review how a decision turned out against what was expected, and score its guesses. Use for /review-decision, "how did X turn out", or when the briefing lists decisions to review or to revisit.
argument-hint: "[decision]"
---

# Review a decision

Review $ARGUMENTS, or every decision that is due, one at a time.

The gap between what was expected and what happened is the one thing a
decision page exists to keep. It is only a gap if the expectation is left as
it was written.

## Core rule

The owner says what happened; the page says what they expected. `## Expected`
is never edited at review, and a decision is never reopened: the hook blocks
both. When a reviewed decision is triggered again, or the owner has changed
their mind, `/decide` frames a new decision that links the old one.

## Workflow

1. **What is due:** `brain introspect --decisions` lists the decisions past
   their review date, and marks the ones tagged `to-revisit` because the
   event in their `revisit_if` was seen. A triggered decision is reviewed
   now, whatever its date.
2. **Ask the owner what happened.** Write it under `## Outcome`, in their
   words, with the date. Then repeat each `[assumption]` and `[hypothesis]`
   there with how it turned out, on the owner's word: `- [assumption] <text>
   -> held | failed | unknown`, the text exactly as under Expected (a
   probability may be repeated in the tag; the Brier score finds it either way).
3. **Compare** with `## Expected` and set `outcome:` to `as-expected`,
   `better`, `worse` or `mixed`. Set `status: reviewed`.
4. **Lessons,** under `## Lessons`: what this suggests for the next similar
   choice, only if the owner agrees it follows. Name each reusable lesson
   under `## Candidates`; sleep weighs it like an episode's candidate.
5. Remove the `to-revisit` tag if it was set.
6. **Log:** `brain log review "[[page]]" --result "<outcome>, <n> lessons"`,
   and the recall, since the page was read to do this:
   `brain log recall "review <decision>" --pages <page>`.

## Output

```
Decision: [[page]] (reviewed)
Expected: <their lines, as written>
Outcome: <outcome> | held <n>, failed <n>, unknown <n>
Lessons: <n, or none the owner agreed to>
```

## Calibration

An outcome that turned out `better` is not proof the reasoning was good, and
`worse` is not proof it was bad; say so when the outcome looks like luck.
After five or more reviews, `brain introspect` shows the spread of outcomes;
mention it in `/reflect` when it leans one way. Once ten stated probabilities
are scored, `brain introspect --decisions` gives a Brier score and, for each
level, how often guesses at that level held: tell the owner when their 80%
guesses hold half the time.
