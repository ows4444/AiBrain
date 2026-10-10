---
name: forget
disable-model-invocation: true
description: Remove one source from the brain - its input, its episodes and every citation of them - after showing what rests on it
argument-hint: "<file in senses/ | episode name> [dry-run]"
---

# Forget one source

Take $ARGUMENTS out of the brain: a source that was wrong, private, or should
never have been encoded.

## Core rule

Nothing is removed before the owner has seen the whole list and said yes to
it. Only the owner starts this skill, and the removal itself asks them again.
This is the one way an input leaves `senses/`; no other skill, and no shell
command, removes one.

## Steps

1. **Show.** `brain forget <source>` writes nothing. Give the owner its
   output in full: the input, the episodes, the candidates that go with them,
   each citing page with its lines, and what happens to each concept and
   entity. Add anything it cannot see: a decision whose `## Context` leans on
   the episode, an answer in `motor/` built from it. With `dry-run`, stop here.
2. **Ask** for a yes to that list. A yes to part of it is a no: a source is
   forgotten whole or kept.
3. **Remove.** `brain forget <source> --yes`. It writes the `forget` log line
   and the `forgotten` fingerprint line first, then removes the input, the
   episodes and their index lines.
4. **Clean the citing pages**, one at a time, as the list said:
   - take out the citation, and any sentence that rested only on it; a claim
     another episode also supports keeps that episode's citation;
   - a concept left with one source and no salient episode: log
     `brain log forget "<concept>" --result "back to a candidate on [[episode]]"`, add it
     under `## Candidates` on the episode that is left, remove the page and
     run `brain index`;
   - a concept left with one salient episode: `status: emerging`;
   - a page with no source left: remove it the same way, unless the owner
     says what it now rests on;
   - set `updated:` on every page changed.
5. **Check.** `brain check` must list no broken link to the removed episodes.

Never rewrite a page to say the same thing without its source. What only
that source said goes with it.

## Output

```
Forgotten: <input> | episodes: <n>
Pages cleaned: <list> | removed: <list or none> | demoted: <list or none>
Not touched, for you: <decisions, motor/ files, or none>
Still in git history: <yes | not a git repository>. Say if it must go from there too.
```
