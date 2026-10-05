#!/usr/bin/env python3
"""Build a synthetic brain of any size, to test the engine before there is real content.

Usage:
    brain synth OUT [--pages N] [--seed S] [--days D] [--today YYYY-MM-DD]

OUT must not exist yet. The brain is scaffolded from templates/brain/, then
filled with N pages that pass every contract: about half episodes, the rest
concepts, entities, insights and a few reviewed decisions with stated
probabilities. Links grow by preferential attachment (a page links to
well-linked pages more often), so a few hubs and a long tail form, as in a
real brain. The log holds ingests, sleeps, recall lines that name related
pages together, and rehearsals with passes and misses, spread over D days.
The same seed gives the same brain. Nothing here is anyone's knowledge.
"""
import argparse
import datetime
import os
import random
import shutil
import sys

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORDS = ("memory recall graph signal pattern evidence source habit focus review schedule interval practice "
         "concept model network cluster bridge hub decay salience context project goal outcome forecast "
         "pricing market customer churn latency cache index query search weight learning sleep replay").split()
MIX = (("episode", 0.5), ("concept", 0.22), ("entity", 0.15), ("insight", 0.08), ("decision", 0.05))
FOLDER = {"episode": "episodes", "concept": "concepts", "entity": "entities", "insight": "insights",
          "decision": "decisions"}


def sentence(rng, n=12):
    return " ".join(rng.choice(WORDS) for _ in range(n)).capitalize() + "."


def frontmatter(**fields):
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in fields.items() if v is not None) + "---\n"


