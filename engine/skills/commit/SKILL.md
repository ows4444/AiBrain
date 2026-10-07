---
name: commit
disable-model-invocation: true
description: Check, then commit the current state with a one-line message
---

Run `brain check` and `brain test`;
if either fails, report and stop. A failure under "inputs or append-only lines
changed" means a file in `senses/`, or a line of the log or metrics, was
changed or removed: show the owner `git diff` for it and commit only on their
yes, since committing is what accepts the change. After a large run (an archive ingest, a
sleep over ten episodes), offer the `critic` agent's verdict on it first. Mention any log lines `brain check` lists
with an unknown operation, but do not stop for them. Stage and commit with one line naming what
changed and which run produced it, from the latest log lines (e.g. `sleep: 3
episodes, 1 concept established`). Report the diff summary. Never push. If
work is still open in a project, run `brain resume` after the commit: a
commit is the place to compact or stop. If the commit changed `engine/`, remind the owner that the running hooks are
still the old ones until `claude plugin update aibrain@aibrain` and a restart;
old versions stay in the plugin cache until they prune them.
