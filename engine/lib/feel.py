"""What the record gives the brain to feel, each feeling with what it rests on.

Usage:
    brain feel [WORD ...] [--limit N] [--json]

A feeling is worked out here from the log and the pages each time it is asked
for; none is kept. A rule reads an event or a state that stands today:

    surprise      new input says the opposite of a page; a decision turned out
                  other than expected
    frustration   a rehearsal missed; a question asked again and still not
                  answered; a decision that turned out worse; a reminder done
                  after its day
    curiosity     a question no page answers, each time it is asked
    satisfaction  a rehearsal passed; a decision that turned out as expected
                  or better; a reminder done by its day
    worry         a goal at risk or past its date; a decision past its
                  review; a reminder due

An event counts for one and fades by half every 7 days; a state that stands
counts one more for each 7 days it has stood. Three fresh events of one kind
toward one target are that feeling at its strongest (1.00), and one weaker
than 0.10 has faded and is not listed. (7, 3 and 0.1 are thresholds: a brain
may hold its own in hippocampus/tuning.md.)

The mood comes first: the same events read over 30 days and added up across
every target, each target counting for one at most. It is content when what
was done well outweighs what was missed and is overdue by a third of both,
uneasy the other way, even between, curious when there are only questions and
surprises, and quiet when the record gives nothing to feel.

The target is a page, a goal or a reminder, or the words an unanswered
question is known by. WORD keeps the feelings whose target holds every word
given, or is the page the words name. Under each feeling are its causes, the
one that counts most first, with its day.

It reads only, and writes no log line. It orders attention and nothing else:
what a page is held to be worth is its confidence, from the evidence alone.
It is a model of affect, read off the record; it says nothing of experience.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import Vault  # noqa: E402

CAUSES = 3  # causes printed under a feeling; --json has them all


def about(vault, rows, words):
    """The rows whose target holds every word, or is the page the words name."""
    named = vault.resolve(" ".join(words))
    return [r for r in rows if all(w.lower() in r["target"].lower() for w in words)
            or (named is not None and r["kind"] == "page" and r["target"] == named.rel)]


def arguments(ap):
    ap.add_argument("words", nargs="*", metavar="WORD", help="only what is felt toward a target holding these words")
    ap.add_argument("--limit", type=int, default=10)


def run(root, args):
    vault = Vault(root)
    rows = vault.feelings()
    rows = about(vault, rows, args.words) if args.words else rows
    limit = max(args.limit, 0)
    return {"date": vault.today.isoformat(), "about": " ".join(args.words), "half_life": vault.tuning.feeling_half_life,
            "mood": dict(vault.mood(), said=vault.mood_said()), "feelings": rows[:limit],
            "more": max(0, len(rows) - limit)}


def render(result, args):
    toward = f' toward "{result["about"]}"' if result["about"] else ""
    mood = [f"  mood: {result['mood']['said']}"] if result["mood"]["said"] else []
    if not result["feelings"] and not result["more"]:
        return "\n".join([f"feel, {result['date']}: nothing{toward} is felt now. No event in the log and no state of "
                          "the pages is recent enough to count"] + mood)
    out = [f"feel, {result['date']}: what the record gives to feel{toward} "
           f"(each cause fades by half in {result['half_life']} days)"] + mood
    for r in result["feelings"]:
        out.append(f"  {r['intensity']:.2f}  {r['feeling']:<12}  {r['target']}" + ("" if r["kind"] == "page" else f"  ({r['kind']})"))
        out += [f"        {c['date']}  {c['why']}" for c in r["causes"][:CAUSES]]
        if len(r["causes"]) > CAUSES:
            out.append(f"        and {len(r['causes']) - CAUSES} more (--json has every cause)")
    if result["more"]:
        out.append(f"  and {result['more']} weaker (--limit N lists more)")
    return "\n".join(out)
