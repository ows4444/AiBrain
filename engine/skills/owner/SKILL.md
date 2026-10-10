---
name: owner
disable-model-invocation: true
description: Interview the owner and fill in OWNER.md
---

Interview the owner one question at a time: who they are, goals with dates,
how they want to be spoken to, active projects. Write the answers into
`OWNER.md` at the brain's root, as short facts (in a brain without that file,
the Owner section of the root `CLAUDE.md`). Goals go under
`## Goals`, one line each: `- <goal> by YYYY-MM-DD -> [[page]], [[project]]`
(date and links optional; link the concept pages or `prefrontal/` project the
goal depends on, if any exist). The brain reads this list: it decides what is
rehearsed first and what never fades. When a goal is met or abandoned, end
its line with `(done)` or `(dropped)` rather than deleting it. Change no other file
without asking. A vague answer gets a follow-up question, not a vague line.
Log `brain log owner --result "OWNER.md <filled | updated: what changed>"`.
