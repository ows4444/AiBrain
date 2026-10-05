---
name: ingest
description: >-
  Fast encoding: turn new input in senses/ (or a URL, PDF, paper, transcript, voice note, highlights, the owner's own work, a chat export, or a whole archive) into one episode page linked to what already exists. Use for /ingest, "add this", "process senses". Do NOT use for consolidating into concepts (sleep) or answering questions (ask).
argument-hint: "[path | URL | archive]"
---

# Encode

Encode $ARGUMENTS, or everything in `senses/` without an episode (and in `inbox/`), oldest first. More than twenty pending: switch to archive batches.

The hippocampus records an experience quickly and faithfully, without
rewriting what the cortex already knows. Encoding does the same: one episode,
linked to existing pages, with new ideas held as candidates for sleep.

## Core rule

Encoding writes the episode, the index entry and the log line. It does not
create or rewrite concept pages; `/sleep` does that once evidence repeats.

## Workflow

1. **Land the input** in `senses/` if it is not there yet (see Input types).
   Notes waiting in `inbox/` are moved (not copied) to
   `senses/inbox/<YYYY-MM-DD>-<name>`, the date they were swept. Never edit a
   file already in `senses/`. Then run `brain fingerprint`, which records a
   hash of each new input so `brain check` catches any later edit.
2. **Read it completely** before writing. Pages built from the introduction
   are built from the least specific part.
3. **Check fit.** `brain search "<topic words>"` for the entities and
   concepts it touches; input that fits existing pages is the fast path.
   **Salience:** set `salience:` on the episode, 1 to 5, from what is in front
   of you: 1-3 when it contradicts an established page, touches a live goal
   or project, or carries high stakes (say which). 4 or 5 only when the owner
   says it matters: from 4 up, one episode is enough for a concept and the
   pages never fade, so that call is theirs. Otherwise leave it out.
   **Prediction error:** for each established concept the input bears on,
   ask whether it says the opposite. If it does, write the claim with
   `(contradicts:: [[page]])` on the episode and report it under
   `Contradictions:`; the briefing and `brain introspect --queue` list it until
   sleep records both positions. Do not touch the concept page.
   **Triggers:** read the `revisit if` lines in `brain introspect --decisions`
   and the reminders in `brain introspect --remind`: if this input reports the
   event a decision or a reminder names, say so under `Triggers:` in the
   output. Do not touch the decision page; sleep tags it.
4. **Write the episode** in `cortex/episodes/` from `${CLAUDE_PLUGIN_ROOT}/templates/episode.md`:
   `input:` = its path in `senses/`; `url:` = where the content originally
   came from (for a newsletter or post relaying someone else's work, the
   original's url, so relays of one source count once); claims as claims with
   attribution, numbers with the conditions they hold under. Leave `consolidated:` empty.
5. **Link** the first mention of every existing concept and entity. Under
   `## Candidates`, list each new idea or entity as `- Name - one line on what
   this episode says about it`. Reuse an existing candidate name exactly when
   another episode already lists it (`brain introspect --queue`), and run
   `brain search "<name>"` first: an idea already on a page under another
   name is a link to that page, not a new candidate.
6. **Index and log** in the same run: add the episode to `index.md`; append
   `DATE ingest <path> -> 1 episode, <n> candidates, <n> links`.

## Input types

| Input | Before step 2 |
|---|---|
| URL | Fetch, save readable text to `senses/` with url, author, date. A paywall or fragment is reported, not encoded. |
| PDF | Extract text, check its quality; scans need OCR. Figures that carry the argument go to `senses/assets/`. |
| Paper | Episode built around question, method, result with real numbers, sample size, stated limitations. |
| Video, podcast, voice | Clean the transcript first (below), save it to `senses/`, split by topic if it covers several. |
| Highlights | One episode per book; candidates are ideas, not quotes. Keep quotes short. |
| Newsletters | Group the issues by topic first. One episode per actual item, citing every newsletter that covered it. Repetition across newsletters is not confirmation: five issues relaying one claim are one source. |
| Owner's own work | Episode authored by the owner: their positions, stated plainly, dated. |
| Chat export | `brain chats <export> senses/chats`, then `guard` privacy pass, then triage: ingest only conversations where the owner worked something out or decided something (expect about one in ten), on approval. Build around their reasoning, not the assistant's. |
| Archive (20+ items) | Triage into encode / keep in senses / delete. Oldest first, ten per batch, each batch handed to the `encoder` agent so the main context stays small; log and stop for a go-ahead between batches. Read every page of batch one. Over about 200 items, propose a filter first. |

**Cleaning a transcript.** Punctuate, paragraph at topic shifts, label
speakers, fix mistranscribed terms (flag what you cannot resolve), keep a
timestamp every few minutes, add title, speaker, url, date. Never cut or
summarise; keep hedges and self-corrections. Too garbled to clean reliably:
say so and ask for a better copy.

## Output

```
Encoded: <input> -> [[episode]]
Linked to: <existing pages>
Candidates: <names>, (<n> already named by other episodes)
Salience: <none | n: why>
Contradictions: <none | which page, which claim>
Triggers: <none | [[decision]] or reminder: the event it names, and what this input says>
```

## Calibration

Over-encoding is writing concept pages at ingest; that is sleep's job, and
doing it now fills the cortex with one-source ideas. Under-encoding is an
episode with no links and no candidates. A typical article yields one to three
candidates.
