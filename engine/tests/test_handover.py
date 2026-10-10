"""Outside work is handed to another program, and what came of it returns as an input. Run: brain test"""
import datetime
import json
import os
import re
import subprocess
import sys

from support import BRAIN, TempBrain, page, run_brain, vaultlib

import commands  # noqa: E402  (support puts engine/lib on the path)
import tend  # noqa: E402
from vault_intentions import handover, read_intentions  # noqa: E402

FIX, SEND = "fix the login redirect", "send the report"
SHOWN = "the page loads after sign-in"
META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "a stand-in for a runtime", "version": "0"}}


class Handed(TempBrain):
    """A brain with one reminder for another program whose day has come, one far off, and one the brain does itself."""

    def setUp(self):
        super().setUp()
        self.remind(f"{FIX} when 2026-10-01 for `acline` until {SHOWN}", f"{SEND} when 2099-01-01 09:00 for `acline`",
                    "keep the listing current when 2026-10-01 do `index`", "call the supplier when 2026-10-01")
        self.name = handover(FIX, "acline", SHOWN, "2026-10-01")

    def remind(self, *lines):
        self.write("hippocampus/intentions.md", page("intentions", "\n# Intentions\n\n## Open\n\n"
                                                     + "".join(f"- {line}\n" for line in lines), title="Intentions"))

    def tool(self, name, **arguments):
        """What `brain mcp` answers a program that calls one tool: the text it gets back."""
        env = {k: v for k, v in os.environ.items() if k not in ("BRAIN_ROOT", "CLAUDE_PROJECT_DIR")}
        sent = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments, "_meta": META}}) + "\n"
        r = subprocess.run([sys.executable, BRAIN, "mcp"], input=sent, capture_output=True, text=True,
                           env=dict(env, BRAIN_ROOT=self.root))
        answer = json.loads(r.stdout.splitlines()[0])["result"]
        self.assertFalse(answer["isError"], answer)
        return answer["content"][0]["text"]

    def report(self, name, said="The redirect loop is gone: the page loads after sign-in. Checked by hand, twice."):
        """What a runtime leaves when it is done, and what `/ingest` then does with a note: it lands, and gets its episode."""
        self.write("inbox/acline-report.md", f"---\ntitle: The login redirect, fixed\nhanded: {name}\n---\n\n{said}\n")
        os.makedirs(os.path.join(self.root, "senses", "inbox"), exist_ok=True)
        os.replace(os.path.join(self.root, "inbox", "acline-report.md"),
                   os.path.join(self.root, "senses", "inbox", "2026-10-03-acline-report.md"))
        return commands.call("new", ["episode", "--from", "senses/inbox/2026-10-03-acline-report.md"], root=self.root)


class TheLine(Handed):
    def test_a_reminder_may_be_for_another_program_and_say_how_it_is_known_to_be_done(self):
        read = [(i["text"], i["when"], i["hand"], i["hand_until"], i["do"], i["problem"])
                for i in vaultlib.Vault(self.root).intentions()]
        self.assertEqual(read, [(FIX, "2026-10-01", "acline", SHOWN, None, None),
                                (SEND, "2099-01-01 09:00", "acline", None, None, None),
                                ("keep the listing current", "2026-10-01", None, None, "index", None),
                                ("call the supplier", "2026-10-01", None, None, None, None)])
        prose = read_intentions("- thank them when it is good for them\n")[0]
        self.assertEqual((prose["event"], prose["hand"], prose["problem"]), ("it is good for them", None, None))

    def test_what_cannot_be_handed_over_is_a_problem_of_the_page(self):
        wrong = [(i["hand"], i["do"], i["problem"]) for i in read_intentions(
            "- a when 2026-11-01 do `index` for `acline`\n- b when every day for `acline`\n"
            "- c when it ships for `acline`\n- d when 2026-11-01 for `My Tool`\n- e when 2026-02-30 for `acline`\n")]
        self.assertEqual(wrong, [
            (None, None, "'2026-11-01 do `index` for `acline`': a reminder is carried out by the brain (`do`) or handed to "
                         "another program (`for`), not both"),
            (None, None, "'every day' is a repeat, and a repeat cannot be handed over yet: give it a day"),
            (None, None, "'it ships' is an event, and an event cannot be when it is handed to `acline`: only a day, a time "
                         "or a repeat can, since nothing but a reader can tell that an event has come"),
            (None, None, "`My Tool` is no name of a program to hand it to: lower-case letters, digits and hyphens, as in "
                         "`acline`"),
            (None, None, "'2026-02-30' is no day: a reminder's date is YYYY-MM-DD, then HH:MM if it has a time")])
        self.remind("b when every day for `acline`")
        self.assertEqual(run_brain(self.root, "check").returncode, 1)
        self.assertEqual(vaultlib.Vault(self.root).handed_over(), [])

    def test_its_name_is_another_once_anything_about_it_changes(self):
        names = {handover(FIX, "acline", SHOWN, "2026-10-01"), handover(FIX + " now", "acline", SHOWN, "2026-10-01"),
                 handover(FIX, "other", SHOWN, "2026-10-01"), handover(FIX, "acline", None, "2026-10-01"),
                 handover(FIX, "acline", SHOWN, "2026-10-02")}
        self.assertEqual(len(names), 5)
        self.assertRegex(self.name, r"^[0-9a-f]{7}$")


