"""The error log: what the engine swallowed or refused, kept for refactoring.

Hooks fail silent on purpose (a prompt, a compaction or a status line is never
blocked by the brain's own bug) and they refuse writes with a message that is
shown once. Both leave one line here, in .cache/errors.log:

    YYYY-MM-DD HH:MM <source> <kind> | <detail>

`source` is the hook or script, `kind` is `error` (it crashed and went on) or
the rule that refused (`senses`, `log`, `expected`, `schema`, `secret`, `recall`).
Read it with:

    brain errors              counts by source and kind, newest last seen, then the last lines
    brain errors --since DATE only lines from DATE on
    brain errors --tail N     the last N lines (default 10)
    brain errors --json       the same as data; after --clear, where the log was and whether there was one
    brain errors --clear      delete the log

`note` never raises and imports nothing from the engine, so the walls can call
it without a new way to fail. The file is capped (CAP bytes, then the old one
becomes errors.log.1) and git ignores .cache/. It is a diagnostic, not memory.
"""
import datetime
import os
import sys

LOG = os.path.join(".cache", "errors.log")
CAP = 256 * 1024
SHOWN = 200  # characters of detail kept per line


def brain_of(start):
    """The nearest folder at or above `start` holding cortex/ and hippocampus/, else None."""
    here = os.path.realpath(start)
    while True:
        if all(os.path.isdir(os.path.join(here, d)) for d in ("cortex", "hippocampus")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def note(source, kind, detail=None, root=None):
    """Append one line for `source`; with no `detail`, describe the exception being handled.

    `root` names the brain when the caller knows it; otherwise it is found from the project dir. Never raises.
    """
    try:
        root = brain_of(root or os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        if root is None:
            return
        if detail is None:
            exc = sys.exc_info()
            tb = exc[2]
            while tb is not None and tb.tb_next is not None:
                tb = tb.tb_next
            where = f" at {os.path.basename(tb.tb_frame.f_code.co_filename)}:{tb.tb_lineno}" if tb else ""
            detail = f"{exc[0].__name__}: {exc[1]}{where}" if exc[0] else "no detail"
        path = os.path.join(root, LOG)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > CAP:
            os.replace(path, path + ".1")
        line = f"{datetime.datetime.now():%Y-%m-%d %H:%M} {source} {kind} | {' '.join(str(detail).split())[:SHOWN]}\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:  # noqa: BLE001  a logger that fails must not break what it watches
        pass


def read(root, since=None):
    """[(date, time, source, kind, detail)] oldest first; lines that do not parse are skipped."""
    path = os.path.join(root, LOG)
    if not os.path.isfile(path):
        return []
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for text in fh:
            head, _, detail = text.rstrip("\n").partition(" | ")
            parts = head.split(" ")
            if len(parts) != 4 or (since and parts[0] < since):
                continue
            rows.append((*parts, detail))
    return rows


def summary(rows):
    """[{source, kind, count, last}] most frequent first."""
    groups = {}
    for date, clock, source, kind, _ in rows:
        entry = groups.setdefault((source, kind), {"source": source, "kind": kind, "count": 0, "last": ""})
        entry["count"] += 1
        entry["last"] = f"{date} {clock}"
    return sorted(groups.values(), key=lambda e: (-e["count"], e["source"], e["kind"]))


def arguments(ap):
    ap.add_argument("--since", metavar="YYYY-MM-DD")
    ap.add_argument("--tail", type=int, default=10, metavar="N")
    ap.add_argument("--clear", action="store_true")


def run(root, args):
    path = os.path.join(root, LOG)
    if args.clear:
        existed = os.path.exists(path)
        if existed:
            os.remove(path)
        return {"path": path, "cleared": existed}
    rows = read(root, args.since)
    last = rows[-args.tail:] if args.tail > 0 else []
    return {"path": path, "total": len(rows), "groups": summary(rows),
            "last": [dict(zip(("date", "time", "source", "kind", "detail"), r)) for r in last]}


def render(result, args):
    if "cleared" in result:
        return "errors: " + ("log cleared" if result["cleared"] else "nothing to clear")
    if not result["total"]:
        return "errors: none logged" + (f" since {args.since}" if args.since else "") + f" ({LOG})"
    out = [f"errors: {result['total']} logged ({LOG})"]
    out += [f"  {g['count']:>4}  {g['source']} {g['kind']}  (last {g['last']})" for g in result["groups"]]
    if result["last"]:
        out += ["\nlast:"] + [f"  {r['date']} {r['time']} {r['source']} {r['kind']} | {r['detail']}"
                             for r in result["last"]]
    return "\n".join(out)
