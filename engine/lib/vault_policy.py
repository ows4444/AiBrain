"""Policy: what the brain may do to itself with nobody there, in one registry, and a brain's own word on it.

An action is a `brain` command with its arguments fixed, under a name. Each has a tier:

    reads     it changes nothing: it may always run
    changes   it changes the brain, and git can undo it: it runs with nobody there only
              when hippocampus/policy.md names it
    outside   it reaches outside the brain (the network, another folder, this machine):
              no line of the policy can allow it; it waits for the owner's yes
    final     it cannot be undone: only the owner does it, in a session

A brain allows a changing action with a line under `## Allowed` in hippocampus/policy.md,

    - index (2026-10-12: the listing is worked out from the pages, so nothing is lost)

and `brain act NAME` is the one way an action runs: it asks decide() at that moment, with
the page as it then is. What a model says of an action (that it is safe, that it was
asked for) counts for nothing here. `brain check` fails on a line that names no action
or one no line can allow, and the page is the owner's to write: a wall refuses any other
hand (hooks/protect_policy.py).

A reminder that waits (its action is not allowed, or it failed too often) is a proposal,
and has a name of seven characters made from everything about it: its words, its plan
(each action and what must hold after it), its `when`, and how often it was started. The owner's yes for
that one proposal is a line under `## Once`, the name and the day they wrote it,

    - 3f9a2c1 2026-10-12 (just this time)

It lets that reminder run once and no other: change anything about the reminder and its
name is another; once it has started, its name is another too. And it lapses: it holds
for yes_days after its day. A line there is checked for its form only; whether a
proposal by that name still waits is seen when a round looks.

No dependencies. Nothing here walks the brain: the policy is one file, read by its path.
"""
import collections
import datetime
import difflib
import hashlib
import os
import re

