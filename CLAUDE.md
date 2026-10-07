# AiBrain

A knowledge base modelled on how human memory works, kept for its owner. The
owner puts material into `senses/` and asks questions; `cortex/` and
`hippocampus/` are yours to write and keep correct. The procedures are the
`aibrain` plugin's skills (`/ingest`, `/sleep`, `/ask`, ...; `/aibrain:ask` on
a name clash) and the `brain` command. This file holds only the rules every
procedure shares, and changes only when a rule does. Who the owner is and
their goals are in `OWNER.md`, which the wake-up briefing prints.

## Anatomy

```
inbox/           quick notes from anywhere; /ingest moves them into senses/
senses/          input as it arrived; never edited after it lands (assets/: images)
hippocampus/     index.md (every page; read first), log.md (every operation and
                 recall), metrics.md, fingerprints.md (a hash of every input),
                 intentions.md (remind me when ...)
cortex/          long-term memory
  episodes/      one page per input: what that one item said
  concepts/      one idea per page, built only from repeated evidence
  entities/      people, organisations, products, tools
  insights/      what no single episode said: agreements, conflicts, patterns
  decisions/     choices: options, what was expected, what happened
prefrontal/      projects, one goal each; <name>/CLAUDE.md is the page [[name]]
dormant/         faded pages: out of the index and graph, still searchable
motor/           reports, drafts, exports for use outside the brain
engine/          the aibrain plugin
```

## How memory forms

- **Encode** (`/ingest`): one episode per input, linked to existing pages, new
  ideas under `## Candidates`; nothing else changes. An episode that
  contradicts a page says so with `(contradicts:: [[page]])`: prediction
  error, queued for sleep.
- **Consolidate** (`/sleep`): episodes replayed oldest first; a candidate
  becomes a concept once two or more distinct sources name it (episodes
  sharing a `url` or `input` are one source), or one salient episode
  (`salience: 4` or more; `high` is 5) does. One-off details stay on their episode.
- **Recall**: `brain recall` finds pages by their words, then spreads along
  links, stronger where pages were recalled together before. Every recall
  leaves a log line, which keeps the page in use; pages never recalled, and
  linked only from their own episodes, fade to `dormant/`, later the more
  salient they are. Recall never overwrites: a stale page it used is put to
  the owner, and only their answer is recorded.
- **Rehearse**: only `/rehearse` moves a page's rehearsal date. A pass pushes
  it out, a miss starts it over; the model reading or editing a page moves nothing.
- **Purpose**: pages linked from live goals (`OWNER.md` > Goals) and projects not
  `done` are rehearsed first and never fade.
- **Beyond the evidence**: `/explore` writes `origin: generated` episodes,
  never counted as evidence; `/decide` records what the owner expects, and a
  reviewed decision is replayed by sleep like an episode.

## Page contracts

Every page starts from its template in `engine/templates/` (`brain new`) and
carries `title`, `summary` (one sentence, at most 200 characters, on what the
page holds), `type` (episode | concept | entity | insight | decision),
`created` and `updated`; it may add `aliases` and at most three `tags`. Concepts add `status: emerging`
(one salient episode) or `established` (two or more distinct sources).
File names are lowercase-hyphenated; capitals live in `title`. Every other field is in `engine/templates/README.md`.
The hooks reject a page that breaks this; `brain check` rechecks every page.

An episode says what one source said (this source says X, not X is true). An
entity says what it is and why it is here. A concept explains one idea for
someone who never saw the episodes. An insight says what no single episode
did. A decision's fields, its frozen `## Expected` and its line tags are in
`.claude/rules/decisions.md`, which loads when a decision page is read.
System types (`index`, `log`, `metrics`, `fingerprints`, `intentions`) belong
to their one file in `hippocampus/`, never to a memory page.

## Rules

- Never edit or delete anything in `senses/`; new files may land there. Only
  `/forget` removes an input, and only on the owner's yes.
- Log before you delete or move a page.
- Link the first mention of every page with `[[wikilinks]]`; a page that does
  not exist yet goes under Gaps in the index.
- Type a link only when the source states the relation, `(supports:: [[Page]])`:
  `supports`, `contradicts`, `extends`, `part-of`, `applies`.
- Never invent a fact. "Not covered by any page here" is a valid answer.
- Answers come from pages, cited inline; outside knowledge is labelled.
- Plain sentences, no filler. Write for the owner in six months.
- Do the job asked; list what else you noticed. Any command accepts `dry-run`:
  list what would change, and write nothing.
- Count and find with the instruments, never by hand: `brain check`,
  `brain introspect` (`--help` lists its views), `brain search`,
  `brain recall`, `brain since`, `brain export`.

## Disagreement

When a new episode contradicts a page, record both positions with sources and
dates; never overwrite. Tag the page `disputed` until `/maintain settle`.

## Tags

`unverified` `to-revisit` `disputed` `schema`

## Log

One line per operation in `hippocampus/log.md`, newest last:
`DATE <operation> <what> -> <result>`. Operations: `ingest`, `recall`,
`sleep`, `explore`, `decide`, `review`, `write`, `focus`, `maintain`,
`health`, `guard`, `rehearse`, `rollback`, `owner`, `engine`, `remind`, `forget`. Every skill that
answers or writes from pages (ask, rehearse, explore, decide, write, focus)
also writes a `recall` line naming them; a missed rehearsal is
`DATE rehearse missed -> [[page]]`. The log is append-only. Keep `index.md`
current in the same run. Example lines are in `engine/templates/README.md`.

## Compact Instructions

When this conversation is compacted, keep: the active project and its open
plan item; files changed and not committed; the last failing command and its
error; decisions the owner made this session; log lines not yet written.
