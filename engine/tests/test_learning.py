"""Learning signals: salience, rehearsal order, prediction error, probabilities, intentions, goals, structure. Run: brain test"""
import json

from support import DECIDED, TempBrain, ago, page, run_brain, vaultlib


def concept(body="", **fields):
    return page("concept", body, **dict(dict(status="established", created=ago(300), updated=ago(300)), **fields))


class Salience(TempBrain):
    def test_levels_protect_and_stretch_fading(self):
        old = ago(250)  # past 180 days, short of 180 x 1.5 = 270
        for name, s in (("plain", None), ("two", "2"), ("four", "4"), ("high", "high")):
            fields = dict(updated=old, created=old) if s is None else dict(updated=old, created=old, salience=s)
            self.write(f"cortex/concepts/{name}.md", concept(**fields))
        v = self.brain()
        self.assertEqual([(p.stem, p.salience) for p in sorted(v.knowledge, key=lambda p: p.stem)],
                         [("four", 4), ("high", 5), ("plain", 0), ("two", 2)])
        self.assertEqual([p.stem for p in v.dormant_candidates()], ["plain"])  # two waits until 360 days
        self.assertEqual(v.fade_days(v.resolve("two")), 360)
        self.assertEqual(vaultlib.schema_problems(page("concept", **dict(DECIDED, status="emerging", salience="6"))),
                         ["'salience' must be one of high, 1, 2, 3, 4, 5, or absent"])

    def test_salient_candidate_is_marked(self):
        self.write("cortex/episodes/e.md", page("episode", "## Candidates\n- Big idea - x\n", salience="4"))
        self.assertTrue(self.brain().candidate_tally()[0]["salient"])


class RehearsalOrder(TempBrain):
    def test_an_edit_does_not_move_the_rehearsal_clock(self):
        # F2: CLAUDE.md says only /rehearse moves it. Sleep editing a page today must not hide it.
        self.write("cortex/concepts/edited.md", concept(created=ago(60), updated=ago(0)))
        self.log(f"{ago(40)} recall rehearse -> [[edited]]")
        v = self.brain()
        self.assertEqual(v.last_rehearsed(v.resolve("edited")), v.today - __import__("datetime").timedelta(days=40))
        self.assertEqual([p.stem for p in v.due_for_rehearsal()], ["edited"])

    def test_never_rehearsed_pages_start_from_creation(self):
        self.write("cortex/concepts/new.md", concept(created=ago(0), updated=ago(0)))
        self.write("cortex/concepts/old.md", concept(created=ago(5), updated=ago(0)))
        self.assertEqual([p.stem for p in self.brain().due_for_rehearsal()], ["old"])

    def test_salience_then_misses_then_overdue(self):
        for name in ("calm", "missed", "salient"):
            self.write(f"cortex/concepts/{name}.md", concept(created=ago(100), salience="3" if name == "salient" else "1"))
        self.log(*[f"{ago(n)} rehearse missed -> [[missed]]" for n in (30, 20, 10)])
        v = self.brain()
        self.assertEqual([p.stem for p in v.due_for_rehearsal()], ["salient", "missed", "calm"])
        self.assertEqual(v.miss_risk(v.resolve("missed")), (0.8, 3))
        r = run_brain(self.root, "introspect", "--due")
        self.assertIn("misses 80% of 3", r.stdout)


class PredictionError(TempBrain):
    def test_new_input_against_a_page_is_queued_and_briefed(self):
        self.write("cortex/concepts/spacing.md", concept(title="Spacing"))
        self.write("cortex/episodes/blog.md", page("episode", "Spacing is a myth (contradicts:: [[spacing]]).",
                                                   created=ago(1)))
        self.write("cortex/episodes/old.md", page("episode", "(contradicts:: [[spacing]])", consolidated=ago(5)))
        v = self.brain()
        self.assertEqual([(a.stem, b.stem) for a, b in v.contradiction_queue()], [("blog", "spacing")])
        out = self.run_hook("wake_up.py", {}).stdout
        self.assertIn("Prediction errors: 1 new inputs contradict a page (blog vs spacing)", out)
        stats = json.loads(run_brain(self.root, "introspect", "--json").stdout)
        self.assertEqual(stats["contradictions"], [{"episode": "cortex/episodes/blog.md",
                                                    "page": "cortex/concepts/spacing.md", "status": "established"}])


