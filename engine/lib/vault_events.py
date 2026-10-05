"""The log as events: one parse of hippocampus/log.md, read by everything that learns from use.

Recall strength, rehearsal, co-recall (Hebbian) weights, usage, goal activity
and the time views all derive from these records, so they agree with each
other and nothing derived is ever stored: edit or roll back the log and every
view follows.
"""
import collections
import os

from vault_model import LINK, LOG_LINE, LOG_PATH, parse_date

# date: the YYYY-MM-DD text; day: it as a date (None if impossible, e.g. 2026-02-30);
# op: the operation; rest: everything after it; what: the part before `->`;
# targets: the link targets after `->` ([] when there is no arrow); arrow: whether there was one.
Event = collections.namedtuple("Event", "date day op rest what targets arrow")


def read_events(root):
    """[Event] for every dated line in the log, in file order."""
    path = os.path.join(root, LOG_PATH)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            m = LOG_LINE.match(raw.strip())
            if not m:
                continue
            date, op, rest = m.groups()
            what, arrow, after = rest.partition("->")
            out.append(Event(date, parse_date(date), op, rest, what.strip(),
                             [t.strip() for t in LINK.findall(after)] if arrow else [], bool(arrow)))
    return out


def is_rehearsal_pass(event):
    """`DATE recall rehearse -> [[page]]`: the owner recalled the page."""
    return event.op == "recall" and event.what.split()[:1] == ["rehearse"]


def is_rehearsal_miss(event):
    """`DATE rehearse missed -> [[page]]`: the owner did not."""
    return event.op == "rehearse" and event.what.split()[:1] == ["missed"]
