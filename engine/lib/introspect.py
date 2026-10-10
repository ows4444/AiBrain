"""The brain looking at itself: health metrics and the queues sleep works from.

Usage:
    brain introspect [--json] [--queue] [--due] [--decisions] [--open] [--goals] [--projects]
                                  [--dormant] [--stale] [--snapshot] [--remind] [--links]
                                  [--hubs] [--bridges] [--clusters] [--tags] [--graph] [--usage]
                                  [--gaps] [--context]

Default output is the four health metrics (orphan rate, average degree,
components, stale-concept rate) with a verdict on each, plus counts and the
most recalled pages. Only what is asked for is computed: that summary, and
each flag's own views. `--json` with no flag gives the whole report, apart
from the graph views and the link suggestions, which cost more; with flags it
gives the summary and those flags' views. `links` is always the number of
links; `--links` adds `link_suggestions`. `tuning` is the thresholds this
brain overrides (hippocampus/tuning.md), {} for most: the numbers named below
are the defaults, and the text prints the brain's own.
  --queue    episodes and reviewed decisions awaiting consolidation, and
             candidate ideas by how many distinct sources name them (two or
             more is the bar for a concept page; episodes sharing a url or an
             input are one source; /explore episodes are listed apart and
             never count toward it; `salient` marks one from a salience 4+
             episode), and new episodes that contradict a page (prediction
             error); and how encoding is doing: links an episode makes on
             average, and how many held ideas two sources or more name
  --due      concept and insight pages due for rehearsal on the spaced-retrieval
             schedule: pages the owner's goals depend on first, then the more
             salient, then those most often missed (shown from 3 rehearsals)
  --decisions  decisions due for an outcome review, open decisions, how
             reviewed ones turned out against what was expected, and for each
             decision in force: its `revisit_if` line, its claims by tag (a
             decision resting mostly on guesses is marked), and across reviews
             how many assumptions and hypotheses held; the Brier score of the
             owner's stated probabilities, and the reference class by tag
  --goals    the owner's goals (OWNER.md > Goals): state (open,
             past-due, stale, done, dropped), days left, the pages behind
             each, goals with nothing behind them, and goals at risk (due
             within 30 days with nothing edited or recalled in 28)
  --remind   intentions (hippocampus/intentions.md) whose date has come, and
             those waiting on an event
  --links    pairs of pages not linked that probably should be: shared
             neighbours (Adamic-Adar) and pages recalled together
  --projects each project in prefrontal/: status, goal, the pages it uses,
             the decisions that name it and what is in its feedback/
  --snapshot append today's metrics to hippocampus/metrics.md as one line of
             data and print the change since the previous snapshot; the only
             flag that writes, and at most once a day
  --open     what is unresolved: pages tagged disputed or to-revisit, and
             every (contradicts:: [[...]]) link
  --dormant  pages sleep would propose moving to dormant/: unlinked, never
             recalled and untouched for 180 days, unless salient or hand-written
  --stale    concept pages untouched for 90+ days, oldest first
  --hubs     pages with outsized inbound degree: candidates for a split
  --bridges  pages holding clusters together: highest betweenness, and
             cut points whose removal disconnects the graph
  --clusters what the brain is actually about, by label propagation, and
             clusters of 4+ concepts no insight frames yet (schema candidates)
  --tags     every tag in use with its count
  --graph    all four graph views (betweenness is O(pages x links), so above
             500 pages it is estimated from 200 starting pages, and says so)
  --usage    what is actually used: log operations by count and by month,
             the operations, typed-link relations and tags never used, and
             progress to the calibration checkpoint (20 inputs, 4 sleeps):
             the evidence for deciding which features stay; and every
             threshold with its range, what it does and this brain's value
             (its default too, where the brain overrides it), for that review
  --gaps     what was asked and not answered: the recall lines that named no
             page, most asked first. Questions that share a rare word (one
             under 5% of the pages hold) are one gap, known by the words they
             all share; a later question that did name pages and holds those
             words closes it. With each: the ideas held on an episode and the
             pages listed under the index's Gaps that it names, which is where
             to start reading. From the log only
  --context  the context budget: the size of what loads every session (the
             root CLAUDE.md, the description of each skill and agent the
             model can see, the wake-up briefing) and of what loads on use
             (each skill and agent body), in bytes, lines and estimated
             tokens (bytes over 2.7, the ratio Claude Code's `/context`
             showed for this kind of text on 2026-10-07: an estimate, not
             a measurement); growth since the last snapshot; a
             warning when CLAUDE.md passes 200 lines. What the harness loads
             before the brain (other plugins, connectors) is not visible
             here: `/context` in Claude Code shows it
"""
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import TUNING_PATH, Tuning, Vault, shown, verdicts  # noqa: E402

