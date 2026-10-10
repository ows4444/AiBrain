"""Tuning per brain: every threshold in one registry, a brain's own values in hippocampus/tuning.md. Run: brain test"""
import datetime
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from support import ENGINE, HOOKS, SCRIPTS, TODAY, TempBrain, ago, page, project, run_brain, vaultlib

import commands  # noqa: E402  (support puts engine/lib on the path)
import introspect  # noqa: E402
import vault_cache  # noqa: E402
import vault_tuning  # noqa: E402

DATES = dict(created="2026-01-01", updated="2026-01-01")
OLD = dict(created=ago(300), updated=ago(300))


def concept(body="", **fields):
    return page("concept", body, **dict(dict(status="established", **OLD), **fields))


def ahead(days):
    return (TODAY + datetime.timedelta(days=days)).isoformat()


class Tuned(TempBrain):
    def tune(self, *lines):
        """Write hippocampus/tuning.md holding these override lines; none leaves the section empty."""
        return self.write(vaultlib.TUNING_PATH, page("tuning", "\n# Tuning\n\nWhat this brain changed.\n\n## Overrides\n\n"
                                                     + "".join(f"- {line}\n" for line in lines), title="Tuning"))

    def trying(self, **values):
        """The brain with these values laid over its own, as `brain eval --set` runs it."""
        return vaultlib.Vault(self.root, today=TODAY, tuning=values)


class Registry(unittest.TestCase):
    def test_every_default_is_inside_its_range_and_reads_back_as_it_is_shown(self):
        for name, spec in vaultlib.THRESHOLDS.items():
            with self.subTest(name):
                self.assertTrue(spec.what and not spec.what.endswith("."), "what it does, as one phrase")
                # value_of refuses a value outside the range, so this holds the default inside it
                # too; and a line of `brain introspect --usage` can be pasted into tuning.md as it is.
                self.assertEqual(vault_tuning.value_of(name, vaultlib.shown(spec.default)), spec.default)

    def test_every_threshold_is_read_by_the_engine_and_none_is_left_as_a_constant(self):
        source = ""
        for name in sorted(os.listdir(SCRIPTS)):
            if name.endswith(".py") and name != "vault_tuning.py":
                with open(os.path.join(SCRIPTS, name), encoding="utf-8") as fh:
                    source += fh.read()
        relations = {r.replace("-", "_") for r in vaultlib.RELATIONS}
        for name in vaultlib.THRESHOLDS:
            with self.subTest(name):
                self.assertFalse(hasattr(vaultlib, name.upper()), "one place holds it: the registry")
                family, _, member = name.partition("_")
                if family == "weight":  # read by its prefix: the fields search knows how to take from a page
                    self.assertIn(member, ("title", "aliases", "answers", "body", "summary"))
                elif family == "relation":  # read by its prefix: one for each relation of the vocabulary
                    self.assertIn(member, relations)
                elif name == "trait_span":  # read where the traits are applied, which is the registry's own module
                    tried = vault_tuning.tuning_of(self.id(), {"trait_span": 3.0, "caution": 0.0})  # no brain there
                    self.assertEqual(tried.min_coverage, 0.05)  # a third of 0.15, where a span of 2 gives half
                else:
                    self.assertRegex(source, rf"\.{name}\b")
        self.assertEqual({n.partition("_")[2] for n in vaultlib.THRESHOLDS if n.startswith("relation_")}, relations)

    def test_values_are_plain_data_in_a_result_and_come_back_as_they_were(self):
        tuning = vaultlib.Tuning({"rehearsal_days": [2, 6], "recall_floor": 0.3})  # as JSON carries them
        self.assertEqual((tuning.rehearsal_days, tuning.recall_floor, tuning.stale_days), ((2, 6), 0.3, 90))
        self.assertEqual(tuning.changed(), {"rehearsal_days": [2, 6], "recall_floor": 0.3})
        self.assertEqual(vaultlib.Tuning(tuning.changed()).rehearsal_days, (2, 6))
        self.assertEqual(vaultlib.Tuning().changed(), {})
        self.assertEqual((vaultlib.shown((1, 3)), vaultlib.shown([1, 3]), vaultlib.shown(0.4)), ("1, 3", "1, 3", "0.4"))
        json.dumps(tuning.rows())


