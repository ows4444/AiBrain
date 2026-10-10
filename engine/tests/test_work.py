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


def named(text, do, until=None, when="2026-10-01", started=0):
    """The name a reminder goes by while it waits: what the owner's yes must say."""
    return vaultlib.proposal(text, do, until, when, started)


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

    def allow(self, *names, once=()):
        """The policy page as the owner would write it by hand: what may always run, and a yes for this once."""
        self.write(vaultlib.POLICY_PATH, page("policy", "\n# Policy\n\n## Allowed\n\n" + "".join(f"- {n}\n" for n in names)
                                              + "\n## Once\n\n" + "".join(f"- {line}\n" for line in once), title="Policy"))

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
        name = named(LISTING, "index")
        self.assertEqual([(x["text"], x["why"]) for x in found["left"]],
                         [(LISTING, f"the policy does not allow it (yes {name})")])
        self.assertEqual(self.steps(), [f"waiting {LISTING} -> {NOT_ALLOWED}; yes {name}",
                                        f"started {LOOK} -> a1: check, due since 2026-10-01",
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
        name = named(WHOLE, "index", "check", started=3)
        self.assertEqual(self.steps()[-1], f"waiting {WHOLE} -> owner: it failed 3 times; yes {name}")
        self.assertEqual(late["left"][0]["why"], "it waits for the owner")
        idle = work.round_of(self.root, now=self.later(20000))
        self.assertEqual((idle["left"][0]["why"], len(self.steps())),
                         (f"it waits for the owner (yes {name}, or `brain work --retry`)", 7))
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
                f"waiting {LISTING} -> owner: interrupted, and `index` is not run twice unasked; yes "
                + named(LISTING, "index", started=1)])
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
                     "would be waiting: policy: hippocampus/policy.md does not allow snapshot; yes "
                     + named(WHOLE, "snapshot", started=1)])])
        self.assertEqual((self.steps(), self.listed(), self.locked()), (before, False, False))
        text = run_brain(self.root, "work", "--dry-run").stdout.splitlines()
        self.assertRegex(text[0], r"^work, \d{4}-\d\d-\d\d: 2 carried a step further, 1 left \(a dry run: nothing was written\)$")
        self.assertEqual(text[1:3], [f"  {LISTING} (index)", "      would be started: index, due since 2026-10-01"])
        self.assertIn(f"  left: {WHOLE} (snapshot): the policy does not allow it (yes {named(WHOLE, 'snapshot', started=1)})",
                      text)

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


