# Roadmap: what to build, chosen item by item

Every gap found in the review of the brain's features, skills and agents, as separate items. Pick any set
whose dependencies are met; none requires all the others. Scores are usefulness out of 10 for one owner
(judgment, not measurement). Effort: S under half a day, M one to two days, L several days.

Rules every item keeps (from CLAUDE.md): standard library only in `engine/lib`; memory dates stay
`YYYY-MM-DD`; nothing derived is stored, the log is the record; senses/ is never edited; each new
skill gets a `recall` or operation line in the log; `brain test` and `brain check --guard` pass before it
counts as done. A new skill name must be lowercase-hyphenated and match its folder.

The order of work, with what was measured, is in `REFACTOR.md`; its checklist is `TASKS.md`.

## 0. Before building anything

| ID | Item | Effort | Done when |
|----|------|--------|-----------|
| P0 | Fill the brain: `/start`, `/owner`, 10 to 20 real inputs, one `/tend` | S | `brain introspect` gives a verdict other than "too small to judge" |
| P1 | A question set of your own (`brain eval --draft N`, kept in `motor/`) | S | Baseline hit@1 and hit@k recorded on real content |

Why first: items below are justified by gaps in recall and upkeep. With 0 pages nothing shows which gap
matters. P1 gives the measure that decides item F1.

## 1. Features (engine)

| ID | Score | Item | Effort | Depends on | Risk |
|----|-------|------|--------|------------|------|
| F1 | 9 | Semantic search | L | P1 | Breaks "standard library only". Build as optional: `brain search --semantic`, off when no embedding source is configured. Keep BM25 the default and measure with `brain eval` before and after |
| F2 | 9 | Automatic runs (scheduler) | M | none | Unattended writes to memory. Run read-only checks by default; write only through `/tend` with the critic verdict logged |
| F3 | 8 | Quality on real data | S | P0, P1 | None. Output is a short report of hit@1/hit@k and sleep outcomes |
| F4 | 7 | Low-friction capture | M | none | Needs one concrete door, named before anything is built, not a general design |
| F5 | 6 | Engine-side extraction (PDF text, image text) | M | none | Needs a dependency or a system tool; keep it optional and fall back to the model |
| F6 | 6 | Audio and video transcription | M | F4 | External tool or API; the transcript must land in `senses/` as text with its source named |
| F7 | 5 | Imports from note apps and mail | M each | none | One importer per source (Obsidian vault first: it is already Markdown). Never overwrite; one input per note |
| F8 | 5 | Visual interface | L | none | Cheapest form is a static HTML graph from `brain graph`; a server is not worth it |
| F9 | 4 | Intra-day ordering | S | none | Optional `HH:MM` after the date in log lines. Check every parser that assumes `^\d{4}-\d{2}-\d{2} (\S+)` (`LOG_LINE` in vault_model.py) |
| F10 | 4 | Backup and sync | S | none | Document a git remote; the shipped permissions deny `git push` on purpose |
| F12 | 3 | MCP server over `brain` | M | F1 | Read-only tools only (`search`, `recall`, `since`); no write path |
| F13 | 4 | Windows support | M | none | Paths, `python3` name, the `brain` symlink `install.sh` makes |

### F2 in detail (the one most likely to be chosen)
1. `brain tend --check` (new, read-only): prints queues, due rehearsals, due reminders, decisions to review. No writes.
2. A scheduled run of that command (Claude Code `/schedule` routine, or cron) that sends the result to you.
3. Only then consider a scheduled `/tend` that writes. It must run the critic and stop on a bad verdict.
Acceptance: leaving the brain alone for a week produces one report, and no page changes.

### F1 in detail
1. Decide the embedding source (local model or API). This is the one real decision; everything else follows.
2. Store vectors in `.cache/` (rebuildable, never committed), keyed by page path and text hash like `vault_cache.py`.
3. `search` blends BM25 and similarity; `recall` seeds activation from the blend.
4. Gate: `brain eval` hit@k does not fall on the fixture and rises on your question set from P1.

