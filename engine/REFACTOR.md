# Refactor plan: structure first, then a brain that learns from its own use

As of 2026-10-09. Written from a full read of `engine/` (lib, hooks, bin, skills, agents, templates), one run
of the tests and of the answer test set, and timings on synthetic brains of 1,000 and 5,000 pages. The tests
were run, not read line by line. Read with `ARCHITECTURE.md` (how the pieces fit) and `ROADMAP.md` (the feature
list). This file gives the order of work, and says which roadmap items it moves, splits or defers.

## 1. Verdict

The engine is sound and should not be rewritten. About 6,400 lines of Python sit under 316 tests, with every
line and branch run in CI. The split between the model (judgment) and code (counting, checking, refusing) holds
everywhere, and nothing derived is stored. A refactor that keeps those three properties is cheap and safe.

What holds it back, most limiting first:

1. **It has never run on real content.** The brain holds 0 pages and the log 0 lines. Every threshold was tuned
   on a fixture of 21 pages and 37 questions.
2. **The one record it learns from is typed by hand and hardly checked** (A1).
3. **It learns less from use than the documents say** (A2), and it cannot test itself on its own history.
4. **Recall is words only.** A question in other words than the page loses (A4), and questions the brain does
   not cover still get pages (A3).
5. **Every command loads and computes everything.** `brain introspect` takes 8 s at 5,000 pages (B1, B2).
6. **Nothing runs between sessions** (roadmap F2).

The plan in one sentence: make the log exact, make the engine cheap to extend, let the brain measure itself on
its own use, raise recall with what is already in the loop (the model, at write time), and only then weigh
embeddings.

## 2. What was measured

| What | Result |
|------|--------|
| `brain test` | 316 tests pass in 22 s |
| `brain eval`, standard set (13 questions) | recall hit@1 0.846, hit@5 0.923; search 0.769, 0.808 |
| `brain eval`, paraphrase set (8) | recall hit@1 0.750, hit@5 0.938; search hit@1 0.625 |
| `brain eval`, first set (8) | recall hit@1 0.750, hit@5 1.000 |
| `brain eval`, uncovered (6) | recall still lists pages for 2 of them |
| Bytes an answer reads per question | 3,078; the expected pages alone are 1,397 |
| Recall, warm cache, 1,000 / 5,000 pages | 0.16 s / 0.47 s (the README says 0.45 s: it holds) |
| Status line and wake-up hook | 0.13 s / 0.35 s |
| `brain check` | 0.20 s / 1.80 s (1.25 s of it in `near_duplicates`) |
| `brain introspect`, any flag | 0.67 s / 8.08 s (nearly all of it in `candidate_pairs`) |
| `Vault()` load alone at 5,000 pages | 0.58 s, paid by every command, hook and status-line refresh |
| One hook process | 24 to 32 ms; five run on each Write or Edit, about 145 ms |

The synthetic brain draws its text from 40 words, so it overstates how many candidate pairs match. The cost of
each comparison is the engine's own. The timing scripts are not in the repository yet (item 0.3).

## 3. Findings

### A. Correctness and learning

| ID | Finding | Evidence |
|----|---------|----------|
| A1 | A recall line that names a page that does not exist strengthens nothing and is reported nowhere. A line with a malformed date is dropped in silence. Only an unknown operation is listed, and it does not fail. The log is "the only record of use", and the model types every line of it by hand. | `vaultlib.py:115` skips the log when resolving links; `vault_events.py:27` drops what does not parse; `vault_memory.py:38` checks the operation only. Probe: lines naming `[[spacing-efect]]`, `[[no-such-page]]` and dated `2026-10-2` gave `brain check` exit 0 and no mention. |
| A2 | A page's own recalls do not change its rank. Recall lines feed pair weights and keep a page from fading; the only lift on a page is its rehearsal level. ARCHITECTURE 6.2 step 6 says "the next recall sees stronger pages and stronger pairs". | `vault_retrieval.py:259`, `vault_memory.py:100`. Probe: 28 recall lines naming one page left every score identical. |
| A3 | Abstention reads how much of the question the best page holds, so a question whose subject the brain never mentions passes when its other words match. "Which painters did Picasso learn from?" scores 0.49 against a bar of 0.15 and returns four pages. The engine knows `picasso` is in no page and does not say so. | `vault_retrieval.py:239`; eval questions u05, u06. |
| A4 | Vocabulary gap. "Why do I lose what I learned last week?" does not find `forgetting-curve`; "Which program picks the day I next see a card?" does not find `anki`. | eval questions q10, p07. |
| A5 | The fixture is too small to tune on: 21 pages. Field weights and the recall floor are set from it. | `vault_retrieval.py:30`, `vault_model.py:187`. |

