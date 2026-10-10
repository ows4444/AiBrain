# AiBrain: structure, architecture and flow

As of 2026-10-10. Read with `CLAUDE.md` (the rules every procedure shares) and `README.md` (install and use).
This file describes how the pieces fit; it does not repeat the rules.

## 1. The idea in one paragraph

A knowledge base for one owner, modelled on human memory. The owner puts material in `senses/` and asks
questions. A language model does the reading and writing of pages (it follows the skills). A small
Python engine does everything that must be exact: counting, ranking, checking and refusing. Pages are plain
Markdown with frontmatter; the only record of use is an append-only log. Everything else (recall strength,
decay, rehearsal schedules, queues) is computed from pages and that log when asked, never stored.

## 2. The three layers

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 1. DATA     the brain: plain Markdown folders (what the owner keeps)       │
│    inbox/ senses/  cortex/  hippocampus/  prefrontal/  dormant/  motor/   │
├────────────────────────────────────────────────────────────────────────────┤
│ 2. ENGINE   engine/: deterministic Python, standard library only          │
│    lib/ (model + instruments)  hooks/ (walls + sensors)  bin/brain (CLI)  │
├────────────────────────────────────────────────────────────────────────────┤
│ 3. PROCEDURES  engine/skills/ + engine/agents/: instructions the model    │
│    follows; they call the engine for anything that needs to be right      │
└────────────────────────────────────────────────────────────────────────────┘
        host: Claude Code plugin `aibrain`
