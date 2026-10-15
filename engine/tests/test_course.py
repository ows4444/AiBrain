"""Intentions the brain carries out itself: the line that names an action, and its course in the log. Run: brain test"""
import json
import os
import subprocess
import sys

from support import HOOKS, TempBrain, page, run_brain, vaultlib

import act  # noqa: E402  (support puts engine/lib on the path)
import commands  # noqa: E402
import tend  # noqa: E402
import vault_intentions  # noqa: E402
from vault_intentions import NEXT, VERBS, read_intentions  # noqa: E402

LISTING = "keep the listing current"
WHOLE = "see the listing is whole"
PAGE = "hippocampus/intentions.md"


class Carried(TempBrain):
    """A brain with a daily reminder, one whose day has come, one far off, a plain one and one closed by hand."""

    LINES = (f"{LISTING} when every day do `index`", f"{WHOLE} when 2026-10-01 do `index` until `check`",
             "take the numbers when 2099-01-01 09:00 do `snapshot`", "call the supplier when 2026-10-01",
             "tidy up when 2026-10-01 do `graph` (done 2026-10-02: by hand)")

    def setUp(self):
        super().setUp()
        self.remind(*self.LINES)

    def remind(self, *lines):
        return self.write(PAGE, page("intentions", "\n# Intentions\n\n## Open\n\n" + "".join(f"- {line}\n" for line in lines),
                                     title="Intentions"))

    def stands(self):
        v = vaultlib.Vault(self.root)
        return {i["text"]: (i["stands"]["state"], i["stands"]["attempt"], i["stands"]["attempts"]) for i in v.carried_out()}

    def steps(self):
        return [e.rest for e in vaultlib.read_events(self.root) if e.op == "act"]


class TheLine(Carried):
    def test_a_reminder_may_end_with_an_action_and_what_must_hold_after_it(self):
        read = {i["text"]: i for i in read_intentions("\n".join(f"- {line}" for line in self.LINES))}
        self.assertEqual([(i["when"], i["do"], i["until"], i["every"], i["problem"]) for i in read.values()], [
            ("every day", "index", None, "day", None), ("2026-10-01", "index", "check", None, None),
            ("2099-01-01 09:00", "snapshot", None, None, None), ("2026-10-01", None, None, None, None),
            ("2026-10-01", "graph", None, None, None)])
        self.assertEqual(read["tidy up"]["ended"], "done")  # the closing mark is read as before, after the action
        # Prose that holds the word is no action: the name is in backticks, or it is an event like any other.
        prose = read_intentions("- call them when they do check\n")[0]
        self.assertEqual((prose["event"], prose["do"], prose["problem"]), ("they do check", None, None))

    def test_what_cannot_be_carried_out_is_a_problem_of_the_page_and_nothing_is_done(self):
        wrong = [(i["text"], i["do"], i["problem"]) for i in read_intentions(
            "- a when every day do index\n- b when 2026-11-01 do `indx`\n- c when 2026-11-01 do `fetch`\n"
            "- d when a rival cuts prices do `index`\n- e when 2026-11-01 do `index` until `index`\n"
            "- f when 2026-02-30 do `index`\n- g when 2026-11-01 do `index` until `chek`\n")]
        self.assertEqual(wrong, [
            ("a", None, "'every day do index': an action is written in backticks, do `index`, so that prose is never "
                        "taken for one"),
            ("b", None, "`indx` is no action that can be done with nobody there (closest: index); `brain act` lists them"),
            ("c", None, "`fetch` is no action that can be done with nobody there; `brain act` lists them"),
            ("d", None, "'a rival cuts prices' is an event, and an event cannot start `index`: only a day, a time or a "
                        "repeat can, since nothing but a reader can tell that an event has come"),
            ("e", None, "`index` is no action that only reads; `brain act` lists them"),
            ("f", None, "'2026-02-30' is no day: a reminder's date is YYYY-MM-DD, then HH:MM if it has a time"),
            ("g", None, "`chek` is no action that only reads (closest: check); `brain act` lists them")])
        path = self.remind(f"{LISTING} when every day do `indx`", "old when 2026-11-01 do `fetch` (dropped)")
        r = run_brain(self.root, "check", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["schema"], [{"page": PAGE, "problems": [
            "`indx` is no action that can be done with nobody there (closest: index); `brain act` lists them"]}])
        self.assertEqual(vaultlib.Vault(self.root).carried_out(), [])  # nothing is carried out on a guess
        hook = subprocess.run([sys.executable, os.path.join(HOOKS, "validate_page.py"), "--pre"], text=True,
                              capture_output=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root),
                              input=json.dumps({"tool_name": "Edit", "tool_input": {
                                  "file_path": path, "old_string": "do `indx`", "new_string": "do `forget`"}}))
        self.assertEqual(hook.returncode, 2)
        self.assertIn("`forget` is no action that can be done with nobody there", hook.stderr)


