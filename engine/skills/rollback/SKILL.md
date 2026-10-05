---
name: rollback
disable-model-invocation: true
description: Show what the last run changed, and undo it on confirmation
---

Find the last run (or $ARGUMENTS) from `hippocampus/log.md` and
`git log`/`git diff`. Show what it changed (the `critic`
agent can judge whether the run met its goal) and stop. On confirmation, revert
only those files: `git restore` if uncommitted, `git revert <commit>` if
committed; never `git reset --hard`. Log
`DATE rollback <run> -> <n> files restored` and run `brain check`.
