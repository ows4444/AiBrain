#!/usr/bin/env python3
"""Stop: a turn that recalled from the brain must leave a recall line in the log.

Recall lines are what strengthen pages and schedule rehearsal. If the model
forgets one, a useful page looks unused and is eventually proposed for
dormant/. This hook turns that rule from a guide into a sensor: when the turn
used a skill that reads pages (with or without the aibrain: prefix), or read
memory to answer without any skill and wrote no page, and wrote no
`DATE recall ... ->` line to hippocampus/log.md, Claude is asked to log before
stopping. Reading memory is any of: a `Read` of a page in cortex/ or dormant/;
`brain recall` or `brain search` in the shell, whose rows carry each page's
summary, enough to answer from; the same two tools of the brain's MCP server
(`mcp__<a name holding brain>__recall`, `..._search`), which the plugin gives
every session; a `Grep` or `Glob` under cortex/ or dormant/; a question handed
to an agent that answers from pages (ANSWERING_AGENTS, with or without the
plugin's prefix). Such an agent is read-only and returns the pages for its
caller to log, so the session owes the line: what the agent read is in its own
transcript, which this hook never opens. The line is owed by the turn in which
the agent's answer is there. An agent that ran in the turn answered in it. One
started in the background has only been launched (its call's result says so),
and that turn owes nothing; its answer comes back later as a task notification,
which starts a turn of its own and names the call, and that turn owes the line.
A search can also be a test of the engine or a look before a change, and the
hook cannot tell: so it asks once, and the model may answer that nothing was
answered from the pages and stop.

The line is written by `brain log recall ...` (or
`brain log rehearse missed ...`: a rehearsal where every page was missed counts);
another log line (`explore`, `decide`) does not; the line may carry its time
of day after the date, as `brain log` writes it. A call whose result was an
error wrote nothing: `brain log` refusing a misspelt page, a hook refusing an
edit of the log. A line appended by a shell command still counts; when the
shell builds the date itself (`$(date +%F) recall q -> ...`) the log must hold
today's line with exactly that text. A command that only reads the log, or
`brain log --dry-run`, proves nothing. Fails open on any error, and never
fires twice in a row.

A rehearsal is two turns: one puts the questions, the next grades what the
owner answered. Its lines are its grades, so the turn that starts one owes
none: it read the pages to ask, and the owner has recalled nothing yet. Its
limit: the turn that grades is asked for its line only when it reads the
pages again, and a rehearsal whose answers came with the command is not asked.
"""
import datetime
import json
import os
import re
import sys

from shared import ROOT, is_brain, note, transcript_tail  # the brain may be above the folder the session started in

