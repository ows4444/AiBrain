---
name: decide
description: >-
  Frame a choice from the pages and record what the owner expects before the outcome is known. Use for /decide, "help me decide", "I decided X". Not for questions (ask) or outcomes (review-decision).
argument-hint: "<question> | made <decision>"
---

# Decide

Decide $ARGUMENTS: frame a new choice, or record one already made.

The orbitofrontal cortex weighs options against expected value; the striatum
learns from the gap between what was expected and what happened. Without that
gap there is nothing to learn from, so the expectation is written down before
the outcome is known and never revised afterwards.

## Core rule

The owner decides; the brain lays out what its pages say. `## Expected` is
written before the outcome and never edited once the decision is `decided`.
Hindsight that rewrites the prediction destroys the only signal this page
exists to keep. Every line of the reasoning says what it is, so evidence and
guesses never look alike (tags and what each must carry:
`${CLAUDE_PLUGIN_ROOT}/templates/README.md` > Claims on a decision page).

## Workflow

**Frame** (a question with a choice in it):
1. Create `cortex/decisions/<slug>.md` from
   `${CLAUDE_PLUGIN_ROOT}/templates/decision.md`, `status: open`, and run
   `brain index`, which lists it under Decisions.
2. Retrieve as `ask` does: `brain recall "<the question>"` (with `--project`
   when it belongs to one). Under `## Options`, list each option with the pages that bear
   on it, cited, one tagged line per claim: `[observation]` only for what a
   page records, `[interpretation]` for a reading of it. Anything not on a
   page is `[assumption]` and labelled outside knowledge.
3. Under `## Context`, link the project it belongs to (`[[<name>]]`, the
   folder name in `prefrontal/`) and name the goal in `OWNER.md` it serves, if any.
4. Ask the owner what they expect from each option and how sure they are.
   Before they put a number on it, show the reference class: `brain
   introspect --decisions` lists, for each tag, how reviewed decisions with
   that tag turned out and how well calibrated their probabilities were.
   Write their answer, in their words, under `## Expected`, one line per
   claim. Do not supply the expectation for them. Propose a tag for each line
   (`[hypothesis]` if they say what would show it, `[assumption]` if not) and
   read the tags back for a yes; the words stay theirs. When they give a
   probability, it goes inside the tag: `- [hypothesis 70%] <their words>`.
   Never suggest the number.
5. Log: `brain log decide "<short question>" --pages <page>`.

**Record** (`made <decision>`, or the owner says what they chose):
1. Fill `## Decision`: what, when, why, in the owner's words.
2. If `## Expected` is empty, ask for it now, before anything else. Every
   line under Options, Expected, Decision and Lessons must be tagged before
   the next step: the hook refuses a decided page with an untagged line, and
   Expected cannot be changed afterwards.
3. Ask what would make them look again before the review date, and write it
   as `revisit_if: "<event>"`, quoted. It names something that can be seen to
   happen: evidence an input could report ("a source reports X failing"), or
   something only the owner will notice ("I skip it three weeks running").
   "If things change" gets a follow-up question.
4. Set `status: decided` and `review:` to when the outcome will be visible;
   ask the owner if unsure. Default three months.
5. Log: `brain log decide "<decision>" --pages <page> --result "review <date>"`.

**Review** is its own skill, `/review-decision`, so that it can be run or
scheduled alone: what happened, how each guess turned out, the outcome, the
lessons. A decision is never reopened: the hook blocks taking `status` back.
When a `reviewed` decision is triggered, or the owner changes their mind,
frame a new decision that links the old one.

In both modes, also log `brain log recall "decide <short question>" --pages <page> ...`
for the pages read, the decision page included; the recall hook checks for it.

## Output

```
Decision: [[page]] (<status>)
Options: <n>, each with <n> supporting pages | expected: <recorded | missing>
Claims: <n> observations, <n> interpretations, <n> hypotheses, <n> assumptions
Review: <date> | revisit if: <event> | outcome: <outcome or pending>
Not covered: <what the brain could not inform>
```

## Calibration

A decision with more assumptions and hypotheses than observations rests
mostly on guesses: say so before it is made, without arguing against it.
Before the owner puts a number on a guess, the reference class is the
calibration they have: once ten stated probabilities are scored, `brain
introspect --decisions` says how often guesses at each level held.
