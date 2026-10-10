"""The round nobody watches: what is due and allowed is carried a step further, and each step is in the log. Run: brain test"""
import datetime
import json
import os
import time
from unittest import mock

from support import TempBrain, page, run_brain, vaultlib

import act  # noqa: E402  (support puts engine/lib on the path)
import commands  # noqa: E402
import index  # noqa: E402
import tend  # noqa: E402
import vault_policy  # noqa: E402
import work  # noqa: E402

DATES = dict(created="2026-01-01", updated="2026-01-01")
LISTING, WHOLE, LOOK = "keep the listing current", "see the listing is whole", "look it over"
NOT_ALLOWED = "policy: hippocampus/policy.md does not allow index"


class Worked(TempBrain):
    """A brain with one page, an index that does not list it yet, and reminders that name an action."""

    def setUp(self):
        super().setUp()
        with open(index.TEMPLATE, encoding="utf-8") as fh:
            self.write("hippocampus/index.md", fh.read())
        self.write("cortex/concepts/spacing.md", page("concept", "Study spread over days lasts.\n", title="Spacing effect",
                                                      status="established", summary="Spread study lasts.", **DATES))
        self.remind(f"{LISTING} when 2026-10-01 do `index`")
        self.allow("work", "index")

    def remind(self, *lines):
        self.write("hippocampus/intentions.md", page("intentions", "\n# Intentions\n\n## Open\n\n"
                                                     + "".join(f"- {line}\n" for line in lines), title="Intentions"))

    def allow(self, *names):
        """The policy page as the owner would write it by hand."""
        self.write(vaultlib.POLICY_PATH, page("policy", "\n# Policy\n\n## Allowed\n\n" + "".join(f"- {n}\n" for n in names),
                                              title="Policy"))

    def steps(self):
        return [e.rest for e in vaultlib.read_events(self.root) if e.op == "act"]

    def listed(self):
        with open(os.path.join(self.root, "hippocampus/index.md"), encoding="utf-8") as fh:
            return "[[spacing]]" in fh.read()

    def locked(self):
        return os.path.exists(os.path.join(self.root, work.LOCK))

    def later(self, minutes):
        return datetime.datetime.now() + datetime.timedelta(minutes=minutes)


class ARound(Worked):
    def test_what_is_due_and_allowed_is_carried_out_and_both_steps_are_in_the_log(self):
        found = work.round_of(self.root)
        self.assertEqual((found["may"], found["why"], found["busy"], found["left"]),
                         (True, "hippocampus/policy.md allows it", False, []))
        self.assertEqual([(d["text"], d["do"], len(d["steps"])) for d in found["did"]], [(LISTING, "index", 2)])
        self.assertEqual(self.steps(), [f"started {LISTING} -> a1: index, due since 2026-10-01",
                                        f"finished {LISTING} -> a1: index: 1 pages listed; added spacing"])
        self.assertTrue(self.listed())
        self.assertFalse(self.locked())
        again = work.round_of(self.root)  # done: a second round finds nothing to do, and says nothing more
        self.assertEqual((again["did"], again["left"], len(self.steps())), ([], [], 2))

    def test_the_worker_itself_runs_only_where_the_owner_s_line_allows_it(self):
        self.allow("index")  # the action, and not the worker: that line is the switch
        found = work.round_of(self.root)
        self.assertEqual((found["may"], found["did"], self.steps(), self.listed(), self.locked()), (False, [], [], False, False))
        self.assertTrue(found["why"].startswith("it changes the brain, and hippocampus/policy.md does not allow it: a line "
                                                "`- work (why)`"))
        r = run_brain(self.root, "work")
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout.splitlines()[0], r"^work, \d{4}-\d\d-\d\d: nothing was carried out: it changes the brain, "
                                                   r"and hippocampus/policy\.md does not allow it: a line `- work \(why\)`")
        self.assertIn("kinds of thing wait on the owner (`brain tend --check`)", r.stdout)
        self.allow("work", "index")
        ran = run_brain(self.root, "act", "work")  # the same round, asked for by its name
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("1 carried a step further, 0 left", ran.stdout)
        self.assertTrue(self.listed())

    def test_an_action_the_policy_does_not_allow_waits_and_is_said_once(self):
        self.allow("work")
        self.remind(f"{LISTING} when 2026-10-01 do `index`", f"{LOOK} when 2026-10-01 do `check`")
        found = work.round_of(self.root)
        self.assertEqual([(x["text"], x["why"]) for x in found["left"]], [(LISTING, "the policy does not allow it")])
        self.assertEqual(self.steps(), [f"waiting {LISTING} -> {NOT_ALLOWED}", f"started {LOOK} -> a1: check, due since 2026-10-01",
                                        f"finished {LOOK} -> a1: pages: 1"])  # one that only reads needs no line
        work.round_of(self.root)
        work.round_of(self.root)
        self.assertEqual(len(self.steps()), 3)  # found waiting again: nothing more is written
        self.allow("work", "index")  # the owner's line: the next round starts it
        work.round_of(self.root)
        self.assertEqual(self.steps()[3:], [f"started {LISTING} -> a1: index, due since 2026-10-01",
                                            f"finished {LISTING} -> a1: index: 1 pages listed; added spacing"])

    def test_a_repeat_is_carried_out_once_a_round_and_again_when_it_comes_round(self):
        self.remind(f"{LISTING} when every day do `index`")
        work.round_of(self.root)
        work.round_of(self.root)
        self.assertEqual(len(self.steps()), 2)
        work.round_of(self.root, now=self.later(24 * 60 + 5))
        self.assertEqual([s.split(" -> ")[1][:2] for s in self.steps()], ["a1", "a1", "a2", "a2"])  # no name twice
        self.assertTrue(self.steps()[3].endswith("a2: index: up to date (1 pages listed)"))


