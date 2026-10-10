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

Optional: `pdftotext` (from poppler) and `tesseract`. With them
`brain extract` turns a PDF or a picture of text into an input without Claude
reading the file; without them Claude reads it, as before.

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
| `/character` | Say who the brain is to you: what it holds to and how it speaks  |
| `/ingest`    | Encode new input (files, URLs, PDFs, transcripts, chat exports)  |
| `/capture`   | Keep one line for later: a note in `inbox/`, encoded by `/ingest` |
| `/import`    | Bring an Obsidian vault into `senses/`, one input a note         |
| `/tend`      | Clear the queues in one go: encode, consolidate, check, report   |
| `/sleep`     | Consolidate episodes into concepts, entities and insights        |
| `/ask`       | Answer from your pages, with citations                           |
| `/brief`     | One page on a person, project or topic, every line cited         |
| `/feel`      | How a project, goal or page sits in the record, and why          |
| `/rehearse`  | Quiz yourself on what is due                                     |
| `/explore`   | Push an idea past what the brain holds                           |
| `/decide`    | Frame a choice and record what you expect, before the outcome    |
| `/review-decision` | Hold a decision's outcome against what you expected        |
| `/focus`     | Create or check a project with one measurable goal               |
| `/write`     | Draft an outline, article, report or brief into `motor/`         |
| `/remind`    | "Remind me to X when Y"                                          |
| `/reflect`   | Weekly review: what was learned, what is unresolved              |
| `/health`    | Health metrics and trends                                        |
| `/maintain`  | Fix links, orphans, duplicates; rename, merge, split             |
| `/guard`     | Scan for secrets and private data; check what is safe to publish |
| `/export`    | Check chosen pages, then write clean copies to `motor/export/`   |
| `/restore`   | Bring a faded page back from `dormant/`                          |
| `/forget`    | Remove one source: its input, its episodes and every citation    |
| `/commit`    | Check, then commit                                               |
| `/rollback`  | Show and undo what the last run changed                          |

If another plugin uses the same name, prefix it: `/aibrain:ask`.

The `brain` command works in any terminal (`brain --help`):

```sh
brain check           # broken links, schema, index drift
brain search QUERY    # pages by their words
brain recall QUERY    # words, then associations along links; --also "..." adds another wording of the question
brain since 2026-09-01
brain capture "a line" # keep it for later: a note in inbox/, which /ingest encodes
brain door FOLDER     # a synced folder as the way in from the phone: what is saved there comes into inbox/
brain inbox           # what waits in inbox/, sorted: ready, duplicate, credential, not text
brain extract FILE    # a PDF's or an image's text into senses/, if pdftotext or tesseract is installed
brain fit senses/FILE # what an input bears on, before it is encoded, and the reasons for a salience; /ingest runs it
brain import obsidian VAULT   # every note of a vault into senses/, once; --dry-run to look first
brain restore PAGE    # bring a faded page back from dormant/; the move is logged
brain ground FILE     # a draft: links, numbers and quotations with no page behind them
brain feel            # what the record gives the brain to feel, each feeling with its causes; none is stored
brain character       # who the brain is to you: what CHARACTER.md says it holds to and how it speaks
brain tend --check    # everything that needs you, in one read-only digest
brain schedule        # have this machine run that every few minutes, with no session open
brain mcp             # a read-only MCP server for other programs: search, recall, since, gaps, waiting, character
brain log recall "a question" --pages a-page   # one checked line in the log; skills run it
brain index           # rewrite the index's listing from the pages and their summaries
brain graph --format html   # the pages and their links as one page for a browser; no network, no server
brain test            # the engine's own tests
brain cache           # the search cache: size; --rebuild or --clear
brain errors          # what the hooks swallowed or refused, counted by source
brain bench           # how long each instrument takes on a synthetic brain (--pages N)
```

Every command takes `--json` and then prints what it found or did as data, in
place of the text.

### Error log

Hooks fail silent on purpose, so a bug in one would go unseen. Each crash a hook
swallows, and each write it refuses (senses, the log, frozen decision, schema,
secret, unlogged recall), leaves one line in `.cache/errors.log`. `brain errors` counts
them by source and kind (`--since DATE`, `--tail N`, `--json`, `--clear`). Read
it before refactoring: the most frequent line is the rule or hook to look at
first. The file is capped at 256 KB and git ignores it.


### Search cache

`brain search` and `brain recall` keep each page's search terms in a SQLite
cache at `.cache/search.sqlite` (Python's built-in `sqlite3`, nothing to
install). Each entry is keyed by a hash of the page's text, so an edited page
is always re-read and a deleted one dropped. The cache is never the source of
truth: delete it any time, and if it is missing, damaged or read-only, search
runs without it and gives the same results. Git ignores it.