REVIEWED = """## Expected
- [hypothesis 70%] Churn stays under 5%.
- [assumption 90%] The price holds.
## Decision
- [decision] Raise it.
## Outcome
- [hypothesis] Churn stays under 5%. -> held
- [assumption 90%] The price holds. -> failed
"""


class Probabilities(TempBrain):
    def decision(self, slug, body, tags=None, outcome="better"):
        fields = dict(DECIDED, status="reviewed", review="2026-01-01", revisit_if="x", outcome=outcome)
        if tags:
            fields["tags"] = tags
        self.write(f"cortex/decisions/{slug}.md", page("decision", body, **fields))

    def test_probability_lives_inside_the_tag(self):
        claims = vaultlib.claims_in(REVIEWED + "## Options\n- [observation] 70% of teams quit. [[x]]\n")
        self.assertEqual([(c["tag"], c["p"]) for c in claims if c["section"] == "Expected"],
                         [("hypothesis", 0.7), ("assumption", 0.9)])
        self.assertEqual(claims[-1]["p"], None)  # a claim that starts with a number is not a probability
        bad = vaultlib.claim_problems("## Options\n- [observation 70%] Seen. [[x]]\n## Expected\n- [hypothesis 150%] y\n")
        self.assertTrue(any("only a hypothesis or assumption" in p for p in bad))
        self.assertTrue(any("0-100%" in p for p in bad))

    def test_brier_and_reference_class(self):
        self.decision("raise", REVIEWED, tags="[unverified]")
        v = self.brain()
        b = v.brier()
        # held at 70% (0.09) and failed at 90% (0.81): mean 0.45; the Outcome line inherits 70% from Expected
        self.assertEqual((b["n"], b["score"], b["enough"]), (2, 0.45, False))
        self.assertEqual(b["buckets"], {"70%": {"n": 1, "held": 1}, "90%": {"n": 1, "held": 0}})
        self.assertEqual(v.reference_class()["unverified"]["outcomes"], {"better": 1})
        text = run_brain(self.root, "introspect", "--decisions").stdout
        self.assertIn("probabilities: 2 scored, too few to judge (needs 10)", text)

    def test_enough_guesses_get_a_score(self):
        for i in range(5):
            self.decision(f"d{i}", REVIEWED)
        b = self.brain().brier()
        self.assertEqual((b["n"], b["enough"]), (10, True))


class Intentions(TempBrain):
    def test_dated_and_event_reminders(self):
        self.write("hippocampus/intentions.md", page("intentions", "\n## Open\n\n"
                                                    f"- Renew the domain when {ago(1)}\n"
                                                    f"- Call the bank when {ago(3)} (done)\n"
                                                    "- Revisit pricing when a rival cuts prices\n"
                                                    "- Not an intention line\n"))
        v = self.brain()
        self.assertEqual([i["text"] for i in v.due_intentions()], ["Renew the domain"])
        self.assertEqual([i["event"] for i in v.waiting_intentions()], ["a rival cuts prices"])
        self.assertIn("Reminders: 1 due (Renew the domain)", self.run_hook("wake_up.py", {}).stdout)
        text = run_brain(self.root, "introspect", "--remind").stdout
        self.assertIn("a rival cuts prices", text)

    def test_intentions_type_only_at_its_path(self):
        self.write("cortex/concepts/sneaky.md", page("intentions", "- x when 2020-01-01\n"))
        v = self.brain()
        self.assertEqual(v.due_intentions(), [])
        self.assertIn("cortex/concepts/sneaky.md", [p.rel for p, _ in v.schema_problems()])


