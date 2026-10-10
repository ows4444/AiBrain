"""Time the brain's instruments on a synthetic brain: what a change to the engine costs or saves.

Usage:
    brain bench [--pages N] [--seed S] [--repeat R] [--json]

Builds a synthetic brain of N pages (default 1000; see `brain synth`) in a
temporary folder, runs each instrument against it, prints how long each took
and removes the folder. Three groups:
    commands  each `brain` command as a skill runs it: a new process, the
              page load included. Recall is timed with the search cache empty,
              then filled
    hooks     a process each: the wake-up briefing, the hooks one Write or Edit
              starts, and their sum
    vault     inside one process: loading the pages, and the views that grow
              fastest with the brain
With --repeat R each row is the fastest of R runs. A row shows `(exit N)` when
its command failed: that time means nothing.

The times are this machine's, today. Compare two runs on one machine, before
and after a change; never one run against a number written down elsewhere.
The synthetic pages draw from 40 words, so a view that compares words
(candidate_pairs) finds more matches than a real brain gives it.
Needs no brain and touches none.
"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402
from commands import Refused  # noqa: E402
import vaultlib  # noqa: E402

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN = os.path.join(ENGINE, "bin", "brain")
HOOKS = os.path.join(ENGINE, "hooks")
# Each command: its label, its arguments, and a command run first and not timed.
COMMANDS = (
    ("recall, cache empty", ("recall", "memory", "graph", "signal"), ("cache", "--clear")),
    ("recall, cache filled", ("recall", "memory", "graph", "signal"), None),
    ("search", ("search", "pricing", "market"), None),
    ("statusline", ("statusline",), None),
    ("check", ("check",), None),
    ("introspect", ("introspect",), None),
    ("introspect --due", ("introspect", "--due"), None),
    ("introspect --graph", ("introspect", "--graph"), None),
    ("since, this month", ("since", "MONTH"), None),
)
# What one Write or Edit starts, in the order of hooks.json.
WRITE_HOOKS = (("protect_senses.py",), ("protect_log.py",), ("protect_expected.py",), ("validate_page.py", "--pre"),
               ("validate_page.py",), ("scan_secrets.py",))
EDITED = os.path.join("cortex", "concepts", "concept-1.md")  # a page every brain of MIN_PAGES or more holds
MIN_PAGES = 10
CONCEPTS = 200


def fastest(repeat, action):
    """(seconds of the fastest of `repeat` runs of action(), what the last run returned)."""
    best, out = None, None
    for _ in range(repeat):
        start = time.perf_counter()
        out = action()
        took = time.perf_counter() - start
        best = took if best is None else min(best, took)
    return round(best, 3), out


def process(root, command, payload=None):
    """Run one engine process against the brain at `root`; its exit code."""
    env = dict(os.environ, BRAIN_ROOT=root, CLAUDE_PROJECT_DIR=root)
    # No input means an empty stdin, not an open one: the status line waits for what an open one might send.
    return subprocess.run([sys.executable, *command], input=payload or "", capture_output=True, text=True,
                          env=env, cwd=root).returncode


def command_rows(root, today, repeat):
    rows = []
    for label, args, first in COMMANDS:
        command = [BRAIN, *(today.strftime("%Y-%m") if a == "MONTH" else a for a in args)]
        seconds, code = None, 0
        for _ in range(repeat):
            if first:  # run before each timing, never timed itself
                process(root, [BRAIN, *first])
            took, code = fastest(1, lambda: process(root, command))
            seconds = took if seconds is None else min(seconds, took)
        rows.append({"what": label, "seconds": seconds, "exit": code})
    return rows


def hook_rows(root, repeat):
    # An edit that changes nothing: each hook does its whole check and lets it through.
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": os.path.join(root, EDITED),
                                                              "old_string": "# Concept 1", "new_string": "# Concept 1"}})
    seconds, code = fastest(repeat, lambda: process(root, [os.path.join(HOOKS, "wake_up.py")]))
    rows = [{"what": "wake_up (session start)", "seconds": seconds, "exit": code}]
    total = 0.0
    for hook in WRITE_HOOKS:
        seconds, code = fastest(repeat, lambda: process(root, [os.path.join(HOOKS, hook[0]), *hook[1:]], payload))
        rows.append({"what": " ".join(hook), "seconds": seconds, "exit": code})
        total += seconds
    return rows + [{"what": f"the {len(WRITE_HOOKS)} hooks of one Write or Edit, together", "seconds": round(total, 3),
                    "exit": 0}]


def vault_rows(root, today, repeat):
    seconds, vault = fastest(repeat, lambda: vaultlib.Vault(root, today=today))
    concepts = vault.of_type("concept")[:CONCEPTS]
    views = (("candidate_pairs", vault.candidate_pairs), ("near_duplicates", vault.near_duplicates),
             (f"confidence on {len(concepts)} concepts", lambda: [vault.confidence(p) for p in concepts]),
             ("betweenness", vault.betweenness))
    return [{"what": "Vault() load", "seconds": seconds}] + [{"what": label, "seconds": fastest(repeat, view)[0]}
                                                             for label, view in views]


def measure(pages=1000, seed=1, repeat=1, today=None):
    """Build the synthetic brain, time everything, remove it; the result as one dict."""
    today = today or datetime.date.today()
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(os.path.realpath(tmp), "brain")
        made = synth.build(root, pages, seed, today=today)
        return dict(made, seed=seed, repeat=repeat, commands=command_rows(root, today, repeat),
                    hooks=hook_rows(root, repeat), vault=vault_rows(root, today, repeat))


def render(result, args):
    lines = [f"bench: {result['pages']} synthetic pages, {result['links']} links, {result['log_lines']} log lines"
             + (f"; each row is the fastest of {result['repeat']} runs" if result["repeat"] > 1 else "")]
    for title, key in (("commands (a new process each, the page load included)", "commands"),
                       ("hooks (a process each)", "hooks"), ("inside the vault (one process)", "vault")):
        lines.append(title)
        lines += [f"  {row['seconds']:8.3f} s  {row['what']}" + (f"  (exit {row['exit']})" if row.get("exit") else "")
                  for row in result[key]]
    return "\n".join(lines)


def arguments(ap):
    ap.add_argument("--pages", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--repeat", type=int, default=1)


def run(root, args):
    if args.pages < MIN_PAGES or args.repeat < 1:
        raise Refused(f"brain bench: --pages is at least {MIN_PAGES} (a smaller brain may hold no concept to time), "
                      "--repeat at least 1")
    return measure(args.pages, args.seed, args.repeat)
