"""The answer test set: after an engine change, does the brain still find the right pages?

Usage:
    brain eval [--root DIR] [--questions FILE] [--answers FILE] [--k N] [--json]
               [--save-baseline] [--baseline FILE] [--draft N] [--set NAME=VALUE ...]
    brain eval --from-log [--root DIR] [--k N] [--save-baseline] [--baseline FILE]
               [--set NAME=VALUE ...] [--json]

Runs on the fixture brain in engine/eval/fixture/ with engine/eval/questions.json
unless --root and --questions point elsewhere (an owner can keep a question
set for their own brain, e.g. in motor/).

Retrieval (default). Each covered question goes through `search` (words only)
and `recall` (words, then association; with the question's `project` if it
names one), and each is scored:
    hit@1   questions whose first page is an expected one
    hit@k   expected pages in the top k, as a share of the pages expected
    all@k   questions with every expected page in the top k
    mrr     1 / rank of the first expected page, averaged (0 if none in the top k)
    bytes   size of the top k pages, which is what an answer reads when it
            opens every page returned; the size of the expected pages alone
            (the least it could read); and, since recall prints each page's
            `summary:`, the size of that listing plus the expected pages:
            what an answer reads when the summaries lead it to the right
            pages and no others. That last number is a floor, not a
            measurement of what a reader does
Questions are scored in sets, each reported apart, because they fail for
different reasons and one number hides a change that helps one set and hurts
another: the standard set (questions with no `set`), `paraphrase` (no word
shared with the title or aliases of the expected pages) and `first` (the term
is named; which page comes first). The numbers at the top of the report and of
the JSON are the standard set's. A "buried" question is one whose first
expected page is below rank 3 or absent; it is listed with the page that
came first instead.

Recall is scored as `brain recall` runs it: rows under recall_floor of the
best are cut and a gross mismatch returns nothing, so `rows` and `bytes` are
what the command would hand an answer.

A question with `held` names an idea that has no page yet (a candidate on an
episode). It is scored on whether `held_ideas` lists that idea, and reports
the bytes of its one line against the episodes an answer would otherwise open.

Uncovered questions are listed with how many pages search returned and how
many recall lists: a retriever cannot know a question is uncovered, only that
its words barely reach any page; the answer has to say so.

Answers (--answers FILE, JSON {"q01": "text citing [[page]]", ...}), for
example from running /ask on each question in a copy of the fixture. A
covered answer scores citation recall (expected pages cited) and precision
(cited pages that are expected or acceptable); an uncovered one passes when
it says it is not covered and cites nothing.

--save-baseline writes the retrieval numbers of every set to
engine/eval/baseline.json (or --baseline FILE, which the text report also
compares against), with a hash of the brain's pages: numbers from a changed
brain are not comparable, and the report says when the hash differs. The
tests fail when `recall` falls below the saved one on any set. Reads only, apart from that.

--set NAME=VALUE runs the set with one threshold at another value (repeat it
for more): how a value is measured before the brain keeps it. Nothing is
written, the search cache included; the report names what was tried and the
brain's own value. To keep one, add `- NAME = VALUE (why)` under `## Overrides`
in the brain's hippocampus/tuning.md; `brain introspect --usage` lists every
threshold with its range. A baseline is never saved from a tried value.

--from-log takes the questions from the brain's own log, in place of a
question set: every recall line that is not a rehearsal is a question, and
the pages it names are the ones expected. A line that named none (`-> none`)
is an uncovered question. Each is replayed as the brain was on its day: the
log's lines before it, and no later one, so the line that recorded an answer
never helps to find it. The brain is --root, or the one `brain` is run in.
It is scored like a question set, and its baseline is kept in that brain, at
motor/eval-from-log-baseline.json. Two limits are printed with every result.
The questions are the ones recall already answered on the day they were
asked, so a fall is a regression and a high number is not quality. And the
pages are as they are now, not as they were. A line all of whose pages are
gone since (merged, renamed, faded) cannot be scored: it is listed, not run.

A question set for a brain other than the fixture keeps its baseline beside
it (`motor/eval-questions.json` -> `motor/eval-questions-baseline.json`), so
it never overwrites the engine's. `--draft N` prints, as JSON, N questions to
write for that brain: one page each that no question expects yet, concepts,
insights and entities before episodes, with the page's `summary` and the
words to `avoid` (its title and aliases), and an empty `question`. Whoever
fills them in asks what the page answers without those words; the set is
`paraphrase`. A question left empty is skipped. The report lists questions
that break their own set: an expected page that does not exist, or a
paraphrase that uses a word of the page's names.
"""
import contextlib
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused, brain_root  # noqa: E402
from vaultlib import (LINK, Vault, is_rehearsal_pass, parse_date, plain, setting, shown, tokens,  # noqa: E402
                      tuning_of)

EVAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval")
FIXTURE = os.path.join(EVAL, "fixture")
QUESTIONS = os.path.join(EVAL, "questions.json")
BASELINE = os.path.join(EVAL, "baseline.json")
FROM_LOG_BASELINE = os.path.join("motor", "eval-from-log-baseline.json")  # in the brain whose log it is
# What a replay of the log cannot show; printed with every result.
LIMITS = ("these are the questions recall already answered on the day they were asked: a fall is a regression, "
          "a high number is not quality",
          "each is replayed against the pages as they are now, not as they were that day")
SHOWN = 10              # questions listed of each kind in the text of --from-log; --json has them all
STANDARD = "standard"   # the set of a question that names none
BURIED_BELOW = 3        # a first expected page under this rank is buried
PARAPHRASE = "paraphrase"
DRAFT_TYPES = ("concept", "insight", "entity", "episode")  # the order pages are drafted in
NOT_COVERED = re.compile(r"not covered|no page|nothing (?:in|here|on|about)|does(?:n't| not) (?:answer|cover)"
                         r"|no (?:pages?|notes?|episodes?) (?:here )?(?:on|about|cover)", re.I)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def size(page):
    return len(page.text.encode("utf-8"))


def brain_hash(root):
    """A hash of every page under cortex/ and prefrontal/: the brain the numbers were measured on."""
    digest = hashlib.sha1()
    for folder in ("cortex", "prefrontal"):
        for base, dirs, files in os.walk(os.path.join(root, folder)):
            dirs.sort()
            for name in sorted(f for f in files if f.endswith(".md")):
                path = os.path.join(base, name)
                digest.update(os.path.relpath(path, root).replace(os.sep, "/").encode("utf-8"))
                with open(path, "rb") as fh:
                    digest.update(fh.read())
    return digest.hexdigest()[:16]


def names_of(page):
    return set(tokens(" ".join([page.title, *page.aliases])))


def question_problems(vault, questions):
    """Questions that break their own set: a page that is not there, a paraphrase that names its page."""
    problems = []
    for q in questions:
        for stem in q.get("expect", []):
            page = vault.resolve(stem)
            if page is None:
                problems.append(f"{q['id']}: expects [[{stem}]], which is not a page")
            elif q.get("set") == PARAPHRASE:
                names = names_of(page)  # stems; the report shows the question's own words
                shared = sorted({w for w in re.findall(r"[^\W_]+", q["question"].lower()) if names & set(tokens(w))})
                if shared:
                    problems.append(f"{q['id']}: not a paraphrase, it uses {', '.join(shared)} from [[{stem}]]")
    return problems


def draft(vault, questions, n):
    """N questions to write: a page no question expects yet, its summary, and the words to avoid."""
    taken = {vault.resolve(stem) for q in questions for stem in q.get("expect", [])}
    ids = {q["id"] for q in questions}
    pages = sorted((p for p in vault.knowledge if p.type in DRAFT_TYPES and p not in taken and not p.generated),
                   key=lambda p: (DRAFT_TYPES.index(p.type), p.rel))
    out, number = [], 0
    for page in pages[:max(n, 0)]:
        number += 1
        while f"o{number:02d}" in ids:
            number += 1
        out.append({"id": f"o{number:02d}", "set": PARAPHRASE, "question": "", "expect": [page.stem],
                    "summary": page.summary,
                    "avoid": sorted(set(re.findall(r"[^\W_]+", " ".join([page.title, *page.aliases]).lower())))})
    return out


def log_cases(vault):
    """(questions, lines not replayed) from the brain's own log: every recall line that is not a rehearsal.

    A question is what the line says before its arrow; the pages expected are the ones it
    names that are here now. A line that names none is a question no page answered. `line` is
    where it stands among the log's dated lines and `day` its date: it is asked of the brain
    as it was then (Vault.as_of). A line all of whose pages are gone since cannot be scored.
    """
    questions, gone = [], []
    for at, e in enumerate(vault.events):
        if e.op != "recall" or not e.arrow or not e.day or not e.what or is_rehearsal_pass(e):
            continue
        here = [p.stem for p in map(vault.resolve, e.targets) if p is not None and not p.is_system]
        if e.targets and not here:
            gone.append(f"{e.date} recall {e.rest}")
            continue
        asked = {"id": f"{e.date}#{at + 1}", "question": e.what, "date": e.date, "line": at, "day": e.day}
        questions.append(dict(asked, expect=sorted(set(here))) if here else dict(asked, covered=False))
    return questions, gone


