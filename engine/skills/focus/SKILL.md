---
name: focus
description: >-
  Working memory: create a project in prefrontal/ with one measurable goal, pull the relevant concept pages into it, or report where it stands. Use for /focus, "create a project", "set up X", "where does X stand". Do NOT use for one-off tasks or for wiki pages about a topic.
argument-hint: "<project> [scope | status]"
---

# Focus

Focus on the project in $ARGUMENTS: create it if new, otherwise scope or report status as asked.

Working memory holds about four things and the prefrontal cortex inhibits the
rest. A project gives the agent one goal instead of the owner's whole life.

## Core rule

One goal per project, measurable, with a date. At most four active items in
its `## Current state`. Three goals are three projects; work that ends this
week is a task, not a project.

## Modes

**Create.** Interview if needed: what it produces, for whom, by when, the
agent's role and what it must not do. Copy `${CLAUDE_PLUGIN_ROOT}/templates/project/` to
`prefrontal/<name>/` (lowercase-hyphenated, and not a name an existing page
answers to: `brain check` fails on a clash, and links would reach the wrong page) and fill its `CLAUDE.md`,
frontmatter included (`goal:`, `due:`, `status: active`). Link the concept
pages it depends on as wikilinks: that keeps them from fading. Under Owner >
Goals in the root `CLAUDE.md`, link it from the goal it serves
(`- <goal> by <date> -> [[<name>]]`), adding the goal if it is new, and log
`DATE focus <project> -> created prefrontal/<name>/`.

**Scope.** Find the concept pages relevant to the project, save a briefing
(cited, with gaps named) to its `inputs/`, so work can continue inside the
project folder alone.

In every mode, log `DATE recall focus <project> -> [[page]], ...` for the
concept pages read, even if none (`-> none`); the recall hook checks for it.

**Status.** `brain introspect --projects` for its pages, decisions and
feedback files. Report goal, done, in progress, blocked, stale; compare
`outputs/` against `feedback/`, and the decisions that name the project
against their outcomes. A decision due for review is part of the status.
Set `status: done` when the goal is met, so its pages stop counting as in use.

## Output

```
Project: <name> | Goal: <outcome, date>
Depends on: <concept pages>
Active: <up to four items>
```

`feedback/` is the folder people skip and the one that makes the system
improve. No idea what goes in it usually means the goal is not measurable yet.
