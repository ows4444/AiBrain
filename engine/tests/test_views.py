"""`brain introspect` says what each of its views is, and the views that say they only read move nothing:
measuring the briefing brings no note in through the door. Run: brain test"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from support import HOOKS, SCRIPTS, TempBrain, run_brain

sys.path.insert(0, SCRIPTS)
import bench  # noqa: E402
import introspect  # noqa: E402

FLAGS = [*introspect.FLAG_VIEWS, "graph", "snapshot", "context"]


class EveryViewSaysWhatItIs(TempBrain):
    def test_help_gives_each_flag_the_words_the_module_has_for_it(self):
        said = introspect.flag_help()
        self.assertEqual(sorted(said), sorted(FLAGS))  # every flag is described above the code, and nothing else is
        self.assertEqual(said["tags"], "every tag in use with its count")
        self.assertEqual(said["stale"], "concept pages untouched for 90+ days, oldest first")
        self.assertTrue(said["queue"].startswith("episodes and reviewed decisions awaiting consolidation, and candidate "
                                                 "ideas by how many distinct sources name them (two or more is the bar"))
        self.assertTrue(said["context"].endswith("is not visible here: `/context` in Claude Code shows it"))  # the last
        for flag, text in said.items():
            self.assertEqual((text, "  " in text), (text.strip(), False), flag)  # one line, folded
        # argparse wraps a help text to the terminal, and breaks a word at its hyphen: a wide one keeps each whole.
        r = run_brain(self.root, "introspect", "--help", env=dict(os.environ, COLUMNS="100000"))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout.split()[:4], ["usage:", "brain", "introspect", "[-h]"])
        shown = [" ".join(line.split()) for line in r.stdout.splitlines()]
        for flag in FLAGS:
            self.assertIn(f"--{flag} {said[flag]}", shown, flag)
        self.assertIn("under 5% of the pages hold", r.stdout)  # a per cent sign in a help text is printed as one

    def test_the_text_of_a_view_is_written_once(self):
        with open(os.path.join(SCRIPTS, "introspect.py"), encoding="utf-8") as fh:
            source = fh.read()
        for flag, text in introspect.flag_help().items():  # in the text above the code, and nowhere in the code
            self.assertEqual(source.count(text[:40]), 1, flag)


class MeasuringTheBriefingMovesNothing(TempBrain):
    """`--context` and `--snapshot` run the session's own hook to size the briefing; that hook brings notes in."""

    def setUp(self):
        super().setUp()
        self.beside = tempfile.TemporaryDirectory()
        self.addCleanup(self.beside.cleanup)
        self.synced = os.path.join(os.path.realpath(self.beside.name), "Synced")
        os.makedirs(self.synced)
        self.assertEqual(run_brain(self.root, "door", self.synced).returncode, 0)
        with open(os.path.join(self.synced, "train.md"), "w", encoding="utf-8") as fh:
            fh.write("A thought had on the train.\n")

    def moved(self):
        """(what is at the door, what is in inbox/ beside the door's own link)."""
        return os.listdir(self.synced), [f for f in os.listdir(os.path.join(self.root, "inbox")) if f != ".door"]

    def test_the_views_that_measure_it_leave_the_note_at_the_door(self):
        for args in (("--context",), ("--context", "--json"), ("--snapshot",), ("--snapshot", "--context")):
            r = run_brain(self.root, "introspect", *args)
            self.assertEqual((r.returncode, r.stderr), (0, ""), args)
            self.assertEqual(self.moved(), (["train.md"], []), args)
        counted = json.loads(run_brain(self.root, "introspect", "--context", "--json").stdout)["context"]["every_session"]
        briefing = introspect.wake_up_output(self.root)
        self.assertEqual(counted[-1], introspect.measure("wake-up briefing", briefing))  # the briefing was run, and sized
        self.assertIn("\nDoor: 1 notes waiting there (the next session brings them in)\n", briefing)
        self.assertEqual(self.moved(), (["train.md"], []))
        # A session's own start does bring it in: the same hook, with no switch.
        self.assertIn("Inbox: 1 notes waiting, 1 of them just in through the door", self.run_hook("wake_up.py", {}).stdout)
        self.assertEqual(self.moved(), ([], ["train.md"]))

    def test_bench_times_the_briefing_the_same_way(self):
        ran = []
        with mock.patch.object(bench, "process", lambda root, command, payload=None: ran.append(command) or 0):
            rows = bench.hook_rows(self.root, 1)
        self.assertEqual(ran[0], [os.path.join(HOOKS, "wake_up.py"), "--look"])
        self.assertEqual((rows[0]["what"], rows[0]["exit"]), ("wake_up (session start)", 0))
        self.assertEqual(bench.process(self.root, ran[0]), 0)  # and run for real, it moves nothing
        self.assertEqual(self.moved(), (["train.md"], []))


if __name__ == "__main__":
    unittest.main()