class TheCourse(Carried):
    def test_where_each_stands_is_read_from_the_log_alone(self):
        self.assertEqual(self.stands(), {LISTING: ("ready", None, 0), WHOLE: ("ready", None, 0),
                                         "take the numbers": ("scheduled", None, 0)})
        v = vaultlib.Vault(self.root)
        self.assertEqual([(i["text"], i["do"], i["stands"] and i["stands"]["state"]) for i in v.due_intentions()],
                         [(WHOLE, "index", "ready"), ("call the supplier", None, None), (LISTING, "index", "ready")])
        self.assertIsNone(v.standing(v.intentions()[3]))  # one that only reminds has no course
        # What `brain act index` leaves is an action that ran, not a step of a reminder.
        self.log("2026-10-02 09:00 act index -> index: 3 pages listed", "2026-10-02 remind call the supplier -> x")
        self.assertEqual(self.stands()[LISTING], ("ready", None, 0))

    def test_a_course_from_start_to_end_and_the_round_after_it(self):
        line = act.advance(self.root, WHOLE, "started", "index, due since 2026-10-01")
        self.assertRegex(line, rf"^\d{{4}}-\d\d-\d\d \d\d:\d\d act started {WHOLE} -> a1: index, due since 2026-10-01$")
        self.assertEqual(self.stands()[WHOLE], ("started", "a1", 1))
        act.advance(self.root, WHOLE, "failed", "check: 1 broken link")
        act.advance(self.root, WHOLE, "started", "index, tried again")
        act.advance(self.root, "  SEE the listing   is whole ", "finished", "index: 3 pages listed\nand more it said")
        self.assertEqual(self.steps(), [f"started {WHOLE} -> a1: index, due since 2026-10-01",
                                        f"failed {WHOLE} -> a1: check: 1 broken link",
                                        f"started {WHOLE} -> a2: index, tried again",
                                        f"finished {WHOLE} -> a2: index: 3 pages listed"])
        self.assertEqual(self.stands()[WHOLE], ("finished", "a2", 2))
        v = vaultlib.Vault(self.root)
        self.assertNotIn(WHOLE, [i["text"] for i in v.due_intentions()])  # done: it no longer waits on anyone
        # A repeat that finished is over for this round, and stands ready again when the next one comes.
        act.advance(self.root, LISTING, "started", "index")
        act.advance(self.root, LISTING, "finished", "index: up to date")
        self.assertEqual(self.stands()[LISTING], ("scheduled", None, 0))
        self.assertNotIn(LISTING, [i["text"] for i in vaultlib.Vault(self.root).due_intentions()])
        ahead = vaultlib.Vault(self.root, now=v.now + __import__("datetime").timedelta(days=1, minutes=1))
        self.assertEqual(ahead.standing(ahead.intentions()[0])["state"], "ready")

    def test_no_step_is_written_that_may_not_follow(self):
        # Every state against every step: a step is accepted where the table has it, and nowhere else.
        reach = {"ready": [], "started": ["started"], "passed": ["started", "passed"], "failed": ["started", "failed"],
                 "waiting": ["waiting"], "finished": ["started", "finished"]}
        for state, taken in reach.items():
            for step in VERBS:
                with self.subTest(state=state, step=step):
                    self.log()
                    for done in taken:
                        act.advance(self.root, WHOLE, done)
                    self.assertEqual(self.stands()[WHOLE][0], state)
                    before = self.steps()
                    if step in NEXT[state]:
                        act.advance(self.root, WHOLE, step)
                        self.assertEqual(len(self.steps()), len(before) + 1)
                    else:
                        with self.assertRaises(commands.Refused) as refused:
                            act.advance(self.root, WHOLE, step)
                        self.assertEqual(str(refused.exception), f"'{WHOLE}' is {state}: it cannot be {step} now (what may "
                                         f"follow: {', '.join(NEXT[state]) or 'nothing'})")
                        self.assertEqual(self.steps(), before)
        self.assertEqual(set(NEXT), {"scheduled", "ready", "started", "passed", "failed", "waiting", "finished"})
        self.assertEqual(VERBS, ("started", "passed", "finished", "failed", "waiting"))
        self.assertEqual(NEXT["waiting"], ("started",))  # found waiting again, nothing more is written
        self.assertFalse(set(VERBS) & set(vaultlib.ACTIONS))  # a step is never mistaken for an action that ran
        self.log()
        for text, step, why in (("take the numbers", "started", "'take the numbers' is scheduled: it cannot be started "
                                                               "now (what may follow: nothing)"),
                                ("call the supplier", "started", "no open reminder with an action says 'call the supplier'"),
                                ("tidy up", "started", "no open reminder with an action says 'tidy up'"),
                                ("no such thing", "waiting", "no open reminder with an action says 'no such thing'")):
            with self.assertRaises(commands.Refused) as refused:
                act.advance(self.root, text, step)
            self.assertEqual(str(refused.exception), why)

    def test_a_step_is_logged_whatever_was_said_of_it(self):
        key = "AKIA" + "ABCDEFGHIJKLMNOP"  # what the log refuses to hold
        act.advance(self.root, WHOLE, "waiting", f"the policy page does not allow index ({key})")
        act.advance(self.root, WHOLE, "started", f"index with {key}")
        act.advance(self.root, WHOLE, "failed", "it named [[no-such-page]]")
        self.assertEqual(self.steps(), [f"waiting {WHOLE} -> none", f"started {WHOLE} -> a1",
                                        f"failed {WHOLE} -> a1: it named no-such-page"])
        v = vaultlib.Vault(self.root)
        self.assertEqual([step[2:] for step in v.standing(v.intentions()[1])["course"]],
                         [("waiting", None, ""), ("started", "a1", ""), ("failed", "a1", "it named no-such-page")])


