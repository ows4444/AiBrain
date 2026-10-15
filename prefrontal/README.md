# prefrontal/

Working memory: one folder per project. Each holds its own `CLAUDE.md` and the four-stage pipeline. Run
`/focus <name>` to create one from the engine's project template:

```
project-name/
  CLAUDE.md    what this project is, its one goal, the agent's role
  inputs/      ideas, briefs, source material for this project
  process/     work in progress
  outputs/     finished work
  feedback/    results, metrics, what actually happened
```

A project's `CLAUDE.md` is a page named after its folder: link it as
`[[project-name]]` from a decision or from a goal in the Owner section. Its own
links to concept pages count as real links, so what a live project depends on
never fades. `status: done` releases them. `brain introspect --projects` shows
each project with its pages, the decisions that name it and its `feedback/`.

`feedback/` is the folder people skip and the one that makes the system
improve. Without it the agent has no idea whether last month's output worked.

Open a project folder as its own working directory when you are working in it,
so the agent sees one goal instead of your whole life. `/focus <project> scope`
pulls the relevant concept pages into its `inputs/` first. Keep at most four
active items in each project's current state.