# Skills that read pages to produce something; matched with or without the plugin prefix (aibrain:ask).
RECALL_SKILLS = {"ask", "brief", "feel", "rehearse", "explore", "decide", "review-decision", "write", "focus"}
# Of those, the ones whose line is written in a later turn, after the owner has answered: the turn that
# starts one reads pages to ask, as another skill reads them to change, and owes no line.
ASKS_FIRST = {"rehearse"}
OWES_A_LINE = RECALL_SKILLS - ASKS_FIRST
RECALL_COMMAND = re.compile(r"<command-name>/(?:[\w-]+:)?(?:%s)</command-name>" % "|".join(sorted(OWES_A_LINE)))
ANY_COMMAND = re.compile(r"<command-name>/([\w:-]+)</command-name>")
RECALL_LINE = re.compile(r"\d{4}-\d{2}-\d{2} (?:\d{2}:\d{2} )?(?:recall|rehearse missed) .*->")
# The engine writes the line and checks it: `brain log recall <question> --pages ...`.
BRAIN_LOG = re.compile(r"(?:^|[\s;&|(/])brain\s+log\s+(?:recall|rehearse\s+missed)\b")
# The recall line a shell command writes when it builds the date itself.
SHELL_RECALL = re.compile(r"((?:recall|rehearse missed) [^\"'\n]*?->[^\"'\n]*)")
LOG = "hippocampus/log.md"
# Pages read here are memory; a turn that reads one and answers has recalled.
MEMORY_READ = re.compile(r"(?:^|/)(?:cortex|dormant)/[^/].*\.md$")
# The same, for what only looks there: a folder of memory, or anything under one.
MEMORY_FOLDER = re.compile(r"(?:^|/)(?:cortex|dormant)(?:/|$)")
# The engine's own two ways to find pages, run in the shell. `brain log recall` writes the line and is not one.
BRAIN_READ = re.compile(r"(?:^|[\s;&|(/])brain\s+(?:recall|search)\b")
# The same two as tools of the brain's MCP server. A client names the server: here it is `plugin_aibrain_brain`.
MCP_READ = re.compile(r"mcp__.*brain.*__(?:recall|search)", re.I)
# The search tools, and the arguments of each that say where it looks (Grep's `pattern` is what it looks for).
SEARCHES = {"Grep": ("path", "glob"), "Glob": ("path", "pattern")}
WRITES = ("Write", "Edit", "MultiEdit", "NotebookEdit")
# The tool that hands work to an agent (`Task` is its older name), and the agents that answer from pages:
# they are read-only and return the pages, so a call of one is the caller's recall. The one place for the names.
AGENT_TOOLS = ("Agent", "Task")
ANSWERING_AGENTS = {"researcher"}
# How the answer of an agent started in the background comes back: an entry that opens with this tag and
# names the call that started the agent.
NOTIFICATION = re.compile(r"\A\s*<task-notification>.*?<tool-use-id>([^<\s]+)</tool-use-id>", re.S)
# What the model is told. It may answer that the turn was no recall: the hook sees a search, not what it was for.
ASKED = ("This turn recalled from the brain (a skill that reads pages, a page read, `brain recall` or `brain search`, "
         "a search under cortex/, a question handed to an agent that answers from pages: "
         f"{', '.join(sorted(ANSWERING_AGENTS))}) and logged no recall line. If it answered from the pages, run "
         "`brain log recall \"<the question as asked>\" --pages <page> ...` (CLAUDE.md > Log), naming the pages "
         "that contributed, then finish. If nothing was answered from them (a test of the engine, a look before a "
         "change), say so in one line and stop: this is asked once.")