### B. Structure and cost

| ID | Finding | Evidence |
|----|---------|----------|
| B1 | `candidate_pairs` tokenises every page again for each held candidate. | `vault_memory.py:259` |
| B2 | `introspect.report()` computes every view whatever flag is passed, so `brain introspect --due` costs the same 8 s. `due_for_rehearsal` is computed three times. | `introspect.py:228`, lines 247, 265, 267 |
| B3 | No adjacency. `links_from`, `evidence_for` and `confidence` scan every edge on each call, and `typed_edges()` copies its set each time it is asked. | `vault_purpose.py:44`, `vault_memory.py:393`, `vault_graph.py:185` |
| B4 | The same code in several places with no test holding the copies in step: finding the brain (six times), the text an edit would leave (twice), reading `## Expected` and `status` (twice). | `bin/brain:60`, `vault_model.py:256`, `errlog.py:35`, `protect_senses.py:22`, `protect_expected.py:22`, `check_recall.py:27`; `validate_page.py:35`, `protect_expected.py:57`; `link_check.py:49`, `protect_expected.py:39` |
| B5 | No single calling surface. `bin/brain` starts a second process and passes the root three different ways; each script has its own argument parsing and its own JSON shape; skills read the text form. | `bin/brain:36` |
| B6 | About 60 thresholds are constants in the engine. Trying another value means editing `engine/`, updating the plugin and restarting, so the calibration checkpoint has nowhere to record its result. | `vault_model.py:131` to 221 |
| B7 | `check_recall` parses the whole transcript on every Stop; `save_resume` already reads only its last 4 MB. | `check_recall.py:68`, `save_resume.py:109` |
| B8 | The index listing is derived data kept by hand: each line is the page's `summary`, and every run must edit it. `brain check` exists partly to catch the drift. | skills `ingest` step 6, `maintain` step 7 |

### C. The two documents

| ID | Finding |
|----|---------|
| C1 | `.opencode/plugins/aibrain.js`, `.opencode/skills/`, `.opencode/commands/` and `opencode.json` are described as present and tested (ARCHITECTURE sections 2, 7 and 9; ROADMAP rules, P2 and section 5). None of them is in the repository or its history. |
| C2 | ARCHITECTURE 6.2 step 6 overstates what recall learns (A2). |
| C3 | Small ones. Section 4.3 says seven events; `hooks.json` registers six, with nine commands. It says walls are self-contained; `validate_page.py` imports `vaultlib`, so the schema wall lets a write through if that import breaks (the commit gate still catches the page). `templates/README.md` places `FIELDS` in `vaultlib.py`; it is in `vault_model.py`. |
| C4 | ROADMAP is a feature list with sound gates, and it is right to put P0 and P1 first. It has no item on the log's integrity (A1), none on structure (B), and one recall item only: F1, embeddings, effort L, which breaks "standard library only". Three cheaper recall steps need nothing new (4.1 to 4.3 below). P1 asks the owner to write a question set by hand, when the log will hold labelled questions (3.1). F12 depends on F1 for no stated reason; it depends on B5. |

## 4. Target shape

Three layers stay as they are. Inside the engine, four things change; nothing else moves.

```
skills · agents · scheduler · MCP          call one surface and read JSON
              │
bin/brain     run(root, args) -> dict, render(dict) -> text          (2.4)
              │
Vault         pages + adjacency (2.1) · views on demand (2.3) · tuning per brain (2.5)
              │                                   │
pages (Markdown, the source of truth)     log.md, written only by `brain log` (1.1)
              │                                   │
.cache/ terms, page index (2.7)           eval --from-log, introspect --gaps (3.1, 3.2)
```

