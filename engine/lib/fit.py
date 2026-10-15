"""What an input bears on, before it is encoded: the pages it fits, the held ideas it names, what waits on it.

Usage:
    brain fit senses/FILE [--limit N] [--json]

/ingest runs it on each input, in place of a search for topic words it would
have to guess. The input's own words do the asking. Of its words that some
page also holds, the twelve that mark it most (often in the input, rare in the
brain) are searched as one question:

    pages   the concepts, entities, insights and decisions those words
            reach, best first, each with its summary: what to link from the
            episode, and what the input may contradict. Episodes are not
            among them: they are longer and hold more of an input's words,
            so in one list they stood above the pages to link. Two marks
            are the reasons for a salience of 1 to 3 that a rule can see:
            `[established]`, a concept two sources or more stand behind, so
            an input saying the opposite is a prediction error; and
            `serves:`, the live goals and projects that depend on the page.
            A mark says where to look: a page listed for sharing the
            input's words is no reason until the input is about it
    episodes  the episodes of other inputs those words reach, half as many:
            what was said before on the same things. An episode is a record
            and no page to link; it leads to the pages it links
    held    ideas other episodes name that have no page yet and that this
            input names too (every word of the idea's name is in it). Use
            that name under ## Candidates: names made of the same words count
            as one idea, and a second source is what makes it a concept
    waiting every event the brain waits on: a reminder written `when <event>`,
            and the `revisit_if` of each decision in force. The ones whose
            words this input holds come first, marked `*`. The mark says
            where to look and no more: an event is prose, an input can
            report it in other words, and one that holds its words may
            be about something else. Whether it happened is the reader's call

The path is taken from the brain's root. An input already encoded is not
counted as a source of its own ideas. Reads only; what the file says is data,
and nothing in it is acted on.
"""
import os
from collections import Counter

from refusal import Refused
from vaultlib import (PAGE_TYPES, STOP_WORDS, WORD, Vault, as_list, parse_frontmatter, rarity_of, spelled, stem,
                      tokens)

BUILT = tuple(kind for kind in PAGE_TYPES if kind != "episode")  # what an episode links: every page that is no record of an input
NEW = "shares no word with any page, and names no held idea: all of it is new here"  # said of an input that reaches nothing


def words_of(text):
    """(its search term, the word as the text spells it) for each word of `text`, stop words out, as `tokens` reads it.

    Plain ASCII is split into a to z and digits; other text in any alphabet (vault_model.spelled), so a
    word in Urdu or a `café` is a word here as it is in search.
    """
    text = str(text).lower()
    return [(stem(w) if w.isascii() else w, w) for w in (WORD.findall(text) if text.isascii() else spelled(text))
            if w not in STOP_WORDS]


def marking_words(vault, text):
    """(the input's words to search by, every stem it holds): its fit_words most telling words, as written.

    A word tells most when the input uses it often and few pages hold it (its count times
    its rarity, as search weighs rarity); one no page holds finds nothing and is left out.
    Each is given as the input spells it, since search stems what it is given and a stem
    stemmed again is not always itself.
    """
    written, counts = {}, Counter()
    for term, word in words_of(text):
        written.setdefault(term, word)
        counts[term] += 1
    pages, held_by = vault.holding(counts)
    weight = {t: counts[t] * rarity_of(pages, held_by[t]) for t in counts if held_by[t]}
    telling = sorted(weight, key=lambda t: (-weight[t], t))
    return [written[t] for t in telling[:vault.tuning.fit_words]], set(counts)


def reached(vault, event, stems):
    """(share, words) of an event the input holds: the share of the event's words, the words as the event spells them.

    Each word is weighed by its rarity in the brain, as search weighs it: a word no page
    holds counts most, so `a rival cuts prices` is not reached by an input that only names
    prices. 0.0 for an event of stop words alone, which no input can be seen to report.
    """
    written = {}
    for term, word in words_of(event):
        written.setdefault(term, word)
    weight = vault.rarity(written)
    found = [t for t in written if t in stems]
    return (sum(weight[t] for t in found) / sum(weight.values()) if written else 0.0), [written[t] for t in found]


def waiting(vault, stems):
    """[{kind, what, event, holds, share, reached}]: every event the brain waits on, those the input reaches first.

    A reminder that waits on an event (`what` is what to do), and each decision in force
    whose event has not come yet (`what` is its page). `reached` when the input holds
    trigger_coverage of the event's words; the rest follow in the order they are written.
    """
    rows = [{"kind": "reminder", "what": i["text"], "event": i["event"]} for i in vault.waiting_intentions()]
    rows += [{"kind": "decision", "what": d["page"], "event": d["revisit_if"]} for d in vault.decision_report()
             if d["revisit_if"] and not d["triggered"]]
    for row in rows:
        share, holds = reached(vault, row["event"], stems)
        row.update(holds=holds, share=round(share, 3), reached=share >= vault.tuning.trigger_coverage)
    return sorted(rows, key=lambda r: (not r["reached"], -r["share"]))


