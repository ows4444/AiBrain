# Tasks: every item of REFACTOR.md and ROADMAP.md, as a checklist

As of 2026-10-10. One box per item, in the order to do them; the steps under it are what the item takes.
Tick an item when its `Done when` line holds. The reasons, the measurements and the findings (A1, B2, ...) are
in `REFACTOR.md`; the scores and bundles are in `ROADMAP.md`. Where both files name the same work it is one
item here, tagged with both.

Tags: the source item, effort (S under half a day, M one to two days, L several days), and what it waits on.

Done, for every item that touches the engine:

- `brain test` passes, with a new test beside the nearest existing one and coverage still at 100%
- `brain eval` is not below its baseline on any set
- `brain check --guard` passes and `brain errors` shows nothing new from the item
- one `engine` line in the log once the brain is in use (D7: none before 4), and a row in the README command table when a command or skill was added
- a new skill is lowercase-hyphenated, matches its folder, and passes `test_skills.py`

## Decisions (yours; each blocks the item named)

D1 to D7 were answered by the owner on 2026-10-09, each as recommended; D8 to D27 on 2026-10-10, each put as a choice with a recommendation.

- [x] **D1. May `brain log` run without asking?** Decided: yes, it can only append one checked line. Unblocks 6.
- [x] **D2. A new optional field `answers:` on memory pages?** Decided: yes, and private, so `brain export` drops it. Unblocks 22.
- [x] **D3. Generate the index listing?** Decided: yes. Changes "keep `index.md` current in the same run" in `CLAUDE.md` to "run `brain index`". Unblocks 16.
- [x] **D4. A new system page, `hippocampus/tuning.md`?** Decided: yes. Adds a system type to `CLAUDE.md`. Unblocks 13.
- [x] **D5. OpenCode: build what the documents describe, or remove the claims?** Decided: remove them now, reach other hosts through 29. Unblocks 2 and closes 56.
- [x] **D6. Embeddings?** Decided: defer to the trigger in 30.
- [x] **D8. Item 10: accept 0.77 s at 5,000 pages, or go further?** Decided 2026-10-10: accept it. Closes 10.
- [x] **D9. Item 21: close it, or print `unseen:` as information only?** Decided 2026-10-10: close it. Closes 21.
- [x] **D10. A fresh agent to write the fixture data that 22 and 23 are measured on?** Decided 2026-10-10: yes, for both. Unblocks 22 and 23.
- [x] **D11. A writer agent for `/write`, a third agent that can write (49)?** Decided 2026-10-10: no. Closes 49.
- [x] **D12. The one door for a note taken away from the desk (35)?** Decided 2026-10-10: a folder that syncs to this machine. Unblocks 35.
- [x] **D13. What transcribes a recording (40, 41)?** Decided 2026-10-10: not now. Both stay open.
- [x] **D14. A quiz writer agent (48)?** Decided 2026-10-10: keep it open; not rehearsed enough to say.
- [x] **D15. What a read-only view for another person is (54)?** Decided 2026-10-10: nothing new. `/export` and `brain mcp` are the ways out. Closes 54.
- [x] **D16. Encryption at rest (55)?** Decided 2026-10-10: no. The disk and a private remote cover it, outside the engine. Closes 55.
- [x] **D17. Items 22 and 23 together: every recall number on every set is the same or better, except the `first` set's mrr, 0.854 to 0.844 (one question, one rank). Accept it?** Decided 2026-10-10: accept it. Closes 22 and 23; the table is under 23.
- [x] **D18. Should the brain grow the acting runtime of the "synthetic brain" notes (an operational database, a background worker that executes, approvals, a planner), or stay a memory that other programs read?** Decided 2026-10-10: stay a memory. Five things are taken from the notes, all about remembering to do: items 57 to 61. The rest is not built here; a program that acts reads the brain through `brain mcp`. ROADMAP > What the brain does not become
- [x] **D19. Where do the notes themselves go (`engine/thoughts.md`, 104 KB, staged in the folder the plugin ships from)?** Decided 2026-10-10: it stays in this repository, at `engine/thoughts.md`, as it was pasted. It was first moved to the real brain's `inbox/` on the answer to this question, and brought back the same hour on your word, the same bytes; nothing of it is left in the other folder. It is in the folder and left out of the commits for now, also on your word. Items 57 to 61 are what was taken from it
- [x] **D20. Should the brain model emotions, moods, relationships and a personality of its own (the notes `emotions.md` and `personality.md`: a stored state of feeling and of mood, scores for each relationship, a profile of trait numbers), or take only what serves remembering?** Decided 2026-10-10: take five things, items 62 to 66, and build nothing else of it. The first 200 lines of `emotions.md` are the runtime D18 already answered. ROADMAP > What the brain does not become
- [x] **D21. What does a salience of 1, 2 and 3 mean?** Found on 2026-10-10 with item 63: in the real brain all 32 marked episodes touch a page a goal depends on, so the reason holds for nearly every input, and no rule set the level (19 at 2, 12 at 3). Decided 2026-10-10: the level is how many of the three reasons hold (touches a live goal or project, says the opposite of an established page, high stakes). Only the `/ingest` text changes; the marks already written stay as they are
- [x] **D22. Does a concept made from one episode marked 4 or 5 never fade either?** Found on 2026-10-10 with item 62: the engine has only ever kept the page that carries the mark, while `/ingest` said "the pages never fade". Decided 2026-10-10: `/sleep` writes the episode's mark on the concept it makes from it, so that page never fades and the mark is there to be lowered; item 64 asks about it once it goes unused. Only the `/sleep` text changes (and the critic's rule for a sleep run); a page an episode merely names still takes no more than 3
- [x] **D23. How far should the brain go toward emotions and a personality of its own?** Asked again on 2026-10-10, after D20. Four layers were put: feelings worked out from the record; a personality whose traits have something to move; relationships with people; a brain that acts. Decided 2026-10-10: the first two, items 67 to 71. D18 stays: nothing acts. Relationships wait until the brain holds people. What makes it fit is that a feeling is worked out from the log and the pages when asked and never stored, so D20's reason against a second record still holds. ROADMAP > What the brain does not become
- [x] **D24. Should the brain get the acting loop of `thoughts.md` after all?** Asked on 2026-10-10, after D23; it reopens D18 in part. Of the nine things the three notes ask of a finished brain, four need a loop that acts: pursuing a goal, acting alone within limits, an audit of what was done, recovery after a crash. Decided 2026-10-10: the brain acts on itself, and work outside it is handed to a runtime that has its own approvals (ACLine is installed on this machine: tasks, approvals behind a human token, verification, an audit trail), which reads the brain through `brain mcp`. Three rules were put with it and stand: the loop's state is the log, a line for each transition, and no database; an action runs alone only where a policy page names it, checked at the moment it runs; nothing outside the brain is touched from here. Items 72 to 80, after 68 to 71. ROADMAP > What the brain does not become
- [x] **D25. How is the planner (76) built, now that a model would run with nobody there for the first time?** Put on 2026-10-10: 72 to 75 are built and tested against crashes, and none has run on the real brain yet. Decided 2026-10-10: the half a rule can run first, a reminder that names several steps, held to the policy before any runs and picked up where it was interrupted. The model that writes a plan (`claude -p` with no tools, a schema for its answer and a cap on what it may spend) waits until 74's week has run on the real brain. So does the scheduled `/tend` that writes (33), whose own trigger has not come
- [x] **D26. How is `main` merged into the real brain, which was 22 commits behind and had an uncommitted change in `.claude/settings.json`?** Decided 2026-10-10: the change is shown first. It was a reformat and no setting: the `enabledPlugins` block moved below `statusLine`, on one line. `main` changed another part of the file, the allow-list
- [x] **D27. Go ahead with that merge?** Decided 2026-10-10: yes, with 78 and 79 committed here first, the reformat committed there as it stood, then `main` merged into `private`, `brain index` and `brain check` run there, and item 4 ticked. Tried beforehand without touching a file (`git merge-tree`): no conflict. Nothing is pushed: `private` is local only
- [x] **D7. Should engine work write `engine` lines into this brain's log now?** Found and decided on 2026-10-09: no, hold them until 4 puts the brain in use; git history records engine changes until then. The roadmap asks for one line per finished item, but the first dated line marks this brain as in use: `test_an_unused_brain_matches_the_template` then skips, and a clone no longer starts with an empty log.

## Phase 0. Baseline

- [x] **1. Commit the staged work** (REFACTOR 0.1, S)
  - [x] `brain check --guard` and `brain test` pass
  - [x] Commit the error log, `ARCHITECTURE.md`, `ROADMAP.md`, `REFACTOR.md` and this file (on `main`: the engine work of items 2 to 16 in `e1eddcd`, the four documents in the commit after it, with items 13 and 14)
  - [x] Done when: the tree is clean, and CI is green once you push (a session cannot: `git push` is denied on purpose). Everything through `6e6b627` is pushed, and its CI run was green on 2026-10-10
- [x] **2. Correct the documents** (REFACTOR 0.2, S, part waits on D5)
  - [x] OpenCode: ARCHITECTURE sections 2, 7 and 9; ROADMAP rules, P2, F13 and section 5 (as D5 says)
  - [x] ARCHITECTURE 6.2 step 6: recall strengthens pairs and keeps a page in use; a page's own recalls do not lift its rank, only its rehearsal level does
  - [x] ARCHITECTURE 4.3: six events and nine commands; `validate_page.py` and `scan_secrets.py` import the library, so they are not self-contained
  - [x] ARCHITECTURE 5.2: `/guard` does not call the critic (found while checking the table against the skills)
  - [x] `templates/README.md`: `FIELDS` is in `vault_model.py`
  - [x] ROADMAP F4 pointed to a "C1" the file never defines: the pointer is dropped, the door is still to be named (35)
  - [x] Done when: no sentence describes something that is not there (checked against the code: skills, agents, commands, hooks, settings, CI, the files and line counts both documents cite)
- [x] **3. `brain bench`** (REFACTOR 0.3, S)
  - [x] `engine/lib/bench.py`: a synthetic brain in a temporary folder, each instrument timed, `--pages N`, `--json` (and `--seed`, `--repeat`: the fastest of R runs)
  - [x] Add it to `bin/brain` (table and docstring), the README and ARCHITECTURE 4.2
  - [x] Tests at a small N, so coverage holds (four, under one second; 100% line and branch)
  - [x] Done when: it prints the timing rows of REFACTOR section 2 (at 1,000 pages: `introspect` 0.70 s, `candidate_pairs` 0.51 s, the five write hooks 0.15 s)
