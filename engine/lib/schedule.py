"""A schedule that needs no session: this machine looks at the brain every few minutes and says what waits.

Usage:
    brain schedule                       whether this brain has one, and what it runs
    brain schedule --set [--minutes N]   set it, or set it again (every 15 minutes unless given)
    brain schedule --remove              take it out

What it runs is `brain tend --check --notify`: read-only, so no page, no index
and no log line changes, and a week left alone leaves the brain as it was. The
first run of a day shows everything that waits in one notification; a later
run shows only a reminder that has come due since, so one written
`when 2026-10-11 10:00` is on the screen within N minutes of ten.

On macOS it is a launchd job of your own user, `~/Library/LaunchAgents/
com.aibrain.tend.<id>.plist`, one for each brain, started at login. Elsewhere
nothing is installed: the cron line that does the same is printed.

Its limit: a machine that is asleep or off runs it when it wakes, so a reminder
can be shown late. A reminder closed with its day records how late (`brain
introspect --remind`). It installs a job on this machine and nothing in the
brain, which is why Claude Code asks before it runs.
"""
import hashlib
import os
import plistlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402

BRAIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "brain")
MINUTES = 15


def on_mac():
    return sys.platform == "darwin"


def job(root):
    """(label, path of its plist) for the job of the brain at `root`: one for each brain on this machine."""
    label = "com.aibrain.tend." + hashlib.sha1(os.path.realpath(root).encode("utf-8")).hexdigest()[:8]
    return label, os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", label + ".plist")


def launchctl(*args):
    """Run launchctl; (whether it worked, what it said)."""
    try:
        r = subprocess.run(["launchctl", *args], capture_output=True, text=True)
    except OSError as why:
        return False, str(why)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def state(root, did):
    """What stands now: {brain, did, set, plist, minutes, runs, cron}; `cron` is the line that does the same."""
    label, path = job(root)
    minutes = None
    if on_mac() and os.path.exists(path):
        with open(path, "rb") as fh:
            minutes = plistlib.load(fh).get("StartInterval", MINUTES * 60) // 60
    return {"brain": root, "did": did, "set": minutes is not None, "plist": path if minutes is not None else None,
            "minutes": minutes, "runs": "brain tend --check --notify",
            "cron": f"*/{minutes or MINUTES} * * * * cd {root} && brain tend --check --notify"}


def arguments(ap):
    ap.add_argument("--set", action="store_true", help="install the job, or install it again with another interval")
    ap.add_argument("--minutes", type=int, default=MINUTES, help="how often it looks (15)")
    ap.add_argument("--remove", action="store_true", help="take the job out")


def run(root, args):
    label, path = job(root)
    target = f"gui/{os.getuid()}"
    if args.set and args.remove:
        raise Refused("brain schedule: --set or --remove, not both")
    if args.set and not 1 <= args.minutes <= 1440:
        raise Refused("brain schedule: --minutes is from 1 to 1440 (a day)")
    if not on_mac() or not (args.set or args.remove):
        found = state(root, "looked")
        if args.set:  # not macOS: nothing to install here, the cron line is the way
            found["cron"] = f"*/{args.minutes} * * * * cd {root} && brain tend --check --notify"
        return found
    was = os.path.exists(path)
    launchctl("bootout", f"{target}/{label}")  # the one running, if any: it is replaced or removed
    if args.remove:
        if was:
            os.remove(path)
        return state(root, "removed" if was else "nothing to remove")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.makedirs(os.path.join(root, ".cache"), exist_ok=True)
    with open(path, "wb") as fh:
        plistlib.dump({"Label": label, "ProgramArguments": [sys.executable, BRAIN, "tend", "--check", "--notify"],
                       "EnvironmentVariables": {"BRAIN_ROOT": root}, "WorkingDirectory": root,
                       "StartInterval": args.minutes * 60, "RunAtLoad": True,
                       "StandardOutPath": os.path.join(root, ".cache", "schedule.log"),
                       "StandardErrorPath": os.path.join(root, ".cache", "schedule.log")}, fh)
    worked, said = launchctl("bootstrap", target, path)
    if not worked:
        os.remove(path)
        raise Refused(f"brain schedule: launchctl would not start the job, and nothing is left installed: {said}")
    return state(root, "set again" if was else "set")


def render(found, args):
    if not on_mac():
        return ("schedule: this machine is not macOS, so nothing is installed here. The line that does the same, "
                f"for `crontab -e`:\n  {found['cron']}")
    if not found["set"]:
        return {"removed": "schedule: removed. Nothing looks at this brain between sessions now",
                "nothing to remove": "schedule: there was none to remove"}.get(
                    found["did"], "schedule: none set for this brain. `brain schedule --set` has this machine look every "
                                  f"{MINUTES} minutes and say what waits")
    return (f"schedule: {found['did'] if found['did'] != 'looked' else 'set'}. Every {found['minutes']} minutes this machine "
            f"runs `{found['runs']}`\n  {found['plist']}\n  the day's first run shows what waits; a later one shows a "
            "reminder that has come due since\n  asleep or off, it runs on waking: a reminder can be shown late")
