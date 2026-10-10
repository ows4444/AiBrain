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
    return vaultlib.proposal(text, do + (f" until {until}" if until else ""), when, started)


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
        self.assertEqual(self.steps(), [f"started {LOOK} -> a1: check, due since 2026-10-01",
                                        f"finished {LOOK} -> a1: pages: 1",  # one that only reads needs no line, and goes first
                                        f"waiting {LISTING} -> {NOT_ALLOWED}; yes {name}"])
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
                         ([LOOK, "feel it"], [(LISTING, "the round's budget is spent")]))  # what only reads comes first
        self.log()
        clock = iter([0.0, 0.0, 601.0, 601.0, 601.0])  # ten minutes pass while the first one runs
        with mock.patch.object(work.time, "monotonic", side_effect=lambda: next(clock)):
            late = work.round_of(self.root)
        self.assertEqual(([d["text"] for d in late["did"]], [x["why"] for x in late["left"]]),
                         ([LOOK], ["the round's budget is spent"] * 2))

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
        self.assertRegex(text[1], rf"^  {LISTING} \(index\)  \[worry \d\.\d\d; it changes the brain; due since 2026-10-01\]$")
        self.assertEqual(text[2], "      would be started: index, due since 2026-10-01")
        left = f"  left: {WHOLE} (snapshot): the policy does not allow it (yes {named(WHOLE, 'snapshot', started=1)})  ["
        self.assertTrue(any(line.startswith(left) for line in text), text)

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


