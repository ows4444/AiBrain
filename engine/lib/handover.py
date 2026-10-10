"""What the brain hands to another program, and what has come back.

Usage:
    brain handover [--json]

Nothing outside the brain is touched from here. A reminder whose work is
outside (code to change, a message to send) says which program it is for, and
may say in words how it is known to be done (hippocampus/intentions.md):

    - fix the login redirect when 2026-11-01 for `acline` until the page loads after sign-in

This lists each such reminder whose time has come and that nothing has
reported on, with its name: seven characters made from its words, its program,
its condition and its day, so they are others once any of them changes. With
each comes what the record gives the brain to feel about it (`brain feel`).

The program that takes one on (a runtime with approvals and an audit trail of
its own: ACLine is the first it is written for) reads this through `brain mcp`
and does the work its own way. What came of it returns as an input, like
everything the brain learns: a Markdown note left in inbox/, or at the door,
that begins

    ---
    handed: <the name>
    ---

and then says what was done, what was checked and how it ended. `/ingest`
encodes it as it encodes any note, as what that source says it did, and `brain
new` carries the name onto the episode. From then on the reminder waits on no
one, and that episode is the evidence it is closed on: what the brain did
through another program is something it remembers, not a second record of
state. Closing the line itself, `(done <day>: ...)`, stays with `/remind`.

It reads only. The brain starts no program and sends nothing: it says what
waits, and reads what comes back.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_affect import CALLING  # noqa: E402
from vault_intentions import stamp  # noqa: E402
from vaultlib import Vault  # noqa: E402

NOTE = ("to report on one: a Markdown note in the brain's inbox/ that begins `---`, `handed: <its name>`, `---`, then "
        "what was done, what was checked and how it ended")


def arguments(ap):
    pass


def run(root, args):
    vault = Vault(root)
    felt = {}
    for row in vault.feelings():  # the strongest first, so a reminder keeps its strongest
        if row["kind"] == "reminder" and row["feeling"] in CALLING:
            felt.setdefault(row["target"], row)
    rows = vault.handed_over()

    def said(h):
        feeling = felt.get(h["text"])
        return {"name": h["name"], "text": h["text"], "for": h["hand"], "until": h["hand_until"],
                "since": stamp(h["since"], h["timed"]), "episode": h["episode"],
                "felt": {"feeling": feeling["feeling"], "intensity": feeling["intensity"],
                         "why": feeling["causes"][0]["why"]} if feeling else None}

    return {"date": vault.today.isoformat(), "waiting": [said(h) for h in rows if h["state"] == "handed"],
            "returned": [said(h) for h in rows if h["state"] == "returned"],
            "scheduled": [said(h) for h in rows if h["state"] == "scheduled"], "note": NOTE}


def render(result, args):
    if not (result["waiting"] or result["returned"] or result["scheduled"]):
        return f"handover, {result['date']}: nothing is handed to another program"
    out = [f"handover, {result['date']}: {len(result['waiting'])} wait on another program, {len(result['returned'])} "
           f"reported on, {len(result['scheduled'])} not due yet"]
    for h in result["waiting"]:
        out.append(f"  {h['name']}  {h['text']}  (for {h['for']}; due since {h['since']})")
        out += [f"           done when: {h['until']}"] if h["until"] else []
        out += [f"           {h['felt']['feeling']} {h['felt']['intensity']:.2f}: {h['felt']['why']}"] if h["felt"] else []
    out += [f"  reported on: {h['text']} (for {h['for']}): {h['episode']}; `/remind` closes its line" for h in result["returned"]]
    out += [f"  not due yet: {h['text']} (for {h['for']}; {h['since']})" for h in result["scheduled"]]
    return "\n".join(out + ([result["note"]] if result["waiting"] else []))
