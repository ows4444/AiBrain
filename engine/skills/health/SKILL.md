---
name: health
description: >-
  Report the brain's health from the instruments, check the setup, record metric snapshots. Use for /health, "is it working", "metrics", "graph shape". Not for repairs (maintain).
argument-hint: "[setup | snapshot | graph]"
---

# Introspect

Report health for $ARGUMENTS (`setup` to check the setup, `snapshot` to record metrics, `graph` for hubs, bridges, clusters and tags).

A single reading says little; direction over months is the information.

## Core rule

Numbers come from the scripts, never from counting by hand. Page count and
word count are never health signals; both rise whether things improve or not.

## Workflow

1. `brain introspect --json`. To look at the graph, `brain graph --format html` writes one page to
   `motor/graph/graph.html` that opens in a browser with no network. Optionally `brain graph`
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
   with the interests in `OWNER.md`.
4. **Setup check** (for "is it working"): `brain test`
   passes; `brain check` runs; `brain eval` is at or above its baseline (the
   answer test set: retrieval on a fixed fixture brain); `claude plugin list`
   shows `aibrain` enabled with no errors, and `which brain` is this brain's
   `engine/bin/brain`; the folders in CLAUDE.md > Anatomy exist; `OWNER.md`
   is filled in and has at least one goal under `## Goals`;
   `git status`; `git config core.hooksPath` is `engine/githooks` (the
   pre-commit gate; offer to set it if not).
   **Own question set** (when asked, or once the brain holds about 50
   pages): `brain eval --root . --questions motor/eval-questions.json
   --draft 10` prints ten pages no question expects yet, each with its
   summary and the words to avoid. Read each page and write one question it
   answers without those words; add two or three questions no page covers
   (`"covered": false`). Show the owner the questions; on their yes, write
   them into `motor/eval-questions.json` and run the same command without
   `--draft`, then with `--save-baseline`. Its baseline stays beside it, and
   it is the set to rerun before and after a threshold changes.
5. **Calibration checkpoint** (when the briefing asks for it, or on
   request). Every threshold is a guess until this brain's own use tests it.
   `brain introspect --usage` lists each with its value here, its range and
   what it does, beside what has been used. Change one only on evidence:
   - Before: `brain eval --from-log` replays every question the log holds,
     each as the brain was on its day; add `--save-baseline` to keep the
     numbers to beat. Read its two limits aloud: a fall is a regression, a
     high number is not quality. So run the owner's own question set too,
     when there is one.
   - For each value worth trying, run the same again with
     `--set name=value` (it writes nothing) and put its numbers beside the
     first run's. One threshold at a time.
   - Show the owner the runs. On their yes, keep the value as a line under
     `## Overrides` in `hippocampus/tuning.md`, `- name = value (why,
     date)`; a brain without that page takes it from
     `${CLAUDE_PLUGIN_ROOT}/templates/brain/hippocampus/tuning.md`.
     Removing the line restores the default. Then save the baseline again,
     so the next review starts from the values kept.
   - A trait is reviewed the same way, and never changed any other: the
     traits `brain introspect --usage` lists each move a few thresholds
     together. Say what the trait is now, what it would be, and the
     evidence (the runs with `--set <trait>=<value>` beside the ones
     without; for `resilience` and `sensitivity`, what `brain feel` lists
     with and without). On the owner's yes it is one line under `## Traits`
     in `CHARACTER.md`, `- name = value (why, date)`. Nothing changes a
     trait by itself.
   - Record that the review was done, whatever came of it:
     `brain log health calibration --result "<what was kept, or nothing;
     recall hit@5 before and after>"`. The briefing stops asking once the
     log holds that line.
6. **Context budget:** `brain introspect --context` prints what loads every
   session and what loads on use, in bytes, lines and estimated tokens, and
   the change since the last snapshot. Report the every-session total; on
   `GROWN` or a `WARNING`, name what was added and ask whether it has to
   load every session. The tokens are an estimate; say so.
7. **Snapshot** (monthly or when asked): `brain introspect --snapshot`
   appends today's metrics to `hippocampus/metrics.md` as one line of data
   (once a day) and prints what changed since the previous snapshot. Report
   that; never compute the change by reading the file. This is the only
   writer of `metrics.md`. Log `brain log health snapshot --result "<pages> pages,
   orphan <n>%, degree <n>"`.

## Output

```
<date> | pages <n>
orphan rate    <n>%  (<+/-> since <date>)
avg degree     <n>   (<+/->)
components     <n>   (main <n>%)
stale concepts <n>%  (<+/->)
queues: consolidate <n> | rehearse <n> | dormant candidates <n>
context: <n> bytes every session (<+/-> since <date>), ~<n> tokens estimated
Moved: <what changed and the likely cause>
Watch: <one number, or none>
```

## Calibration

A rising orphan rate with a rising page count means encoding has stopped
linking or sleep is not running; call it out explicitly. One thing to watch,
not five.
