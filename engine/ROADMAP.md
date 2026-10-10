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
| F14 | 6 | Reminders with a time and a repeat | S | F9 | A repeat is never closed by `(done)`: when it was last done is read from the log, or a second record of state appears beside it |
| F15 | 7 | Event reminders found by `brain fit` | S to M | none | It lists what to check, the model still judges: an event is prose, and words alone will list some that are not it |
| F16 | 5 | A reminder closes with its date and what happened | S | none | `(done)` is shared with goals (`GOAL_END`); a bare one must still read |
| F17 | 7 | A schedule that needs no session, with a notification | M | F2 step 1 | It installs a job on the machine, so it asks. A machine asleep runs it late: report the lateness, never promise the time |
| F18 | 4 | What waits, as a fifth MCP tool | S | F12 | Read-only, as the other four. This is how a program that acts learns what the brain is waiting on |
| F19 | 7 | Salience reaches the pages built on an episode | S | none | It moves the order of rehearsal and the time to fade for a brain in use. Capped at 3: from 4 up is the owner's call and is never passed on |
| F20 | 6 | `brain fit` gives the reasons for a salience | S | none | It marks where to look, as it does for an event: whether the input says the opposite of a page is still read |
| F21 | 5 | Salience is asked about again | S | F19 | A list for the owner, never a change: only their answer lowers a mark they set |
| F22 | 6 | A contradicted page names what contradicts it | S | none | One more key on a recall row; a caller that pins the row's keys is told |
| F23 | 5 | A source's track record | M | 100 episodes | Counts of one or two episodes a source read as a verdict on it. It counts claims, never what a source meant |
| F24 | 6 | Feelings from the record | M | none | It can read as more than it is: a model of affect that orders attention. Every feeling prints its causes, and none is stored |
| F25 | 6 | Mood, and where a feeling moves attention | M | F24 | A feeling that reorders what waits must hide nothing: the same lists, another order |
| F26 | 5 | A character page | S | none | Prose the model reads every session costs context; keep it short, and measure it with `brain introspect --context` |
| F27 | 6 | Traits that scale thresholds | M | F26 | A trait with nothing to move is prose under a number: each one maps to thresholds that exist, and an override in `tuning.md` still wins |
| F28 | 5 | Traits shape what is felt, and change on evidence | M | F25, F27 | Never by itself: the calibration checkpoint proposes, the owner decides, the log records |
| F29 | 7 | Actions with a name, and a policy page | M | none | The policy is code and a page, never a prompt: unknown is refused, and it is asked at the moment an action runs |
| F30 | 7 | Intentions that can be carried out | M | F29 | State read from the log has no lock of its own: one worker a brain, and a transition table a test holds |
| F31 | 7 | A worker that does what is permitted | M | F30, F17 | Unattended writes. A step that started and did not finish is of unknown outcome, never taken as not done |
| F32 | 6 | Approvals | M | F31 | A yes that outlives its action: it is bound to the exact proposal and lapses |
| F33 | 6 | A planner | L | F31, F32 | A model that says a step is done, or safe: neither counts. Checks decide, under a budget |
| F34 | 6 | What it feels about its own work, and what it does next | M | F25, F28, F33 | A feeling used as a reason to skip a rule: the order may change, what is allowed may not |
| F35 | 6 | Outside work is handed over, and comes back as input | M | F30 | Two engines holding one task's state: the brain holds the intention and the evidence, the runtime holds the run |
| F36 | 7 | Tests where the right thing is to wait, to ask or to refuse | M | F33 | A set that only rewards finishing teaches the wrong thing: acting without leave must count as failure |
| F37 | 5 | Relationships | M | people in the brain | A reading of a person hardens into a verdict: every reading carries its evidence, and none is stored |

### What the brain does not become (decided 2026-10-10)

F14 to F18 are what was taken from a design for a "synthetic brain" that acts by itself (`thoughts.md`): an operational
database, a background worker that executes tasks, approvals, a planner, model adapters. None of that is built
here. The brain stays a memory: its record is Markdown and the log, it changes nothing outside itself, and an
unattended run only reads. A database of intentions in `.cache/` would be a second record, one that git does
not carry to another machine. A program that acts (a task runner with its own approvals and audit trail) reads
the brain through `brain mcp` and keeps its own state.

F19 to F23 are what was taken from two more notes, on emotions and on a personality (`emotions.md`,
`personality.md`; decided 2026-10-10, D20). They describe the brain having feelings and traits of its own: a stored
state of emotion and of mood, a score for trust, attachment and aversion toward each person and tool, a profile
of trait numbers, a `/feel` and a `/personality`. Not built as written: a table of feelings is a second record
beside the pages and the log, and a trait written `curiosity: 0.85` has no code that reads it, so it is prose for
the model under a number. `salience` stays the mark of what matters, and the notes' rule for it is kept: it moves
attention, never what is held true. It stays out of the rank of recall for now: that is the same kind of lift as
`use_lift`, and is judged when that one is (TASKS 25).

F24 to F28 are the form of it that keeps the rules (decided the same day, D23). A feeling is worked out from the
log and the pages when it is asked for, as recall strength is, and fades as the log moves on: nothing is stored,
and each one names its causes. A trait is a number only where it has something to move: a threshold that exists,
or how fast a feeling fades. Still not built: scores for love, attachment or aversion toward a person or a tool
(the brain holds no person yet; when it does, what it knows of one is read from the pages that name them), and
anything that acts. A feeling about its own runs, and a motive that picks the next action, need the runtime
above, and that is still no.

F29 to F37 reopen the first decision above in part (decided the same day, D24). Of what the three notes ask of
a finished brain, four things need a loop that acts: pursuing a goal, acting alone within limits, an audit of
what was done, recovery after a crash. So the brain acts, on itself. What is kept from the first decision is
its reason: there is still no database of intentions. The loop's state is the log, one line a transition, read
when asked, so git still carries all of it and a rollback still undoes it. And the brain still changes nothing
outside itself: outside work goes to a runtime with approvals of its own (ACLine, on this machine), which
reads the brain through `brain mcp`, and what came of it returns as an input. Still not built: a rewrite in
another language, a second task engine, and any action the policy page does not name.

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
| Remembering to do | F14, F15, F16, F17, F18 | A reminder that says when, is found when its event comes, shows without a session, and records how it ended |
| What matters | F19, F20, F21, F22, F23 | The mark of what matters reaches the pages it was meant for, has a reason, is asked about again; both sides come back at recall |
| Feelings and character | F24, F25, F26, F27, F28 | What the record gives the brain to feel, where that moves attention, and a character whose traits have something to move |
| A brain that acts on itself | F29, F30, F31, F32, F33, F34, F35, F36 | Named actions under a policy, a worker, approvals, then a planner; each proved with actions a rule can run before a model chooses one |

Smallest useful first step: P0 and P1, then Upkeep. Bundles can run in any order after that.

## 5. How each item is checked

- Tests: `brain test` plus a new test beside the nearest existing one (`test_skills.py` for skills,
  `test_hooks.py` and `test_walls.py` for hooks, `test_retrieval.py` for search).
- Retrieval items: `brain eval --baseline engine/eval/baseline.json` must not regress on the fixture.
- Brain items: `brain check --guard` passes and `brain errors` shows nothing new from the item.
- Each finished item gets a log line (`engine` operation) and a line in the README command table.