class WhatWentWrong(Worked):
    def broken(self):
        self.write("cortex/concepts/broken.md", page("concept", "See [[nowhere]].\n", title="Broken", status="established",
                                                     summary="It points nowhere.", **DATES))

    def test_what_must_hold_after_it_is_checked_and_a_failure_is_tried_again_later_and_then_left_to_the_owner(self):
        self.remind(f"{WHOLE} when 2026-10-01 do `index` until `check`")
        self.broken()
        found = work.round_of(self.root)
        self.assertEqual(self.steps(), [f"started {WHOLE} -> a1: index, due since 2026-10-01",
                                        f"failed {WHOLE} -> a1: check does not hold: pages: 2"])
        self.assertEqual(len(found["did"][0]["steps"]), 2)
        soon = work.round_of(self.root)  # the next round, minutes later: not yet
        self.assertEqual((soon["did"], len(self.steps())), ([], 2))
        self.assertRegex(soon["left"][0]["why"], r"^it is tried again after \d{4}-\d\d-\d\d \d\d:\d\d$")
        work.round_of(self.root, now=self.later(31))        # after 30 minutes
        work.round_of(self.root, now=self.later(55))        # the second wait is twice as long: not yet
        self.assertEqual(len(self.steps()), 4)
        work.round_of(self.root, now=self.later(62))
        self.assertEqual([s.split(" -> ")[0].split()[0] + " " + s.split(" -> ")[1][:2] for s in self.steps()],
                         ["started a1", "failed a1", "started a2", "failed a2", "started a3", "failed a3"])
        late = work.round_of(self.root, now=self.later(10000))  # three tries: now it is the owner's
        self.assertEqual(self.steps()[-1], f"waiting {WHOLE} -> owner: it failed 3 times; `brain work --retry` tries again")
        self.assertEqual(late["left"][0]["why"], "it waits for the owner")
        idle = work.round_of(self.root, now=self.later(20000))
        self.assertEqual((idle["left"][0]["why"], len(self.steps())),
                         ("it waits for the owner (`brain work --retry` releases it)", 7))
        os.remove(os.path.join(self.root, "cortex/concepts/broken.md"))  # put right, and released by the owner
        r = run_brain(self.root, "work", "--retry", "see", "the", "listing", "is", "whole")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([s.split(" -> ")[0].split()[0] for s in self.steps()[7:]], ["started", "finished"])
        self.assertTrue(self.steps()[7].startswith(f"started {WHOLE} -> a4: index"))

    def test_an_action_that_raises_has_an_end_in_the_log_all_the_same(self):
        for wrong, said in ((commands.Refused("the index has no markers"), "Refused: the index has no markers"),
                            (RuntimeError("it broke"), "RuntimeError: it broke")):
            with self.subTest(said):
                self.log()
                with mock.patch.object(act, "perform", side_effect=wrong):
                    work.round_of(self.root)
                self.assertEqual(self.steps(), [f"started {LISTING} -> a1: index, due since 2026-10-01",
                                                f"failed {LISTING} -> a1: {said}"])
                self.assertFalse(self.locked())

    def test_a_crash_at_each_boundary_loses_nothing_and_repeats_no_step(self):
        whole = [f"started {LISTING} -> a1: index, due since 2026-10-01",
                 f"finished {LISTING} -> a1: index: 1 pages listed; added spacing"]
        recovered = [whole[0], f"failed {LISTING} -> a1: {work.INTERRUPTED}",
                     f"started {LISTING} -> a2: index, due since 2026-10-01"]
        advance = act.advance

        def dies_at(step):
            return lambda root, text, kind, note="", now=None: (_ for _ in ()).throw(KeyboardInterrupt()) \
                if kind == step else advance(root, text, kind, note, now)

        # Before the first line is written: nothing happened, and the next round does all of it, once.
        with mock.patch.object(act, "advance", side_effect=dies_at("started")):
            with self.assertRaises(KeyboardInterrupt):
                work.round_of(self.root)
        self.assertEqual((self.steps(), self.locked(), self.listed()), ([], False, False))
        work.round_of(self.root)
        self.assertEqual(self.steps(), whole)
        # After it began, while the action ran: its outcome is not known, and the log says so.
        self.log()
        with mock.patch.object(act, "perform", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                work.round_of(self.root)
        self.assertEqual(self.steps(), whole[:1])
        work.round_of(self.root)
        self.assertEqual(self.steps()[:3], recovered)
        self.assertTrue(self.steps()[3].startswith(f"finished {LISTING} -> a2: index: "))
        self.assertEqual(len(self.steps()), 4)
        # After the action ran, before its end was written: the same, since the log cannot tell the two apart.
        self.log()
        with mock.patch.object(act, "advance", side_effect=dies_at("finished")):
            with self.assertRaises(KeyboardInterrupt):
                work.round_of(self.root)
        self.assertEqual(self.steps(), whole[:1])
        work.round_of(self.root)
        self.assertEqual((self.steps()[:3], len(self.steps())), (recovered, 4))
        # After its end was written: nothing is left to do.
        work.round_of(self.root)
        self.assertEqual(len(self.steps()), 4)

    def test_an_action_that_may_not_run_twice_waits_for_the_owner_after_an_interruption(self):
        once = vault_policy.ACTIONS["index"]._replace(again=False)
        with mock.patch.dict(vault_policy.ACTIONS, {"index": once}):
            with mock.patch.object(act, "perform", side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):
                    work.round_of(self.root)
            found = work.round_of(self.root)
            self.assertEqual(self.steps()[1:], [
                f"failed {LISTING} -> a1: {work.INTERRUPTED}",
                f"waiting {LISTING} -> owner: interrupted, and `index` is not run twice unasked; `brain work --retry` "
                "runs it"])
            self.assertEqual((found["left"][0]["why"], self.listed()), ("it waits for the owner", False))
            work.round_of(self.root)
            self.assertEqual(len(self.steps()), 3)  # never taken as not done: it is not run again unasked
            work.round_of(self.root, retry=LISTING)  # the owner's word
            self.assertTrue(self.steps()[3].startswith(f"started {LISTING} -> a2: index"))
            self.assertTrue(self.listed())


class ItsLimits(Worked):
    def test_one_round_runs_for_a_brain_and_a_lock_left_by_a_dead_one_is_taken_over(self):
        lock = os.path.join(self.root, work.LOCK)
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        with open(lock, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))  # a round that is running: this very process
        busy = work.round_of(self.root)
        self.assertEqual((busy["busy"], busy["did"], self.steps(), self.locked()), (True, [], [], True))
        self.assertIn("another round is running for this brain", run_brain(self.root, "work").stdout)
        old = time.time() - 2 * 10 * 60 - 5  # far past the time a round may take
        os.utime(lock, (old, old))
        self.assertFalse(work.round_of(self.root)["busy"])
        self.assertEqual(len(self.steps()), 2)
        self.log()
        for holder in ("999999999", "", "0", "not a number", str(10 ** 30)):  # a process that is gone, or none
            with self.subTest(holder):
                with open(lock, "w", encoding="utf-8") as fh:
                    fh.write(holder)
                self.assertTrue(work.take(self.root, 10))
                os.remove(lock)
        self.assertTrue(work.alive(os.getpid()))
        with mock.patch.object(os, "kill", side_effect=PermissionError()):  # it is there, and another user's
            self.assertTrue(work.alive(4242))
        with mock.patch.object(os, "open", side_effect=FileExistsError()):  # taken again before this one could
            with open(lock, "w", encoding="utf-8") as fh:
                fh.write("0")
            self.assertFalse(work.take(self.root, 10))

    def test_a_round_has_a_budget_of_steps_and_of_minutes(self):
        self.remind(f"{LISTING} when 2026-10-01 do `index`", f"{LOOK} when 2026-10-01 do `check`",
                    "feel it when 2026-10-01 do `feel`")
        self.write(vaultlib.TUNING_PATH, page("tuning", "\n## Overrides\n\n- work_steps = 2\n", title="Tuning"))
        found = work.round_of(self.root)
        self.assertEqual(([d["text"] for d in found["did"]], [(x["text"], x["why"]) for x in found["left"]]),
                         ([LISTING, LOOK], [("feel it", "the round's budget is spent")]))
        self.log()
        clock = iter([0.0, 0.0, 601.0, 601.0, 601.0])  # ten minutes pass while the first one runs
        with mock.patch.object(work.time, "monotonic", side_effect=lambda: next(clock)):
            late = work.round_of(self.root)
        self.assertEqual(([d["text"] for d in late["did"]], [x["why"] for x in late["left"]]),
                         ([LISTING], ["the round's budget is spent"] * 2))

    def test_a_dry_run_says_what_a_round_would_do_and_writes_nothing(self):
        self.remind(f"{LISTING} when 2026-10-01 do `index`", f"{WHOLE} when 2026-10-01 do `snapshot`")
        self.log(f"2026-10-02 09:00 act started {WHOLE} -> a1: snapshot, due since 2026-10-01")  # one left half done
        before = self.steps()
        found = work.round_of(self.root, dry=True)
        self.assertEqual([(d["text"], d["steps"]) for d in found["did"]], [
            (LISTING, ["would be started: index, due since 2026-10-01"]),
            (WHOLE, [f"would be failed: {work.INTERRUPTED}",
                     "would be waiting: policy: hippocampus/policy.md does not allow snapshot"])])
        self.assertEqual((self.steps(), self.listed(), self.locked()), (before, False, False))
        text = run_brain(self.root, "work", "--dry-run").stdout.splitlines()
        self.assertRegex(text[0], r"^work, \d{4}-\d\d-\d\d: 2 carried a step further, 1 left \(a dry run: nothing was written\)$")
        self.assertEqual(text[1:3], [f"  {LISTING} (index)", "      would be started: index, due since 2026-10-01"])
        self.assertIn(f"  left: {WHOLE} (snapshot): the policy does not allow it", text)

    def test_the_owner_s_retry_names_one_reminder_that_is_due(self):
        self.remind(f"{LISTING} when 2026-10-01 do `index`", "take the numbers when 2099-01-01 do `snapshot`",
                    "call the supplier when 2026-10-01")
        for said in ("take the numbers", "call the supplier", "no such thing"):
            with self.assertRaises(commands.Refused) as refused:
                work.round_of(self.root, retry=said)
            self.assertEqual(str(refused.exception), f"brain work: no reminder with an action that is due says '{said}' "
                                                     "(`brain introspect --remind` lists them)")
        self.assertEqual(run_brain(self.root, "work", "--retry", "no", "such", "thing").returncode, 1)
        self.assertEqual(len(work.round_of(self.root, retry="KEEP the listing  current")["did"]), 1)

    def test_then_it_says_what_waits_as_the_digest_does(self):
        self.remind(f"{LISTING} when 2026-10-01 do `index`", "call the supplier when 2026-10-01")
        with mock.patch.object(tend, "show", return_value=True) as shown:
            found = commands.call("work", ["--notify"], root=self.root)
        self.assertEqual((len(found["did"]), found["needs"], len(found["notified"]), shown.call_count), (1, 2, 1, 1))
        self.assertIn("reminders due 1", found["notified"][0])  # the one it carried out no longer waits
        quiet = commands.call("work", [], root=self.root)
        self.assertEqual((quiet["notified"], quiet["did"]), ([], []))
        json.dumps(quiet)
        self.remind()
        os.remove(os.path.join(self.root, "cortex/concepts/spacing.md"))
        self.assertEqual(run_brain(self.root, "work").stdout.splitlines()[-1], "  nothing waits on the owner")