def rank_scores(pages, expect, k):
    top = [p.stem for p in pages[:k]]
    found = [e for e in expect if e in top]
    first = next((i for i, stem in enumerate(top, 1) if stem in expect), None)
    return {"hit": len(found) / len(expect), "all": len(found) == len(expect), "rr": 1 / first if first else 0.0,
            "rank": first,
            "missed": [e for e in expect if e not in top], "top": top, "bytes": sum(size(p) for p in pages[:k]),
            "rows": len(pages[:k]),
            "listing": sum(len(f"{p.rel}\n{p.summary}\n".encode("utf-8")) for p in pages[:k]),
            "unsummarised": sum(not p.summary for p in pages[:k])}


def summary(rows):
    n = len(rows)
    return {"questions": n, "hit_at_1": round(sum(r["rank"] == 1 for r in rows) / n, 3) if n else 0.0,
            "hit_at_k": round(sum(r["hit"] for r in rows) / n, 3) if n else 0.0,
            "all_at_k": sum(r["all"] for r in rows), "mrr": round(sum(r["rr"] for r in rows) / n, 3) if n else 0.0,
            "rows": sum(r["rows"] for r in rows), "bytes_read": sum(r["bytes"] for r in rows), "bytes_needed": sum(r["needed"] for r in rows),
            "bytes_listing": sum(r["listing"] for r in rows),
            "bytes_by_summary": sum(r["listing"] + r["needed"] for r in rows),
            "unsummarised": sum(r["unsummarised"] for r in rows)}


def retrieval(vault, questions, k):
    out = {"search": [], "recall": [], "uncovered": [], "held": []}

    def recalled(q):  # as `brain recall` does it: weak rows cut, nothing on a gross mismatch
        then = vault.as_of(q["line"], q["day"]) if "line" in q else vault  # a logged question: the brain of its day
        return [r["page"] for r in then.recall(q["question"], project=q.get("project"), limit=k,
                                               floor=vault.tuning.recall_floor, abstain=True)]

    for q in questions:
        if "held" in q:  # the question names an idea still held on its episode
            listed = vault.held_ideas(q["question"])
            names = [h["name"].lower() for h in listed]
            row = next((h for h in listed if h["name"].lower() == q["held"].lower()), None)
            out["held"].append({"id": q["id"], "rank": names.index(q["held"].lower()) + 1 if row else None,
                                "row": len(f"{row['name']} - {row['note']}".encode("utf-8")) if row else 0,
                                "episodes": sum(size(p) for p in row["episodes"]) if row else 0})
            continue
        if q.get("covered", True) is False:
            out["uncovered"].append({"id": q["id"], "search_results": len(vault.search(q["question"], limit=k)),
                                     "recall_results": len(recalled(q))})
            continue
        searched = [p for p, _ in vault.search(q["question"], limit=k)]
        needed = sum(size(p) for p in map(vault.resolve, q["expect"]) if p)
        name = q.get("set", STANDARD)
        out["search"].append(dict(rank_scores(searched, q["expect"], k), id=q["id"], set=name, needed=needed))
        out["recall"].append(dict(rank_scores(recalled(q), q["expect"], k), id=q["id"], set=name, needed=needed))
    names = sorted({r["set"] for r in out["recall"]}, key=lambda s: (s != STANDARD, s))
    sets = {name: {mode: summary([r for r in out[mode] if r["set"] == name]) for mode in ("search", "recall")}
            for name in names}
    standard = sets.get(STANDARD) or {mode: summary([]) for mode in ("search", "recall")}
    return {"k": k, "search": standard["search"], "recall": standard["recall"], "sets": sets,
            "per_question": {"search": out["search"], "recall": out["recall"]}, "uncovered": out["uncovered"],
            "held": {"questions": len(out["held"]), "listed": sum(1 for h in out["held"] if h["rank"]),
                     "row_bytes": sum(h["row"] for h in out["held"]),
                     "episode_bytes": sum(h["episodes"] for h in out["held"]), "per_question": out["held"]}}