TOP = 10
GAP_QUESTIONS = 3  # wordings of one gap printed; --json has them all
METRICS = os.path.join("hippocampus", "metrics.md")
SNAPSHOT_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\{.*\})$")
SNAPSHOT_KEYS = ("pages", "links", "avg_degree", "orphan_rate", "components", "main_component_share",
                 "stale_concept_rate", "awaiting_consolidation", "due_for_rehearsal", "decisions_due",
                 "session_bytes")
ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_FILE_LINES = 200  # past this the root CLAUDE.md is followed less well (Anthropic's guidance, as the source cites it)
# What `/context` reported on 2026-10-07 against the bytes on disk: the root file 6,854 bytes as 2,600
# tokens, the skill listing 4,189 as about 1,440, the agent listing 1,167 as 465. Markdown with paths and
# backticks runs denser than plain prose (about 4). Recheck against `/context` when the model changes.
BYTES_PER_TOKEN = 2.7


def snapshots(root):
    """[(date, metrics)] already recorded in metrics.md, oldest first."""
    path = os.path.join(root, METRICS)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for m in filter(None, (SNAPSHOT_LINE.match(line.strip()) for line in fh)):
            try:
                out.append((m.group(1), json.loads(m.group(2))))
            except ValueError:
                continue  # a damaged line is not a snapshot; it must not stop the next one
    return out


def snapshot(root, r, today):
    """Append today's metrics (once a day) and return (previous, current, changes)."""
    history = snapshots(root)
    current = {k: r[k] for k in SNAPSHOT_KEYS if k in r}
    previous = history[-1] if history else None
    if not (previous and previous[0] == today):
        path = os.path.join(root, METRICS)
        with open(path, "a+", encoding="utf-8") as fh:
            fh.seek(0)
            existing = fh.read()
            # Start on a fresh line, or the snapshot is glued to the last one and never read back.
            lead = "" if not existing or existing.endswith("\n") else "\n"
            fh.write(f"{lead}{today} {json.dumps(current, sort_keys=True)}\n")
    else:
        previous = history[-2] if len(history) > 1 else None
    changes = {k: round(current[k] - previous[1][k], 2) for k in current
               if previous and k in previous[1] and current[k] != previous[1][k]}
    return previous, current, changes


def tokens_estimate(text):
    """Estimated tokens: the text's bytes over BYTES_PER_TOKEN."""
    return round(len(text.encode("utf-8")) / BYTES_PER_TOKEN)


def measure(what, text):
    return {"what": what, "bytes": len(text.encode("utf-8")), "lines": len(text.splitlines()),
            "tokens_est": tokens_estimate(text)}


