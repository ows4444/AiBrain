---
name: reflect
description: >-
  Periodic review of what the brain learned: what was added, what is unresolved, what next. Use for /reflect, "weekly review", "weekly digest", "what changed". Not for metrics (health).
argument-hint: "[period] [save]"
---

# Reflect

Review $ARGUMENTS, defaulting to the last seven days. With `save` (or when run on a schedule), also write the review to `motor/digest-<YYYY-MM-DD>.md`.

Capture systems fail where nothing comes back out. A review turns a period of
encoding into something the owner reads and acts on.

## Core rule

Report on what the owner now knows, not on agent activity. Under a page.
Three recommendations, not ten.

## Workflow

The `reviewer` agent can run this whole review in its own context.

1. **Diff the period** (default seven days): `brain since <start date>` lists
   the pages made and changed, operations, questions asked and rehearsals.
2. **Where attention went:** concepts that gained the most links and recalls.
3. **Unresolved:** `brain introspect --open` (`disputed` and `to-revisit`
   pages, `contradicts` links), open questions on concepts and insights,
   decisions still `open`, and decisions past their review date
   (`brain introspect --decisions`). Concepts untouched for 90 days or more
   (`brain introspect --stale`, oldest first): name the oldest few and ask
   whether each still holds; only the owner's answer changes a page.
   Pages marked `salience: 4` or more never fade, and
   `brain introspect --salience` lists the ones no live goal reaches and
   nothing has used for 180 days. Ask of each whether it still matters. Yes: add
   `- Rechecked (owner, DATE): still matters.` under its last section and
   set `updated:`. No: lower or remove the mark, as they say. The same view
   counts the episodes marked 1 to 3 for no reason the pages show; when
   that is most of them, say so, because a mark on everything tells nothing.
4. **Decisions:** reviewed in the period and how they compared with what was
   expected. Once five or more are reviewed, say whether the outcomes lean
   `better` or `worse` than expected; that is a calibration signal. So is
   the share of assumptions and hypotheses that held. Then list every
   `revisit if` line from `brain introspect --decisions`, one per decision in
   force, and ask whether any has happened: many of these events only the
   owner can see.
5. **Goals:** `brain introspect --goals`. A goal past its date (close,
   re-date or drop it), one with no pages behind it, or one marked AT RISK
   (due within 30 days, nothing behind it edited or recalled in 28) outranks
   everything else in Next. Reminders due or waiting: `brain introspect --remind`.
6. **Thin spots:** pages recalled or linked often but thin; gaps that keep
   being linked; candidates waiting on a second episode; `/explore`
   candidates still waiting on any evidence. Questions asked and not
   answered: `brain introspect --gaps` lists them, most asked first, each
   with the held idea or the index gap it names. The one asked most is
   what to read next; say so in Next.
7. **Next:** three actions, each tied to a page. `brain feel` lists what the
   record gives most to feel about, each with its cause: of two actions
   that are otherwise equal, the one more is felt about comes first, and its
   cause is said. A feeling orders the three; it adds none and drops none.
8. **Schedule** (only if asked): propose cadences from log volume, by default
   `/ingest` when senses/ fills, `/sleep` weekly (proposals only: fading and
   schema pages still wait for a yes), `/reflect save` weekly as the digest,
   `/maintain` weekly, `/health` monthly, with the exact prompt for each.
   Create nothing without approval.
9. **Save** (with `save`): write the output below to
   `motor/digest-<YYYY-MM-DD>.md` and log
   `brain log write "digest <period>" --result motor/digest-<YYYY-MM-DD>.md`.

## Output

```
## <period>
Added: <n> episodes, <n> concepts | recalls: <n>
### Where your attention went
### Unresolved
### Decisions
### Goals
### Thin spots
### Next
1. 2. 3.
```

If the period produced nothing worth reporting, say so in one line.
