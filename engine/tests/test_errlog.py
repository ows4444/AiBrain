"""The error log: hooks leave a line when they crash or refuse, and `brain errors` reads it."""
import json
import os
import subprocess
import sys
import unittest

from support import ENGINE, TempBrain, page, run_brain, VALID

import errlog

LOG = os.path.join(".cache", "errors.log")
BRAIN = os.path.join(ENGINE, "bin", "brain")


class ErrLogTest(TempBrain):
    def path(self):
        return os.path.join(self.root, LOG)

    def lines(self):
        with open(self.path(), encoding="utf-8") as fh:
            return fh.read().splitlines()

    def note(self, *args, project=None):
        old = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = project or self.root
        try:
            errlog.note(*args)
        finally:
            if old is None:
                del os.environ["CLAUDE_PROJECT_DIR"]
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old

    def main(self, *argv):
        r = run_brain(self.root, "errors", *argv)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_note_writes_one_line_with_detail(self):
        self.note("hook", "schema", "two\nlines   here")
        self.assertRegex(self.lines()[0], r"^\d{4}-\d\d-\d\d \d\d:\d\d hook schema \| two lines here$")

    def test_note_describes_the_exception_being_handled(self):
        try:
            {}["missing"]
        except KeyError:
            self.note("hook", "error")
        self.assertIn("KeyError: 'missing' at test_errlog.py:", self.lines()[0])

    def test_note_without_an_exception_says_so(self):
        self.note("hook", "error")
        self.assertTrue(self.lines()[0].endswith("| no detail"))

    def test_note_keeps_detail_short_and_finds_the_brain_above(self):
        sub = os.path.join(self.root, "prefrontal", "x")
        os.makedirs(sub)
        self.note("hook", "error", "x" * 1000, project=sub)
        self.assertEqual(len(self.lines()[0].split(" | ")[1]), errlog.SHOWN)

    def test_note_outside_a_brain_writes_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as bare:
            self.note("hook", "error", "x", project=bare)
            self.assertFalse(os.path.exists(os.path.join(bare, LOG)))

    def test_note_never_raises(self):
        self.write(".cache", "a file where the folder should be")
        self.note("hook", "error", "x")  # would raise without the guard

    def test_log_is_capped(self):
        self.write(LOG, "x" * (errlog.CAP + 1))
        self.note("hook", "error", "new")
        self.assertEqual(len(self.lines()), 1)
        self.assertTrue(os.path.exists(self.path() + ".1"))

    def test_read_skips_bad_lines_and_filters_by_date(self):
        self.write(LOG, "2026-01-01 10:00 a error | old\ngarbage\n2026-02-01 10:00 b schema | new\n")
        self.assertEqual(len(errlog.read(self.root)), 2)
        self.assertEqual([r[2] for r in errlog.read(self.root, "2026-02-01")], ["b"])

    def test_summary_orders_by_count(self):
        self.write(LOG, "2026-01-01 10:00 a error | x\n2026-01-02 10:00 b schema | y\n2026-01-03 10:00 b schema | z\n")
        top = errlog.summary(errlog.read(self.root))
        self.assertEqual((top[0]["source"], top[0]["count"], top[0]["last"]), ("b", 2, "2026-01-03 10:00"))

    def test_report_text_json_empty_and_clear(self):
        self.assertIn("none logged", self.main())
        self.assertIn("none logged since 2030-01-01", self.main("--since", "2030-01-01"))
        self.write(LOG, "2026-01-01 10:00 a error | boom\n")
        text = self.main()
        self.assertIn("1 logged", text)
        self.assertIn("a error | boom", text)
        self.assertNotIn("last:", self.main("--tail", "0"))
        data = json.loads(self.main("--json"))
        self.assertEqual((data["total"], data["last"][0]["detail"]), (1, "boom"))
        self.assertIn("log cleared", self.main("--clear"))
        self.assertIn("nothing to clear", self.main("--clear"))
        self.assertEqual(json.loads(self.main("--clear", "--json")), {"path": self.path(), "cleared": False})

    def test_brain_command_runs_it(self):
        self.write(LOG, "2026-01-01 10:00 a error | boom\n")
        r = subprocess.run([sys.executable, BRAIN, "errors"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("a error", r.stdout)


class HookLoggingTest(TempBrain):
    def logged(self):
        path = os.path.join(self.root, LOG)
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_a_crashing_hook_is_logged_and_still_exits_clean(self):
        self.write("cortex/concepts/a.md", page("concept", **VALID))
        r = self.run_hook("check_recall.py", {"transcript_path": os.path.join(self.root, "missing.jsonl")})
        self.assertEqual(r.returncode, 0)
        self.assertIn("check_recall error | ", self.logged())

    def test_prompt_recall_crash_is_logged(self):
        r = self.run_hook("prompt_recall.py", "not json", BRAIN_PROMPT_RECALL="1")
        self.assertEqual(r.returncode, 0)
        self.assertIn("prompt_recall error | ", self.logged())

    def test_refusals_are_logged(self):
        senses = os.path.join(self.root, "senses", "a.md")
        self.write("senses/a.md", "input")
        r = self.run_hook("protect_senses.py", {"tool_name": "Edit", "tool_input": {"file_path": senses}})
        self.assertEqual(r.returncode, 2)
        bad = self.write("cortex/concepts/bad.md", "no frontmatter at all\n")
        r = self.run_hook("validate_page.py", {"tool_input": {"file_path": bad}})
        self.assertEqual(r.returncode, 2)
        secret = self.write("cortex/concepts/s.md", page("concept", "key AKIAIOSFODNN7EXAMPLE\n", **VALID))
        r = self.run_hook("scan_secrets.py", {"tool_input": {"file_path": secret}})
        self.assertEqual(r.returncode, 2)
        r = self.run_hook("protect_log.py", {"tool_name": "Edit", "tool_input": {"file_path": "hippocampus/log.md"}})
        self.assertEqual(r.returncode, 2)
        text = self.logged()
        for source in ("protect_senses senses", "validate_page schema", "scan_secrets secret", "protect_log log"):
            self.assertIn(source, text)


if __name__ == "__main__":
    unittest.main()