def buried(rows):
    """Questions whose first expected page is below BURIED_BELOW or absent, with the page that came first."""
    return [(r["id"], r["rank"], r["top"][0] if r["top"] else None) for r in rows
            if r["rank"] is None or r["rank"] > BURIED_BELOW]


def answers(vault, questions, given):
    rows = []
    for q in questions:
        if "held" in q:
            continue
        text = given.get(q["id"])
        if text is None:
            rows.append({"id": q["id"], "answered": False})
            continue
        cited = {vault.resolve(t).stem if vault.resolve(t) else t.strip().lower() for t in LINK.findall(text)}
        if q.get("covered", True) is False:
            rows.append({"id": q["id"], "answered": True, "covered": False,
                         "pass": bool(NOT_COVERED.search(text)) and not cited, "cited": sorted(cited)})
            continue
        expect, allowed = set(q["expect"]), set(q["expect"]) | set(q.get("acceptable", []))
        rows.append({"id": q["id"], "answered": True, "covered": True,
                     "recall": round(len(cited & expect) / len(expect), 3),
                     "precision": round(len(cited & allowed) / len(cited), 3) if cited else 0.0,
                     "missing": sorted(expect - cited), "extra": sorted(cited - allowed)})
    done = [r for r in rows if r["answered"]]
    covered = [r for r in done if r["covered"]]
    uncovered = [r for r in done if not r["covered"]]
    return {"answered": len(done), "of": len(rows),
            "citation_recall": round(sum(r["recall"] for r in covered) / len(covered), 3) if covered else None,
            "citation_precision": round(sum(r["precision"] for r in covered) / len(covered), 3) if covered else None,
            "uncovered_passed": f"{sum(r['pass'] for r in uncovered)}/{len(uncovered)}",
            "per_question": rows}


def arguments(ap):
    ap.add_argument("--root", help="the brain to test: the engine's fixture, or with --from-log the brain you are in")
    ap.add_argument("--from-log", action="store_true", help="the questions are the brain's own log, replayed")
    ap.add_argument("--questions", default=QUESTIONS)
    ap.add_argument("--answers")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--baseline")
    ap.add_argument("--draft", type=int, metavar="N")
    ap.add_argument("--set", action="append", dest="tried", metavar="NAME=VALUE", default=[],
                    help="run with a threshold at another value; nothing is written")


def baseline_of(args, brain=None):
    """Where the baseline is kept: the engine's set keeps the engine's; any other keeps its own beside it.

    A replay of the log (`brain`: whose log it is) keeps its baseline in that brain's motor/.
    """
    if args.baseline:
        return args.baseline
    if brain:
        return os.path.join(brain, FROM_LOG_BASELINE)
    own = os.path.realpath(args.questions) != os.path.realpath(QUESTIONS)
    return os.path.splitext(args.questions)[0] + "-baseline.json" if own else BASELINE


def tested(args):
    """The brain a run tests: --root; without it the engine's fixture, or for --from-log the brain `brain` is run in."""
    if args.from_log and (args.draft is not None or args.answers or args.questions != QUESTIONS):
        raise Refused("brain eval --from-log: the questions are the log's own; it takes no --questions, "
                      "--answers or --draft")
    return args.root or (brain_root() if args.from_log else FIXTURE)


@contextlib.contextmanager
def cache_off():
    """Search without the cache inside this block, and leave BRAIN_CACHE as it was found."""
    was = os.environ.get("BRAIN_CACHE")
    os.environ["BRAIN_CACHE"] = "0"
    try:
        yield
    finally:
        del os.environ["BRAIN_CACHE"]
        if was is not None:
            os.environ["BRAIN_CACHE"] = was


def tried(args):
    """{name: value} for every --set; Refused for a name that is no threshold or a value outside its range."""
    trial = {}
    for item in args.tried:
        try:
            name, value = setting(item)
        except ValueError as why:
            raise Refused(f"brain eval --set: {why}") from None
        trial[name] = value
    if trial and args.save_baseline:
        raise Refused("brain eval: --set tries a value, and a baseline holds the numbers of the brain's own "
                      "thresholds; leave one of the two out")
    return trial


