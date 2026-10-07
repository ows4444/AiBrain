"""Memory over time: recall, the sleep queue, decisions, goals ending, sources, snapshots. Run: brain test"""
import datetime
import json
import os
import subprocess
import sys
import unittest

from support import DECIDED, SCRIPTS, TempBrain, VALID, ago, page, vaultlib


class Memory(TempBrain):
    def test_consolidation_queue_and_candidates(self):
        cand = "## Candidates\n- LLM wiki - a pattern\n- [[Karpathy]]\n\n## Links\n- not a candidate\n"
        self.write("cortex/episodes/e1.md", page("episode", cand, created="2026-01-02"))
        self.write("cortex/episodes/e2.md", page("episode", "## Candidates\n* llm wiki: again\n",
                                                 created="2026-01-01", consolidated="2026-01-05"))
        self.write("cortex/entities/karpathy.md", page("entity"))
        v = self.brain()
        self.assertEqual([p.stem for p in v.unconsolidated()], ["e1"])
        tally = {r["name"].lower(): (len(r["episodes"]), r["page"]) for r in v.candidate_tally()}
        self.assertEqual(tally["llm wiki"][0], 2)
        self.assertEqual(tally["karpathy"][1].stem, "karpathy")
        self.assertNotIn("not a candidate", tally)

    def test_candidates_that_may_be_one_idea_are_paired_for_sleep(self):
        self.write("cortex/episodes/e1.md", page("episode", "## Candidates\n- Illusion of fluency - rereading feels "
                                                 "like learning\n- Optimal gap - the best gap between study "
                                                 "sessions depends on the retention interval\n", url="https://a.example"))
        self.write("cortex/episodes/e2.md", page("episode", "## Candidates\n- Fluency illusion - ease is mistaken for "
                                                 "progress\n- Sleep - rest matters\n", url="https://b.example"))
        self.write("cortex/episodes/e3.md", page("episode", "## Candidates\n- Fluent speech - talking smoothly\n",
                                                 url="https://a.example"))
        self.write("cortex/concepts/spacing.md", page("concept", title="Spacing effect", summary="Study spread over "
                                                      "sessions lasts; the best gap depends on how long it must last."))
        v = self.brain()
        self.assertEqual({r["name"]: r["sources"] for r in v.candidate_tally()}["Illusion of fluency"], 1)
        pairs = {(x["a"], x["b"]): x for x in v.candidate_pairs()}
        self.assertEqual(sorted(pairs), [("Fluency illusion", "Illusion of fluency"), ("Optimal gap", "Spacing effect")])
        self.assertEqual(pairs["Fluency illusion", "Illusion of fluency"]["why"], "names")
        self.assertEqual(pairs["Optimal gap", "Spacing effect"]["page"].stem, "spacing")
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "introspect.py"), self.root, "--queue"],
                             capture_output=True, text=True).stdout
        self.assertIn("possibly one idea twice", out)
        self.assertIn("Fluency illusion ~ Illusion of fluency  (shared: fluency, illusion)", out)
        self.assertIn("Optimal gap ~ cortex/concepts/spacing.md", out)

    def test_a_fact_that_goes_out_of_date_needs_a_date_or_a_pointer(self):
        self.write("cortex/episodes/survey.md", page("episode", "The suite has 240 tests.\n"))
        self.write("cortex/entities/tool.md", page("entity", "\n".join([
            "The suite has 240 tests and all pass.", "",
            "It is currently the largest of its kind.", "",
            "It has 14 packages (as of 2026-10-07).", "",
            "The store holds 9 tables, on one\nwrapped line ([[survey]]).", "",
            "- It runs 71 tools; see the README.", "",
            "Spacing means study spread over time.", "",
            "In 1885 one man learned 2 lists."])))
        self.write("cortex/episodes/own.md", page("episode", "It still has 5 open bugs.\n"))
        v = self.brain()
        self.assertEqual([(p.stem, line) for p, line in v.undated_facts()],
                         [("tool", "The suite has 240 tests and all pass."),
                          ("tool", "It is currently the largest of its kind.")])
        run = subprocess.run([sys.executable, os.path.join(SCRIPTS, "link_check.py"), self.root],
                             capture_output=True, text=True)
        self.assertIn("with no date or pointer (/maintain: restamp, point or move): 2", run.stdout)
        self.assertIn("cortex/entities/tool.md: The suite has 240 tests and all pass.", run.stdout)
        # A warning: the check reads words, not meaning. A valid page holding such a line still passes.
        for rel in ("cortex/episodes/survey.md", "cortex/episodes/own.md", "cortex/entities/tool.md"):
            os.remove(os.path.join(self.root, rel))
        self.write("cortex/entities/tool.md", page("entity", "The suite has 240 tests and all pass.\n", title="Tool",
                                                   summary="A tool.", kind="tool", created="2026-01-01",
                                                   updated="2026-01-01"))
        self.write("hippocampus/index.md", page("index", "- [[tool]]\n"))
        run = subprocess.run([sys.executable, os.path.join(SCRIPTS, "link_check.py"), self.root],
                             capture_output=True, text=True)
        self.assertIn("restamp, point or move): 1", run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)

    def test_forgetting_a_source_shows_what_rests_on_it_then_removes_it_whole(self):
        def run(script, *args):
            return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)

        self.write("senses/bad.md", "a bad source")
        self.write("senses/good.md", "a good source")
        self.write("cortex/episodes/bad.md", page("episode", "## Candidates\n- Held idea - only here\n",
                                                  title="Bad", input="senses/bad.md"))
        self.write("cortex/episodes/good.md", page("episode", "x\n", title="Good", input="senses/good.md"))
        self.write("cortex/concepts/idea.md", page("concept", "Seen twice ([[bad]], [[good]]).\n", title="Idea"))
        self.write("cortex/entities/tool.md", page("entity", "Named once ([[bad]]).\n", title="Tool"))
        self.write("hippocampus/index.md", page("index", "- [[bad]] - x\n- [[good]] - y\n- [[idea]]\n- [[tool]]\n"))
        self.log("2026-01-01 ingest senses/bad.md -> 1 episode")
        run("fingerprint.py", self.root)

        shown = run("forget.py", "--root", self.root, "senses/bad.md").stdout
        for fragment in ("would forget: senses/bad.md", "cortex/episodes/bad.md", "go with it: Held idea",
                         "cortex/concepts/idea.md  sources 2 -> 1: falls under the two-source bar: back to a "
                         "candidate on [[good]]", "cortex/entities/tool.md  sources 1 -> 0: no source left",
                         "Seen twice ([[bad]], [[good]]).", "nothing was changed"):
            self.assertIn(fragment, shown)
        self.assertTrue(os.path.exists(os.path.join(self.root, "senses", "bad.md")))  # showing writes nothing
        self.assertEqual(run("forget.py", "--root", self.root, "bad").stdout, shown)   # by episode name too
        self.assertIn("neither a file in senses/ nor an episode", run("forget.py", "--root", self.root, "idea").stderr)

        done = run("forget.py", "--root", self.root, "senses/bad.md", "--yes").stdout
        self.assertIn("forgotten: senses/bad.md", done)
        for gone in ("senses/bad.md", "cortex/episodes/bad.md"):
            self.assertFalse(os.path.exists(os.path.join(self.root, gone)), gone)
        self.assertTrue(os.path.exists(os.path.join(self.root, "senses", "good.md")))
        with open(os.path.join(self.root, "hippocampus", "log.md"), encoding="utf-8") as fh:
            self.assertRegex(fh.read(), r"\d{4}-\d\d-\d\d forget senses/bad.md -> 1 episodes and 1 input files removed "
                                        r"on the owner's yes; 2 pages cited them")
        with open(os.path.join(self.root, "hippocampus", "fingerprints.md"), encoding="utf-8") as fh:
            prints = fh.read()
        self.assertRegex(prints, r"[0-9a-f]{64} senses/bad.md\n")       # that it was once held stays on record
        self.assertRegex(prints, r"\d{4}-\d\d-\d\d forgotten senses/bad.md\n")
        with open(os.path.join(self.root, "hippocampus", "index.md"), encoding="utf-8") as fh:
            index = fh.read()
        self.assertNotIn("[[bad]]", index)
        self.assertIn("[[good]]", index)
        check = json.loads(run("link_check.py", self.root, "--json").stdout)
        self.assertEqual(check["history"], [])  # removed on purpose: not a tampered input
        self.assertEqual(sorted(b["page"] for b in check["broken"]),  # the work left for /forget
                         ["cortex/concepts/idea.md", "cortex/entities/tool.md"])

    def test_only_the_owner_can_let_an_input_be_forgotten(self):
        def hook(command):
            return self.run_hook("protect_senses.py", {"tool_name": "Bash", "tool_input": {"command": command}})

        asked = hook("brain forget senses/bad.md --yes")
        self.assertEqual(asked.returncode, 0)
        self.assertEqual(json.loads(asked.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertEqual(hook("brain forget senses/bad.md").stdout, "")       # showing needs no one
        self.assertEqual(hook("rm senses/bad.md").returncode, 2)               # every other way is still shut
        self.assertEqual(hook("echo forget it --yes").stdout, "")

    def test_recall_strengthens_and_schedules(self):
        self.write("cortex/concepts/fresh.md", page("concept", updated=ago(2)))
        self.write("cortex/concepts/rehearsed.md", page("concept", updated=ago(100)))
        self.write("cortex/concepts/neglected.md", page("concept", updated=ago(40)))
        self.log(f"{ago(10)} recall rehearse -> [[rehearsed]]", f"{ago(6)} recall rehearse -> [[rehearsed]]",
                 f"{ago(3)} ingest senses/x.md -> [[neglected]]", f"{ago(1)} recall what is it -> [[neglected]]")
        v = self.brain()
        self.assertEqual(v.recall_count, {v.resolve("rehearsed"): 2, v.resolve("neglected"): 1})
        self.assertEqual(v.strength(v.resolve("rehearsed")), 2)  # 4 days apart: the 3-day interval had passed
        # fresh: 2 days >= 1-day interval; rehearsed: 6 days < 7; neglected: 40 days, most overdue,
        # and the model reading it yesterday to answer a question is not the owner recalling it
        self.assertEqual(v.strength(v.resolve("neglected")), 0)
        self.assertEqual([p.stem for p in v.due_for_rehearsal()], ["neglected", "fresh"])

    def test_a_missed_rehearsal_starts_over(self):
        self.write("cortex/concepts/known.md", page("concept", updated=ago(300)))
        passes = [f"{ago(n)} recall rehearse -> [[known]]" for n in (200, 190, 170, 130)]
        self.log(*passes)
        v = self.brain()
        self.assertEqual(v.strength(v.resolve("known")), 4)
        self.log(*passes, f"{ago(2)} rehearse missed -> [[known]]")
        v = self.brain()
        self.assertEqual(v.strength(v.resolve("known")), 0)
        self.assertEqual([p.stem for p in v.due_for_rehearsal()], ["known"])  # a miss comes back the next day
        self.log(*passes, f"{ago(2)} rehearse missed -> [[known]]", f"{ago(2)} recall rehearse -> [[known]]",
                 f"{ago(1)} recall rehearse -> [[known]]")
        v = self.brain()
        self.assertEqual(v.strength(v.resolve("known")), 1)  # re-asked the same day counts for nothing
        self.assertEqual(v.due_for_rehearsal(), [])

    def test_cramming_counts_once_per_interval(self):
        self.write("cortex/concepts/crammed.md", page("concept", updated=ago(30)))
        self.log(*[f"{ago(9)} recall rehearse -> [[crammed]]" for i in range(7)],
                 f"{ago(8)} recall rehearse -> [[crammed]]")
        v = self.brain()
        page_ = v.resolve("crammed")
        self.assertEqual((v.recall_count[page_], v.strength(page_)), (8, 1))
        self.assertEqual([p.stem for p in v.due_for_rehearsal()], ["crammed"])  # 8 days since, 3-day interval

    def test_dormant_candidates_spare_linked_salient_and_human(self):
        old = ago(400)
        self.write("cortex/concepts/faded.md", page("concept", updated=old))
        self.write("cortex/concepts/linked.md", page("concept", updated=old))
        self.write("cortex/concepts/salient.md", page("concept", updated=old, salience="high"))
        self.write("cortex/concepts/mine.md", page("concept", updated=old, maintained_by="human"))
        self.write("cortex/concepts/recent.md", page("concept", "[[linked]]", updated=ago(10)))
        self.write("cortex/episodes/ep.md", page("episode", updated=old))
        self.assertEqual([p.stem for p in self.brain().dormant_candidates()], ["faded"])

    def test_a_link_from_its_own_episode_does_not_keep_a_page(self):
        old = ago(400)
        self.write("cortex/concepts/unused.md", page("concept", "From [[ep]].", updated=old))
        self.write("cortex/concepts/used.md", page("concept", "From [[ep]].", updated=old))
        self.write("cortex/episodes/ep.md", page("episode", "About [[unused]] and [[used]].", updated=old))
        self.write("cortex/decisions/d.md", page("decision", "Rests on [[used]].", status="open", updated=old))
        v = self.brain()
        self.assertEqual([p.stem for p in v.dormant_candidates()], ["unused"])  # a decision depends on the other
        self.assertEqual(v.orphans(), [])  # still linked, so not an orphan: fading is about use
        os.makedirs(os.path.join(self.root, "dormant"))
        os.rename(os.path.join(self.root, "cortex/concepts/unused.md"), os.path.join(self.root, "dormant/unused.md"))
        v = self.brain()  # once it has faded, the episode's link is to a dormant page, not a broken one
        self.assertEqual((v.broken, [(p.stem, t) for p, t in v.faded]), ([], [("ep", "unused")]))

    def test_stale_concepts(self):
        self.write("cortex/concepts/old.md", page("concept", updated=ago(200)))
        self.write("cortex/concepts/new.md", page("concept", updated=ago(1)))
        concepts, stale = self.brain().stale_concepts()
        self.assertEqual((len(concepts), [p.stem for p in stale]), (2, ["old"]))


class Decisions(TempBrain):
    def problems(self, kind, **fields):
        return vaultlib.schema_problems(page(kind, **dict(DECIDED, **fields)))

    def test_decision_contract(self):
        self.assertEqual(self.problems("decision", status="open"), [])
        made = dict(review="2026-04-01", revisit_if='"churn passes 5%"')
        self.assertEqual(self.problems("decision", status="decided", **made), [])
        self.assertEqual(self.problems("decision", status="reviewed", outcome="worse", **made), [])
        for fields, expect in ((dict(status="maybe"), "status"), (dict(), "status"),
                               (dict(status="decided", revisit_if="x"), "review"),
                               (dict(status="decided", review="2026-04-01"), "revisit_if"),
                               (dict(status="decided", review="soon", revisit_if="x"), "YYYY-MM-DD"),
                               (dict(status="reviewed", **made), "outcome"),
                               (dict(status="reviewed", outcome="fine", **made), "outcome"),
                               (dict(status="decided", outcome="better", **made), "outcome")):
            self.assertIn(expect, "; ".join(self.problems("decision", **fields)), fields)
        self.assertIn("decision pages only", self.problems("concept", status="emerging", revisit_if="x")[0])

    CLAIMS = ("## Options\n### Raise\n- [observation] Two rivals raised and kept customers. [[rivals]]\n"
              "  A wrapped line belongs to the bullet above.\n- [interpretation] Price is not why people stay.\n"
              "## Expected\n- [hypothesis] Few leave; true if churn stays under 5%.\n- [assumption] Costs hold.\n"
              "## Decision\n- [decision] Raise by 10%.\n## Outcome\nChurn was 3% (owner).\n"
              "- [hypothesis] Few leave. -> held\n- [assumption] Costs hold. -> failed\n")

    def decided(self, body, status="decided", **fields):
        fields = dict(dict(review="2026-04-01", revisit_if="x"), **fields)
        return page("decision", body, status=status, **dict(DECIDED, **fields))

    def test_claims_are_tagged_once_decided(self):
        self.assertEqual(vaultlib.schema_problems(self.decided(self.CLAIMS)), [])
        loose = "## Expected\nFew customers leave.\n- no tag\n- [guess] not a tag\n"
        self.assertEqual(vaultlib.schema_problems(page("decision", loose, status="open", **DECIDED)), [])
        self.assertIn("3 untagged lines under ## Expected", vaultlib.schema_problems(self.decided(loose))[0])
        for body, expect in (("## Options\n- [decision] Raise.\n", "belongs under ## Decision"),
                             ("## Options\n- [observation] Rivals raised.\n", "cites nothing"),
                             ("## Lessons\nprose\n", "untagged")):
            self.assertIn(expect, "; ".join(vaultlib.schema_problems(self.decided(body))), body)
        seen = "## Options\n- [observation] I lost two customers last time (owner, 2026-01-05).\n"
        self.assertEqual(vaultlib.schema_problems(self.decided(seen)), [])

    def test_decision_report_counts_claims_and_results(self):
        self.write("cortex/concepts/rivals.md", page("concept"))
        self.write("cortex/episodes/imagined.md", page("episode", origin="generated"))
        self.write("cortex/decisions/raise.md", self.decided(self.CLAIMS, status="reviewed", outcome="better",
                                                             revisit_if='"a rival cuts prices"'))
        self.write("cortex/decisions/guess.md", self.decided(
            "## Options\n- [observation] It would work. [[imagined]]\n- [assumption] a\n- [assumption] b\n",
            tags="[to-revisit]"))
        self.write("cortex/decisions/framing.md", page("decision", "## Options\nnot tagged yet\n", status="open"))
        v = self.brain()
        guess, raise_ = v.decision_report()
        self.assertEqual((raise_["revisit_if"], raise_["triggered"]), ("a rival cuts prices", False))
        self.assertEqual(raise_["claims"], {"observation": 1, "interpretation": 1, "hypothesis": 1, "assumption": 1,
                                            "decision": 1})
        self.assertEqual((guess["claims"], guess["triggered"]), ({"observation": 1, "assumption": 2}, True))
        self.assertEqual(v.claim_results(), {"assumption": {"held": 0, "failed": 1, "unknown": 0},
                                             "hypothesis": {"held": 1, "failed": 0, "unknown": 0}})
        self.assertEqual([(p.stem, c) for p, c in v.claim_link_problems()], [("guess", "It would work. [[imagined]]")])
        self.assertEqual([p.stem for p in v.untagged_open()], ["framing"])
        check = subprocess.run([sys.executable, os.path.join(SCRIPTS, "link_check.py"), self.root, "--json"],
                               capture_output=True, text=True)
        report = json.loads(check.stdout)
        self.assertEqual((check.returncode, [c["page"] for c in report["claims"]], report["untagged"]),
                         (1, ["cortex/decisions/guess.md"], ["cortex/decisions/framing.md"]))
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "introspect.py"), self.root, "--decisions"],
                             capture_output=True, text=True, check=True).stdout
        for line in ("guess.md  TO REVISIT", "revisit if: a rival cuts prices", "(rests mostly on guesses)",
                     "hypothesis lines in reviewed decisions: held 1, failed 0, unknown 0"):
            self.assertIn(line, out)
        self.assertIn("decisions to revisit: 1 (guess)", self.run_hook("wake_up.py", {}).stdout)

    def test_outcome_and_origin_belong_to_their_types(self):
        self.assertIn("decision pages only", self.problems("concept", status="emerging", outcome="better")[0])
        self.assertIn("origin", self.problems("concept", status="emerging", origin="generated")[0])
        self.assertIn("origin", self.problems("episode", origin="dreamt")[0])
        self.assertEqual(self.problems("episode", origin="generated"), [])

    def test_due_open_and_calibration(self):
        self.write("cortex/decisions/late.md", page("decision", status="decided", review=ago(30)))
        self.write("cortex/decisions/today.md", page("decision", status="decided", review=ago(0)))
        self.write("cortex/decisions/later.md", page("decision", status="decided", review="2027-01-01"))
        self.write("cortex/decisions/done.md", page("decision", status="reviewed", review=ago(60), outcome="worse"))
        self.write("cortex/decisions/weighing.md", page("decision", status="open"))
        v = self.brain()
        self.assertEqual([p.stem for p in v.decisions_due()], ["late", "today"])
        self.assertEqual(v.calibration(), {"as-expected": 0, "better": 0, "worse": 1, "mixed": 0})

    def test_reviewed_decision_is_evidence_and_generated_episode_is_not(self):
        cand = "## Candidates\n- Small bets\n"
        self.write("cortex/episodes/read.md", page("episode", cand, created="2026-01-01"))
        self.write("cortex/episodes/imagined.md", page("episode", cand, created="2026-01-02", origin="generated"))
        self.write("cortex/decisions/tried.md", page("decision", cand, status="reviewed", updated="2026-03-01"))
        self.write("cortex/decisions/pending.md", page("decision", cand, status="decided"))
        v = self.brain()
        row, = v.candidate_tally()
        self.assertEqual(sorted(p.stem for p in row["episodes"]), ["read", "tried"])
        self.assertEqual([p.stem for p in row["generated"]], ["imagined"])
        # dated by its review: replayed after both episodes; an unreviewed decision is not queued
        self.assertEqual([p.stem for p in v.unconsolidated()], ["read", "imagined", "tried"])

    def test_decisions_never_fade(self):
        self.write("cortex/decisions/old.md", page("decision", status="open", updated=ago(400)))
        self.assertEqual(self.brain().dormant_candidates(), [])

    def test_briefing_and_introspect_show_due_decisions(self):
        self.write("cortex/decisions/pick-a-host.md", page("decision", status="decided", review="2020-01-01"))
        self.write("cortex/decisions/tried.md", page("decision", status="reviewed", outcome="better",
                                                     review="2020-01-01", updated="2020-02-01"))
        out = self.run_hook("wake_up.py", {}).stdout
        self.assertIn("Awaiting /sleep: 0 episodes, 1 decisions", out)
        self.assertIn("decisions to review: 1 (pick-a-host)", out)
        r = json.loads(subprocess.run([sys.executable, os.path.join(SCRIPTS, "introspect.py"), self.root, "--json"],
                                      capture_output=True, text=True, check=True).stdout)
        self.assertEqual((r["decisions_due"], r["calibration"]["better"]), (1, 1))
        self.assertEqual(r["decisions"]["due"], [{"page": "cortex/decisions/pick-a-host.md", "review": "2020-01-01"}])

    def test_explore_and_decide_must_log_recall(self):
        for skill in ("aibrain:explore", "decide"):
            path = self.write("t.jsonl", json.dumps({"type": "user", "message": {"content": "go"}}) + "\n"
                              + json.dumps({"type": "assistant", "message": {"content": [
                                  {"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]}}))
            r = self.run_hook("check_recall.py", {"transcript_path": path})
            self.assertEqual(r.returncode, 2, skill)


class OverTime(TempBrain):
    """S2: goals end, evidence counts by source, snapshots are data."""

    def owner(self, *goals):
        self.write("CLAUDE.md", "# Brain\n\n## Owner\n\n### Goals\n\n" + "\n".join(goals) + "\n\n## Tags\n\n`disputed`\n")

    def test_goal_states(self):
        self.owner(f"- Open by {ago(-10)}", f"- Late by {ago(5)}", f"- Old by {ago(31)}",
                   f"- Shipped by {ago(90)} (done)", "- Abandoned (dropped) -> [[x]]", "- Someday")
        states = {g["goal"]: g["state"] for g in self.brain().goal_report()}
        self.assertEqual(states, {"Open": "open", "Late": "past-due", "Old": "stale", "Shipped": "done",
                                  "Abandoned": "dropped", "Someday": "open"})

    def test_ended_and_stale_goals_let_go_of_their_pages(self):
        for name in ("live", "late", "stale", "done"):
            self.write(f"cortex/concepts/{name}.md", page("concept", updated=ago(400)))
        self.owner(f"- A -> [[live]]", f"- B by {ago(10)} -> [[late]]", f"- C by {ago(60)} -> [[stale]]",
                   "- D -> [[done]] (done)")
        v = self.brain()
        self.assertEqual({p.stem for p in v.purpose()}, {"live", "late"})
        self.assertEqual(sorted(p.stem for p in v.dormant_candidates()), ["done", "stale"])

    def test_briefing_names_goals_that_need_the_owner(self):
        self.owner("- Calm -> [[page]]")
        self.write("cortex/concepts/page.md", page("concept"))
        self.assertNotIn("Goals:", self.run_hook("wake_up.py", {}).stdout)  # nothing to act on, nothing said
        self.owner("- Ship course by 2020-01-01", "- Learn Go")
        out = self.run_hook("wake_up.py", {}).stdout
        self.assertIn("Goals: 1 past due (Ship course): close, re-date or drop | 1 with no pages behind them (Learn Go)",
                      out)

    def test_same_source_counts_once(self):
        cand = "## Candidates\n- Idea - x\n"
        self.write("cortex/episodes/a.md", page("episode", cand, url="https://www.blog.example/post/"))
        self.write("cortex/episodes/b.md", page("episode", cand, url="http://blog.example/post"))
        self.write("cortex/episodes/c.md", page("episode", cand, input="senses/talk.md"))
        self.write("cortex/episodes/d.md", page("episode", cand, input="./senses/talk.md"))
        row, = self.brain().candidate_tally()
        self.assertEqual((len(row["episodes"]), row["sources"]), (4, 2))
        self.write("cortex/decisions/tried.md", page("decision", cand, status="reviewed"))
        self.write("cortex/episodes/e.md", page("episode", cand))  # no url, no input: its own source
        row, = self.brain().candidate_tally()
        self.assertEqual((len(row["episodes"]), row["sources"]), (6, 4))

    def test_tracking_parameters_do_not_make_a_new_source(self):
        cand = "## Candidates\n- Idea - x\n"
        for name, url in (("a", "https://blog.example/post?utm_source=mail&fbclid=1#top"),
                          ("b", "https://blog.example/post"),
                          ("c", "https://Video.example/watch?v=one"), ("d", "https://video.example/watch?v=One"),
                          ("e", "https://video.example/watch?v=one&UTM_medium=x")):
            self.write(f"cortex/episodes/{name}.md", page("episode", cand, url=url))
        row, = self.brain().candidate_tally()
        self.assertEqual(row["sources"], 3)  # the post once; two videos, told apart by what the query names

    def test_an_alias_names_the_same_candidate(self):
        self.write("cortex/concepts/llm-wiki.md", page("concept", title="LLM Wiki", aliases="[llm wiki pattern]"))
        self.write("cortex/episodes/a.md", page("episode", "## Candidates\n- LLM Wiki - x\n", url="https://a.example"))
        self.write("cortex/episodes/b.md", page("episode", "## Candidates\n- llm wiki pattern - x\n",
                                                url="https://b.example"))
        row, = self.brain().candidate_tally()
        self.assertEqual((row["sources"], row["page"].stem), (2, "llm-wiki"))

    def snap(self, *extra):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "introspect.py"), self.root, "--snapshot",
                            "--json", *extra], capture_output=True, text=True, check=True)
        return json.loads(r.stdout)["snapshot"]

    def metrics(self):
        with open(os.path.join(self.root, "hippocampus", "metrics.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_snapshot_starts_on_its_own_line(self):
        self.write("hippocampus/metrics.md", page("metrics", "no trailing newline"))
        self.snap()
        self.snap()
        self.assertEqual(sum(line[:4].isdigit() for line in self.metrics().splitlines()), 1)

    def test_snapshot_is_data_once_a_day_with_changes(self):
        self.write("hippocampus/metrics.md", page("metrics", "\n# Metrics\n\n`YYYY-MM-DD {metrics as JSON}`\n"
                                                  '2020-01-01 {"pages": 3, "links": 1, "orphan_rate": 50.0}\n'))
        self.write("cortex/concepts/a.md", page("concept", "[[b]]", **VALID))
        self.write("cortex/concepts/b.md", page("concept", "[[a]]", title="B", status="established",
                                                created="2026-01-01", updated="2026-01-01"))
        first = self.snap()
        self.assertEqual(first["since"], "2020-01-01")
        self.assertEqual((first["changes"]["pages"], first["changes"]["orphan_rate"]), (-1, -50.0))
        self.assertEqual(self.snap()["since"], "2020-01-01")  # same day: compares with the same baseline
        today = [line for line in self.metrics().splitlines() if line.startswith(datetime.date.today().isoformat())]
        self.assertEqual(len(today), 1)
        self.assertEqual(json.loads(today[0].split(" ", 1)[1])["pages"], 2)


if __name__ == "__main__":
    unittest.main()
