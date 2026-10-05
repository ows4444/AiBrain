#!/usr/bin/env python3
"""PreToolUse: senses/ is sensory input. New files may land; existing ones are never edited.

Deliberately dependency-free: a wall must not fail open because an import broke.
The Bash check is best-effort; it catches the common ways a shell edits, removes
or overwrites a file (rm, mv, sed -i, >, tee, and cp/rsync onto an existing file).
"""
import json
import os
import re
import shlex
import sys

ROOT = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
SENSES = os.path.join(ROOT, "senses")
MESSAGE = "Blocked: {} is in senses/, which is never edited after it lands. Write what you learned to cortex/ instead."

# Shell commands that change or remove an existing file in senses/.
SENSES_PATH = r"(?:\./|[\w./-]*/)?senses/"
# Each pattern stays on one line so prose in a heredoc does not trip it.
BASH_MUTATIONS = [
    rf"(?:^|[\s;&|(])(?:rm|unlink|truncate|shred)\s[^|;&\n]*{SENSES_PATH}",
    rf"(?:^|[\s;&|(])(?:sed|perl|ruby)\s+(?:-\S*\s+)*-i\S*[^|;&\n]*{SENSES_PATH}",
    rf"(?:^|[\s;&|(])mv\s+(?:-\S+\s+)*{SENSES_PATH}",
    rf"(?:^|[\s\d&])>>?\s*{SENSES_PATH}",
    rf"(?:^|[\s;&|(])tee\b(?:\s+-\S+)*\s+{SENSES_PATH}",
]


def in_senses(path):
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(ROOT, path))
    # macOS and Windows file systems are case-insensitive: Senses/ is senses/.
    a, b = os.path.normcase(full), os.path.normcase(SENSES)
    readme = os.path.normcase(os.path.join(SENSES, "README.md"))
    if sys.platform == "darwin":
        a, b, readme = a.lower(), b.lower(), readme.lower()
    # The folder's own README is documentation, not input.
    return (a == b or a.startswith(b + os.sep)) and a != readme


COPY_COMMANDS = {"cp", "mv", "rsync", "install", "ditto", "ln"}
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")"}


def copy_overwrites(command):
    """True when cp/mv/rsync/install/ditto/ln would replace a file that already exists in senses/.

    Copying a new file in is how input lands, so only an existing destination is blocked.
    Relative paths are taken from the project root, where Claude's shell starts.
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
            dest = paths[-1] if os.path.isabs(paths[-1]) else os.path.join(ROOT, paths[-1])
            if os.path.isfile(dest):
                return True
            if os.path.isdir(dest) and any(
                    os.path.exists(os.path.join(dest, os.path.basename(s.rstrip("/")))) for s in paths[:-1]):
                return True
    return False


def block(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def main():
    if not all(os.path.isdir(os.path.join(ROOT, d)) for d in ("cortex", "hippocampus")):
        sys.exit(0)  # not a brain: the plugin may be enabled in other projects
    try:
        data = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    tool = data.get("tool_name", "")
    args = data.get("tool_input", {}) or {}

    if tool == "Bash":
        command = args.get("command", "")
        mutates = any(re.search(p, command, re.I | re.M) for p in BASH_MUTATIONS)
        if mutates or copy_overwrites(command):
            block("Blocked: this command would change or remove a file in senses/, which is never "
                  "edited after it lands. Copying a new file in is fine; write what you learned to cortex/.")
        sys.exit(0)

    path = args.get("file_path") or args.get("notebook_path") or ""
    full = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if path and in_senses(path) and (tool != "Write" or os.path.exists(full)):
        block(MESSAGE.format(os.path.relpath(os.path.realpath(full), ROOT)))
    sys.exit(0)


if __name__ == "__main__":
    main()