class HandedAndBack(Handed):
    def test_what_waits_on_another_program_is_listed_with_its_name_and_the_brain_does_nothing_about_it(self):
        v = vaultlib.Vault(self.root)
        self.assertEqual([(h["text"], h["state"], h["name"], h["episode"]) for h in v.handed_over()],
                         [(FIX, "handed", self.name, None), (SEND, "scheduled", handover(SEND, "acline", None, "2099-01-01 09:00"),
                                                              None)])
        found = commands.call("handover", [], root=self.root)
        self.assertEqual((found["waiting"][0]["name"], found["waiting"][0]["for"], found["waiting"][0]["until"],
                          found["waiting"][0]["since"], found["waiting"][0]["felt"]["feeling"]),
                         (self.name, "acline", SHOWN, "2026-10-01", "worry"))
        self.assertEqual(([h["text"] for h in found["returned"]], [h["text"] for h in found["scheduled"]]), ([], [SEND]))
        text = run_brain(self.root, "handover").stdout.splitlines()
        self.assertRegex(text[0], r"^handover, \d{4}-\d\d-\d\d: 1 wait on another program, 0 reported on, 1 not due yet$")
        self.assertEqual(text[1:3], [f"  {self.name}  {FIX}  (for acline; due since 2026-10-01)", f"           done when: {SHOWN}"])
        self.assertRegex(text[3], r"^           worry \d\.\d\d: due since 2026-10-01$")
        self.assertEqual(text[4:], [f"  not due yet: {SEND} (for acline; 2099-01-01 09:00)",
                                    "to report on one: a Markdown note in the brain's inbox/ that begins `---`, `handed: "
                                    "<its name>`, `---`, then what was done, what was checked and how it ended"])
        # It is due, so it shows where reminders do; and no round of the worker takes it up.
        row = [r for r in tend.digest(v)["reminders"] if r["text"] == FIX][0]
        self.assertEqual(row, {"text": FIX, "when": "2026-10-01", "for": "acline"})
        self.assertIn(f"{FIX} (2026-10-01; for acline, not reported on)", tend.render(tend.digest(v), None))
        self.assertEqual([i["text"] for i in v.carried_out()], ["keep the listing current"])

    def test_a_stand_in_reads_it_does_it_and_its_report_closes_it(self):
        listed = self.tool("handed")  # a runtime asks what is for it
        name = re.search(r"^  ([0-9a-f]{7})  " + FIX, listed, re.M).group(1)
        self.assertEqual((name, f"done when: {SHOWN}" in listed), (self.name, True))
        made = self.report(name)  # it does the work its own way, and leaves a note; the note is encoded
        self.assertIn("handed", made["filled"])
        v = vaultlib.Vault(self.root)
        back = [h for h in v.handed_over() if h["text"] == FIX][0]
        self.assertEqual((back["state"], back["episode"], back["reported"]),
                         ("returned", made["page"], datetime.date.today()))
        self.assertNotIn(FIX, [i["text"] for i in v.due_intentions()])  # it waits on no one now
        after = self.tool("handed")
        self.assertNotIn(f"  {name}  ", after)
        self.assertIn(f"  reported on: {FIX} (for acline): {made['page']}; `/remind` closes its line", after)
        felt = {(r["feeling"], r["target"]): r["causes"][0]["why"] for r in v.feelings()}
        self.assertEqual(felt["satisfaction", FIX], f"what was handed to acline came back: {made['page']}")
        self.assertNotIn(("worry", FIX), felt)
        text = run_brain(self.root, "introspect", "--remind").stdout
        self.assertIn(f"\n  returned  {FIX}  (when 2026-10-01: for acline until {SHOWN}; {name})\n"
                      f"        reported on by {made['page']}\n", text)
        self.assertIn(f"\n  scheduled {SEND}  (when 2099-01-01 09:00: for acline; ", text)

    def test_a_report_under_another_name_closes_nothing_and_an_imagined_one_is_no_report(self):
        self.report("0000000")
        v = vaultlib.Vault(self.root)
        self.assertEqual([h["state"] for h in v.handed_over()], ["handed", "scheduled"])
        self.write("cortex/episodes/imagined.md", page("episode", "What if it were fixed.\n", title="Imagined",
                                                       origin="generated", handed=self.name, created="2026-10-02",
                                                       updated="2026-10-02"))
        self.assertEqual(vaultlib.Vault(self.root).handed_over()[0]["state"], "handed")
        # The reminder changed after the name was read: what reports on the old one does not close the new.
        self.remind(f"{FIX} when 2026-10-01 for `acline` until nobody is sent round twice")
        self.write("cortex/episodes/late.md", page("episode", "Fixed.\n", title="Late", handed=self.name,
                                                   created="2026-10-02", updated="2026-10-02"))
        self.assertEqual(vaultlib.Vault(self.root).handed_over()[0]["state"], "handed")

    def test_another_program_may_ask_what_the_brain_feels_too(self):
        said = self.tool("feel")
        self.assertRegex(said, r"(?m)^  \d\.\d\d  worry +" + FIX + r"  \(reminder\)$")
        self.assertIn(FIX, self.tool("feel", about="login redirect"))
        self.assertNotIn("supplier", self.tool("feel", about="login redirect"))
        empty = TempBrain()
        empty.setUp()
        self.addCleanup(empty.tearDown)
        self.assertRegex(run_brain(empty.root, "handover").stdout, r"^handover, \d{4}-\d\d-\d\d: nothing is handed to another "
                                                                   r"program\n$")