On a 5,000-page brain, a recall takes about 0.45 s with the cache and 1.2 s
without. Set `BRAIN_CACHE=0` to turn it off.

### A check that runs without you

`brain tend --check` prints everything the brain is waiting on: input not
encoded, pages awaiting sleep, rehearsals and reminders due, decisions to
review, goals slipping, questions asked and not answered. It reads and never
writes, so it can run on a schedule. Three ways:

- **`brain schedule --set`, no model.** On macOS it installs a launchd job of
  your own user that runs `brain tend --check --notify` every 15 minutes
  (`--minutes N` for another interval) and at login. The day's first run puts
  everything that waits in one notification; a later one shows only a
  reminder that has come due since, so `when 2026-10-11 10:00` is on your
  screen within minutes of ten. `brain schedule` says what is set and
  `brain schedule --remove` takes it out. A machine that is asleep runs it on
  waking, so a reminder can be late. Elsewhere it installs nothing and prints
  the cron line that does the same.

- **cron, by hand.** Once a week, from the brain's folder, with the output
  sent wherever you read it. Mondays at nine, mailed:

  ```
  0 9 * * 1  cd /path/to/brain && brain tend --check | mail -s "brain" you@example.com
  ```

- **Claude Code.** Ask the `watcher` agent: "use the watcher agent to tell me
  what needs me". It runs the same command and reports it in a few lines. A
  scheduled routine (`/schedule`) can do that only for a brain its cloud
  session can read, which a brain kept on one machine is not.

Nothing here encodes, consolidates or rehearses for you: `/tend` does the
first two when you start it, and `/rehearse` is yours alone.

### A note taken away from the desk

Pick one folder that a sync service keeps on this machine and on your phone
(iCloud Drive, Dropbox, Syncthing), and open it as the door, once:

```sh
brain door "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Brain"
```

A note, a photo or a PDF saved there from anywhere is moved into `inbox/` when
the next session starts (`brain door --pull` does it by hand), and from there
it is a note like any other: `brain inbox` sorts it and `/ingest` encodes it.
Files are moved, not copied, so the folder is empty again. `brain door` alone
says where the door is and what waits; `brain door --close` closes it and
leaves the folder alone. The door is a link, `inbox/.door`, which git ignores:
a second machine opens its own.

### Other programs

`brain mcp` is a read-only [MCP](https://modelcontextprotocol.io) server over
the same instruments: `search`, `recall`, `since`, `gaps` and `waiting`
(what `brain tend --check` reports: what is due and what waits). Another client
(a desktop app, an editor) starts it and reads the brain with no hooks of its
own. In that client's configuration:

```json
{"mcpServers": {"brain": {"command": "python3",
                          "args": ["/path/to/aibrain/engine/bin/brain", "mcp"],
                          "env": {"BRAIN_ROOT": "/path/to/your/brain"}}}}
```

It has no tool that writes, and a page read through it leaves no recall line,
so it does not count as used. Claude Code starts it with the plugin; outside a
brain it offers no tools.

### Thresholds

Every number the brain judges by (how long before a concept is stale, where
recall stops, how fast rehearsals space out) has a default in the engine, and a
brain may hold its own. `brain introspect --usage` lists them all, each with
its range and what it does. To try one, `brain eval --set recall_floor=0.35`
runs the question set with it and writes nothing; with `--from-log` the
questions are the ones your own log holds, each asked again of the brain as it
was that day. To keep one, add a line under `## Overrides` in
`hippocampus/tuning.md`:

```
- recall_floor = 0.35 (2026-11-02: hit@5 0.81 to 0.88 on my own questions)
```

Every command reads it from then on; remove the line to go back to the default.
`brain check` fails on a name that is not a threshold or a value outside its
range. A brain from before this page has none and needs none: copy it from
`engine/templates/brain/hippocampus/tuning.md` when the first value is kept.

## Backup and a second machine

The brain is a git repository, and its history is its backup. `/commit`
checks it and commits; nothing else is needed on one machine.

To keep a copy elsewhere, add a remote and push it yourself:

```sh
git remote add origin <address of a repository only you can read>
git push -u origin main
```

A brain holds your notes, your goals and what you decided, so the remote
should be private. A session cannot push: `.claude/settings.json` denies
`git push` on purpose, because where a copy goes is your decision.

On another machine: `git clone` it, run `./install.sh` there, then
`brain check`. Pull before a session and push after it. `.cache/` is not in
git and rebuilds itself. If both machines added lines to the log, the
metrics or the fingerprints, the merge keeps both (`.gitattributes`), and the
log reads in the order things happened, since each line carries its time.
Two machines editing the same page still conflict as any file does: settle
it by hand, then `brain check`.

## Layout

```
inbox/         quick notes; /ingest sweeps them into senses/
senses/        input as it arrived, never edited
hippocampus/   index, log, metrics, fingerprints, reminders, tuning
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