class GoalSlip(TempBrain):
    def owner(self, due):
        self.write("CLAUDE.md", f"# B\n\n## Owner\n\n### Goals\n\n- Ship by {due} -> [[plan]]\n\n## Tags\n\n`disputed`\n")

    def test_a_goal_due_soon_with_no_activity_is_at_risk(self):
        self.owner(ago(-20))
        self.write("cortex/concepts/plan.md", concept(updated=ago(60)))
        v = self.brain()
        self.assertEqual((v.goal_report()[0]["activity"], v.goal_report()[0]["at_risk"]), (0, True))
        self.log(f"{ago(2)} recall how is the plan -> [[plan]]")
        self.assertFalse(self.brain().goal_report()[0]["at_risk"])

    def test_briefing_names_a_slipping_goal(self):
        import datetime
        real = datetime.date.today()  # the hook runs on the clock, not on the tests' fixed date
        self.owner((real + datetime.timedelta(days=20)).isoformat())
        self.write("cortex/concepts/plan.md", concept(created="2020-01-01", updated="2020-01-01"))
        self.assertIn("1 due soon with nothing done lately (Ship)", self.run_hook("wake_up.py", {}).stdout)

    def test_a_distant_goal_is_not_at_risk(self):
        self.owner(ago(-200))
        self.write("cortex/concepts/plan.md", concept(updated=ago(60)))
        self.assertFalse(self.brain().goal_report()[0]["at_risk"])


class Structure(TempBrain):
    def test_near_duplicates_by_name_and_by_neighbours(self):
        self.write("cortex/concepts/spaced-repetition.md", concept(title="Spaced repetition"))
        self.write("cortex/concepts/spacing-repetitions.md", concept(title="Spacing repetitions"))
        for x in ("a", "b", "c", "d"):
            self.write(f"cortex/entities/{x}.md", page("entity", "[[left]] [[right]]" if x != "d" else ""))
        self.write("cortex/concepts/left.md", concept("[[a]] [[b]] [[c]]", title="Left"))
        self.write("cortex/concepts/right.md", concept("[[a]] [[b]] [[c]]", title="Right"))
        self.write("cortex/episodes/e1.md", page("episode", title="Spaced repetition"))  # records never merge
        pairs = {(a.stem, b.stem): why for a, b, _, why in self.brain().near_duplicates()}
        self.assertIn(("spaced-repetition", "spacing-repetitions"), pairs)
        self.assertIn(("left", "right"), pairs)
        self.assertIn("3 neighbours shared", pairs[("left", "right")])
        self.assertFalse(any("e1" in pair for pair in pairs))
        r = run_brain(self.root, "check", "--json")
        self.assertEqual(len(json.loads(r.stdout)["near_duplicates"]), len(pairs))

    def test_schema_candidates(self):
        names = [f"c{i}" for i in range(5)]
        for n in names:  # a dense cluster of five concepts
            self.write(f"cortex/concepts/{n}.md", concept(" ".join(f"[[{m}]]" for m in names if m != n)))
        self.assertEqual(len(self.brain().schema_candidates()), 1)
        self.write("cortex/insights/frame.md", page("insight", "[[c0]] [[c1]] [[c2]]"))
        self.assertEqual(self.brain().schema_candidates(), [])

    def test_usage_lists_every_threshold(self):
        u = self.brain().usage()
        self.assertEqual(u["thresholds"]["dormant_days"], vaultlib.DORMANT_DAYS)
        self.assertIn("hebbian_half_life", u["thresholds"])
        text = run_brain(self.root, "introspect", "--usage").stdout
        self.assertIn("rehearsal_days = [1, 3, 7, 14, 30, 60, 120]", text)


class Inbox(TempBrain):
    def test_briefing_counts_waiting_notes(self):
        self.write("inbox/README.md", "about")
        self.assertNotIn("Inbox", self.run_hook("wake_up.py", {}).stdout)
        self.write("inbox/idea.txt", "a thought on the train")
        self.assertIn("Inbox: 1 notes waiting", self.run_hook("wake_up.py", {}).stdout)


if __name__ == "__main__":
    import unittest
    unittest.main()