def definition(path):
    """(fields, body) of a skill or agent file; a folded `description: >-` is read as one line."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head, _, body = text[4:].partition("\n---\n") if text.startswith("---\n") else ("", "", text)
    fields, key = {}, None
    for line in head.splitlines():
        m = re.match(r"([\w-]+):\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            fields[key] = "" if value in (">", ">-", "|", "|-") else value
        elif key and line.startswith(" "):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields, body


def wake_up_output(root):
    """What the SessionStart hook prints for this brain today; it only reads."""
    try:
        r = subprocess.run([sys.executable, os.path.join(ENGINE, "hooks", "wake_up.py")], capture_output=True,
                           text=True, timeout=30, cwd=root, env=dict(os.environ, CLAUDE_PROJECT_DIR=root))
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def context_budget(root):
    """What the brain puts in the context: every session, and when a skill or agent is used."""
    path = os.path.join(root, "CLAUDE.md")
    root_file = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            root_file = fh.read()
    listed, on_use, hidden = {"skill": [], "agent": []}, [], []
    for kind, pattern in (("skill", os.path.join("skills", "*", "SKILL.md")), ("agent", os.path.join("agents", "*.md"))):
        for path in sorted(glob.glob(os.path.join(ENGINE, pattern))):
            fields, body = definition(path)
            fallback = os.path.dirname(path) if kind == "skill" else os.path.splitext(path)[0]
            label = fields.get("name") or os.path.basename(fallback)
            on_use.append(measure(f"{kind} {label}", body))
            if fields.get("disable-model-invocation") == "true":
                hidden.append(label)
            else:
                listed[kind].append(f"{label}: {fields.get('description', '')}")
    every = [measure("CLAUDE.md", root_file),
             measure(f"skill descriptions ({len(listed['skill'])} listed, {len(hidden)} hidden)",
                     "\n".join(listed["skill"])),
             measure(f"agent descriptions ({len(listed['agent'])})", "\n".join(listed["agent"])),
             measure("wake-up briefing", wake_up_output(root))]
    warnings = []
    if every[0]["lines"] > ROOT_FILE_LINES:
        warnings.append(f"CLAUDE.md is {every[0]['lines']} lines, past {ROOT_FILE_LINES}: move detail to where it is used")
    return {"every_session": every, "session_bytes": sum(x["bytes"] for x in every),
            "session_tokens_est": sum(x["tokens_est"] for x in every),
            "on_use": sorted(on_use, key=lambda x: (-x["bytes"], x["what"])), "hidden_skills": hidden,
            "warnings": warnings}


def context_since(root, budget, today):
    """Growth against the last snapshot that recorded session_bytes, not counting today's."""
    for date, metrics in reversed(snapshots(root)):
        if date != today and "session_bytes" in metrics:
            return {"date": date, "session_bytes": metrics["session_bytes"],
                    "change": budget["session_bytes"] - metrics["session_bytes"]}
    return None


def pct(part, whole):
    return round(100 * part / whole, 1) if whole else 0.0


def _risk(r):
    return {p.rel: {"miss_rate": round(risk, 2), "attempts": n}
            for p in r["_due"] for risk, n in [r.vault.miss_risk(p)] if n >= r.vault.tuning.risk_min_attempts}


def _encoding(r):
    """How encoding is doing: what an episode links on average, and how many held ideas a second source has named."""
    vault = r.vault
    episodes = [p for p in vault.of_type("episode") if not p.generated]
    links = sum(not q.is_system for p in episodes for q in vault.links_from(p))
    held = [c for c in r["candidates"] if not c["page"] and c["episodes"]]
    return {"episodes": len(episodes), "links_per_episode": round(links / len(episodes), 1) if episodes else 0.0,
            "held": len(held), "held_by_two_sources": sum(c["sources"] >= 2 for c in held)}


def _decisions(r):
    vault = r.vault
    return {"due": [{"page": p.rel, "review": p.fields["review"]} for p in r["_decisions_due"]],
            "open": [p.rel for p in vault.of_type("decision") if p.fields.get("status") == "open"],
            "in_force": vault.decision_report(),
            "claim_results": vault.claim_results(),
            "brier": vault.brier(),
            "reference_class": vault.reference_class()}


def _bridges(r):
    between = r.vault.betweenness()
    return [{"page": p.rel, "betweenness": round(b, 3)}
            for p, b in sorted(between.items(), key=lambda kv: -kv[1])[:TOP] if b > 0]


def _hubs(r):
    inbound = r.vault.inbound()
    return [{"page": p.rel, "inbound": inbound[p]} for p in r.vault.hubs()]


