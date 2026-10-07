#!/usr/bin/env python3
"""Stop: a turn that recalled from the brain must leave a recall line in the log.

Recall lines are what strengthen pages and schedule rehearsal. If the model
forgets one, a useful page looks unused and is eventually proposed for
dormant/. This hook turns that rule from a guide into a sensor: when the turn
used a skill that reads pages (with or without the aibrain: prefix), or read a
page in cortex/ or dormant/ to answer without any skill and wrote no page,
and wrote no `DATE recall ... ->` line to hippocampus/log.md, Claude is asked
to log before stopping. Another log line (`explore`, `decide`) does not count;
a rehearsal where every page was missed (`DATE rehearse missed ->`) does. A
shell command may build the date itself (`$(date +%F) recall q -> ...`): then
the log must hold today's line with exactly that text. A command that only
reads the log proves nothing. Fails open on any error, and never fires twice
in a row.
"""
import datetime
import json
import os
import re
import sys

START = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))


def brain_root(start):
    """The nearest folder at or above `start` holding cortex/ and hippocampus/, else `start`."""
    here = start
    while True:
        if all(os.path.isdir(os.path.join(here, d)) for d in ("cortex", "hippocampus")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return start
        here = parent


# The brain may be above the folder the session started in (prefrontal/<name>/).
ROOT = brain_root(START)
# Skills that read pages to produce something; matched with or without the plugin prefix (aibrain:ask).
RECALL_SKILLS = {"ask", "rehearse", "explore", "decide", "write", "focus"}
RECALL_COMMAND = re.compile(r"<command-name>/(?:[\w-]+:)?(?:%s)</command-name>" % "|".join(sorted(RECALL_SKILLS)))
ANY_COMMAND = re.compile(r"<command-name>/([\w:-]+)</command-name>")
RECALL_LINE = re.compile(r"\d{4}-\d{2}-\d{2} (?:recall|rehearse missed) .*->")
# The recall line a shell command writes when it builds the date itself.
SHELL_RECALL = re.compile(r"((?:recall|rehearse missed) [^\"'\n]*?->[^\"'\n]*)")
LOG = "hippocampus/log.md"
# Pages read here are memory; a turn that reads one and answers has recalled.
MEMORY_READ = re.compile(r"(?:^|/)(?:cortex|dormant)/[^/].*\.md$")
WRITES = ("Write", "Edit", "MultiEdit", "NotebookEdit")


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


def turn_entries(path):
    with open(path, encoding="utf-8") as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    starts = [i for i, e in enumerate(entries) if is_prompt(e)]
    return entries[starts[-1]:] if starts else []


def in_log_today(text):
    """True when the log holds today's line `DATE <text>`: the line a shell command built, not any line."""
    try:
        with open(os.path.join(ROOT, LOG), encoding="utf-8") as fh:
            today = datetime.date.today().isoformat()
            return any(line.strip() == f"{today} {text.strip()}" for line in fh)
    except OSError:
        return False


def shell_logged(command):
    """A shell command that writes a recall line: literally dated, or dated by the shell and found in the log."""
    if RECALL_LINE.search(command):
        return True
    if not re.search(r">>|\btee\b", command):
        return False  # reading the log (tail, grep, cat) writes nothing
    return any(in_log_today(m) for m in SHELL_RECALL.findall(command))


def check(entries):
    recalled = logged = read_memory = wrote_pages = other_skill = False
    for entry in entries:
        for b in blocks(entry):
            if b.get("type") == "text":
                text = b.get("text", "")
                if RECALL_COMMAND.search(text):
                    recalled = True
                elif ANY_COMMAND.search(text):
                    other_skill = True
            if b.get("type") != "tool_use":
                continue
            name, args = b.get("name"), b.get("input") or {}
            path = str(args.get("file_path", "") or args.get("notebook_path", ""))
            if name == "Skill":
                if str(args.get("skill", "")).split(":")[-1] in RECALL_SKILLS:
                    recalled = True
                else:
                    other_skill = True
            if name == "Read" and MEMORY_READ.search(path.replace(os.sep, "/")):
                read_memory = True
            if name in WRITES and not path.endswith(LOG):
                wrote_pages = True
            if name in ("Write", "Edit", "MultiEdit") and path.endswith(LOG):
                written = [args.get("content"), args.get("new_string")]
                written += [e.get("new_string") for e in args.get("edits") or [] if isinstance(e, dict)]
                logged = logged or any(RECALL_LINE.search(str(w)) for w in written if w)
            if name == "Bash" and LOG in str(args.get("command", "")):
                logged = logged or shell_logged(str(args.get("command", "")))
    # Reading memory to answer, with no skill and no page written, is a recall too.
    # A turn that writes pages (/ingest, /sleep, /maintain) or runs another skill reads to change, not to answer.
    recalled = recalled or (read_memory and not wrote_pages and not other_skill)
    return recalled, logged


def main():
    if not all(os.path.isdir(os.path.join(ROOT, d)) for d in ("cortex", "hippocampus")):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if data.get("stop_hook_active"):
            sys.exit(0)
        recalled, logged = check(turn_entries(data["transcript_path"]))
    except Exception:
        sys.exit(0)
    if recalled and not logged:
        print("This turn recalled from the brain but logged no recall line. Append "
              "`DATE recall <short question> -> [[page]], ...` to hippocampus/log.md "
              "(CLAUDE.md > Log), naming the pages that contributed, then finish.", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
