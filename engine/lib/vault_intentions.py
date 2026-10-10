"""Reminders: the lines of hippocampus/intentions.md, and when each one is due.

A line is `- <what to do> when <when>`, and `<when>` is one of

    2026-11-01             a day: due from its start
    2026-11-01 10:00       a minute of a day: due from then
    every day              a repeat: also `every monday` (any weekday) and
    every monday 09:00     `every month` (its first day), each with a time or without
    a rival cuts prices    anything else is an event, which `brain fit` holds
                           every new input against

A line is closed by ending it with `(done)` or `(dropped)`, which may carry the
day and what happened: `(done 2026-11-03: the setup was confirmed)`. A repeat is
not closed by `(done)`: each time it is done the `remind` log line says so, and
it is due again at the next round after that line; `(dropped)` ends it.

What looks like a day or a repeat and is neither (`2026-02-30`, `every fortnight`)
would wait for ever as an event nothing reports, so it is a problem of the page:
`brain check` fails on it and the page hook refuses the write that would leave it.

A reminder may be one the brain carries out itself. Its line then ends with the
action, in backticks, and may say what must hold once it is done:

    - keep the listing current when every day 07:00 do `index`
    - see the listing is whole when 2026-11-01 do `index` until `check`
    - put it in order when every friday do `fingerprint`, `index` until `check`, `snapshot`

The action is one of the brain's own (vault_policy) that can run with nobody
there, and `until` names one that only reads and gives a verdict. Several, with
commas between them, are a plan: done in that order, each with its own check, the
next begun only when the one before it passed. Only a day, a time or a repeat can
start one: nothing but a reader can tell that an event has come. Whether an
action is allowed is the policy page's to say at the moment the plan would run,
for every step of it before the first, not this line's. How one was carried out
is lines in the log, one a step (`act started <the reminder's words> -> a1:
index, due since ...`), and where it stands is read from them: NEXT is every
step that may follow another. A part of a plan that is done is `passed`, and
the plan `finished` with its last; so one that was interrupted is taken up at
the part it had reached.

A reminder may also be one for another program to carry out, since nothing
outside the brain is touched from here. Its line ends with that program's name,
in backticks, and may say in words how it is known to be done:

    - fix the login redirect when 2026-11-01 for `acline` until the page loads after sign-in

The brain does nothing about such a one but list it, with a name of seven
characters made from everything about it (`brain handover`, and the MCP tool a
runtime reads). What came of it comes back as an input like any other: a note
that begins `handed: <that name>`, whose episode is the evidence it is closed
on. Only a day or a time starts one; a repeat cannot be handed over yet.

Nothing here reads a file: the page's text is handed in. It knows the actions
by vault_policy, which has no dependencies either.
"""
import datetime
import difflib
import hashlib
import re

from vault_policy import ACTIONS, CHANGES, READS

LINE = re.compile(r"^[-*]\s+(.+?)\s+when\s+(.+?)\s*$")
# ... do `index`, and then: until `check`; several with commas between them are a plan. The names are in
# backticks, so prose that holds the word `do` is not one.
PART = r"`([^`]*)`(?:\s+until\s+`([^`]*)`)?"
DO = re.compile(rf"\s+do\s+({PART}(?:\s*,\s*{PART})*)\s*$")
BARE = re.compile(r"\s+do\s+([a-z]+)(?:\s+until\s+[a-z]+)?\s*$")  # the same without them: said, not guessed at
# ... for `acline`, and then: until <how it is known to be done, in words>. A program outside the brain carries it out.
FOR = re.compile(r"\s+for\s+`([^`]*)`(?:\s+until\s+(.+?))?\s*$")
PROGRAM = re.compile(r"^[a-z][a-z0-9-]*$")
# How an intention with an action is carried out: each step is one `act` line of the log.
VERBS = ("started", "passed", "finished", "failed", "waiting")
STEP = re.compile(r"^(started|passed|finished|failed|waiting)\s+(.+)$")
ATTEMPT = re.compile(r"^(a\d+)(?::\s*(.*))?$")
# Where one stands -> the steps that may follow. Nothing follows `waiting` but a start, so a
# worker that finds it waiting again writes no second line: the log holds each thing once.
# `passed` is a part of a plan done with more to come; `finished` after it is a plan that was
# shortened under it, so that every part it now has has passed.
NEXT = {"scheduled": (), "ready": ("started", "waiting"), "started": ("passed", "finished", "failed"),
        "passed": ("started", "waiting", "finished"), "failed": ("started", "waiting"), "waiting": ("started",),
        "finished": ()}
