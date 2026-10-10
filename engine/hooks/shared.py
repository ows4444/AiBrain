"""What the hooks share: where the brain is, what a tool call would write, and how a wall answers.

A wall is a function of one tool call (the JSON Claude Code hands a hook) that
returns nothing, or a Verdict: `block` (the call is refused, with a message for
the model) or `ask` (the owner is asked first). Each wall lives in its own file,
which still runs on its own (`python3 protect_log.py < call.json`); gate.py runs
every wall of an event in one process. Both go through `main` here, so a wall
answers the same either way:

    not a brain, or a call that cannot be read    nothing: exit 0
    a block                                       its message on stderr, one line in
                                                  the error log, exit 2
    an ask                                        the decision as JSON on stdout, exit 0
    a wall that raises                            one line in the error log; then the
                                                  call is blocked when it writes into
                                                  senses/ or cortex/decisions/, where
                                                  nothing can be undone, and let
                                                  through anywhere else

Standard library only, and nothing from engine/lib: a wall must not fail open
because an import broke. The error log is the one thing borrowed from there,
inside a guard, since a log that cannot be written is no reason to fail.

lib/ keeps its own copies of what is here, for the commands: vault_model's
find_brain, is_brain, fold_case, MEMORY_DIRS and PROJECTS_DIR, errlog's
brain_of, link_check's expected_of and status_of. A wall must not need the
library and the library must not need the hooks, so the copies stay; a test
holds them to the same answers (tests/test_walls.py).
"""
import collections
import contextlib
import json
import os
import re
import sys

HOOKS = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HOOKS, "..", "lib")
MEMORY_DIRS = ("cortex", "hippocampus")  # a folder holding both is a brain
PROJECTS_DIR = "prefrontal"
WRITES = ("Write", "Edit", "MultiEdit")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
# Quotes are legal YAML and the schema check strips them, so a wall must too.
STATUS = re.compile(r"^status:\s*[\"']?(\w+)", re.M)
EXPECTED = re.compile(r"^## Expected\s*\n(.*?)(?=^## |\Z)", re.S | re.M)
# The folder itself, not a name that only contains the word (`senses-old`, `senses.md`).
SENSES_WORD = re.compile(r"(?<![\w.-])senses(?![\w.-])", re.I)
IRREVERSIBLE = ("senses" + os.sep, os.path.join("cortex", "decisions", ""))  # what is written there is never undone

# block: the call is refused. ask: the owner is asked. `kind` is the rule that refused, for
# the error log (None: nothing more to log); `detail` is what the log keeps, when it is not the message.
Verdict = collections.namedtuple("Verdict", "decision source kind message detail")


def is_brain(root):
    """A brain is a folder holding both cortex/ and hippocampus/; the hooks stay silent anywhere else."""
    return all(os.path.isdir(os.path.join(root, d)) for d in MEMORY_DIRS)


def find_brain(start):
    """The nearest folder at or above `start` that is a brain, else None.

    A session opened in prefrontal/<name>/ is still inside its brain.
    """
    here = os.path.realpath(start)
    while True:
        if is_brain(here):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


# Where the session started, and its brain: that folder itself when it is in none, which
# is_brain then says, so the plugin can be enabled in projects that are not brains.
START = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
ROOT = find_brain(START) or START


def fold(path):
    """A path as the file system compares it: macOS and Windows take Cortex/ for cortex/."""
    return path.lower() if sys.platform == "darwin" else os.path.normcase(path)


def full_path(path):
    """The file a tool call names; a relative path is taken from where the session started."""
    return os.path.realpath(path if os.path.isabs(path) else os.path.join(START, path))


def from_root(path):
    """The file a tool call names, as a path from the brain's root."""
    return os.path.relpath(full_path(path), ROOT)


def text_after(tool, args, before):
    """The text a Write, Edit or MultiEdit would leave in a file that holds `before`."""
    if tool == "Write":
        return args.get("content", "")
    edits = args.get("edits") if tool == "MultiEdit" else [args]
    text = before
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def expected_of(text):
    """A decision's `## Expected` section, with its white space folded: what is frozen once it is decided."""
    m = EXPECTED.search(text)
    return " ".join(m.group(1).split()) if m else ""


def status_of(text):
    """The status in the frontmatter only: a `status:` line in the body is prose."""
    front = FRONTMATTER.match(text)
    m = STATUS.search(front.group(1)) if front else None
    return m.group(1) if m else None


def note(source, kind, detail=None):
    """One line in the error log (lib/errlog.py); with no detail, the exception being handled. Never raises."""
    with contextlib.suppress(Exception):  # the log must not add a way to fail
        sys.path.insert(0, LIB)
        from errlog import note as write
        write(source, kind, detail)


def block(source, kind, message, detail=None):
    return Verdict("block", source, kind, message, detail)


def ask(source, reason):
    return Verdict("ask", source, None, reason, None)


def irreversible(data):
    """True when the call writes where nothing can be undone: senses/ or cortex/decisions/.

    A shell command counts when it names senses, the one folder a wall reads commands for.
    """
    args = data.get("tool_input")
    args = args if isinstance(args, dict) else {}
    if data.get("tool_name") == "Bash":
        return bool(SENSES_WORD.search(str(args.get("command", ""))))
    path = str(args.get("file_path") or args.get("notebook_path") or "")
    return bool(path) and fold(from_root(path) + os.sep).startswith(IRREVERSIBLE)


def judge(walls, data):
    """The verdicts of these walls on one call, in their order; `walls` is (name, function of the call) pairs.

    A wall that raises is logged and then counted as a block or as nothing, by where the call writes.
    """
    verdicts = []
    for source, wall in walls:
        try:
            verdict = wall(data)
        except Exception:  # noqa: BLE001  whatever broke, the answer must still be one of the two
            note(source, "error")
            verdict = None
            if irreversible(data):
                verdict = block(source, None, f"Blocked: {source} failed before it could check this call, and nothing "
                                              "goes into senses/ or cortex/decisions/ unchecked: neither can be "
                                              "undone. `brain errors` shows what failed.")
        if verdict is not None:
            verdicts.append(verdict)
    return verdicts


def settle(verdicts):
    """Say what the verdicts come to, as Claude Code reads a hook; the exit code."""
    blocks = [v for v in verdicts if v.decision == "block"]
    for v in blocks:
        print(v.message, file=sys.stderr)
        if v.kind:
            note(v.source, v.kind, v.detail or v.message)
    if blocks:
        return 2
    if verdicts:  # what is left asks the owner
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                                 "permissionDecisionReason": verdicts[0].message}}))
    return 0


def call():
    """The tool call on stdin, or None: not in a brain, or not a call that can be read."""
    if not is_brain(ROOT):
        return None  # the plugin may be enabled in other projects
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return None  # input it cannot read is not a reason to stop a write
    return data if isinstance(data, dict) else None


def main(*walls):
    """Run as a hook: put the call on stdin to these walls and answer Claude Code. Exits."""
    data = call()
    sys.exit(settle(judge(walls, data)) if data is not None else 0)
