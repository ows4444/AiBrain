"""The round nobody watches: carry out the reminders that are due and allowed, a step each.

Usage:
    brain work [--notify] [--dry-run] [--json]
    brain work --retry WORD ...      carry out that one reminder now, whatever its tries

A reminder may name an action of the brain's own (`... do `index``,
hippocampus/intentions.md). One round looks at each such reminder whose time
has come, longest due first, and takes it one step further. Each step is one
line in the log, written by `brain act`'s `advance`, before the action runs
and after it: started, then finished or failed, or waiting with the reason.

What a round may do is the policy page's to say, each time:

    the worker itself   runs only where hippocampus/policy.md has `- work`
                        under `## Allowed`. It writes steps in the log, so
                        it changes the brain. Taking that line out stops all
                        of it at the next round: that is the switch
    each action         is asked of the policy when it would run. One the
                        page does not allow leaves the reminder waiting, said
                        once (`waiting ... -> policy: ...`), and is started
                        when a later round finds it allowed

What a round does about a step that went wrong:

    failed       tried again after 30 minutes, then twice as long, three
                 tries in all; after that it waits for the owner
                 (`waiting ... -> owner: ...`)
    interrupted  a step that started and has no end in the log (the machine
                 went down, the process was killed) is of unknown outcome:
                 it is never taken as not done. It is written down as failed,
                 and tried again only when its action may be run twice;
                 otherwise it waits for the owner

A reminder that waits is a proposal, and its step ends with its name: `yes
3f9a2c1`. The owner's yes is a line of the policy page, under `## Once`: that
name and the day, `- 3f9a2c1 2026-10-12`. It lets that one reminder run once:
its name is made from everything about it, so it is another once the reminder
changes or has started, and the yes holds for seven days. `--retry` is the
same word given in a session, for one that failed too often.

One round runs for a brain at a time (a lock in .cache/, which a round that
died leaves and the next takes over once it is old or its process is gone),
carries out five reminders at most and starts nothing after ten minutes.
(3, 30, 5, 10 and the 7 days of a yes are thresholds: a brain may hold its
own in hippocampus/tuning.md.) On two machines that share a brain, set the schedule
on one: the lock is this machine's.

--notify then puts what waits on the screen, as `brain tend --check --notify`
does: `brain schedule` runs `brain work --notify`. A brain whose policy does
not allow the worker gets only that, which is what the schedule did before.
--dry-run says what a round would do and writes nothing.

Nothing outside the brain is touched: every action is one of the registry's
that reads, or changes the brain where git can undo it.
"""
import contextlib
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import act  # noqa: E402
import tend  # noqa: E402
from commands import Refused  # noqa: E402
from vault_intentions import stamp, words  # noqa: E402
from vault_policy import ACTIONS, POLICY_PATH, decide, policy_of, yes_of  # noqa: E402
from vaultlib import Vault  # noqa: E402

LOCK = os.path.join(".cache", "work.lock")
INTERRUPTED = "interrupted: it started and no end was written, so what it did is not known"


def alive(pid):
    """Whether a process of that number is running here; a number that is none is not."""
    try:
        if int(pid) <= 0:
            return False
        os.kill(int(pid), 0)
    except (ValueError, OverflowError, ProcessLookupError):
        return False
    except OSError:  # it is there, and another user's
        return True
    return True


def take(root, minutes):
    """True when this process now holds the brain's lock; False when a round that is still running holds it."""
    path = os.path.join(root, LOCK)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for _ in range(2):
        try:
            with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY), "w") as fh:
                fh.write(str(os.getpid()))
            return True
        except FileExistsError:
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    holder = fh.read().strip()
                fresh = time.time() - os.path.getmtime(path) <= 2 * minutes * 60
            except FileNotFoundError:
                continue  # let go between the two looks: the next one takes it
            if alive(holder) and fresh:
                return False
            with contextlib.suppress(FileNotFoundError):
                os.remove(path)  # left by a round that died, or one far past its time
    return False


def moment(step):
    """When a step of a course was written: its day and its time, the end of the day for a line with no time."""
    day, clock = step[0], step[1]
    return datetime.datetime.combine(day, datetime.time(*map(int, clock.split(":"))) if clock else datetime.time(23, 59))


def carry_out(root, i, why, now):
    """One attempt at a reminder's action: its two steps in the log, as the lines written."""
    started = act.advance(root, i["text"], "started", f"{i['do']}, {why}", now)
    try:
        said, failed = act.perform(root, i["do"])
        if not failed and i["until"]:
            checked, failed = act.perform(root, i["until"])
            said = f"{i['until']} does not hold: {act.first_line(checked)}" if failed else said
    except Exception as wrong:  # noqa: BLE001  whatever it was, the step has an end and the log says which
        said, failed = f"{type(wrong).__name__}: {wrong}", True
    return [started, act.advance(root, i["text"], "failed" if failed else "finished", said, now)]