# Every view of the report, by name. A view is computed when it is first asked for and kept
# (Report), and may ask for others. A name that starts with `_` is a part several views
# share: computed once, never printed.
VIEWS = {
    "_components": lambda r: r.vault.components(),
    "_stale": lambda r: r.vault.stale_concepts(),  # (every concept, the stale ones)
    "_queue": lambda r: r.vault.unconsolidated(),
    "_due": lambda r: r.vault.due_for_rehearsal(),
    "_decisions_due": lambda r: r.vault.decisions_due(),
    "pages": lambda r: len(r.vault.knowledge),
    "by_type": lambda r: dict(Counter(p.type for p in r.vault.knowledge).most_common()),
    "links": lambda r: len(r.vault.knowledge_edges()),
    "avg_degree": lambda r: round(2 * r["links"] / r["pages"], 2) if r["pages"] else 0,
    "orphan_rate": lambda r: pct(len(r.vault.orphans()), len(r.vault.linked_to())),  # records are never orphans
    "components": lambda r: len(r["_components"]),
    "main_component_share": lambda r: pct(len(r["_components"][0]), r["pages"]) if r["_components"] else 0.0,
    "verdicts": lambda r: verdicts(r["orphan_rate"], r["avg_degree"], r["main_component_share"], r["pages"],
                                   r.vault.tuning),
    "tuning": lambda r: r.vault.tuning.changed(),
    "stale_concept_rate": lambda r: pct(len(r["_stale"][1]), len(r["_stale"][0])),
    "broken_links": lambda r: len(r.vault.broken),
    "awaiting_consolidation": lambda r: len(r["_queue"]),
    "due_for_rehearsal": lambda r: len(r["_due"]),
    "decisions_due": lambda r: len(r["_decisions_due"]),
    "goals": lambda r: r.vault.goal_report(),
    "projects": lambda r: r.vault.project_report(),
    "relations": lambda r: dict(sorted(Counter(rel for _, rel, _ in r.vault.typed_edges()).items())),
    "calibration": lambda r: r.vault.calibration(),
    "usage": lambda r: r.vault.usage(),
    "most_recalled": lambda r: [{"page": p.rel, "recalls": n} for p, n in
                                sorted(r.vault.recall_count.items(), key=lambda kv: -kv[1])[:10]],
    "stale": lambda r: [{"page": p.rel, "updated": p.updated.isoformat()} for p in r["_stale"][1]],
    "queue": lambda r: [p.rel for p in r["_queue"]],
    "candidates": lambda r: [{"name": c["name"], "episodes": len(c["episodes"]), "sources": c["sources"],
                              "generated": len(c["generated"]), "salient": c["salient"],
                              "page": c["page"].rel if c["page"] else None} for c in r.vault.candidate_tally()],
    "candidate_pairs": lambda r: [{"a": x["a"], "b": x["b"], "page": x["page"].rel if x["page"] else None,
                                   "why": x["why"], "words": x["words"]} for x in r.vault.candidate_pairs()],
    "contradictions": lambda r: [{"episode": a.rel, "page": b.rel, "status": b.fields.get("status")}
                                 for a, b in r.vault.contradiction_queue()],
    "encoding": _encoding,
    "due": lambda r: [p.rel for p in r["_due"]],
    "risk": _risk,
    "decisions": _decisions,
    "intentions": lambda r: {"due": [{"text": i["text"], "when": i["when"]} for i in r.vault.due_intentions()],
                             "waiting": [{"text": i["text"], "when": i["when"]}
                                         for i in r.vault.waiting_intentions()]},
    "dormant": lambda r: [p.rel for p in r.vault.dormant_candidates()],
    "open": lambda r: {k: [p.rel if not isinstance(p, tuple) else f"{p[0].rel} contradicts {p[1].rel}" for p in v]
                       for k, v in r.vault.open_items().items()},
    "gaps": lambda r: r.vault.unanswered(),
    # The graph views cost more (betweenness is pages x links), so they come only when asked for.
    "hubs": _hubs,
    "bridges": _bridges,
    "bridges_estimated": lambda r: r.vault.betweenness_estimated(),
    "cut_points": lambda r: [p.rel for p in r.vault.cut_points()],
    "clusters": lambda r: [{"size": len(c), "core": [p.title for p in c[:3]]} for c in r.vault.clusters()],
    "schema_candidates": lambda r: [[p.rel for p in c] for c in r.vault.schema_candidates()],
    "tags": lambda r: r.vault.tag_counts(),
    "link_suggestions": lambda r: [{"pages": [a.rel, b.rel], "score": s, "why": why}
                                   for a, b, s, why in r.vault.link_suggestions()],
}
# What the default output prints, and so what every run computes.
SUMMARY = ("pages", "by_type", "links", "avg_degree", "orphan_rate", "components", "main_component_share", "verdicts",
           "stale_concept_rate", "broken_links", "awaiting_consolidation", "due_for_rehearsal", "decisions_due",
           "goals", "projects", "calibration", "most_recalled", "tuning")