Rules every item keeps: standard library only in `engine/lib`; nothing derived is stored; the log is append-only;
`senses/` is never edited; `brain test`, 100% coverage and `brain eval` at or above its baseline before an item
counts as done.

## 5. The plan

Effort as in ROADMAP: S under half a day, M one to two days, L several days. Phases 0 to 5 come to roughly 16 to
22 working days; that is an estimate.

### Phase 0. Baseline (half a day)

| ID | Item | Effort | Done when |
|----|------|--------|-----------|
| 0.1 | Commit the staged work (the error log, the two documents) | S | Clean tree, CI green |
| 0.2 | Correct the documents: C1 (decision D5), C2, C3 | S | No sentence describes something that is not there |
| 0.3 | `brain bench [--pages N]`: a synthetic brain in a temporary folder, each instrument timed | S | It prints the timing rows of section 2 |
| 0.4 | Roadmap P0 and P1 start now and run alongside: they need the owner, not code | | 20 inputs, one `/tend` |

### Phase 1. An exact record of use (1 to 2 days)

| ID | Item | Fixes | Effort | Done when |
|----|------|-------|--------|-----------|
| 1.1 | `brain log OP WHAT [--pages NAME ...] [--result TEXT]`: the one way a procedure writes a log line. It checks the operation, resolves every page and refuses an unknown one (naming the closest), stamps the date and appends one line. For `recall`, WHAT is the question as it was asked, cut at 120 characters, not a shortened form | A1 | M | Every skill's log step names the command and `test_skills.py` holds them to it; `check_recall` accepts it; the allow-list has `Bash(brain log *)` (D1) |
| 1.2 | `brain check` lists dated lines that do not parse, and recall or rehearse lines whose targets reach no page and no dormant name. Listed, not failed: history may name pages since merged | A1 | S | The probe in A1 reports all three lines |
| 1.3 | A wall on the log: a Write or Edit of `hippocampus/log.md` is refused, naming the command to use. Append-only then holds when the line is written, not only at the commit gate | A1 | S | A test in `test_walls.py` |

Time of day in the log (roadmap F9) becomes an option of 1.1 once it owns the format; it is not part of this phase.

### Phase 2. Structure (4 to 6 days)

Nothing here changes what a command returns. Gate for every item: the tests pass, `brain eval` equals its baseline
to three decimals, and `brain bench` shows the gain.

| ID | Item | Fixes | Effort | Done when |
|----|------|-------|--------|-----------|
| 2.1 | Adjacency built once in `_resolve`: outbound, inbound and typed links by page. `links_from`, `evidence_for`, `confidence` and `inbound` read it; `typed_edges()` stops copying | B3 | S | `confidence` on 200 concepts at 5,000 pages falls from 0.10 s to under 0.01 s |
| 2.2 | `candidate_pairs`: tokenise each page once, index name words, compare only pairs that share a word, as `near_duplicates` already does | B1 | S | Under 0.5 s at 5,000 pages; the same pairs on the fixture |
| 2.3 | Views on demand: `introspect` becomes a table of named views, each a function of the vault. A flag computes its own views; the default computes the summary | B2 | S | `brain introspect --due` under 1 s at 5,000 pages |
| 2.4 | One calling convention: each script exposes `run(root, args) -> dict` and `render(dict) -> text`. `bin/brain` calls them in its own process, passes the root one way, and every command takes `--json`. A test pins the keys of each command's JSON | B5 | M | A scheduler or an MCP server can call any instrument without parsing text |
| 2.5 | Tuning per brain: thresholds move into one registry (name, default, range, what it does). A brain overrides them in `hippocampus/tuning.md`; `brain check` fails on an unknown key or a value out of range; `brain introspect --usage` shows default and override; `brain eval --set key=value` tries a value without writing it | B6, A5 | M | A threshold is changed, measured and rolled back without touching `engine/` or restarting (D4) |
| 2.6 | Walls share one file and one process per event: `hooks/gate.py` runs them in order. The shared code lives in `hooks/`, imports nothing from `lib/`, and each hook file stays runnable on its own. A wall that raises blocks a write into `senses/` or `cortex/decisions/` and lets any other through with an error-log line | B4, C3 | M | One process before a Write or Edit and one after, from five; the existing hook tests pass unchanged |
| 2.7 | `check_recall` reads the end of the transcript, as `save_resume` does | B7 | S | A test with a transcript over the limit |
| 2.8 | Index listing generated: `brain index` rewrites the listing between two markers (by type, one line a page, its `summary`) and leaves `## Gaps` and everything outside the markers alone. Skills stop editing the index | B8 | S | `not_in_index` cannot occur after a run (D3) |
| 2.9 | Only when measured: a page index in `.cache/`, parsed records keyed by path, size and modification time, so an unchanged page is not read again | | M | Build it when `Vault()` load passes 0.3 s on the real brain, about 2,500 pages |

