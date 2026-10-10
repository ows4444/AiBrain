#!/usr/bin/env python3
"""Stop: a turn that recalled from the brain must leave a recall line in the log.

Recall lines are what strengthen pages and schedule rehearsal. If the model
forgets one, a useful page looks unused and is eventually proposed for
dormant/. This hook turns that rule from a guide into a sensor: when the turn
used a skill that reads pages (with or without the aibrain: prefix), or read a
page in cortex/ or dormant/ to answer without any skill and wrote no page,
and wrote no `DATE recall ... ->` line to hippocampus/log.md, Claude is asked
to log before stopping. The line is written by `brain log recall ...` (or
`brain log rehearse missed ...`: a rehearsal where every page was missed counts);
another log line (`explore`, `decide`) does not; the line may carry its time
of day after the date, as `brain log` writes it. A call whose result was an
error wrote nothing: `brain log` refusing a misspelt page, a hook refusing an
edit of the log. A line appended by a shell command still counts; when the
shell builds the date itself (`$(date +%F) recall q -> ...`) the log must hold
today's line with exactly that text. A command that only reads the log, or
`brain log --dry-run`, proves nothing. Fails open on any error, and never
fires twice in a row.
"""
import datetime
import json
import os
import re
import sys

from shared import ROOT, is_brain, note  # the brain may be above the folder the session started in

# Skills that read pages to produce something; matched with or without the plugin prefix (aibrain:ask).
RECALL_SKILLS = {"ask", "brief", "feel", "rehearse", "explore", "decide", "review-decision", "write", "focus"}
RECALL_COMMAND = re.compile(r"<command-name>/(?:[\w-]+:)?(?:%s)</command-name>" % "|".join(sorted(RECALL_SKILLS)))
ANY_COMMAND = re.compile(r"<command-name>/([\w:-]+)</command-name>")
RECALL_LINE = re.compile(r"\d{4}-\d{2}-\d{2} (?:\d{2}:\d{2} )?(?:recall|rehearse missed) .*->")
# The engine writes the line and checks it: `brain log recall <question> --pages ...`.
BRAIN_LOG = re.compile(r"(?:^|[\s;&|(/])brain\s+log\s+(?:recall|rehearse\s+missed)\b")
# The recall line a shell command writes when it builds the date itself.
SHELL_RECALL = re.compile(r"((?:recall|rehearse missed) [^\"'\n]*?->[^\"'\n]*)")
LOG = "hippocampus/log.md"
# Pages read here are memory; a turn that reads one and answers has recalled.
MEMORY_READ = re.compile(r"(?:^|/)(?:cortex|dormant)/[^/].*\.md$")
WRITES = ("Write", "Edit", "MultiEdit", "NotebookEdit")
TAIL_BYTES = 4_000_000  # of the transcript read, from its end (save_resume.py reads the same)


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
    """The entries of the turn that is ending: from the last prompt the owner typed, read from the transcript's end.

    A long session's transcript is many megabytes and this runs at every stop, so only its last
    TAIL_BYTES are read. The first line of a tail is cut short and dropped. A tail with no
    prompt in it means the turn began before it, so all of it belongs to the turn.
    """
    size = os.path.getsize(path)
    cut = size > TAIL_BYTES
    with open(path, "rb") as fh:
        fh.seek(max(0, size - TAIL_BYTES))
        lines = fh.read().decode("utf-8", "replace").splitlines()
    entries = [json.loads(line) for line in (lines[1:] if cut else lines) if line.strip()]
    starts = [i for i, e in enumerate(entries) if is_prompt(e)]
    return entries[starts[-1]:] if starts else (entries if cut else [])


def in_log_today(text):
    """True when the log holds today's line `DATE <text>`: the line a shell command built, not any line."""
    try:
        with open(os.path.join(ROOT, LOG), encoding="utf-8") as fh:
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


def check(entries):
    recalled = read_memory = wrote_pages = other_skill = False
    wrote_line, failed = [], set()  # the calls that would log a recall; the calls whose result was an error
    for entry in entries:
        for b in blocks(entry):
            if b.get("type") == "tool_result" and b.get("is_error") and b.get("tool_use_id"):
                failed.add(b["tool_use_id"])  # refused by a hook, or it failed: nothing was written
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
                if any(RECALL_LINE.search(str(w)) for w in written if w):
                    wrote_line.append(b.get("id"))
            if name == "Bash" and shell_logged(str(args.get("command", ""))):
                wrote_line.append(b.get("id"))
    # Reading memory to answer, with no skill and no page written, is a recall too.
    # A turn that writes pages (/ingest, /sleep, /maintain) or runs another skill reads to change, not to answer.
    recalled = recalled or (read_memory and not wrote_pages and not other_skill)
    return recalled, any(call not in failed for call in wrote_line)


def main():
    if not is_brain(ROOT):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
        if data.get("stop_hook_active"):
            sys.exit(0)
        recalled, logged = check(turn_entries(data["transcript_path"]))
    except Exception:
        note("check_recall", "error")
        sys.exit(0)
    if recalled and not logged:
        print("This turn recalled from the brain but logged no recall line. Run "
              "`brain log recall \"<the question as asked>\" --pages <page> ...` "
              "(CLAUDE.md > Log), naming the pages that contributed, then finish.", file=sys.stderr)
        note("check_recall", "recall", "recalled from the brain, no recall line in the log")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
