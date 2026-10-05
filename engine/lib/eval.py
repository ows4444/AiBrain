#!/usr/bin/env python3
"""The answer test set: after an engine change, does the brain still find the right pages?

Usage:
    brain eval [--root DIR] [--questions FILE] [--answers FILE] [--k N] [--json]
               [--save-baseline] [--baseline FILE]

Runs on the fixture brain in engine/eval/fixture/ with engine/eval/questions.json
unless --root and --questions point elsewhere (an owner can keep a question
set for their own brain, e.g. in motor/).

Retrieval (default). Each covered question goes through `search` (words only)
and `recall` (words, then association; with the question's `project` if it
names one), and each is scored:
    hit@k   expected pages in the top k, as a share of the pages expected
    all@k   questions with every expected page in the top k
    mrr     1 / rank of the first expected page, averaged (0 if none in the top k)
Uncovered questions are listed with how many pages search returned: a
retriever cannot know a question is uncovered; the answer has to say so.

Answers (--answers FILE, JSON {"q01": "text citing [[page]]", ...}), for
example from running /ask on each question in a copy of the fixture. A
covered answer scores citation recall (expected pages cited) and precision
(cited pages that are expected or acceptable); an uncovered one passes when
it says it is not covered and cites nothing.

--save-baseline writes the retrieval numbers to engine/eval/baseline.json (or
--baseline FILE, which the text report also compares against); the tests fail
when `recall` falls below the saved one. Reads only, apart from that.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import LINK, Vault, parse_date  # noqa: E402

EVAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval")
FIXTURE = os.path.join(EVAL, "fixture")
QUESTIONS = os.path.join(EVAL, "questions.json")
BASELINE = os.path.join(EVAL, "baseline.json")
NOT_COVERED = re.compile(r"not covered|no page|nothing (?:in|here|on|about)|does(?:n't| not) (?:answer|cover)"
                         r"|no (?:pages?|notes?|episodes?) (?:here )?(?:on|about|cover)", re.I)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rank_scores(ranked, expect, k):
    top = ranked[:k]
    found = [e for e in expect if e in top]
    first = next((i for i, stem in enumerate(top, 1) if stem in expect), None)
    return {"hit": len(found) / len(expect), "all": len(found) == len(expect), "rr": 1 / first if first else 0.0,
            "missed": [e for e in expect if e not in top], "top": top}


def summary(rows):
    n = len(rows)
    return {"questions": n, "hit_at_k": round(sum(r["hit"] for r in rows) / n, 3) if n else 0.0,
            "all_at_k": sum(r["all"] for r in rows), "mrr": round(sum(r["rr"] for r in rows) / n, 3) if n else 0.0}


def retrieval(vault, questions, k):
    out = {"search": [], "recall": [], "uncovered": []}
    for q in questions:
        if q.get("covered", True) is False:
            out["uncovered"].append({"id": q["id"], "search_results": len(vault.search(q["question"], limit=k))})
            continue
        searched = [p.stem for p, _ in vault.search(q["question"], limit=k)]
        recalled = [r["page"].stem for r in vault.recall(q["question"], project=q.get("project"), limit=k)]
        out["search"].append(dict(rank_scores(searched, q["expect"], k), id=q["id"]))
        out["recall"].append(dict(rank_scores(recalled, q["expect"], k), id=q["id"]))
    return {"k": k, "search": summary(out["search"]), "recall": summary(out["recall"]),
            "per_question": {"search": out["search"], "recall": out["recall"]}, "uncovered": out["uncovered"]}


def answers(vault, questions, given):
    rows = []
    for q in questions:
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


def main():
    ap = argparse.ArgumentParser(prog="brain eval")
    ap.add_argument("--root", default=FIXTURE)
    ap.add_argument("--questions", default=QUESTIONS)
    ap.add_argument("--answers")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--baseline", default=BASELINE)
    args = ap.parse_args()
    spec = load(args.questions)
    if os.path.realpath(args.root) == os.path.realpath(FIXTURE):
        os.environ["BRAIN_CACHE"] = "0"  # the engine never writes into its own folder
    vault = Vault(args.root, today=parse_date(spec.get("today", "")) or None)
    result = {"retrieval": retrieval(vault, spec["questions"], args.k)}
    if args.answers:
        result["answers"] = answers(vault, spec["questions"], load(args.answers))
    if args.save_baseline:
        r = result["retrieval"]
        with open(args.baseline, "w", encoding="utf-8") as fh:
            json.dump({"k": r["k"], "search": r["search"], "recall": r["recall"]}, fh, indent=2)
            fh.write("\n")
    if args.json:
        print(json.dumps(result, indent=2))
        return
    r = result["retrieval"]
    base = load(args.baseline) if os.path.exists(args.baseline) else None
    print(f"retrieval over {r['recall']['questions']} covered questions, top {r['k']}")
    for mode in ("search", "recall"):
        s = r[mode]
        was = f"   (baseline hit {base[mode]['hit_at_k']}, mrr {base[mode]['mrr']})" if base and mode in base else ""
        print(f"  {mode:<7} hit@{r['k']} {s['hit_at_k']:.3f}   all {s['all_at_k']}/{s['questions']}   "
              f"mrr {s['mrr']:.3f}{was}")
    for row in r["per_question"]["recall"]:
        if row["missed"]:
            print(f"  recall missed {row['id']}: {', '.join(row['missed'])}")
    print("  uncovered: " + ", ".join(f"{u['id']} ({u['search_results']} pages matched words)"
                                      for u in r["uncovered"]))
    if args.answers:
        a = result["answers"]
        print(f"answers: {a['answered']}/{a['of']} given; citation recall {a['citation_recall']}, "
              f"precision {a['citation_precision']}; uncovered said so {a['uncovered_passed']}")
        for row in a["per_question"]:
            if row.get("missing") or row.get("extra") or row.get("pass") is False:
                print(f"  {row['id']}: missing {row.get('missing', [])}, extra {row.get('extra', [])}"
                      + ("" if row.get("pass", True) else ", did not say it was not covered"))
    if args.save_baseline:
        print(f"baseline saved to {args.baseline}")


if __name__ == "__main__":
    main()
