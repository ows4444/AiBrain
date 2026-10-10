"""The log's one writer: `brain log` checks a line before it writes it, and refuses what would be lost. Run: brain test"""
import datetime
import json
import os
import subprocess
import sys

from support import ENGINE, TODAY, TempBrain, page, vaultlib

import commands  # noqa: E402  (support puts engine/lib on the path)
import log  # noqa: E402

BIN = os.path.join(ENGINE, "bin", "brain")
HEADER = "---\ntitle: Log\ntype: log\n---\n\n# Log\n\nOne line per operation.\n"


class LogCommand(TempBrain):
    def setUp(self):
        super().setUp()
        self.write("cortex/concepts/spacing-effect.md", page(
            "concept", "Study spread over days lasts longer.\n", title="Spacing effect", aliases="[Spaced practice]",
            status="established", created="2026-01-01", updated="2026-01-01"))
        self.write("cortex/episodes/cepeda-2006.md", page(
            "episode", "A review of 254 studies.\n", title="Cepeda 2006", created="2026-01-01", updated="2026-01-01"))
        self.write("dormant/old-idea.md", page("concept", "Faded.\n", title="Old idea", status="emerging",
                                               created="2025-01-01", updated="2025-01-01"))
        self.path = self.write("hippocampus/log.md", HEADER)

    def text(self):
        with open(self.path, encoding="utf-8") as fh:
            return fh.read()

    def lines(self):
        return [line for line in self.text().splitlines() if line[:4].isdigit()]

    def brain_log(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"}
        return subprocess.run([sys.executable, BIN, "log", *args], capture_output=True, text=True, cwd=self.root,
                              env=env)

    def refused(self, *args, **kw):
        before = self.text()
        with self.assertRaises(log.Refused) as caught:
            log.write(self.root, *args, today=TODAY, **kw)
        self.assertEqual(self.text(), before)  # a refused line writes nothing
        return str(caught.exception)

    def test_a_recall_names_its_pages_by_file_name_whatever_name_they_were_given_by(self):
        out = log.write(self.root, "recall", "how long  between\nsessions", today=TODAY,
                      pages=["Spacing effect", "[[cepeda-2006]]", "spaced practice", "SPACING-EFFECT"])
        line = "2026-10-03 recall how long between sessions -> [[spacing-effect]], [[cepeda-2006]]"
        self.assertEqual(out, {"line": line, "pages": ["spacing-effect", "cepeda-2006"], "written": True})
        self.assertEqual(self.text(), HEADER + "\n" + line + "\n")  # apart from the prose above it
        log.write(self.root, "recall", "again", pages=["cepeda-2006"], today=TODAY)
        self.assertEqual(self.text().count("\n\n2026"), 1)  # the second line sits right under the first
        vault = vaultlib.Vault(self.root, today=TODAY)
        self.assertEqual(vault.recall_count[vault.resolve("cepeda-2006")], 2)
        self.assertEqual(len(vault.edge_weights()), 1)  # the two pages named together are now a pair

    def test_a_question_no_page_answered_is_still_a_line(self):
        self.assertEqual(log.write(self.root, "recall", "what is the capital of Australia", today=TODAY)["line"],
                         "2026-10-03 recall what is the capital of Australia -> none")
        event = vaultlib.read_events(self.root)[-1]
        self.assertEqual((event.op, event.arrow, event.targets), ("recall", True, []))

    def test_a_page_that_is_not_there_is_refused_with_the_closest_name(self):
        self.assertEqual(self.refused("recall", "q", ["spacing-efect"]),
                         "no page named 'spacing-efect' (closest: spacing-effect)")
        self.assertEqual(self.refused("recall", "q", ["spacing-effect", "zzz"]), "no page named 'zzz'")
        self.assertIn("no page named 'nope'", self.refused("review", "[[spacing-effect]]", result="see [[nope]]"))
        self.assertIn("no page named 'gone'", self.refused("explore", "[[gone]]", ["cepeda-2006"]))
        r = self.brain_log("recall", "q", "--pages", "spacing-efect")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertEqual(r.stderr, "brain log: no page named 'spacing-efect' (closest: spacing-effect); "
                                   "nothing was written\n")
        self.assertEqual(self.lines(), [])

    def test_a_dormant_page_and_links_typed_in_the_line_are_accepted(self):
        self.assertEqual(log.write(self.root, "recall", "what faded", ["Old idea"], today=TODAY)["line"],
                         "2026-10-03 recall what faded -> [[Old idea]]")
        self.assertEqual(log.write(self.root, "review", "[[spacing-effect]]", result="worse,  2 lessons",
                                 today=TODAY)["line"], "2026-10-03 review [[spacing-effect]] -> worse, 2 lessons")
        self.assertEqual(log.write(self.root, "decide", "weekly review", ["cepeda-2006"], "review 2027-01-09",
                                 today=TODAY)["line"],
                         "2026-10-03 decide weekly review -> [[cepeda-2006]], review 2027-01-09")

    def test_an_unknown_operation_is_refused(self):
        self.assertIn("'recal' is not an operation of the log; one of: ingest, recall,", self.refused("recal", "q"))

    def test_a_rehearsal_line_needs_its_pages(self):
        for op, what in (("recall", "rehearse"), ("rehearse", "missed")):
            self.assertEqual(self.refused(op, what), "a rehearsal line names the pages rehearsed: give --pages")
        log.write(self.root, "recall", "rehearse", ["spacing-effect"], today=TODAY)
        log.write(self.root, "rehearse", "missed", ["spacing-effect"], today=TODAY)
        self.assertEqual(self.lines(), ["2026-10-03 recall rehearse -> [[spacing-effect]]",
                                        "2026-10-03 rehearse missed -> [[spacing-effect]]"])
        vault = vaultlib.Vault(self.root, today=TODAY)
        self.assertEqual(vault.rehearsals[vault.resolve("spacing-effect")], [(TODAY, False), (TODAY, True)])

    def test_the_question_is_one_line_without_an_arrow_and_cut_at_120_characters(self):
        long = "why " + "x" * 200
        line = log.write(self.root, "recall", long + " -> still part of it", ["cepeda-2006"], today=TODAY)["line"]
        self.assertEqual(line, "2026-10-03 recall why " + "x" * 116 + " -> [[cepeda-2006]]")
        kept = log.write(self.root, "sleep", "a -> b " + "y" * 200, result="1 concept", today=TODAY)["line"]
        self.assertEqual(kept, "2026-10-03 sleep a → b " + "y" * 200 + " -> 1 concept")  # only a question is cut
        self.assertEqual(vaultlib.read_events(self.root)[-1].what, "a → b " + "y" * 200)

    def test_a_line_with_nothing_before_the_arrow(self):
        self.assertEqual(log.write(self.root, "owner", result="OWNER.md filled", today=TODAY)["line"],
                         "2026-10-03 owner -> OWNER.md filled")
        event = vaultlib.read_events(self.root)[-1]
        self.assertEqual((event.op, event.what, event.rest), ("owner", "", "-> OWNER.md filled"))

    def test_a_credential_is_refused_and_not_repeated(self):
        key = "AKIA" + "ABCDEFGHIJKLMNOP"
        why = self.refused("recall", f"is {key} still valid")
        self.assertEqual(why, "the line holds a possible credential (AWS access key), which is not repeated here")

    def test_a_dry_run_writes_nothing_and_json_gives_the_line(self):
        r = self.brain_log("recall", "what", "is", "it", "--pages", "cepeda-2006", "--dry-run")
        today = datetime.date.today().isoformat()
        self.assertEqual((r.returncode, r.stdout), (0, f"would log: {today} recall what is it -> [[cepeda-2006]]\n"))
        self.assertEqual(self.lines(), [])
        r = self.brain_log("ingest", "senses/a.md", "--result", "1 episode", "--json")
        self.assertEqual(json.loads(r.stdout), {"line": f"{today} ingest senses/a.md -> 1 episode", "pages": [],
                                                "written": True})
        r = self.brain_log("recall", "rehearse", "--pages", "spacing-effect")
        self.assertEqual(r.stdout, f"logged: {today} recall rehearse -> [[spacing-effect]]\n")
        self.assertEqual(len(self.lines()), 2)

    def test_a_missing_empty_or_unfinished_log_is_put_right_first(self):
        os.remove(self.path)
        log.write(self.root, "sleep", "1 episode", result="none", today=TODAY)
        self.assertEqual(self.text(), log.HEADER + "2026-10-03 sleep 1 episode -> none\n")
        self.assertEqual(vaultlib.Vault(self.root, today=TODAY).of_type("log")[0].rel, "hippocampus/log.md")
        self.write("hippocampus/log.md", " \n")
        log.write(self.root, "sleep", "2 episodes", result="none", today=TODAY)
        self.assertEqual(self.text(), log.HEADER + "2026-10-03 sleep 2 episodes -> none\n")
        self.write("hippocampus/log.md", HEADER + "\n2026-10-01 sleep 0 episodes -> none")  # no newline at its end
        log.write(self.root, "sleep", "3 episodes", result="none", today=TODAY)
        self.assertEqual(self.lines(), ["2026-10-01 sleep 0 episodes -> none", "2026-10-03 sleep 3 episodes -> none"])
        self.assertNotIn("none\n\n2026-10-03", self.text())

    def test_outside_a_brain_it_writes_nothing(self):
        with self.assertRaises(commands.Refused) as stopped:
            commands.call("log", ["recall", "q"], root=os.path.join(self.root, "cortex"))
        self.assertIn("not a brain", str(stopped.exception))


class LogCheck(TempBrain):
    """`brain check` lists what the log holds and nothing reads: the lines `brain log` would have refused."""

    def check(self, *args):
        r = subprocess.run([sys.executable, BIN, "check", *args], capture_output=True, text=True, cwd=self.root,
                           env={k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"})
        return r.returncode, r.stdout

    def test_lines_read_as_nothing_and_names_that_reach_no_page_are_listed_and_do_not_fail(self):
        self.write("cortex/concepts/spacing-effect.md", page(
            "concept", "Study spread over days lasts longer.\n", title="Spacing effect", status="established",
            created="2026-01-01", updated="2026-01-01"))
        self.write("dormant/old-idea.md", page("concept", "Faded.\n", title="Old idea", status="emerging",
                                               created="2025-01-01", updated="2025-01-01"))
        self.log("2026-10-01 recall fine -> [[spacing-effect]], [[Old idea]]",
                 "2026-10-02 recall typo test -> [[spacing-efect]], [[no-such-page]], [[spacing-effect]]",
                 "2026-10-02 rehearse missed -> [[gone]]",
                 "2026-10-02 sleep 2 episodes -> [[not-a-recall]]",
                 "2026-10-02 recall no arrow at all",
                 "2026-10-2 recall bad date -> [[spacing-effect]]",
                 "2026-02-30 recall a date that does not exist -> [[spacing-effect]]",
                 "2026-10-03 sleep",
                 "Notes in prose are not log lines, even with 2026-10-03 in them.")
        code, out = self.check("--json")
        report = json.loads(out)
        self.assertEqual(code, 0)  # history may name pages since merged: listed, never failed
        self.assertEqual(report["log_unread"], ["2026-10-2 recall bad date -> [[spacing-effect]]",
                                                "2026-02-30 recall a date that does not exist -> [[spacing-effect]]",
                                                "2026-10-03 sleep"])
        self.assertEqual(report["log_unresolved"], [
            {"line": "2026-10-02 recall typo test -> [[spacing-efect]], [[no-such-page]], [[spacing-effect]]",
             "names": ["spacing-efect", "no-such-page"]},
            {"line": "2026-10-02 rehearse missed -> [[gone]]", "names": ["gone"]}])
        code, text = self.check()
        self.assertEqual(code, 0)
        self.assertIn("log lines read as nothing (they do not parse, or their date does not exist): 3\n"
                      "  2026-10-2 recall bad date -> [[spacing-effect]]\n", text)
        self.assertIn("recall lines naming a page that is not here (it strengthens nothing): 2\n", text)
        self.assertIn("  2026-10-02 rehearse missed -> [[gone]]  (not a page: gone)\n", text)

    def test_a_brain_with_no_log_has_nothing_to_list(self):
        report = json.loads(self.check("--json")[1])
        self.assertEqual((report["log_unread"], report["log_unresolved"]), ([], []))