def blocks(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def is_prompt(entry):
    """A user turn the owner typed, as opposed to a tool result fed back to the model."""
    # A loaded skill's instructions arrive as a user entry too (isMeta); the turn began before it.
    return (entry.get("type") == "user" and not entry.get("isMeta")
            and any(b.get("type") == "text" for b in blocks(entry)))


def read_entries(path):
    """(the entries at the end of a session's transcript, whether its beginning was left out).

    A long session's transcript is many megabytes and this runs at every stop, so only its end
    is read (shared.transcript_tail). The first line of a tail is cut short and dropped.
    """
    lines, cut = transcript_tail(path)
    return [json.loads(line) for line in (lines[1:] if cut else lines) if line.strip()], cut


def turn_of(entries, cut):
    """Of those entries, the turn that is ending: from the last prompt on.

    With no prompt among them the turn began before the part that was read, so all of it belongs to the turn.
    """
    starts = [i for i, e in enumerate(entries) if is_prompt(e)]
    return entries[starts[-1]:] if starts else (entries if cut else [])


def in_log_today(text):
    """True when the log holds today's line `DATE <text>`: the line a shell command built, not any line."""
    try:
        with open(os.path.join(ROOT, LOG), encoding="utf-8", errors="replace") as fh:
            today = re.compile(rf"{datetime.date.today().isoformat()} (?:\d{{2}}:\d{{2}} )?{re.escape(text.strip())}")
            return any(today.fullmatch(line.strip()) for line in fh)
    except OSError:
        return False


def shell_logged(command):
    """A shell command that writes a recall line: `brain log`, or an append to the log, literally dated or found there."""
    if BRAIN_LOG.search(command):
        return "--dry-run" not in command
    if LOG not in command:
        return False
    if RECALL_LINE.search(command):
        return True
    if not re.search(r">>|\btee\b", command):
        return False  # reading the log (tail, grep, cat) writes nothing
    return any(in_log_today(m) for m in SHELL_RECALL.findall(command))


def reads_memory(name, args):
    """True for a tool call that reads memory, as a turn does to answer from it.

    A page opened, the engine's recall or search (in the shell, or as tools of its MCP server), or a
    search tool pointed at cortex/ or dormant/.
    """
    def said(key):
        return str(args.get(key) or "").replace(os.sep, "/")

    if name == "Read":
        return bool(MEMORY_READ.search(said("file_path")))
    if name == "Bash":
        return bool(BRAIN_READ.search(str(args.get("command", ""))))
    if name in SEARCHES:
        return any(MEMORY_FOLDER.search(said(key)) for key in SEARCHES[name])
    return bool(MCP_READ.fullmatch(str(name)))


def hands_over(name, args):
    """True for a call that hands a question to an agent that answers from pages (ANSWERING_AGENTS)."""
    return name in AGENT_TOOLS and str(args.get("subagent_type") or "").split(":")[-1] in ANSWERING_AGENTS


def handed_over(entries):
    """The calls, anywhere in what was read of the transcript, that handed a question to such an agent, by id."""
    return {b.get("id") for entry in entries for b in blocks(entry)
            if b.get("type") == "tool_use" and hands_over(b.get("name"), b.get("input") or {})}


def check(entries, handed=frozenset()):
    """(whether the turn recalled from the brain, whether it logged a recall line), for the entries of one turn.

    `handed` is the calls that handed a question to an answering agent anywhere in the transcript
    (handed_over): a task notification that names one of them is that agent's answer, come back.
    """
    recalled = read_memory = wrote_pages = other_skill = False
    wrote_line, failed = [], set()  # the calls that would log a recall; the calls whose result was an error
    asked, launched = [], set()  # the calls of an answering agent in this turn; those only started, in the background
    for entry in entries:
        result = entry.get("toolUseResult")
        for b in blocks(entry):
            if b.get("type") == "tool_result" and b.get("is_error") and b.get("tool_use_id"):
                failed.add(b["tool_use_id"])  # refused by a hook, or it failed: nothing was written
            if b.get("type") == "tool_result" and isinstance(result, dict) and result.get("isAsync"):
                launched.add(b.get("tool_use_id"))  # its answer is not here yet: a later turn brings it
            if b.get("type") == "text":
                text = b.get("text", "")
                back = NOTIFICATION.match(text)
                if back and back.group(1) in handed:
                    read_memory = True  # what the agent found has come back: this turn answers from it
                if RECALL_COMMAND.search(text):
                    recalled = True
                elif ANY_COMMAND.search(text):
                    other_skill = True
            if b.get("type") != "tool_use":
                continue
            name, args = b.get("name"), b.get("input") or {}
            path = str(args.get("file_path", "") or args.get("notebook_path", ""))
            if name == "Skill":
                if str(args.get("skill", "")).split(":")[-1] in OWES_A_LINE:
                    recalled = True
                else:
                    other_skill = True
            if reads_memory(name, args):
                read_memory = True
            if hands_over(name, args):
                asked.append(b.get("id"))
            if name in WRITES and not path.endswith(LOG):
                wrote_pages = True
            if name in ("Write", "Edit", "MultiEdit") and path.endswith(LOG):
                written = [args.get("content"), args.get("new_string")]
                written += [e.get("new_string") for e in args.get("edits") or [] if isinstance(e, dict)]
                if any(RECALL_LINE.search(str(w)) for w in written if w):
                    wrote_line.append(b.get("id"))
            if name == "Bash" and shell_logged(str(args.get("command", ""))):
                wrote_line.append(b.get("id"))
    # Reading memory to answer, with no skill and no page written, is a recall too.
    # A turn that writes pages (/ingest, /sleep, /maintain) or runs another skill reads to change, not to answer.
    read_memory = read_memory or any(call not in launched for call in asked)  # an agent that answered in the turn
    recalled = recalled or (read_memory and not wrote_pages and not other_skill)
    return recalled, any(call not in failed for call in wrote_line)


def main():
    if not is_brain(ROOT):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if data.get("stop_hook_active"):
            sys.exit(0)
        entries, cut = read_entries(data["transcript_path"])
        recalled, logged = check(turn_of(entries, cut), handed_over(entries))
    except Exception:  # noqa: BLE001  whatever broke, the turn is never stopped by the sensor's own bug
        note("check_recall", "error")
        sys.exit(0)
    if recalled and not logged:
        print(ASKED, file=sys.stderr)
        note("check_recall", "recall", "recalled from the brain, no recall line in the log")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
