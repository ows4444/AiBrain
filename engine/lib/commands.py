"""One way to call every command: `brain` uses it, and so can a test, a scheduler or another program.

A command is a module with three functions:

    arguments(parser)             adds the command's own arguments to an argparse parser
    run(root, args) -> dict       does the work and returns what it found or did, as plain data.
                                  `root` is the brain it works on (None for a command that needs
                                  none), `args` the parsed arguments
    render(result, args) -> str   that result as text for a person; "" prints nothing

`brain NAME ARGS` finds the brain, parses ARGS, calls `run` and prints `render`; with `--json`,
which every command takes, it prints the dict instead. So nothing a command says exists only as
text, and no caller has to parse what a person reads. From Python the same call is:

    from commands import Refused, call
    rows = call("recall", ["spacing effect", "--limit", "3"], root="/path/to/brain")["results"]

ARGS are the words the owner would type after the command's name; each module's docstring lists
them. A command that will not do what was asked raises Refused with the reason: `brain` prints it
on stderr and exits 1, or 2 for arguments it cannot read. A command whose result can itself be a
failure (`check`) also has `exit_code(result)`, which `brain` exits with.

The brain is $BRAIN_ROOT, else the nearest folder at or above the working directory that holds
cortex/ and hippocampus/. `brain` works from the brain's own folder, so a path among ARGS is read
from there; `call` leaves the working directory alone.
"""
import argparse
import importlib
import json
import os
import subprocess
import sys

LIB = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(LIB)
sys.path.append(os.path.join(ENGINE, "hooks"))  # `resume` is the PreCompact hook, run on request
from vault_model import find_brain, is_brain  # noqa: E402

# command -> (its module, whether it works on a brain, arguments it always has)
COMMANDS = {
    "check": ("link_check", True, {}),
    "introspect": ("introspect", True, {}),
    "search": ("search", True, {"mode": "search"}),
    "recall": ("search", True, {"mode": "recall"}),
    "since": ("timeline", True, {}),
    "log": ("log", True, {}),
    "index": ("index", True, {}),
    "fingerprint": ("fingerprint", True, {}),
    "graph": ("graph_export", True, {}),
    "export": ("export", True, {}),
    "cache": ("cache", True, {}),
    "errors": ("errlog", True, {}),
    "fetch": ("fetch", True, {}),
    "fit": ("fit", True, {}),
    "ground": ("ground", True, {}),
    "new": ("new_page", True, {}),
    "chats": ("chat_export_to_md", False, {}),
    "resume": ("save_resume", True, {}),
    "session": ("session", True, {}),
    "forget": ("forget", True, {}),
    "statusline": ("statusline", True, {}),
    "eval": ("eval", False, {}),
    "synth": ("synth", False, {}),
    "bench": ("bench", False, {}),
}
TEST_FLAGS = ("-v", "-q", "-f", "-b")


class Refused(Exception):
    """The command did not do what was asked, and says why. `code` is what `brain` exits with."""

    def __init__(self, reason, code=1):
        super().__init__(reason)
        self.code = code


class Arguments(argparse.ArgumentParser):
    """argparse, refusing where it would exit: a caller in the same process is told why, and goes on."""

    def error(self, message):
        raise Refused(f"{self.format_usage()}{self.prog}: error: {message}", code=2)


def brain_root():
    """The brain `brain` works on: $BRAIN_ROOT, else the nearest one at or above the working directory."""
    if os.environ.get("BRAIN_ROOT"):
        return os.path.abspath(os.environ["BRAIN_ROOT"])
    root = find_brain(os.getcwd())
    if root is None:
        raise Refused("brain: no brain here (no folder with cortex/ and hippocampus/ at or above this one)")
    return root


def prepare(name, argv, root, help_too=False):
    """(the command's module, its parsed arguments), or Refused: an unknown command, a root that is no brain."""
    if name not in COMMANDS:
        raise Refused(f"brain: unknown command '{name}'; run `brain help`")
    module_name, on_a_brain, always = COMMANDS[name]
    if on_a_brain and not os.path.isdir(root or ""):
        raise Refused(f"not a directory: {root}")
    if on_a_brain and not is_brain(root):
        raise Refused(f"not a brain: {root}")
    module = importlib.import_module(module_name)
    parser = Arguments(prog=f"brain {name}", add_help=help_too)
    module.arguments(parser)
    parser.add_argument("--json", action="store_true", help="the result as JSON, in place of the text")
    parser.set_defaults(**always)
    return module, parser.parse_args(list(argv))


def call(name, argv=(), root=None):
    """What `brain NAME ARGV` found or did on the brain at `root`, as a dict. Raises Refused."""
    module, args = prepare(name, argv, root)
    return module.run(root if COMMANDS[name][1] else None, args)


def tests(flags):
    """`brain test`: the engine's own tests, in a process of their own."""
    # Only the engine's own tests: an option that points discovery elsewhere (-s, -t, -p)
    # would run any Python file under a permission that allows `brain`.
    rest = list(flags)
    while rest:
        flag = rest.pop(0)
        if flag == "-k" and rest:
            rest.pop(0)
        elif flag not in TEST_FLAGS:
            raise Refused(f"brain test: '{flag}' is not accepted; use {', '.join(TEST_FLAGS)} or -k PATTERN")
    return subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", os.path.join(ENGINE, "tests"), *flags])


def main(argv, usage=""):
    """`brain ARGV`: print what the command says, and return the exit code."""
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage.strip())
        return 0
    name, rest = argv[0], argv[1:]
    try:
        if name == "test":
            return tests(rest)
        root = brain_root() if name in COMMANDS and COMMANDS[name][1] else None
        module, args = prepare(name, rest, root, help_too=True)
        if root:
            os.chdir(root)
        result = module.run(root, args)
    except Refused as why:
        print(why, file=sys.stderr)
        return why.code
    text = json.dumps(result, indent=2, ensure_ascii=False) if args.json else module.render(result, args)
    if text:
        print(text)
    return module.exit_code(result) if hasattr(module, "exit_code") else 0
