---
name: explore
description: >-
  Push a concept past what the brain holds: question assumptions, carry it to other fields, propose tests. Use for /explore, "what am I missing about X", "where else does X apply".
argument-hint: "[concept] [field]"
---

# Explore

Explore $ARGUMENTS: question what it assumes, move it into other fields, and record what comes out. No concept named: offer the three from `brain introspect --goals` that the owner's goals depend on most.

Imagination recombines what memory holds into things it never stored; the
default-mode network proposes and the executive network checks. Here the
proposals are written down, and sleep does the checking: nothing imagined
becomes a concept until evidence from outside arrives.

## Core rule

An exploration is a hypothesis, not a memory. Its episode is marked
`origin: generated` and tagged `unverified`, and its candidates never count
toward the concept bar. Every claim names its basis: a page here, outside
knowledge (labelled), or speculation (labelled).

## Workflow

1. **Read the concept** and everything one hop from it, starting from
   `hippocampus/index.md`. A topic with no page: say so, and offer `/ingest`
   instead. Exploring nothing produces fiction.
2. **Assumptions.** What the concept takes for granted that no page here
   tested. Two to five, each with the page that relies on it.
3. **Transfer.** Carry the idea into two or three other fields (or the one
   named in $ARGUMENTS). Prefer fields the brain already has pages on; for each,
   what would the idea predict or change there?
4. **Angles.** What a sceptic, a practitioner and a newcomer would each ask.
   Keep only angles a page here does not already answer.
5. **Write the episode** at `cortex/episodes/explore-<concept>-<date>.md`
   from `${CLAUDE_PLUGIN_ROOT}/templates/episode.md`, with `origin: generated`,
   `author: aibrain /explore`, `tags: [unverified]` and no `input:`.
   `## Claims` holds the assumptions and transfers, each labelled;
   `## Candidates` holds the ideas worth testing, each with what evidence
   would confirm it. Link the concept on first mention. Change no other page.
6. **Log** `DATE explore [[concept]] -> [[episode]], <n> candidates` and
   `DATE recall explore <concept> -> [[page]], ...` for the pages that
   contributed, and add the episode to the index under Episodes.

## Output

```
Explored: [[concept]] (<n> pages read)
Assumptions: <n> | fields: <list> | candidates: <n>
Episode: [[explore-...]] (generated, unverified)
Test next: <the one candidate most worth finding evidence for, and where to look>
```

## Calibration

Five sharp candidates beat twenty loose ones. A candidate already covered by
a page is not new; link the page instead. If every candidate came from
outside knowledge and none from the pages, say so: the concept may be too thin
to explore yet.
