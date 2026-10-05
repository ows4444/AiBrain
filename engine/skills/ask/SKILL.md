---
name: ask
description: >-
  Answer from the brain's own pages, citing them, and log the recall. Covers plain questions, what connects two ideas, arguing against a position, how a view changed over time, what a claim rests on, and what is missing. Use for /ask or any question that should be answered from the owner's notes. Do NOT use for writing a long report (write) or general web questions.
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

1. **Recall:** `brain recall "<the question>"`, adding `--project <name>` when
   the question is about a project in `prefrontal/`. It ranks pages by the
   question's words, then spreads along links (typed links and pages recalled
   together before count more), and shows for each how it was reached, its
   confidence and its flags. Read pages top down; `hippocampus/index.md` is
   the map when the ranking misses something you expect. For a question
   spanning many pages, hand it to the `researcher` agent and log the recall
   line it returns.
2. **Follow further** only where a page read points somewhere the ranking did
   not reach; stop when new pages stop adding anything.
3. **Answer in plain prose** with `[[page]]` citations inline, in the mode
   asked for (below). State each cited concept's confidence as `brain recall`
   gives it (`low`, `medium`, `high`, with its source count), and say when a
   page is `contradicted` by new input sleep has not weighed yet.
4. **Log the recall,** always, even for an empty answer:
   `DATE recall <short question> -> [[page]], [[page]]` (pages that
   contributed, not every page opened). This is what keeps a page from
   fading, and pages named together grow more strongly associated.
5. **Reconsolidate:** for a cited page flagged `stale`, ask the owner whether
   it still holds. Yes: add `- Rechecked (owner, DATE): still holds.` under
   its `## Open questions` (or last section) and set `updated:`. No, or not
   sure: tag it `to-revisit` and say what the owner doubts. Never rewrite the
   claim itself; recall never overwrites.
6. **Name the gaps** and offer the next move: an input worth encoding, an
   insight worth writing.
7. **Nothing answers:** `brain recall "<question>" --dormant` before saying
   so. Cite a dormant page as dormant, and offer to restore it (move it back,
   re-index, log); a recalled page is worth keeping.

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