def run(root, args):
    """`root` is not used: the brain tested is --root, the engine's fixture unless another is given."""
    trial = tried(args)
    brain = tested(args)
    if args.from_log:
        spec = {}
    else:
        spec = load(args.questions) if os.path.exists(args.questions) or not args.draft else {"questions": []}
    fixture = os.path.realpath(brain) == os.path.realpath(FIXTURE)
    # The engine never writes into its own folder, and a value being tried leaves nothing behind.
    with cache_off() if fixture or trial else contextlib.nullcontext():
        vault = Vault(brain, today=parse_date(spec.get("today", "")) or None, tuning=trial)
        if args.draft is not None:
            return {"questions": draft(vault, spec["questions"], args.draft)}
        if args.from_log:
            asked, gone = log_cases(vault)
            problems = [f"not replayed, it names only pages that are not here: {line}" for line in gone]
        else:
            asked = [q for q in spec["questions"] if q.get("question", "").strip()]
            problems = question_problems(vault, asked)
        result = {"retrieval": dict(retrieval(vault, asked, args.k), brain=brain_hash(brain)), "problems": problems}
        if args.answers:
            result["answers"] = answers(vault, asked, load(args.answers))
    where = baseline_of(args, brain if args.from_log else None)
    if args.from_log:
        result["from_log"] = {"log_lines": len(vault.events), "limits": list(LIMITS), "baseline": where,
                              "questions": [{"id": q["id"], "date": q["date"], "question": q["question"],
                                             "expect": q.get("expect", [])} for q in asked]}
    if trial:
        own = tuning_of(brain)
        result["set"] = {name: {"value": plain(value), "was": plain(getattr(own, name))}
                         for name, value in trial.items()}
    if args.save_baseline:
        r = result["retrieval"]
        os.makedirs(os.path.dirname(where), exist_ok=True)
        with open(where, "w", encoding="utf-8") as fh:
            json.dump({"k": r["k"], "brain": r["brain"], "search": r["search"], "recall": r["recall"],
                       "sets": r["sets"], "held": {k: v for k, v in r["held"].items() if k != "per_question"}},
                      fh, indent=2)
            fh.write("\n")
    return result


def score_lines(k, sets, was_sets, indent):
    """One line for search and one for recall: the scores of a set, with the baseline's beside them."""
    rows = []
    for mode in ("search", "recall"):
        s, b = sets[mode], (was_sets or {}).get(mode)
        was = f"   (baseline hit {b['hit_at_k']}, mrr {b['mrr']})" if b else ""
        rows.append(f"{indent}{mode:<7} hit@1 {s['hit_at_1']:.3f}   hit@{k} {s['hit_at_k']:.3f}   "
                    f"all {s['all_at_k']}/{s['questions']}   mrr {s['mrr']:.3f}{was}")
    return rows


def tried_line(result):
    return ["  tried with " + ", ".join(f"{name} = {shown(x['value'])} (the brain's own: {shown(x['was'])})"
                                        for name, x in result["set"].items()) + "; nothing was written"] \
        if "set" in result else []


def render_from_log(result, args):
    """The replay of the log: its two limits first, then the scores, then the questions that went wrong."""
    r, log = result["retrieval"], result["from_log"]
    asked = {q["id"]: q for q in log["questions"]}
    covered, uncovered = r["recall"]["questions"], r["uncovered"]
    if not asked:
        return (f"recall replayed from the log: no question in it yet ({log['log_lines']} lines; a question is a "
                "recall line that is not a rehearsal)")
    base = load(log["baseline"]) if os.path.exists(log["baseline"]) else None
    out = [f"recall replayed from the log: {covered} questions that named pages, {len(uncovered)} that named none, "
           f"each as the brain was that day, top {r['k']}"]
    out += [f"  limit: {limit}" for limit in log["limits"]] + tried_line(result)
    if base and (base["brain"], base["recall"]["questions"]) != (r["brain"], covered):
        out.append(f"  the pages or the log changed since the baseline was saved ({base['recall']['questions']} "
                   f"questions then, {covered} now): its numbers are not comparable")
    out += [f"  {problem}" for problem in result["problems"]]
    out += score_lines(r["k"], r, base, "  ")

    def some(rows, said):
        return [said(row) for row in rows[:SHOWN]] + (
            [f"    and {len(rows) - SHOWN} more (--json lists them)"] if len(rows) > SHOWN else [])

    missed = [row for row in r["per_question"]["recall"] if row["missed"]]
    if missed:
        out.append(f"  recall missed a page of {len(missed)} of {covered}:")
        out += some(missed, lambda row: f"    {asked[row['id']]['date']} {asked[row['id']]['question']} -> "
                                        f"{', '.join(row['missed'])}; {row['top'][0] if row['top'] else 'nothing'} "
                                        "came first")
    listed = [u for u in uncovered if u["recall_results"]]
    if uncovered:
        out.append(f"  uncovered questions recall still lists pages for: {len(listed)} of {len(uncovered)}")
        out += some(listed, lambda u: f"    {asked[u['id']]['date']} {asked[u['id']]['question']} "
                                      f"({u['recall_results']} pages)")
    if args.save_baseline:
        out.append(f"baseline saved to {log['baseline']}")
    return "\n".join(out)