class APlan(Worked):
    """Several actions to one reminder: held to the policy before any runs, done in order, taken up where it stopped."""

    ORDER = "put it in order"
    LINE = f"{ORDER} when 2026-10-01 do `fingerprint`, `index` until `check`, `snapshot`"

    def setUp(self):
        super().setUp()
        self.remind(self.LINE)
        self.allow("work", "fingerprint", "index", "snapshot")

    def said(self):
        """Each step of the log as its kind and what it names: `started a2: 2/3 index`."""
        return [s.split(" -> ")[0].split()[0] + " " + s.split(" -> ")[1].split(",")[0].split(": ", 2)[0] + ": "
                + s.split(" -> ")[1].split(": ", 1)[1].split(",")[0] if s.split()[0] == "started"
                else s.split(" -> ")[0].split()[0] + " " + s.split(" -> ")[1].split(":")[0] for s in self.steps()]

    def test_its_parts_run_in_order_each_with_its_own_end(self):
        read = vaultlib.Vault(self.root).intentions()[0]
        self.assertEqual((read["do"], read["until"], read["steps"]), ("fingerprint, index, snapshot", None, [
            {"do": "fingerprint", "until": None}, {"do": "index", "until": "check"}, {"do": "snapshot", "until": None}]))
        found = work.round_of(self.root)
        self.assertEqual(self.said(), ["started a1: 1/3 fingerprint", "passed a1", "started a2: 2/3 index", "passed a2",
                                       "started a3: 3/3 snapshot", "finished a3"])
        self.assertEqual((len(found["did"][0]["steps"]), found["did"][0]["do"], found["left"]),
                         (6, "fingerprint, index, snapshot", []))
        self.assertTrue(self.listed())
        v = vaultlib.Vault(self.root)
        self.assertEqual((v.standing(v.intentions()[0])["state"], [i["text"] for i in v.due_intentions()]), ("finished", []))

    def test_every_part_is_asked_of_the_policy_before_the_first_runs(self):
        self.allow("work", "fingerprint", "index")  # the last part is not allowed: none of it runs
        found = work.round_of(self.root)
        name = vaultlib.proposal(self.ORDER, "fingerprint, index until check, snapshot", "2026-10-01", 0)
        self.assertEqual(self.steps(), [f"waiting {self.ORDER} -> policy: hippocampus/policy.md does not allow snapshot; "
                                        f"yes {name}"])
        self.assertEqual((found["left"][0]["why"], self.listed()), (f"the policy does not allow it (yes {name})", False))
        self.allow("work", "fingerprint", "index", "snapshot")
        work.round_of(self.root)
        self.assertEqual(self.said()[1:], ["started a1: 1/3 fingerprint", "passed a1", "started a2: 2/3 index", "passed a2",
                                           "started a3: 3/3 snapshot", "finished a3"])

    def test_a_part_that_fails_stops_the_plan_there_and_is_the_one_tried_again(self):
        self.write("cortex/concepts/broken.md", page("concept", "See [[nowhere]].\n", title="Broken", status="established",
                                                     summary="It points nowhere.", **DATES))
        work.round_of(self.root)
        self.assertEqual(self.said(), ["started a1: 1/3 fingerprint", "passed a1", "started a2: 2/3 index", "failed a2"])
        self.assertTrue(self.steps()[-1].endswith("a2: check does not hold: pages: 2"))
        v = vaultlib.Vault(self.root)
        stands = v.standing(v.intentions()[0])
        self.assertEqual((stands["state"], stands["part"], stands["attempts"], stands["ever"]), ("failed", 1, 1, 2))
        self.assertRegex(work.round_of(self.root)["left"][0]["why"], r"^it is tried again after ")
        os.remove(os.path.join(self.root, "cortex/concepts/broken.md"))
        work.round_of(self.root, now=self.later(31))
        self.assertEqual(self.said()[4:], ["started a3: 2/3 index", "passed a3", "started a4: 3/3 snapshot", "finished a4"])

    def test_one_that_was_interrupted_is_taken_up_at_the_part_it_had_reached(self):
        perform, ran = act.perform, []

        def dies_on_the_second(root, name):
            ran.append(name)
            if len(ran) == 2:
                raise KeyboardInterrupt()
            return perform(root, name)

        with mock.patch.object(act, "perform", side_effect=dies_on_the_second):
            with self.assertRaises(KeyboardInterrupt):
                work.round_of(self.root)
        self.assertEqual(self.said(), ["started a1: 1/3 fingerprint", "passed a1", "started a2: 2/3 index"])
        work.round_of(self.root)
        self.assertEqual(self.said()[3:], ["failed a2", "started a3: 2/3 index", "passed a3", "started a4: 3/3 snapshot",
                                           "finished a4"])
        self.assertEqual(self.said().count("started a1: 1/3 fingerprint"), 1)  # what had passed is not done again

    def test_a_round_s_budget_is_counted_in_parts_and_the_rest_goes_on_in_the_next(self):
        self.write(vaultlib.TUNING_PATH, page("tuning", "\n## Overrides\n\n- work_steps = 2\n", title="Tuning"))
        first = work.round_of(self.root)
        self.assertEqual(self.said(), ["started a1: 1/3 fingerprint", "passed a1", "started a2: 2/3 index", "passed a2"])
        self.assertEqual(first["left"][0]["why"], "the round's budget is spent")
        text = run_brain(self.root, "introspect", "--remind").stdout
        self.assertIn(f"\n  passed    {self.ORDER}  (when 2026-10-01: do fingerprint, index until check, snapshot; 2 of 3 "
                      "parts passed)\n", text)
        row = [r for r in tend.digest(vaultlib.Vault(self.root))["reminders"] if r["text"] == self.ORDER][0]
        self.assertEqual((row["do"], row["state"]), ("fingerprint, index, snapshot", "passed"))
        work.round_of(self.root)
        self.assertEqual(self.said()[4:], ["started a3: 3/3 snapshot", "finished a3"])
        carried = json.loads(run_brain(self.root, "introspect", "--remind", "--json").stdout)["intentions"]["carried"][0]
        self.assertEqual((carried["plan"], carried["part"], carried["parts"], carried["state"]),
                         ("fingerprint, index until check, snapshot", 2, 3, "finished"))

    def test_a_yes_is_for_the_whole_plan_once_through_and_ends_with_a_failure(self):
        self.allow("work")
        self.write(vaultlib.TUNING_PATH, page("tuning", "\n## Overrides\n\n- work_steps = 1\n", title="Tuning"))
        work.round_of(self.root)
        name = vaultlib.proposal(self.ORDER, "fingerprint, index until check, snapshot", "2026-10-01", 0)
        today = datetime.date.today().isoformat()
        self.allow("work", once=[f"{name} {today}"])
        work.round_of(self.root)   # one part a round here: the first, under the yes
        self.assertTrue(self.steps()[1].endswith(f"a1: 1/3 fingerprint, due since 2026-10-01, by the owner's yes {name}"))
        self.write("cortex/concepts/broken.md", page("concept", "See [[nowhere]].\n", title="Broken", status="established",
                                                     summary="It points nowhere.", **DATES))
        work.round_of(self.root)   # the second goes on under it, though its name is another by now, and fails
        self.assertEqual(self.said()[1:], ["started a1: 1/3 fingerprint", "passed a1", "started a2: 2/3 index", "failed a2"])
        late = work.round_of(self.root, now=self.later(31))  # a failure ends the yes: it waits again, under a new name
        again = vaultlib.proposal(self.ORDER, "fingerprint, index until check, snapshot", "2026-10-01", 2)
        self.assertEqual(self.steps()[-1], f"waiting {self.ORDER} -> policy: hippocampus/policy.md does not allow index, "
                                           f"snapshot; yes {again}")
        self.assertEqual(late["left"][0]["why"], f"the policy does not allow it (yes {again})")

    def test_a_plan_shortened_under_it_is_finished_when_every_part_it_has_now_has_passed(self):
        self.write(vaultlib.TUNING_PATH, page("tuning", "\n## Overrides\n\n- work_steps = 2\n", title="Tuning"))
        work.round_of(self.root)  # two of three passed
        self.remind(f"{self.ORDER} when 2026-10-01 do `fingerprint`, `index` until `check`")
        found = work.round_of(self.root)
        self.assertEqual(self.steps()[-1], f"finished {self.ORDER} -> a2: every part its plan now has has passed")
        self.assertEqual(len(found["did"][0]["steps"]), 1)

    def test_a_dry_run_says_the_part_it_would_begin_with(self):
        found = work.round_of(self.root, dry=True)
        self.assertEqual(found["did"][0]["steps"], ["would be started: 1/3 fingerprint, due since 2026-10-01"])
        self.assertEqual(self.steps(), [])

    def test_a_plan_is_taken_whole_or_not_at_all(self):
        wrong = [(i["do"], i["steps"], i["problem"]) for i in vaultlib.Vault(self.root).intentions()]
        self.assertIsNone(wrong[0][2])
        self.remind("a when 2026-11-01 do `index`, `fetch`", "b when 2026-11-01 do `index`, snapshot",
                    "c when 2026-11-01 do `index` until `graph`, `snapshot`")
        self.assertEqual([(i["do"], i["steps"], i["problem"]) for i in vaultlib.Vault(self.root).intentions()], [
            (None, [], "`fetch` is no action that can be done with nobody there; `brain act` lists them"),
            (None, [], "'2026-11-01 do `index`, snapshot': what follows `do` cannot be read. Each action is in backticks, "
                       "with a comma before the next: do `fingerprint`, `index` until `check`"),
            (None, [], "`graph` is no action that only reads (closest: gaps); `brain act` lists them")])
        self.assertEqual(run_brain(self.root, "check").returncode, 1)
        self.assertEqual(work.round_of(self.root)["did"], [])