### Phase 3. The brain measures itself (2 to 3 days)

| ID | Item | Effort | Depends on | Done when |
|----|------|--------|------------|-----------|
| 3.1 | `brain eval --from-log`: every logged question, with the pages that answered it, is a test case. Each is replayed as of its own date, using only the log lines before it, so the pair weights it taught are not used to find it. Scored like the fixture. Lines that named no page are the uncovered set | M | 1.1 | It runs on a synthetic brain in the tests, and on the real one after P0 |
| 3.2 | `brain introspect --gaps`: what was asked and not answered. Recall lines with no page, grouped by the rare words they share, with any held idea or index gap they name. Read-only, from the log | S | 1.1 | `/reflect` reads it for Thin spots; it tells the owner what to read next |
| 3.3 | The calibration checkpoint closes its loop: `/health` runs 3.1 before and after each `--set` trial and writes the value kept to `tuning.md`, with a `health calibration` log line | S | 2.5, 3.1 | Skill text only |

Print two limits with every 3.1 result. The cases are questions the retriever of that day already answered, so it
shows a regression and not absolute quality. And the pages are as they are now, not as they were. The owner's own
paraphrase questions (roadmap P1) stay worth writing for that reason; the log supplies the volume.

### Phase 4. Better recall without a dependency (4 to 6 days)

Gate for every item: no set of the fixture falls below its baseline, and the target named is reached. An item that
misses its target is closed and not shipped.

| ID | Item | Fixes | Effort | Target |
|----|------|-------|--------|--------|
| 4.1 | Say what the brain never mentions: `brain recall` prints the question's words found in no page, dormant ones included (`unseen: picasso`), and the JSON carries them. Then tune abstention on that signal | A3 | S | Uncovered questions that still get pages: 2 of 6 to 0, covered sets unchanged |
| 4.2 | Questions a page answers, written when the page is: an optional `answers:` field, up to five short questions in the owner's kind of words, filled by `/ingest` and `/sleep` and searched as a field of its own. The model's understanding goes into the index at write time, where it is already paid for | A4 | M | Paraphrase recall hit@1 0.750 to 0.875 or better (D2) |
| 4.3 | Several wordings, one ranking: `brain recall Q --also Q2 --also Q3` fuses the rankings by reciprocal rank before spreading. `/ask` always passes two rewordings | A4 | S | Paraphrase hit@5 0.938 to 1.000; q10 found |
| 4.4 | `brain fit senses/FILE`: the pages and held candidates an input bears on, from its own rarest words. `/ingest` steps 3 and 5 use it in place of guessed topic words. Candidate names made of the same words after stemming count as one candidate | | M | On real ingests: more links per episode, more candidates reaching two sources |
| 4.5 | Use, recency and rank: try a capped lift from a page's own recall history, rehearsals left out. Keep it only if 3.1 improves and the fixture does not fall. Either way ARCHITECTURE 6.2 then says what is true | A2 | S | Decided by 3.1 on at least 50 logged questions |
| 4.6 | The best section with each row: `recall` names the section of each page that matches best, so an answer opens that first | | S | Bytes read per question below 2,500, from 3,078 |

Two cautions. For 4.2, the fixture's `answers:` must be written by an agent that sees the page and not
`questions.json`, or the number means nothing. For 4.5, the risk is that often-used pages crowd out the right one;
the cap and the gate are the guard.

### Phase 5. Trust and time (4 to 5 days)