class Overrides(unittest.TestCase):
    def test_a_line_is_a_name_a_value_and_an_optional_note(self):
        text = page("tuning", "\n# Tuning\n\n- stale_days = 1 (above the heading: prose, never read)\n\n## Overrides\n\n"
                    "Kept after the review of November.\n\n"
                    "- recall_floor = 0.35 (2026-11-02: hit@5 0.81 to 0.88 (my own questions))\n"
                    "* `stale_days` = 120\n- `weight_title = 4`\n- rehearsal_days = 2, 5,11\n---\n_Nothing else._\n\n"
                    "## Notes\n\n- dormant_days = 1\n")
        self.assertEqual(vault_tuning.read_overrides(text), ({"recall_floor": 0.35, "stale_days": 120,
                                                              "weight_title": 4.0, "rehearsal_days": (2, 5, 11)}, []))
        self.assertEqual(vault_tuning.read_overrides("a page with no such section"), ({}, []))

    def test_what_cannot_be_used_is_listed_and_the_default_holds(self):
        listed = "; `brain introspect --usage` lists them"
        for line, problem in (
                ("recal_floor = 0.3", "'recal_floor' is not a threshold (closest: recall_floor)" + listed),
                ("zzz = 1", "'zzz' is not a threshold" + listed),
                ("spread_hops = 9", "'spread_hops = 9' is outside 0 to 6"),
                ("spread_hops = 1.5", "'spread_hops = 1.5' is not a whole number"),
                ("recall_floor = low", "'recall_floor = low' is not a number"),
                ("recall_floor = 0.3 since November", "'recall_floor = 0.3 since November' is not a number"),
                ("recall_floor =", "'recall_floor = ' is not a number"),
                ("recall_floor = nan", "'recall_floor = nan' is outside 0.0 to 1.0"),
                ("rehearsal_days = 1, two", "'rehearsal_days = 1, two' is not whole numbers with commas between them"),
                ("rehearsal_days = 1, 7, 7", "'rehearsal_days = 1, 7, 7' must rise: each number larger than the one before"),
                ("rehearsal_days = 0, 7", "'rehearsal_days = 0, 7' is outside 1 to 3650"),
                ("recall_floor 0.3", "cannot read '- recall_floor 0.3': an override is `- name = value (why)`")):
            with self.subTest(line):
                self.assertEqual(vault_tuning.read_overrides(f"## Overrides\n\n- {line}\n"), ({}, [problem]))
        twice = "## Overrides\n- recall_floor = 0.3\n- recall_floor = 0.2\n"
        self.assertEqual(vault_tuning.read_overrides(twice),
                         ({"recall_floor": 0.2}, ["'recall_floor' is set twice; the later line is the one used"]))
        self.assertEqual(vault_tuning.tuning_problems(twice), vault_tuning.read_overrides(twice)[1])

    def test_a_value_given_on_the_command_line_is_read_the_same_way(self):
        self.assertEqual(vaultlib.setting("recall_floor=0.3"), ("recall_floor", 0.3))
        self.assertEqual(vaultlib.setting(" rehearsal_days = 1,2 "), ("rehearsal_days", (1, 2)))
        for text, why in (("recall_floor", "'recall_floor' is not name=value"),
                          ("recall_floor=2", "'recall_floor = 2' is outside 0.0 to 1.0")):
            with self.assertRaises(ValueError) as refused:
                vaultlib.setting(text)
            self.assertEqual(str(refused.exception), why)

    def test_the_template_page_overrides_nothing_and_its_type_belongs_to_that_one_file(self):
        with open(os.path.join(ENGINE, "templates", "brain", vaultlib.TUNING_PATH), encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(vault_tuning.read_overrides(text), ({}, []))
        self.assertEqual(vaultlib.schema_problems(text, rel=vaultlib.TUNING_PATH), [])
        elsewhere = vaultlib.schema_problems(text, rel="cortex/concepts/tuning.md", stem="tuning")
        self.assertIn("type 'tuning' belongs only to hippocampus/tuning.md", elsewhere[0])


class ABrainsOwnValues(Tuned):
    """Done when: a threshold is changed, measured and rolled back without touching engine/ or restarting."""

    def stale(self):
        return json.loads(run_brain(self.root, "introspect", "--stale", "--json").stdout)

    def test_a_line_changes_a_threshold_for_every_command_and_removing_it_changes_it_back(self):
        self.write("cortex/concepts/old.md", concept("Study spread over days. " * 20, title="Old", updated=ago(30)))
        self.assertEqual((self.stale()["stale"], self.stale()["tuning"]), ([], {}))  # no tuning.md: the defaults
        self.tune("stale_days = 20 (trying a shorter wait)")
        now = self.stale()
        self.assertEqual(([x["page"] for x in now["stale"]], now["tuning"]), (["cortex/concepts/old.md"], {"stale_days": 20}))
        self.assertIn("(untouched 20+ days)", run_brain(self.root, "introspect").stdout)
        self.assertIn("ask the owner whether these still hold: cortex/concepts/old.md",
                      run_brain(self.root, "recall", "study spread over days").stdout)
        self.tune()
        self.assertEqual((self.stale()["stale"], self.stale()["tuning"]), ([], {}))
        self.assertIn("(untouched 90+ days)", run_brain(self.root, "introspect").stdout)

    def test_check_fails_on_a_name_that_is_no_threshold_and_on_a_value_out_of_range(self):
        self.write("cortex/concepts/short.md", concept("Seven words of text and no link.", title="Short"))
        self.tune("recal_floor = 0.3", "spread_hops = 9", "stub_words = 5 (a stub is shorter here)")
        r = run_brain(self.root, "check", "--json")
        report = json.loads(r.stdout)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(report["schema"], [{"page": "hippocampus/tuning.md", "problems": [
            "'recal_floor' is not a threshold (closest: recall_floor); `brain introspect --usage` lists them",
            "'spread_hops = 9' is outside 0 to 6"]}])
        # What could be read is in force; what could not keeps its default.
        self.assertEqual((report["tuning"], report["stubs"], self.brain().tuning.spread_hops), ({"stub_words": 5}, [], 2))
        self.assertIn("\nstubs (<5 words, no links): 0\n", run_brain(self.root, "check").stdout)
        self.tune("stub_words = 5")
        self.assertEqual(run_brain(self.root, "check").returncode, 0)
        self.tune()
        default = run_brain(self.root, "check")
        self.assertEqual(default.returncode, 0)
        self.assertIn("\nstubs (<40 words, no links): 1\n", default.stdout)

    def test_the_page_hook_refuses_the_write_that_would_leave_a_bad_override(self):
        path = self.tune("recall_floor = 0.3")

        def hook(*flags, **tool_input):
            return subprocess.run([sys.executable, os.path.join(HOOKS, "validate_page.py"), *flags], text=True,
                                  input=json.dumps({"tool_name": "Edit", "tool_input": dict(file_path=path, **tool_input)}),
                                  capture_output=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))

        bad = hook("--pre", old_string="recall_floor = 0.3", new_string="recall_floor = 3")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("Blocked before writing hippocampus/tuning.md: 'recall_floor = 3' is outside 0.0 to 1.0", bad.stderr)
        self.assertEqual(hook("--pre", old_string="0.3", new_string="0.35 (measured)").returncode, 0)
        self.tune("no_such_thing = 1")  # written some other way: the check after the write still says so
        self.assertEqual(hook().returncode, 2)

    def test_usage_lists_every_threshold_with_its_default_beside_the_brain_s_value(self):
        self.tune("recall_floor = 0.3", "rehearsal_days = 2, 6")
        r = json.loads(run_brain(self.root, "introspect", "--usage", "--json").stdout)
        row = r["usage"]["thresholds"]["recall_floor"]
        self.assertEqual((row["value"], row["default"], row["low"], row["high"]), (0.3, 0.4, 0.0, 1.0))
        self.assertEqual(r["usage"]["thresholds"]["rehearsal_days"]["value"], [2, 6])
        self.assertEqual(r["tuning"], {"recall_floor": 0.3, "rehearsal_days": [2, 6]})
        text = run_brain(self.root, "introspect", "--usage").stdout
        self.assertIn("\nthresholds (a line under `## Overrides` in hippocampus/tuning.md changes one, written as below; "
                      f"`brain eval --set name=value` measures one first): {len(vaultlib.THRESHOLDS)}\n", text)
        self.assertIn("\n  recall_floor = 0.3  (default 0.4; 0.0 to 1.0): recall cuts rows scoring under", text)
        self.assertIn("\n  rehearsal_days = 2, 6  (default 1, 3, 7, 14, 30, 60, 120; 1 to 3650): days until", text)
        self.assertIn("\n  min_coverage = 0.15  (0.0 to 1.0): recall lists nothing", text)

    def test_a_value_being_tried_lies_over_the_brain_s_own_and_is_never_written(self):
        path = self.tune("recall_floor = 0.3")
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        vault = self.trying(recall_floor=0.2, stale_days=5)
        self.assertEqual((vault.tuning.recall_floor, vault.tuning.stale_days, vault.tuning.dormant_days), (0.2, 5, 180))
        self.assertEqual(vault.tuning.changed(), {"recall_floor": 0.2, "stale_days": 5})
        self.assertEqual(self.brain().tuning.changed(), {"recall_floor": 0.3})
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)