class WhatComesFirst(Worked):
    """The order of a round is worked out by rule and said with each reminder; it decides nothing but the order."""

    def setUp(self):
        super().setUp()
        self.day = datetime.date.today().isoformat()
        self.remind(f"{LOOK} when {self.day} do `check`", f"{LISTING} when {self.day} do `index`",
                    f"tend [[spacing]] when {self.day} do `index`", f"{WHOLE} when {self.day} do `index`")
        self.write("OWNER.md", "# Owner\n\n## Goals\n\n- Pass the exam by 2099-01-01 -> [[spacing]]\n")
        self.failures = [f"{self.day} act {step} {WHOLE} -> a{n}: it broke" for n in (1, 2) for step in ("started", "failed")]
        self.log(*self.failures)

    def test_a_goal_first_then_what_is_felt_then_the_lesser_risk(self):
        found = work.round_of(self.root, dry=True)
        self.assertEqual(found["order"], [
            {"text": "tend [[spacing]]", "first": f"a goal depends on a page it names; worry 0.33; it changes the brain; due "
                                                  f"since {self.day}"},
            {"text": WHOLE, "first": f"frustration 0.67; it changes the brain; due since {self.day}"},  # it failed twice
            {"text": LOOK, "first": f"worry 0.33; it only reads; due since {self.day}"},
            {"text": LISTING, "first": f"worry 0.33; it changes the brain; due since {self.day}"}])
        text = run_brain(self.root, "work", "--dry-run").stdout
        self.assertIn(f"\n  tend [[spacing]] (index)  [a goal depends on a page it names; worry 0.33; it changes the brain; "
                      f"due since {self.day}]\n", text)
        self.assertEqual(json.loads(run_brain(self.root, "work", "--dry-run", "--json").stdout)["order"], found["order"])

    def test_what_the_brain_did_itself_is_felt_and_a_wait_is_one_worry_not_two(self):
        v = vaultlib.Vault(self.root)
        felt = {(r["feeling"], r["target"]): r for r in v.feelings()}
        self.assertEqual([c["why"] for c in felt["frustration", WHOLE]["causes"]], ["its action failed: it broke"] * 2)
        self.allow("work")
        work.round_of(self.root)  # index is not allowed: three wait, and the one that only reads is carried out
        v = vaultlib.Vault(self.root)
        felt = {(r["feeling"], r["target"]): r for r in v.feelings()}
        self.assertEqual(felt["satisfaction", LOOK]["causes"][0]["why"], "carried out: pages: 1")
        waits = felt["worry", LISTING]["causes"]
        self.assertEqual(len(waits), 1)  # the wait, and not also that it is due
        self.assertEqual(waits[0]["why"], f"waits for the owner since {self.day}: policy: hippocampus/policy.md does not "
                                          f"allow index; yes {named(LISTING, 'index', when=self.day)}")
        later = vaultlib.Vault(self.root, now=self.later(7 * 24 * 60))
        self.assertEqual({(r["feeling"], r["target"]): r["intensity"] for r in later.feelings()}["worry", LISTING], 0.67)
        # A reminder since taken off the page is still what the log says of it, under its words.
        self.remind()
        gone = {(r["feeling"], r["target"]) for r in vaultlib.Vault(self.root).feelings()}
        self.assertIn(("frustration", WHOLE), gone)

    def test_no_feeling_and_no_trait_changes_what_the_policy_allows(self):
        self.allow("work")
        self.write("CHARACTER.md", "# Character\n\n## Traits\n\n" + "".join(f"- {name} = 1.0\n" for name in vaultlib.TRAITS))
        v = vaultlib.Vault(self.root)
        self.assertEqual((v.tuning.work_tries, v.tuning.yes_days), (6, 4))  # persistence and caution, at their ends
        allowed = vaultlib.policy_of(self.root)
        for name in vaultlib.ACTIONS:
            self.assertEqual(vaultlib.decide(name, allowed)[0], name == "work" or vaultlib.ACTIONS[name].tier == "reads")
        found = work.round_of(self.root)
        self.assertEqual([d["text"] for d in found["did"]], ["tend [[spacing]]", WHOLE, LOOK, LISTING])  # each took a step
        steps = [s for s in self.steps() if s not in [line.split(" act ", 1)[1] for line in self.failures]]
        self.assertEqual(sorted(s.split()[0] for s in steps), ["finished", "started", "waiting", "waiting", "waiting"])
        self.assertFalse(self.listed())  # first in the order, most felt, every trait at its end: and index did not run
        # What persistence does change is how often a failure is tried before it is the owner's.
        self.allow("work", "index")
        self.log(*[f"{self.day} act {step} {WHOLE} -> a{n}: it broke" for n in (1, 2, 3) for step in ("started", "failed")])
        patient = work.round_of(self.root, now=self.later(100000))
        self.assertIn(WHOLE, [d["text"] for d in patient["did"]])
        self.assertTrue([s for s in self.steps() if s.startswith(f"started {WHOLE} -> a4")])
        os.remove(os.path.join(self.root, "CHARACTER.md"))
        self.log(*[f"{self.day} act {step} {WHOLE} -> a{n}: it broke" for n in (1, 2, 3) for step in ("started", "failed")])
        work.round_of(self.root, now=self.later(100000))
        self.assertEqual(self.steps()[-1].split(" -> ")[1].split(";")[0], "owner: it failed 3 times")


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
