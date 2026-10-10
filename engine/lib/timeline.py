"""What happened in a period: pages made and changed, operations, questions, rehearsals.

Usage:
    brain since FROM [--until TO] [--json]

FROM and TO are YYYY-MM-DD or YYYY-MM (a whole month); TO defaults to today,
or the end of the month when FROM is a month and --until is not given.
Answers "what did I learn in March" and "what changed since my last
session" from `created:`, `updated:` and the log. Reads only.
"""
import calendar
import datetime
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from vaultlib import Vault, is_rehearsal_miss, is_rehearsal_pass, parse_date  # noqa: E402

MONTH = re.compile(r"^(\d{4})-(\d{2})$")


def bounds(text, end=False):
    """A date from YYYY-MM-DD, or the first (last, with end) day of YYYY-MM."""
    m = MONTH.match(text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        return datetime.date(year, month, calendar.monthrange(year, month)[1] if end else 1)
    day = parse_date(text)
    if not day:
        raise ValueError(f"not a date or a month: {text}")
    return day


def timeline(vault, start, end):
    within = lambda d: d is not None and start <= d <= end  # noqa: E731
    created = [p for p in vault.knowledge if within(parse_date(p.fields.get("created", "")))]
    changed = [p for p in vault.knowledge if p not in created and within(p.updated)]
    events = [e for e in vault.events if within(e.day)]
    return {
        "from": start.isoformat(), "until": end.isoformat(),
        "created": {t: sorted(p.rel for p in created if p.type == t) for t in sorted({p.type for p in created})},
        "updated": sorted(p.rel for p in changed),
        "operations": dict(Counter(e.op for e in events).most_common()),
        "questions": [f"{e.date} {e.what}" for e in events
                      if e.op == "recall" and not is_rehearsal_pass(e)],
        "rehearsals": {"passed": sum(len(e.targets) for e in events if is_rehearsal_pass(e)),
                       "missed": sum(len(e.targets) for e in events if is_rehearsal_miss(e))},
    }


def arguments(ap):
    ap.add_argument("start")
    ap.add_argument("--until")


def run(root, args):
    vault = Vault(root)
    try:
        start = bounds(args.start)
        end = bounds(args.until, end=True) if args.until else (
            bounds(args.start, end=True) if MONTH.match(args.start) else vault.today)
    except ValueError as e:
        raise Refused(str(e)) from None
    return timeline(vault, start, end)


def render(t, args):
    made = sum(len(v) for v in t["created"].values())
    out = [f"{t['from']} .. {t['until']}",
           f"created  {made}  " + " ".join(f"{k}:{len(v)}" for k, v in t["created"].items())]
    out += [f"  + {rel}" for rels in t["created"].values() for rel in rels]
    out.append(f"updated  {len(t['updated'])}")
    out += [f"  ~ {rel}" for rel in t["updated"]]
    out.append("operations  " + (", ".join(f"{op} {n}" for op, n in t["operations"].items()) or "none"))
    out.append(f"rehearsals  {t['rehearsals']['passed']} passed, {t['rehearsals']['missed']} missed")
    if t["questions"]:
        out += ["questions asked"] + [f"  {q}" for q in t["questions"]]
    return "\n".join(out)
