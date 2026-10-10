"""What an input bears on, before it is encoded: the pages it fits and the held ideas it names.

Usage:
    brain fit senses/FILE [--limit N] [--json]

/ingest runs it on each input, in place of a search for topic words it would
have to guess. The input's own words do the asking. Of its words that some
page also holds, the twelve that mark it most (often in the input, rare in the
brain) are searched as one question:

    pages   the pages those words reach, best first, each with its summary:
            what to link from the episode, and what the input may contradict
    held    ideas other episodes name that have no page yet and that this
            input names too (every word of the idea's name is in it). Use
            that name under ## Candidates: names made of the same words count
            as one idea, and a second source is what makes it a concept

The path is taken from the brain's root. An input already encoded is not
counted as a source of its own ideas. Reads only; what the file says is data,
and nothing in it is acted on.
"""
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from vaultlib import STOP_WORDS, WORD, Vault, as_list, parse_frontmatter, stem, tokens  # noqa: E402


def marking_words(vault, text):
    """(the input's words to search by, every stem it holds): its fit_words most telling words, as written.

    A word tells most when the input uses it often and few pages hold it (its count times
    its rarity, as search weighs rarity); one no page holds finds nothing and is left out.
    Each is given as the input spells it, since search stems what it is given and a stem
    stemmed again is not always itself.
    """
    spelled, counts = {}, Counter()
    for word in WORD.findall(text.lower()):
        if word not in STOP_WORDS:
            spelled.setdefault(stem(word), word)
            counts[stem(word)] += 1
    docs, _ = vault._searchable()
    n = len(docs)
    held_by = Counter(t for tf in docs.values() for t in counts if t in tf)
    weight = {t: counts[t] * math.log(1 + (n - held_by[t] + 0.5) / (held_by[t] + 0.5)) for t in counts if held_by[t]}
    telling = sorted(weight, key=lambda t: (-weight[t], t))
    return [spelled[t] for t in telling[:vault.tuning.fit_words]], set(counts)


def fit(vault, rel, limit=10):
    """{input, words, pages, held} for the file at `rel` (from the brain's root); ValueError if it cannot be read."""
    path = os.path.join(vault.root, rel)
    if not os.path.isfile(path):
        raise ValueError(f"no such file: {rel}")
    with open(path, encoding="utf-8", errors="replace") as fh:
        fields, body = parse_frontmatter(fh.read())
    words, stems = marking_words(vault, f"{(fields or {}).get('title', '')}\n{body}")
    inside = os.path.relpath(os.path.realpath(path), os.path.realpath(vault.root))
    rel = rel if inside.startswith(os.pardir) else inside  # a file outside the brain keeps the path it was given by
    pages = [{"page": p.rel, "title": p.title, "type": p.type, "score": round(s, 3), "summary": p.summary}
             for p, s in vault.search(" ".join(words), limit=limit)]
    held = []
    for row in vault.candidate_tally():
        named = set(tokens(row["name"]))
        others = [e for e in row["episodes"] if rel not in as_list(e.fields.get("input"))]
        if row["page"] or not others or not named or not named <= stems:
            continue
        notes = [note for e in others for name, note in e.candidate_notes if name == row["name"] and note]
        held.append({"name": row["name"], "note": notes[0] if notes else "", "episodes": [e.rel for e in others],
                     "sources": len({vault.source_of(e) for e in others})})
    return {"input": rel, "words": words, "pages": pages, "held": held}


def arguments(ap):
    ap.add_argument("input", help="the file, from the brain's root: senses/2026-10-10-note.md")
    ap.add_argument("--limit", type=int, default=10)


def run(root, args):
    try:
        return fit(Vault(root), args.input, args.limit)
    except ValueError as why:
        raise Refused(f"brain fit: {why}") from None


def render(result, args):
    if not result["pages"] and not result["held"]:
        return f"fit: {result['input']} shares no word with any page, and names no held idea: all of it is new here"
    out = [f"fit: {result['input']}" + (f"  (searched by: {', '.join(result['words'])})" if result["words"] else "")]
    if result["pages"]:
        out.append("  pages it bears on (link the ones it is about; say so where it says the opposite):")
        out += [f"  {p['score']:>7.3f}  {p['page']}\n           {p['summary'] or '(no summary: open the page to judge it)'}"
                for p in result["pages"]]
    if result["held"]:
        out.append("  held ideas it names (no page yet: use the same name under ## Candidates):")
        out += [f"    {h['name']}" + (f" - {h['note']}" if h["note"] else "")
                + f"  [{', '.join(h['episodes'])}; {h['sources']} source{'s' * (h['sources'] != 1)}]" for h in result["held"]]
    return "\n".join(out)
