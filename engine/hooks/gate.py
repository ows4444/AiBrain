#!/usr/bin/env python3
"""PreToolUse and PostToolUse: every wall of the event, in one process.

    gate.py pre    before a Write, Edit, MultiEdit, NotebookEdit or Bash call:
                   protect_senses, protect_log, protect_expected, validate_page (first pass)
    gate.py post   after a Write, Edit or MultiEdit:
                   validate_page (the file as written), scan_secrets

Starting Python costs more than any wall does, and a Write used to start six.
Each wall is still its own file and still runs on its own; this only calls them
in turn and answers once: every block is said, in the walls' order, and the
call is refused if there is one (shared.py holds the rules, the same for a wall
run alone).

A wall is loaded when its turn comes, inside the guard that runs it. So one that
cannot be loaded has raised, like one that fails halfway: it is logged, the call
is blocked when it writes into senses/ or cortex/decisions/, and the other walls
still give their answer. A wall that does not read the tool being called is not
loaded at all: a Bash command costs the senses wall and nothing else.
"""
import importlib
import sys

import shared
from shared import WRITES

# event -> its walls in order: (file, function, the tools it reads; None for whatever the event sends)
EVENTS = {
    "pre": (("protect_senses", "check", WRITES + ("NotebookEdit", "Bash")),
            ("protect_log", "check", WRITES),
            ("protect_policy", "check", WRITES + ("NotebookEdit", "Bash")),
            ("protect_expected", "check", WRITES),
            ("validate_page", "before", WRITES)),
    "post": (("validate_page", "written", None),
             ("scan_secrets", "check", None)),
}


def walls(event, tool):
    """(name, wall) for each wall of the event that reads this tool; loading the file is part of calling it."""
    def loaded(module, function):
        return lambda data: getattr(importlib.import_module(module), function)(data)

    return [(module, loaded(module, function)) for module, function, tools in EVENTS[event]
            if tools is None or tool in tools]


def main(argv):
    if len(argv) != 1 or argv[0] not in EVENTS:
        print(f"usage: gate.py {' | '.join(EVENTS)}   (the tool call as JSON on stdin)", file=sys.stderr)
        return 1  # not 2: a hook wired wrongly must not read as a wall refusing
    data = shared.call()
    if data is None:
        return 0
    return shared.settle(shared.judge(walls(argv[0], data.get("tool_name", "")), data))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