class WhatEachThresholdMoves(Tuned):
    """One reading of each kind: a threshold a brain changes is the number the engine then judges by."""

    def test_rehearsal_fading_stubs_and_the_checkpoint(self):
        self.write("cortex/concepts/fresh.md", concept("Three words only.", created=ago(5), updated=ago(5)))
        self.write("cortex/concepts/two.md", concept("Three words only.", salience="2"))
        self.write("cortex/episodes/e.md", page("episode", "## Candidates\n- A - x\n", **DATES))
        self.log(f"{ago(9)} rehearse missed -> [[two]]", f"{ago(4)} recall rehearse -> [[fresh]]",
                 f"{ago(2)} sleep 1 episode -> done", f"{ago(1)} recall rehearse -> [[fresh]]")
        v = self.brain()
        self.assertEqual(v.strength(v.resolve("fresh")), 2)  # three days apart: a second spaced pass
        self.assertEqual([p.stem for p in v.due_for_rehearsal()], ["two"])  # a miss nine days ago, due after one
        self.assertEqual(introspect.report(v, ["due"])["risk"], {})  # one attempt: too few to show a rate
        self.assertEqual((v.fade_days(v.resolve("two")), v.dormant_candidates()), (360, []))
        self.assertEqual(sorted(p.stem for p in v.stubs()), ["fresh", "two"])
        self.assertFalse(v.usage()["checkpoint"]["reached"])

        t = self.trying(rehearsal_days=(1, 5), risk_min_attempts=1)
        self.assertEqual(t.strength(t.resolve("fresh")), 1)  # five days are asked for now
        self.assertEqual(introspect.report(t, ["due"])["risk"], {"cortex/concepts/two.md": {"miss_rate": 0.67, "attempts": 1}})
        self.assertEqual(self.trying(rehearsal_days=(10, 20)).due_for_rehearsal(), [])
        sooner = self.trying(dormant_days=100)
        self.assertEqual((sooner.fade_days(sooner.resolve("two")), [p.stem for p in sooner.dormant_candidates()]),
                         (200, ["two"]))  # untouched for 300 days
        self.assertEqual(self.trying(dormant_days=100, salience_stretch=1.0).dormant_candidates(), [])  # 300, not past it
        self.assertEqual(self.trying(stub_words=3).stubs(), [])  # a stub has fewer words than this
        self.assertEqual(self.trying(checkpoint_inputs=1, checkpoint_sleeps=1).usage()["checkpoint"], {
            "inputs": 1, "inputs_needed": 1, "sleeps": 1, "sleeps_needed": 1, "reached": True, "reviewed": False})

    def test_guesses_scored_and_ideas_paired(self):
        self.write("cortex/episodes/e1.md", page("episode", "## Candidates\n- Optimal gap - the best gap between study "
                                                 "sessions\n", url="https://a.example"))
        self.write("cortex/episodes/e2.md", page("episode", "## Candidates\n- Session timing - the gap between study "
                                                 "sessions matters\n", url="https://b.example"))
        self.assertEqual([(x["a"], x["b"]) for x in self.brain().candidate_pairs()], [("Optimal gap", "Session timing")])
        self.assertEqual(self.trying(pair_min_words=5).candidate_pairs(), [])  # they share four words
        self.assertEqual(self.trying(pair_overlap=1.0).candidate_pairs(), [])  # four of the six each holds
        self.assertFalse(self.brain()._brier([(0.7, True)])["enough"])
        self.assertTrue(self.trying(brier_min=1)._brier([(0.7, True)])["enough"])

    def test_the_graph_views(self):
        for name in ("a", "b", "c"):
            self.write(f"cortex/concepts/{name}.md", concept("[[hub]] [[a]] [[b]] [[c]]", title=name.upper()))
        self.write("cortex/concepts/hub.md", concept("[[a]] [[b]] [[c]]", title="Hub"))
        self.write("cortex/concepts/s1.md", concept(title="Spaced repetition schedule"))
        self.write("cortex/concepts/s2.md", concept(title="Spaced repetition system"))
        v = self.brain()
        self.assertEqual((v.hubs(), v.near_duplicates(), v.betweenness_estimated()), ([], [], False))
        self.assertEqual(len(v.schema_candidates()), 1)  # four concepts linked to each other, no insight over them
        self.assertEqual([p.stem for p in self.trying(hub_min=2, hub_factor=1).hubs()], ["a", "b", "c", "hub"])
        self.assertEqual(self.trying(hub_min=2, hub_factor=2).hubs(), [])  # each has three inbound; twice the average is four
        self.assertEqual([(a.stem, b.stem) for a, b, _, _ in self.trying(near_duplicate=0.5).near_duplicates()], [("s1", "s2")])
        self.assertEqual(self.trying(schema_min=5).schema_candidates(), [])
        self.assertEqual(vaultlib.verdicts(6, 2.5, 70, 50), {
            "orphan_rate": "watch", "avg_degree": "acceptable", "components": "fragmented: answers will be silently incomplete"})
        loose = vaultlib.Tuning({"orphan_healthy": 7, "degree_low": 2, "main_component_min": 60})
        self.assertEqual(vaultlib.verdicts(6, 2.5, 70, 50, loose), {
            "orphan_rate": "healthy", "avg_degree": "working range", "components": "one main component"})
        tight = vaultlib.Tuning({"orphan_broken": 5, "degree_weak": 3, "degree_decorative": 2})
        self.assertIn("not linking", vaultlib.verdicts(6, 2.5, 70, 50, tight)["orphan_rate"])
        self.assertIn("barely", vaultlib.verdicts(6, 2.5, 70, 50, tight)["avg_degree"])
        self.assertIn("decorative", vaultlib.verdicts(6, 3.5, 70, 50, vaultlib.Tuning({"degree_decorative": 3}))["avg_degree"])
        self.assertEqual(vaultlib.verdicts(6, 9, 70, 50, vaultlib.Tuning({"degree_high": 9}))["avg_degree"], "working range")

    def test_bridges_are_estimated_from_the_brain_s_sample(self):
        for i in range(1, 7):  # a chain: every page between the ends is a bridge
            self.write(f"cortex/concepts/c{i}.md", concept(f"[[c{i + 1}]]" if i < 6 else "", title=f"C{i}"))
        v, sampled = self.brain(), self.trying(bridges_exact_up_to=3, bridges_sample=2)
        self.assertEqual((v.betweenness_estimated(), sampled.betweenness_estimated()), (False, True))
        named = lambda scores: {p.stem: s for p, s in scores.items()}  # noqa: E731
        self.assertEqual(named(sampled.betweenness()), named(v.betweenness(exact_up_to=3, sample=2)))
        self.assertNotEqual(named(sampled.betweenness()), named(v.betweenness()))

    def test_goals(self):
        self.write("cortex/concepts/thesis.md", concept(updated=ago(20)))
        self.write("OWNER.md", f"# Owner\n\n## Goals\n\n- Hand in by {ahead(20)} -> [[thesis]]\n- Move by {ago(10)}\n")
        report = {g["goal"]: g for g in self.brain().goal_report()}
        self.assertEqual((report["Hand in"]["at_risk"], report["Hand in"]["activity"], report["Move"]["state"]),
                         (False, 1, "past-due"))
        quiet = {g["goal"]: g for g in self.trying(activity_days=10).goal_report()}
        self.assertEqual((quiet["Hand in"]["at_risk"], quiet["Hand in"]["activity"]), (True, 0))
        self.assertFalse(self.trying(activity_days=10, goal_slip_days=5).goal_report()[0]["at_risk"])
        self.assertEqual(self.trying(goal_stale_days=5).goal_report()[1]["state"], "stale")

    def test_search_weighs_the_fields_as_the_brain_says(self):
        self.write("cortex/concepts/spacing.md", concept("Study spread over days. " * 30, title="Spacing effect",
                                                         summary="Longer gaps hold a memory."))
        self.write("cortex/concepts/gaps.md", concept("Gaps between rows of a table.", title="Layout"))

        def found(vault, query):
            return {p.stem: round(score, 4) for p, score in vault.search(query)}

        v = self.brain()
        self.assertEqual(list(found(v, "gaps")), ["gaps", "spacing"])  # a word of the summary counts for half
        self.assertEqual(list(found(self.trying(weight_summary=0.0), "gaps")), ["gaps"])  # at 0 it is not searched
        self.assertEqual(list(found(self.trying(weight_summary=50.0), "gaps")), ["spacing", "gaps"])
        self.assertEqual([f for f, _ in self.trying(weight_summary=0.0).tuning.field_weights],
                         ["title", "aliases", "answers", "body"])
        self.assertGreater(found(self.trying(bm25_b=0.0), "study")["spacing"], found(v, "study")["spacing"])  # length forgiven
        self.assertLess(found(self.trying(bm25_k1=0.0), "study")["spacing"], found(v, "study")["spacing"])  # repeats ignored

    def test_recall_spreads_and_stops_as_the_brain_says(self):
        self.write("cortex/concepts/alpha.md", concept("Alpha alpha, see (supports:: [[beta]]) and (part-of:: [[gamma]]).",
                                                       title="Alpha"))
        self.write("cortex/concepts/beta.md", concept("Nothing of the word here.", title="Beta"))
        self.write("cortex/concepts/gamma.md", concept("Nor here.", title="Gamma"))
        self.write("cortex/concepts/delta.md", concept("Alpha is named once in a long page. " + "Filler text. " * 40,
                                                       title="Delta"))
        self.write("cortex/concepts/far.md", concept("Unlinked.", title="Far"))
        self.write("prefrontal/work/CLAUDE.md", project("Uses [[delta]] and [[far]]."))
        self.log(f"{ago(90)} recall what is alpha -> [[alpha]], [[far]]", f"{ago(40)} recall rehearse -> [[alpha]]")
        v = self.brain()
        alpha, beta, gamma, far = (v.resolve(n) for n in ("alpha", "beta", "gamma", "far"))

        def scores(vault, **how):
            return {r["page"].stem: r["score"] for r in vault.recall("alpha", **how)}

        self.assertEqual(v.edge_weights(), {frozenset((alpha, far)): 0.5})  # one half-life old
        graph = v.association_graph()
        self.assertEqual((graph[alpha][beta], graph[alpha][gamma]), (1.2, 1.1))
        self.assertAlmostEqual(graph[alpha][far], 0.5 * 0.4054651, places=6)
        self.assertEqual(sorted(scores(v)), ["alpha", "beta", "delta", "far", "gamma"])
        self.assertEqual(scores(v, hops=0)["alpha"], 1.05)  # one rehearsal passed lifts it by strength_lift

        t = self.trying(hebbian_half_life=45, relation_supports=2.0, relation_part_of=3.0, unlinked_association=0.0)
        alpha, beta, gamma, far = (t.resolve(n) for n in ("alpha", "beta", "gamma", "far"))
        self.assertEqual(t.edge_weights(), {frozenset((alpha, far)): 0.25})
        self.assertEqual((t.association_graph()[alpha][beta], t.association_graph()[alpha][gamma]), (2.0, 3.0))
        self.assertNotIn(far, t.association_graph()[alpha])
        self.assertEqual(sorted(scores(self.trying(spread_hops=0))), ["alpha", "delta"])       # the hits and no further
        self.assertEqual(sorted(scores(self.trying(seed_limit=1, spread_hops=0))), ["alpha"])  # one hit seeds it
        self.assertEqual(scores(self.trying(spread_decay=0.0))["beta"], 0.0)                   # followed, nothing passed on
        self.assertEqual(scores(self.trying(strength_lift=0.5), hops=0)["alpha"], 1.5)

        on_project = scores(v, project="work", hops=0)
        self.assertEqual(on_project["far"], 0.2)  # linked from the project, no hit: a weak seed
        tried = scores(self.trying(project_boost=3.0, project_seed=0.7), project="work", hops=0)
        self.assertEqual(tried["far"], 0.7)
        self.assertAlmostEqual(tried["delta"] / on_project["delta"], 2.0, places=2)  # 3.0 against 1.5

    def test_a_page_s_own_recalls_lift_it_only_when_the_brain_says(self):
        self.write("cortex/concepts/alpha.md", concept("Alpha alpha alpha.", title="Alpha"))
        self.write("cortex/concepts/delta.md", concept("Alpha, and alpha again here.", title="Delta"))
        self.write("cortex/concepts/far.md", concept("Unlinked.", title="Far"))
        self.write("hippocampus/index.md", page("index", "\n# Index\n"))
        self.log(f"{ago(90)} recall alpha in passing -> [[delta]], [[far]], [[no-such-page]]",
                 f"{ago(0)} recall alpha in passing again -> [[delta]], [[delta]], [[index]]",  # named twice: used once
                 f"{ago(0)} recall and once more -> [[delta]]",
                 f"{ago(0)} recall rehearse -> [[far]]", f"{ago(0)} rehearse missed -> [[far]]",  # the owner tested: no use
                 f"{ago(0)} ingest senses/a.md -> 1 episode")

        def scores(vault):
            return {r["page"].stem: r["score"] for r in vault.recall("alpha", hops=0)}

        v = self.brain()
        delta, far = v.resolve("delta"), v.resolve("far")
        self.assertEqual(v.use_weights(), {delta: 2.5, far: 0.5})  # one half-life old counts half; no system page
        self.assertEqual((v.lift_from_use(delta), scores(v)["alpha"]), (0.0, 1.0))  # counted, and left out of the rank
        plain = scores(v)
        self.assertEqual(list(plain), ["alpha", "delta"])
        self.assertTrue(0.5 < plain["delta"] < 0.8, plain)  # what the three cases below rest on

        on = self.trying(use_lift=0.2)
        self.assertAlmostEqual(on.lift_from_use(on.resolve("delta")), 0.1)  # 2.5 of the 5 that earn all of it
        self.assertEqual(on.lift_from_use(on.resolve("alpha")), 0.0)  # never recalled: nothing to lift it by
        self.assertAlmostEqual(on.lift_from_use(on.resolve("far")), 0.02)
        self.assertAlmostEqual(scores(on)["delta"] / plain["delta"], 1.1, places=3)
        full = self.trying(use_lift=0.2, use_full=2)
        self.assertEqual(full.lift_from_use(full.resolve("delta")), 0.2)  # past use_full it grows no further
        self.assertEqual(list(scores(full)), ["alpha", "delta"])  # the cap: the page the question names stays first
        self.assertEqual(list(scores(self.trying(use_lift=1.0, use_full=2))), ["delta", "alpha"])  # what a cap is for
        faster = self.trying(use_lift=0.2, hebbian_half_life=45)
        self.assertEqual(faster.use_weights()[faster.resolve("delta")], 2.25)  # the old recall is two half-lives old

    def test_recall_cuts_and_abstains_as_the_brain_says(self):
        self.write("cortex/concepts/alpha.md", concept("Alpha alpha alpha.", title="Alpha", summary="What alpha is."))
        self.write("cortex/concepts/delta.md", concept("A long page. " + "Filler text. " * 40, title="Delta",
                                                       summary="It names alpha in passing."))

        def recalled(*args):
            return [r["page"] for r in json.loads(run_brain(self.root, "recall", *args, "--json").stdout)["results"]]

        self.assertEqual(recalled("alpha"), ["cortex/concepts/alpha.md"])  # delta scores under 0.4 of it: cut
        asked = ("alpha", "zebra", "quartz", "violin", "harbour", "lantern", "mosaic")
        self.assertEqual(recalled(*asked), [])  # one word of seven reaches a page
        self.tune("recall_floor = 0.0", "min_coverage = 0.0")
        self.assertEqual(recalled("alpha"), ["cortex/concepts/alpha.md", "cortex/concepts/delta.md"])
        self.assertEqual(recalled(*asked), ["cortex/concepts/alpha.md", "cortex/concepts/delta.md"])

    def test_the_hops_of_recall_are_the_brain_s_unless_the_command_gives_them(self):
        self.write("cortex/concepts/alpha.md", concept("Alpha, see [[beta]].", title="Alpha", summary="What alpha is."))
        self.write("cortex/concepts/beta.md", concept("Nothing of the word.", title="Beta", summary="What beta is."))

        def recalled(*args):
            rows = json.loads(run_brain(self.root, "recall", "alpha", "--all", *args, "--json").stdout)["results"]
            return [(r["page"], r["hop"]) for r in rows]

        both = [("cortex/concepts/alpha.md", 0), ("cortex/concepts/beta.md", 1)]
        self.assertEqual(recalled(), both)
        self.tune("spread_hops = 0")
        self.assertEqual(recalled(), both[:1])
        self.assertEqual(recalled("--hops", "1"), both)

    def test_prompt_recall_and_held_ideas(self):
        for n in ("one", "two"):
            self.write(f"cortex/concepts/spacing-{n}.md", concept("Spacing effect in practice.", title="Spacing effect",
                                                                  summary=f"Spacing, part {n}. " + "x" * 80))
        self.write("cortex/episodes/e.md", page("episode", "## Candidates\n- Spacing schedule - a plan of gaps\n"
                                                "- Spacing interval - one gap\n", **DATES))
        v = self.brain()
        self.assertEqual(v.prompt_recall("spacing effect?"), ([], "short"))
        self.assertEqual(len(v.prompt_recall("What is the spacing effect?")[0]), 2)
        other = "What does the spacing of kubernetes pods across nodes do?"
        self.assertEqual(v.prompt_recall(other), ([], "weak match (0.02)"))
        self.assertEqual(self.trying(prompt_min_words=1).prompt_recall("spacing effect?")[1], "match (1.00)")
        self.assertEqual(len(self.trying(prompt_rows=1).prompt_recall("What is the spacing effect?")[0]), 1)
        self.assertEqual(len(self.trying(prompt_chars=150).prompt_recall("What is the spacing effect?")[0]), 1)
        self.assertEqual(self.trying(prompt_coverage=0.01).prompt_recall(other)[1], "match (0.02)")  # the bar is passed
        asked = "spacing schedule interval"
        self.assertEqual([h["name"] for h in v.held_ideas(asked)], ["Spacing interval", "Spacing schedule"])
        self.assertEqual([h["name"] for h in self.trying(held_limit=1).held_ideas(asked)], ["Spacing interval"])
        self.assertEqual(self.trying(held_coverage=0.9).held_ideas(asked), [])  # each holds two of the three words

    def test_the_text_names_the_brain_s_own_numbers(self):
        for name in ("a", "b"):
            self.write(f"cortex/concepts/{name}.md", concept(f"[[{'b' if name == 'a' else 'a'}]]", title=name.upper()))
        self.tune("dormant_days = 50", "hub_min = 2", "hub_factor = 4", "schema_min = 6", "orphan_healthy = 7",
                  "bridges_exact_up_to = 1", "bridges_sample = 1", "brier_min = 7")
        out = run_brain(self.root, "introspect", "--dormant", "--graph").stdout
        for fragment in ("orphan rate     0.0%   (healthy under 7)", "dormant candidates (unlinked, unrecalled, 50+ days)",
                         "hubs (inbound >= 2 and 4x average): split candidates",
                         "bridges (highest betweenness, estimated from 1 starting pages)",
                         "schema candidates (6+ concepts no insight frames; sleep proposes one tagged schema)"):
            self.assertIn(fragment, out)
        b = {"n": 3, "score": 0.2, "enough": False, "buckets": {}}
        self.assertEqual(introspect.brier_line(b, 7), "probabilities: 3 scored, too few to judge (needs 7)")


