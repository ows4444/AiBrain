# Page templates

Every memory page starts from one of these. `brain/` is the scaffold for a new,
empty brain; `project/` is copied by `/aibrain:focus` into `prefrontal/<name>/`.
A project's `CLAUDE.md` is a system page (`type: project`, with `status:
active | paused | done`, `goal:` and `due:`): its links count and are checked,
but it is not a memory page, so the field table below does not apply to it.
`graph.html` is no page of the brain: `brain graph --format html` fills it
with the pages and their links and writes it to `motor/graph/`.

## Frontmatter

```yaml
---
title: Canonical name
summary: One sentence on what the page holds, at most 200 characters
type: episode | concept | entity | insight | decision
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: [other names]
tags: [zero to three, from the Tags section of the brain's CLAUDE.md]
---
```

The rules for `status` (concepts and decisions) live in the brain's
`CLAUDE.md` > Page contracts. Every field below is defined once, in
`engine/lib/vault_model.py` (`FIELDS`, which `vaultlib` re-exports): which pages may carry it, its allowed
values, and whether `brain export` drops it as private. A test keeps this
table in step with that registry. Lists may be inline, `[a, b]`, or one
`  - item` per line, the way Obsidian's Properties editor writes them.

| Field | On | Values | Exported | Meaning |
|---|---|---|---|---|
| `title` | all, required | text | yes | Canonical name; capitals live here, not in the file name |
| `summary` | all, required once the page has text | one sentence, at most 200 characters | yes | What the page holds, so a reader of `brain recall` or `brain search` can tell whether to open it. Written by whoever wrote the page, from what it says; never derived from headings |
| `type` | all, required | episode, concept, entity, insight, decision | yes | Page type |
| `created`, `updated` | all, required | YYYY-MM-DD | yes | Dates |
| `aliases` | all | list | yes | Other names the page resolves by |
| `tags` | all | up to three, from the vocabulary | no | |
| `status` | concept, decision | concept: emerging, established; decision: open, decided, reviewed | no | See Page contracts |
| `input` | episode | path | no | Its path in `senses/`; this marks the input encoded |
| `url`, `author`, `published` | any | text | yes | Where the content came from; episodes sharing a `url` (or `input`) are one source for the concept bar |
| `consolidated` | episode, decision | YYYY-MM-DD | no | Set by sleep once replayed |
| `origin` | episode | generated | no | Written by `/explore`, not encoded from input; never evidence |
| `kind` | entity | person, org, product, tool | yes | What sort of thing it is |
| `review` | decision | YYYY-MM-DD | no | When to check the outcome; required once decided |
| `outcome` | decision | as-expected, better, worse, mixed | no | How it turned out against `## Expected`; required once reviewed |
| `revisit_if` | decision | text, quoted | no | The event that means look again before `review`; required once decided |
| `salience` | any | 1-5, or high (= 5) | no | How much it matters. 4-5 (the owner's call): one episode makes a concept, never fades. 1-3 (proposed at ingest: contradicts a page, touches a goal, high stakes): fades later, rehearsed sooner |
| `maintained_by` | any | human | no | Never merge, split or rewrite without asking |
| `publish` | any | true | no | Opted in to `brain export --published` |

Fields not in this table are allowed and left alone. The `validate_page` hook
checks every write against the registry; `brain check` rechecks every page.

## Claims on a decision page

Under `## Options`, `## Expected`, `## Decision` and `## Lessons`, every
top-level line is a bullet that starts with what it is. Indented lines and
`###` sub-headings belong to the line above. The hook and `brain check`
enforce this once the decision is `decided`; an `open` one is only listed.

```markdown
- [observation] Two of three teams dropped it within a month. [[habits-survey]]
- [interpretation] That looks like a scheduling problem. [[habits-survey]]
- [hypothesis 70%] A 15-minute cap keeps it going; true if I still do it in week six.
- [assumption] My calendar stays as free as it is now.
- [decision] Weekly review, Fridays, capped at 15 minutes.
```

A hypothesis or assumption may carry the owner's probability inside its tag,
`[hypothesis 70%]`, never anywhere else (a claim may start with a number of its
own). Reviewed ones are scored: `brain introspect --decisions` shows the Brier
score once ten are scored, and how often each level held.

| Tag | Means | Must carry |
|---|---|---|
| `observation` | A page records it, or the owner saw it | A link to a page that is not an `/explore` episode, or `(owner, YYYY-MM-DD)` |
| `interpretation` | A reading of observations | The page it reads, when there is one |
| `hypothesis` | A guess that can be tested | What would show it true |
| `assumption` | Taken as true, untested | Nothing |
| `decision` | The choice itself | Only under `## Decision` |

At review, each assumption and hypothesis is repeated under `## Outcome` with
how it turned out: `- [assumption] My calendar stays free. -> failed` (`held`,
`failed` or `unknown`). `brain introspect --decisions` adds these up.

## Log lines

One line per operation in `hippocampus/log.md`, newest last; the format and
the operations are in the brain's `CLAUDE.md` > Log. `brain log` writes them:
it checks the operation and every page name, sets the date, and refuses a
name it does not know. These three commands

```
brain log ingest senses/some-article.md --result "1 episode, 2 candidates, 4 links"
brain log recall "what is an llm wiki" --pages llm-wiki karpathy
brain log sleep "3 episodes" --result "1 concept established, 2 updated, 1 insight"
```

write these three lines:

```
2026-09-07 09:12 ingest senses/some-article.md -> 1 episode, 2 candidates, 4 links
2026-09-08 18:40 recall what is an llm wiki -> [[llm-wiki]], [[karpathy]]
2026-09-09 07:05 sleep 3 episodes -> 1 concept established, 2 updated, 1 insight
```

The time of day is the moment the line was written. Lines from before it was
written have a date only and are read as before; within one day they come
ahead of the lines that carry a time.
