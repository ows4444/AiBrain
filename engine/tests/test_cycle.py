"""The whole memory cycle, end to end, through the real hooks and scripts.

Scaffolds a fresh brain from templates/brain/ in a temporary folder, then
encodes two inputs, consolidates them, recalls, and checks every contract on
the way, running the engine's hooks and instruments in place. Run: brain test
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = "2026-10-03"


def episode(slug, candidates, created):
    return f"""---
title: {slug.upper()}
type: episode
created: {created}
updated: {created}
input: senses/{slug}.md
consolidated:
aliases: []
tags: []
---

# {slug}

## Claims

This input says something about [[obsidian]].

## Candidates

{candidates}
"""


class MemoryCycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "brain")
        shutil.copytree(os.path.join(ENGINE, "templates", "brain"), self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def run_py(self, rel, *args, stdin=None):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.dir, BRAIN_ROOT=self.dir)
        return subprocess.run([sys.executable, os.path.join(ENGINE, rel), *args], input=stdin,
                              capture_output=True, text=True, env=env, cwd=self.dir)

    def write(self, rel, text):
        """Write a page the way Claude does, then run the PostToolUse hook on it."""
        path = os.path.join(self.dir, rel)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.run_py("hooks/validate_page.py", stdin=json.dumps({"tool_input": {"file_path": path}}))

    def edit(self, rel, old, new):
        path = os.path.join(self.dir, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(old, text)
        return self.write(rel, text.replace(old, new))

    def stats(self):
        return json.loads(self.run_py("bin/brain", "introspect", "--json").stdout)

    def briefing(self):
        return self.run_py("hooks/wake_up.py").stdout

    def test_encode_sleep_recall(self):
        # an entity the brain already knows
        r = self.write("cortex/entities/obsidian.md", "---\ntitle: Obsidian\ntype: entity\nkind: product\n"
                       f"created: {TODAY}\nupdated: {TODAY}\n---\nA note app. Mentioned in [[a1]].\n")
        self.assertEqual(r.returncode, 0, r.stderr)

        # input lands in the senses
        for name in ("a1", "a2"):
            with open(os.path.join(self.dir, "senses", f"{name}.md"), "w") as fh:
                fh.write("an article")
        self.assertIn("Unencoded in senses/: 2", self.briefing())

        # encode: one episode each, candidates listed, no concept yet
        for slug, cands, created in (("a1", "- LLM wiki - the pattern\n- Karpathy - its author", "2026-09-01"),
                                     ("a2", "- LLM wiki: the same pattern again", "2026-09-02")):
            r = self.write(f"cortex/episodes/{slug}.md", episode(slug, cands, created))
            self.assertEqual(r.returncode, 0, r.stderr)
        brief = self.briefing()
        self.assertIn("Unencoded in senses/: 0", brief)
        self.assertIn("Awaiting /sleep: 2 episodes", brief)

        s = self.stats()
        self.assertEqual(s["queue"], ["cortex/episodes/a1.md", "cortex/episodes/a2.md"])  # oldest first
        named = {c["name"].lower(): c["episodes"] for c in s["candidates"]}
        self.assertEqual(named, {"llm wiki": 2, "karpathy": 1})  # only one clears the two-episode bar

        # sleep: the hook refuses a concept without status, accepts an established one
        bad = self.write("cortex/concepts/llm-wiki.md", "---\ntitle: LLM wiki\ntype: concept\n"
                         f"created: {TODAY}\nupdated: {TODAY}\n---\nx\n")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("status", bad.stderr)
        r = self.write("cortex/concepts/llm-wiki.md", "---\ntitle: LLM wiki\ntype: concept\nstatus: established\n"
                       f"created: {TODAY}\nupdated: {TODAY}\n---\nAn idea from [[a1]] and [[a2]], kept in "
                       "[[obsidian]].\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        for slug in ("a1", "a2"):
            r = self.edit(f"cortex/episodes/{slug}.md", "consolidated:\n", f"consolidated: {TODAY}\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.edit(f"cortex/episodes/{slug}.md", "about [[obsidian]]", "about [[llm-wiki]] in [[obsidian]]")

        s = self.stats()
        self.assertEqual(s["awaiting_consolidation"], 0)
        self.assertIn("cortex/concepts/llm-wiki.md", [c["page"] for c in s["candidates"]])

        # the index lists every page (written by `brain index`) and the one gap (written by hand);
        # link check still passes, so /commit can run
        listed = self.run_py("bin/brain", "index")
        self.assertEqual(listed.stdout, "index: 4 pages listed; added a1, a2, llm-wiki, obsidian\n")
        self.edit("hippocampus/index.md", "Pages that are linked but do not exist yet.\n\n_Nothing yet._",
                  "Pages that are linked but do not exist yet.\n\n- [[Karpathy]]")
        self.assertEqual(self.run_py("bin/brain", "index").stdout, "index: up to date (4 pages listed)\n")
        check = self.run_py("bin/brain", "check", "--json")
        report = json.loads(check.stdout)
        self.assertEqual((check.returncode, report["broken"], report["schema"], report["not_in_index"]),
                         (0, [], [], []))
        self.assertEqual(report["gaps"], ["Karpathy"])

        # recall leaves a trace that strengthens the page; the line is the command's, never typed into the file
        typed = json.dumps({"tool_name": "Edit", "tool_input": {
            "file_path": "hippocampus/log.md", "new_string": f"{TODAY} recall what is an llm wiki -> [[llm-wiki]]\n"}})
        self.assertEqual(self.run_py("hooks/protect_log.py", stdin=typed).returncode, 2)
        refused = self.run_py("bin/brain", "log", "recall", "what is an llm wiki", "--pages", "llm-wikis")
        self.assertIn("no page named 'llm-wikis' (closest: llm-wiki)", refused.stderr)
        logged = self.run_py("bin/brain", "log", "recall", "what is an llm wiki", "--pages", "LLM wiki", "obsidian")
        self.assertRegex(logged.stdout, r"^logged: \d{4}-\d\d-\d\d recall what is an llm wiki -> "
                                        r"\[\[llm-wiki\]\], \[\[obsidian\]\]\n$")
        s = self.stats()
        self.assertIn({"page": "cortex/concepts/llm-wiki.md", "recalls": 1}, s["most_recalled"])
        self.assertEqual((s["orphan_rate"], s["components"]), (0.0, 1))
        self.assertNotIn("what is an llm wiki", self.briefing())  # the briefing skips recall lines

        # the encoded input stays as it arrived
        for tool, args in (("Edit", {"file_path": "senses/a1.md"}), ("Bash", {"command": "cp x.md senses/a1.md"})):
            r = self.run_py("hooks/protect_senses.py", stdin=json.dumps({"tool_name": tool, "tool_input": args}))
            self.assertEqual(r.returncode, 2, tool)

    def test_explore_decide_review(self):
        # an exploration raises an idea; it waits in the queue but is not evidence
        r = self.write("cortex/episodes/explore-pricing.md", episode("explore-pricing", "- Small bets - try cheap first",
                                                                     "2026-09-01").replace(
            "input: senses/explore-pricing.md\n", "origin: generated\n"))
        self.assertEqual(r.returncode, 0, r.stderr)
        named = {c["name"].lower(): (c["episodes"], c["generated"]) for c in self.stats()["candidates"]}
        self.assertEqual(named["small bets"], (0, 1))

        # a decision: the hook refuses a decided page with no review date
        head = f"---\ntitle: Raise prices\ntype: decision\ncreated: 2026-09-02\nupdated: 2026-09-02\n"
        body = "---\n## Expected\nFew customers leave.\n## Candidates\n- Small bets - a 5% test told us enough\n"
        made = 'status: decided\nreview: 2020-01-01\nrevisit_if: "a rival cuts prices"\n'
        bad = self.write("cortex/decisions/raise-prices.md", head + "status: decided\n" + body)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("review", bad.stderr)
        self.assertIn("revisit_if", bad.stderr)
        bad = self.write("cortex/decisions/raise-prices.md", head + made + body)  # the expectation is not tagged
        self.assertEqual(bad.returncode, 2)
        self.assertIn("untagged lines under ## Expected", bad.stderr)
        body = body.replace("Few customers", "- [hypothesis] Few customers")
        r = self.write("cortex/decisions/raise-prices.md", head + made + body)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("decisions to review: 1 (raise-prices)", self.briefing())
        self.assertEqual(self.stats()["queue"], ["cortex/episodes/explore-pricing.md"])  # not yet evidence

        # review: the outcome is recorded and the decision joins the sleep queue as evidence
        r = self.edit("cortex/decisions/raise-prices.md", "status: decided\n", "status: reviewed\noutcome: better\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.stats()
        self.assertNotIn("decisions to review", self.briefing())
        self.assertEqual(s["queue"], ["cortex/episodes/explore-pricing.md", "cortex/decisions/raise-prices.md"])
        named = {c["name"].lower(): (c["episodes"], c["generated"]) for c in s["candidates"]}
        self.assertEqual(named["small bets"], (1, 1))  # one real source: still below the bar
        self.assertEqual(s["calibration"]["better"], 1)


    def test_months_of_use(self):
        """One brain stepped through 200 days: the instruments agree at every step."""
        import datetime
        sys.path.insert(0, os.path.join(ENGINE, "lib"))
        import vaultlib
        day0 = datetime.date(2026, 1, 5)
        on = lambda n: (day0 + datetime.timedelta(days=n)).isoformat()  # noqa: E731
        brain = lambda n: vaultlib.Vault(self.dir, today=day0 + datetime.timedelta(days=n))  # noqa: E731
        fm = lambda **f: "---\n" + "".join(f"{k}: {v}\n" for k, v in f.items()) + "---\n"  # noqa: E731

        def page(rel, body, **fields):
            r = self.write(rel, fm(**fields) + body)
            self.assertEqual(r.returncode, 0, r.stderr)

        def log(*lines):
            with open(os.path.join(self.dir, "hippocampus", "log.md"), "a") as fh:
                fh.write("".join(line + "\n" for line in lines))

        claude = os.path.join(self.dir, "OWNER.md")
        with open(claude, encoding="utf-8") as fh:
            text = fh.read()
        goal = f"- Learn pricing by {on(60)} -> [[pricing]], [[tangent]]"
        with open(claude, "w", encoding="utf-8") as fh:
            fh.write(re.sub(r"(## Goals\n\n).*", lambda m: m.group(1) + goal + "\n", text, flags=re.S))

        # week 1: two clips of one article, then a second article
        ep = dict(type="episode", created=on(0), updated=on(0))
        for slug, url in (("a1", "https://x.example/p"), ("a2", "https://x.example/p/"), ("b1", "https://y.example")):
            page(f"cortex/episodes/{slug}.md", "## Candidates\n- Pricing - x\n", title=slug, url=url, **ep)
        row = {r["name"]: r for r in brain(0).candidate_tally()}["Pricing"]
        self.assertEqual((len(row["episodes"]), row["sources"]), (3, 2))  # three episodes, two sources: the bar

        # sleep: the concept, linked both ways; a tangent only the goal links
        page("cortex/concepts/pricing.md", "From [[a1]], [[a2]] and [[b1]].", title="Pricing", type="concept",
             status="established", created=on(0), updated=on(0))
        page("cortex/concepts/tangent.md", "word " * 50, title="Tangent", type="concept", status="emerging",
             created=on(0), updated=on(0), salience="high")
        for slug in ("a1", "a2", "b1"):
            self.edit(f"cortex/episodes/{slug}.md", f"updated: {on(0)}\n", f"updated: {on(0)}\nconsolidated: {on(0)}\n")
        self.assertEqual(brain(0).unconsolidated(), [])

        # a decision on day 3, reviewed on day 30; never an orphan
        page("cortex/decisions/raise.md", "About [[pricing]].\n\n## Expected\n- [assumption] Few leave.\n",
             title="Raise", type="decision", status="decided", review=on(30), revisit_if="a rival cuts prices",
             created=on(3), updated=on(3))
        self.assertEqual([p.stem for p in brain(29).decisions_due()], [])
        self.assertEqual([p.stem for p in brain(30).decisions_due()], ["raise"])
        self.assertEqual([p.stem for p in brain(30).orphans()], ["tangent"])  # records are not orphans

        # spaced rehearsal: day 1 counts, day 2 is cramming, day 5 counts; next interval 7 days.
        # The model reading the page on day 9 to answer a question does not restart that clock.
        log(f"{on(1)} recall rehearse -> [[pricing]]", f"{on(2)} recall rehearse -> [[pricing]]",
            f"{on(5)} recall rehearse -> [[pricing]]", f"{on(9)} recall what is pricing -> [[pricing]]")
        v = brain(11)
        self.assertEqual(v.strength(v.resolve("pricing")), 2)
        self.assertNotIn("pricing", [p.stem for p in v.due_for_rehearsal()])
        self.assertIn("pricing", [p.stem for p in brain(12).due_for_rehearsal()])

        # the goal: protects while past due (day 70), lets go once stale (day 200); fading then follows
        self.edit("cortex/concepts/tangent.md", "salience: high\n", "")
        self.assertEqual(brain(70).goal_report()[0]["state"], "past-due")
        self.assertIn("tangent", [p.stem for p in brain(70).purpose()])
        with open(claude, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(brain(200).goal_report()[0]["state"], "stale")
        self.assertEqual([p.stem for p in brain(200).dormant_candidates()], ["tangent"])
        with open(claude, "w", encoding="utf-8") as fh:
            fh.write(text.replace(f"by {on(60)}", f"by {on(240)}"))  # re-dated: protected again
        self.assertEqual(brain(200).dormant_candidates(), [])

        check = self.run_py("bin/brain", "check", "--json")
        self.assertEqual(check.returncode, 0, check.stdout)


if __name__ == "__main__":
    unittest.main()