class TryingAValue(Tuned):
    """`brain eval --set`: a value is measured on the brain's own questions before any line is written."""

    def setUp(self):
        super().setUp()
        self.write("cortex/concepts/spacing.md", concept("Study spread over days lasts.", title="Spacing effect",
                                                         summary="Longer gaps hold a memory."))
        self.write("cortex/concepts/layout.md", concept("Rows and columns of a table.", title="Layout",
                                                        summary="How a table is set out."))
        self.questions = self.write("motor/eval-questions.json", json.dumps({"today": TODAY.isoformat(), "questions": [
            {"id": "o01", "question": "What do longer gaps do for a memory?", "expect": ["spacing"]}]}))

    def run_eval(self, *args):
        return commands.call("eval", ["--root", self.root, "--questions", self.questions, *args])

    def test_the_set_is_run_with_the_value_and_nothing_is_written(self):
        with mock.patch.dict(os.environ, {"BRAIN_CACHE": "1"}):
            self.assertEqual(self.run_eval()["retrieval"]["sets"]["standard"]["recall"]["hit_at_1"], 1.0)
            cache = vault_cache.cache_path(self.root)
            self.assertTrue(os.path.exists(cache))  # a plain run of one's own set fills the search cache
            os.remove(cache)
            tried = self.run_eval("--set", "weight_summary=0", "--set", "seed_limit=3")
            # The question's words are in the summary only, so without it the page is not found: measured.
            self.assertEqual(tried["retrieval"]["sets"]["standard"]["recall"]["hit_at_1"], 0.0)
            self.assertEqual(tried["set"], {"weight_summary": {"value": 0.0, "was": 0.5},
                                            "seed_limit": {"value": 3, "was": 5}})
            self.assertFalse(os.path.exists(cache))
            self.assertFalse(os.path.exists(os.path.join(self.root, vaultlib.TUNING_PATH)))
            self.assertNotIn("set", self.run_eval())

    def test_the_report_names_what_was_tried_beside_the_brain_s_own_value(self):
        self.tune("weight_summary = 0.2", "rehearsal_days = 2, 6")
        out = run_brain(None, "eval", "--root", self.root, "--questions", self.questions, "--set", "weight_summary=0",
                        "--set", "rehearsal_days=1,4").stdout
        self.assertIn("\n  tried with weight_summary = 0.0 (the brain's own: 0.2), rehearsal_days = 1, 4 "
                      "(the brain's own: 2, 6); nothing was written\n", out)
        self.assertNotIn("tried with", run_brain(None, "eval", "--root", self.root, "--questions", self.questions).stdout)

    def test_a_trait_is_tried_the_same_way_with_everything_it_moves(self):
        # The question's words reach `layout` only weakly: an open, incautious brain lists it, a cautious one does not.
        self.write("CHARACTER.md", "# Character\n\n## Traits\n\n- caution = 0.2 (as it stands)\n")
        tried = self.run_eval("--set", "caution=1.0", "--set", "openness=0.75")
        self.assertEqual(tried["set"], {"caution": {"value": 1.0, "was": 0.2}, "openness": {"value": 0.75, "was": 0.5}})
        out = run_brain(None, "eval", "--root", self.root, "--questions", self.questions, "--set", "caution=1.0").stdout
        self.assertIn("\n  tried with caution = 1.0 (the brain's own: 0.2); nothing was written\n", out)
        with open(os.path.join(self.root, "CHARACTER.md"), encoding="utf-8") as fh:
            self.assertIn("- caution = 0.2 (as it stands)", fh.read())
        with self.assertRaises(commands.Refused) as refused:
            self.run_eval("--set", "caution=2")
        self.assertEqual(str(refused.exception), "brain eval --set: 'caution = 2' is outside 0 to 1")

    def test_a_value_that_cannot_be_tried_is_refused_and_a_baseline_is_never_saved_from_one(self):
        for args, why in ((["--set", "recal_floor=0.2"], "brain eval --set: 'recal_floor' is not a threshold (closest: "
                           "recall_floor); `brain introspect --usage` lists them"),
                          (["--set", "spread_hops=9"], "brain eval --set: 'spread_hops = 9' is outside 0 to 6"),
                          (["--set", "spread_hops"], "brain eval --set: 'spread_hops' is not name=value"),
                          (["--set", "spread_hops=1", "--save-baseline"],
                           "brain eval: --set tries a value, and a baseline holds the numbers of the brain's own "
                           "thresholds; leave one of the two out")):
            with self.subTest(args):
                with self.assertRaises(commands.Refused) as refused:
                    self.run_eval(*args)
                self.assertEqual((str(refused.exception), refused.exception.code), (why, 1))
        self.assertFalse(os.path.exists(os.path.join(self.root, "motor", "eval-questions-baseline.json")))


