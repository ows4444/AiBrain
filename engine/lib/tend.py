"""What needs the owner, in one read-only digest.

Usage:
    brain tend --check [--notify] [--json]

Everything the brain is waiting on, on one screen: input not encoded and notes
in inbox/, episodes and decisions awaiting sleep, new input that says the
opposite of a page, pages due for rehearsal, reminders whose date has come
(one the brain carries out itself says its action and where it stands), the
ones among those that wait for the owner's yes with the name each goes by,
decisions to review or to revisit, goals past their date or slipping, and the
questions asked and not answered (`brain introspect --gaps`). A line is printed
only when there is something on it, with how many and the first five; when
nothing needs the owner it says so in one line, which is what a scheduled run
then sends. `needs` in the JSON is how many of the lists hold anything.

What the record gives most to feel about comes first (`brain feel`): a goal
ten days past its date before an input not yet encoded. Such a line ends with
the feeling, how strong it is and its cause, in brackets; `felt` in the JSON
has it for each list. The lists are the same and all of them are printed: a
feeling moves the order and hides nothing. A line nothing is felt about keeps
its place among the others like it, after the ones something is.

It reads and never writes: no page, no log line, no index. So it is safe to
run unattended, on a schedule, by the `watcher` agent or by cron. Encoding and
consolidating what it lists is `/tend`, the skill, and that is started by the
owner; rehearsal is theirs alone. Without --check there is nothing to run:
this command has no form that writes.

--notify also puts what waits on the screen, for a run nobody is watching
(`brain schedule` sets one): a notification through `osascript` on macOS, or
`notify-send` where there is one. Each thing is said once a day. The day's
first run says everything that waits in one line, in the digest's order, so
what is felt most is named first; a later run says only a
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
from vaultlib import CALLING, Vault  # noqa: E402

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
        "reminders": [dict({"text": i["text"], "when": i["when"]},
                           **({"do": i["do"], "state": i["stands"]["state"]} if i["stands"] else {}),
                           **({"for": i["hand"]} if i["hand"] else {}))
                      for i in vault.due_intentions()],
        "review": [{"page": p.rel, "review": p.fields["review"]} for p in vault.decisions_due()],
        "revisit": [d["page"] for d in vault.decision_report() if d["triggered"]],
        "proposals": vault.proposals(),
        "late": [{"goal": g["goal"], "state": g["state"], "due": g["due"]} for g in goals
                 if g["state"] in ("past-due", "stale")],
        "at_risk": [{"goal": g["goal"], "days_left": g["days_left"]} for g in goals if g["at_risk"]],
        "gaps": [{"words": g["words"], "asked": g["asked"], "last": g["last"]} for g in vault.unanswered()],
    }
    found["needs"] = sum(1 for key, value in found.items() if key != "date" and value)
    found["felt"] = felt_about(vault, found)
    return found


def felt_about(vault, d):
    """{list: {feeling, intensity, target, why}}: for each list of the digest, what is felt most toward something on it.

    Of the feelings that ask for something to be done; satisfaction asks for nothing. A
    list nothing is felt about is not in it.
    """
    felt = {}
    for row in vault.feelings():  # the strongest first, so a target keeps its strongest
        if row["feeling"] in CALLING:
            felt.setdefault((row["kind"], row["target"]), row)
    stands_for = {"contradictions": [("page", c["page"]) for c in d["contradictions"]],
                  "rehearse": [("page", rel) for rel in d["rehearse"]],
                  "reminders": [("reminder", r["text"]) for r in d["reminders"]],
                  "review": [("page", r["page"]) for r in d["review"]],
                  "revisit": [("page", rel) for rel in d["revisit"]],
                  "late": [("goal", g["goal"]) for g in d["late"]],
                  "at_risk": [("goal", g["goal"]) for g in d["at_risk"]],
                  "gaps": [("gap", ", ".join(g["words"])) for g in d["gaps"]]}
    out = {}
    for key, targets in stands_for.items():
        rows = [felt[t] for t in targets if t in felt]
        if rows:
            top = max(rows, key=lambda r: r["intensity"])
            out[key] = {"feeling": top["feeling"], "intensity": top["intensity"], "target": top["target"],
                        "why": top["causes"][0]["why"]}
    return out


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
    """(key, label, rows, hint) for each list of the digest, in the order they are printed: the most felt first."""
    return tuple(sorted(lines_in_turn(d), key=lambda line: -d["felt"].get(line[0], {}).get("intensity", 0)))


def lines_in_turn(d):
    """The lists in the order the work goes: what came in, what sleep owes, what is the owner's, what was asked."""
    return (
        ("senses", "not encoded", d["senses"], "/ingest, or /tend"),
        ("inbox", "in the inbox", d["inbox"], "/ingest moves them into senses/"),
        ("sleep", "awaiting sleep", d["sleep"], "/sleep, or /tend"),
        ("contradictions", "contradictions", [f"{c['episode']} against {c['page']}" for c in d["contradictions"]],
         "/sleep records both sides"),
        ("rehearse", "due to rehearse", d["rehearse"], "/rehearse: yours alone"),
        ("reminders", "reminders due", [f"{r['text']} ({r['when']}" + (f"; do {r['do']}: {r['state']}" if "do" in r else "")
                                        + (f"; for {r['for']}, not reported on" if "for" in r else "") + ")"
                                        for r in d["reminders"]], ""),
        ("proposals", "wait for a yes", [f"{p['text']} (do {p['do']}; yes {p['yes']})" for p in d["proposals"]],
         "yours alone: `- <yes> <today>` under `## Once` in hippocampus/policy.md runs one once"),
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
    out = [f"tend check, {d['date']}: waiting on you" + (", what is felt most first" if d["felt"] else "")]
    out += [f"  {label:<16}{len(d[key]):>3}: {some(rows)}" + (f"  ({hint})" if hint else "") + felt_said(d["felt"].get(key))
            for key, label, rows, hint in waiting_lines(d) if d[key]]
    return "\n".join(out)


def felt_said(felt):
    """`  [worry 0.81: Move, 10 days past its date]` after a line something is felt about; "" after any other."""
    if not felt:
        return ""
    name = os.path.splitext(os.path.basename(felt["target"]))[0]  # a page by its file name; any other target is its words
    return f"  [{felt['feeling']} {felt['intensity']:.2f}: {name}, {felt['why']}]"