# `(done)`, `(done 2026-11-03)`, `(dropped: no longer needed)`, `(done 2026-11-03: confirmed)`; goals end the same way.
END = re.compile(r"\s*\((done|dropped)(?:\s+(\d{4}-\d{2}-\d{2}))?(?:\s*:\s*([^)]*?))?\s*\)", re.I)
DAY = re.compile(r"^(\d{4}-\d{1,2}-\d{1,2})(?:\s+(.+))?$")
REPEAT = re.compile(r"^every\s+(\S+)(?:\s+(.+))?$", re.I)
CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
ROUNDS = ("day", *WEEKDAYS, "month")
# A repeat nothing in the log names has never been done: its latest round is the one that is due.
SPAN = {"day": 1, "month": 31}
MIDNIGHT = datetime.time(0, 0)


def clock(text):
    """HH:MM as a time of day; None for one that is none (25:99)."""
    m = CLOCK.match(text)
    return datetime.time(int(m.group(1)), int(m.group(2))) if m and int(m.group(1)) < 24 and int(m.group(2)) < 60 else None


def read_when(text):
    """What a `when` says: {at, timed} for a day, {every, time, timed} for a repeat, {event} for anything else.

    `problem` is set, with the text kept as an event, for what starts as a day or a
    repeat and cannot be read as one.
    """
    said = {"at": None, "every": None, "time": None, "timed": False, "event": None, "problem": None}
    day, repeat = DAY.match(text), REPEAT.match(text)
    if day:
        try:
            date = datetime.date.fromisoformat(day.group(1))
        except ValueError:
            return dict(said, event=text, problem=f"'{text}' is no day: a reminder's date is YYYY-MM-DD, then HH:MM if "
                                                  "it has a time")
        time = clock(day.group(2)) if day.group(2) else MIDNIGHT
        if time is None:
            return dict(said, event=text, problem=f"'{text}' has no time of day after its date: HH:MM, as in 09:30")
        return dict(said, at=datetime.datetime.combine(date, time), timed=bool(day.group(2)))
    if repeat:
        time = clock(repeat.group(2)) if repeat.group(2) else MIDNIGHT
        if repeat.group(1).lower() not in ROUNDS or time is None:
            return dict(said, event=text, problem=f"'{text}' is no repeat: every day, every monday (any weekday) or "
                                                  "every month, then HH:MM if it has a time. An event is written "
                                                  "another way (`when all of them pass`)")
        return dict(said, every=repeat.group(1).lower(), time=time, timed=bool(repeat.group(2)))
    return dict(said, event=text)


def read_intentions(body):
    """[{text, when, at, due, every, time, timed, event, do, until, steps, hand, hand_until, ended, closed, outcome,
    problem}] for the lines of the page.

    `at` is the moment a dated one is due and `due` its day; `every` and `time` are a
    repeat's round; `event` is what any other waits on. `do` is the action of one the brain
    carries out itself and `until` what must hold after it, both None for a reminder that
    only reminds; `steps` is its whole plan. `hand` is the program one is handed to, and
    `hand_until` how it is known to be done, in words. `when` is the line's `when` without them. `ended` is `done` or `dropped`,
    `closed` the day the closing mark gives (None when it gives none) and `outcome` what it
    says happened.
    """
    out = []
    for line in body.splitlines():
        end = END.search(line)
        m = LINE.match(END.sub("", line).strip())
        if m:
            closed = end.group(2) if end else None
            try:
                closed = datetime.date.fromisoformat(closed) if closed else None
            except ValueError:
                closed = None
            when, hand, shown, unfit = read_for(m.group(2))
            when, steps, wrong = read_do(when)
            said = read_when(when)
            if steps and hand:
                steps, hand, wrong = [], None, (f"'{m.group(2)}': a reminder is carried out by the brain (`do`) or handed "
                                                "to another program (`for`), not both")
            elif (steps or hand) and said["event"] and not said["problem"]:
                what = f"start `{steps[0]['do']}`" if steps else f"be when it is handed to `{hand}`"
                wrong = (f"'{when}' is an event, and an event cannot {what}: only a day, a time or a repeat can, since "
                         "nothing but a reader can tell that an event has come")
                steps, hand = [], None
            elif hand and said["every"]:
                hand, wrong = None, f"'{when}' is a repeat, and a repeat cannot be handed over yet: give it a day"
            keep = not said["problem"]
            out.append(dict(said, text=m.group(1), when=when, due=said["at"].date() if said["at"] else None,
                            ended=end.group(1).lower() if end else None, closed=closed,
                            outcome=(end.group(3) or "").strip() if end else "", steps=steps if keep else [],
                            do=(", ".join(s["do"] for s in steps) or None) if keep else None,
                            until=steps[0]["until"] if keep and len(steps) == 1 else None,
                            hand=hand if keep else None, hand_until=shown if keep and hand else None,
                            problem=wrong or unfit or said["problem"]))
    return out