class TheOwnersYes(Worked):
    """A reminder that waits is a proposal with a name; a yes is for that name, once, and for a few days."""

    def setUp(self):
        super().setUp()
        self.today = datetime.date.today()
        self.remind(f"{LISTING} when 2026-10-01 do `index`", f"{WHOLE} when 2026-10-01 do `graph`")
        self.allow("work")
        work.round_of(self.root)  # neither action is allowed: both wait, each under its own name
        self.listing, self.whole = named(LISTING, "index"), named(WHOLE, "graph")

    def yes(self, name, days_ago=0):
        return f"{name} {(self.today - datetime.timedelta(days=days_ago)).isoformat()} (just this time)"

    def test_what_waits_is_shown_with_the_name_the_yes_must_say(self):
        self.assertEqual(self.steps(), [f"waiting {LISTING} -> {NOT_ALLOWED}; yes {self.listing}",
                                        f"waiting {WHOLE} -> policy: hippocampus/policy.md does not allow graph; yes {self.whole}"])
        self.assertNotEqual(self.listing, self.whole)
        found = tend.digest(vaultlib.Vault(self.root))
        self.assertEqual(found["proposals"], [
            {"text": LISTING, "do": "index", "why": f"{NOT_ALLOWED}; yes {self.listing}", "yes": self.listing},
            {"text": WHOLE, "do": "graph", "why": f"policy: hippocampus/policy.md does not allow graph; yes {self.whole}",
             "yes": self.whole}])
        line = [row for row in tend.render(found, None).splitlines() if "wait for a yes" in row][0]
        self.assertEqual(line, f"  wait for a yes    2: {LISTING} (do index; yes {self.listing}), {WHOLE} (do graph; yes "
                               f"{self.whole})  (yours alone: `- <yes> <today>` under `## Once` in hippocampus/policy.md runs "
                               "one once)")
        briefing = self.run_hook("wake_up.py", {}).stdout
        self.assertIn(f"Your yes: 2 wait for it ({LISTING}: do index, yes {self.listing}; {WHOLE}: do graph, yes "
                      f"{self.whole}): written by you in hippocampus/policy.md, `- <yes> <today>` under `## Once` for this "
                      "once, `- <action>` under `## Allowed` for always", briefing)

    def test_a_yes_runs_that_one_reminder_once_and_no_other(self):
        self.allow("work", once=[self.yes(self.listing)])
        found = work.round_of(self.root)
        self.assertEqual([d["text"] for d in found["did"]], [LISTING])  # the other still waits: the yes is not for it
        self.assertEqual(self.steps()[2:], [
            f"started {LISTING} -> a1: index, due since 2026-10-01, by the owner's yes {self.listing}",
            f"finished {LISTING} -> a1: index: 1 pages listed; added spacing"])
        self.assertEqual([p["text"] for p in vaultlib.Vault(self.root).proposals()], [WHOLE])
        listing = commands.call("act", [], root=self.root)["once"]
        self.assertEqual(listing, [{"yes": self.listing, "day": self.today.isoformat(), "for": None, "holds": False}])
        self.assertIn(f"yes {self.listing} of {self.today.isoformat()}: names nothing that waits now (used, or its reminder "
                      "changed)", run_brain(self.root, "act").stdout)

    def test_a_yes_is_spent_once_the_reminder_has_started(self):
        self.remind(f"{LISTING} when every day do `index`")
        self.log()
        work.round_of(self.root)  # it waits, under the name of a reminder never started
        first = named(LISTING, "index", when="every day")
        self.allow("work", once=[self.yes(first)])
        work.round_of(self.root)
        self.assertEqual([s.split(" -> ")[0].split()[0] for s in self.steps()], ["waiting", "started", "finished"])
        tomorrow = self.later(24 * 60 + 5)
        again = work.round_of(self.root, now=tomorrow)  # the next round: not allowed still, and the old yes is of no use
        second = named(LISTING, "index", when="every day", started=1)
        self.assertNotEqual(first, second)
        self.assertEqual(self.steps()[3], f"waiting {LISTING} -> {NOT_ALLOWED}; yes {second}")
        self.assertEqual(again["left"][0]["why"], f"the policy does not allow it (yes {second})")

    def test_a_yes_does_not_hold_for_the_same_reminder_changed(self):
        for changed in (f"{LISTING} when 2026-10-01 do `graph`", f"{LISTING} when 2026-10-01 do `index` until `check`",
                        f"{LISTING} when 2026-10-02 do `index`", f"{LISTING} now when 2026-10-01 do `index`"):
            with self.subTest(changed):
                self.remind(changed)
                self.log(f"2026-10-02 09:00 act waiting {changed.split(' when ')[0]} -> policy: it waits")
                self.allow("work", once=[self.yes(self.listing)])
                found = work.round_of(self.root)
                self.assertEqual((found["did"], len(self.steps())), ([], 1))
        self.assertNotEqual(named("a", "index", "check"), named("a", "index"))
        self.assertRegex(self.listing, r"^[0-9a-f]{7}$")

    def test_a_yes_lapses_and_one_dated_ahead_does_not_count_yet(self):
        for days_ago, holds in ((8, False), (-1, False), (7, True)):
            with self.subTest(days_ago):
                self.allow("work", once=[self.yes(self.listing, days_ago)])
                before = len(self.steps())
                work.round_of(self.root)
                self.assertEqual(len(self.steps()) - before, 2 if holds else 0)
                if not holds and days_ago > 0:
                    self.assertEqual(commands.call("act", [], root=self.root)["once"][0],
                                     {"yes": self.listing, "day": (self.today - datetime.timedelta(days=8)).isoformat(),
                                      "for": LISTING, "holds": False})
                    self.assertIn(f"`{LISTING}` waits, and this yes has lapsed", run_brain(self.root, "act").stdout)
        self.write(vaultlib.TUNING_PATH, page("tuning", "\n## Overrides\n\n- yes_days = 30\n", title="Tuning"))
        self.allow("work", once=[self.yes(self.whole, 20)])
        self.assertIn(f"yes {self.whole} of ", run_brain(self.root, "act").stdout)
        self.assertEqual([d["text"] for d in work.round_of(self.root)["did"]], [WHOLE])

    def test_one_that_failed_too_often_is_released_by_a_yes_too_and_one_given_early_counts(self):
        self.remind(f"{LOOK} when 2026-10-01 do `index` until `check`")
        self.allow("work", "index")
        self.write("cortex/concepts/broken.md", page("concept", "See [[nowhere]].\n", title="Broken", status="established",
                                                     summary="It points nowhere.", **DATES))
        self.log(*[f"2026-10-0{n} 09:00 act {step} {LOOK} -> a{n}: x" for n in (1, 2, 3) for step in ("started", "failed")])
        work.round_of(self.root)
        name = named(LOOK, "index", "check", started=3)
        self.assertEqual(self.steps()[-1], f"waiting {LOOK} -> owner: it failed 3 times; yes {name}")
        os.remove(os.path.join(self.root, "cortex/concepts/broken.md"))
        self.allow("work", "index", once=[self.yes(name)])
        work.round_of(self.root)
        self.assertEqual([s.split(" -> ")[0].split()[0] for s in self.steps()[-2:]], ["started", "finished"])
        self.assertTrue(self.steps()[-2].endswith(f"by the owner's yes {name}"))
        # A yes written before the reminder was ever found waiting holds as well: the name is the same.
        self.remind(f"{WHOLE} when 2026-10-01 do `graph`")
        self.log()
        self.allow("work", once=[self.yes(self.whole)])
        work.round_of(self.root)
        self.assertEqual([s.split(" -> ")[0].split()[0] for s in self.steps()], ["started", "finished"])

    def test_a_yes_that_cannot_be_read_is_a_problem_of_the_page_and_counts_for_nothing(self):
        self.allow("work", once=[f"{self.listing}", "3f9a2c 2026-10-12", f"{self.whole} 2026-02-30", "yes please",
                                 f"`{self.whole}` {self.today.isoformat()}"])
        r = run_brain(self.root, "check", "--json")
        self.assertEqual(r.returncode, 1)
        wrong = "a yes is `- <the proposal's name> YYYY-MM-DD (why)`, the name as `brain tend --check` gives it and the " \
                "day you write it"
        self.assertEqual(json.loads(r.stdout)["schema"], [{"page": "hippocampus/policy.md", "problems": [
            f"cannot read '- {self.listing}': {wrong}", f"cannot read '- 3f9a2c 2026-10-12': {wrong}",
            f"cannot read '- {self.whole} 2026-02-30': {wrong}", f"cannot read '- yes please': {wrong}"]}])
        self.assertEqual(vaultlib.yes_of(self.root, self.today, 7), frozenset({self.whole}))  # the one line that reads
        self.assertEqual(vaultlib.yes_of(os.path.join(self.root, "no-brain"), self.today, 7), frozenset())
        self.assertEqual(vaultlib.read_once("# Policy\n\n## Once\n\nProse here.\n"), ([], []))