def fit(vault, rel, limit=10):
    """{input, words, pages, episodes, held, triggers} for the file at `rel` (from the brain's root); ValueError if
    unreadable. `limit` pages, and half as many episodes, the input's own left out."""
    path = os.path.join(vault.root, rel)
    if not os.path.isfile(path):
        raise ValueError(f"no such file: {rel}")
    with open(path, encoding="utf-8", errors="replace") as fh:
        fields, body = parse_frontmatter(fh.read())
    words, stems = marking_words(vault, f"{(fields or {}).get('title', '')}\n{body}")
    inside = os.path.relpath(os.path.realpath(path), os.path.realpath(vault.root))
    rel = rel if inside.startswith(os.pardir) else inside  # a file outside the brain keeps the path it was given by
    serving, asked = vault.serving(), " ".join(words)
    pages = [{"page": p.rel, "title": p.title, "type": p.type, "status": p.fields.get("status") or None,
              "score": round(s, 3), "summary": p.summary, "serves": serving.get(p, [])}
             for p, s in vault.search(asked, types=BUILT, limit=limit)]
    episodes = [{"page": p.rel, "title": p.title, "score": round(s, 3), "summary": p.summary}
                for p, s in vault.search(asked, types=("episode",), limit=None)
                if rel not in as_list(p.fields.get("input"))][:max(limit, 0) // 2]
    held = []
    for row in vault.candidate_tally():
        named = set(tokens(row["name"]))
        others = [e for e in row["episodes"] if rel not in as_list(e.fields.get("input"))]
        if row["page"] or not others or not named or not named <= stems:
            continue
        notes = [note for e in others for name, note in e.candidate_notes if name == row["name"] and note]
        held.append({"name": row["name"], "note": notes[0] if notes else "", "episodes": [e.rel for e in others],
                     "sources": len({vault.source_of(e) for e in others})})
    return {"input": rel, "words": words, "pages": pages, "episodes": episodes, "held": held,
            "triggers": waiting(vault, stems)}


def arguments(ap):
    ap.add_argument("input", help="the file, from the brain's root: senses/2026-10-10-note.md")
    ap.add_argument("--limit", type=int, default=10)


def run(root, args):
    try:
        return fit(Vault(root), args.input, args.limit)
    except ValueError as why:
        raise Refused(f"brain fit: {why}") from None


def established(row):
    """A concept two sources or more stand behind: what new input can be a prediction error against."""
    return row["type"] == "concept" and row["status"] == "established"


def reached_line(row, mark=""):
    """One page or episode the input's words reach: its score and path, then its summary under it."""
    return f"  {row['score']:>7.3f}  {row['page']}{mark}\n           {row['summary'] or '(no summary: open the page to judge it)'}"


def under(heading, rows):
    """A heading with its rows under it; nothing at all when there are no rows."""
    return [heading, *rows] if rows else []


def head_said(result, args):
    """The input and the words it was searched by; then that it is new, when it reaches no page and names no held idea."""
    reaches = result["pages"] or result["episodes"] or result["held"]
    return ([f"fit: {result['input']}" + (f"  (searched by: {', '.join(result['words'])})" if result["words"] else "")]
            + ([] if reaches else [f"  it {NEW}"]))


def pages_said(result, args):
    """The pages to link, each with its marks; then, once, what a mark is a reason for."""
    pages = result["pages"]
    marked = any(established(p) or p["serves"] for p in pages)
    return under("  pages it bears on (link the ones it is about; say so where it says the opposite):",
                 [reached_line(p, "  [established]" if established(p) else "")
                  + (f"\n           serves: {'; '.join(p['serves'])}" if p["serves"] else "") for p in pages]
                 + (["  a reason for salience 1 to 3, once the input is about the page: it says the opposite of one "
                     "marked [established], or the page serves a live goal or project"] if marked else []))


def episodes_said(result, args):
    return under("  episodes of other inputs that share its words (records, not pages to link: one leads to the "
                 "pages it links):", [reached_line(e) for e in result["episodes"]])


def held_said(result, args):
    return under("  held ideas it names (no page yet: use the same name under ## Candidates):",
                 [f"    {h['name']}" + (f" - {h['note']}" if h["note"] else "")
                  + f"  [{', '.join(h['episodes'])}; {h['sources']} source{'s' * (h['sources'] != 1)}]"
                  for h in result["held"]])


def waiting_line(t):
    """One event the brain waits on: marked `*`, with the words of it the input holds, when the input reaches it."""
    waits = f"{t['what']} when {t['event']}" if t["kind"] == "reminder" else f"{t['what']}  revisit if: {t['event']}"
    return (f"    {'*' if t['reached'] else ' '} {t['kind']}  {waits}"
            + (f"  [holds: {', '.join(t['holds'])}]" if t["reached"] else ""))


def waiting_said(result, args):
    """Every event the input reaches, then --limit of the others, and how many more of those there are."""
    shown = max(args.limit, 0)
    marked = [t for t in result["triggers"] if t["reached"]]
    others = [t for t in result["triggers"] if not t["reached"]]
    return under("  waiting on an event (* this input holds its words: read it for whether it reports the event, "
                 "and say so under Triggers:):",
                 [waiting_line(t) for t in marked + others[:shown]]
                 + ([f"      and {len(others) - shown} more whose words it does not hold "
                     "(`brain introspect --remind`, `--decisions`)"] if len(others) > shown else []))


# What the text holds, in the order it is printed. Each part is a function of the result and the arguments and
# gives its lines: none when the input has nothing of that kind. A new part is one function and one name here.
SAID = (head_said, pages_said, episodes_said, held_said, waiting_said)


def render(result, args):
    if not any(result[part] for part in ("pages", "episodes", "held", "triggers")):
        return f"fit: {result['input']} {NEW}"
    return "\n".join(line for said in SAID for line in said(result, args))