class Traits(Tuned):
    """A trait is a number with something to move: the thresholds the registry names for it, and nothing else."""

    def character(self, *traits, voice="- Plain and short."):
        """Write CHARACTER.md with these trait lines under `## Traits`; none leaves the section out."""
        return self.write("CHARACTER.md", "# Character\n\nWho this brain is to its owner.\n\n## Voice\n\n" + voice + "\n"
                          + ("\n## Traits\n\n" + "".join(f"- {line}\n" for line in traits) if traits else ""))

    def test_every_trait_moves_thresholds_that_exist_and_no_threshold_has_two(self):
        moved = [name for trait in vaultlib.TRAITS.values() for name, _ in trait.moves]
        self.assertEqual(len(moved), len(set(moved)))  # a value always has one reason
        self.assertNotIn("trait_span", moved)
        for name, trait in vaultlib.TRAITS.items():
            with self.subTest(name):
                self.assertTrue(trait.what and trait.moves and not trait.what.endswith("."))
                self.assertFalse(name in vaultlib.THRESHOLDS)
                for threshold, way in trait.moves:
                    self.assertIn(threshold, vaultlib.THRESHOLDS)
                    self.assertIn(way, (1, -1))
                    self.assertNotIsInstance(vaultlib.THRESHOLDS[threshold].default, tuple)  # a ladder is not scaled
                self.assertEqual(vault_tuning.moved_by({name: 0.5}, 2.0), ({}, {}))  # at 0.5 it moves nothing
                for value in (0.0, 0.1, 0.9, 1.0):  # whatever it is, what it moves stays inside its own range
                    for threshold, to in vault_tuning.moved_by({name: value}, 10.0)[0].items():
                        self.assertEqual(vault_tuning.value_of(threshold, str(to)), to)

    def test_a_trait_at_one_end_doubles_what_it_raises_and_halves_what_it_lowers(self):
        moved = lambda **traits: vault_tuning.moved_by(traits, 2.0)[0]  # noqa: E731
        self.assertEqual(moved(caution=1.0), {"min_coverage": 0.3, "recall_floor": 0.8, "held_coverage": 1.0})
        self.assertEqual(moved(caution=0.0), {"min_coverage": 0.075, "recall_floor": 0.2, "held_coverage": 0.25})
        self.assertEqual(moved(curiosity=1.0), {"held_limit": 6, "schema_min": 2})  # it lowers the second
        self.assertEqual(moved(curiosity=0.0), {"held_limit": 2, "schema_min": 8})  # 1.5 is 2: a whole number stays whole
        self.assertEqual(moved(persistence=0.75), {"dormant_days": 255, "goal_stale_days": 42, "hebbian_half_life": 127})
        self.assertEqual(moved(openness=1.0), {"spread_hops": 4, "spread_decay": 1.0, "unlinked_association": 1.0})
        self.assertEqual(moved(resilience=1.0, sensitivity=0.0),
                         {"feeling_half_life": 4, "mood_half_life": 15, "feeling_full": 6.0})
        self.assertEqual(vault_tuning.moved_by({"openness": 1.0}, 10.0)[0]["spread_hops"], 6)  # never past its range
        self.assertEqual(vault_tuning.moved_by({"caution": 1.0}, 1.0), ({}, {}))  # a span of 1: no trait moves anything
        self.assertEqual(vault_tuning.moved_by({"caution": 1.0}, 2.0)[1],
                         dict.fromkeys(("min_coverage", "recall_floor", "held_coverage"), "caution"))

    def test_a_line_is_a_trait_a_value_and_a_note_and_what_cannot_be_used_is_listed(self):
        text = "# Character\n\n## Traits\n\nHow it leans.\n\n- caution = 0.8 (2026-11-02: fewer weak pages)\n" \
               "- `openness` = `0.25`\n\n## Voice\n\n- recall_floor = 9 (prose here, not a trait)\n"
        self.assertEqual(vault_tuning.read_traits(text), ({"caution": 0.8, "openness": 0.25}, []))
        self.assertEqual(vault_tuning.read_traits("# Character\n\n## Voice\n\n- Plain.\n"), ({}, []))
        values, problems = vault_tuning.read_traits(
            "## Traits\n\n- cautoin = 0.8\n- caution = 1.5\n- openness = wide\n- recall_floor = 0.3\n"
            "- curiosity 0.7\n- persistence = 0.2\n- persistence = 0.9\n- zeal = 1\n")
        self.assertEqual(values, {"persistence": 0.9})
        self.assertEqual(problems, [
            "'cautoin' is not a trait (closest: caution); the traits are caution, curiosity, persistence, openness, "
            "resilience, sensitivity",
            "'caution = 1.5' is outside 0 to 1", "'openness = wide' is not a number",
            "'recall_floor' is a threshold, not a trait: it is set under `## Overrides` in hippocampus/tuning.md",
            "cannot read '- curiosity 0.7': a trait is `- name = value (why)`",
            "'persistence' is set twice; the later line is the one used",
            "'zeal' is not a trait; the traits are caution, curiosity, persistence, openness, resilience, sensitivity"])
        self.assertEqual(vault_tuning.character_problems(text), [])
        # And the other way: a trait among the overrides of tuning.md is sent to its own page.
        self.assertEqual(vault_tuning.tuning_problems("## Overrides\n\n- caution = 0.8\n"),
                         ["'caution' is a trait, not a threshold: it is set under `## Traits` in CHARACTER.md"])
        self.assertEqual(vault_tuning.setting("caution = 0.8"), ("caution", 0.8))
        with self.assertRaisesRegex(ValueError, "'cautoin' is not a threshold \\(closest: caution\\)"):
            vault_tuning.setting("cautoin=0.8")

    def test_a_trait_on_the_page_moves_recall_in_the_next_command_and_removing_it_moves_it_back(self):
        self.write("cortex/concepts/alpha.md", concept("Alpha alpha alpha.", title="Alpha", summary="What alpha is."))
        self.write("cortex/concepts/delta.md", concept("A long page. " + "Filler text. " * 40, title="Delta",
                                                       summary="It names alpha in passing."))

        def recalled():
            return [r["page"] for r in json.loads(run_brain(self.root, "recall", "alpha", "--json").stdout)["results"]]

        both = ["cortex/concepts/alpha.md", "cortex/concepts/delta.md"]
        self.assertEqual(recalled(), both[:1])  # delta scores 0.22 of alpha: under the floor of 0.4, cut
        self.character("caution = 0.0 (I would rather see the weak pages too)")
        self.assertEqual(recalled(), both)  # the floor is 0.2 now
        v = self.brain()
        self.assertEqual((v.tuning.recall_floor, v.tuning.min_coverage, v.tuning.traits), (0.2, 0.075, {"caution": 0.0}))
        self.assertEqual(v.tuning.changed(), {"min_coverage": 0.075, "recall_floor": 0.2, "held_coverage": 0.25})
        self.character("caution = 1.0")
        self.assertEqual(recalled(), both[:1])
        self.character()  # the page without the section: the engine's own values again
        self.assertEqual((recalled(), self.brain().tuning.changed()), (both[:1], {}))

    def test_an_override_holds_over_a_trait_and_a_value_being_tried_over_both(self):
        self.character("caution = 0.0", "openness = 1.0")
        self.tune("recall_floor = 0.6 (measured)")
        t = self.brain().tuning
        self.assertEqual((t.recall_floor, t.min_coverage, t.spread_hops), (0.6, 0.075, 4))  # the trait starts, the line stands
        self.assertEqual(t.by, {"min_coverage": "caution", "held_coverage": "caution", "spread_hops": "openness",
                                "spread_decay": "openness", "unlinked_association": "openness"})
        tried = self.trying(caution=1.0, spread_hops=1).tuning  # as `brain eval --set caution=1.0 --set spread_hops=1`
        self.assertEqual((tried.recall_floor, tried.min_coverage, tried.spread_hops, tried.traits["caution"]),
                         (0.6, 0.3, 1, 1.0))
        self.assertNotIn("spread_hops", tried.by)
        self.tune("trait_span = 1.0")  # this brain's traits move nothing
        self.assertEqual(self.brain().tuning.changed(), {"trait_span": 1.0})
        self.assertEqual(self.trying(trait_span=4.0).tuning.min_coverage, 0.0375)
        self.assertEqual(vaultlib.Tuning(self.trying(trait_span=4.0).tuning.changed()).spread_hops, 6)  # as a result carries it

    def test_check_fails_on_a_trait_it_does_not_know_and_the_page_hook_refuses_the_write(self):
        path = self.character("cautoin = 0.8", "openness = 2", "persistence = 0.9")
        r = run_brain(self.root, "check", "--json")
        report = json.loads(r.stdout)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(report["schema"], [{"page": "CHARACTER.md", "problems": [
            "'cautoin' is not a trait (closest: caution); the traits are caution, curiosity, persistence, openness, "
            "resilience, sensitivity", "'openness = 2' is outside 0 to 1"]}])
        # What could be read is in force: the pages a persistent brain keeps, kept twice as long, or nearly.
        self.assertEqual(report["tuning"], {"dormant_days": 313, "goal_stale_days": 52, "hebbian_half_life": 157})
        self.assertIn("\nschema problems: 1\n  CHARACTER.md: 'cautoin' is not a trait", run_brain(self.root, "check").stdout)

        def hook(*flags, tool="Edit", **tool_input):
            return subprocess.run([sys.executable, os.path.join(HOOKS, "validate_page.py"), *flags], text=True,
                                  input=json.dumps({"tool_name": tool, "tool_input": dict(file_path=path, **tool_input)}),
                                  capture_output=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))

        self.assertEqual(hook().returncode, 2)  # as it stands on the disk
        # A page that is already wrong can be put right a line at a time; a new wrong line is refused.
        self.assertEqual(hook("--pre", old_string="cautoin = 0.8", new_string="caution = 0.8").returncode, 0)
        bad = hook("--pre", old_string="persistence = 0.9", new_string="persistence = 9")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("Blocked before writing CHARACTER.md: 'persistence = 9' is outside 0 to 1", bad.stderr)
        self.character("caution = 0.8")
        self.assertEqual((hook().returncode, run_brain(self.root, "check").returncode), (0, 0))
        # Its prose is the owner's: no frontmatter, no summary, nothing but the traits is held to anything.
        fresh = hook("--pre", tool="Write", content="# Character\n\n## Voice\n\n- Blunt.\n")
        self.assertEqual((fresh.returncode, fresh.stderr), (0, ""))
        os.remove(path)
        self.assertEqual(json.loads(run_brain(self.root, "check", "--json").stdout)["schema"], [])

    def test_usage_lists_every_trait_and_says_which_one_moved_a_threshold(self):
        self.character("caution = 0.8 (measured)")
        self.tune("recall_floor = 0.3")
        r = json.loads(run_brain(self.root, "introspect", "--usage", "--json").stdout)["usage"]
        self.assertEqual(list(r["traits"]), list(vaultlib.TRAITS))
        self.assertEqual((r["traits"]["caution"]["value"], r["traits"]["caution"]["moves"], r["traits"]["openness"]["value"]),
                         (0.8, ["min_coverage", "recall_floor", "held_coverage"], 0.5))
        self.assertEqual([(name, row["value"], row["by"]) for name, row in r["thresholds"].items()
                          if row["value"] != row["default"]],
                         [("recall_floor", 0.3, None), ("min_coverage", 0.2274, "caution"), ("held_coverage", 0.7579, "caution")])
        text = run_brain(self.root, "introspect", "--usage").stdout
        self.assertIn("\n  min_coverage = 0.2274  (default 0.15, moved by caution; 0.0 to 1.0): recall lists nothing", text)
        self.assertIn("\n  recall_floor = 0.3  (default 0.4; 0.0 to 1.0): recall cuts rows", text)
        self.assertIn("\ntraits (0 to 1, a line under `## Traits` in CHARACTER.md; 0.5 moves nothing, and an override "
                      "holds over a trait; `brain eval --set name=value` measures one first): 6\n"
                      "  caution = 0.8  (moves min_coverage, recall_floor, held_coverage): how sure it must be", text)
        self.assertIn("\n  sensitivity = 0.5  (moves feeling_full): how much one event counts", text)
        # The briefing prints the traits with the rest of the page, so the model reads the same line the engine does.
        self.assertIn("  Traits:\n  - caution = 0.8 (measured)\n", run_brain(self.root, "character").stdout)