def one(root, i, vault, forced, spent, dry):
    """What a round does about one reminder: ({text, do, steps} when it wrote or would write, else None; why it was left).

    `spent` says the round's budget is used up. `dry` writes nothing and says what would be written.
    """
    t, stands = vault.tuning, i["stands"]
    state, tries, steps, name = stands["state"], stands["attempts"], [], stands["proposal"]
    yes = name in yes_of(root, vault.today, t.yes_days)  # the owner's yes for this one, as it stands: once, and now
    forced = forced or (yes and state == "waiting")

    def step(kind, note):
        steps.append(f"would be {kind}: {note}" if dry else act.advance(root, i["text"], kind, note, vault.now))

    def done(left=None):
        return ({"text": i["text"], "do": i["do"], "steps": steps} if steps else None), left

    if state == "started":  # no round is running it: this one holds the lock
        step("failed", INTERRUPTED)
        state = "failed"
        if not ACTIONS[i["do"]].again and not forced:
            step("waiting", f"owner: interrupted, and `{i['do']}` is not run twice unasked; yes {name}")
            return done("it waits for the owner")
    if state == "waiting" and stands["course"][-1][4].startswith("owner:") and not forced:
        return done(f"it waits for the owner (yes {name}, or `brain work --retry`)")
    if not decide(i["do"], policy_of(root))[0] and not yes:  # a reminder names only what reads or changes
        if state != "waiting":
            step("waiting", f"policy: {POLICY_PATH} does not allow {i['do']}; yes {name}")
        return done(f"the policy does not allow it (yes {name})")
    if state == "failed" and not forced:
        if tries >= t.work_tries:
            step("waiting", f"owner: it failed {tries} times; yes {name}")
            return done("it waits for the owner")
        again = moment(stands["course"][-1]) + datetime.timedelta(minutes=t.work_wait * 2 ** (tries - 1))
        if steps == [] and again > vault.now:
            return done(f"it is tried again after {again:%Y-%m-%d %H:%M}")
    if spent:
        return done("the round's budget is spent")
    since = f"due since {stamp(i['since'], i['timed'])}" + (f", by the owner's yes {name}" if yes else "")
    if dry:
        steps.append(f"would be started: {i['do']}, {since}")
    else:
        steps.extend(carry_out(root, i, since, vault.now))
    return done()


def round_of(root, retry=None, dry=False, now=None):
    """One round: {date, may, why, busy, did, left}. `retry` is the words of the one reminder to carry out, forced."""
    vault = Vault(root, now=now)
    t = vault.tuning
    may, why = decide("work", policy_of(root))
    found = {"date": vault.today.isoformat(), "may": may, "why": why, "busy": False, "did": [], "left": []}
    due = [i for i in vault.due_intentions() if i["do"]]
    if retry is not None:
        due = [i for i in due if words(i["text"]) == words(retry)]
        if not due:
            raise Refused(f"brain work: no reminder with an action that is due says '{retry}' "
                          "(`brain introspect --remind` lists them)")
    if not may:
        return found
    if not dry and not take(root, t.work_minutes):
        return dict(found, busy=True)
    began = time.monotonic()
    try:
        for i in due:
            spent = len(found["did"]) >= t.work_steps or time.monotonic() - began >= t.work_minutes * 60
            did, left = one(root, i, vault, retry is not None, spent, dry)
            if did:
                found["did"].append(did)
            if left:
                found["left"].append({"text": i["text"], "do": i["do"], "why": left})
    finally:
        if not dry:
            with contextlib.suppress(FileNotFoundError):  # taken over by a round that found it too old
                os.remove(os.path.join(root, LOCK))
    return found


def arguments(ap):
    ap.add_argument("--notify", action="store_true", help="then put what waits on the screen, each thing once a day")
    ap.add_argument("--dry-run", action="store_true", help="say what a round would do, and write nothing")
    ap.add_argument("--retry", nargs="+", metavar="WORD", help="carry out that one reminder now, whatever its tries")


def run(root, args):
    found = round_of(root, " ".join(args.retry) if args.retry else None, args.dry_run)
    waits = tend.digest(Vault(root))
    found["needs"] = waits["needs"]
    found["notified"] = [line for line in tend.announcements(root, waits) if tend.show(line)] if args.notify else []
    return found


def render(found, args):
    if not found["may"]:
        head = f"work, {found['date']}: nothing was carried out: {found['why']}"
    elif found["busy"]:
        head = f"work, {found['date']}: another round is running for this brain; this one did nothing"
    else:
        head = (f"work, {found['date']}: {len(found['did'])} carried a step further, {len(found['left'])} left"
                + (" (a dry run: nothing was written)" if args.dry_run else ""))
    out = [head]
    for d in found["did"]:
        out.append(f"  {d['text']} ({d['do']})")
        out += [f"      {line}" for line in d["steps"]]
    out += [f"  left: {x['text']} ({x['do']}): {x['why']}" for x in found["left"]]
    out.append(f"  {found['needs']} kinds of thing wait on the owner (`brain tend --check`)" if found["needs"]
               else "  nothing waits on the owner")
    return "\n".join(out)
