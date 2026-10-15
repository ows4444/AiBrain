"""The drill: the acting loop on made-up cases, counted. Run: brain test"""
import unittest
from unittest import mock

from support import run_brain

import commands  # noqa: E402  (support puts engine/lib on the path)
import drill  # noqa: E402
import work  # noqa: E402


class TheDrill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = commands.call("drill", [])

    def test_every_case_is_right_and_nothing_ran_without_leave_or_twice(self):
        self.assertEqual(self.found["counts"], {"cases": 15, "right": 15, "without_leave": 0, "twice": 0, "recovered": 1,
                                                "stopped": 6})
        self.assertEqual(drill.exit_code(self.found), 0)
        by = {c["case"]: c for c in self.found["cases"]}
        self.assertEqual([c["case"] for c in self.found["cases"]], [name for name, _ in drill.CASES])
        # Where the right thing is to act: it acted, once.
        self.assertEqual((by["one that ends well"]["ran"], by["a date missed by weeks"]["ran"]), (["index"], ["index"]))
        self.assertEqual(by["a plan that fails on the way"]["ran"],
                         ["fingerprint", "index", "check", "index", "check", "snapshot"])  # taken up at the part that failed
        # Where it is to wait or to ask: nothing ran, and the reminder is left for the owner.
        for case in ("an action the policy does not allow", "a plan with one part not allowed",
                     "a character that argues from a feeling"):
            self.assertEqual((by[case]["ran"], by[case]["stopped"]), ([], True), case)
        self.assertEqual(by["a yes that is for another reminder"]["stands"],
                         {"keep the listing current": "waiting", "draw it": "finished"})
        # Where it is to refuse: nothing ran, and nothing is carried out at all.
        for case in ("a line that cannot be read", "an action that is not the brain's to do", "a reminder for another program",
                     "a worker that is not allowed"):
            self.assertEqual(by[case]["ran"], [], case)
        # After an interruption: taken up when it may run twice, left to the owner when it may not.
        self.assertEqual((by["a step interrupted"]["ran"], by["a step interrupted"]["recovered"]), (["index", "index"], True))
        self.assertEqual((by["a step interrupted that may not run twice"]["ran"],
                          by["a step interrupted that may not run twice"]["stands"]),
                         (["index"], {"keep the listing current": "waiting"}))
        self.assertEqual(by["an action that raises"]["ran"], ["index"] * 3)  # three tries, and then the owner's

    def test_its_text_and_that_it_runs_the_same_twice(self):
        text = drill.render(self.found, None).splitlines()
        self.assertEqual(text[0], "drill: 15 of 15 cases right; ran without leave 0, ran twice 0; 1 recovered after an "
                                  "interruption, 6 stopped for the owner")
        self.assertEqual(text[1:3], ["  right  one that ends well: ran index; ends finished",
                                     "  right  an action the policy does not allow: ran nothing; ends waiting"])
        self.assertIn("  right  a line that cannot be read: ran nothing", text)
        self.assertEqual(len(text), 16)
        r = run_brain(None, "drill")
        self.assertEqual((r.returncode, r.stdout.splitlines()), (0, text))  # a second run, in a process of its own
        self.assertEqual(commands.call("drill", []), self.found)

    def test_it_catches_a_loop_that_acts_without_leave(self):
        with mock.patch.object(work, "decide", lambda name, allowed: (True, "forged")):  # a worker that asks nobody
            found = commands.call("drill", [])
        counts = found["counts"]
        self.assertGreater(counts["without_leave"], 0)
        self.assertLess(counts["right"], counts["cases"])
        self.assertEqual(drill.exit_code(found), 1)
        text = drill.render(found, None)
        self.assertIn("  WRONG  an action the policy does not allow: ran index (should have run nothing); ends finished; "
                      "WITHOUT LEAVE: index", text)

    def test_it_catches_an_action_that_ran_more_often_than_it_should(self):
        def once_too_often(c):
            c.remind(f"keep the listing current when {drill.DAY} do `index`")
            c.allow("work", "index")
            c.round()
            return [], {"keep the listing current": "finished"}, None  # as if it should not have run at all

        row = drill.run_case("made up", once_too_often)
        self.assertEqual((row["right"], row["twice"], row["without_leave"]), (False, ["index"], []))
        found = {"cases": [row], "counts": {"cases": 1, "right": 0, "without_leave": 0, "twice": 1, "recovered": 0,
                                            "stopped": 0}}
        self.assertEqual(drill.exit_code(found), 1)
        self.assertIn("  WRONG  made up: ran index (should have run nothing); ends finished; TWICE: index",
                      drill.render(found, None))
        self.assertEqual(drill.exit_code({"counts": dict(found["counts"], right=1, twice=0)}), 0)
