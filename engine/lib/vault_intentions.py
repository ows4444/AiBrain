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

No dependencies, and nothing here reads a file: the page's text is handed in.
"""
import datetime
import re

LINE = re.compile(r"^[-*]\s+(.+?)\s+when\s+(.+?)\s*$")
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
    """[{text, when, at, due, every, time, timed, event, ended, closed, outcome, problem}] for the lines of the page.

    `at` is the moment a dated one is due and `due` its day; `every` and `time` are a
    repeat's round; `event` is what any other waits on. `ended` is `done` or `dropped`,
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
            said = read_when(m.group(2))
            out.append(dict(said, text=m.group(1), when=m.group(2), due=said["at"].date() if said["at"] else None,
                            ended=end.group(1).lower() if end else None, closed=closed,
                            outcome=(end.group(3) or "").strip() if end else ""))
    return out


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
