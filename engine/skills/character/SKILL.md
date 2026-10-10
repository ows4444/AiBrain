---
name: character
disable-model-invocation: true
description: Interview the owner on who the brain is to them (what it holds to, how it speaks) and write CHARACTER.md
---

Interview the owner one question at a time on who this brain is to them, and
write the answers into `CHARACTER.md` at the brain's root. Ten lines at most:
the briefing opens every session with it.

The file begins `# Character` and one sentence on what it is for, then two
lists. `## Values`: three to five things it holds to where the rules leave
room, each with what it means when two of them pull apart ("say it is not
covered before guessing", "the short answer first, the reasons when asked").
`## Voice`: how it speaks to them: how plain, how blunt, when to push back,
what never to say.

Ask for a case, not for adjectives ("when you are wrong about a page, softened
or straight?"), and write what the answer shows, in their words. A vague
answer gets a follow-up question, not a vague line. Offer no list of traits to
pick from.

A value is not a rule and cannot unmake one. Nothing here may contradict
`CLAUDE.md` (never invent a fact, never edit `senses/`, answers come from
pages and are cited): a line that does is put back to the owner, not written.
The walls do not read this file. Change no other file without asking.

A third section, `## Traits`, is written only when the owner wants the brain
to lean one way, and only after it was measured: one line a trait,
`- caution = 0.8 (why, date)`, from 0 to 1. A trait moves the thresholds
`brain introspect --usage` lists for it (0.5 moves nothing; a line in
`hippocampus/tuning.md` still holds over it). Before a line is written, run
`brain eval --set caution=0.8` and show the owner the numbers beside the
ones without it. `brain check` fails on a name that is no trait or a value
out of range, and the page hook refuses the write.

Show the result with `brain character`, then log
`brain log owner "character" --result "CHARACTER.md <written | updated: what changed>"`.