```

The split is the main design decision. The model is trusted with judgment (what a source said, whether two
ideas are the same) and not with arithmetic or rules: counts, search, schema, immutability and secret
scans live in code and run as hooks or `brain` commands.

## 3. The data layer (the brain's folders)

| Folder | Role | Written by | Rule |
|--------|------|-----------|------|
| `inbox/` | quick notes from anywhere | owner | swept into `senses/inbox/` by `/ingest` |
| `senses/` | input as it arrived (`assets/` holds images) | owner, `brain fetch`, `brain chats` | never edited after landing; only `/forget` removes, on the owner's yes |
| `cortex/episodes/` | one page per input: what that source said | `/ingest` | "this source says X", not "X is true" |
| `cortex/concepts/` | one idea per page | `/sleep` | needs 2+ distinct sources or one salient (`salience` 4+) |
| `cortex/entities/` | people, organisations, products, tools | `/sleep` | what it is and why it is here |
| `cortex/insights/` | what no single episode said | `/sleep` | agreements, conflicts, patterns |
| `cortex/decisions/` | choices: options, frozen `## Expected`, outcome | `/decide` | `## Expected` never rewritten once decided |
| `hippocampus/` | `index.md`, `log.md`, `metrics.md`, `fingerprints.md`, `intentions.md`, `tuning.md` | skills (the log only through `brain log`, the index's listing through `brain index`) and `brain fingerprint` | the log is append-only; the index's listing is rewritten every run, its Gaps kept by hand; `tuning.md` holds the thresholds this brain keeps at its own value |
| `prefrontal/<name>/` | projects, one goal each (`CLAUDE.md` is page `[[name]]`) | `/focus` | pages linked from live goals and active projects never fade |
| `dormant/` | faded pages: out of index and graph, still searchable | `/maintain` | moved only on approval; nothing moves them back yet |
| `motor/` | reports, drafts, exports for use outside | `/write`, `brain export` | `publish: true` is opt-in |
| `OWNER.md` | who the owner is and their goals | `/owner` | one goal per line: `- goal by DATE -> [[page]]` |

Page contract: frontmatter `title`, `summary` (one sentence, max 200 chars), `type`, `created`, `updated`
(dates as `YYYY-MM-DD`, no time of day), optional `aliases` and at most three `tags` from the vocabulary in
`CLAUDE.md`. Links are `[[wikilinks]]`; typed ones are `(supports:: [[Page]])` with `supports`,
`contradicts`, `extends`, `part-of`, `applies`.

## 4. The engine layer

### 4.1 The model: `engine/lib/vaultlib.py`

One `Vault` class, composed from four mixins over four base modules, so every script and hook reports the
same numbers.

```
vault_model.py      constants, field registry, page parsing, Page          (no brain walk)
vault_tuning.py     every threshold: default, range, what it does; a brain's own values
vault_events.py     hippocampus/log.md parsed once into typed events
        │
vaultlib.Vault = GraphMixin + MemoryMixin + PurposeMixin + RetrievalMixin
  vault_graph.py      edges, orphans, components, hubs, bridges, clusters, near-duplicates
  vault_memory.py     recall strength, sleep queue, evidence, confidence, decay, calibration
  vault_purpose.py    goals, projects, intentions, and what they keep in use
  vault_retrieval.py  BM25 search, spreading-activation recall, co-recall weights
  vault_cache.py      term frequencies in .cache/search.sqlite (rebuildable, optional)
```

Key property: **nothing derived is stored**. Recall strength, the Hebbian pair weights, rehearsal dates
and goal activity are all folded out of the log at read time, so editing or rolling back the log changes
every view at once.

Every number a judgment rests on (when a concept is stale, where recall stops, how a word in a title weighs)
is one entry of the registry in `vault_tuning.py`. A brain changes one with a line under `## Overrides` in
`hippocampus/tuning.md`; `Vault.tuning` is the result, and no module keeps a number of its own. A command whose
text names a threshold carries the brain's overrides in its result (`tuning`), so the text and the JSON agree.
The numbers the documents state as rules (two sources for a concept, salience 4, a summary of 200 characters)
are not thresholds and stay constants.

### 4.2 The instruments: `bin/brain` → `lib/*.py`

`brain` finds the brain (nearest folder at or above the working directory holding `cortex/` and
`hippocampus/`, or `$BRAIN_ROOT`) and calls the command's module in its own process. Every command is called
one way, stated in `lib/commands.py`: its module has `arguments(parser)`, `run(root, args) -> dict` (what it
found or did, as data) and `render(result, args) -> text` (the same for a person). `brain` prints the text, or
the dict with `--json`, which every command takes. Another program makes the same call without a process,
`commands.call(name, argv, root)`, and reads the dict; a command that will not do what was asked raises
`Refused`. The modules are not scripts: `brain` is the one way in.

| Group | Commands |
|-------|----------|
| Find | `search` (BM25), `recall` (words, then links), `since` (period view) |
| Check | `check` (links, schema, index drift, edited inputs), `introspect` (18 views; `--gaps` is what was asked and not answered), `eval` (a question set, or with `--from-log` the log's own questions, each replayed as the brain was that day; `--set` tries a threshold at another value and writes nothing), `ground` (a drafted answer or piece held to the pages it cites: the sensor for the core rule of `/ask` and `/write`) |
| Input | `fetch`, `chats`, `session`, `fingerprint`, `fit` (the pages an input's own words reach, the held ideas it names), `new` |
| Record | `log` (the one writer of log lines: it checks the operation and every page name), `index` (rewrites the index's listing from the pages) |
| Output | `export`, `graph` |
| Remove and continue | `forget` (remove an input), `resume` (write where the work stands) |
| Operate | `statusline`, `cache`, `errors`, `synth`, `bench`, `test` |

### 4.3 The hooks: `engine/hooks/` (six events, one command each)

| Event | Hook | What it does | Can block |
|-------|------|--------------|-----------|
| SessionStart | `wake_up.py` | briefing: owner, queues, last activity, engine drift | no |
| UserPromptSubmit | `prompt_recall.py` | adds matching page summaries to a question (off unless `BRAIN_PROMPT_RECALL=1`) | no |
| PreToolUse (write, edit, bash) | `gate.py pre` | runs the walls in turn: `protect_senses.py` (edits to existing inputs; `brain forget --yes` is an "ask"), then for a write `protect_log.py` (the log written only by `brain log`), `protect_expected.py` (a frozen `## Expected`) and `validate_page.py` (schema before the write) | yes |
| PostToolUse (write, edit) | `gate.py post` | `validate_page.py` (schema of the file as written), `scan_secrets.py` (credentials) | feedback |
| PreCompact | `save_resume.py` | writes the "where the work stood" note | no |
| Stop | `check_recall.py` | a turn that recalled but logged nothing is asked to log once | yes |

A wall is a function of one tool call that returns nothing, a block or an ask. Each is its own file and still
runs on its own; `gate.py` calls every wall of an event in one process (a write used to start six) and says
what each would have said. What they share is `shared.py`: finding the brain, the text an edit would leave, a
decision's `## Expected` and `status`, and how a wall answers Claude Code. It uses the standard library only and
nothing from `lib/`, so a broken import there cannot open `protect_senses.py`, `protect_log.py` or
`protect_expected.py`, the three walls over what can never be undone. `validate_page.py` and `scan_secrets.py`
load the engine's library when a call names a page. A wall that raises, or cannot be loaded, is logged; the call is
then blocked when it writes into `senses/` or `cortex/decisions/` and let through anywhere else, where
`brain check` at the commit gate still catches the page. `lib/` keeps its own copies of what `shared.py` holds,
and a test holds the two to the same answers. Hooks that must never block (`prompt_recall`, `save_resume`,
`statusline`, `check_recall`) fail silent; both kinds write one line to `.cache/errors.log` (`brain errors`) so a
swallowed crash is not invisible.

### 4.4 The gates outside a session

`engine/githooks/pre-commit` and `.github/workflows/check.yml` run the same `brain check --guard` and
`brain test` (Python 3.9 to 3.13). `.claude/settings.json` allows the read-only `brain` commands and denies
`rm -rf`, `git push`, `git reset --hard`, `git clean` and reads of `.env`, `.key`, `.pem`.

## 5. The procedure layer

### 5.1 Skills (19), grouped by the stage they serve

| Stage | Skills |
|-------|--------|
| Set up | `/start`, `/owner` |
| Encode | `/ingest` |
| Consolidate | `/sleep`, `/tend` (encode + consolidate + check + report) |
| Recall | `/ask`, `/rehearse`, `/explore` (generated, never evidence), `/decide` |
| Purpose | `/focus`, `/remind` |
| Output | `/write` |
| Review and repair | `/reflect`, `/health`, `/maintain`, `/guard` |
| Control | `/forget`, `/rollback`, `/commit` |

`/commit`, `/forget`, `/rollback`, `/start`, `/owner` and `/tend` are manual-only
(`disable-model-invocation`). Skills that answer or write from pages also append a `recall` log line.

### 5.2 Agents (7)

| Agent | Model | Tools | Called by |
|-------|-------|-------|-----------|
| encoder | sonnet | read + write | `/ingest`, `/tend` |
| consolidator | inherit | read + write | `/sleep`, `/tend` |
| critic | inherit | read + bash | `/tend`, `/commit`, `/rollback` |
| researcher | inherit | read + bash | `/ask` |
| curator | haiku | read only | `/sleep`, `/maintain` |
| reviewer | sonnet | read only | `/reflect` |
| graph-analyst | haiku | read + bash | `/health` |

Only encoder and consolidator write. The critic judges a run in a clean context against its log line.

## 6. The flows

### 6.1 Memory lifecycle

```
 owner ─► inbox/ ─┐
 URL ──► brain fetch ─┤
 chat export ► brain chats ─┼─► senses/ ──► brain fingerprint (SHA-256 per input)
 file ───────────────┘            │
                                  ▼  /ingest  (encoder)
                    cortex/episodes/  one per input, links to existing pages,
                                      new ideas under ## Candidates, log line
                                      contradiction ► (contradicts:: [[page]]) queued
                                  │
                                  ▼  /sleep  (consolidator), oldest first
          candidate named by 2+ distinct sources, or 1 salient ─► cortex/concepts/
          people, tools, orgs ─► cortex/entities/    cross-episode patterns ─► cortex/insights/
          reviewed decisions replayed like episodes
                                  │
        /ask  /rehearse  /decide  /write  (recall, each leaves a log line)
                                  │
                                  ▼  log.md (append-only) ◄── the only record of use
       pages never recalled and linked only from their own episodes ─► fade to dormant/
       (later if more salient; pages tied to live goals/projects never fade)
```

### 6.2 One recall (`/ask`)

1. `prompt_recall` (if enabled) adds a pointer: matching summaries only.
2. `/ask` runs `brain recall`: BM25 seeds activation, which spreads 1 to 2 hops along links, stronger on typed
   links and on pairs recalled together before. Each hit shows how it was reached, its confidence, and the
   section to read first: the one holding the question's words that the page's title does not.
3. The model reads the pages and answers from them with inline citations; outside knowledge is labelled.
   "Not covered by any page here" is a valid answer. A stale page is put to the owner, never overwritten.
4. The skill runs `brain log recall`, which checks the page names and appends
   `DATE recall <question> -> [[page]], ...` to the log.
5. `check_recall` (Stop) confirms the line exists, else asks once.
6. The next recall sees stronger pairs: pages named together in a recall line associate more strongly, and
   the line keeps each of them in use, so it does not fade. Both are folded from the log. A page's own recalls
   do not lift its rank: the only lift from its history is its rehearsal level, which `/rehearse` moves.

### 6.3 One write, as the hooks see it

```
model calls Write/Edit ─► gate.py pre:  protect_senses, protect_log, protect_expected, validate_page (before)
        (any may refuse: exit 2, one error-log line each, every message shown to the model)
   ─► file written ─► gate.py post: validate_page (as written), scan_secrets ─► errors fed back
```

### 6.4 A session

`SessionStart` briefing → work (walls on every write) → `PreCompact` resume note → `Stop` recall check →
pre-commit and CI gates at `git commit`.

## 7. Hosts

| Host | How the engine is reached | Status |
|------|---------------------------|--------|
| Claude Code | plugin `aibrain` (`engine/.claude-plugin`, `hooks/hooks.json`, `skills/`, `agents/`, `bin/` on PATH) | primary |

No other host is supported: the hooks are Claude Code's. A read-only MCP server (`REFACTOR.md` 5.3) is the
planned way for another host to read the brain. The brain also works as plain Markdown in Obsidian (the folder
is its own vault).

## 8. Observability

| Where | Holds | Time resolution |
|-------|-------|-----------------|
| `hippocampus/log.md` | every operation and recall | date |
| `hippocampus/metrics.md` | health snapshots | date |
| `hippocampus/fingerprints.md` | hash of each input | date |
| `.cache/errors.log` | swallowed crashes and refusals (`brain errors`) | date and time, local |
| `.cache/prompt-recall.log` | each prompt-recall decision | date and time, local |
| `.cache/search.sqlite` | term frequencies (`brain cache`) | none |

`.cache/` is git-ignored and always rebuildable.

## 9. Limits that follow from this design

- Search is word-based plus link spreading; there is no embedding search.
- Nothing runs unless a session is open (no scheduler); reminders and decay act only then.
- The model does the extraction from PDFs, images and transcripts; the engine has no extractor.
- One owner; memory dates carry no time of day, so order within a day is log position.
- Enforcement needs Claude Code hooks; no other host runs them.

The ideas for lifting these are in `engine/ROADMAP.md`; the order of work is in `engine/REFACTOR.md`, and its
checklist in `engine/TASKS.md`.

## 10. Where to start reading the code

1. `CLAUDE.md`, then `engine/templates/README.md` (every field).
2. `engine/lib/vault_model.py`, then `vault_events.py` (the vocabulary and the log).
3. `engine/lib/vault_retrieval.py` (recall) and `vault_memory.py` (decay, evidence).
4. `engine/hooks/shared.py` (how a wall answers), `protect_senses.py` (a wall) and `engine/lib/commands.py` (how
   every command is called).
5. `engine/skills/ingest/SKILL.md` and `sleep/SKILL.md` (the core procedures).