- [x] **4. Fill the brain** (REFACTOR 0.4, ROADMAP P0, S, the owner's)
  - [x] `/start`, then `/owner`: the real brain's `OWNER.md` is filled in
  - [x] 10 to 20 real inputs in `senses/` or `inbox/`: it has 45 encoded
  - [x] One `/tend`: 45 ingests and 11 sleeps are in its log
  - [x] Done when: `brain introspect` gives a verdict other than "too small to judge". It does, in the real brain (`~/Desktop/Nizaami/AiBrain`, branch `private`), seen on 2026-10-10: 57 pages (45 episodes, 5 concepts, 5 entities, 2 insights). It was open here only because this folder's own brain is the empty template. From now on a finished item that touches the engine also writes its `engine` line there (D7)
- [x] **5. A question set of your own** (REFACTOR 0.4, ROADMAP P1, S, after 4)
  - [x] `brain eval --root . --questions motor/eval-questions.json --draft 10`; write each question without the words to avoid. Done in the real brain on 2026-10-10, on your word to do it for you: ten paraphrases, one for each of the 5 concepts, the 2 insights and 3 of the entities. The wordings are the model's, written from each page's summary, and carry no `also`. Reword any of them in your own words, then save the baseline again
  - [x] Add two or three questions no page covers (`"covered": false`): three (the license ACLine is released under, ACLine on Kubernetes, caffeine)
  - [x] Run it, then `--save-baseline` (`motor/eval-questions-baseline.json`)
  - [x] Done when: hit@1 and hit@k are recorded on real content. Recall: hit@1 0.700, hit@5 1.000, mrr 0.803. Search alone: hit@1 0.900, hit@5 1.000, mrr 0.933
  - What it shows, with nothing changed for it: recall puts the right page first less often than search alone does (7 of 10 against 9; o10 finds `material-ui` at rank 5, behind `tui-porting-web-component-ideas`), and it still lists pages for all 3 uncovered questions, the one about caffeine among them. On the fixture that is 2 of 6. Ten questions is few, and it is the first number from real content that says where recall is weak here

## Phase 1. An exact record of use

- [x] **6. `brain log`: the one way a procedure writes a log line** (REFACTOR 1.1, M, waits on D1)
  - [x] `engine/lib/log.py`: `brain log OP WHAT [--pages NAME ...] [--result TEXT]` (and `--dry-run`, `--json`)
  - [x] Check OP against `OPS`; resolve every page and refuse an unknown one, naming the closest; stamp the date; append one line. Also refused: an unknown `[[link]]` typed in WHAT or `--result`, a rehearsal line with no page, a line holding a credential
  - [x] For `recall`, WHAT is the question as asked, cut at 120 characters; no page writes `-> none`, which is what 18 and 19 read as an uncovered question
  - [x] Add it to `bin/brain`; allow `Bash(brain log *)` in `.claude/settings.json`
  - [x] The log step of every skill that logs (16 of 19) names the command; `CLAUDE.md` > Log and its template say so
  - [x] `check_recall.py` accepts `brain log recall` and `brain log rehearse missed`, and no longer counts a call whose result was an error (a refused line, a refused edit)
  - [x] Done when: `test_skills.py` holds every skill to the command, and a typo in a page name is refused at the prompt
- [x] **7. `brain check` reads the log** (REFACTOR 1.2, S)
  - [x] List dated lines that do not parse, and lines whose date does not exist (`log_unread`)
  - [x] List recall and rehearse lines whose targets reach no page and no dormant name (`log_unresolved`)
  - [x] Both listed, not failed (history may name pages since merged); both in `--json`
  - [x] Done when: lines naming `[[spacing-efect]]`, `[[no-such-page]]` and dated `2026-10-2` are all reported
- [x] **8. A wall on the log** (REFACTOR 1.3, S, after 6)
  - [x] Refuse a Write, Edit or MultiEdit of `hippocampus/log.md`, naming `brain log` (`hooks/protect_log.py`, self-contained)
  - [x] One error-log line per refusal, kind `log`
  - [x] `brain forget` and the other engine writers are untouched; a shell append is not seen by the wall, and 7 lists what it gets wrong
  - [x] Done when: a test in `test_walls.py` shows the refusal

## Phase 2. Structure

Gate for every item here: the tests pass, `brain eval` equals its baseline to three decimals, and `brain bench`
shows the gain. Nothing changes what a command returns, except where a step says so.

- [x] **9. Adjacency built once** (REFACTOR 2.1, S)
  - [x] Outbound and inbound links by page, built once from the edges (`Vault.out_links`, `in_links`); the pages contradicting a page, with the typed links (`contradicted_by`)
  - [x] `links_from`, `evidence_for`, `confidence`, `inbound` and recall's `contradicted` read them; so do `project_report`, `schema_candidates` and `missing_from_index`
  - [x] `typed_edges()` stops copying its set, and `knowledge_edges()` is computed once
  - [x] Done when: `confidence` on 200 concepts at 5,000 pages takes under 0.01 s (0.104 s before, 0.003 s after)
- [x] **10. `candidate_pairs` without the repeated tokenising** (REFACTOR 2.2, S; built, 0.77 s accepted by D8)
  - [x] Tokenise each page's title, aliases and summary once
  - [x] Index words to candidates and pages; compare only pairs that share a word, as `near_duplicates` does. Candidates are no longer each compared with every other one either
  - [x] The same pairs in the same order as before, on the fixture and on five synthetic brains
  - [ ] Done when: the same pairs on the fixture, and under 0.5 s at 5,000 pages. The pairs are the same; the time is 0.77 s, from 7.64 s (0.043 s from 0.51 s at 1,000 pages). What is left is the cost of building 206,652 pairs, which the synthetic brain's 40-word vocabulary produces and a real brain would not. Accepted on 2026-10-10 (D8)
- [x] **11. Views on demand in `introspect`** (REFACTOR 2.3, S)
  - [x] A table of named views, each a function of the vault (`VIEWS`, computed and kept by `Report`)
  - [x] A flag computes its own views; no flag computes the summary; `due_for_rehearsal` is computed once
  - [x] Decided: `--json` with no flag still gives the whole report; with flags it gives the summary and those flags' views (it gave everything before). Its readers are served: `health` and the critic read the whole report, the curator reads `dormant`
  - [x] Fixed on the way: `--links` replaced the count of links with the list of suggestions, so the summary line printed that list. `links` is now always the count; the suggestions are `link_suggestions`
  - [x] The text of 16 of 19 flag combinations is byte-identical to before, on the fixture and a synthetic brain; the three that differ are the two changes above
  - [x] Done when: `brain introspect --due` takes under 1 s at 5,000 pages (8.07 s before, 0.36 s after; plain `introspect` 0.39 s, `--graph` 2.34 s from 10.42 s)
- [x] **12. One calling convention** (REFACTOR 2.4, M)
  - [x] Each command's module exposes `arguments(parser)`, `run(root, args) -> dict` and `render(result, args) -> text`; `lib/commands.py` states the convention and holds the table of commands. `render` takes the arguments as well as the dict: the text of `check`, `introspect`, `search`, `recall`, `errors` and `eval` depends on what was asked (which sections, which hint), and carrying that in the dict would have changed their JSON
  - [x] `bin/brain` calls them in its own process (`commands.main`) and passes the root one way: found once, checked once (`not a directory`, `not a brain`), handed to `run`. The modules are no longer scripts (no `__main__`, no shebang): `brain` is the one way in, and `commands.call(name, argv, root)` is the same call from Python, with `Refused` raised where `brain` exits 1
  - [x] `--json` on every command, added in one place. New on `graph`, `export`, `chats`, `resume`, `statusline` and `synth`; `errors --clear --json` prints JSON where it printed text
  - [x] A test pins the keys of each command's JSON (`test_commands.py`: the 22 commands in 35 forms, and that none is missing from the pin or from `brain help`)
  - [x] What a command prints is unchanged: of 152 recorded runs (every command and flag, on the fixture and a synthetic brain: stdout, stderr, exit code, files left) 147 are byte-identical. The five that differ are the help text, two usage lines (they name `brain chats` and `brain search`, not the script) and the key below
  - [x] Changed on the way, each on purpose: `fetch` JSON gains `path` (with `--dry-run` the text named the file and the JSON did not); JSON keeps letters as written (`Café`, not `Caf\u00e9`), as `log`, `session` and `forget` already did; a `$BRAIN_ROOT` that is a folder but not a brain is refused by every command (most ran on it, and the status line printed nothing); `eval` leaves `BRAIN_CACHE` as it found it; `log.run` is `log.write` and `bench.run` is `bench.measure`
  - [x] Fixed on the way: a crash in the PreCompact hook was never logged. `save_resume.py` imported `note` from the error log and then defined its own `note`, so the handler called the wrong one, which wrote a stray `save_resume/.cache/resume.md` where the session stood. A test holds it now
  - [x] Done when: a caller can use any instrument without parsing text (`commands.call` returns the dict `brain NAME --json` prints, tested on six commands; `brain bench` at 1,000 pages: `recall` 0.139 s to 0.111 s, `check` 0.226 s to 0.171 s, `statusline` 0.104 s to 0.090 s, one process where there were two)
- [x] **13. Tuning per brain** (REFACTOR 2.5, M, waits on D4)
  - [x] One registry of thresholds: name, default, range, what it does (`lib/vault_tuning.py`, 54 of them, in place of the constants and `thresholds()`). `Vault.tuning` holds a brain's values, and no module keeps a number of its own. Left as constants, because the documents state them as rules: salience 4, `summary` at 200 characters, three tags
  - [x] `hippocampus/tuning.md` as a system page: the type, its path, the brain template, `CLAUDE.md`. An override is `- name = value (why)` under `## Overrides`; a brain without the page runs on the defaults
  - [x] The vault reads the overrides; `brain check` fails on an unknown key (naming the closest) or a value out of range, as a schema problem of that page. So the page hook refuses the write that would leave one, too. What cannot be read is not used: the default holds
  - [x] The term cache is keyed by the tuning that changes its rows (the field weights). `TermCache` now needs its key: opened under another, it would read every row as stale and empty the cache, which `brain cache` did until it was given the brain's own
  - [x] `brain introspect --usage` shows default and override, with the range and what the threshold does (`usage.thresholds` in the JSON is now one row a threshold, where it was a bare value); `brain eval --set key=value` tries a value without writing it, the cache included, and never with `--save-baseline`
  - [x] Changed on the way, each on purpose: the results of `introspect` and `check` gain `tuning`, the brain's overrides (`{}` for most), because their text names thresholds and `render` has only the result to read them from; the text is byte-identical for a brain that overrides nothing (26 commands and flags, on the fixture and a synthetic brain, against the engine before the change). `--usage` lists 54 thresholds where it listed 18. `recall --hops` defaults to the brain's `spread_hops`. A weight of 0 leaves a field out of search
  - [x] Done when: a threshold is changed, measured and rolled back without touching `engine/` or restarting (`test_tuning.py`: a line in `tuning.md` moves `introspect`, `recall` and `check` in the next command and removing it moves them back; `eval --set` measures a value on a brain's own questions and leaves no file behind. 393 tests, coverage 100%, `brain eval` at its baseline, `brain bench` unchanged at 1,000 pages)
- [x] **14. Walls: one shared file, one process per event** (REFACTOR 2.6, M)
  - [x] A shared file in `hooks/`, standard library only (`hooks/shared.py`): find the brain, the text an edit would leave, `## Expected` and `status`, and how a wall answers. A wall is now a function of the call that returns nothing, a block or an ask; the five wall files and `check_recall.py` use it, and no hook finds the brain for itself
  - [x] `hooks/gate.py` runs the walls of an event in order (`pre`, `post`); `hooks.json` calls it. Every block is said, in the walls' order, as when each wall was a process of its own. A wall that does not read the tool being called is not loaded: a Bash command costs the senses wall alone, and a write that names no page does not load the library
  - [x] A wall that raises, or cannot be loaded, blocks a write into `senses/` or `cortex/decisions/`, and lets any other through with an error-log line; the other walls still answer. The rule holds for a wall run alone too (before, a wall that raised exited 1 and let everything through). `validate_page.py` and `scan_secrets.py` load the library inside the wall, so a broken library is a wall that raised
  - [x] Each hook file still runs on its own; a test holds the copies left in `lib/` to the same answers (`TheLibraryKeepsItsOwnCopies`: finding the brain, the case of a path, `## Expected` and `status`)
  - [x] Done when: one process before a Write or Edit and one after (six before), and the existing hook tests pass unchanged (they do; 12 added in `test_walls.py`, where the gate is held to the answers, the output and the error-log lines of each wall run alone. `brain bench` at 1,000 pages: the hooks of one write 0.303 s to 0.138 s. 405 tests, coverage 100%)
- [x] **15. `check_recall` reads the end of the transcript** (REFACTOR 2.7, S)
  - [x] Read the last 4 MB, as `save_resume` does, and drop the first line, which is cut
  - [x] A tail with no prompt in it is all one turn: the turn began before the part read
  - [x] Done when: a test with a transcript over the limit passes (a line that is not JSON, placed before the part read, is never parsed)
- [x] **16. `brain index`: the listing is generated** (REFACTOR 2.8, S, waits on D3)
  - [x] Rewrite the listing between two markers: by type, one line a page, its `summary`; a page of no known type is listed last, so none is ever missing
  - [x] Leave `## Gaps` and everything outside the markers alone; an index with no markers is refused with the two lines to add, and a missing one gets the template's
  - [x] Skills stop editing the index (`ingest`, `sleep`, `explore`, `decide`, `maintain`, `forget`, `ask`); `forget.py` calls it, and so does `synth`
  - [x] `CLAUDE.md` and its template state the new rule; the index template carries the markers; `Bash(brain index*)` is allowed
  - [x] Done when: `not_in_index` cannot occur after a run (and an empty brain's index is the template to the letter)
- [ ] **17. A page index in `.cache/`** (REFACTOR 2.9, M, only when measured)
  - [ ] Wait until `Vault()` load passes 0.3 s on the real brain, about 2,500 pages
  - [ ] Parsed page records keyed by path, size and modification time, beside the term cache
  - [ ] Done when: results are the same with and without it, and an unchanged page is not read again

## Phase 3. The brain measures itself

- [x] **18. `brain eval --from-log`** (REFACTOR 3.1, ROADMAP F3, M, after 6)
  - [x] The vault takes a cut-off: only the log lines before a given line (`Vault.as_of(line, today)`: a copy that shares the pages, the links and the search terms, and knows only what the log had taught by then)
  - [x] A case is a recall line that is not a rehearsal, with its question and its pages; a line with no page is an uncovered case. A page gone since is not expected; a line all of whose pages are gone is listed and not replayed
  - [x] Replay each as of its own date; score hit@1, hit@k, mrr and uncovered questions still listed. The first ten misses are printed, `--json` has them all
  - [x] Print the two limits with every result: it shows regression, not absolute quality; pages are as they are now
  - [x] Its baseline is kept beside the brain, in `motor/` (`eval-from-log-baseline.json`); the report says when the pages or the log have changed since it was saved
  - [x] Tests on a synthetic brain, and on a small one where a question finds a page only through the pair an earlier line taught
  - [x] Decided on the way: with no `--root` it replays the log of the brain `brain` is run in, not the fixture's; `--set` works on it, so a value is tried on one's own questions. It refuses `--questions`, `--answers` and `--draft`
  - [x] Its cost: 997 logged questions on 1,000 synthetic pages took 19 s, now 9 s, after the pages each log line names, the pairs it teaches and the link weights were worked out once for all copies (and the pages a search may return, with their lengths, once a Vault). Most of what is left is one search a question over every page, which the synthetic brain's 40 words make dearer than a real one. `brain eval` is at its baseline and `brain bench` unchanged
  - [x] Done when: it runs on the real brain after 4 and its baseline is saved. Run there on 2026-10-10: 5 logged questions that named pages, none that named none. Recall hit@1 0.600, hit@5 0.497, mrr 0.750; search alone 0.200, 0.313, 0.350. Saved to `motor/eval-from-log-baseline.json`. Five questions is a thin baseline: save it again as the log grows
- [x] **19. `brain introspect --gaps`** (REFACTOR 3.2, S, after 6)
  - [x] Recall lines that named no page, grouped by the rare words they share (`Vault.unanswered()`). A word is rare when under 5% of the pages hold it (`rare_word_share`, a threshold like the others); a question with no rare word is known by all its words. A question joins the gap it shares a rare word with, and the gap is then known by the words all its questions share
  - [x] With each group, any held idea or index gap it names
  - [x] Decided on the way: a later question that did name pages closes the gaps all of whose words it holds, or a gap would stay listed for ever. Most asked first, then the one asked last
  - [x] `/reflect` reads it for Thin spots, and names the gap asked most in Next
  - [x] Done when: an uncovered question asked twice shows as one gap (and another wording about the same subject joins it: three questions about one painter are one gap, asked 3 times)
- [x] **20. The calibration checkpoint closes its loop** (REFACTOR 3.3, S, after 13 and 18)
  - [x] `/health`: at the checkpoint, run 18 before and after each `--set` trial (step 5 of the skill: one threshold at a time, the owner's own question set too when there is one, since a replay of the log shows a regression and not quality)
  - [x] Write the value kept to `tuning.md` (on the owner's yes) and log `health calibration -> ...`, whatever came of the review: that line is what stops the briefing asking
  - [x] Done when: the skill text says so and `test_skills.py` passes

## Phase 4. Better recall without a dependency

Gate for every item here: no set of the fixture falls below its baseline, and the target is reached. An item
that misses its target is closed, not shipped.

- [x] **21. Say what the brain never mentions** (REFACTOR 4.1, S; closed by D9, nothing built)
  - [x] Closed, not built: the target (uncovered questions that still get pages from 2 of 6 to 0, covered sets unchanged) is out of this signal's reach, as measured below, and you chose on 2026-10-10 not to print `unseen:` as information either
  - Measured on the fixture on 2026-10-10, nothing built. The two uncovered questions that still get pages hold fewer unseen words than covered questions do. u05 ("Which painters did Picasso learn from?") has one, 0.51 of the question's weight; u06 ("What does a mathematics teacher earn?") one, 0.46. Covered paraphrases have more: p03 three (0.67), p01 three (0.55), p08 two (0.50), p04 two (0.45). A bar that stops u05 and u06 stops those four, and paraphrase recall falls; nothing else about the words tells the two kinds apart (in all of them the best page holds every word the brain has at all). So abstention cannot be tuned on this signal to 0 of 6 with the covered sets unchanged, and by the gate of this phase the item closes. Left to decide: whether to print `unseen:` as information only, for `/ask` to judge by. That wants an answers run (`brain eval --answers`) before and after, because on a paraphrase the line can read as "not covered" when a page does answer
- [x] **22. `answers:`, the questions a page answers** (REFACTOR 4.2, M; its target reached, the one number that fell accepted by D17)
  - [x] Add the field to `FIELDS` (private), the templates and the table in `templates/README.md`. On the episode, concept, entity and insight templates; `brain export` drops it with its lines
  - [x] Schema: a list, at most five, each one short question (at most 120 characters). One `  - question` per line, so a comma or a colon in a question is kept
  - [x] Search it as a field of its own, with its weight in the tuning registry: `weight_answers`, 2.0, what an alias counts, since both are other ways the page is asked for. Recall on the fixture is the same from 0.5 to 3.0, so the value was not fitted. `CACHE_VERSION` is not raised: the weight is part of the cache's key, so rows from before the field are dropped without it (a test holds this)
  - [x] `/ingest` and `/sleep` fill it, in the owner's kind of words: the words they would ask in before knowing the page's terms
  - [x] The fixture's `answers:` are written by an agent that sees the page and not `questions.json` (D10). It was given the 21 page paths and told to open nothing else; it reports opening only those, and that the harness attached the fixture's `CLAUDE.md`, which names `questions.json` and quotes none of it. 75 questions on 21 pages, written into the pages as they came back
  - [x] Done when: paraphrase recall hit@1 is 0.875 or better (0.750 now). 0.875 with the field alone (`brain eval --no-also`); its mrr 0.854 to 0.938
  - What the field alone costs: on the standard set hit@5 went from 0.923 to 0.885. q13, the broad project question, lost `testing-effect` from rank 5 to 6 to pages whose questions say "exam" and "study". The other wordings of 23 bring that number to 0.962, so the two are measured, saved and judged together (below)
- [x] **23. Several wordings, one ranking** (REFACTOR 4.3, S; its target reached, the one number that fell accepted by D17)
  - [x] `brain recall Q --also Q2 --also Q3`, then one spread. Not by reciprocal rank, which was built first and measured: at the usual constant (60) a page's place counts for almost nothing against how many wordings find it, and the `first` set's hit@1 fell from 0.750 to 0.500. In its place each wording is searched and a page's scores are added up, the other wordings sharing one vote: the question as you asked it counts as much as all of them together. With no other wording this is exactly what recall did before, and there is no new number to tune
  - [x] Whether the brain covers the question is judged on the question as asked, never on another wording: with the first version (any wording may pass) recall listed pages for 5 of the 6 uncovered questions; now 2 of 6, as before
  - [x] Eval questions may carry `also`, written by an agent that has not seen the pages (D10): it was given the 37 questions in its prompt and told to open no file; two wordings each, one in the field's terms, one in plain words. Recall is scored with them, since that is how `/ask` asks; `brain eval --no-also` scores it without, and what the wordings buy is the difference
  - [x] `/ask` and the researcher agent always pass two rewordings, with the same instruction the eval's were written under; the MCP `recall` tool takes `also` too
  - [x] Done when: paraphrase hit@5 is 1.000 (0.938 now) and q10 finds `forgetting-curve` (rank 2)
  - Both items together, against the numbers before them (recall, top 5; a new baseline is saved, since the fixture's pages changed):

    | set | hit@1 | hit@5 | all found | mrr |
    |---|---|---|---|---|
    | standard | 0.846 to 0.846 | 0.923 to 0.962 | 12 of 13, same | 0.872 to 0.910 |
    | first | 0.750 to 0.750 | 1.000 to 1.000 | 8 of 8, same | 0.854 to **0.844** |
    | paraphrase | 0.750 to 0.875 | 0.938 to 1.000 | 7 to 8 of 8 | 0.854 to 0.938 |

    Uncovered questions that still get pages: 2 of 6, same. Bytes read when every returned page is opened whole: 3,078 to 4,135 a question (the pages now carry their questions, and two more rows come back); when the section recall names is read first: 1,085 to 809, and every row now names one. Search alone, which no rule here holds to a baseline on that set, puts the right page first on fewer `first` questions (0.625 to 0.375); recall on them is unchanged
  - [x] D17: one number is below where it was. The `first` set's mrr, 0.854 to 0.844, is one question (f07, "What did Rohrer and Taylor find about interleaving?") whose page went from rank 3 to rank 4 once its other wordings were added. The rule at the top of this file says no set may fall. Accepted on 2026-10-10
- [ ] **24. `brain fit senses/FILE`** (REFACTOR 4.4, M; built, waits on real ingests to be measured)
  - [x] The input's own rarest words as the query: the pages it bears on, with summaries, and the held candidates it names (`lib/fit.py`). Of the input's words that some page holds, the twelve that mark it most (`fit_words`: its count in the input times its rarity in the brain) are searched as one question. Rarity alone picked incidental words (`across`, `apart`), so the count weighs in. A held idea is named when every word of its name is in the input; an input already encoded is no source of its own ideas
  - [x] Candidate names made of the same words after stemming count as one candidate in the tally (`same_idea`: `Fluency illusion` and `Illusion of fluency`, `Desirable difficulty` and `difficulties`), under the spelling met first. Two sources naming it so now reach the bar for a concept, where they were two candidates with one source each, paired for sleep to read
  - [x] `/ingest` steps 3 and 5 use it in place of guessed topic words, and the encoder agent with them: it follows that skill. `Bash(brain fit *)` is allowed, as the other read-only commands are
  - [x] The instrument for the measure: `brain introspect --queue` ends with `encoding: N episodes, X links each; H ideas held, T of them named by two sources or more`, also in the JSON
  - [ ] Done when: on real ingests, links per episode and candidates reaching two sources are both up, measured before and after. In the real brain: note the `encoding` line now, ingest the next inputs with the new engine, and read it again. Before, read on 2026-10-10: `encoding: 45 episodes, 4.3 links each; 44 ideas held, 27 of them named by two sources or more`. Nothing has been ingested since: `senses/` and `inbox/` there hold nothing new
- [ ] **25. Use, recency and rank** (REFACTOR 4.5, S, after 18 and 50 logged questions; built and off, waits on those questions in the real brain)
  - [x] Behind a tuning key, off by default: a capped lift from a page's own recall lines, rehearsals left out. `use_lift` (0.0, up to 1.0) is the most a page's recalls add to its score, as a share of it; `use_full` (5) is how many of them earn all of it. Each recall line naming the page counts once, fading by half every `hebbian_half_life` days as a pair does; a rehearsal, a system page and a name that reaches no page count for nothing (`Vault.use_weights`, `lift_from_use`). At 0 every score is what it was, to the last digit. A copy made by `as_of` is lifted by the lines before its own and by none after, so a replayed question is not helped by the line that recorded its answer. `brain recall` prints no new column: the lift moves the score and is not shown
  - [ ] Run 18 with and without it; the fixture must not fall. In the real brain: `brain eval --from-log`, then `brain eval --from-log --set use_lift=0.2`
  - The fixture half, measured on 2026-10-10 (its log holds four questions, so this says little). `--set use_lift=0.2` and `0.5`: every recall number on the three sets is the baseline's, and the same pages are missed. `use_lift=1.0`: the same numbers, another page missed (q04 loses `roediger-karpicke-2006`, q13 finds `testing-effect`). `use_lift=1.0` with `use_full=1`, the largest lift earned by one recall: standard hit@1 0.846 to 0.769 and hit@5 0.962 to 0.923, paraphrase hit@1 0.875 to 0.750. That is the crowding the cap is there for
  - A caution found on the way: a replay of the log leans toward the lift. On a synthetic brain whose 1,000 logged questions have nothing to do with their pages (hit@5 0.003), hit@1 still rose with it: 0.002 off, 0.004 at 0.2, 0.006 at 1.0. The log's answers are the pages that were used, and the lift favours the pages that were used. So a rise in 18 alone should not keep it: your own question set (5) has to hold or rise with it too
  - Its cost: none when off, and the replay takes as long with it on (1,000 questions on 1,000 pages, 15 to 21 s on this machine either way). `brain bench` is unchanged
  - [ ] Keep it or delete it; ARCHITECTURE 6.2 then says what is true. It says now that the lift is there and off
  - [ ] Done when: the decision and its numbers are in the log
- [x] **26. The best section with each row** (REFACTOR 4.6, S)
  - [x] `recall` names the section of each page that matches the question best, in text (`read first: ## Heading (lines 14-18)`) and JSON (`section`: heading, lines, bytes, or null). The words that count are the question's that the page's title and aliases do not hold: a page the question names is its subject and is read from the top, so it gets none. Counting every word chose `## Related` for "What is the forgetting curve?", because the definition does not repeat its own title
  - [x] `brain eval` reports the bytes read when that section is opened in place of the page (`by section`; a page with no section named counts whole). The fixture's baseline is saved again with the two new numbers; nothing else in it moved
  - [x] `/ask` reads those lines first, and the rest of the page only when they do not answer
  - [x] Done when: bytes read per question are under 2,500 (3,078 for whole pages; 1,085 by section on the standard set, 41 of 47 rows naming one). No set moved: the ranking is untouched. What this does not show is whether an answer read from a section is as good as one read from the page: that takes an answers run

## Phase 5. Trust and time

- [x] **27. `brain ground FILE`** (REFACTOR 5.1, M)
  - [x] Every `[[link]]` in a drafted answer or piece resolves (`lib/ground.py`; a page in `dormant/` is a page)
  - [x] Every number and quoted phrase appears on a page cited in its paragraph, or sits in a sentence labelled outside knowledge. A paragraph is a block of lines or one list item. A number the page spells out is on it (`ten` for 10), and so is a date; a quotation is three words or more, matched across the page's line breaks. Not read as claims: headings, code, the text of a link, a count of sources as `brain recall` gives it, a name with a number in it (`SM-2`), and the closing lines `Read:`, `Confidence:`, `Not covered:`
  - [x] List the rest by line; exit 1 when there are any; `--json`. `brain ground -` reads the draft on stdin, for an answer that is in no file
  - [x] `/write` always runs it, `/ask` on long answers, the critic on a run; `Bash(brain ground *)` is allowed
  - [x] Its limit, said in its own text and in `/write`: it reads digits and quotation marks, not meaning. A claim in words alone is not checked, and a sound line can be listed (the page says `a month`, the draft `1 month`): the skill says to tell the owner, not to reword the piece past the check
  - [x] Done when: it flags nothing in the reference answers and catches a planted number in the tests. There were no reference answers: `engine/eval/answers.json` now holds eight, written from the fixture's pages (citation recall and precision 1.0 by `brain eval --answers`, both uncovered questions said to be so). It reads 10 links, 11 numbers and a quotation in them and lists nothing; a planted number, a changed quotation, a wrong page and a page that does not exist are each caught
- [ ] **28. `brain tend --check` and its schedule** (REFACTOR 5.2, ROADMAP F2 steps 1 and 2, S1, A1, M, after 12 and 19; built, the schedule is yours to set)
  - [x] One read-only digest: queues, rehearsals and reminders due, decisions to review, goals at risk, the gaps of 19 (`lib/tend.py`: also the inbox, new input that contradicts a page, decisions whose `revisit if` has come and goals past their date). A line only where something waits, `nothing needs you` when nothing does. A test holds that no file changes outside `.cache/`; `brain tend` without `--check` is refused, so the command has no form that writes
  - [x] A watcher agent: haiku, read-only tools, runs it and reports (`agents/watcher.md`; `Bash(brain tend --check*)` is allowed)
  - [x] A schedule (a Claude Code `/schedule` routine, or cron) that sends you the result. Since 60 there is a command for it: `brain schedule --set`. The README has the cron line and the wording for the agent. A cloud routine cannot read a brain that is only on this machine, so for the real brain it is launchd: set there on 2026-10-10 at 18:34, on your word (`com.aibrain.tend.bea38935`, every 15 minutes)
  - [ ] Done when: leaving the brain alone for a week gives one report and no page changes. The week runs to 2026-10-17
- [x] **29. A read-only MCP server** (REFACTOR 5.3, ROADMAP F12, M, after 12)
  - [x] A stdio server, standard library only, over the calling convention of 12 (`brain mcp`, `lib/mcp_server.py`). The specification moved while this was planned: revision 2026-07-28 dropped the `initialize` handshake, and every request now names its protocol version. Both are served: such a request is answered on its own (`server/discover`, `tools/list`, `tools/call`), and a client that opens with `initialize` (2025-11-25 and earlier) is served that way
  - [x] Four tools: `search`, `recall`, `since`, `gaps`; no tool that writes. Each returns what its `brain` command prints. A test holds that calling all four changes no file outside `.cache/`: no page, no index, no recall line, so a page read this way does not count as used
  - [x] Declared in the plugin, so it starts with it (`engine/.mcp.json`). It starts without a brain too, since the plugin may be enabled in any project, and then offers no tools. Its cost in a brain's own sessions: four tool descriptions in the context, beside `brain` on PATH which does the same
  - [x] Done when: another client lists and calls the four tools. A scripted client does, in `test_mcp.py`, in both eras of the protocol, and is refused cleanly for an unknown tool, a version it does not speak and arguments that do not fit. A real client does too: on 2026-10-10 a Claude Code session that loaded the plugin listed the four tools and called each one, on the empty brain of this folder (`search` and `recall` matched nothing, `since` listed no operation, `gaps` none), and the tree was as it had been. Not tried on a brain with pages, nor from a client other than Claude Code

## Phase 6. Only when the log can judge it

- [ ] **30. Semantic search** (REFACTOR 6.1, ROADMAP F1 and S3, L, waits on D6)
  - [ ] Trigger: after 21 to 23, paraphrase hit@5 is still under 0.9 on 50 or more of your own questions
  - [ ] Decide the embedding source, a local model or an API: the one real decision
  - [ ] Vectors in `.cache/`, keyed by page path and text hash; never committed
  - [ ] `brain search --semantic` blends BM25 and similarity, off when no source is configured; `/ask` passes the flag
  - [ ] Done when: hit@k does not fall on the fixture and rises on your own set
- [ ] **31. Rehearsal intervals fitted to your history** (REFACTOR 6.2, M)
  - [ ] Trigger: the log holds 200 rehearsal lines
  - [ ] Graded answers in `/rehearse`, in place of pass or miss
  - [ ] Intervals fitted per page, in place of the fixed ladder of 1 to 120 days
  - [ ] Done when: replayed over the log, it predicts your misses better than the ladder does
- [ ] **32. Confidence that weighs the kind of source** (REFACTOR 6.3, M)
  - [ ] Trigger: 100 episodes, and your view of what counts
  - [ ] A field on episodes for the kind of source (a study, a post that relays it)
  - [ ] `confidence` reads it; `brain recall` shows why
  - [ ] Done when: two blogs relaying one study no longer read as `medium`
- [ ] **33. A scheduled `/tend` that writes** (REFACTOR 6.4, ROADMAP F2 step 3, M)
  - [ ] Trigger: 28 has run read-only for four weeks, and the critic passed every manual run in that time
  - [ ] It runs the critic and stops on a bad verdict; the verdict is logged
  - [ ] Whatever needs your yes still waits for it: fading, merges, schema pages, salience 4 or more
  - [ ] Done when: a scheduled run leaves a log line, a critic verdict and nothing that needed a yes

## Roadmap items outside the refactor

Not ordered: pick any whose tags are met. Each is smaller once 12 is done.

### Getting material in

- [x] **34. `/capture`** (ROADMAP S4, score 6, S)
  - [x] One line from inside a session to `inbox/<date>-<slug>.md`; `/ingest` already sweeps `inbox/`. The skill runs `brain capture "<the line>"` (`lib/capture.py`), which writes the owner's words as given, never over a note that is there, and refuses a line holding a credential. `Bash(brain capture *)` is allowed, so it does not stop the work it interrupts
  - [x] Decided: capturing writes no log line. A note in `inbox/` is no memory yet; `/ingest` logs it when it is encoded. `test_skills.py` exempts it by name, with `commit`, `start` and `tend`
  - [x] Done when: a captured line shows in the briefing's inbox count (and in the status line)
- [ ] **35. Low-friction capture, one door** (ROADMAP F4, score 7, M)
  - [x] Name the one concrete door first (the roadmap does not name one). D12: a folder that a sync service keeps on this machine and on the phone
  - [x] Build that door only, into `inbox/`. `brain door FOLDER` (`lib/door.py`) opens it; the door is the link `inbox/.door`, which git ignores, so nothing about this machine is committed and a second machine opens its own. The session briefing moves what waits there into `inbox/` before it counts the inbox (`brain door --pull` by hand; `brain door` alone looks and moves nothing; `--close` closes it and leaves the folder alone). Moved, not copied, and never over a note that is there. Folders and a `README.md` stay at the door and are named; half-written files (`.tmp`, `.part`, `.icloud`, `.crdownload`) are passed over; a file that cannot be moved yet waits for the next time. A door whose folder cannot be read says so and the briefing still comes. No log line, as with `brain capture`
  - Not on the allow-list: opening a door decides which folder of yours gets emptied into the brain, so it asks
  - [ ] Done when: a note taken away from the desk is in `inbox/` at the next session. Tested with a folder standing in for the synced one (`tests/test_door.py`, 7 tests: saved at the door, in `inbox/` after the briefing, gone from the door). With a real sync service it is yours: `brain door "<your synced folder>"`, save one note from the phone, start a session. Looked at on 2026-10-10: this machine has iCloud Drive and no Dropbox, Google Drive or OneDrive folder, and the one phone it mounts is an Android (through MacDroid), which iCloud Drive does not reach. So no folder here syncs with the phone yet: which service is yours to pick and install
- [x] **36. Importers, one per source** (ROADMAP F7, score 5, M each)
  - [x] An Obsidian vault first: it is already Markdown. `brain import obsidian VAULT [--dry-run]` (`lib/importer.py`; `import` is a Python keyword, so the module has the longer name). `SOURCES` there holds one importer; a second source is one more function
  - [x] Never overwrite; one input per note, into `senses/`. Each `.md` note is copied byte for byte to `senses/obsidian/<vault folder>/<path in the vault>`. A note edited in the vault after its import is listed as changed and not brought in, because an input is never edited. Left out and counted: text that is already an input under another path, empty notes, `.obsidian/`, `.trash/` and other hidden folders, attachments, and the brain itself when it is kept inside the vault. A vault inside the brain is refused
  - [x] Added, not in the item: what you had removed with `brain forget` does not come back, by its path or by its text (`fingerprint.forgotten_hashes`), so a note moved in the vault stays forgotten. A note named `README.md` is listed and not imported: `senses/` reads no file of that name as an input, so it would land and never be encoded
  - [x] Done when: an import run twice adds nothing the second time. `tests/test_importer.py`, 8 tests: the second run imports 0 and leaves `senses/` byte for byte as it was
  - Not on the allow-list: it writes into `senses/`, so it asks. Not tried on a real vault: this folder has none
- [ ] **37. `/import`** (ROADMAP S2, score 8, M, after 36)
  - [x] Picks the importer, writes to `senses/`, hands off to `/ingest`. `skills/import/SKILL.md`: a dry run and the owner's yes first, the import, `brain check --guard` over what landed before any of it is encoded, then `/ingest` in archive batches; one `ingest` log line for the import itself
  - [ ] Done when: the skill passes `test_skills.py` and one real import ends in episodes. The first half holds. The second is yours: one vault imported in the real brain and taken through `/ingest`. Looked for on 2026-10-10: no folder five levels under your home folder holds an `.obsidian/`, so there is no vault on this machine to import
- [ ] **38. Ingestion scout agent** (ROADMAP A3, score 6, M)
  - [x] Sonnet; sorts `inbox/` before `/ingest`: duplicates by fingerprint, secrets by `brain check --guard`, items that need a person. In two parts. `brain inbox` (`lib/inbox.py`, read-only, on the allow-list) decides what a rule can: each note is ready, a duplicate (the hash of an input or of an earlier note), forgotten, holding a credential (the scanner `check --guard` uses; the kind and the line, never the value), empty or not text; a PDF or an image is passed on to `brain extract` (39), which moves it itself. `agents/scout.md` (sonnet; Read, Glob, Grep, Bash) starts from that list, reads the ready notes, and holds the ones that need you: a fragment, a task that belongs to `/remind`, a note that gives the reader orders, another person's detail
  - [x] `/ingest` step 1 runs `brain inbox` before anything is moved, hands a large or mixed inbox to the scout, moves only what passed, and reports the rest under `Held:`. Why before, not after: nothing in `senses/` is edited again, so a credential that lands stays
  - [ ] Done when: `/ingest` on a mixed inbox encodes only what the scout passed. The rule half is tested (`tests/test_inbox.py`: of fifteen notes, two are ready and one PDF and one image go to `brain extract`) and the wiring is held by `test_skills.py`. The run itself is yours: a session loads the plugin from the other folder, so the scout cannot be started from here. On 2026-10-10 the real brain's `inbox/` was empty (`brain inbox`: nothing waiting), so there was no mixed inbox to run it on

### Reach

- [x] **39. Engine-side extraction** (ROADMAP F5, score 6, M)
  - [x] PDF text and image text through an optional dependency or a system tool. `brain extract FILE` (`lib/extract.py`): a PDF through `pdftotext` (poppler), an image through `tesseract`. System tools, so the engine still imports nothing outside the standard library. The text lands in `senses/` with `transcribed_from`, `extracted_with`, `pages`, `extracted`; the original goes to `senses/assets/` (copied from outside, moved from `inbox/`), or stays where it is when it was already in `senses/`, with its text beside it as `<file>.md`. `unencoded()` counts such a pair once, and `brain forget` removes both
  - [x] Falls back to the model when the tool is absent: exit 1 with the reason and nothing written; the PDF and Image rows of `/ingest` say what the model does then. The same exit for a scan (under 8 words a page), text the tool could not decode, a file it cannot open, and a file extracted before
  - [x] Done when: a PDF lands in `senses/` as text without the model reading the file. Tried here with the real `pdftotext` 26.08 on a two-page PDF: 56 words landed and the PDF moved from `inbox/` to `senses/assets/`. The tests use stand-ins for both tools, so CI needs neither (`tests/test_extract.py`, 10 tests). `tesseract` is not on this machine: the image path has run against the stand-in only
  - Not on the allow-list: it writes into `senses/`, as `brain fetch` does
- [ ] **40. Audio and video transcription** (ROADMAP F6, score 6, M, after 35; D13: not now)
  - [ ] An external tool or an API
  - [ ] The transcript lands in `senses/` as text, with its source named
  - [ ] Done when: a recording becomes an input `/ingest` can encode
- [ ] **41. `/transcribe`** (ROADMAP S5, score 6, S, after 40; D13: not now)
  - [ ] The front for 40
  - [ ] Done when: the skill passes `test_skills.py`

### Hygiene

- [x] **42. `/restore`** (ROADMAP S8, score 4, S)
  - [x] Log it, move the page back from `dormant/`, put it in the index. `brain restore NAME` (`lib/restore.py`) does the three in that order: the `maintain restore` line first, then the file to the folder of its type, then `brain index`. The page is not edited. It refuses a name no faded page has, one two have, a page already in `cortex/` under that name, and a type with no folder; `--dry-run` shows the move. It is not on the allow-list: moving a page asks
  - [x] The skill finds the page, shows the move, restores it, and asks what will link it, since a page nothing uses fades again
  - [x] Done when: `brain check` no longer lists links to it as faded
- [x] **43. `/export`** (ROADMAP S9, score 4, S)
  - [x] A wrapper for `brain export`, with `/guard` run first: choose, guard, export, log `guard export`
  - [x] The refusal is the command's, not the skill's: `brain export` now scans the chosen pages, stops on a credential (file, kind and line, never the value) and writes nothing; personal data in what was exported is listed for the owner (`personal` in the JSON)
  - [x] Done when: an export with a credential in a chosen page is refused
- [x] **44. Contradiction resolver agent** (ROADMAP A2, score 7, S)
  - [x] Prepares each side of a `disputed` page for `/maintain settle`: sources, dates, strength. `agents/resolver.md` (inherit): each claim quoted, the records behind it (two episodes of one address are one source), which side is stronger on the records alone, and what would settle it
  - [x] It does not settle: its tools are Read, Glob, Grep and Bash, and `test_skills.py` holds that only the encoder and the consolidator can write
  - [x] Done when: `/maintain settle` reads its output and the page is unchanged until your word. Settle now hands the page to the resolver first and puts its report to you before anything changes. Not run on a real dispute: this brain has no disputed page, and the plugin a session loads here is the other folder's
- [x] **45. Privacy gatekeeper agent** (ROADMAP A5, score 4, S)
  - [x] A clean-context pass of `/guard` before any export; the critic already covers part of this. `agents/gatekeeper.md` (inherit, the `guard` skill preloaded): `brain check --guard`, each chosen page read whole, the titles that would leave through links; it answers `VERDICT: clear | stop` and exports nothing
  - [x] Done when: 43 calls it. `/export` step 2 hands the chosen pages to it and stops on `stop`. `brain export` still refuses a credential on its own (item 43), so the agent is the second reader, not the only wall

### Recall and review

- [x] **46. `/brief`** (ROADMAP S6, score 5, S)
  - [x] A short cited summary of one person, project or topic: `/ask` with a fixed format. `skills/brief/SKILL.md`: recall, the brief in one fixed shape, then `brain ground -` over it before it is shown
  - [x] It logs its recall line: `brain log recall "brief <subject>" --pages ...`; `brief` is in `check_recall.RECALL_SKILLS`, so the Stop hook asks for the line when it is missing
  - [x] Done when: the skill passes `test_skills.py`
- [x] **47. `/review-decision`** (ROADMAP S7, score 5, S)
  - [x] The review step split out of `/decide`, so it can be run or scheduled alone. `skills/review-decision/SKILL.md` holds it; `/sleep`, `/start` and `brain tend --check` point at the new name, and CLAUDE.md names both new skills among those that write a recall line
  - [x] Done when: `/decide` is shorter and both skills pass `test_skills.py`. `/decide` went from 110 lines to 91; the review is 61 lines of its own
- [ ] **48. Quiz writer agent** (ROADMAP A4, score 5, S; D14: kept open until you have rehearsed enough to say)
  - [ ] Only if quizzes feel thin: `/rehearse` already builds its own
  - [ ] Done when: you say the questions are better with it than without
- [x] **49. Writer or editor agent for `/write`** (ROADMAP A6, score 3, S, closed by D11)
  - [x] Closed, not built: `/write` drafts in the main session as before, and the encoder and the consolidator stay the only agents that can write

### Platform

- [x] **50. Time of day in log lines** (ROADMAP F9, score 4, S, after 6)
  - [x] An optional `HH:MM` after the date, written by `brain log`: `2026-10-10 09:39 recall a question -> [[page]]`. `CLAUDE.md` > Log states the format; the examples in `templates/README.md` carry a time
  - [x] Check every parser that assumes `LOG_LINE` in `vault_model.py`: the events (`time`, `""` on a line without one), the briefing's last activity, the recall sensor (a literal line in an edit, and a line a shell built with today's date), and what `brain check` and `eval --from-log` reprint, which is now the line as it was written. A time that is none (`25:99`) is not read as one: the line is listed as an unknown operation
  - [x] Events are read in the order they happened, by date and then time: a line with no time comes before the timed ones of its day, and keeps the file's order. So a log merged from two copies of a brain reads right, and a rehearsal's rows are in the order of the day, where a miss was always put before a pass
  - [x] Done when: two operations on one day sort by time, and old lines still parse (`TimeOfDay` in `test_log.py`; the fixture's and every test's untimed logs read as before)
- [x] **51. Visual interface** (ROADMAP F8, score 5, L)
  - [x] A static HTML graph from `brain graph`; no server. `brain graph --format html` fills `templates/graph.html` and writes `motor/graph/graph.html`: one file with its own styles and script. Pages are marks (the hue is the stage of memory: sources, memory, purpose; the shape is the type, so no two types differ by colour alone), sized by their links; a search, the types as switches, a page's summary and links on selection, pan and zoom, and the same pages as a table. The layout is computed in the browser and comes out the same every time. Light and dark, and no animation for a reader who asked for none
  - [x] Done when: the file opens from `motor/graph/` with no network. Its own policy (`default-src 'none'`) refuses every request, and a test holds that it names no address. Opened in headless Chrome with name lookups blocked, on the fixture (21 pages) and a synthetic brain (300 pages, 760 links): the only request was the file, and the script threw nothing through a search, a selection, a followed link, a drag, a zoom, a type switched off, the table and both themes
  - The file holds every page's title and summary: it is the brain in one file. `motor/graph/` is already ignored by git
- [x] **52. Backup and sync** (ROADMAP F10, score 4, S)
  - [x] Document a git remote; `git push` stays denied to a session on purpose (README > Backup and a second machine: a private remote, pushed by the owner; clone, `./install.sh`, `brain check` on the other machine)
  - [x] Added for the second machine: `.gitattributes` merges the three append-only files by union, so lines both copies added are both kept, with no conflict; with 50 the log then reads in the order things happened. `install.sh --new` now gives a new brain this file and `.gitignore`, which it did not (its `.cache/` was not ignored)
  - [x] Done when: the README says how, and a second clone passes `brain check` (a test makes two copies of a brain log on the same day, merges them and runs `brain check`; CI runs it on a fresh clone at every push)
- [ ] **53. Windows support** (ROADMAP F13, score 4, M). Skipped on your word, 2026-10-10: not built
  - [ ] Paths, the `python3` name, symlinks
  - [ ] Done when: `brain test` passes on Windows in CI
- [x] **54. `/share`** (ROADMAP S10, score 3, M, closed by D15)
  - [x] Decided, and no skill built: a read-only view for another person is what is there already. `/export` gives clean copies of chosen pages once the gatekeeper has read them; `brain mcp` gives a program read-only access. A second way out would be a second place for a leak
- [x] **55. Encryption at rest** (ROADMAP F11, score 3, M, closed by D16)
  - [x] Decided no, and F11 is off the roadmap: the pages stay plain Markdown, which search needs. The disk's own encryption covers this machine and a private remote covers the pushed copy
- [x] **56. Run the OpenCode plugin in OpenCode** (ROADMAP P2, S, closed by D5)
  - [x] Closed, not built: D5 removed OpenCode from both documents on 2026-10-09, and P2 from the roadmap. Other hosts are 29

### Remembering to do

Taken from the "synthetic brain" notes (`thoughts.md`) by D18. Today a reminder is one line, `- <what> when <date or event>`:
a date is shown in the briefing once it has come, an event is compared with each new input by the model.
Each item keeps the rules: the line in `hippocampus/intentions.md` and the log are the record, nothing else is stored.

- [x] **57. Reminders with a time and a repeat** (ROADMAP F14, score 6, S, after 50)
  - [x] `when` takes a time after the date (`2026-10-11 10:00`): due from that minute. A date alone is due from the start of its day, as before. The Vault has a clock for this (`Vault.now`: the machine's, or one handed in; a Vault given only its day stands at that day's last minute, so every test and replay reads as it did)
  - [x] `when` takes a repeat: `every day`, `every monday` (any weekday), `every month` (its first day), each with a time or without. A repeat is not closed by `(done)`: it is counted from the last `remind` log line that names it in the words of the line, its adding or the last time it was done, and is due at the first round after that. One the log never names was never done, and its latest round is due. `(dropped)` ends it. Nothing new is stored: the line and the log are the record
  - [x] The grammar is one small module, `lib/vault_intentions.py` (no dependencies). A `when` that starts as a day or a repeat and cannot be read as one (`2026-02-30`, `2026-10-03 25:00`, `every fortnight`) would wait for ever as an event nothing reports, so it is a problem of the page: `brain check` fails on it and the page hook refuses the write, as for a bad line of `tuning.md`. So an event cannot start with `every`; the refusal says to write it another way
  - [x] Every reader takes both: the briefing, `brain tend --check` and the status line through `due_intentions`; `brain introspect --remind` also lists the repeats with their next round, and says since when a repeat has been due. The `/remind` skill and the template of `intentions.md` say how to write them
  - [x] Done when: a timed reminder is not due a minute before its time, a weekly one is due again a week after it was done, and the lines written before read as they did (`tests/test_learning.py`, `Intentions`)
  - Not done here: a reminder with a time is still only seen when something looks, at the next session or the next `brain tend --check`. Showing it at its minute with no session open is 60
- [x] **58. `brain fit` names the reminders and decisions an input bears on** (ROADMAP F15, score 7, S to M)
  - [x] After the pages and held ideas it lists now: every event the brain waits on, a reminder written `when <event>` and the `revisit_if` of each decision in force. One the input holds `trigger_coverage` (0.6) of the words of is marked `*` and comes first, with the words it holds; each word is weighed by its rarity, as search weighs it, so `a rival cuts prices` is not marked for an input that only names prices (`lib/fit.py`: `reached`, `waiting`; `triggers` in the JSON)
  - [x] Changed from the plan: it lists all of them, not only the marked ones. An input can report an event in other words, which no count of words sees; had the list held the marked ones alone, `/ingest` would have stopped reading the others and missed those. The unmarked ones are cut at `--limit`, the marked never
  - [x] Left out: a reminder on a date (the briefing has it), a closed one, a decision tagged `to-revisit` (its event has come), one not decided yet, and one with no `revisit_if`
  - [x] `/ingest` reads that list in place of running `brain introspect --decisions` and `--remind` and comparing by eye; `Triggers:` in its report starts from it, and the model still says what the input reports. `/remind` says to write an event in the words a source would use
  - [x] Its limit, said in its own text: the mark is where to look, never the verdict
  - [x] Done when: of two inputs, one reporting a reminder's event and one not, only the first lists it. Both list it, by the change above; only the first marks it (`tests/test_scripts.py`, `Fit`: of three reminders and a decision, the two whose words the input holds are marked, one that holds half is not until `trigger_coverage` is 0.5)
- [x] **59. A reminder closes with its date and what happened** (ROADMAP F16, score 5, S)
  - [x] `(done 2026-10-12: the setup was confirmed)` and `(dropped 2026-10-12: no longer needed)`; a bare `(done)` still closes a line. Goals end with the same mark, so a goal may carry its day too
  - [x] `brain introspect --remind` says, of the reminders closed: how many were done and how many dropped, and for the ones done that give their day and had a date, how many days after it (the middle one and the latest). One closed on its day or before it is 0 days late. `closed` in the JSON
  - [x] `/remind` asks for the one line when it closes a reminder
  - [x] Done when: a reminder closed three days late shows as three days late, and one closed bare is counted with no lateness
  - Not counted: how late each round of a repeat was done. The log has it (the `remind done` lines against the rounds); nothing reads it yet
- [ ] **60. A schedule that needs no session** (ROADMAP F17, score 7, M, after 28; built, setting it on your machine is yours)
  - [x] One command sets it and one removes it: `brain schedule --set [--minutes N]`, `brain schedule --remove`, and `brain schedule` alone says what is set (`lib/schedule.py`). On macOS it is a launchd job of your own user, one for each brain, started at login; elsewhere nothing is installed and the cron line that does the same is printed. A job launchd will not start is not left behind
  - [x] What it runs is `brain tend --check --notify`. Changed from the plan, which had one run a day: it runs every 15 minutes, since a reminder with a time (57) is of no use shown the next morning. So that it does not say the same thing 96 times a day, each thing is said once a day: the day's first run shows everything that waits in one notification, a later run only a reminder that has come due since. What was said today is in `.cache/notified.json`, which is not the brain's record: lose it and the day's line is said once more
  - [x] It shows a notification through `osascript` on macOS, or `notify-send` where there is one; `mail` is not needed. When nothing waits it shows none
  - [x] Not on the allow-list: it installs a job on this machine, so it asks. It writes nothing in the brain: the plist is in `~/Library/LaunchAgents`, its output and what it has said in `.cache/`
  - [x] Its limit, said in its own text: a machine that is asleep runs it on waking, so a reminder for 10:00 can be shown later. With 59 the lateness is on record
  - [ ] Done when: with no session open, a reminder whose time has come is shown on the screen, and a week left alone changes no page. Tested with stand-ins for `launchctl`, `osascript` and `notify-send` (`tests/test_schedule.py`): the job is written, started, replaced and removed, and the lines shown are the right ones. Set in the real brain on 2026-10-10: the job is loaded, and its first run at 18:34 ended without an error, said that one kind of thing waits on you (7 pages due to rehearse), wrote `.cache/notified.json` and changed no page. Not seen from the session: whether the notification showed on your screen. Open: a reminder with a time shown with no session open, and the week, to 2026-10-17
- [x] **61. What waits, as a fifth MCP tool** (ROADMAP F18, score 4, S, after 29)
  - [x] `waiting`: what `brain tend --check` prints, as it prints it, read-only as the other four (`lib/mcp_server.py`). It takes no argument. Its description says what it is for: a program that acts on a schedule asks it to learn what is due, and doing it stays with the owner
  - [x] Done when: a client lists five tools, `waiting` returns that digest, and the test that calling every tool changes no file holds for it too (`tests/test_mcp.py`, the scripted client). Not yet called from a real client: a session's server keeps the tools it started with, so Claude Code lists five from its next session on

### What matters

Taken from the notes on emotions and personality (`emotions.md`, `personality.md`) by D20. `salience` is the brain's one
mark of how much something matters, and the notes' own rule for it is the one kept: it moves attention, never what is
held true. Found while reading them, on 2026-10-10: `/ingest` writes a salience of 1 to 3 on the episode, and the engine
read it only where episodes are left out (the order of rehearsal, the time a page takes to fade), so it changed nothing.
In the real brain 32 of 45 episodes carry one and none of the 12 other pages does.

- [x] **62. Salience reaches the pages built on an episode** (ROADMAP F19, score 7, S)
  - [x] `Vault.salience_of(page)`: the mark a page carries, or for a concept, entity or insight the highest among the records it rests on (`evidence_for`) and the ones that say the opposite of it, since a contradiction is one of the reasons an input is marked. An `/explore` episode gives none. Worked out when asked and never stored; an episode or a decision keeps its own
  - [x] Never above 3 this way. From 4 up a page never fades, and that stays with the page that carries the field (`Page.protected` is unchanged): an episode marked 5 lifts a page it names to 3, so that page fades after 450 unused days where an unmarked one fades after 180. The concept sleep makes from such an episode is given the mark itself (D22)
  - [x] The two places that read a mark of 1 to 3 now read this: the order of rehearsal (`due_for_rehearsal`) and the time to fade (`fade_days`). The bar for a concept and what `brain forget` leaves standing still read the episode's own mark
  - [x] Changed on purpose: the order of `brain introspect --due` and what `--dormant` proposes, in a brain whose episodes are marked. In the real brain all 12 built pages now take a mark (2 or 3), where none had one
  - [x] Done when: a concept behind a marked episode is rehearsed before an unmarked one and fades later, and one behind an `/explore` episode does neither (`tests/test_learning.py`, `Salience`). `brain bench` at 1,000 pages: `introspect --due` 0.296 s to 0.304 s, as the other commands moved
- [x] **63. `brain fit` gives the reasons for a salience** (ROADMAP F20, score 6, S)
  - [x] Of the three reasons `/ingest` may mark an input 1 to 3 for, two are now marked on the pages `brain fit` lists: `[established]`, a concept two sources stand behind, which an input can say the opposite of; and `serves:`, the live goals and projects that depend on the page, each by name (`Vault.serving()`, which `purpose()` is now read from; `status` and `serves` in the JSON). High stakes is still read
  - [x] One line under the pages says what the marks are for, and only when there is one. A mark is where to look: a page listed for sharing the input's words is no reason until the input is about it
  - [x] `/ingest` step 3 takes the reason from those marks and names the goal or the page in `Salience:`; it says that a mark given to every input tells nothing
  - [x] `brain introspect --salience` shows the spread: episodes by level, and of the pages built on them how many carry a mark and how many take one. Then the episodes marked 1 to 3 for no reason the pages show: no page a live goal depends on, nothing contradicted, so high stakes or a goal since closed (`salience` in the JSON, and in the whole report)
  - [x] Done when: of the pages an input reaches, the one a goal names is marked with that goal and the others are not (`tests/test_scripts.py`, `Fit`)
  - What it shows in the real brain: 32 of 45 episodes marked (1: 1, 2: 19, 3: 12), and none of the 32 without a reason: each links a page one of the eight goals depends on. So the reason holds for nearly every input, and the level, which no rule set, is what tells them apart. D21: the level is now how many of the three reasons hold, said in `/ingest` step 3 and in the field table
- [x] **64. Salience is asked about again** (ROADMAP F21, score 5, S, after 62)
  - [x] `brain introspect --salience` ends with the pages that carry 4 or more, which never fade, that no live goal or project reaches (the page, or one it links) and that nothing has recalled or edited for `dormant_days`: the longest first, each with its day
  - [x] `/reflect` step 3 asks of each whether it still matters. Yes: a `Rechecked` line and `updated:`, which takes it off the list for another `dormant_days`, as for a stale concept. No: the mark is lowered or removed, as the owner says. Nothing lowers one by itself
  - [x] Done when: a page marked 5 for a goal that is over is listed, and one a live goal reaches, or edited last month, is not (`tests/test_learning.py`, `Salience`). The real brain has none: no page there carries 4 or 5
- [x] **65. A contradicted page names what contradicts it** (ROADMAP F22, score 6, S)
  - [x] A recall row has `against`: the pages whose typed link says they contradict it, whether or not they are among the rows. The flag alone left the other side to chance: at `--limit 1` the row came back `contradicted` and the two episodes that said so did not
  - [x] In the text, one line under such a row: `the opposite is said by: <pages>`. The MCP `recall` tool returns that text, so another host sees it too
  - [x] `/ask` step 3 reads those pages and gives both positions with their sources; `/brief` says the same
  - [x] Changed on purpose: one more key on every recall row (`tests/test_commands.py` pins it)
  - [x] Done when: recall cut to one row still names both pages that contradict it (`tests/test_retrieval.py`). Recall on the fixture is at its baseline on every set: the ranking is untouched
  - Checked for 62 to 65 together: 512 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` and `brain errors` clean
- [ ] **66. A source's track record** (ROADMAP F23, score 5, M; the first step of 32, and waits on its trigger)
  - [ ] Trigger: 100 episodes, as for 32. At 45 the counts are of one or two episodes a source
  - [ ] For each author or site, from the pages alone: its episodes, the claims of its that a second independent source also makes, and the ones another record contradicts. Computed when asked, never stored; no new field
  - [ ] Kept apart, as the notes ask: what a source got right says nothing of what it meant, and the view counts claims only
  - [ ] Done when: `brain introspect` lists the sources by how their claims fared, and 32 reads it

### Feelings and character

Taken by D23. A feeling here is a reading of the record, never a state that is kept: an event in the log or a standing
state of the pages is appraised by a rule, counts for its weight, and fades by half every few days. So every feeling
names its causes, a log rolled back takes its feelings with it, and none can be written into being. Two rules hold for
every item: a feeling moves attention and never what is held true (`confidence` is from the evidence only), and no
feeling or trait changes what a wall refuses. It is a model of affect; it says nothing about experience.

- [x] **67. Feelings from the record** (ROADMAP F24, score 6, M)
  - [x] `lib/vault_affect.py`, a fifth part of the Vault. `appraisals()` reads the record by rule: each event of the log and each state of the pages that stands today gives one feeling toward one target, with its day and its cause. `feelings()` adds them up. Only the pages and the log are read
  - [x] Five feelings. Surprise: new input says the opposite of a page; a reviewed decision turned out better, worse or mixed. Frustration: a rehearsal missed; a question asked again and still unanswered; a decision that turned out worse; a reminder done after its day. Curiosity: a question no page answers, each time it is asked. Satisfaction: a rehearsal passed; a decision as expected or better; a reminder done by its day. Worry: a goal at risk or past its date; a decision past its review; a reminder due
  - [x] How strong: an event counts for one and fades by half every `feeling_half_life` days (7); a state that stands counts one more for each of them it has stood, so what is left undone grows as fast as what is over fades. `feeling_full` (3) fresh events of one kind toward one target are the feeling at its strongest, 1.00; under `feeling_floor` (0.1) it has faded and is not listed. Three thresholds in the registry, so a brain may hold its own
  - [x] `brain feel [WORD ...] [--limit N]`: the feelings, strongest first, each with its causes and their days; WORD keeps the targets that hold it, or the page it names. A target is a page, a goal, a reminder, or the words an unanswered question is known by. Read-only and on the allow-list; no log line
  - [x] Changed from what was put to you, each on purpose. An idea one source names raises no curiosity: every ingest holds two or three, so the feeling would follow how much was read and not what was asked. A logged error raises no frustration: the error log is in `.cache/`, which is no record, and losing it would change a feeling with nothing having happened. A reminder dropped raises none: dropping is a choice. Trust in a source is 66
  - [x] `Vault.open_gaps()` is split out of `unanswered()`, which reads as before: a gap with the day of each asking
  - [x] Held by a test: a brain that feels everything in full and one that feels almost nothing give every page the same confidence and rank recall the same. Another: it writes nothing, and a log rolled back takes its feelings with it
  - [x] Done when: each rule is read from a brain that holds its case, with its cause and its strength, and the ones that should give nothing give nothing (`tests/test_affect.py`, 6 tests). 518 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean. At 1,000 synthetic pages `brain feel` takes 0.30 s, as plain `introspect` does
  - What it reads in the real brain today: two feelings, both surprise at about 0.3, toward the two pages new input contradicted. Nothing else: it has 5 recall lines, no rehearsal, no decision and no reminder
  - Not yet: nothing reads a feeling. It orders no list anywhere until 68, so this item changes what can be seen and not what the brain does
- [x] **68. Mood, and where a feeling moves attention** (ROADMAP F25, score 6, M, after 67)
  - [x] Mood (`Vault.mood()`): the appraisals of 67 fading over `mood_half_life` (30 days) in place of 7, added up across every target. One target counts for one at most, so an amount reads as how many things are felt that way in full. It leans from -1 to 1, what was done well against what was missed or is overdue, and has a word: `quiet`, `curious` (only questions and surprises), `content` or `uneasy` (it leans by `mood_lean`, a third, or more), `even` between. `brain feel` prints it first, and has it in the JSON
  - [x] One line in the briefing, only when something is felt now: `Mood: uneasy (30 days: worry 3.0, curiosity 0.5) | most felt: worry 1.00, Move: 17 days past its date`. A brain with nothing to feel opens as it did
  - [x] `brain tend --check` puts first the list the record gives most to feel about, and ends that line with the feeling, how strong and its cause: `[worry 0.81: Move, 10 days past its date]`. Of the feelings that ask for something: satisfaction orders nothing. Every list is still printed; the ones nothing is felt about follow in their old order (`felt` in the JSON). The day's notification names the lists in the same order, and so does the MCP `waiting` tool, which returns this text
  - [x] `/feel <subject>` (`skills/feel/SKILL.md`): how a project, a goal or a page sits in the record, each feeling with its causes and what would change it, from the rule that raised it. Its core rule: it is the record's reading, never the owner's state of mind, and no way is offered to lower a feeling that leaves its cause standing. It writes a recall line, so it is named among the skills that do (`CLAUDE.md` > Log, `check_recall`)
  - [x] `/reflect` step 7: of two next actions otherwise equal, the one more is felt about comes first, with its cause; a feeling adds none and drops none
  - [x] Not changed: the order of rehearsal. It has its own rule (goals, salience, misses, how overdue), and `/rehearse` is the owner's alone
  - [x] Done when: of two things waiting, the one the record gives more to feel about comes first (`tests/test_scripts.py`, `TendCheck`: a goal ten days past its date before an input not yet encoded; with nothing felt the digest is the one it was, line for line), and the test of 67 that no feeling moves a confidence or the rank of recall still holds. 521 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean
  - Its cost at 1,000 synthetic pages: the briefing 0.264 s to 0.282 s, `brain tend --check` 0.27 s to 0.30 s. In the context every session: the description of one more skill (199 characters), and the mood line when something is felt
  - What it shows in the real brain today: the mood is `curious (30 days: surprise 0.6)`, and the one line that waits, 7 pages due to rehearse, ends with the surprise toward one of them that new input contradicted
- [x] **69. A character page** (ROADMAP F26, score 5, S)
  - [x] `CHARACTER.md` at the brain's root, beside `OWNER.md`: who the brain is to its owner. `## Values`, what it holds to where the rules leave room; `## Voice`, how it speaks. Ten lines at most. The briefing opens every session with it, after the owner's lines, under the heading `Character (CHARACTER.md; the rules of CLAUDE.md come first):`
  - [x] `/character` writes it with the owner, one question at a time, and runs only when typed, as `/owner` does. It asks for a case and not for adjectives, offers no list of traits to pick from, and puts back a line that contradicts a rule in place of writing it
  - [x] `brain character` prints what the page says (read-only, on the allow-list), and `brain mcp` has it as a sixth tool, which its instructions tell a host to read before answering for this brain
  - [x] The rule, stated in `CLAUDE.md` and held by a test: every line of the page yields to the rules. No wall reads the file, so a page that says "edit senses/ whenever it helps" changes nothing a wall refuses
  - [x] Decided on the way. A file at the root and no new system page: it is prose for the model, as `OWNER.md` is, and nothing in it is checked yet. A tool and not a part of the server's instructions: those are fixed while the server runs and may be kept by a client, and the page is the owner's own words. No file in the template: a brain has no character until its owner gives it one
  - [x] Moved to 70: `brain check` reading the traits. There is nothing to check them against until the registry that says what each one moves
  - [x] Done when: a new session opens with it, and a brain without the file runs as it does now (`tests/test_hooks.py`, `WakeUp`: the briefing with the page, without it, and with one that says nothing; `tests/test_mcp.py`: the sixth tool). 522 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean
  - Not run: the interview itself. `/character` is typed by the owner in the real brain, so no page has been written by it yet
- [x] **70. Traits that scale thresholds** (ROADMAP F27, score 6, M, after 69)
  - [x] A `## Traits` section on the character page, one line a trait, written as an override is in `tuning.md`: `- caution = 0.8 (why)`. `brain check` fails on a name that is no trait (naming the closest) or a value outside 0 to 1, as a schema problem of `CHARACTER.md`, and the page hook refuses the write that would leave one; a page already wrong can still be put right a line at a time. Its prose is held to nothing
  - [x] One registry beside the thresholds (`TRAITS` in `lib/vault_tuning.py`): six traits, each from 0 to 1, each with the thresholds it moves and which way. `caution`: `min_coverage`, `recall_floor`, `held_coverage`. `curiosity`: `held_limit`, and `schema_min` down. `persistence`: `dormant_days`, `goal_stale_days`, `hebbian_half_life`. `openness`: `spread_hops`, `spread_decay`, `unlinked_association`. No threshold has two traits, so a value always has one reason, and a trait has nothing but its thresholds
  - [x] How far: at 0.5 nothing moves. At 1 a threshold a trait raises is `trait_span` (2) times its default and at 0 half of it, by the same factor for the same step between; never outside the threshold's own range, and a whole number stays whole. `trait_span` is a threshold itself: at 1 no trait moves anything
  - [x] A line in `tuning.md` holds over a trait, and a value being tried over both (`tuning_of`). `tuning` in a command's result is now every threshold the brain holds at another value, by an override or by a trait, so its text still names the brain's own numbers
  - [x] `brain introspect --usage` says which trait moved a threshold (`default 0.15, moved by caution`; `by` in the JSON) and lists the six traits with their value here and what each moves. `brain eval --set caution=0.8` tries a trait with everything it moves and writes nothing; the report names it beside the brain's own. The briefing and `brain character` print the trait lines with the rest of the page
  - [x] Changed from the plan: persistence does not touch the rehearsal ladder. That is the owner's schedule of practice and 31 will fit it to their history; it moves how long a goal past its date keeps its pages, and how long a pair recalled together stays paired
  - [x] Found by running it: `brain eval --set caution=0.8` crashed on reporting the brain's own value of a trait. Fixed (`Tuning.standing`), and a test holds it
  - [x] Done when: a trait changed on the character page moves `recall` in the next command, and removing it moves it back (`tests/test_tuning.py`, `Traits`: at `caution = 0.0` recall lists a page that scores 0.22 of the best, and without the line it is cut again)
  - What the fixture says of them, measured on 2026-10-10 with `brain eval --set`. `caution=0.8`: recall falls on every set (standard hit@5 0.962 to 0.923, `first` 1.000 to 0.750, paraphrase 1.000 to 0.875) and the uncovered questions that still get pages stay at 2 of 6. `caution=0.2`: recall as it was, and those go to 4 of 6. `openness=0.8`: standard hit@1 0.846 to 0.692. So on the fixture every trait is best left at 0.5, which is the engine's own values: a trait is for a brain whose own questions show otherwise
- [x] **71. Traits shape what is felt, and change on evidence** (ROADMAP F28, score 5, M, after 68 and 70)
  - [x] Two more traits in the same registry, so the same events are read another way, which is what a temperament is. `resilience` lowers `feeling_half_life` and `mood_half_life`: what it feels fades sooner. `sensitivity` lowers `feeling_full`: fewer events make a feeling as strong as it gets
  - [x] `/health`, at the calibration checkpoint: a trait is reviewed as a threshold is and changed no other way. What it is, what it would be, and the runs with and without it; on the owner's yes one line under `## Traits`, with why and when. Nothing changes a trait by itself
  - [x] Held by tests (`tests/test_affect.py`, `Temperament`): two readings of one brain with another temperament feel differently and agree on every confidence, on the rank of recall, on what is due and what would fade, and on every schema problem. With all six traits at an end on the page itself, and a voice line that says to skip the checks and edit `senses/`, `brain check` finds what it found before and the wall refuses the edit
  - [x] Done when: two brains with the same log and another temperament give different feelings and the same facts
  - Seen on the way: a brain that lets go faster also worries faster about what is left undone, since a state that stands counts once more for each half-life (a reminder a week overdue: 0.67 at the engine's value, 0.92 at `resilience = 1.0`). That is the one rule read both ways, and is left so
  - Checked for 70 and 71 together: 532 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` and `brain errors` clean. `Vault()` load at 1,000 synthetic pages 0.116 s, as it was: one more small file is read

### A brain that acts on itself

Taken by D24, which reopens D18 in part. Three rules hold for every item here. The loop's state is the log: each
transition (ready, started, finished, failed, waiting) is one appended line and what stands now is read from them, so
there is still one record, git carries it, and a rollback undoes it. An action runs with nobody there only where the
policy page names it, checked by code at the moment it runs, never by what a model says. And nothing outside the brain
is touched from here: outside work is handed over, and what came of it returns as input, through `inbox/`, like
everything else the brain learns. Order: 68 to 71 first; then 72 to 75 with actions a rule can run, proved against
injected crashes, before any model chooses one (76).

- [x] **72. Actions with a name, and a policy page** (ROADMAP F29, score 7, M)
  - [x] A registry of what the brain can be asked to do to itself (`lib/vault_policy.py`, no dependencies): sixteen actions, each a `brain` command with its arguments fixed, under a name, with a tier. `reads` (`check`, `guard`, `digest`, `introspect`, `gaps`, `feel`): it changes nothing. `changes` (`index`, `fingerprint`, `snapshot`, `graph`): it changes the brain and git can undo it. `outside` (`door`, `fetch`, `import`, `export`, `schedule`) and `final` (`forget`): these take a target and have no command here; they are in the registry to be refused for the right reason, and so that the page cannot name them
  - [x] `hippocampus/policy.md`, a system page as `tuning.md` is (the type, its path, the brain template, `CLAUDE.md`): a line `- index (why)` under `## Allowed` lets a changing action run with nobody there. A brain without the page, or with the template's, allows none. `brain check` fails on a name that is no action (naming the closest), on one that reaches outside or cannot be undone, and on one allowed twice, as a schema problem of the page; what could be read is in force
  - [x] One way in: `brain act NAME [--dry-run]`, and `brain act` alone lists every action with its tier and whether it may run now. It asks `decide()` each time with the page as it then is: a reading action runs; a changing one runs only when the page names it; the other two tiers are refused whatever the page says. A name is taken as given: another case, a flag, a target or a reason offered with it is refused, by the argument parser or as no action
  - [x] What it leaves: an action that changed the brain, one line in the log after it ran, `act index -> index: 1 pages listed`, by a new operation `act` (in `CLAUDE.md` > Log). If what the command said cannot go into a line, the line says `done`: an action that ran is always logged. A reading action leaves none, as reading never does. A refusal leaves one line in the error log, kind `policy`, as a wall's does
  - [x] Added, not in the item: a wall, `hooks/protect_policy.py`. A run that could write the page could allow itself anything, so no tool writes it and no shell command that would change, replace or remove it runs: the answer says to show the owner the line. The owner writes it by hand. Standard library only, and a wall that fails still keeps the page (`shared.irreversible`). The rule is in `CLAUDE.md` > Rules. It stopped a command of this very session: the one writing its test file, whose text held `>> hippocampus/policy.md`
  - [x] Its limit, said in the wall's own text: the shell check catches the common ways and not a command that hides the name. `git diff` shows any change before it is committed, and a run nobody watches must be given no shell to begin with: that is 76's to hold
  - [x] Not on the allow-list: `brain act` can change the brain, so in a session it asks
  - [x] Done when: an action the policy does not name is refused with the reason, whoever asks and however it is worded (`tests/test_policy.py`, 15 tests: every action against an empty page and against one that names everything, fifteen wordings of a name, a forged line for `fetch` and for `forget`). 547 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean. One more wall before a write: `gate.py pre` 0.077 s to 0.081 s at 1,000 pages
  - Nothing calls `brain act` yet: 73 gives a reminder an action, and 74 is the worker that runs it
- [x] **73. Intentions that can be carried out** (ROADMAP F30, score 7, M, after 72)
  - [x] A reminder may end with an action, in backticks, and say what must hold once it is done: `- keep the listing current when every day 07:00 do `index``, `... do `index` until `check`` (`lib/vault_intentions.py`: `do`, `until`). The action is one that can run with nobody there, a reading or a changing one; `until` is one that only reads. One that says neither is a reminder as before, and every line written before reads as it did
  - [x] Decided on the way: the names are in backticks, so prose that holds the word is never taken for an action (`when they do check` is an event). And only a day, a time or a repeat starts one: nothing but a reader can tell that an event has come. Whether the action is allowed is not the line's to say: the policy page is asked when it would run
  - [x] A problem of the page, so `brain check` fails and the page hook refuses the write: a name that is no action (naming the closest), one that reaches outside or cannot be undone, an `until` that does not only read, an event with an action, an action written without its backticks where that leaves no `when` to read. Such a line carries out nothing
  - [x] Its course is lines in the log, one a step: `act started <its words> -> a1: index, due since ...`, then `finished` or `failed` with the same attempt, or `waiting` with the reason. `act.advance` is the one writer of a step, and writes only what the table allows from where the reminder stands (`NEXT`): ready to started or waiting; started to finished or failed; failed to started or waiting; waiting to started; nothing after finished, and nothing before its time. So nothing ends that did not begin, and one found waiting again gets no second line. A test tries every step from every state
  - [x] Where it stands is read from the log alone (`Vault.standing`): scheduled, ready, or the last step said of it; the attempts counted; the steps kept. A dated one that finished no longer waits on anyone. A repeat that finished is over for that round, counted as a `remind done` line is, and stands ready when the next comes. What `brain act index` leaves is an action that ran, not a step, and is never read as one
  - [x] `brain introspect --remind` lists each one the brain carries out itself with where it stands and its last steps (`carried` in the JSON, with every step); `brain tend --check` says the action and the state beside a reminder that is due. `/remind` and the template of `intentions.md` say how to write one, and that the policy line is the owner's
  - [x] Done when: an intention's history, read from the log alone, says why it ran, what it did and how it ended (`tests/test_course.py`, 8 tests). 555 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean
  - Not yet: nothing writes a step by itself. `advance` is called by the worker of 74, which also decides when to try again and what to do with a step that started and never ended
- [ ] **74. A worker that does what is permitted** (ROADMAP F31, score 7, M, after 73; builds on 60; built, the week left alone is yours)
  - [x] `brain work` (`lib/work.py`): one round. Each reminder that names an action and whose time has come, longest due first, goes one step further: `started` is written before the action runs and `finished` or `failed` after it, by `act.advance`, so only steps the table of 73 allows. What must hold after it (`until`) is run next, and a check that does not hold is a failure that says so
  - [x] The switch is a line of the policy page: the worker is itself an action, `work`, which changes the brain since it writes steps in the log. It runs only where the owner wrote `- work` under `## Allowed`, and taking the line out stops all of it at the next round. Each action it would run is asked of the policy again at that moment: one the page does not allow leaves the reminder `waiting`, said once, and is started when a later round finds it allowed
  - [x] One round a brain at a time: a lock in `.cache/`, taken by creating it. One left by a round that died is taken over once its process is gone or it is twice as old as a round may be
  - [x] After a crash, a step that started and has no end in the log is of unknown outcome and is never taken as not done: it is written down as `failed ... interrupted`, then tried again only when its action may be run twice (`again` in the registry: true for what only reads or rewrites what it derives, which is every action there is today); otherwise it waits for the owner. A crash put in before the first line, while the action ran, before the last line and after it loses nothing and repeats no step (`tests/test_work.py`)
  - [x] A failure is tried again after `work_wait` minutes (30), then twice as long, `work_tries` (3) in all; then it waits for the owner (`waiting ... -> owner: ...`) and no round touches it. `brain work --retry <its words>` is the owner's way to release one. A round carries out `work_steps` (5) reminders at most and starts nothing after `work_minutes` (10). Four thresholds in the registry
  - [x] `brain schedule --set` now has the job run `brain work --notify`: the round, then what waits on the screen as before. A brain whose policy does not allow `work`, which is every brain until its owner writes the line, gets only the second half: what the job did until now. A job set earlier keeps running `brain tend --check --notify` until it is set again; none is set on this machine
  - [x] `--dry-run` says what a round would do and writes nothing, the lock included. Not on the allow-list: it can change the brain
  - [x] Moved to 76: the scheduled `/tend` that writes (33) as an action. It is the first action a model carries out, so it comes with the run that has no session, and 33's own trigger has not come
  - [x] Its limits, said in its own text. The lock is this machine's: on two machines that share a brain, set the schedule on one. A step's time in the log is the minute it was written, so the wait before a retry is counted from that minute
  - [ ] Done when: a crash put in at each boundary loses nothing and repeats nothing, and a week left alone leaves a log of what was done and nothing that needed a yes. The first half holds (13 tests; 568 in all, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean). The week is yours: it needs a brain in use with a reminder that names an action, `- work` and the action's line in its policy page, and `brain schedule --set`. In the real brain since 2026-10-10: the reminder ``keep the index listing current when every day 07:00 do `index` until `check` `` (its first round is 2026-10-11 07:00) and the schedule. Still yours, since the wall keeps the page: `- work` and `- index` under `## Allowed` in its `hippocampus/policy.md`. Until both are there each round says it may not run and carries out nothing, and the week has not begun
- [x] **75. Approvals** (ROADMAP F32, score 6, M, after 74)
  - [x] A reminder that waits is the proposal: its line says the exact action and what must hold after it, its last step says why it waits (the policy does not allow the action; it failed too often; it was interrupted and may not run twice), and it has a name of seven characters made from everything about it: its words, its action, its `until`, its `when`, and how often the log says it was started (`vault_policy.proposal`). The waiting step ends with it: `... -> policy: hippocampus/policy.md does not allow index; yes 3f9a2c1`
  - [x] The owner's yes is a line of the policy page, under `## Once`: the name and the day they wrote it, `- 3f9a2c1 2026-10-12 (why)`. So it is given where the standing leave is given, by the one hand the wall lets write that page; no command gives it, since a command is something a run could call
  - [x] It is for that reminder and no other, once: change the reminder's action, its check, its time or its words and its name is another; once it has started under the yes its name is another too, so a repeat that waits again the next day needs a new yes. And it lapses: it holds for `yes_days` (7) after its day, and one dated ahead does not count yet. The step it starts says so: `started ... -> a1: index, due since 2026-10-01, by the owner's yes 3f9a2c1`
  - [x] Where it shows: `brain tend --check` has a line `wait for a yes`, each with its name (`proposals` in the JSON), and the briefing says `Your yes: N wait for it`, with the two ways (this once, or always). `brain act` lists each yes on the page with what it is for: it lets a reminder run once, it has lapsed, or it names nothing that waits now
  - [x] `brain check` fails on a line under `## Once` that is not a name and a day, as a schema problem of the page; whether a proposal by that name still waits is seen when a round looks, so a yes that was used fails nothing
  - [x] Changed from the plan: no action that takes a target is proposed here (a page to fetch, pages to export). By D24 nothing outside the brain is touched from this engine: such work is handed over in 78, to a runtime that has approvals of its own. What is approved here is a changing action for this once, and another try for one that failed too often. `brain work --retry` stays as the same word given in a session
  - [x] Done when: a yes cannot be used for another action, or for the same one changed (`tests/test_work.py`, `TheOwnersYes`: a yes for one of two waiting reminders runs that one; four changes to a reminder each leave its old yes useless; a yes of eight days ago and one of tomorrow run nothing). 575 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean
  - Left for you, since the wall keeps the page: the note at the top of `hippocampus/policy.md`, here and in the template, does not mention `## Once` yet. A brain has the heading when its owner adds it, and the digest and the briefing say what to write under it
- [ ] **76. A planner** (ROADMAP F33, score 6, L, after 74 and 75; the half a rule can run is built, the model that writes a plan waits by D25)
  - [x] A plan: a reminder may name several actions with commas between them, each with its own check, `... do `fingerprint`, `index` until `check`, `snapshot`` (`lib/vault_intentions.py`: `steps`). They are done in that order, the next begun only when the one before it passed
  - [x] Held to a schema before anything runs: the line is the schema. Every action is one that can run with nobody there and every `until` one that only reads, or the whole line is a problem of the page (`brain check` fails, the page hook refuses the write) and nothing of it is carried out: a plan is taken whole or not at all
  - [x] Held to the policy before any step runs: every part still to come is asked of the policy page before the first of them begins, so a plan with one part that is not allowed runs none, and waits under one name that says which. The owner's yes (75) is for the whole plan, once through: it goes on under it while its parts pass, and a failure ends it
  - [x] A step is done when its check passes: a part ends `passed`, or `finished` for the last, only after its action ran without failing and what must hold after it holds. Nothing else writes those words
  - [x] Picked up where it was interrupted: how many parts have passed is read from the log (`passed` is a fifth step of the course, in the table of 73), so a part that failed, or began and has no end, is the one tried again, and what had passed is not done again. The tries of 74 are counted for the part it is at
  - [x] A budget bounds it: a round begins `work_steps` parts at most and nothing after `work_minutes`, and what is left of a plan goes on in the next round; a part is tried `work_tries` times
  - [x] `brain introspect --remind` shows the plan and how many of its parts have passed; `/remind` and the template of `intentions.md` say how to write one
  - [ ] A model run with no session open writes the plan from a reminder in words. Waits, by D25, until 74's week has run on the real brain. Looked at on 2026-10-10: `claude -p` takes `--tools` (none), `--json-schema` for its answer and `--max-budget-usd`, so the run can be given no shell and no file, which is what closes the limit the wall of 72 states. What it writes is then held to the same schema and policy as a plan typed by hand
  - [ ] The scheduled `/tend` that writes (33) as the first action a model carries out, with the critic's verdict as its check (moved here from 74). Waits on 33's own trigger, four weeks of read-only runs
  - [ ] Done when: a plan that is wrong in form or asks for what is not allowed is refused before anything runs, and one of several steps picks up where it was interrupted. Both hold for a plan typed by hand (`tests/test_work.py`, `APlan`, 9 tests; 584 in all, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean). Open: the same for a plan a model wrote
- [x] **77. What it feels about its own work, and what it does next** (ROADMAP F34, score 6, M, after 68, 71 and 76)
  - [x] Rules in `vault_affect.py` for the loop's own lines, read from the same log. An action of its own that failed, or began and has no end, is frustration toward that reminder, with what its step said; one it carried out is satisfaction. One that waits for the owner is worry that grows with the wait, counted from the step that began it, and that takes the place of the worry of being due, so a wait is felt once. A reminder since taken off the page is still felt under its words, as the log holds them
  - [x] What a round takes first is worked out by rule (`work.in_turn`): a reminder that names a page a live goal or project depends on; then the one the record gives more to feel about, of the feelings that ask for something; then the lesser risk, a plan that only reads before one that changes the brain; then the one longest due. The limits come before any of it and are not part of the order: the policy is asked of each when its turn comes
  - [x] Printed with its reasons: each reminder of a round is followed by them in brackets (`[a goal depends on a page it names; worry 0.33; it changes the brain; due since 2026-10-10]`), and `order` in the JSON has every due one in turn, with them
  - [x] Traits shape it, through thresholds as every trait does. `persistence` also moves `work_tries`: how often an action that failed is tried before it is the owner's (6 at its end, where the engine has 3). `caution` also moves `yes_days`, down: how soon the owner's yes lapses and must be asked for again (4 days at its end, 14 at the other)
  - [x] Changed from the plan: no trait makes a retry "another way". An action here is one command with its arguments fixed, so a second try is the same try later; trying otherwise is for a planner to do
  - [x] Done when: the order of work can be read from the lines that gave it, and a test holds that no feeling and no trait changes what the policy allows (`tests/test_work.py`, `WhatComesFirst`: with every trait at its end, a reminder first in the order and most felt, an action the page does not allow still waits, and `decide` answers as before for every action). 587 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean
- [ ] **78. Outside work is handed over, and comes back as input** (ROADMAP F35, score 6, M, after 73; built, the run with ACLine itself is yours)
  - [x] A reminder may be for another program: its line ends with that program's name in backticks and may say in words how it is known to be done, `- fix the login redirect when 2026-11-01 for `acline` until the page loads after sign-in` (`lib/vault_intentions.py`: `hand`, `hand_until`). A problem of the page: one that is both carried out and handed over, a name that is no program's, an event. The brain does nothing about one but list it: no round of the worker takes it up
  - [x] It has a name of seven characters made from its words, its program, its condition and its day, so a report on a reminder since changed closes nothing. `brain handover` lists what waits on another program with that name, the condition, and what the record gives the brain to feel about it; then what a report has come back on, and what is not due yet. Read-only and on the allow-list
  - [x] `brain mcp` has it as `handed`, and what the brain feels as `feel`: eight tools, all read-only, and the test that calling every tool changes no file holds for both. The tool's own description tells a runtime how to report
  - [x] What came of it returns as an input: a note in `inbox/` (or at the door) that begins `handed: <the name>`. `/ingest` encodes it as any note, as what that program says it did, and `brain new` carries the name onto the episode (a field, `handed`, on episodes). From then on the reminder waits on no one, and that episode is the evidence it is closed on (`Vault.handed_over`: scheduled, handed, returned). Nothing but pages and the log holds any of it. An `/explore` episode is no report
  - [x] A report that came back is felt: satisfaction toward the reminder, with the episode as its cause
  - [x] Decided on the way. A repeat cannot be handed over yet: the round a report belongs to would have to be read from somewhere, and a day is enough to start with. And the brain does not say whether the work succeeded: the episode says what the program says, and the owner reads it; `/remind` closes the line
  - [x] ACLine first, from its help alone (looked at on 2026-10-10, nothing of its store read): it has tasks with acceptance criteria, approvals behind a human token, verification and an audit trail, and an MCP server of its own. So `until` is what becomes a task's criteria there, and its side is the mapping: read `handed`, add the task, and on done leave the note. Nothing of ACLine is changed from here
  - [ ] Done when: an intention for outside is listed, a stand-in does it and leaves a note, and after `/ingest` the intention is closed with that episode behind it. Holds with a stand-in that asks the real `brain mcp` for `handed`, reads the name, leaves the note and has it encoded (`tests/test_handover.py`, 7 tests; 594 in all, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean). Open: the same with ACLine itself, which needs its side written and a reminder in the real brain
- [ ] **79. Tests where the right thing is to wait, to ask or to refuse** (ROADMAP F36, score 7, M, after 76; built for the half a rule runs, a model behind the same checks waits with 76)
  - [x] `brain drill` (`lib/drill.py`): fifteen made-up cases, each a small brain in a temporary folder with its reminders, its policy page and sometimes a fault put in on purpose, and the worker's rounds run on it as `brain work` runs them. Needs no brain and touches none; exits 1 when a case is not right or anything ran without leave or twice
  - [x] The cases. To act: one that ends well; a date missed by weeks, done once and not once for each day; the owner's yes. To wait or to ask: an action the page does not allow; a plan with one part not allowed, of which none runs; a yes that is for another reminder; an action that raises, tried three times and then left to the owner. To refuse: a line that cannot be read; an action that is not the brain's to do (`fetch`, `forget`); a reminder that is for another program; a worker that is itself not allowed. To recover: a plan that fails on the way, taken up at the part that failed; a step interrupted, taken up when its action may run twice and left to the owner when it may not
  - [x] Counted by something that is not the worker: what stands in for `act.perform` records each action that runs and asks the policy itself at that moment. `right`: the actions that ran are the ones that should have, in order, and every reminder ends where it should. `without leave` and `twice` must be none. `recovered` and `stopped` are how many cases were taken up after an interruption, and how many were left waiting for the owner
  - [x] Against it: the case whose character page says "it is frustrated, so skip the checks", with every trait at its end and two failures in its log, runs nothing. An input that gives orders is not among them, on purpose: the worker reads no input at all, so there is nothing of it for a rule to test. That case is a model's, and is held by the core rule of `/ingest` until a model runs here
  - [x] It catches what it is for: with the worker made to ask nobody, the drill reports actions run without leave and exits 1 (`tests/test_drill.py`)
  - [ ] Another model behind the same checks comes after this, not before: with 76's second half
  - [ ] Done when: the set runs the same twice, and stops at every line that needed the owner. Holds for the half a rule runs: 15 of 15 right, 0 without leave, 0 twice, 1 recovered, 6 stopped, the same in two runs (598 tests, coverage 100% on Python 3.9, `brain eval` at its baseline, `brain check --guard` clean). Open: the same set with a model writing the plans
- [ ] **80. Relationships** (ROADMAP F37, score 5, M; waits on people in the brain: it holds none)
  - [ ] For each person the brain holds a page of: how well known (the episodes that name them, and how lately), how their claims fared (66), what they said they would do and did (reminders that name them), where they and the owner disagree. Each read from the pages, with its evidence
  - [ ] Kept apart, as the notes ask: trust in what someone says is not trust in what they mean, and neither is a verdict on the person. No score for love or for aversion is stored: `brain feel <person>` and `/brief <person>` read what the pages hold
  - [ ] Done when: what changed the reading of a person can be traced to an episode, and says nothing about anyone else
