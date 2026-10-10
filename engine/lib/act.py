"""Run one action of the brain's own, if its policy allows it now.

Usage:
    brain act                     every action: its tier, and whether it may run with nobody there
    brain act NAME [--dry-run]    run it, or say why not

An action is a `brain` command with its arguments fixed, under a name
(lib/vault_policy.py). This is the one way an action runs when nobody is
there to ask: a schedule, a worker, another program. Each time it asks the
policy, with hippocampus/policy.md as it is at that moment:

    reads     it changes nothing: it runs
    changes   it changes the brain and git can undo it: it runs only when the
              page names it under `## Allowed`
    outside   it reaches outside the brain: refused, whatever the page says
    final     it cannot be undone: refused, whatever the page says

A name is taken as given, and nothing else is: no other spelling, no argument
of the caller's, no reason offered with it. A refusal exits 1 with the reason
and leaves one line in the error log (`brain errors`), kind `policy`.

An action that changed the brain leaves one line in the log, `act <name> ->
<what it said>`, written after it ran. One that only read leaves none, as
reading never does. --dry-run decides and runs nothing.

In a session, the skills and the owner's own word decide what is done, and
the walls hold what they hold; this command is for the run nobody watches.

A reminder may name an action (`... do `index``, hippocampus/intentions.md).
How one was carried out is steps in the log, each a line: `act started <its
words> -> a1: index, due since ...`, then `finished` or `failed`, or `waiting`
when the policy does not allow it. `advance` is the one writer of a step, and
writes only one the table allows from where the reminder stands
(vault_intentions.NEXT): nothing is finished that was not started.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import commands  # noqa: E402
import log  # noqa: E402
from commands import Refused  # noqa: E402
from errlog import note  # noqa: E402
from vault_intentions import NEXT, words  # noqa: E402
from vault_policy import ACTIONS, CHANGES, POLICY_PATH, READS, decide, policy_of  # noqa: E402
from vaultlib import Vault  # noqa: E402

SAID = 120  # characters of what the command said that go into its log line


def arguments(ap):
    ap.add_argument("name", nargs="?", help="the action; none lists them all")
    ap.add_argument("--dry-run", action="store_true", help="decide, and run nothing")


def listing(root):
    allowed = policy_of(root)
    rows = []
    for name, action in ACTIONS.items():
        may, why = decide(name, allowed)
        rows.append({"action": name, "tier": action.tier, "what": action.what, "may": may, "why": why})
    return {"policy": POLICY_PATH, "allowed": sorted(allowed), "actions": rows}


def run(root, args):
    if args.name is None:
        return listing(root)
    may, why = decide(args.name, policy_of(root))
    if not may:
        note("act", "policy", f"{args.name}: {why}", root=root)
        raise Refused(f"brain act: {args.name} was not run: {why}")
    action = ACTIONS[args.name]
    found = {"action": args.name, "tier": action.tier, "why": why, "ran": not args.dry_run, "failed": False,
             "said": "", "line": None}
    if args.dry_run:
        return found
    found["said"], found["failed"] = perform(root, args.name)
    if action.tier == CHANGES:
        found["line"] = logged(root, args.name, found["said"])
    return found


def perform(root, name):
    """(what the action's command said, whether its own verdict was a failure). It runs; whether it may is asked before."""
    command = ACTIONS[name].command
    module, parsed = commands.prepare(command[0], command[1:], root)
    result = module.run(root, parsed)
    return module.render(result, parsed), bool(getattr(module, "exit_code", lambda _: 0)(result))


def first_line(said):
    """What a command said, as it goes into a log line: its first line, without link brackets, cut short."""
    return (said.splitlines() or ["done"])[0].replace("[[", "").replace("]]", "")[:SAID]


def advance(root, text, step, note=""):
    """Write the next step of how a reminder is carried out, and return the line; Refused when it may not follow.

    `text` is the reminder's words, `step` one of started, finished, failed, waiting. The
    table says what may follow where the reminder stands, as the log has it: a step is
    never written twice, and nothing ends that did not begin. A start names its attempt
    (a1, a2, ...), and the step that ends it carries the same name.
    """
    vault = Vault(root)
    found = [i for i in vault.carried_out() if words(i["text"]) == words(text)]
    if not found:
        raise Refused(f"no open reminder with an action says '{text}'")
    stands = found[0]["stands"]
    if step not in NEXT[stands["state"]]:
        raise Refused(f"'{found[0]['text']}' is {stands['state']}: it cannot be {step} now "
                      f"(what may follow: {', '.join(NEXT[stands['state']]) or 'nothing'})")
    attempt = f"a{stands['attempts'] + 1}" if step == "started" else stands["attempt"]
    said = first_line(note) if note else ""
    result = said if step == "waiting" else f"{attempt}: {said}" if said else attempt
    try:
        return log.write(root, "act", f"{step} {found[0]['text']}", result=result)["line"]
    except Refused:  # what was said cannot go into a line: the step is logged all the same
        return log.write(root, "act", f"{step} {found[0]['text']}", result="" if step == "waiting" else attempt)["line"]


def logged(root, name, said):
    """The line the log now holds for an action that ran: what it said, or `done` if that cannot go into a line."""
    try:
        return log.write(root, "act", name, result=first_line(said))["line"]
    except Refused:  # the action has run: it is logged whatever its own words were
        return log.write(root, "act", name, result="done")["line"]


def exit_code(result):
    return 1 if result.get("failed") else 0


def render(result, args):
    if "actions" in result:
        state = lambda a: "runs" if a["tier"] == READS else "never" if a["tier"] != CHANGES else \
            "allowed" if a["may"] else "not allowed"  # noqa: E731
        return "\n".join(
            ["actions, and whether each may run with nobody there:"]
            + [f"  {state(a):<12} {a['action']:<12} {a['tier']:<8} {a['what']}" for a in result["actions"]]
            + ["reads: it changes nothing, and always runs. changes: it runs only where a line `- name (why)` under "
               f"`## Allowed` in {result['policy']}, written by the owner, allows it; git can undo it.",
               "outside, final: it reaches outside the brain, or cannot be undone. No line can allow it."])
    if not result["ran"]:
        return f"act: {result['action']} would run ({result['why']}); nothing was run"
    return "\n".join(filter(None, [result["said"], f"act: {result['action']} ran ({result['why']})"
                                   + (", and it failed" if result["failed"] else "")
                                   + (f"; logged: {result['line']}" if result["line"] else "")]))