class WhereItShows(Carried):
    def test_its_history_says_why_it_ran_what_it_did_and_how_it_ended(self):
        act.advance(self.root, WHOLE, "waiting", "hippocampus/policy.md does not allow index")
        act.advance(self.root, WHOLE, "started", "index, due since 2026-10-01")
        act.advance(self.root, WHOLE, "finished", "index: 3 pages listed; check found nothing")
        found = json.loads(run_brain(self.root, "introspect", "--remind", "--json").stdout)["intentions"]["carried"]
        whole = found[1]
        self.assertEqual((whole["text"], whole["when"], whole["do"], whole["until"], whole["state"], whole["attempts"]),
                         (WHOLE, "2026-10-01", "index", "check", "finished", 1))
        self.assertEqual([(s["step"], s["attempt"], s["note"]) for s in whole["course"]], [
            ("waiting", None, "hippocampus/policy.md does not allow index"),
            ("started", "a1", "index, due since 2026-10-01"),
            ("finished", "a1", "index: 3 pages listed; check found nothing")])
        self.assertEqual([(i["text"], i["state"]) for i in found],
                         [(LISTING, "ready"), (WHOLE, "finished"), ("take the numbers", "scheduled")])
        text = run_brain(self.root, "introspect", "--remind").stdout
        self.assertIn("\nreminders the brain carries out itself (where each stands, then its last steps, from the log): 3\n"
                      f"  ready     {LISTING}  (when every day: do index)\n"
                      f"  finished  {WHOLE}  (when 2026-10-01: do index until check)\n", text)
        self.assertRegex(text, r"\n        \d{4}-\d\d-\d\d \d\d:\d\d waiting: hippocampus/policy.md does not allow index\n"
                               r"        \d{4}-\d\d-\d\d \d\d:\d\d started a1: index, due since 2026-10-01\n"
                               r"        \d{4}-\d\d-\d\d \d\d:\d\d finished a1: index: 3 pages listed; check found nothing\n"
                               r"  scheduled take the numbers  \(when 2099-01-01 09:00: do snapshot\)\n")
        plain = TempBrain()
        plain.setUp()
        self.addCleanup(plain.tearDown)
        self.assertNotIn("carries out itself", run_brain(plain.root, "introspect", "--remind").stdout)

    def test_the_digest_says_the_action_and_where_it_stands(self):
        act.advance(self.root, LISTING, "waiting", "hippocampus/policy.md does not allow index")
        found = tend.digest(vaultlib.Vault(self.root))
        self.assertEqual(found["reminders"], [
            {"text": WHOLE, "when": "2026-10-01", "do": "index", "state": "ready"},
            {"text": "call the supplier", "when": "2026-10-01"},
            {"text": LISTING, "when": "every day", "do": "index", "state": "waiting"}])
        line = [row for row in tend.render(found, None).splitlines() if "reminders due" in row][0]
        self.assertIn(f"{WHOLE} (2026-10-01; do index: ready), call the supplier (2026-10-01), "
                      f"{LISTING} (every day; do index: waiting)", line)
        self.assertEqual(vault_intentions.words("  Keep  THE listing current "), LISTING)
