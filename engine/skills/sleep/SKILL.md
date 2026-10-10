---
name: sleep
description: >-
  Consolidate: replay new episodes into concept and entity pages, write insights, propose fading. Use for /sleep, "consolidate", "link things up". Not for encoding input (ingest) or repairs (maintain).
argument-hint: "[episodes]"
---

# Consolidate (sleep)

Run all four stages on the consolidation queue, or on $ARGUMENTS.

In the brain, slow-wave sleep replays recent episodes into the cortex, REM
sleep integrates and abstracts, and synapses that were not reinforced are
scaled down. Only what recurs becomes general knowledge; one-off detail stays
with its episode. `/sleep` runs the same four stages in order.

## Core rule

A concept page needs two or more distinct sources, or one episode with
`salience: 4` or more (`high` is 5); `brain introspect --queue` shows sources/episodes for each
candidate, and episodes sharing a `url` or `input` are one source. A reviewed decision counts as an episode; an
`origin: generated` episode from `/explore` never counts. Interleave: replay episodes oldest first so later evidence
updates earlier pages, never the reverse.

## Stages

1. **Replay.** Run `brain introspect --queue`. Its prediction errors (new
   episodes that say they contradict a page) come first: each one is a
   Disagreement to record on that page before anything else is added to it.
   For each episode or reviewed decision awaiting consolidation, oldest
   first, and for each of its candidates:
   - a page exists: add what this episode contributes, cite it, update
     `updated:`, link both ways. A contradiction is recorded with both
     positions (CLAUDE.md > Disagreement), the page is tagged `disputed`, and
     the episode links it with `(contradicts:: [[page]])` when it states the
     disagreement. Check insights that link the page: a `## Current position`
     the episode undercuts gets the same treatment.
   - no page, named by two or more sources (or salient): create it from
     `${CLAUDE_PLUGIN_ROOT}/templates/`; concepts start `established` with two sources, `emerging`
     with one salient episode. Entities need only one episode.
   - otherwise leave it on the episode. Not consolidating is correct here.
     A candidate raised only by generated episodes stays there however many
     explorations name it; once a real episode names it too, link the
     exploration from the new page as where the question was first asked.
   - an `emerging` concept that now has two sources becomes `established`.
   - the episode reports the event a decision's `revisit_if` names
     (`brain introspect --decisions` lists them): tag that decision
     `to-revisit` and link the episode from it under `## Context`. Nothing
     else on the decision changes; `/decide review` takes it from there.
   Then set the episode's (or decision's) `consolidated:` to today.
2. **Integrate.** Where two episodes disagree, or three describe the same
   pattern, and no insight covers it, write one in `cortex/insights/`.
   `brain introspect --links` proposes missing links (pages sharing
   neighbours, pages the owner keeps recalling together): add one only where
   the relation is real; a link the owner would not agree with on reading
   both pages is noise. `brain introspect --clusters` lists schema
   candidates, dense clusters of four or more concepts no insight frames:
   propose one insight per cluster, tagged `schema`, that says what the
   concepts have in common and links each; write it on the owner's yes.
3. **Scale down.** Run `brain introspect --dormant` (salience 1-3 already
   stretches how long a page may sit unused). Propose, never perform,
   moving those pages to `dormant/`. On approval: log first, move the file,
   run `brain index` and `brain check`.
4. **Record.** `brain index` (it lists the new pages), then
   `brain log sleep "<n> episodes" --result "<counts>"`. Metric snapshots
   are `/health snapshot`'s job, monthly; a weekly sleep writing them too
   turns the trend into noise.

## Output

```
Replayed: <n> episodes (<range>)
Concepts: <n> new (<n> established, <n> emerging), <n> updated, <n> promoted
Entities: <n> new, <n> updated
Held on episodes: <n> candidates (one source only)
Insights: <n> | links added: <n> | contradictions: <list or none>
Decisions to revisit: <list or none>
Propose: <n> schema pages, <n> links, fading <n> pages (awaiting your yes)
```

## Calibration

More than ten episodes in the queue: hand replay to the `consolidator` agent
ten at a time, report after each batch, and stop for a go-ahead. Stage three's
proposals can come from the `curator` agent.

A sleep that creates a concept for every candidate has skipped the
two-source bar; a sleep that creates none after twenty episodes is probably
missing that candidates share an idea under different names: the queue lists
likely pairs under "possibly one idea twice". Read both; if they are one idea,
count both sources under one name, and if a candidate is part of a page, add
it to that page.