def read_for(when):
    """(the `when` without it, the program it is for, how it is known to be done, what is wrong) from what follows `when`."""
    m = FOR.search(when)
    if not m:
        return when, None, None, None
    rest, program = when[:m.start()].strip(), m.group(1).strip()
    if not PROGRAM.match(program):
        return rest, None, None, (f"`{program}` is no name of a program to hand it to: lower-case letters, digits and "
                                  "hyphens, as in `acline`")
    return rest, program, (m.group(2) or "").strip() or None, None


def handover(said, program, shown, when):
    """The name of one thing handed over: seven characters that are others once anything about it changes."""
    return hashlib.sha256("\n".join((said, program, shown or "", when)).encode("utf-8")).hexdigest()[:7]


def plan_said(steps):
    """A plan as its line writes it, without the backticks: `fingerprint, index until check, snapshot`."""
    return ", ".join(s["do"] + (f" until {s['until']}" if s["until"] else "") for s in steps)


def words(text):
    """A reminder's words as the log is matched by them: whatever their case and spacing."""
    return " ".join(text.lower().split())


def read_do(when):
    """(the `when` without its plan, the plan as [{do, until}], what is wrong) from what follows `when`.

    Each action is one that can run with nobody there, a reading or a changing one; `until`
    is one that only reads. A name that is neither, and an action written without its
    backticks where that leaves no `when` to read, are said as a problem and nothing is
    done: a plan is taken whole or not at all.
    """
    m = DO.search(when)
    if not m and re.search(r"\sdo\s+`", when):
        return re.split(r"\s+do\s+`", when)[0].strip(), [], (
            f"'{when}': what follows `do` cannot be read. Each action is in backticks, with a comma before the next: "
            "do `fingerprint`, `index` until `check`")
    if not m:
        bare = BARE.search(when)
        if bare and bare.group(1) in ACTIONS and read_when(when)["problem"]:
            return when[:bare.start()].strip(), [], (
                f"'{when}': an action is written in backticks, do `{bare.group(1)}`, so that prose is never taken for one")
        return when, [], None
    rest = when[:m.start()].strip()
    steps = [{"do": do.strip(), "until": until.strip() or None} for do, until in re.findall(PART, m.group(1))]
    for step in steps:
        for name, tiers, what in ((step["do"], (READS, CHANGES), "can be done with nobody there"),
                                  (step["until"], (READS,), "only reads")):
            if name is not None and (name not in ACTIONS or ACTIONS[name].tier not in tiers):
                close = difflib.get_close_matches(name, [n for n, a in ACTIONS.items() if a.tier in tiers], n=1)
                return rest, [], (f"`{name}` is no action that {what}" + (f" (closest: {close[0]})" if close else "")
                                  + "; `brain act` lists them")
    return rest, steps, None


def read_course(events):
    """{a reminder's words: [(day, time, step, attempt, note)]} from the log's `act` lines that say a step of one.

    `act started keep the listing current -> a1: index, due since 2026-10-12` is such a
    line; `act index -> index: 12 pages listed`, which `brain act index` leaves, is not.
    """
    course = {}
    for e in events:
        m = STEP.match(e.what) if e.op == "act" and e.day else None
        if m:
            after = " ".join(e.rest.partition("->")[2].split())
            after = "" if after == "none" else after  # what the log writes for a line with no result
            said = ATTEMPT.match(after)
            course.setdefault(words(m.group(2)), []).append(
                (e.day, e.time, m.group(1), said.group(1) if said else None, (said.group(2) or "") if said else after))
    return course


def intention_problems(body):
    """What is wrong with the reminders in an intentions page's text; [] if nothing."""
    return [i["problem"] for i in read_intentions(body) if i["problem"] and not i["ended"]]


def next_round(moment, every, time):
    """The first time a repeat comes round after `moment`: every day, on a weekday, or on the first of a month."""
    day = moment.date()
    if every == "month":
        day = day.replace(day=1)
    elif every != "day":
        day += datetime.timedelta(days=(WEEKDAYS.index(every) - day.weekday()) % 7)
    first = datetime.datetime.combine(day, time)
    if first > moment:
        return first
    if every == "month":
        return datetime.datetime.combine((day + datetime.timedelta(days=32)).replace(day=1), time)
    return first + datetime.timedelta(days=1 if every == "day" else 7)


def stamp(moment, timed):
    """A moment as a reminder is written: its day, and the time when the reminder has one."""
    return moment.strftime("%Y-%m-%d %H:%M") if timed else moment.date().isoformat()
