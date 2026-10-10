"""Learning signals: salience, rehearsal order, prediction error, probabilities, intentions, goals, structure. Run: brain test"""
import datetime
import json
import os
import subprocess
import sys

from support import DECIDED, HOOKS, TODAY, TempBrain, ago, page, run_brain, vaultlib

import vault_intentions  # noqa: E402  (support puts engine/lib on the path)


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

    def reminders(self, *lines):
        return self.write("hippocampus/intentions.md", page("intentions", "\n# Intentions\n\n## Open\n\n"
                                                            + "".join(f"- {line}\n" for line in lines)))

    def at(self, *moment):
        """The brain at a minute of a day: (2026, 10, 3, 9, 59)."""
        return vaultlib.Vault(self.root, now=datetime.datetime(*moment))

    def test_a_reminder_with_a_time_is_due_from_that_minute(self):
        self.reminders("Call DevOps when 2026-10-03 10:00", "Renew the domain when 2026-10-03")
        due = lambda v: [(i["text"], i["since"]) for i in v.due_intentions()]  # noqa: E731
        domain = ("Renew the domain", datetime.datetime(2026, 10, 3, 0, 0))  # a day alone is due from its start
        self.assertEqual(due(self.at(2026, 10, 2, 23, 59)), [])
        self.assertEqual(due(self.at(2026, 10, 3, 9, 59)), [domain])
        self.assertEqual(due(self.at(2026, 10, 3, 10, 0)), [domain, ("Call DevOps", datetime.datetime(2026, 10, 3, 10, 0))])
        # A brain given only its day stands at that day's last minute, and one given a minute knows its day.
        self.assertEqual((len(due(self.brain())), self.brain().now, self.at(2026, 10, 3, 9, 59).today),
                         (2, datetime.datetime(2026, 10, 3, 23, 59), TODAY))
        self.assertEqual(self.brain().as_of(0, today=datetime.date(2026, 10, 2)).now, datetime.datetime(2026, 10, 2, 23, 59))
        self.assertEqual(self.at(2026, 10, 3, 9, 59).as_of(0).now, datetime.datetime(2026, 10, 3, 9, 59))
        text = run_brain(self.root, "introspect", "--remind").stdout  # the clock's own day: both are long due
        self.assertIn("\nreminders due: 2\n  2026-10-03  Renew the domain\n  2026-10-03 10:00  Call DevOps\n", text)
        self.assertNotIn("reminders that repeat", text)
        self.assertNotIn("reminders closed", text)

    def test_a_repeat_is_due_again_at_the_round_after_it_was_last_done(self):
        self.reminders("Water the plants when every monday", "Stretch when every day 07:30", "Pay the rent when every month",
                       "Old habit when every friday (dropped)")
        self.log("2026-09-28 10:00 remind Water the plants -> hippocampus/intentions.md",  # added on a Monday
                 "2026-10-01 remind done pay the  RENT -> hippocampus/intentions.md",       # no time: the end of that day
                 "2026-10-01 ingest senses/a.md -> 1 episode", "2026-02-30 remind Stretch -> hippocampus/intentions.md")
        due = lambda v: [(i["text"], vault_intentions.stamp(i["since"], i["timed"])) for i in v.due_intentions()]  # noqa: E731
        # Saturday 3 October: the plants wait for Monday, the rent was paid on the 1st, and stretching, which
        # no line of the log names on a real day, was never done: its latest round is due.
        self.assertEqual(due(self.at(2026, 10, 3, 7, 0)), [("Stretch", "2026-10-02 07:30")])
        self.assertEqual(due(self.at(2026, 10, 3, 8, 0)), [("Stretch", "2026-10-03 07:30")])
        self.assertEqual(due(self.at(2026, 10, 5, 8, 0)), [("Water the plants", "2026-10-05"), ("Stretch", "2026-10-05 07:30")])
        self.assertEqual(due(self.at(2026, 11, 1, 6, 0)), [("Water the plants", "2026-10-05"), ("Stretch", "2026-10-31 07:30"),
                                                           ("Pay the rent", "2026-11-01")])
        self.assertEqual([(i["text"], vault_intentions.stamp(i["next"], i["timed"]))
                          for i in self.at(2026, 10, 3, 8, 0).repeating_intentions()],
                         [("Water the plants", "2026-10-05"), ("Stretch", "2026-10-03 07:30"), ("Pay the rent", "2026-11-01")])
        self.log("2026-09-28 10:00 remind Water the plants -> hippocampus/intentions.md",
                 "2026-10-01 remind done pay the  RENT -> hippocampus/intentions.md",
                 "2026-10-05 09:00 remind done Water the plants -> hippocampus/intentions.md",
                 "2026-10-05 07:31 remind dropped Stretch -> hippocampus/intentions.md")
        self.assertEqual(due(self.at(2026, 10, 11, 23, 59)), [("Stretch", "2026-10-06 07:30")])  # done on Monday: a week's rest
        self.assertEqual(due(self.at(2026, 10, 12, 0, 0))[0], ("Stretch", "2026-10-06 07:30"))
        self.assertEqual(due(self.at(2026, 10, 12, 0, 0))[1], ("Water the plants", "2026-10-12"))
        self.assertEqual(self.at(2026, 10, 3, 8, 0).waiting_intentions(), [])  # a repeat waits on no event
        text = run_brain(self.root, "introspect", "--remind").stdout
        self.assertIn("\nreminders that repeat: 3\n  every monday  Water the plants  (next 2026-10-12)\n", text)
        # A repeat that is due says since when; whatever the clock reads, that round is behind it.
        self.assertIn("\n  every day 07:30  Stretch  (since 2026-10-06 07:30)\n", text)

    def test_the_first_round_after_a_moment(self):
        day, at = datetime.datetime, datetime.time
        after = vault_intentions.next_round
        self.assertEqual(after(day(2026, 10, 3, 7, 0), "day", at(7, 30)), day(2026, 10, 3, 7, 30))
        self.assertEqual(after(day(2026, 10, 3, 7, 30), "day", at(7, 30)), day(2026, 10, 4, 7, 30))  # after, not at
        self.assertEqual(after(day(2026, 10, 3, 12, 0), "saturday", at(13, 0)), day(2026, 10, 3, 13, 0))
        self.assertEqual(after(day(2026, 10, 3, 12, 0), "saturday", at(9, 0)), day(2026, 10, 10, 9, 0))
        self.assertEqual(after(day(2026, 10, 3, 12, 0), "friday", at(0, 0)), day(2026, 10, 9, 0, 0))
        self.assertEqual(after(day(2026, 10, 1, 8, 0), "month", at(9, 0)), day(2026, 10, 1, 9, 0))
        self.assertEqual(after(day(2026, 12, 1, 9, 0), "month", at(9, 0)), day(2027, 1, 1, 9, 0))

    def test_a_reminder_closes_with_its_day_and_what_happened(self):
        self.reminders("Call DevOps when 2026-09-20 (done 2026-09-23: the setup was confirmed)",
                       "Send the form when 2026-09-20 (done)",
                       "Book the room when 2026-09-28 10:00 (done 2026-09-27)",
                       "Ask again when 2026-09-25 (dropped 2026-09-26: no longer needed)",
                       "Check the feed when a rival cuts prices (Done 2026-09-30 : they did)",
                       "Mend it when 2026-09-01 (done 2026-02-30: on a day that is none)",
                       "Renew the domain when 2026-10-01")
        v = self.brain()
        over = {i["text"]: (i["ended"], i["closed"], i["outcome"]) for i in v.intentions() if i["ended"]}
        self.assertEqual(over["Call DevOps"], ("done", datetime.date(2026, 9, 23), "the setup was confirmed"))
        self.assertEqual((over["Send the form"], over["Mend it"]), (("done", None, ""), ("done", None, "on a day that is none")))
        self.assertEqual(over["Ask again"], ("dropped", datetime.date(2026, 9, 26), "no longer needed"))
        self.assertEqual(over["Check the feed"], ("done", datetime.date(2026, 9, 30), "they did"))
        # Three days late, one closed a day early (0), and four with no day of its own or no date to be late for.
        self.assertEqual(v.reminder_record(), {"done": 5, "dropped": 1, "late": [0, 3]})
        self.assertEqual([i["text"] for i in v.due_intentions()], ["Renew the domain"])
        self.assertEqual(v.waiting_intentions(), [])
        text = run_brain(self.root, "introspect", "--remind").stdout
        self.assertIn("\nreminders closed: 5 done, 1 dropped; of the 2 done that say when, the middle one 3 days after it "
                      "was due, the latest 3\n", text)
        self.reminders("Send the form when 2026-09-20 (done)")
        self.assertIn("\nreminders closed: 1 done, 0 dropped\n", run_brain(self.root, "introspect", "--remind").stdout)
        self.write("OWNER.md", "# Owner\n\n## Goals\n\n- Ship it by 2026-09-01 (done 2026-09-03: shipped)\n")
        self.assertEqual([(g["text"], g["ended"]) for g in vaultlib.owner_goals(self.root)], [("Ship it", "done")])

    def test_a_when_that_could_never_come_is_a_problem_of_the_page(self):
        bad = ("A when 2026-02-30", "B when 2026-10-03 25:00", "C when 2026-10-03 at ten", "D when every fortnight",
               "E when every monday morning", "F when every test passes", "G when every day 7:75")
        path = self.reminders(*bad, "H when 2026-13-45 (dropped)", "I when everything is ready", "J when every Monday 9:05")
        with open(path, encoding="utf-8") as fh:
            problems = vault_intentions.intention_problems(fh.read())
        self.assertEqual(len(problems), len(bad))
        self.assertEqual(problems[0], "'2026-02-30' is no day: a reminder's date is YYYY-MM-DD, then HH:MM if it has a time")
        self.assertEqual(problems[1], "'2026-10-03 25:00' has no time of day after its date: HH:MM, as in 09:30")
        self.assertEqual(problems[3], "'every fortnight' is no repeat: every day, every monday (any weekday) or every "
                                      "month, then HH:MM if it has a time. An event is written another way (`when all of "
                                      "them pass`)")
        v = self.brain()
        self.assertEqual([(p.rel, len(found)) for p, found in v.schema_problems()], [("hippocampus/intentions.md", 7)])
        # Until it is put right the line waits as an event, so it is seen; the two that can be read are read.
        self.assertEqual([i["text"] for i in v.waiting_intentions()], ["A", "B", "C", "D", "E", "F", "G", "I"])
        self.assertEqual([(i["text"], i["when"], i["time"]) for i in v.repeating_intentions()],
                         [("J", "every Monday 9:05", datetime.time(9, 5))])
        self.assertEqual(run_brain(self.root, "check").returncode, 1)

        def hook(**tool_input):
            return subprocess.run([sys.executable, os.path.join(HOOKS, "validate_page.py"), "--pre"], text=True,
                                  input=json.dumps({"tool_name": "Edit", "tool_input": dict(file_path=path, **tool_input)}),
                                  capture_output=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))

        path = self.reminders("Water the plants when every monday")
        refused = hook(old_string="every monday", new_string="every other monday")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("Blocked before writing hippocampus/intentions.md: 'every other monday' is no repeat", refused.stderr)
        self.assertEqual(hook(old_string="every monday", new_string="every tuesday 08:00").returncode, 0)

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
        self.assertEqual(list(u["thresholds"]), list(vaultlib.THRESHOLDS))
        self.assertEqual(u["thresholds"]["dormant_days"], {
            "value": 180, "default": 180, "low": 1, "high": 3650,
            "what": "days unlinked, unrecalled and unedited before a page is proposed for dormant/"})
        text = run_brain(self.root, "introspect", "--usage").stdout
        self.assertIn("\n  rehearsal_days = 1, 3, 7, 14, 30, 60, 120  (1 to 3650): days until the next rehearsal", text)


class Inbox(TempBrain):
    def test_briefing_counts_waiting_notes(self):
        self.write("inbox/README.md", "about")
        self.assertNotIn("Inbox", self.run_hook("wake_up.py", {}).stdout)
        self.write("inbox/idea.txt", "a thought on the train")
        self.assertIn("Inbox: 1 notes waiting", self.run_hook("wake_up.py", {}).stdout)


if __name__ == "__main__":
    import unittest
    unittest.main()
