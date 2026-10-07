#!/usr/bin/env python3
"""The brain looking at itself: health metrics and the queues sleep works from.

Usage:
    brain introspect [--json] [--queue] [--due] [--decisions] [--open] [--goals] [--projects]
                                  [--dormant] [--stale] [--snapshot] [--remind] [--links]
                                  [--hubs] [--bridges] [--clusters] [--tags] [--graph] [--usage]
                                  [--context]

Default output is the four health metrics (orphan rate, average degree,
components, stale-concept rate) with a verdict on each, plus counts and the
most recalled pages.
  --queue    episodes and reviewed decisions awaiting consolidation, and
             candidate ideas by how many distinct sources name them (two or
             more is the bar for a concept page; episodes sharing a url or an
             input are one source; /explore episodes are listed apart and
             never count toward it; `salient` marks one from a salience 4+
             episode), and new episodes that contradict a page (prediction error)
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
             tunable threshold, for that review
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
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import BRIDGES_SAMPLE, BRIER_MIN, DORMANT_DAYS, RISK_MIN_ATTEMPTS, STALE_DAYS, Vault, verdicts  # noqa: E402

TOP = 10
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


def graph_report(vault):
    """The expensive views, computed only when asked for."""
    inbound = vault.inbound()
    between = vault.betweenness()
    return {
        "hubs": [{"page": p.rel, "inbound": inbound[p]} for p in vault.hubs()],
        "bridges": [{"page": p.rel, "betweenness": round(b, 3)}
                    for p, b in sorted(between.items(), key=lambda kv: -kv[1])[:TOP] if b > 0],
        "bridges_estimated": vault.betweenness_estimated(),
        "cut_points": [p.rel for p in vault.cut_points()],
        "clusters": [{"size": len(c), "core": [p.title for p in c[:3]]} for c in vault.clusters()],
        "schema_candidates": [[p.rel for p in c] for c in vault.schema_candidates()],
        "tags": vault.tag_counts(),
    }


def report(vault, graph=False, links=False):
    pages, edges = vault.knowledge, vault.knowledge_edges()
    components = vault.components()
    concepts, stale = vault.stale_concepts()
    avg_degree = round(2 * len(edges) / len(pages), 2) if pages else 0
    orphan_rate = pct(len(vault.orphans()), len(vault.linked_to()))  # records are never orphans
    main_share = pct(len(components[0]), len(pages)) if components else 0.0
    result = {
        "pages": len(pages),
        "by_type": dict(Counter(p.type for p in pages).most_common()),
        "links": len(edges),
        "avg_degree": avg_degree,
        "orphan_rate": orphan_rate,
        "components": len(components),
        "main_component_share": main_share,
        "verdicts": verdicts(orphan_rate, avg_degree, main_share, len(pages)),
        "stale_concept_rate": pct(len(stale), len(concepts)),
        "broken_links": len(vault.broken),
        "awaiting_consolidation": len(vault.unconsolidated()),
        "due_for_rehearsal": len(vault.due_for_rehearsal()),
        "decisions_due": len(vault.decisions_due()),
        "goals": vault.goal_report(),
        "projects": vault.project_report(),
        "relations": dict(sorted(Counter(rel for _, rel, _ in vault.typed_edges()).items())),
        "calibration": vault.calibration(),
        "usage": vault.usage(),
        "most_recalled": [{"page": p.rel, "recalls": n} for p, n in
                          sorted(vault.recall_count.items(), key=lambda kv: -kv[1])[:10]],
        "stale": [{"page": p.rel, "updated": p.updated.isoformat()} for p in stale],
        "queue": [p.rel for p in vault.unconsolidated()],
        "candidates": [{"name": r["name"], "episodes": len(r["episodes"]), "sources": r["sources"],
                        "generated": len(r["generated"]), "salient": r["salient"],
                        "page": r["page"].rel if r["page"] else None} for r in vault.candidate_tally()],
        "candidate_pairs": [{"a": x["a"], "b": x["b"], "page": x["page"].rel if x["page"] else None,
                             "why": x["why"], "words": x["words"]} for x in vault.candidate_pairs()],
        "contradictions": [{"episode": a.rel, "page": b.rel, "status": b.fields.get("status")}
                           for a, b in vault.contradiction_queue()],
        "due": [p.rel for p in vault.due_for_rehearsal()],
        "risk": {p.rel: {"miss_rate": round(r, 2), "attempts": n}
                 for p in vault.due_for_rehearsal() for r, n in [vault.miss_risk(p)] if n >= RISK_MIN_ATTEMPTS},
        "decisions": {
            "due": [{"page": p.rel, "review": p.fields["review"]} for p in vault.decisions_due()],
            "open": [p.rel for p in vault.of_type("decision") if p.fields.get("status") == "open"],
            "in_force": vault.decision_report(),
            "claim_results": vault.claim_results(),
            "brier": vault.brier(),
            "reference_class": vault.reference_class(),
        },
        "intentions": {"due": [{"text": i["text"], "when": i["when"]} for i in vault.due_intentions()],
                       "waiting": [{"text": i["text"], "when": i["when"]} for i in vault.waiting_intentions()]},
        "dormant": [p.rel for p in vault.dormant_candidates()],
        "open": {k: [p.rel if not isinstance(p, tuple) else f"{p[0].rel} contradicts {p[1].rel}" for p in v]
                 for k, v in vault.open_items().items()},
    }
    if graph:
        result.update(graph_report(vault))
    if links:
        result["links"] = [{"pages": [a.rel, b.rel], "score": s, "why": why}
                           for a, b, s, why in vault.link_suggestions()]
    return result


def brier_line(b):
    """The calibration score with its count; no score until there are enough to mean anything."""
    if not b["n"]:
        return "probabilities: none scored yet (write guesses as [hypothesis 70%], review them held/failed)"
    if not b["enough"]:
        return f"probabilities: {b['n']} scored, too few to judge (needs {BRIER_MIN})"
    buckets = ", ".join(f"{k} said: {v['held']}/{v['n']} held" for k, v in b["buckets"].items())
    return f"probabilities: Brier {b['score']} over {b['n']} (0 perfect, 0.25 = always 50%); {buckets}"


def decision_line(d):
    """One decision in force: its page, what reopens it, and what its reasoning is made of."""
    mix = d["claims"]
    guesses, seen = mix.get("assumption", 0) + mix.get("hypothesis", 0), mix.get("observation", 0)
    return (f"{d['page']}{'  TO REVISIT' if d['triggered'] else ''}\n      revisit if: {d['revisit_if'] or '(none)'}"
            f"\n      claims: {', '.join(f'{t} {n}' for t, n in mix.items()) or 'none tagged'}"
            + ("  (rests mostly on guesses)" if guesses > seen else ""))


def print_list(title, rows):
    print(f"\n{title}: {len(rows)}")
    for row in rows:
        print(f"  {row}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    for flag in ("stale", "queue", "due", "decisions", "open", "goals", "projects", "dormant", "snapshot",
                 "hubs", "bridges", "clusters", "tags", "graph", "usage", "remind", "links", "context"):
        ap.add_argument(f"--{flag}", action="store_true")
    args = ap.parse_args()
    if args.graph:
        args.hubs = args.bridges = args.clusters = args.tags = True

    if not os.path.isdir(args.root):
        sys.exit(f"not a directory: {args.root}")
    vault = Vault(args.root)
    r = report(vault, graph=args.hubs or args.bridges or args.clusters or args.tags, links=args.links)
    if args.context or args.snapshot:
        budget = context_budget(args.root)
        budget["since"] = context_since(args.root, budget, vault.today.isoformat())
        r["session_bytes"] = budget["session_bytes"]
        if args.context:
            r["context"] = budget
    if args.snapshot:
        previous, current, changes = snapshot(args.root, r, vault.today.isoformat())
        r["snapshot"] = {"since": previous[0] if previous else None, "changes": changes}

    if args.json:
        print(json.dumps(r, indent=2))
        return

    print(f"pages           {r['pages']}  " + " ".join(f"{t}:{c}" for t, c in r["by_type"].items()))
    print(f"links           {r['links']}   broken {r['broken_links']}")
    v = r["verdicts"]
    print(f"avg degree      {r['avg_degree']:.2f}   {v.get('avg_degree', '')}")
    print(f"orphan rate     {r['orphan_rate']}%   {v.get('orphan_rate', '(healthy under 5)')}")
    print(f"components      {r['components']}   (main holds {r['main_component_share']}%) {v.get('components', '')}")
    print(f"stale concepts  {r['stale_concept_rate']}%   (untouched {STALE_DAYS}+ days)")
    print(f"to consolidate  {r['awaiting_consolidation']} pages   due to rehearse {r['due_for_rehearsal']}")
    reviewed = sum(r["calibration"].values())
    print(f"decisions       {r['decisions_due']} due for review   {reviewed} reviewed"
          + (" (" + ", ".join(f"{k} {n}" for k, n in r["calibration"].items() if n) + ")" if reviewed else ""))
    if r["most_recalled"]:
        print_list("most recalled", [f"{x['recalls']:>4}  {x['page']}" for x in r["most_recalled"]])
    if args.queue:
        print_list("awaiting consolidation, oldest first", r["queue"])
        print_list("candidates (sources/episodes naming them; + generated by /explore, not evidence)",
                   [f"{c['sources']:>3}/{c['episodes']:<3} {c['name']}"
                    + ("  salient" if c["salient"] else "")
                    + (f"  +{c['generated']} generated" if c["generated"] else "")
                    + (f"  -> {c['page']}" if c["page"] else "") for c in r["candidates"]])
        print_list("possibly one idea twice (read both; a candidate that is the same idea counts as one, with both sources)",
                   [f"{x['a']} ~ {x['page'] or x['b']}  (shared: {', '.join(x['words'])})" for x in r["candidate_pairs"]])
        print_list("prediction errors (new episodes contradicting a page; sleep records both sides)",
                   [f"{x['episode']} contradicts {x['page']}" + (f" ({x['status']})" if x["status"] else "")
                    for x in r["contradictions"]])
    if args.due:
        print_list("due for rehearsal (goals first, then salience, misses, most overdue)",
                   [p + (f"  misses {r['risk'][p]['miss_rate']:.0%} of {r['risk'][p]['attempts']}"
                         if p in r["risk"] else "") for p in r["due"]])
    if args.decisions:
        print_list("decisions due for an outcome review, most overdue first",
                   [f"{x['review']}  {x['page']}" for x in r["decisions"]["due"]])
        print_list("open decisions (not made yet)", r["decisions"]["open"])
        print_list("decisions in force (revisit if ...; claims by tag)", [decision_line(d) for d in r["decisions"]["in_force"]])
        for tag, n in r["decisions"]["claim_results"].items():
            if sum(n.values()):
                print(f"{tag} lines in reviewed decisions: " + ", ".join(f"{k} {v}" for k, v in n.items()))
        print(brier_line(r["decisions"]["brier"]))
        print_list("reference classes (reviewed decisions by tag: outcomes; probabilities)",
                   [f"{tag}: {c['n']} reviewed, " + (", ".join(f"{o} {n}" for o, n in c["outcomes"].items()) or
                                                     "no outcomes") + "; " + brier_line(c["brier"])
                    for tag, c in r["decisions"]["reference_class"].items()])
    if r["goals"] or r["projects"]:
        bare = sum(not g["pages"] for g in r["goals"])
        print(f"purpose         {len(r['goals'])} goals ({bare} with no pages)   "
              f"{sum(p['status'] != 'done' for p in r['projects'])} live projects")
    if args.goals:
        print_list("goals (days left: pages behind it)",
                   [f"{'' if g['days_left'] is None else g['days_left']:>5}  {g['goal']} [{g['state']}]: "
                    f"{len(g['pages'])} pages, {g['activity']} recent"
                    + (f", missing {', '.join(g['missing'])}" if g["missing"] else "")
                    + ("  AT RISK: nothing done toward it lately" if g["at_risk"] else "") for g in r["goals"]])
    if args.remind:
        print_list("reminders due", [f"{i['when']}  {i['text']}" for i in r["intentions"]["due"]])
        print_list("reminders waiting on an event", [f"{i['text']}  (when {i['when']})"
                                                      for i in r["intentions"]["waiting"]])
    if args.links:
        print_list("links that probably belong (sleep proposes; the owner agrees or not)",
                   [f"{x['score']:>6.2f}  {' ~ '.join(x['pages'])}  ({x['why']})" for x in r["links"]])
    if args.projects:
        print_list("projects (status: pages, decisions, feedback files)",
                   [f"{p['project']} ({p['status']}): {len(p['pages'])} pages, {len(p['decisions'])} decisions, "
                    f"{len(p['feedback'])} feedback" for p in r["projects"]])
    if args.open:
        print_list("disputed pages", r["open"]["disputed"])
        print_list("contradictions (typed links)", r["open"]["contradicts"])
        print_list("tagged to-revisit", r["open"]["revisit"])
    if args.dormant:
        print_list(f"dormant candidates (unlinked, unrecalled, {DORMANT_DAYS}+ days)", r["dormant"])
    if args.stale:
        print_list("stale concepts, oldest first", [f"{x['updated']}  {x['page']}" for x in r["stale"]])
    if args.hubs:
        print_list("hubs (inbound >= 5 and 3x average): split candidates",
                   [f"{x['inbound']:>4}  {x['page']}" for x in r["hubs"]])
    if args.bridges:
        print_list("bridges (highest betweenness" + (f", estimated from {BRIDGES_SAMPLE} starting pages"
                                                     if r["bridges_estimated"] else "") + ")",
                   [f"{x['betweenness']:.3f}  {x['page']}" for x in r["bridges"]])
        print_list("cut points (removing one disconnects the graph)", r["cut_points"])
    if args.clusters:
        print_list("clusters (size: core pages)", [f"{c['size']:>4}  {', '.join(c['core'])}" for c in r["clusters"]])
        print_list("schema candidates (4+ concepts no insight frames; sleep proposes one tagged schema)",
                   [", ".join(c) for c in r["schema_candidates"]])
    if args.tags:
        print_list("tags in use", [f"{n:>4}  {t}" for t, n in r["tags"].items()])
    if args.usage:
        u = r["usage"]
        print_list("operations logged", [f"{n:>4}  {op}" for op, n in u["operations"].items()])
        print_list("by month", [f"{m}  " + ", ".join(f"{op} {n}" for op, n in c.items())
                                for m, c in u["by_month"].items()])
        for kind, names in u["unused"].items():
            print(f"never used ({kind}): {', '.join(names) or 'none'}")
        c = u["checkpoint"]
        state = "done" if c["reviewed"] else "due now" if c["reached"] else "not yet"
        print(f"calibration checkpoint: {c['inputs']}/{c['inputs_needed']} inputs, "
              f"{c['sleeps']}/{c['sleeps_needed']} sleeps: {state}")
        print_list("thresholds (vault_model.py; tune at the checkpoint against brain eval)",
                   [f"{k} = {v}" for k, v in u["thresholds"].items()])
    if args.context:
        c = r["context"]
        row = lambda x: f"{x['bytes']:>7} {x['lines']:>6} {x['tokens_est']:>7}  {x['what']}"  # noqa: E731
        print(f"\ncontext budget (tokens are an estimate, bytes over {BYTES_PER_TOKEN}, not a measurement)"
              f"\n  {'bytes':>7} {'lines':>6} {'~tokens':>7}  loads every session")
        for x in c["every_session"]:
            print("  " + row(x))
        print(f"  {c['session_bytes']:>7} {'':>6} {c['session_tokens_est']:>7}  total")
        print(f"  {'bytes':>7} {'lines':>6} {'~tokens':>7}  loads on use")
        for x in c["on_use"]:
            print("  " + row(x))
        since = c["since"]
        if since:
            print(f"  since the snapshot of {since['date']}: every-session bytes "
                  f"{'+' if since['change'] > 0 else ''}{since['change']}"
                  + ("  GROWN: say what was added and whether it has to load every session"
                     if since["change"] > 0 else ""))
        else:
            print("  no earlier snapshot holds this number; `brain introspect --snapshot` records it")
        for w in c["warnings"]:
            print(f"  WARNING: {w}")
        print("  not counted: what the harness loads before the brain; `/context` in Claude Code shows it")
    if args.snapshot:
        snap = r["snapshot"]
        if not snap["since"]:
            print("\nsnapshot recorded: the first one, nothing to compare yet")
        else:
            moved = ", ".join(f"{k} {'+' if d > 0 else ''}{d}" for k, d in snap["changes"].items()) or "nothing moved"
            print(f"\nsnapshot recorded; since {snap['since']}: {moved}")
    if "overall" in v:
        print(f"\nverdict: {v['overall']}")


if __name__ == "__main__":
    main()