def render(result, args):
    """The report, with the saved baseline beside each number; the questions to write, for --draft, as JSON."""
    if args.draft is not None:
        return json.dumps(result, indent=2)
    if "from_log" in result:
        return render_from_log(result, args)
    r = result["retrieval"]
    base = load(baseline_of(args)) if os.path.exists(baseline_of(args)) else None
    covered = r['recall']['questions'] or sum(sets['recall']['questions'] for sets in r['sets'].values())
    out = [f"retrieval over {covered} covered questions, top {r['k']}"] + tried_line(result)
    if base and base.get("brain") not in (None, r["brain"]):
        out.append(f"  the brain's pages changed since the baseline was saved ({base['brain']} then, {r['brain']} now): "
                   "its numbers are not comparable")

    def lines(sets, was_sets, indent):
        return score_lines(r["k"], sets, was_sets, indent)

    out += [f"  question {problem}" for problem in result["problems"]]
    if r["recall"]["questions"]:  # the standard set; a set kept for one's own brain may hold none
        out += lines(r, base, "  ")
        s, n = r["recall"], r["recall"]["questions"] or 1
        was = f"   (baseline {base['recall']['bytes_read']})" if base and "bytes_read" in base.get("recall", {}) else ""
        out.append(f"  recall  rows returned {s['rows']}, {s['rows'] / n:.1f} a question")
        out.append(f"  recall  bytes read {s['bytes_read']}, {s['bytes_read'] // n} a question; "
                   f"the expected pages alone {s['bytes_needed']}{was}")
        out.append("    " + ", ".join(f"{row['id']} {row['bytes']}" for row in r["per_question"]["recall"]
                                      if row["set"] == STANDARD))
        out.append(f"  recall  by summary: {s['bytes_by_summary']} ({s['bytes_listing']} of listing, then the expected pages), "
                   f"{s['bytes_by_summary'] // n} a question, if every summary leads to the right page"
                   + (f"; {s['unsummarised']} returned pages had no summary" if s["unsummarised"] else ""))
    for name, sets in r["sets"].items():
        if name != STANDARD:
            out.append(f"set {name}: {sets['recall']['questions']} questions")
            out += lines(sets, (base or {}).get("sets", {}).get(name), "  ")
    out += [f"  recall missed {row['id']}: {', '.join(row['missed'])}" for row in r["per_question"]["recall"]
            if row["missed"]]
    for mode in ("search", "recall"):
        for qid, rank, first in buried(r["per_question"][mode]):
            where = f"at rank {rank}" if rank else f"not in the top {r['k']}"
            out.append(f"  {mode} buried {qid}: the first expected page is {where}; {first or 'nothing'} came first")
    if r["uncovered"]:
        out.append("  uncovered: " + ", ".join(f"{u['id']} ({u['search_results']} pages matched words, recall lists "
                                                 f"{u['recall_results']})" for u in r["uncovered"]))
        listed = sum(1 for u in r["uncovered"] if u["recall_results"])
        out.append(f"  uncovered questions recall still lists pages for: {listed} of {len(r['uncovered'])}")
    h = r["held"]
    if h["questions"]:
        out.append(f"  held ideas: {h['listed']} of {h['questions']} questions list the idea they name; "
                   f"its line is {h['row_bytes']} bytes, the episodes holding it {h['episode_bytes']}")
    if "answers" in result:
        a = result["answers"]
        out.append(f"answers: {a['answered']}/{a['of']} given; citation recall {a['citation_recall']}, "
                   f"precision {a['citation_precision']}; uncovered said so {a['uncovered_passed']}")
        for row in a["per_question"]:
            if row.get("missing") or row.get("extra") or row.get("pass") is False:
                out.append(f"  {row['id']}: missing {row.get('missing', [])}, extra {row.get('extra', [])}"
                           + ("" if row.get("pass", True) else ", did not say it was not covered"))
    if args.save_baseline:
        out.append(f"baseline saved to {baseline_of(args)}")
    return "\n".join(out)
