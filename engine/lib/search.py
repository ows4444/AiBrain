"""Find pages: by their words (search), or by words and then association (recall).

Usage:
    brain search QUERY... [--type TYPE ...] [--dormant] [--limit N] [--json]
    brain recall QUERY... [--type TYPE ...] [--also WORDING ...] [--project NAME] [--hops N] [--dormant] [--limit N]
                          [--all] [--json]

Both take --type (only pages of that type; repeat it for more), --dormant
(the pages in dormant/ too) and --limit. --also, --project, --hops and --all
are recall's alone: search refuses each by name, since it would take the flag
and do nothing with it, and the caller would think the result narrowed.

search  BM25 over title (x3), aliases (x2), the questions a page says it answers (`answers:`,
        x2), body and summary (x0.5). Replaces grepping the brain: same words, ranked, stop
        words and simple suffixes ignored.
recall  search hits seed an activation that spreads along links (typed links
        and pairs recalled together before carry more), so pages one or two
        links from the words can come back. Each page shows how it was
        reached, its confidence (sources behind it) and flags: named,
        disputed, contradicted, stale (ask the owner whether it still holds),
        generated, dormant. A page is `named` when the question is its name
        (`what is X?`, and a page called X): it is the question's subject,
        so it is listed first whatever its score, and never cut.
        A contradicted page names the pages that say the opposite
        (`against`), whether or not they are among the rows: read them too.
        --type lists only pages of those types. The spread still goes by
        every page: the rows are cut to the types, then to --limit.
        --project biases toward the pages a project links to.
        --hops is how many links are followed from each hit.
        --also gives another wording of the same question (repeat it): the
        field's own terms for it, or plainer words. Each wording is searched
        and a page's scores are added up before the spread, the question as
        asked counting as much as its other wordings together. So a page
        that only the right term reaches, and one that only plain words
        reach, both come back, and the words every wording keeps count most.
        A model asking for the owner passes two. Whether the brain covers
        the question is still judged on the question as asked.
        `read first` names the section of a page that holds the words of
        the question its title does not, with its lines: open that part,
        and the rest only if it does not answer. A page the question names
        has none: it is read from the top.
        It stops where the match stops: rows scoring under 0.4 of the best
        are cut, and when the best page holds too little of the question it
        says so in one line and lists nothing. --all turns both off; use it
        before concluding that no page answers. (0.4, the two hops and the
        rest are thresholds: a brain may hold its own in hippocampus/tuning.md.)
held    both also list ideas held on an episode (named by a source, no page
        yet) that the question names: the idea's one line, its episode and
        how many sources name it. An answer may use the line, citing the
        episode and saying how many sources it rests on.

Reads only, apart from the search cache (.cache/, see `brain cache`). It never writes the log: the skill that answers from these pages
logs `DATE recall <question> -> [[page]], ...` for the pages that contributed.
"""
from refusal import Refused
from vaultlib import PAGE_TYPES, Vault

# The flags that are recall's alone: (the flag, whether a run was given it, what recall does with it and search does not).
RECALL_ONLY = (
    ("--also", lambda args: bool(args.also), "which fuses the wordings; search takes one"),
    ("--project", lambda args: args.project is not None,
     "which leans toward the pages a project links to; search goes by the words alone"),
    ("--hops", lambda args: args.hops is not None, "which follows links from each hit; search follows none"),
    ("--all", lambda args: args.everything, "which cuts weak rows and may list none; search cuts nothing"),
)


def search_rows(vault, query, types=None, dormant=False, limit=10):
    return [{"page": p.rel, "title": p.title, "type": p.type, "score": round(s, 3), "summary": p.summary}
            for p, s in vault.search(query, types=types, dormant=dormant, limit=limit)]


def recall_rows(vault, query, project=None, limit=10, hops=None, dormant=False, everything=False, also=(), types=None):
    rows = vault.recall(query, project=project, limit=limit, hops=hops, dormant=dormant, also=also, types=types,
                        floor=0.0 if everything else vault.tuning.recall_floor, abstain=not everything)
    return [{"page": r["page"].rel, "title": r["page"].title, "type": r["page"].type, "score": r["score"],
             "summary": r["page"].summary,
             "hop": r["hop"], "from": r["from"].rel, "confidence": r["confidence"], "flags": r["flags"],
             "against": [p.rel for p in r["against"]], "section": r["section"]}
            for r in rows]


def held_rows(vault, query):
    return [{"name": h["name"], "note": h["note"], "episodes": [p.rel for p in h["episodes"]], "sources": h["sources"]}
            for h in vault.held_ideas(query)]


def held_lines(held):
    lines = ["held ideas (no page yet; cite the episode and say how many sources):"] if held else []
    for h in held:
        note = f" - {h['note']}" if h["note"] else ""
        lines.append(f"  {h['name']}{note}  [{', '.join(h['episodes'])}; {h['sources']} source{'s' * (h['sources'] != 1)}]")
    return lines


