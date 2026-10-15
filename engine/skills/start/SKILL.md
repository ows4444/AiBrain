---
name: start
disable-model-invocation: true
description: First run - check the setup, interview the owner, walk through the first cycle
---

Guide the owner through a first run, one step at a time, waiting for them
between steps:

1. Run the setup check from `health` and fix anything mechanical.
2. If `OWNER.md` is not filled in, ask the owner to type
   `/owner` (it runs only when typed; you cannot start it) and continue once
   the interview is done.
3. Ask for two or three related pieces of input (articles, notes, a video
   link) and save them to `senses/`. Suggest the Obsidian Web Clipper, saving
   into `senses/`, for later.
4. Run `/ingest`, then `/sleep`, explaining what each made: episodes first,
   concepts only where two inputs agree.
5. Run `/ask` on what they just added, so they see a cited answer and a recall
   line.
6. Close with the rhythm: `/ingest` when `senses/` fills, `/sleep` weekly,
   `/rehearse` when the briefing says pages are due, `/review-decision` when it
   says decisions are due, `/health` monthly. Mention `/explore` for pushing a
   concept further and `/decide` for the next real choice.
