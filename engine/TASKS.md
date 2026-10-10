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

All seven were answered by the owner on 2026-10-09: each as recommended.

- [x] **D1. May `brain log` run without asking?** Decided: yes, it can only append one checked line. Unblocks 6.
- [x] **D2. A new optional field `answers:` on memory pages?** Decided: yes, and private, so `brain export` drops it. Unblocks 22.
- [x] **D3. Generate the index listing?** Decided: yes. Changes "keep `index.md` current in the same run" in `CLAUDE.md` to "run `brain index`". Unblocks 16.
- [x] **D4. A new system page, `hippocampus/tuning.md`?** Decided: yes. Adds a system type to `CLAUDE.md`. Unblocks 13.
- [x] **D5. OpenCode: build what the documents describe, or remove the claims?** Decided: remove them now, reach other hosts through 29. Unblocks 2 and closes 56.
- [x] **D6. Embeddings?** Decided: defer to the trigger in 30.
- [x] **D7. Should engine work write `engine` lines into this brain's log now?** Found and decided on 2026-10-09: no, hold them until 4 puts the brain in use; git history records engine changes until then. The roadmap asks for one line per finished item, but the first dated line marks this brain as in use: `test_an_unused_brain_matches_the_template` then skips, and a clone no longer starts with an empty log.

## Phase 0. Baseline