# What each flag adds to the summary. --goals and --projects print views the summary already holds.
FLAG_VIEWS = {
    "queue": ("queue", "candidates", "candidate_pairs", "contradictions", "encoding"),
    "due": ("due", "risk"),
    "decisions": ("decisions",),
    "open": ("open",),
    "goals": (),
    "projects": (),
    "dormant": ("dormant",),
    "stale": ("stale",),
    "remind": ("intentions",),
    "links": ("link_suggestions",),
    "hubs": ("hubs",),
    "bridges": ("bridges", "bridges_estimated", "cut_points"),
    "clusters": ("clusters", "schema_candidates"),
    "tags": ("tags",),
    "usage": ("usage",),
    "gaps": ("gaps",),
}
# `--json` with no flag: the whole report, apart from the graph views and the link suggestions.
EVERYTHING = ("pages", "by_type", "links", "avg_degree", "orphan_rate", "components", "main_component_share",
              "verdicts", "stale_concept_rate", "broken_links", "awaiting_consolidation", "due_for_rehearsal",
              "decisions_due", "goals", "projects", "relations", "calibration", "usage", "most_recalled", "stale",
              "queue", "candidates", "candidate_pairs", "contradictions", "encoding", "due", "risk", "decisions",
              "intentions", "dormant", "open", "gaps", "tuning")
ORDER = EVERYTHING + ("hubs", "bridges", "bridges_estimated", "cut_points", "clusters", "schema_candidates", "tags",
                      "link_suggestions")
GRAPH = ("hubs", "bridges", "clusters", "tags")  # the flags `--graph` stands for


class Report:
    """The report, a view at a time: each view is computed when first asked for, and kept."""

    def __init__(self, vault):
        self.vault = vault
        self.kept = {}

    def __getitem__(self, name):
        if name not in self.kept:
            self.kept[name] = VIEWS[name](self)
        return self.kept[name]

    def only(self, names):
        """{name: view} for these views, in the report's own order."""
        return {name: self[name] for name in ORDER if name in names}


def report(vault, flags=(), everything=False):
    """The views a run needs: the summary and what each flag adds, or `everything` (`--json` with no flag)."""
    names = set(EVERYTHING) if everything else set(SUMMARY).union(*(FLAG_VIEWS[flag] for flag in flags))
    return Report(vault).only(names)


def brier_line(b, needed):
    """The calibration score with its count; no score until there are enough (`needed`) to mean anything."""
    if not b["n"]:
        return "probabilities: none scored yet (write guesses as [hypothesis 70%], review them held/failed)"
    if not b["enough"]:
        return f"probabilities: {b['n']} scored, too few to judge (needs {needed})"
    buckets = ", ".join(f"{k} said: {v['held']}/{v['n']} held" for k, v in b["buckets"].items())
    return f"probabilities: Brier {b['score']} over {b['n']} (0 perfect, 0.25 = always 50%); {buckets}"


def decision_line(d):
    """One decision in force: its page, what reopens it, and what its reasoning is made of."""
    mix = d["claims"]
    guesses, seen = mix.get("assumption", 0) + mix.get("hypothesis", 0), mix.get("observation", 0)
    return (f"{d['page']}{'  TO REVISIT' if d['triggered'] else ''}\n      revisit if: {d['revisit_if'] or '(none)'}"
            f"\n      claims: {', '.join(f'{t} {n}' for t, n in mix.items()) or 'none tagged'}"
            + ("  (rests mostly on guesses)" if guesses > seen else ""))