## 2. Skills

| ID | Score | Skill | Effort | Notes |
|----|-------|-------|--------|-------|
| S1 | 9 | Scheduled `/tend` | M | Same item as F2; the skill is the entry point, the routine is the schedule |
| S2 | 8 | `/import` | M | Front for F7. Picks the importer, writes to `senses/`, hands off to `/ingest` |
| S3 | 7 | Semantic mode for `/ask` | S | Only a flag passed to `brain recall` once F1 exists |
| S4 | 6 | `/capture` | S | One line to `inbox/<date>-<slug>.md` from inside a session. `/ingest` already sweeps `inbox/` |
| S5 | 6 | `/transcribe` | S | Front for F6 |
| S6 | 5 | `/brief` | S | Short cited summary of one person, project or topic. Thin wrapper over `/ask` with a fixed format |
| S7 | 5 | `/review-decision` | S | Splits the review step out of `/decide` (110 lines) so it can be run or scheduled alone |
| S8 | 4 | `/restore` | S | Confirmed gap: `/maintain` moves pages to `dormant/` but nothing moves them back. Log it, move the file, re-add to the index |
| S9 | 4 | `/export` | S | Wrapper for `brain export`, with `/guard` run first |
| S10 | 3 | `/share` | M | Read-only view for another person; needs a decision on what "view" means. Decided 2026-10-10: nothing new, `/export` and `brain mcp` are the ways out; not built |

Skill template: copy `engine/skills/commit/SKILL.md` (19 lines) for a thin skill, `ask` (93 lines) for one
that logs a recall. `engine/tests/test_skills.py` checks the contract; extend it, do not bypass it.

## 3. Agents

| ID | Score | Agent | Effort | Model | Notes |
|----|-------|-------|--------|-------|-------|
| A1 | 8 | Scheduler or watcher | M | haiku | Runs F2 step 1 and reports. Read-only tools |
| A2 | 7 | Contradiction resolver | S | inherit | Prepares each side of a `disputed` page (sources, dates, strength) for `/maintain settle`. Does not settle |
| A3 | 6 | Ingestion scout | M | sonnet | Sorts `inbox/` before `/ingest`: duplicates by fingerprint, secrets by `brain check --guard`, items that need a person |
| A4 | 5 | Quiz writer | S | sonnet | Drafts questions; `/rehearse` already builds its own, so only worth it if quizzes feel thin |
| A5 | 4 | Privacy gatekeeper | S | inherit | Clean-context pass of `/guard` before any export. The critic already covers part of this |
| A6 | 3 | Writer or editor for `/write` | S | sonnet | Drafting stays in the main session today. Decided 2026-10-10: not built |

Agent template: `engine/agents/curator.md` (23 lines, read-only, cheap model). Give new agents the
fewest tools that do the job; only writers get `Write` and `Edit`.

## 4. Suggested bundles

| Bundle | Items | Why together |
|--------|-------|--------------|
| Upkeep | F2, S1, A1, S7 | The brain tends itself; you only read a report |
| Getting material in | F4, S4, F7, S2, A3 | Capture and import with one triage step |
| Better recall | P1, F3, F1, S3, F12 | Measure first, then add meaning-based search |
| Hygiene | S8, S9, A2, A5 | Small, independent, low risk |
| Reach | F6, S5, F5 | Voice and documents without the model doing all the extraction |

Smallest useful first step: P0 and P1, then Upkeep. Bundles can run in any order after that.

## 5. How each item is checked

- Tests: `brain test` plus a new test beside the nearest existing one (`test_skills.py` for skills,
  `test_hooks.py` and `test_walls.py` for hooks, `test_retrieval.py` for search).
- Retrieval items: `brain eval --baseline engine/eval/baseline.json` must not regress on the fixture.
- Brain items: `brain check --guard` passes and `brain errors` shows nothing new from the item.
- Each finished item gets a log line (`engine` operation) and a line in the README command table.
