---
name: maintain
description: >-
  Structural repair: broken links, orphans, schema, index drift, duplicates; rename, merge, split, move to dormant. Use for /maintain, "lint", "fix links", "rename X", "merge X into Y".
argument-hint: "[operation]"
---

# Maintain

Audit and repair $ARGUMENTS, or the whole brain, or run the named operation. Propose anything needing judgement.

Structural rot is silent: nothing errors, the brain just answers worse because
pages are unreachable. Mechanical problems get fixed; judgement calls get
proposed.

## Core rule

Fix what is mechanical. Never delete, merge, split or move a page without
listing it and getting a yes, and never touch `maintained_by: human` pages
without naming them.

## Audit

1. `brain check --json` and `brain introspect`.
   Work from their output; do not recount.
2. **Broken links:** a typo or rename gets fixed; a genuine gap goes under
   Gaps in `index.md`.
3. **Orphans** (concepts, entities, insights and consolidated episodes no
   page links to; decisions and `/explore` episodes are records and never
   listed): link from where they belong, or propose `dormant/`.
4. **Stubs** (concepts, entities, insights under 40 words with no links):
   rebuild from the episodes behind them.
5. **Schema:** fields, types, dates, tags, lowercase-hyphenated file names.
   `brain check` reports these too (the hook only sees Write and Edit).
6. **Near-duplicates:** `near_duplicates` from `brain check` (same-type pages
   whose names overlap, or that share most of their neighbours). Read both
   pages; propose a merge only where they are one idea. On a large brain, the
   `curator` agent drafts the list.
7. **Index drift:** `not_in_index` from `brain check`, and entries pointing
   nowhere.
8. **Undated facts:** `undated` from `brain check` (a count or a status in
   the present tense, with no date and no pointer). It reads words, so first
   drop the lines that are timeless. For each of the rest, one of three:
   look again and restamp it, `(as of DATE, [[episode]])`; keep only the
   pointer to where the number lives; or move it to the dated page it came
   from. Never restamp without looking: a new date on an old number is worse.
9. Repair, rerun `brain check`, log `DATE maintain -> <fixed>, <proposed>`.

## Operations

**Rename.** Check the new name against existing names and aliases (`brain
check` fails on a name two pages answer to); rename the file and `title`; add
the old title to `aliases`; update every inbound link: pages, `index.md`,
project pages (`prefrontal/*/CLAUDE.md`) and Goals in `OWNER.md`; log old -> new; verify with `brain check`, which checks all four. Do not
rename a heavily linked page for style.

**Merge** (only on approval). Survivor by canonical name, not length. Every
distinct claim survives with its source; differing claims both stay. Old title
becomes an alias. Redirect every inbound link, in project pages and the Goals in
`OWNER.md` too. Log first, then delete the old
page, update the index, verify. If the two pages disagree on a fact, they may
not be duplicates: ask.

**Split** (only on approval). The original keeps its name for the main idea;
new pages from `${CLAUDE_PLUGIN_ROOT}/templates/`; point each inbound link at the right page; log.

**Settle** (on the owner's word, or newer evidence that is clearly better).
For a `disputed` page from `brain introspect --open`: keep both claims with
their sources and dates, mark the losing one superseded with what settled it,
remove the `disputed` tag, and change a `contradicts` link that no longer
holds to plain text. Log `DATE maintain settle [[page]] -> <which claim
stands, why>`. A dispute nobody can settle stays disputed; say what evidence
would.

**Typed links.** Add `(supports:: [[X]])` and the rest only where the source
states the relation. Never infer one.

**Retype.** A page filed as the wrong type (an episode that explains an idea
is a concept in the wrong folder): rewrite it to the right contract and
template, move it, keep its name, check its links.

**Aliases.** Find pages whose acronyms, alternate spellings or common names
are missing from `aliases`; missing aliases are the main reason two pages
grow for one thing. Adding an alias is mechanical; do it.

**Tags.** `brain introspect --tags`: flag tags used once, near-synonyms and
anything outside the vocabulary; propose a consolidation.

**Rebuild the index.** From `brain check`'s `not_in_index` and the actual
pages: group by type and theme, one line of description each, gaps last.

**Move to dormant** (only on approval). Log, move the file to `dormant/`,
remove from the index, run `brain check`. Episodes that named the page keep
their links: `brain check` lists them as links to dormant pages, not broken.

## Output

```
Brain: <n> pages (<by type>) | links <n>, avg degree <n>, orphans <n>
Fixed: <list>
Needs a decision: <list, each with the recommended action>
```

## Calibration

A linter that merges on its own judgement destroys work; one that only reports
produces a list nobody acts on. Run weekly or after an import of twenty or
more, not after every ingest.
