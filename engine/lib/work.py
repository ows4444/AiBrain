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

A round does not run on code that is being edited. Where the brain holds its
own engine (the engine that is running is the brain's `engine/` folder) and
`git status -- engine` shows changes that are not committed, the round carries
out nothing and says so: commit, and the next round runs. `--retry` is the
owner's word in a session and runs all the same. A brain with no engine of its
own, a folder that is no git repository and a git that does not answer within
five seconds are not held back.

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

A reminder may name a plan: several actions with commas between them, each
with its own check. Every part still to come is asked of the policy before
the first of them runs, so a plan with a part that is not allowed runs none.
Then they run in order, each a start and an end in the log: `passed` for a
part with more to come, `finished` for the last. One that fails stops the
plan there, and it is that part that is tried again; one interrupted is taken
up at the part it had reached, never from the beginning.

What a round takes first is worked out by rule and said with each reminder,
in brackets: one that names a page a live goal depends on; then the one the
record gives more to feel about (`brain feel`: a reminder that failed, or
has waited long); then one that only reads before one that changes the
brain; then the one longest due. The order decides nothing but the order:
the policy is asked of each when its turn comes.

One round runs for a brain at a time (a lock in .cache/, which a round that
died leaves and the next takes over once it is old or its process is gone),
begins five parts at most and nothing after ten minutes; what is left of a
plan goes on in the next round.
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
import subprocess
import time

import act
import tend
from refusal import Refused
from vaultlib import (ACTIONS, CHANGES, LINK, POLICY_PATH, Vault, decide, moment, policy_of, stamp, words,
                      yes_of)

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the engine that is running
LOCK = os.path.join(".cache", "work.lock")
INTERRUPTED = "interrupted: it started and no end was written, so what it did is not known"
YES_SAID = "by the owner's yes"  # in the step that starts under one; a plan goes on under it while its parts pass
GIT_SECONDS = 5  # how long git is waited for; one that does not answer holds no round back
EDITED = ("the engine in this brain has changes that are not committed (`git status -- engine`), and a round does not "
          "run on code that is being edited: commit them, and the next round runs")


def being_edited(root):
    """Whether the engine that is running is this brain's own `engine/` and git says it has changes not committed.

    Then a round nobody watches would run code that is half changed. Only git's own word
    holds a round back: a brain with no engine of its own, a folder that is no repository
    and a git that is missing or does not answer in GIT_SECONDS are not held. Git is asked
    without its optional locks, so a look every few minutes never stands in the way of a
    commit the owner is making.
    """
    if os.path.realpath(os.path.join(root, "engine")) != os.path.realpath(ENGINE):
        return False
    try:
        said = subprocess.run(["git", "--no-optional-locks", "-C", root, "status", "--porcelain", "--", "engine"],
                              capture_output=True, text=True, timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return False
    return said.returncode == 0 and bool(said.stdout.strip())


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


def part_said(plan, part):
    """A part of a plan as a step names it: the action alone for a plan of one, `2/3 index` in a longer one."""
    do = plan[part]["do"]
    return do if len(plan) == 1 else f"{part + 1}/{len(plan)} {do}"


def carry_out(root, i, part, why, now):
    """One attempt at one part of a reminder's plan: (its two steps in the log, as the lines written; whether it passed)."""
    plan = i["steps"]
    do, until = plan[part]["do"], plan[part]["until"]
    started = act.advance(root, i["text"], "started", f"{part_said(plan, part)}, {why}", now)
    try:
        said, failed = act.perform(root, do)
        if not failed and until:
            checked, failed = act.perform(root, until)
            said = f"{until} does not hold: {act.first_line(checked)}" if failed else said
    except Exception as wrong:  # noqa: BLE001  whatever it was, the step has an end and the log says which
        said, failed = f"{type(wrong).__name__}: {wrong}", True
    end = "failed" if failed else "finished" if part == len(plan) - 1 else "passed"
    return [started, act.advance(root, i["text"], end, said, now)], not failed


def one(root, i, vault, forced, spent, dry):
    """What a round does about one reminder: ({text, do, steps} when it wrote or would write, else None; why it was left).

    `spent()` says the round's budget is used up, and is asked before each part of a plan
    is begun. `dry` writes nothing and says what would be written.
    """
    t, stands, plan = vault.tuning, i["stands"], i["steps"]
    state, tries, steps, name, part = stands["state"], stands["attempts"], [], stands["proposal"], stands["part"]
    yes = name in yes_of(root, vault.today, t.yes_days)  # the owner's yes for this one, as it stands: once, and now
    forced = forced or (yes and state == "waiting")
    # A plan begun under a yes goes on under it while its parts pass: the yes was for the plan, once through.
    under = state == "passed" and any(step[2] == "started" and YES_SAID in step[4] for step in stands["course"])

    def step(kind, note):
        steps.append(f"would be {kind}: {note}" if dry else act.advance(root, i["text"], kind, note, vault.now))

    def done(left=None):
        return ({"text": i["text"], "do": i["do"], "steps": steps} if steps else None), left

    if part >= len(plan):  # the plan was shortened under it: every part it now has has passed
        step("finished", "every part its plan now has has passed")
        return done()
    if state == "started":  # no round is running it: this one holds the lock
        step("failed", INTERRUPTED)
        state = "failed"
        if not ACTIONS[plan[part]["do"]].again and not forced:
            step("waiting", f"owner: interrupted, and `{plan[part]['do']}` is not run twice unasked; yes {name}")
            return done("it waits for the owner")
    if state == "waiting" and stands["course"][-1][4].startswith("owner:") and not forced:
        return done(f"it waits for the owner (yes {name}, or `brain work --retry`)")
    allowed = policy_of(root)  # every part still to come is asked before the first of them runs
    refused = list(dict.fromkeys(p["do"] for p in plan[part:] if not decide(p["do"], allowed)[0]))
    if refused and not yes and not under:
        if state != "waiting":
            step("waiting", f"policy: {POLICY_PATH} does not allow {', '.join(refused)}; yes {name}")
        return done(f"the policy does not allow it (yes {name})")
    if state == "failed" and not forced:
        if tries >= t.work_tries:
            step("waiting", f"owner: it failed {tries} times; yes {name}")
            return done("it waits for the owner")
        day, clock = stands["course"][-1][:2]  # when the step that failed was written
        again = moment(day, clock) + datetime.timedelta(minutes=t.work_wait * 2 ** (tries - 1))
        if steps == [] and again > vault.now:
            return done(f"it is tried again after {again:%Y-%m-%d %H:%M}")
    since = f"due since {stamp(i['since'], i['timed'])}" + (f", {YES_SAID} {name}" if yes else "")
    while part < len(plan):
        if spent():
            return done("the round's budget is spent")
        if dry:
            steps.append(f"would be started: {part_said(plan, part)}, {since}")
            return done()  # what a part would say is not known until it runs
        lines, passed = carry_out(root, i, part, since, vault.now)
        steps.extend(lines)
        if not passed:
            break
        part += 1
    return done()


def in_turn(vault, due):
    """The reminders in the order a round takes them, each given `first`: why it comes where it does.

    One that names a page a live goal or project depends on comes before one that does
    not. Then the one the record gives more to feel about, of the feelings that ask for
    something. Then the lesser risk: a plan that only reads before one that changes the
    brain. Then the one longest due. What may run at all is not decided here: the policy
    is asked of each when its turn comes, and no place in the order changes its answer.
    """
    purpose, felt = vault.purpose(), vault.calling()

    def place(i):
        goal = any(vault.resolve(name) in purpose for name in LINK.findall(i["text"]))
        feeling = felt.get(("reminder", i["text"]))
        changes = any(ACTIONS[part["do"]].tier == CHANGES for part in i["steps"])
        i["first"] = "; ".join(filter(None, (
            "a goal depends on a page it names" if goal else "",
            f"{feeling['feeling']} {feeling['intensity']:.2f}" if feeling else "",
            "it changes the brain" if changes else "it only reads", f"due since {stamp(i['since'], i['timed'])}")))
        return not goal, -(feeling["intensity"] if feeling else 0), changes, i["since"]

    return sorted(due, key=place)


def round_of(root, retry=None, dry=False, now=None):
    """One round: {date, may, why, busy, order, did, left}. `retry` is the words of the one reminder to carry out,
    forced. `order` is every reminder with an action that is due, in the turn a round takes them, each with why.

    `may` is whether the round carries anything out, and `why`: the policy's answer, or, where the policy
    allows the worker, that the engine is being edited (EDITED), which the owner's `retry` is not held by."""
    vault = Vault(root, now=now)
    t = vault.tuning
    may, why = decide("work", policy_of(root))
    if may and retry is None and being_edited(root):
        may, why = False, EDITED
    found = {"date": vault.today.isoformat(), "may": may, "why": why, "busy": False, "order": [], "did": [], "left": []}
    due = in_turn(vault, [i for i in vault.due_intentions() if i["do"]])
    found["order"] = [{"text": i["text"], "first": i["first"]} for i in due]
    if retry is not None:
        due = [i for i in due if words(i["text"]) == words(retry)]
        if not due:
            raise Refused(f"brain work: no reminder with an action that is due says '{retry}' "
                          "(`brain introspect --remind` lists them)")
    if not may:
        return found
    if not dry and not take(root, t.work_minutes):
        return dict(found, busy=True)
    began, begun = time.monotonic(), [0]

    def spent():
        """Whether the round may begin nothing more; each asking that it may counts as one part begun."""
        over = begun[0] >= t.work_steps or time.monotonic() - began >= t.work_minutes * 60
        begun[0] += not over
        return over

    try:
        for i in due:
            did, left = one(root, i, vault, retry is not None, spent, dry)
            if did:
                found["did"].append(dict(did, first=i["first"]))
            if left:
                found["left"].append({"text": i["text"], "do": i["do"], "why": left, "first": i["first"]})
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
        out.append(f"  {d['text']} ({d['do']})  [{d['first']}]")
        out += [f"      {line}" for line in d["steps"]]
    out += [f"  left: {x['text']} ({x['do']}): {x['why']}  [{x['first']}]" for x in found["left"]]
    out.append(f"  {found['needs']} kinds of thing wait on the owner (`brain tend --check`)" if found["needs"]
               else "  nothing waits on the owner")
    return "\n".join(out)
