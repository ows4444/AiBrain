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

The action is one of the brain's own (vault_policy) that can run with nobody
there, and `until` names one that only reads and gives a verdict. Only a day, a
time or a repeat can start one: nothing but a reader can tell that an event has
come. Whether the action is allowed is the policy page's to say at the moment it
would run, not this line's. How one was carried out is lines in the log, one a
step (`act started <the reminder's words> -> a1: index, due since ...`), and
where it stands is read from them: NEXT is every step that may follow another.

Nothing here reads a file: the page's text is handed in. It knows the actions
by vault_policy, which has no dependencies either.
"""
import datetime
import difflib
import re

from vault_policy import ACTIONS, CHANGES, READS

LINE = re.compile(r"^[-*]\s+(.+?)\s+when\s+(.+?)\s*$")
# ... do `index`, and then: until `check`. The names are in backticks, so prose that holds the word `do` is not one.
DO = re.compile(r"\s+do\s+`([^`]*)`(?:\s+until\s+`([^`]*)`)?\s*$")
BARE = re.compile(r"\s+do\s+([a-z]+)(?:\s+until\s+[a-z]+)?\s*$")  # the same without them: said, not guessed at
# How an intention with an action is carried out: each step is one `act` line of the log.
VERBS = ("started", "finished", "failed", "waiting")
STEP = re.compile(r"^(started|finished|failed|waiting)\s+(.+)$")
ATTEMPT = re.compile(r"^(a\d+)(?::\s*(.*))?$")
# Where one stands -> the steps that may follow. Nothing follows `waiting` but a start, so a
# worker that finds it waiting again writes no second line: the log holds each thing once.
NEXT = {"scheduled": (), "ready": ("started", "waiting"), "started": ("finished", "failed"),
        "failed": ("started", "waiting"), "waiting": ("started",), "finished": ()}
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
    """[{text, when, at, due, every, time, timed, event, do, until, ended, closed, outcome, problem}] for the
    lines of the page.

    `at` is the moment a dated one is due and `due` its day; `every` and `time` are a
    repeat's round; `event` is what any other waits on. `do` is the action of one the brain
    carries out itself and `until` what must hold after it, both None for a reminder that
    only reminds; `when` is the line's `when` without them. `ended` is `done` or `dropped`,
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
            when, do, until, wrong = read_do(m.group(2))
            said = read_when(when)
            if do and said["event"] and not said["problem"]:
                do, wrong = None, (f"'{when}' is an event, and an event cannot start `{do}`: only a day, a time or a "
                                   "repeat can, since nothing but a reader can tell that an event has come")
            out.append(dict(said, text=m.group(1), when=when, due=said["at"].date() if said["at"] else None,
                            ended=end.group(1).lower() if end else None, closed=closed,
                            outcome=(end.group(3) or "").strip() if end else "",
                            do=None if said["problem"] else do, until=until, problem=wrong or said["problem"]))
    return out


def words(text):
    """A reminder's words as the log is matched by them: whatever their case and spacing."""
    return " ".join(text.lower().split())


def read_do(when):
    """(the `when` without its action, the action, what must hold after it, what is wrong) from what follows `when`.

    The action is one that can run with nobody there, a reading or a changing one; `until`
    is one that only reads. A name that is neither, and an action written without its
    backticks where that leaves no `when` to read, are said as a problem and nothing is done.
    """
    m = DO.search(when)
    if not m:
        bare = BARE.search(when)
        if bare and bare.group(1) in ACTIONS and read_when(when)["problem"]:
            return when[:bare.start()].strip(), None, None, (
                f"'{when}': an action is written in backticks, do `{bare.group(1)}`, so that prose is never taken for one")
        return when, None, None, None
    rest, do, until = when[:m.start()].strip(), m.group(1).strip(), (m.group(2) or "").strip() or None
    for name, tiers, what in ((do, (READS, CHANGES), "can be done with nobody there"), (until, (READS,), "only reads")):
        if name is not None and (name not in ACTIONS or ACTIONS[name].tier not in tiers):
            close = difflib.get_close_matches(name, [n for n, a in ACTIONS.items() if a.tier in tiers], n=1)
            return rest, None, None, (f"`{name}` is no action that {what}" + (f" (closest: {close[0]})" if close else "")
                                      + "; `brain act` lists them")
    return rest, do, until, None


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
