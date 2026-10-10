"""What needs the owner, in one read-only digest.

Usage:
    brain tend --check [--json]

Everything the brain is waiting on, on one screen: input not encoded and notes
in inbox/, episodes and decisions awaiting sleep, new input that says the
opposite of a page, pages due for rehearsal, reminders whose date has come,
decisions to review or to revisit, goals past their date or slipping, and the
questions asked and not answered (`brain introspect --gaps`). A line is printed
only when there is something on it, with how many and the first five; when
nothing needs the owner it says so in one line, which is what a scheduled run
then sends. `needs` in the JSON is how many of the lists hold anything.

It reads and never writes: no page, no log line, no index. So it is safe to
run unattended, on a schedule, by the `watcher` agent or by cron. Encoding and
consolidating what it lists is `/tend`, the skill, and that is started by the
owner; rehearsal is theirs alone. Without --check there is nothing to run:
this command has no form that writes.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from vaultlib import Vault  # noqa: E402

SHOWN = 5  # names printed on a line; --json has them all


def digest(vault):
    """Every list of what is waiting, as paths and plain rows, and `needs`: how many of them hold anything."""
    inbox = os.path.join(vault.root, "inbox")
    queue = vault.unconsolidated()
    goals = vault.goal_report()
    found = {
        "date": vault.today.isoformat(),
        "senses": vault.unencoded(),
        "inbox": sorted(f for f in (os.listdir(inbox) if os.path.isdir(inbox) else [])
                        if not f.startswith(".") and f != "README.md"),
        "sleep": [p.rel for p in queue],
        "contradictions": [{"episode": a.rel, "page": b.rel} for a, b in vault.contradiction_queue()],
        "rehearse": [p.rel for p in vault.due_for_rehearsal()],
        "reminders": [{"text": i["text"], "when": i["when"]} for i in vault.due_intentions()],
        "review": [{"page": p.rel, "review": p.fields["review"]} for p in vault.decisions_due()],
        "revisit": [d["page"] for d in vault.decision_report() if d["triggered"]],
        "late": [{"goal": g["goal"], "state": g["state"], "due": g["due"]} for g in goals
                 if g["state"] in ("past-due", "stale")],
        "at_risk": [{"goal": g["goal"], "days_left": g["days_left"]} for g in goals if g["at_risk"]],
        "gaps": [{"words": g["words"], "asked": g["asked"], "last": g["last"]} for g in vault.unanswered()],
    }
    found["needs"] = sum(1 for key, value in found.items() if key != "date" and value)
    return found


def some(names):
    return ", ".join(names[:SHOWN]) + (f" and {len(names) - SHOWN} more" if len(names) > SHOWN else "")


def arguments(ap):
    ap.add_argument("--check", action="store_true", help="the read-only digest; the only form there is")


def run(root, args):
    if not args.check:
        raise Refused("brain tend: give --check for the read-only digest of what needs you. Encoding and "
                      "consolidating what is waiting is the /tend skill, started by the owner")
    return digest(Vault(root))


def render(d, args):
    if not d["needs"]:
        return f"tend check, {d['date']}: nothing needs you"
    lines = (
        ("senses", "not encoded", d["senses"], "/ingest, or /tend"),
        ("inbox", "in the inbox", d["inbox"], "/ingest moves them into senses/"),
        ("sleep", "awaiting sleep", d["sleep"], "/sleep, or /tend"),
        ("contradictions", "contradictions", [f"{c['episode']} against {c['page']}" for c in d["contradictions"]],
         "/sleep records both sides"),
        ("rehearse", "due to rehearse", d["rehearse"], "/rehearse: yours alone"),
        ("reminders", "reminders due", [f"{r['text']} ({r['when']})" for r in d["reminders"]], ""),
        ("review", "to review", [f"{r['page']} ({r['review']})" for r in d["review"]], "/review-decision"),
        ("revisit", "to revisit", d["revisit"], "the event the decision named has come"),
        ("late", "goals past date", [f"{g['goal']} ({g['due']})" for g in d["late"]], "close, re-date or drop"),
        ("at_risk", "goals at risk", [f"{g['goal']} ({g['days_left']} days left)" for g in d["at_risk"]],
         "nothing done toward them lately"),
        ("gaps", "not answered", [f"{', '.join(g['words'])} ({g['asked']}x)" for g in d["gaps"]],
         "brain introspect --gaps"),
    )
    out = [f"tend check, {d['date']}: waiting on you"]
    out += [f"  {label:<16}{len(d[key]):>3}: {some(rows)}" + (f"  ({hint})" if hint else "")
            for key, label, rows, hint in lines if d[key]]
    return "\n".join(out)
