#!/usr/bin/env python3
"""SessionStart: orient the brain on waking. What the senses hold, what awaits
sleep, what is due for rehearsal or an outcome review, what happened last.
With an OWNER.md, the briefing opens with it: who the owner is, how to talk to
them and their goals reach every session this way, so the root CLAUDE.md does
not change when a goal does. With a CHARACTER.md, who the brain is to them
follows: what it holds to and how it speaks, under the rules.
Four lines, every session, and more only when something needs the owner: notes
waiting in inbox/ (what waited at the door, `brain door`, is brought in first);
new input contradicting a page; a reminder whose date has come; a goal past
its date, gone stale, with no pages behind it or slipping; the mood of the
last weeks and the one thing the record gives most to feel about (`brain feel`);
the pages the last questions and live projects point to; the calibration
checkpoint reached; a note left before a compaction (save_resume.py) that is
newer than the log; or, in a brain that hosts its own engine, hooks running
from a plugin version older than engine/, one its repository no longer holds,
or another folder's engine.

The four counts are also what `brain statusline` shows all session, outside
the context; they stay here because the model reads this and not that.

The lines are built by `briefing`, which only reads. `main` brings in what
waits at the door before it prints them; run as `wake_up.py --look` it only
looks there and moves nothing, which is how `brain introspect --context` and
`brain bench` measure the briefing. Each log line under "Last activity" is cut
to LINE characters: the briefing is paid at every session start.

It never stops a session from starting: a briefing that breaks off says so in
its last line and leaves one line in the error log (`brain errors`).
"""
import datetime
import os
import re
import subprocess
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import character  # noqa: E402
import door  # noqa: E402
import errlog  # noqa: E402
from vaultlib import (LOG_PATH, OWNER_FILE, Vault, as_written, character_lines, find_brain, inbox_notes,  # noqa: E402
                      is_brain, owner_text, under_title)

# The brain may be above the folder the session started in (prefrontal/<name>/).
ROOT = find_brain(ROOT) or ROOT

SHOW = 5
LINE = 160       # of one log line under "Last activity", the characters shown: the log keeps the whole line
LOOK = "--look"  # the briefing with nothing moved: what waits at the door is counted and stays there


def recent_log(vault):
    """The log's lines in the order things happened. Recall lines are frequent and carry no news, so the briefing skips them."""
    return [as_written(e) for e in vault.events if e.op != "recall"]


def cut(line):
    """A log line as the briefing shows it: whole, or its first LINE characters with a mark that it goes on."""
    return line if len(line) <= LINE else line[:LINE - 1].rstrip() + "…"


def purpose_line(vault):
    """Goals that need the owner, or nothing."""
    goals = vault.goal_report()
    late = [g["goal"] for g in goals if g["state"] in ("past-due", "stale")]
    bare = [g["goal"] for g in goals if g["state"] == "open" and not g["pages"]]
    slipping = [g["goal"] for g in goals if g["at_risk"] and g["pages"]]
    if not late and not bare and not slipping:
        return ""
    parts = ([f"{len(late)} past due ({', '.join(late[:2])}): close, re-date or drop"] if late else []) + \
            ([f"{len(bare)} with no pages behind them ({', '.join(bare[:2])})"] if bare else []) + \
            ([f"{len(slipping)} due soon with nothing done lately ({', '.join(slipping[:2])})"] if slipping else [])
    return "Goals: " + " | ".join(parts)


def inbox_line(came):
    """What waits in inbox/ and at the door (`brain door`).

    `came` is what the door gave when it was pulled (door.pull: `brought`), or what it holds when it
    was only looked at (door.look: `waiting`). Nothing is moved here.
    """
    waiting = inbox_notes(ROOT)
    through = f", {len(came['brought'])} of them just in through the door" if came.get("brought") else ""
    lines = [f"Inbox: {len(waiting)} notes waiting{through} (/ingest moves them into senses/)"] if waiting else []
    if came["unreachable"]:
        lines.append(f"Door: it leads to {came['door']}, which cannot be read (`brain door FOLDER` moves it)")
    elif came["left"]:
        lines.append(f"Door: {len(came['left'])} left there, not brought in ({', '.join(came['left'][:SHOW])})")
    if came.get("waiting"):
        lines.append(f"Door: {len(came['waiting'])} notes waiting there (the next session brings them in)")
    return "\n".join(lines)


