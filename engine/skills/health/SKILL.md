---
name: health
description: >-
  Metacognition: report the brain's health from the instruments (orphan rate, degree, components, stale rate, recall, queues), check the setup works, and record dated snapshots to compare trends. Use for /health, "is it working", "metrics", "graph shape", monthly checks. Read-only except the metrics snapshot. Do NOT use for repairs (maintain).
argument-hint: "[setup | snapshot | graph]"
---

# Introspect

Report health for $ARGUMENTS (`setup` to check the setup, `snapshot` to record metrics, `graph` for hubs, bridges, clusters and tags).

A single reading says little; direction over months is the information.

## Core rule

Numbers come from the scripts, never from counting by hand. Page count and
word count are never health signals; both rise whether things improve or not.

## Workflow

1. `brain introspect --json`. Optionally `brain graph`
   to `motor/graph/` for Gephi or NetworkX.
2. **Read the four metrics:** orphan rate (healthy under 5%), average degree,
   components (main share), stale-concept rate. Add the queues: awaiting
   consolidation, due for rehearsal, most recalled.
   Each metric comes with a verdict from the guide's healthy ranges: orphans
   under 5% healthy, over 15% means encoding is not linking; degree 3-8 is the
   working range, under 2 barely connected, over 10 suspect; the main
   component should hold 80% or more. Under 10 pages there is no verdict.
3. **Graph views** when asked: `brain introspect --graph` (or `--hubs`,
   `--bridges`, `--clusters`, `--tags`); the `graph-analyst` agent can run this
   in its own context. Hubs: say which distinct ideas people link to and
   propose a split. Bridges and cut points: say what stops informing what if
   that page is wrong. Clusters: name each from its core pages, and compare
   with the interests in the Owner section.
4. **Setup check** (for "is it working"): `brain test`
   passes; `brain check` runs; `brain eval` is at or above its baseline (the
   answer test set: retrieval on a fixed fixture brain); `claude plugin list`
   shows `aibrain` enabled with no errors, and `which brain` is this brain's
   `engine/bin/brain`; the folders in CLAUDE.md > Anatomy exist; the Owner
   section is filled in and has at least one goal under `### Goals`;
   `git status`; `git config core.hooksPath` is `engine/githooks` (the
   pre-commit gate; offer to set it if not).
   At the calibration checkpoint, `brain introspect --usage` lists every
   threshold beside the usage numbers; change one only with `brain eval`
   run before and after.
5. **Snapshot** (monthly or when asked): `brain introspect --snapshot`
   appends today's metrics to `hippocampus/metrics.md` as one line of data
   (once a day) and prints what changed since the previous snapshot. Report
   that; never compute the change by reading the file. This is the only
   writer of `metrics.md`. Log `DATE health snapshot -> <pages> pages,
   orphan <n>%, degree <n>`.

## Output

```
<date> | pages <n>
orphan rate    <n>%  (<+/-> since <date>)
avg degree     <n>   (<+/->)
components     <n>   (main <n>%)
stale concepts <n>%  (<+/->)
queues: consolidate <n> | rehearse <n> | dormant candidates <n>
Moved: <what changed and the likely cause>
Watch: <one number, or none>
```

## Calibration

A rising orphan rate with a rising page count means encoding has stopped
linking or sleep is not running; call it out explicitly. One thing to watch,
not five.