- [ ] **1. Commit the staged work** (REFACTOR 0.1, S)
  - [x] `brain check --guard` and `brain test` pass
  - [x] Commit the error log, `ARCHITECTURE.md`, `ROADMAP.md`, `REFACTOR.md` and this file (on `main`: the engine work of items 2 to 16 in `e1eddcd`, the four documents in the commit after it, with items 13 and 14)
  - [ ] Done when: the tree is clean, and CI is green once you push (a session cannot: `git push` is denied on purpose). `e1eddcd` is pushed and green; the commit after it has passed the pre-commit gate and waits for your push
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
- [ ] **4. Fill the brain** (REFACTOR 0.4, ROADMAP P0, S, the owner's)
  - [ ] `/start`, then `/owner`
  - [ ] 10 to 20 real inputs in `senses/` or `inbox/`
  - [ ] One `/tend`
  - [ ] Done when: `brain introspect` gives a verdict other than "too small to judge"
- [ ] **5. A question set of your own** (REFACTOR 0.4, ROADMAP P1, S, after 4)
  - [ ] `brain eval --root . --questions motor/eval-questions.json --draft 10`; write each question without the words to avoid
  - [ ] Add two or three questions no page covers (`"covered": false`)
  - [ ] Run it, then `--save-baseline`
  - [ ] Done when: hit@1 and hit@k are recorded on real content

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
- [ ] **10. `candidate_pairs` without the repeated tokenising** (REFACTOR 2.2, S; built, its time target missed: the owner's call)
  - [x] Tokenise each page's title, aliases and summary once
  - [x] Index words to candidates and pages; compare only pairs that share a word, as `near_duplicates` does. Candidates are no longer each compared with every other one either
  - [x] The same pairs in the same order as before, on the fixture and on five synthetic brains
  - [ ] Done when: the same pairs on the fixture, and under 0.5 s at 5,000 pages. The pairs are the same; the time is 0.77 s, from 7.64 s (0.043 s from 0.51 s at 1,000 pages). What is left is the cost of building 206,652 pairs, which the synthetic brain's 40-word vocabulary produces and a real brain would not. Accept it, or say to go further
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

- [ ] **18. `brain eval --from-log`** (REFACTOR 3.1, ROADMAP F3, M, after 6; built, waits on a run in the real brain)
  - [x] The vault takes a cut-off: only the log lines before a given line (`Vault.as_of(line, today)`: a copy that shares the pages, the links and the search terms, and knows only what the log had taught by then)
  - [x] A case is a recall line that is not a rehearsal, with its question and its pages; a line with no page is an uncovered case. A page gone since is not expected; a line all of whose pages are gone is listed and not replayed
  - [x] Replay each as of its own date; score hit@1, hit@k, mrr and uncovered questions still listed. The first ten misses are printed, `--json` has them all
  - [x] Print the two limits with every result: it shows regression, not absolute quality; pages are as they are now
  - [x] Its baseline is kept beside the brain, in `motor/` (`eval-from-log-baseline.json`); the report says when the pages or the log have changed since it was saved
  - [x] Tests on a synthetic brain, and on a small one where a question finds a page only through the pair an earlier line taught
  - [x] Decided on the way: with no `--root` it replays the log of the brain `brain` is run in, not the fixture's; `--set` works on it, so a value is tried on one's own questions. It refuses `--questions`, `--answers` and `--draft`
  - [x] Its cost: 997 logged questions on 1,000 synthetic pages took 19 s, now 9 s, after the pages each log line names, the pairs it teaches and the link weights were worked out once for all copies (and the pages a search may return, with their lengths, once a Vault). Most of what is left is one search a question over every page, which the synthetic brain's 40 words make dearer than a real one. `brain eval` is at its baseline and `brain bench` unchanged
  - [ ] Done when: it runs on the real brain after 4 and its baseline is saved. In the real brain, after `main` is merged there: `brain eval --from-log --save-baseline`
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

- [ ] **21. Say what the brain never mentions** (REFACTOR 4.1, S; measured before building: the target is out of this signal's reach, the owner's call)
  - [ ] `brain recall` prints the question's words found in no page, dormant ones included: `unseen: picasso`; in the JSON too
  - [ ] `/ask` says so in the answer when the subject of the question is unseen
  - [ ] Tune abstention on that signal with `brain eval --set`
  - [ ] Done when: uncovered questions that still get pages fall from 2 of 6 to 0, covered sets unchanged
  - Measured on the fixture on 2026-10-10, nothing built. The two uncovered questions that still get pages hold fewer unseen words than covered questions do. u05 ("Which painters did Picasso learn from?") has one, 0.51 of the question's weight; u06 ("What does a mathematics teacher earn?") one, 0.46. Covered paraphrases have more: p03 three (0.67), p01 three (0.55), p08 two (0.50), p04 two (0.45). A bar that stops u05 and u06 stops those four, and paraphrase recall falls; nothing else about the words tells the two kinds apart (in all of them the best page holds every word the brain has at all). So abstention cannot be tuned on this signal to 0 of 6 with the covered sets unchanged, and by the gate of this phase the item closes. Left to decide: whether to print `unseen:` as information only, for `/ask` to judge by. That wants an answers run (`brain eval --answers`) before and after, because on a paraphrase the line can read as "not covered" when a page does answer
- [ ] **22. `answers:`, the questions a page answers** (REFACTOR 4.2, M, waits on D2)
  - [ ] Add the field to `FIELDS` (private), the templates and the table in `templates/README.md`
  - [ ] Schema: a list, at most five, each one short question
  - [ ] Search it as a field of its own, with its weight in the tuning registry; raise `CACHE_VERSION`
  - [ ] `/ingest` and `/sleep` fill it, in the owner's kind of words
  - [ ] The fixture's `answers:` are written by an agent that sees the page and not `questions.json`
  - [ ] Done when: paraphrase recall hit@1 is 0.875 or better (0.750 now)
- [ ] **23. Several wordings, one ranking** (REFACTOR 4.3, S)
  - [ ] `brain recall Q --also Q2 --also Q3`: fuse the rankings by reciprocal rank to choose the seeds, then spread once
  - [ ] Eval questions may carry `also`, written by an agent that has not seen the pages
  - [ ] `/ask` and the researcher agent always pass two rewordings
  - [ ] Done when: paraphrase hit@5 is 1.000 (0.938 now) and q10 finds `forgetting-curve`
- [ ] **24. `brain fit senses/FILE`** (REFACTOR 4.4, M; built, waits on real ingests to be measured)
  - [x] The input's own rarest words as the query: the pages it bears on, with summaries, and the held candidates it names (`lib/fit.py`). Of the input's words that some page holds, the twelve that mark it most (`fit_words`: its count in the input times its rarity in the brain) are searched as one question. Rarity alone picked incidental words (`across`, `apart`), so the count weighs in. A held idea is named when every word of its name is in the input; an input already encoded is no source of its own ideas
  - [x] Candidate names made of the same words after stemming count as one candidate in the tally (`same_idea`: `Fluency illusion` and `Illusion of fluency`, `Desirable difficulty` and `difficulties`), under the spelling met first. Two sources naming it so now reach the bar for a concept, where they were two candidates with one source each, paired for sleep to read
  - [x] `/ingest` steps 3 and 5 use it in place of guessed topic words, and the encoder agent with them: it follows that skill. `Bash(brain fit *)` is allowed, as the other read-only commands are
  - [x] The instrument for the measure: `brain introspect --queue` ends with `encoding: N episodes, X links each; H ideas held, T of them named by two sources or more`, also in the JSON
  - [ ] Done when: on real ingests, links per episode and candidates reaching two sources are both up, measured before and after. In the real brain: note the `encoding` line now, ingest the next inputs with the new engine, and read it again
- [ ] **25. Use, recency and rank** (REFACTOR 4.5, S, after 18 and 50 logged questions)
  - [ ] Behind a tuning key, off by default: a capped lift from a page's own recall lines, rehearsals left out
  - [ ] Run 18 with and without it; the fixture must not fall
  - [ ] Keep it or delete it; ARCHITECTURE 6.2 then says what is true
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
- [ ] **28. `brain tend --check` and its schedule** (REFACTOR 5.2, ROADMAP F2 steps 1 and 2, S1, A1, M, after 12 and 19)
  - [ ] One read-only digest: queues, rehearsals and reminders due, decisions to review, goals at risk, the gaps of 19
  - [ ] A watcher agent: haiku, read-only tools, runs it and reports
  - [ ] A schedule (a Claude Code `/schedule` routine, or cron) that sends you the result
  - [ ] Done when: leaving the brain alone for a week gives one report and no page changes
- [ ] **29. A read-only MCP server** (REFACTOR 5.3, ROADMAP F12, M, after 12)
  - [ ] A stdio server, standard library only, over the calling convention of 12
  - [ ] Four tools: `search`, `recall`, `since`, `gaps`; no tool that writes
  - [ ] Declared in the plugin, so it starts with it
  - [ ] Done when: another client lists and calls the four tools

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

- [ ] **34. `/capture`** (ROADMAP S4, score 6, S)
  - [ ] One line from inside a session to `inbox/<date>-<slug>.md`; `/ingest` already sweeps `inbox/`
  - [ ] Done when: a captured line shows in the briefing's inbox count
- [ ] **35. Low-friction capture, one door** (ROADMAP F4, score 7, M)
  - [ ] Name the one concrete door first (the roadmap does not name one)
  - [ ] Build that door only, into `inbox/`
  - [ ] Done when: a note taken away from the desk is in `inbox/` at the next session
- [ ] **36. Importers, one per source** (ROADMAP F7, score 5, M each)
  - [ ] An Obsidian vault first: it is already Markdown
  - [ ] Never overwrite; one input per note, into `senses/`
  - [ ] Done when: an import run twice adds nothing the second time
- [ ] **37. `/import`** (ROADMAP S2, score 8, M, after 36)
  - [ ] Picks the importer, writes to `senses/`, hands off to `/ingest`
  - [ ] Done when: the skill passes `test_skills.py` and one real import ends in episodes
- [ ] **38. Ingestion scout agent** (ROADMAP A3, score 6, M)
  - [ ] Sonnet; sorts `inbox/` before `/ingest`: duplicates by fingerprint, secrets by `brain check --guard`, items that need a person
  - [ ] Done when: `/ingest` on a mixed inbox encodes only what the scout passed

### Reach

- [ ] **39. Engine-side extraction** (ROADMAP F5, score 6, M)
  - [ ] PDF text and image text through an optional dependency or a system tool
  - [ ] Falls back to the model when the tool is absent
  - [ ] Done when: a PDF lands in `senses/` as text without the model reading the file
- [ ] **40. Audio and video transcription** (ROADMAP F6, score 6, M, after 35)
  - [ ] An external tool or an API
  - [ ] The transcript lands in `senses/` as text, with its source named
  - [ ] Done when: a recording becomes an input `/ingest` can encode
- [ ] **41. `/transcribe`** (ROADMAP S5, score 6, S, after 40)
  - [ ] The front for 40
  - [ ] Done when: the skill passes `test_skills.py`

### Hygiene

- [ ] **42. `/restore`** (ROADMAP S8, score 4, S)
  - [ ] Log it, move the page back from `dormant/`, put it in the index (`brain index` after 16)
  - [ ] Done when: `brain check` no longer lists links to it as faded
- [ ] **43. `/export`** (ROADMAP S9, score 4, S)
  - [ ] A wrapper for `brain export`, with `/guard` run first
  - [ ] Done when: an export with a credential in a chosen page is refused
- [ ] **44. Contradiction resolver agent** (ROADMAP A2, score 7, S)
  - [ ] Prepares each side of a `disputed` page for `/maintain settle`: sources, dates, strength
  - [ ] It does not settle
  - [ ] Done when: `/maintain settle` reads its output and the page is unchanged until your word
- [ ] **45. Privacy gatekeeper agent** (ROADMAP A5, score 4, S)
  - [ ] A clean-context pass of `/guard` before any export; the critic already covers part of this
  - [ ] Done when: 43 calls it

### Recall and review

- [ ] **46. `/brief`** (ROADMAP S6, score 5, S)
  - [ ] A short cited summary of one person, project or topic: `/ask` with a fixed format
  - [ ] It logs its recall line
  - [ ] Done when: the skill passes `test_skills.py`
- [ ] **47. `/review-decision`** (ROADMAP S7, score 5, S)
  - [ ] The review step split out of `/decide`, so it can be run or scheduled alone
  - [ ] Done when: `/decide` is shorter and both skills pass `test_skills.py`
- [ ] **48. Quiz writer agent** (ROADMAP A4, score 5, S)
  - [ ] Only if quizzes feel thin: `/rehearse` already builds its own
  - [ ] Done when: you say the questions are better with it than without
- [ ] **49. Writer or editor agent for `/write`** (ROADMAP A6, score 3, S)
  - [ ] Drafting moves out of the main session
  - [ ] Done when: `/write draft` returns a draft and the session holds only its report

### Platform

- [ ] **50. Time of day in log lines** (ROADMAP F9, score 4, S, after 6)
  - [ ] An optional `HH:MM` after the date, written by `brain log`
  - [ ] Check every parser that assumes `LOG_LINE` in `vault_model.py`
  - [ ] Done when: two operations on one day sort by time, and old lines still parse
- [ ] **51. Visual interface** (ROADMAP F8, score 5, L)
  - [ ] A static HTML graph from `brain graph`; no server
  - [ ] Done when: the file opens from `motor/graph/` with no network
- [ ] **52. Backup and sync** (ROADMAP F10, score 4, S)
  - [ ] Document a git remote; `git push` stays denied to a session on purpose
  - [ ] Done when: the README says how, and a second clone passes `brain check`
- [ ] **53. Windows support** (ROADMAP F13, score 4, M)
  - [ ] Paths, the `python3` name, symlinks
  - [ ] Done when: `brain test` passes on Windows in CI
- [ ] **54. `/share`** (ROADMAP S10, score 3, M)
  - [ ] Decide what a read-only view for another person means first; 29 is one answer
  - [ ] Done when: that decision is written down and the skill does only that
- [ ] **55. Encryption at rest** (ROADMAP F11, score 3, M)
  - [ ] Only if the brain leaves your machine: it conflicts with plain-Markdown search
  - [ ] Done when: decided, and dropped from the roadmap if the answer is no
- [x] **56. Run the OpenCode plugin in OpenCode** (ROADMAP P2, S, closed by D5)
  - [x] Closed, not built: D5 removed OpenCode from both documents on 2026-10-09, and P2 from the roadmap. Other hosts are 29
