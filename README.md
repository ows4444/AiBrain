# AiBrain

A personal knowledge base modelled on how human memory works. You drop in
what you read, hear and think; Claude Code turns each item into a linked page,
consolidates repeated ideas into concepts, answers questions from your own
pages with citations, and quizzes you so you keep what matters.

It runs as a Claude Code plugin (`engine/`) over plain Markdown files, so the
whole brain also opens in Obsidian or any editor.

## Requirements

- macOS or Linux
- Python 3.9 or newer (standard library only, no `pip install`)
- git
- [Claude Code](https://claude.com/claude-code) (`claude`)

## Install

```sh
git clone <this-repo> aibrain    # or unzip it
cd aibrain
./install.sh
```

`install.sh` checks the requirements, registers the `aibrain` plugin with
Claude Code, turns on the pre-commit check, links `brain` into
`~/.local/bin`, and runs the engine's tests. Running it again is safe.

| Option          | What it does                                          |
|-----------------|-------------------------------------------------------|
| `--new DIR`     | Also create a fresh, empty brain in `DIR`             |
| `--no-plugin`   | Skip registering the Claude Code plugin               |
| `--no-hook`     | Skip the pre-commit check                             |
| `--no-path`     | Skip linking `brain` into `~/.local/bin`              |

If `~/.local/bin` is not on your PATH, add this to `~/.zshrc`:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

## First steps

```sh
cd aibrain
claude
```

Then, inside Claude Code:

1. `/start`: guided first run. It checks the setup, asks who you are and what
   your goals are, and walks you through one full cycle.
2. Put something in: a file in `senses/`, a quick note in `inbox/`, or a URL.
3. `/ingest`: turns it into an episode page linked to what you already have.
4. `/ask <question>`: answers from your pages, citing them.
5. `/sleep` now and then: consolidates episodes into concepts and insights.

## Commands

| Command      | Use it to                                                        |
|--------------|------------------------------------------------------------------|
| `/start`     | Set up and take the first tour                                   |
| `/owner`     | Fill in or update who you are, your goals and projects           |
| `/ingest`    | Encode new input (files, URLs, PDFs, transcripts, chat exports)  |
| `/tend`      | Clear the queues in one go: encode, consolidate, check, report   |
| `/sleep`     | Consolidate episodes into concepts, entities and insights        |
| `/ask`       | Answer from your pages, with citations                           |
| `/rehearse`  | Quiz yourself on what is due                                     |
| `/explore`   | Push an idea past what the brain holds                           |
| `/decide`    | Frame a choice, record what you expect, review it later          |
| `/focus`     | Create or check a project with one measurable goal               |
| `/write`     | Draft an outline, article, report or brief into `motor/`         |
| `/remind`    | "Remind me to X when Y"                                          |
| `/reflect`   | Weekly review: what was learned, what is unresolved              |
| `/health`    | Health metrics and trends                                        |
| `/maintain`  | Fix links, orphans, duplicates; rename, merge, split             |
| `/guard`     | Scan for secrets and private data; check what is safe to publish |
| `/forget`    | Remove one source: its input, its episodes and every citation    |
| `/commit`    | Check, then commit                                               |
| `/rollback`  | Show and undo what the last run changed                          |

If another plugin uses the same name, prefix it: `/aibrain:ask`.

The `brain` command works in any terminal (`brain --help`):

```sh
brain check           # broken links, schema, index drift
brain search QUERY    # pages by their words
brain recall QUERY    # words, then associations along links
brain since 2026-09-01
brain test            # the engine's own tests
brain cache           # the search cache: size; --rebuild or --clear
```

### Search cache

`brain search` and `brain recall` keep each page's search terms in a SQLite
cache at `.cache/search.sqlite` (Python's built-in `sqlite3`, nothing to
install). Each entry is keyed by a hash of the page's text, so an edited page
is always re-read and a deleted one dropped. The cache is never the source of
truth: delete it any time, and if it is missing, damaged or read-only, search
runs without it and gives the same results. Git ignores it.

On a 5,000-page brain, a recall takes about 0.45 s with the cache and 1.2 s
without. Set `BRAIN_CACHE=0` to turn it off.

## Layout

```
inbox/         quick notes; /ingest sweeps them into senses/
senses/        input as it arrived, never edited
hippocampus/   index, log, metrics, fingerprints, reminders
cortex/        long-term memory: episodes, concepts, entities, insights, decisions
prefrontal/    projects
dormant/       faded pages, still searchable
motor/         drafts, reports and exports
engine/        the plugin: skills, hooks, the brain command, tests
```

`CLAUDE.md` holds the rules every command follows.

## Uninstall

```sh
./uninstall.sh            # remove the plugin, pre-commit hook and brain link
./uninstall.sh --dry-run  # show what would be removed
```

Your pages are never touched. Delete the folder yourself if you want them gone.

## License

MIT