def attention_lines(vault):
    """Prediction errors, reminders due and the pages to have at hand; each only when there is one."""
    lines = []
    errors = vault.contradiction_queue()
    if errors:
        lines.append(f"Prediction errors: {len(errors)} new inputs contradict a page ("
                     + ", ".join(f"{a.stem} vs {b.stem}" for a, b in errors[:SHOW // 2 + 1]) + "): /sleep records both")
    due = vault.due_intentions()
    if due:
        lines.append(f"Reminders: {len(due)} due (" + "; ".join(i["text"] for i in due[:SHOW // 2 + 1]) + ")")
    asked = vault.proposals()
    if asked:
        lines.append(f"Your yes: {len(asked)} wait for it (" + "; ".join(f"{p['text']}: do {p['do']}, yes {p['yes']}"
                                                                        for p in asked[:SHOW // 2 + 1])
                     + "): written by you in hippocampus/policy.md, `- <yes> <today>` under `## Once` for this once, "
                       "`- <action>` under `## Allowed` for always")
    hand = vault.at_hand()
    if hand:
        lines.append("At hand: " + ", ".join(p.stem for p in hand))
    return lines


def mood_line(vault):
    """The mood of the last weeks and the one thing felt most, with its cause; nothing when nothing is felt now."""
    felt = vault.feelings()
    if not felt:
        return ""
    top = felt[0]
    return (f"Mood: {vault.mood_said()} | most felt: {top['feeling']} {top['intensity']:.2f}, {top['target']}: "
            f"{top['causes'][0]['why']} (`brain feel` has the rest)")


def checkpoint_line(vault):
    c = vault.usage()["checkpoint"]
    if not c["reached"] or c["reviewed"]:
        return ""
    return (f"Checkpoint: {c['inputs']} inputs and {c['sleeps']} sleeps: time for the calibration review "
            "(brain introspect --usage and the metrics; `brain log health calibration --result ...` when done)")


def owner_lines():
    """OWNER.md without its heading and its note on how the file is used, or nothing."""
    if not os.path.exists(os.path.join(ROOT, OWNER_FILE)):
        return []
    body = under_title(owner_text(ROOT))
    lines = [("Goals:" if re.match(r"##+ Goals", line) else "  " + line) for line in body.splitlines() if line.strip()]
    return [f"Owner ({OWNER_FILE}):"] + lines if lines else []


def resume_line():
    """Points at the note save_resume.py left, while nothing has been logged since it was written."""
    log = os.path.join(ROOT, LOG_PATH)
    logged = os.path.getmtime(log) if os.path.exists(log) else 0
    notes = [os.path.join(ROOT, ".cache", "resume.md")]
    prefrontal = os.path.join(ROOT, "prefrontal")
    if os.path.isdir(prefrontal):
        notes += [os.path.join(prefrontal, d, "process", "resume.md") for d in sorted(os.listdir(prefrontal))]
    fresh = [n for n in notes if os.path.exists(n) and os.path.getmtime(n) > logged]
    if not fresh:
        return ""
    newest = max(fresh, key=os.path.getmtime)
    return f"Resume: read {os.path.relpath(newest, ROOT)} first; it says where the work stood before the compaction"


def engine_line():
    """One line when the running hooks are not the engine/ in this brain, or nothing.

    An installed plugin runs from a cache folder named after the commit it was
    installed at; engine/ may have moved on since, or hold uncommitted changes,
    or the repository may no longer hold that commit at all.
    A copied brain can also still be running the engine of the folder it was
    copied from, where edits to its own engine/ change nothing.
    """
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    own = os.path.join(ROOT, "engine")
    if not plugin_root or not os.path.isdir(os.path.join(own, ".claude-plugin")):
        return ""
    loaded = os.path.basename(os.path.normpath(plugin_root))
    if not re.fullmatch(r"[0-9a-f]{7,40}", loaded):
        if os.path.realpath(plugin_root) == os.path.realpath(own):
            return ""
        return (f"Engine: hooks and `brain` run from {plugin_root}, not this brain's engine/ "
                "(changes here have no effect until the plugin is installed from this folder)")

    def git(*args):
        return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=5)

    try:
        # A commit this repository does not hold (its history was rewritten since, or the plugin came from
        # another clone) cannot be compared, and that is said: passed over in silence, it hid the engine
        # that had moved furthest. With one it holds, 1 means the trees differ.
        known = git("cat-file", "-e", loaded + "^{commit}").returncode == 0
        changed = known and git("diff", "--quiet", loaded, "HEAD", "--", "engine").returncode == 1
        head = git("log", "-1", "--format=%h", "--", "engine").stdout.strip()  # "" where there is no repository
        dirty = bool(git("status", "--porcelain", "--", "engine").stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return ""
    parts = ([f"running {loaded[:7]}, engine/ is at {head}"] if changed and head else []) + \
            ([f"running {loaded[:7]}, a commit this repository does not hold, so engine/ cannot be compared with it"]
             if head and not known else []) + \
            (["engine/ has uncommitted changes"] if dirty else [])
    if not parts:
        return ""
    return (f"Engine: {'; '.join(parts)} ({'commit, then ' if dirty else ''}"
            "run claude plugin update aibrain@aibrain, then restart)")


def briefing(vault, came):
    """The briefing, a line at a time. It only reads: `came` is what the door gave or holds, as `main` found it."""
    pending, recent = vault.unencoded(), recent_log(vault)
    more = "…" if len(pending) > SHOW else ""
    yield from owner_lines() + character.said(character_lines(ROOT))
    yield f"Today: {datetime.date.today().isoformat()}"
    yield f"Unencoded in senses/: {len(pending)}" + (f" ({', '.join(pending[:SHOW])}{more})" if pending else "")
    queue = vault.unconsolidated()
    decisions = sum(p.type == "decision" for p in queue)
    waiting = f"{len(queue) - decisions} episodes" + (f", {decisions} decisions" if decisions else "")
    status = f"Awaiting /sleep: {waiting} | due to /rehearse: {len(vault.due_for_rehearsal())}"
    if pending or queue:
        status += " | /tend encodes and consolidates in one go"
    due = vault.decisions_due()
    if due:
        status += f" | decisions to review: {len(due)} ({', '.join(p.stem for p in due[:SHOW])})"
    triggered = [d["page"] for d in vault.decision_report() if d["triggered"]]
    if triggered:
        names = ", ".join(os.path.splitext(os.path.basename(p))[0] for p in triggered[:SHOW])
        status += f" | decisions to revisit: {len(triggered)} ({names})"
    yield status
    yield from filter(None, (resume_line(), inbox_line(came), *attention_lines(vault), purpose_line(vault),
                             mood_line(vault), checkpoint_line(vault), engine_line()))
    yield "Last activity:" + ("\n  " + "\n  ".join(map(cut, recent[-SHOW:])) if recent else " none yet")


def main(argv):
    """Print the briefing. What waits at the door comes in first; with `--look` it is counted and stays there."""
    if not is_brain(ROOT):
        return
    came = door.look(ROOT) if LOOK in argv else door.pull(ROOT)
    for line in briefing(Vault(ROOT), came):
        print(line)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:  # noqa: BLE001  whatever broke, the session still starts, and is told the briefing is not whole
        errlog.note("wake_up", "error", root=ROOT)
        print("Briefing: it broke off here (`brain errors` says why)")