def gap_line(g):
    """One gap: how often it was asked, the words it is known by, its questions, and where to start reading."""
    shown = g["questions"][:GAP_QUESTIONS]
    more = len(g["questions"]) - len(shown)
    start = ([f"held on an episode: {', '.join(g['held'])}"] if g["held"] else []) + \
            ([f"a gap in the index: {', '.join(f'[[{name}]]' for name in g['index_gaps'])}"] if g["index_gaps"] else [])
    return (f"{g['asked']:>3}x  {', '.join(g['words'])}  (last {g['last']})"
            + "".join(f"\n        {q}" for q in shown)
            + (f"\n        and {more} more (--json has every wording)" if more else "")
            + (f"\n        start with: {'; '.join(start)}" if start else ""))


def listed(title, rows):
    return [f"\n{title}: {len(rows)}"] + [f"  {row}" for row in rows]


def arguments(ap):
    for flag in (*FLAG_VIEWS, "graph", "snapshot", "context"):
        ap.add_argument(f"--{flag}", action="store_true")


def asked(args):
    """The flags a run was given, `--graph` spelled out as the four views it stands for."""
    return [flag for flag in (*FLAG_VIEWS, "snapshot", "context")
            if getattr(args, flag) or (args.graph and flag in GRAPH)]


def run(root, args):
    vault = Vault(root)
    flags = [flag for flag in asked(args) if flag in FLAG_VIEWS]
    r = report(vault, flags, everything=args.json and not flags)
    if args.context or args.snapshot:
        budget = context_budget(root)
        budget["since"] = context_since(root, budget, vault.today.isoformat())
        r["session_bytes"] = budget["session_bytes"]
        if args.context:
            r["context"] = budget
    if args.snapshot:
        previous, current, changes = snapshot(root, r, vault.today.isoformat())
        r["snapshot"] = {"since": previous[0] if previous else None, "changes": changes}
    return r


def threshold_line(name, row):
    """One threshold as tuning.md takes it, then its default where the brain overrides it, its range and what it does."""
    was = f"default {shown(row['default'])}; " if row["value"] != row["default"] else ""
    return f"{name} = {shown(row['value'])}  ({was}{row['low']} to {row['high']}): {row['what']}"