| ID | Item | Effort | Depends on | Done when |
|----|------|--------|------------|-----------|
| 5.1 | `brain ground FILE`: for a drafted answer or piece, every `[[link]]` resolves, and every number and quoted phrase appears on a cited page or in a sentence labelled outside knowledge. It lists the rest. `/write` always runs it, `/ask` on long answers, the critic on a run | M | none | It flags nothing in reference answers and catches a planted number in the tests. The core rule of `/ask` gets a sensor, as logging did with `check_recall` |
| 5.2 | `brain tend --check` and its schedule: one read-only digest of the queues, rehearsals and reminders due, decisions to review, goals at risk and the gaps of 3.2. This is roadmap F2 steps 1 and 2, S1 and A1 | M | 2.4, 3.2 | The roadmap's own acceptance: a week alone gives one report and no page changes |
| 5.3 | A read-only MCP server over 2.4 (`search`, `recall`, `since`, `gaps`): roadmap F12, which no longer needs F1. Other hosts then read the brain without a second set of hooks | M | 2.4 | Another client lists and calls the four tools |

### Phase 6. Only when the log can judge it

| ID | Item | Build it when |
|----|------|---------------|
| 6.1 | Semantic search (roadmap F1), optional, vectors in `.cache/` | After 4.1 to 4.3, paraphrase hit@5 is still under 0.9 on 50 or more of the owner's own questions |
| 6.2 | Rehearsal intervals fitted to the owner's history, with graded answers, in place of the fixed ladder | The log holds 200 rehearsal lines |
| 6.3 | Confidence that weighs the kind of source (a study against a post that relays it), not only the count | 100 episodes, and the owner's view of what counts |
| 6.4 | A scheduled `/tend` that writes (roadmap F2 step 3) | 5.2 has run read-only for four weeks and the critic has passed each manual run in that time |

### Roadmap items, and where they are now

| Roadmap | Here |
|---------|------|
| P0 | 0.4, unchanged |
| P1 | 0.4, with 3.1 supplying most of the questions |
| P2 | D5: the OpenCode files are not in the repository |
| F1, S3 | 6.1, after 4.1 to 4.3 |
| F2, S1, A1 | 5.2, then 6.4 |
| F3 | 3.1 |
| F9 | An option of 1.1 |
| F12 | 5.3, depending on 2.4 instead of F1 |
| F4 to F8, F10, F11, F13, S2, S4 to S10, A2 to A6 | Untouched by this plan; 2.4 makes each of them smaller |

## 6. What not to do

- Do not rewrite the Vault into services or a package. The mixins are plain and tested; 2.1 to 2.3 remove the cost.
- Do not make a database the source of truth. `.cache/` stays something that can be deleted at any time.
- Do not add embeddings before Phase 4 is measured. The model is already in the loop at write time and at
  question time; 4.2 and 4.3 use it there for nothing.
- Do not let anything write to memory unattended before 5.2 has run read-only for weeks.
- Do not tune any threshold further on the 21-page fixture.

## 7. Decisions that are yours

| ID | Decision | Recommendation |
|----|----------|----------------|
| D1 | May `brain log` run without asking (the allow-list)? | Yes. It can only append one checked line |
| D2 | A new optional field, `answers:`, on memory pages | Yes, and private, so `brain export` drops it |
| D3 | The index listing is generated. This changes "keep `index.md` current in the same run" in `CLAUDE.md` to "run `brain index`" | Yes |
| D4 | A new system page, `hippocampus/tuning.md`. This adds a system type to `CLAUDE.md` | Yes |
| D5 | OpenCode: build what the documents describe, or remove the claims | Remove them now; reach other hosts through 5.3 |
| D6 | Embeddings | Defer to the trigger in 6.1 |

The owner answered all six on 2026-10-09: yes to each recommendation. Progress is tracked in `TASKS.md`.

## 8. Where to start

Day one: 0.1 to 0.3, then 1.1 and 1.2. Day two: 2.1 to 2.3, the three small changes that take `brain introspect`
from 8 s to under 1 s. Alongside both, P0: twenty real inputs and one `/tend`, because Phases 3 and 4 are judged
on what that produces.