def arguments(ap):
    ap.add_argument("query", nargs="+")
    ap.add_argument("--type", action="append", choices=PAGE_TYPES, dest="types",
                    help="only pages of this type; repeat it for more")
    ap.add_argument("--dormant", action="store_true", help="the pages in dormant/ too")
    ap.add_argument("--project", help="recall: lean toward the pages this project links to")
    ap.add_argument("--also", action="append", default=[], metavar="WORDING",
                    help="recall: another wording of the same question; repeat it. The scores are added up")
    ap.add_argument("--hops", type=int,
                    help="recall: links followed from each hit; the brain's spread_hops when not given")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--all", action="store_true", dest="everything",
                    help="recall: every row, however weak, and no abstaining")


def run(root, args):
    """`args.mode` is `search` or `recall`: the command's own name, which `brain` sets."""
    if args.mode == "search":
        for flag, given, does in RECALL_ONLY:
            if given(args):
                raise Refused(f"brain search: {flag} is for recall, {does}")
    vault = Vault(root)
    query = " ".join(args.query)
    also = [w.strip() for w in args.also if w.strip()]
    if args.mode == "search":
        rows = search_rows(vault, query, args.types, args.dormant, args.limit)
    else:
        try:
            rows = recall_rows(vault, query, args.project, args.limit, args.hops, args.dormant, args.everything, also,
                               args.types)
        except ValueError as e:
            raise Refused(str(e)) from None
    # recall found words but too little of the question: name the pages, list nothing
    weak = ([p.rel for p, _ in vault.search(query, types=args.types, dormant=args.dormant, limit=3)]
            if args.mode == "recall" and not rows and not args.everything else [])
    held = held_rows(vault, query)
    return dict({"query": query, "mode": args.mode, "results": rows}, **({"also": also} if also else {}),
                **({"weak": weak} if weak else {}), **({"held": held} if held else {}))


def weak_said(result, args):
    """A recall whose best page holds too little of the question: one line that names what its words barely reach."""
    return [f'recall: no confident match for "{result["query"]}"; its words barely reach '
            f'{", ".join(result["weak"])} (--all lists them)']


def nothing_said(result, args):
    return [f'{result["mode"]}: nothing matches "{result["query"]}"' + ("" if args.dormant else " (try --dormant)")]


def head_said(result, args):
    """The command and the question, the project a recall leaned toward, and each other wording it was asked in."""
    return ([f'{result["mode"]}: "{result["query"]}"' + (f"  [project {args.project}]" if args.project else "")]
            + [f'  also asked as: "{wording}"' for wording in result.get("also", [])])


def reached_said(r):
    """Under a recall's row: how the page was reached, how far to trust it, who says the opposite, where to read first."""
    how = "hit" if r["hop"] == 0 else f"{r['hop']} hop{'s' * (r['hop'] > 1)} from {r['from']}"
    conf = f"{r['confidence']['level']}: {r['confidence']['why']}" if r["confidence"] else "dormant"
    return ([f"{how}; {conf}" + (f"; {', '.join(r['flags'])}" if r["flags"] else "")]
            + ([f"the opposite is said by: {', '.join(r['against'])}"] if r["against"] else [])
            + (["read first: ## {heading} (lines {line}-{end})".format(**r["section"])] if r["section"] else []))


def row_said(r, recalled):
    """One page: its score and path, then under it its summary, and for a recall what `reached_said` adds."""
    under = [r["summary"] or "(no summary: open the page to judge it)"] + (reached_said(r) if recalled else [])
    return f"  {r['score']:>7.3f}  {r['page']}" + "".join(f"\n           {line}" for line in under)


def rows_said(result, args):
    return [row_said(r, result["mode"] == "recall") for r in result["results"]]


def cut_said(result, args):
    """A recall that lists fewer rows than it may has cut the weaker ones, and says so."""
    cut = result["mode"] == "recall" and not args.everything and len(result["results"]) < args.limit
    return ["  weaker matches are cut (--all lists them)"] if cut else []


def held_said(result, args):
    return held_lines(result.get("held", []))


def stale_said(result, args):
    stale = [r["page"] for r in result["results"] if "stale" in r.get("flags", [])]
    return ["ask the owner whether these still hold: " + ", ".join(stale)] if stale else []


# What the text holds, in the order it is printed, for each way a run can end: a recall that found too little
# of the question, a run that found nothing, and one that found pages. Each part is a function of the result
# and the arguments and gives its lines, none when it has nothing to say. The held ideas are said in all three.
WEAK = (weak_said, held_said)
NOTHING = (nothing_said, held_said)
FOUND = (head_said, rows_said, cut_said, held_said, stale_said)


def render(result, args):
    parts = WEAK if "weak" in result else FOUND if result["results"] else NOTHING
    return "\n".join(line for said in parts for line in said(result, args))
