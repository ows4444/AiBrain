"""What needs the owner, in one read-only digest.

Usage:
    brain tend --check [--notify] [--json]

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

--notify also puts what waits on the screen, for a run nobody is watching
(`brain schedule` sets one): a notification through `osascript` on macOS, or
`notify-send` where there is one. Each thing is said once a day. The day's
first run says everything that waits in one line; a later run says only a
reminder that has come due since, which is what a reminder with a time of day
needs. What was said today is kept in .cache/notified.json, which is not the
brain's record: lose it and the day's line is said once more.
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from vaultlib import Vault  # noqa: E402

SHOWN = 5  # names printed on a line; --json has them all
NOTIFIED = os.path.join(".cache", "notified.json")  # what --notify has said today


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


def announcements(root, d):
    """The lines to put on the screen for the digest `d`, each thing that waits said once a day.

    The first run of a day gives one line for everything (none when nothing waits); a
    later one gives a line for each reminder that has come due since. What has been said
    is written to .cache/notified.json before the lines are returned.
    """
    path = os.path.join(root, NOTIFIED)
    try:
        with open(path, encoding="utf-8") as fh:
            said = json.load(fh)
    except (OSError, ValueError):
        said = {}
    due = [r["text"] for r in d["reminders"]]
    if said.get("date") != d["date"]:
        said = {"date": d["date"], "shown": []}
        lines = [", ".join(f"{label} {len(rows)}" for _, label, rows, _ in waiting_lines(d) if rows)] if d["needs"] else []
    else:
        lines = [f"Reminder: {text}" for text in due if text not in said["shown"]]
    said["shown"] = sorted(set(said["shown"]) | set(due))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(said, fh)
    return lines


def show(line, title="brain"):
    """Put one line on the screen; False where this machine has no way to (neither osascript nor notify-send)."""
    if shutil.which("osascript"):
        quoted = line.replace("\\", "\\\\").replace('"', '\\"')  # inside an AppleScript string
        command = ["osascript", "-e", f'display notification "{quoted}" with title "{title}"']
    elif shutil.which("notify-send"):
        command = ["notify-send", title, line]
    else:
        return False
    return subprocess.run(command, capture_output=True, text=True).returncode == 0


def arguments(ap):
    ap.add_argument("--check", action="store_true", help="the read-only digest; the only form there is")
    ap.add_argument("--notify", action="store_true", help="also put what waits on the screen, each thing once a day")


def run(root, args):
    if not args.check:
        raise Refused("brain tend: give --check for the read-only digest of what needs you. Encoding and "
                      "consolidating what is waiting is the /tend skill, started by the owner")
    found = digest(Vault(root))
    found["notified"] = [line for line in announcements(root, found) if show(line)] if args.notify else []
    return found


def waiting_lines(d):
    """(key, label, rows, hint) for each list of the digest, in the order they are printed."""
    return (
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


def render(d, args):
    if not d["needs"]:
        return f"tend check, {d['date']}: nothing needs you"
    out = [f"tend check, {d['date']}: waiting on you"]
    out += [f"  {label:<16}{len(d[key]):>3}: {some(rows)}" + (f"  ({hint})" if hint else "")
            for key, label, rows, hint in waiting_lines(d) if d[key]]
    return "\n".join(out)