class TheCacheFollowsTheWeights(Tuned):
    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ, {"BRAIN_CACHE": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.write("cortex/concepts/spacing.md", concept("Study spread over days.", title="Spacing effect"))
        self.write("cortex/concepts/layout.md", concept("The spacing of rows in a table.", title="Layout"))

    def computed(self):
        """How many pages a search on a fresh Vault had to tokenize."""
        v = self.brain()
        real, calls = v._term_frequencies, []
        v._term_frequencies = lambda p: calls.append(p.rel) or real(p)
        v.search("spacing")
        v._term_cache.close()
        return len(calls)

    def test_rows_computed_under_other_weights_are_not_used(self):
        self.assertEqual((self.computed(), self.computed()), (2, 0))
        self.tune("weight_title = 6")
        self.assertEqual((self.computed(), self.computed()), (2, 0))  # every row was the old weights'
        self.assertEqual(self.brain().tuning.cache_key, "title=6.0 aliases=2.0 answers=2.0 body=1.0 summary=0.5")
        # `brain cache` opens it under the brain's own key: it reports the rows, it does not empty them.
        stats = json.loads(run_brain(self.root, "cache", "--json").stdout)
        self.assertEqual((stats["pages"], stats["version"]), (2, vault_cache.CACHE_VERSION))
        self.assertEqual(self.computed(), 0)
        self.tune("weight_title = 6", "stale_days = 20")  # a threshold search does not read: the rows stand
        self.assertEqual(self.computed(), 0)
        self.tune()
        self.assertEqual((self.computed(), self.computed()), (2, 0))  # and the default weights are a key like any other


if __name__ == "__main__":
    unittest.main()
