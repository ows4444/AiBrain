#!/usr/bin/env python3
"""PreToolUse: senses/ is sensory input. New files may land; existing ones are never edited.

One door out: `brain forget SOURCE --yes` removes an input and its episodes.
That command is never run on the model's say-so: this hook answers "ask", so
Claude Code puts it to the owner even where `brain` commands are allowed.

Needs nothing but the standard library and shared.py beside it: a wall must not
fail open because an import broke. Runs on its own, or as one of gate.py's walls.
The Bash check is best-effort; it catches the common ways a shell edits, removes
or overwrites a file (rm, mv, sed -i, >, tee, and cp/rsync onto an existing file).
"""
import os
import re
import shlex

import shared
from shared import ROOT, START

SENSES = os.path.join(ROOT, "senses")
MESSAGE = "Blocked: {} is in senses/, which is never edited after it lands. Write what you learned to cortex/ instead."

# Shell commands that change or remove an existing file in senses/.
# The folder itself counts (`rm -r senses`), a name that only contains the word does not (`senses-old`, `senses.md`).
SENSES_PATH = r"(?:\./|[\w./-]*/)?(?<![\w.-])senses(?![\w.-])"
# Each pattern stays on one line so prose in a heredoc does not trip it.
BASH_MUTATIONS = [
    rf"(?:^|[\s;&|(])(?:rm|unlink|truncate|shred)\s[^|;&\n]*{SENSES_PATH}",
    # Stepping into the folder first leaves no path on the command that removes: `cd senses && rm a.md`.
    rf"(?:^|[\s;&|(])(?:cd|pushd)\s+{SENSES_PATH}[^\n]*[\s;&|(](?:rm|unlink|truncate|shred|mv)\s",
    rf"(?:^|[\s;&|(])(?:sed|perl|ruby)\s+(?:-\S*\s+)*-i\S*[^|;&\n]*{SENSES_PATH}",
    rf"(?:^|[\s;&|(])mv\s+(?:-\S+\s+)*{SENSES_PATH}",
    rf"(?:^|[\s\d&])>>?\s*{SENSES_PATH}",
    rf"(?:^|[\s;&|(])tee\b(?:\s+-\S+)*\s+{SENSES_PATH}",
]


def in_senses(path):
    # macOS and Windows file systems are case-insensitive: Senses/ is senses/.
    fold = shared.fold
    a, b, readme = fold(shared.full_path(path)), fold(SENSES), fold(os.path.join(SENSES, "README.md"))
    # The folder's own README is documentation, not input.
    return (a == b or a.startswith(b + os.sep)) and a != readme


COPY_COMMANDS = {"cp", "mv", "rsync", "install", "ditto", "ln"}
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")"}


def copy_overwrites(command):
    """True when cp/mv/rsync/install/ditto/ln would replace a file that already exists in senses/.

    Copying a new file in is how input lands, so only an existing destination is blocked.
    Relative paths are taken from the folder the session started in, where Claude's shell starts.
    """
    for line in command.splitlines():
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            continue
        segment = []
        for token in tokens + [";"]:
            if token not in SEPARATORS:
                segment.append(token)
                continue
            words = [w for w in segment if "=" not in w.split("/")[0]]  # drop VAR=value prefixes
            segment = []
            if words and words[0] == "sudo":
                words = words[1:]
            if not words or os.path.basename(words[0]) not in COPY_COMMANDS:
                continue
            paths = [os.path.expanduser(w) for w in words[1:] if not w.startswith("-")]
            if len(paths) < 2 or not in_senses(paths[-1]):
                continue
            dest = paths[-1] if os.path.isabs(paths[-1]) else os.path.join(START, paths[-1])
            if os.path.isfile(dest):
                return True
            if os.path.isdir(dest) and any(
                    os.path.exists(os.path.join(dest, os.path.basename(s.rstrip("/")))) for s in paths[:-1]):
                return True
    return False


FORGET = re.compile(r"(?:^|[\s;&|(/])(?:brain\s+forget|forget\.py)\b[^|;&\n]*\s--yes\b")


def block(message):
    return shared.block("protect_senses", "senses", message)


def check(data):
    """The wall: a Verdict when the call would change an input, or runs the one command that removes one."""
    tool = data.get("tool_name", "")
    args = data.get("tool_input", {}) or {}

    if tool == "Bash":
        command = args.get("command", "")
        if FORGET.search(command):
            return shared.ask("protect_senses", "brain forget --yes removes an input from senses/ and the episodes "
                                                "written from it. Only the owner can approve that.")
        mutates = any(re.search(p, command, re.I | re.M) for p in BASH_MUTATIONS)
        if mutates or copy_overwrites(command):
            return block("Blocked: this command would change or remove a file in senses/, which is never "
                         "edited after it lands. Copying a new file in is fine; write what you learned to cortex/.")
        return None

    path = args.get("file_path") or args.get("notebook_path") or ""
    full = path if os.path.isabs(path) else os.path.join(START, path)
    if path and in_senses(path) and (tool != "Write" or os.path.exists(full)):
        return block(MESSAGE.format(os.path.relpath(os.path.realpath(full), ROOT)))
    return None


if __name__ == "__main__":
    shared.main(("protect_senses", check))