POLICY_PATH = os.path.join("hippocampus", "policy.md")
ALLOWED = re.compile(r"^## Allowed[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)
ONCE = re.compile(r"^## Once[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)
BULLET = re.compile(r"^[-*]\s+")
# `- 3f9a2c1 2026-10-12`: the proposal's name and the day of the yes, then anything in brackets.
YES = re.compile(r"^[-*]\s+`?(?P<name>[0-9a-f]{7})`?\s+(?P<day>\d{4}-\d{1,2}-\d{1,2})\s*(?:\(.*\)\s*)?$")
# `- name`, then anything in brackets: why it is allowed, and since when.
LINE = re.compile(r"^[-*]\s+`?(?P<name>[A-Za-z][\w-]*)`?\s*(?:\(.*\)\s*)?$")

READS, CHANGES, OUTSIDE, FINAL = "reads", "changes", "outside", "final"
# What each tier means for a run with nobody there, said as the reason for the answer.
WHY = {
    READS: "it only reads",
    CHANGES: "it changes the brain, and {page} does not allow it: a line `- {name} (why)` under `## Allowed` there, "
             "written by the owner, lets it run with nobody there",
    OUTSIDE: "it reaches outside the brain, and no line of the policy can allow that: it waits for the owner's yes",
    FINAL: "it cannot be undone: only the owner does it, in a session",
}

# tier: one of the four above
# what: what it does, for the owner who decides whether to allow it
# command: the `brain` command it is, with its arguments; None for one that takes a target
#          (a URL, a page, an input) and so is never a fixed action: it is here to be
#          refused for the right reason, and so that the policy page cannot name it
# again: whether it may be run a second time when nobody knows if the first run ended (a
#        crash after it began). True for what only reads or rewrites what it derives.
Action = collections.namedtuple("Action", "tier what command again", defaults=(True,))
ACTIONS = {
    "check": Action(READS, "broken links, schema problems, index drift, edited inputs", ("check",)),
    "guard": Action(READS, "the same, and a scan for credentials and personal data", ("check", "--guard")),
    "digest": Action(READS, "everything that waits on the owner", ("tend", "--check")),
    "introspect": Action(READS, "the health metrics, with a verdict on each", ("introspect",)),
    "gaps": Action(READS, "what was asked and not answered", ("introspect", "--gaps")),
    "feel": Action(READS, "what the record gives the brain to feel, with its causes", ("feel",)),
    "index": Action(CHANGES, "rewrite the listing of hippocampus/index.md from the pages", ("index",)),
    "fingerprint": Action(CHANGES, "record a hash of each new input, so a later edit of one is caught", ("fingerprint",)),
    "snapshot": Action(CHANGES, "append today's metrics to hippocampus/metrics.md, once a day", ("introspect", "--snapshot")),
    "graph": Action(CHANGES, "write the link graph as one page into motor/graph/", ("graph", "--format", "html")),
    "work": Action(CHANGES, "carry out the reminders that name an action, a step each, and write each step in the log",
                   ("work",)),
    "door": Action(OUTSIDE, "take the notes that wait in the folder at the door, which is outside the brain", None),
    "fetch": Action(OUTSIDE, "a web page into senses/", None),
    "import": Action(OUTSIDE, "the notes of another tool into senses/", None),
    "export": Action(OUTSIDE, "copies of chosen pages for outside the brain", None),
    "schedule": Action(OUTSIDE, "install or remove a job on this machine", None),
    "forget": Action(FINAL, "remove an input and everything that rests on it", None),
}


def decide(name, allowed):
    """(whether the action may run with nobody there, why): the one place that says.

    `allowed` is the changing actions the brain's policy page names (policy_of). A name is
    taken as it is given: no other spelling, case or wording of it is an action.
    """
    action = ACTIONS.get(name)
    if action is None:
        close = difflib.get_close_matches(str(name), ACTIONS, n=1)
        return False, f"'{name}' is not an action" + (f" (closest: {close[0]})" if close else "") + "; `brain act` lists them"
    if action.tier == READS:
        return True, WHY[READS]
    if action.tier == CHANGES and name in allowed:
        return True, f"{POLICY_PATH} allows it"
    return False, WHY[action.tier].format(page=POLICY_PATH, name=name)


def read_policy(text):
    """([the changing actions it allows], [what is wrong]) from the `## Allowed` section of a policy page.

    A line there is `- name`, with an optional note in brackets after it. A name that is
    no action, or one of a tier no line can allow, is not used: it is listed, and the
    action stays refused. A line for an action that only reads changes nothing and is
    let be. Lines that are not list items are prose, and ignored.
    """
    section = ALLOWED.search(text)
    names, problems = [], []
    for line in (section.group(1).splitlines() if section else []):
        line = line.strip()
        if not BULLET.match(line):
            continue
        m = LINE.match(line)
        if not m:
            problems.append(f"cannot read '{line}': a line here is `- action (why)`")
            continue
        name = m.group("name")
        action = ACTIONS.get(name)
        if action is None:
            close = difflib.get_close_matches(name, ACTIONS, n=1)
            problems.append(f"'{name}' is not an action" + (f" (closest: {close[0]})" if close else "")
                            + "; `brain act` lists them")
        elif action.tier in (OUTSIDE, FINAL):
            problems.append(f"'{name}' cannot be allowed here: " + WHY[action.tier])
        elif name in names:
            problems.append(f"'{name}' is allowed twice; one line is enough")
        elif action.tier == CHANGES:
            names.append(name)
    return names, problems


def proposal(said, plan, when, started):
    """The name of one proposal: seven characters that are others once anything about it changes.

    `said` is the reminder's words as the log matches them, `plan` its actions and what
    must hold after each, as its line writes them, `when` its time, `started` how often
    the log says a step of it began.
    """
    return hashlib.sha256("\n".join((said, plan, when, str(started))).encode("utf-8")).hexdigest()[:7]


def read_once(text):
    """([(name, the day of the yes)], [what is wrong]) from the `## Once` section of a policy page.

    A line there is `- name YYYY-MM-DD`, with an optional note in brackets after it: the
    owner's yes for the one proposal of that name, on that day. A line that cannot be read
    so, or whose day is none, is listed and counts for nothing.
    """
    section = ONCE.search(text)
    said, problems = [], []
    for line in (section.group(1).splitlines() if section else []):
        line = line.strip()
        if not BULLET.match(line):
            continue
        m = YES.match(line)
        try:
            said.append((m.group("name"), datetime.date.fromisoformat(m.group("day"))))
        except (AttributeError, ValueError):  # no such line, or no such day
            problems.append(f"cannot read '{line}': a yes is `- <the proposal's name> YYYY-MM-DD (why)`, the name as "
                            "`brain tend --check` gives it and the day you write it")
    return said, problems


def policy_problems(text):
    """What is wrong with the lines of a policy page's text; [] if nothing."""
    return read_policy(text)[1] + read_once(text)[1]


def yes_of(root, today, days):
    """The names of the proposals the owner's yes holds for today: written on a day that has come, at most `days` ago."""
    path = os.path.join(root, POLICY_PATH)
    if not os.path.exists(path):
        return frozenset()
    with open(path, encoding="utf-8", errors="replace") as fh:
        said = read_once(fh.read())[0]
    return frozenset(name for name, day in said if day <= today <= day + datetime.timedelta(days=days))


def policy_of(root):
    """The changing actions the brain at `root` allows with nobody there; none for a brain without the page."""
    path = os.path.join(root, POLICY_PATH)
    if not os.path.exists(path):
        return frozenset()
    with open(path, encoding="utf-8", errors="replace") as fh:
        return frozenset(read_policy(fh.read())[0])