def render(r, args):
    show = asked(args)
    t = Tuning(r["tuning"])  # the text names the brain's own thresholds
    v = r["verdicts"]
    reviewed = sum(r["calibration"].values())
    out = [f"pages           {r['pages']}  " + " ".join(f"{t}:{c}" for t, c in r["by_type"].items()),
           f"links           {r['links']}   broken {r['broken_links']}",
           f"avg degree      {r['avg_degree']:.2f}   {v.get('avg_degree', '')}",
           f"orphan rate     {r['orphan_rate']}%   {v.get('orphan_rate', f'(healthy under {t.orphan_healthy})')}",
           f"components      {r['components']}   (main holds {r['main_component_share']}%) {v.get('components', '')}",
           f"stale concepts  {r['stale_concept_rate']}%   (untouched {t.stale_days}+ days)",
           f"to consolidate  {r['awaiting_consolidation']} pages   due to rehearse {r['due_for_rehearsal']}",
           f"decisions       {r['decisions_due']} due for review   {reviewed} reviewed"
           + (" (" + ", ".join(f"{k} {n}" for k, n in r["calibration"].items() if n) + ")" if reviewed else "")]
    if r["most_recalled"]:
        out += listed("most recalled", [f"{x['recalls']:>4}  {x['page']}" for x in r["most_recalled"]])
    if "queue" in show:
        out += listed("awaiting consolidation, oldest first", r["queue"])
        out += listed("candidates (sources/episodes naming them; + generated by /explore, not evidence)",
                      [f"{c['sources']:>3}/{c['episodes']:<3} {c['name']}"
                       + ("  salient" if c["salient"] else "")
                       + (f"  +{c['generated']} generated" if c["generated"] else "")
                       + (f"  -> {c['page']}" if c["page"] else "") for c in r["candidates"]])
        out += listed("possibly one idea twice (read both; a candidate that is the same idea counts as one, with both sources)",
                      [f"{x['a']} ~ {x['page'] or x['b']}  (shared: {', '.join(x['words'])})" for x in r["candidate_pairs"]])
        out += listed("prediction errors (new episodes contradicting a page; sleep records both sides)",
                      [f"{x['episode']} contradicts {x['page']}" + (f" ({x['status']})" if x["status"] else "")
                       for x in r["contradictions"]])
        e = r["encoding"]
        out.append(f"\nencoding: {e['episodes']} episodes, {e['links_per_episode']} links each; {e['held']} ideas held, "
                   f"{e['held_by_two_sources']} of them named by two sources or more")
    if "due" in show:
        out += listed("due for rehearsal (goals first, then salience, misses, most overdue)",
                      [p + (f"  misses {r['risk'][p]['miss_rate']:.0%} of {r['risk'][p]['attempts']}"
                            if p in r["risk"] else "") for p in r["due"]])
    if "decisions" in show:
        out += listed("decisions due for an outcome review, most overdue first",
                      [f"{x['review']}  {x['page']}" for x in r["decisions"]["due"]])
        out += listed("open decisions (not made yet)", r["decisions"]["open"])
        out += listed("decisions in force (revisit if ...; claims by tag)",
                      [decision_line(d) for d in r["decisions"]["in_force"]])
        for tag, n in r["decisions"]["claim_results"].items():
            if sum(n.values()):
                out.append(f"{tag} lines in reviewed decisions: " + ", ".join(f"{k} {v}" for k, v in n.items()))
        out.append(brier_line(r["decisions"]["brier"], t.brier_min))
        out += listed("reference classes (reviewed decisions by tag: outcomes; probabilities)",
                      [f"{tag}: {c['n']} reviewed, " + (", ".join(f"{o} {n}" for o, n in c["outcomes"].items()) or
                                                        "no outcomes") + "; " + brier_line(c["brier"], t.brier_min)
                       for tag, c in r["decisions"]["reference_class"].items()])
    if r["goals"] or r["projects"]:
        bare = sum(not g["pages"] for g in r["goals"])
        out.append(f"purpose         {len(r['goals'])} goals ({bare} with no pages)   "
                   f"{sum(p['status'] != 'done' for p in r['projects'])} live projects")
    if "goals" in show:
        out += listed("goals (days left: pages behind it)",
                      [f"{'' if g['days_left'] is None else g['days_left']:>5}  {g['goal']} [{g['state']}]: "
                       f"{len(g['pages'])} pages, {g['activity']} recent"
                       + (f", missing {', '.join(g['missing'])}" if g["missing"] else "")
                       + ("  AT RISK: nothing done toward it lately" if g["at_risk"] else "") for g in r["goals"]])
    if "remind" in show:
        out += listed("reminders due", [f"{i['when']}  {i['text']}" for i in r["intentions"]["due"]])
        out += listed("reminders waiting on an event", [f"{i['text']}  (when {i['when']})"
                                                         for i in r["intentions"]["waiting"]])
    if "links" in show:
        out += listed("links that probably belong (sleep proposes; the owner agrees or not)",
                      [f"{x['score']:>6.2f}  {' ~ '.join(x['pages'])}  ({x['why']})" for x in r["link_suggestions"]])
    if "projects" in show:
        out += listed("projects (status: pages, decisions, feedback files)",
                      [f"{p['project']} ({p['status']}): {len(p['pages'])} pages, {len(p['decisions'])} decisions, "
                       f"{len(p['feedback'])} feedback" for p in r["projects"]])
    if "open" in show:
        out += listed("disputed pages", r["open"]["disputed"])
        out += listed("contradictions (typed links)", r["open"]["contradicts"])
        out += listed("tagged to-revisit", r["open"]["revisit"])
    if "dormant" in show:
        out += listed(f"dormant candidates (unlinked, unrecalled, {t.dormant_days}+ days)", r["dormant"])
    if "stale" in show:
        out += listed("stale concepts, oldest first", [f"{x['updated']}  {x['page']}" for x in r["stale"]])
    if "hubs" in show:
        out += listed(f"hubs (inbound >= {t.hub_min} and {t.hub_factor}x average): split candidates",
                      [f"{x['inbound']:>4}  {x['page']}" for x in r["hubs"]])
    if "bridges" in show:
        out += listed("bridges (highest betweenness" + (f", estimated from {t.bridges_sample} starting pages"
                                                        if r["bridges_estimated"] else "") + ")",
                      [f"{x['betweenness']:.3f}  {x['page']}" for x in r["bridges"]])
        out += listed("cut points (removing one disconnects the graph)", r["cut_points"])
    if "clusters" in show:
        out += listed("clusters (size: core pages)", [f"{c['size']:>4}  {', '.join(c['core'])}" for c in r["clusters"]])
        out += listed(f"schema candidates ({t.schema_min}+ concepts no insight frames; sleep proposes one tagged schema)",
                      [", ".join(c) for c in r["schema_candidates"]])
    if "tags" in show:
        out += listed("tags in use", [f"{n:>4}  {t}" for t, n in r["tags"].items()])
    if "gaps" in show:
        out += listed("asked and not answered (recall named no page; most asked first)",
                      [gap_line(g) for g in r["gaps"]])
    if "usage" in show:
        u = r["usage"]
        out += listed("operations logged", [f"{n:>4}  {op}" for op, n in u["operations"].items()])
        out += listed("by month", [f"{m}  " + ", ".join(f"{op} {n}" for op, n in c.items())
                                   for m, c in u["by_month"].items()])
        for kind, names in u["unused"].items():
            out.append(f"never used ({kind}): {', '.join(names) or 'none'}")
        c = u["checkpoint"]
        state = "done" if c["reviewed"] else "due now" if c["reached"] else "not yet"
        out.append(f"calibration checkpoint: {c['inputs']}/{c['inputs_needed']} inputs, "
                   f"{c['sleeps']}/{c['sleeps_needed']} sleeps: {state}")
        out += listed(f"thresholds (a line under `## Overrides` in {TUNING_PATH} changes one, written as below; "
                      "`brain eval --set name=value` measures one first)",
                      [threshold_line(name, row) for name, row in u["thresholds"].items()])
    if "context" in show:
        c = r["context"]
        row = lambda x: f"{x['bytes']:>7} {x['lines']:>6} {x['tokens_est']:>7}  {x['what']}"  # noqa: E731
        out.append(f"\ncontext budget (tokens are an estimate, bytes over {BYTES_PER_TOKEN}, not a measurement)"
                   f"\n  {'bytes':>7} {'lines':>6} {'~tokens':>7}  loads every session")
        out += ["  " + row(x) for x in c["every_session"]]
        out.append(f"  {c['session_bytes']:>7} {'':>6} {c['session_tokens_est']:>7}  total")
        out.append(f"  {'bytes':>7} {'lines':>6} {'~tokens':>7}  loads on use")
        out += ["  " + row(x) for x in c["on_use"]]
        since = c["since"]
        if since:
            out.append(f"  since the snapshot of {since['date']}: every-session bytes "
                       f"{'+' if since['change'] > 0 else ''}{since['change']}"
                       + ("  GROWN: say what was added and whether it has to load every session"
                          if since["change"] > 0 else ""))
        else:
            out.append("  no earlier snapshot holds this number; `brain introspect --snapshot` records it")
        out += [f"  WARNING: {w}" for w in c["warnings"]]
        out.append("  not counted: what the harness loads before the brain; `/context` in Claude Code shows it")
    if "snapshot" in show:
        snap = r["snapshot"]
        if not snap["since"]:
            out.append("\nsnapshot recorded: the first one, nothing to compare yet")
        else:
            moved = ", ".join(f"{k} {'+' if d > 0 else ''}{d}" for k, d in snap["changes"].items()) or "nothing moved"
            out.append(f"\nsnapshot recorded; since {snap['since']}: {moved}")
    if "overall" in v:
        out.append(f"\nverdict: {v['overall']}")
    return "\n".join(out)