def build(out, pages=200, seed=1, days=365, today=None):
    rng = random.Random(seed)
    today = today or datetime.date.today()
    start = today - datetime.timedelta(days=days)
    on = lambda d: (start + datetime.timedelta(days=d)).isoformat()  # noqa: E731
    shutil.copytree(os.path.join(ENGINE, "templates", "brain"), out)

    kinds = [k for k, share in MIX for _ in range(max(1, round(pages * share)))][:pages]
    while len(kinds) < pages:
        kinds.append("episode")
    rng.shuffle(kinds)
    made, degree, links = [], {}, {}
    counts = dict.fromkeys(FOLDER, 0)
    for i, kind in enumerate(kinds):
        counts[kind] += 1
        stem = f"{kind}-{counts[kind]}"
        day = int(i * days / pages)
        targets = set()
        pool = [p for p in made if p[1] != "decision"]
        want = {"episode": rng.randint(1, 3), "concept": rng.randint(2, 4), "entity": 1, "insight": rng.randint(3, 5),
                "decision": rng.randint(1, 3)}[kind]
        if pool:
            weights = [degree[p[0]] + 1 for p in pool]
            for _ in range(want):
                targets.add(rng.choices(pool, weights)[0][0])
        for t in targets:
            degree[t] = degree.get(t, 0) + 1
        degree[stem] = len(targets)
        links[stem] = sorted(targets)
        made.append((stem, kind, day))

    # Sleep links both ways: an episode to the pages it supports, a concept or
    # entity back to the episodes it came from. So most pages get a link back
    # from a later page; one in twenty is left alone, as real orphans are.
    inbound = {t for targets in links.values() for t in targets}
    for stem, kind, day in made:
        if kind == "decision" or stem in inbound or rng.random() < 0.05:
            continue
        want = ("concept", "entity", "insight") if kind == "episode" else ("episode",)
        later = [s for s, k, d in made if k in want and d >= day and s != stem]
        if later:
            links[rng.choice(later)].append(stem)

    for stem, kind, day in made:
        body = [f"# {stem.replace('-', ' ').title()}", "", sentence(rng, 20), sentence(rng, 20), ""]
        body += [f"Linked: " + ", ".join(f"[[{t}]]" for t in links[stem]), ""] if links[stem] else []
        fields = dict(title=stem.replace("-", " ").title(), type=kind, created=on(day), updated=on(day))
        if kind == "episode":
            fields.update(url=f"https://site{rng.randint(1, max(2, pages // 10))}.example/{stem}",
                          consolidated=on(min(days, day + 3)))
            body += ["## Candidates", "", f"- {rng.choice(WORDS).title()} {rng.choice(WORDS)} - {sentence(rng, 6)}", ""]
        elif kind == "concept":
            fields["status"] = rng.choice(("emerging", "established"))
        elif kind == "entity":
            fields["kind"] = rng.choice(("person", "org", "product", "tool"))
        elif kind == "decision":
            p = rng.choice((30, 50, 60, 70, 80, 90))
            held = rng.random() < p / 100
            fields.update(status="reviewed", review=on(min(days, day + 30)), revisit_if='"the market moves"',
                          outcome=rng.choice(("as-expected", "better", "worse", "mixed")),
                          consolidated=on(min(days, day + 31)))
            claim = sentence(rng, 6).rstrip(".")
            body += ["## Options", "", f"- [observation] Seen in [[{links[stem][0]}]]." if links[stem]
                     else "- [assumption] Nothing here yet.", "",
                     "## Expected", "", f"- [hypothesis {p}%] {claim}", "",
                     "## Decision", "", "- [decision] Go ahead.", "",
                     "## Outcome", "", f"- [hypothesis {p}%] {claim} -> {'held' if held else 'failed'}", ""]
        path = os.path.join(out, "cortex", FOLDER[kind], stem + ".md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(frontmatter(**fields) + "\n" + "\n".join(body))

    with open(os.path.join(out, "hippocampus", "index.md"), "w", encoding="utf-8") as fh:
        fh.write(frontmatter(title="Index", type="index", updated=today.isoformat()) + "\n# Index\n\n")
        for kind, folder in FOLDER.items():
            fh.write(f"## {folder.title()}\n\n" + "".join(f"- [[{s}]]\n" for s, k, _ in made if k == kind) + "\n")
        fh.write("## Gaps\n\n_Nothing yet._\n")

    known = [s for s, k, _ in made if k in ("concept", "insight", "entity")]
    rehearsed = [s for s, k, _ in made if k in ("concept", "insight")]
    lines = []
    for stem, kind, day in made:
        if kind == "episode":
            lines.append((day, f"ingest senses/{stem}.md -> 1 episode, 1 candidate, {len(links[stem])} links"))
    for week in range(0, days, 7):
        lines.append((week, f"sleep {rng.randint(1, 8)} episodes -> {rng.randint(0, 3)} concepts"))
    for _ in range(pages):
        day = rng.randrange(days)
        open_ = [s for s, _, d in made if d <= day and s in known]
        if len(open_) >= 2:
            first = rng.choice(open_)
            near = [t for t in links[first] if t in known] or [rng.choice(open_)]
            named = sorted({first, rng.choice(near)})
            lines.append((day, f"recall {' '.join(rng.choice(WORDS) for _ in range(3))} -> "
                               + ", ".join(f"[[{s}]]" for s in named)))
    for _ in range(pages // 2):
        day = rng.randrange(days)
        open_ = [s for s, _, d in made if d <= day and s in rehearsed]
        if open_:
            page = rng.choice(open_)
            lines.append((day, f"recall rehearse -> [[{page}]]" if rng.random() < 0.75
                          else f"rehearse missed -> [[{page}]]"))
    with open(os.path.join(out, "hippocampus", "log.md"), "a", encoding="utf-8") as fh:
        for day, text in sorted(lines, key=lambda t: t[0]):
            fh.write(f"{on(day)} {text}\n")
    return {"pages": pages, "links": sum(len(v) for v in links.values()), "log_lines": len(lines)}


def main():
    ap = argparse.ArgumentParser(prog="brain synth")
    ap.add_argument("out")
    ap.add_argument("--pages", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--today")
    args = ap.parse_args()
    if os.path.exists(args.out):
        sys.exit(f"already exists: {args.out} (synth writes only a new folder)")
    today = datetime.date.fromisoformat(args.today) if args.today else None
    made = build(args.out, args.pages, args.seed, args.days, today)
    print(f"synthetic brain: {made['pages']} pages, {made['links']} links, {made['log_lines']} log lines -> {args.out}")


if __name__ == "__main__":
    main()
