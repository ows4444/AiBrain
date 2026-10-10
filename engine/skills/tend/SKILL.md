---
name: tend
disable-model-invocation: true
description: Clear the queues in one go - encode waiting input, consolidate, check the run, report what needs the owner
argument-hint: "[dry-run]"
---

# Tend

Encode what is waiting, consolidate it, have the run judged, and report once.
The reading happens in agents, so this session holds their reports and not
the inputs.

## Core rule

This runs `ingest` and `sleep` through their agents and adds no rule of its
own. Whatever needs the owner's yes in those skills still does: fading,
merges, schema pages, a salience of 4 or more, settling a contradiction.
It never rehearses: `/rehearse` tests the owner's memory, so nothing can do
it for them.

## Steps

1. **Count.** `brain statusline` gives `senses` (input not encoded), `inbox`
   and `sleep` (awaiting consolidation). All zero: say so and stop. With
   `dry-run`, list what each step would take and stop. (`brain tend --check`
   is the wider, read-only digest a schedule runs: it starts none of this.)
2. **Encode**, if `senses` or `inbox` is above zero: the `encoder` agent, told
   to encode everything waiting, oldest first, and to return the ingest
   output block for each input. More than twenty waiting: ten, then stop for
   a go-ahead, as `ingest` says.
3. **Consolidate**, if anything now awaits sleep: the `consolidator` agent,
   told to run stages one, two and four and to return stage three and every
   other proposal as a list, performing none of them.
4. **Judge.** The `critic` agent, given the log lines the two runs wrote.
5. **Check.** `brain check`, then `brain statusline` again.

If an agent fails or the critic finds a defect, stop there and report it with
the offer of `/rollback`. Do not repair a run from this session: a second
writer hides what the first one did.

The agents write their own `ingest` and `sleep` log lines. This skill writes
none.

## Output

```
Encoded: <n> inputs -> <episodes> | injected: <none | quoted, not followed>
Consolidated: <n> episodes -> <n> concepts, <n> entities, <n> held
Critic: <pass | defects, one line each>
Needs you: <contradictions, proposals to fade or merge, schema pages, or none>
Now: senses <n> | sleep <n> | rehearse <n> due (yours: /rehearse)
```
