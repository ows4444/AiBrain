---
name: ask
description: >-
  Answer a question from the brain's pages, cited, and log the recall. Use for /ask or any question the owner's notes should answer. Not for long reports (write) or web questions.
argument-hint: "<question>"
---

# Recall

Answer $ARGUMENTS from pages only, cite every page, log the recall, and name what is not covered.

Retrieval starts from the words of the question and spreads along
associations, the way a cue brings back its neighbours. An answer that quietly
blends in general knowledge is the most damaging thing this system can do,
because it cannot be checked.

## Core rule

Every claim names the page it came from. A claim from an `origin: generated`
episode is a hypothesis from `/explore`; say so when citing it. Anything known but not on a page is
labelled outside knowledge or left out. If nothing covers the question, say so
in one sentence and stop.

## Workflow

1. **Recall:** `brain recall "<the question>" --also "<wording>" --also
   "<wording>"`, adding `--project <name>` when the question is about a
   project in `prefrontal/`. The question goes in as the owner asked it; the
   two other wordings are yours, one in the terms the field uses for it and
   one in plain everyday words. Same question, same scope: no fact, name or
   number the owner did not give. They reach a page whose words the owner did
   not use; whether the brain covers the question is still judged on theirs. It ranks pages by the
   question's words, then spreads along links (typed links and pages recalled
   together before count more), and shows for each how it was reached, its
   summary, its confidence and its flags. It cuts weak rows, and prints one
   line and no rows when the best page holds too little of the question;
   `--all` lists everything. Under "held ideas" it lists ideas named by a
   source that have no page yet: answer from that line when it is enough,
   cite its episode, and say how many sources it rests on. Read the summaries first and open
   only the pages that bear on the question, top down; a page with no
   summary has to be opened to judge it. Where a row says `read first`, it
   names the section that holds the question's words, with its lines: read
   those lines, and the rest of the page only when they do not answer. `hippocampus/index.md` is
   the map when the ranking misses something you expect. For a question
   spanning many pages, hand it to the `researcher` agent and log the recall
   it returns.
2. **Follow further** only where a page read points somewhere the ranking did
   not reach; stop when new pages stop adding anything.
3. **Answer in plain prose** with `[[page]]` citations inline, in the mode
   asked for (below). State each cited concept's confidence as `brain recall`
   gives it (`low`, `medium`, `high`, with its source count). A row flagged
   `contradicted` names the pages that say the opposite (`the opposite is
   said by:`), whether or not they are among the rows: read them, and give
   both positions with their sources, saying that sleep has not weighed
   them yet. An answer from one side of a contradiction is not an answer. A long
   answer (more than a paragraph, or one that gives numbers or quotes a
   page) is checked before it is given: pass it to `brain ground -` on
   stdin, and for each line it lists cite the page, label the sentence
   outside knowledge, or take it out.
4. **Log the recall,** always, even for an empty answer:
   `brain log recall "<the question as asked>" --pages <page> <page>` (pages
   that contributed, not every page opened; none: leave `--pages` out). It
   refuses a page name it does not know. This is what keeps a page from
   fading, and pages named together grow more strongly associated.
5. **Reconsolidate:** for a cited page flagged `stale`, ask the owner whether
   it still holds. Yes: add `- Rechecked (owner, DATE): still holds.` under
   its `## Open questions` (or last section) and set `updated:`. No, or not
   sure: tag it `to-revisit` and say what the owner doubts. Never rewrite the
   claim itself; recall never overwrites.
6. **Name the gaps** and offer the next move: an input worth encoding, an
   insight worth writing.
7. **Nothing answers:** `brain recall "<question>" --all --dormant`, and once
   more in other words for the same thing, before saying so; name the
   queries tried under `Not covered:`. Cite a dormant page as dormant, and offer to restore it (log, move it
   back, `brain index`); a recalled page is worth keeping.

## Modes

| Asked | Do |
|---|---|
| connect A and B | Show the path through pages, not just the endpoints. |
| argue against X | Everything that opposes X. If nothing does, say so; never manufacture an objection. |
| how my view on X changed | Was (claim, episode, date) / Now (claim, episode, date) / what moved it / how firm. A fixed error is not a change of mind. Recency is not correctness. |
| what does X rest on | Every episode behind it, dates, `unverified` or `disputed` tags, whether self-reported. |
| timeline of X | Episodes in date order and how the claims moved. |
| what did I learn in <period> | `brain since <YYYY-MM or date>`: pages made and changed, questions asked. |
| what is missing on X | Questions the pages raise that no episode answers. |
| compare A and B | Only what pages record; mark unsupported comparison points. |
| open contradictions | `brain introspect --open`: `disputed` pages and `contradicts` links; both positions, both sources, what would settle it (then `/maintain settle`). |
| what did I decide about X | Decision pages: what was chosen, what was expected, and the outcome if reviewed. |

## Output

Prose, then:

```
Read: <pages that contributed>
Confidence: <page: level (n sources)>, ...
Not covered: <what the brain does not answer>
```

## Calibration

Reading three pages when fifteen are relevant is the common failure; reading
everything is the opposite one. Never pad an empty answer. When `brain recall`
puts the right page low or misses it, add the question and the page it should
have found to the owner's question set (`brain eval --questions`); that is how
retrieval gets tuned.
