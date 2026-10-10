#!/usr/bin/env python3
"""SessionStart: orient the brain on waking. What the senses hold, what awaits
sleep, what is due for rehearsal or an outcome review, what happened last.
With an OWNER.md, the briefing opens with it: who the owner is, how to talk to
them and their goals reach every session this way, so the root CLAUDE.md does
not change when a goal does.
Four lines, every session, and more only when something needs the owner: notes
waiting in inbox/; new input contradicting a page; a reminder whose date has
come; a goal past its date, gone stale, with no pages behind it or slipping;
the pages the last questions and live projects point to; the calibration
checkpoint reached; a note left before a compaction (save_resume.py) that is
newer than the log; or, in a brain that hosts its own engine, hooks running
from a plugin version older than engine/, or from another folder's engine.

The four counts are also what `brain statusline` shows all session, outside
the context; they stay here because the model reads this and not that.
"""
import datetime
import os
import re
import subprocess
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from vaultlib import LOG_LINE, LOG_PATH, OWNER_FILE, Vault, find_brain, is_brain  # noqa: E402

# The brain may be above the folder the session started in (prefrontal/<name>/).
ROOT = find_brain(ROOT) or ROOT

SHOW = 5


def recent_log():
    path = os.path.join(ROOT, LOG_PATH)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        # Recall lines are frequent and carry no news, so the briefing skips them.
        matches = (LOG_LINE.match(line) for line in fh.read().splitlines())
        return [m.group(0) for m in matches if m and m.group(3) != "recall"]


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


def inbox_line():
    inbox = os.path.join(ROOT, "inbox")
    waiting = [f for f in (os.listdir(inbox) if os.path.isdir(inbox) else [])
               if not f.startswith(".") and f != "README.md"]
    return f"Inbox: {len(waiting)} notes waiting (/ingest moves them into senses/)" if waiting else ""


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
    hand = vault.at_hand()
    if hand:
        lines.append("At hand: " + ", ".join(p.stem for p in hand))
    return lines


def checkpoint_line(vault):
    c = vault.usage()["checkpoint"]
    if not c["reached"] or c["reviewed"]:
        return ""
    return (f"Checkpoint: {c['inputs']} inputs and {c['sleeps']} sleeps: time for the calibration review "
            "(brain introspect --usage and the metrics; `brain log health calibration --result ...` when done)")


def owner_lines():
    """OWNER.md without its heading and its note on how the file is used, or nothing."""
    path = os.path.join(ROOT, OWNER_FILE)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    body = re.sub(r"\A# .*?\n(?:(?!^[-#_]).*\n)*", "", text, flags=re.M)  # the title and the prose under it
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
    installed at; engine/ may have moved on since, or hold uncommitted changes.
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
        # 1 means the trees differ; anything else (a commit this clone lacks) is not evidence of change.
        changed = git("diff", "--quiet", loaded, "HEAD", "--", "engine").returncode == 1
        head = git("log", "-1", "--format=%h", "--", "engine").stdout.strip()
        dirty = bool(git("status", "--porcelain", "--", "engine").stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return ""
    parts = ([f"running {loaded[:7]}, engine/ is at {head}"] if changed and head else []) + \
            (["engine/ has uncommitted changes"] if dirty else [])
    if not parts:
        return ""
    return (f"Engine: {'; '.join(parts)} ({'commit, then ' if dirty else ''}"
            "run claude plugin update aibrain@aibrain, then restart)")


def main():
    if not is_brain(ROOT):
        return
    vault = Vault(ROOT)
    pending, recent = vault.unencoded(), recent_log()
    more = "…" if len(pending) > SHOW else ""
    for line in owner_lines():
        print(line)
    print(f"Today: {datetime.date.today().isoformat()}")
    print(f"Unencoded in senses/: {len(pending)}" + (f" ({', '.join(pending[:SHOW])}{more})" if pending else ""))
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
    print(status)
    for line in (resume_line(), inbox_line(), *attention_lines(vault), purpose_line(vault), checkpoint_line(vault),
                 engine_line()):
        if line:
            print(line)
    print("Last activity:" + ("\n  " + "\n  ".join(recent[-SHOW:]) if recent else " none yet"))


if __name__ == "__main__":
    main()
