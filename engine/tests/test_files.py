"""A file that is rewritten is written whole: beside the target, then moved onto it. Run: brain test"""
import datetime
import os
import stat
import tempfile
import unittest
from unittest import mock

from support import TODAY, TempBrain, page, run_brain

import files  # noqa: E402  (support puts engine/lib on the path)
import forget  # noqa: E402
import index  # noqa: E402
import tend  # noqa: E402

DATES = dict(created="2026-01-01", updated="2026-01-01")


class WriteWhole(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = self.tmp.name
        self.path = os.path.join(self.folder, "index.md")

    def text(self, path=None):
        with open(path or self.path, encoding="utf-8") as fh:
            return fh.read()

    def test_a_file_that_is_not_there_is_made_and_one_that_is_takes_the_new_text(self):
        files.write_whole(self.path, "first\n")
        self.assertEqual(self.text(), "first\n")
        files.write_whole(self.path, "second, and longer\n")
        self.assertEqual(self.text(), "second, and longer\n")
        files.write_whole(self.path, "")  # shorter than what was there: nothing of the old text is left
        self.assertEqual(self.text(), "")
        self.assertEqual(os.listdir(self.folder), ["index.md"])  # the file written beside it is gone

    def test_the_target_keeps_its_permissions_and_a_link_is_followed(self):
        files.write_whole(self.path, "first\n")
        os.chmod(self.path, 0o640)
        files.write_whole(self.path, "second\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o640)
        link = os.path.join(self.folder, "link.md")
        os.symlink(self.path, link)
        files.write_whole(link, "through the link\n")
        self.assertTrue(os.path.islink(link))  # the link stands: the file it names was replaced
        self.assertEqual((self.text(), self.text(link)), ("through the link\n", "through the link\n"))
        self.assertEqual(sorted(os.listdir(self.folder)), ["index.md", "link.md"])

    def test_the_encoding_and_how_it_treats_what_it_cannot_write_are_the_caller_s(self):
        with open(self.path, "wb") as fh:
            fh.write(b"caf\xe9, as it was\n")  # no UTF-8
        with open(self.path, encoding="utf-8", errors="surrogateescape") as fh:
            read = fh.read()
        files.write_whole(self.path, read + "more\n", errors="surrogateescape")
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), b"caf\xe9, as it was\nmore\n")  # the byte came back as it was
        files.write_whole(self.path, "café\n", encoding="latin-1")
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), b"caf\xe9\n")

    def test_a_write_that_fails_leaves_the_target_as_it_was_and_nothing_beside_it(self):
        files.write_whole(self.path, "whole\n")
        with self.assertRaises(UnicodeEncodeError):  # a byte read back as it was cannot be written as UTF-8 proper
            files.write_whole(self.path, "half of it, then \udce9")
        self.assertEqual((self.text(), os.listdir(self.folder)), ("whole\n", ["index.md"]))
        with mock.patch.object(files.os, "replace", side_effect=OSError("the disk is full")):  # written, and not moved
            with self.assertRaises(OSError):
                files.write_whole(self.path, "all of it\n")
        self.assertEqual((self.text(), os.listdir(self.folder)), ("whole\n", ["index.md"]))
        with self.assertRaises(FileNotFoundError):  # no folder to write beside it in: nothing is made
            files.write_whole(os.path.join(self.folder, "none", "index.md"), "x")
        self.assertEqual(os.listdir(self.folder), ["index.md"])

    def test_a_reader_never_finds_a_part_of_the_file(self):
        files.write_whole(self.path, "old\n")
        seen, replace = [], os.replace

        def looks_first(beside, path):
            seen.append((self.text(), self.text(beside), os.path.dirname(beside) == os.path.dirname(path)))
            replace(beside, path)

        with mock.patch.object(files.os, "replace", side_effect=looks_first):
            files.write_whole(self.path, "new\n")
        # Until the one step that moves it, the target is the old file whole; the new one stands whole beside it.
        self.assertEqual((seen, self.text()), ([("old\n", "new\n", True)], "new\n"))


class WrittenWhole(TempBrain):
    """The files the engine rewrites from start to end: the index, twice, and what --notify has said today."""

    def setUp(self):
        super().setUp()
        self.path = os.path.join(self.root, index.INDEX)
        with open(index.TEMPLATE, encoding="utf-8") as fh:
            self.write(index.INDEX, fh.read() + "\n## Mine\n\nA section of the owner's own.\n")
        self.write("senses/cepeda.md", "the paper\n")
        self.write("cortex/episodes/cepeda-2006.md", page("episode", title="Cepeda 2006", input="senses/cepeda.md",
                                                          **DATES))
        self.write("cortex/concepts/spacing-effect.md", page("concept", "As [[cepeda-2006]] found.\n",
                                                             title="Spacing effect", status="established", **DATES))

    def text(self):
        with open(self.path, encoding="utf-8") as fh:
            return fh.read()

    def beside(self, folder):
        return [name for name in os.listdir(os.path.join(self.root, folder)) if name.endswith(".tmp")]

    def test_an_index_that_cannot_be_finished_is_left_as_it_was(self):
        before = self.text()
        with mock.patch.object(files.os, "replace", side_effect=OSError("it died here")):
            with self.assertRaises(OSError):
                index.rebuild(self.root, today=TODAY)
        self.assertEqual((self.text(), self.beside("hippocampus")), (before, []))  # not emptied, not short
        self.assertTrue(index.rebuild(self.root, today=TODAY)["written"])
        self.assertIn("- [[spacing-effect]]\n", self.text())
        self.assertTrue(self.text().endswith("\n## Mine\n\nA section of the owner's own.\n"))
        self.assertEqual(self.beside("hippocampus"), [])

    def test_forgetting_a_source_takes_its_line_out_of_the_index_in_one_step(self):
        index.rebuild(self.root, today=TODAY)
        self.write(index.INDEX, self.text() + "\nSee also [[cepeda-2006]], by hand.\n")  # a line outside the listing
        wrote, write_whole = [], files.write_whole

        def recorded(path, text, **how):
            wrote.append((os.path.relpath(path, self.root), "cepeda-2006" in text, how))
            write_whole(path, text, **how)

        with mock.patch.object(forget, "write_whole", side_effect=recorded):
            forget.apply(self.brain(), forget.report(self.brain(), "senses/cepeda.md"), datetime.datetime.now())
        self.assertEqual(wrote, [(index.INDEX, False, {"errors": index.AS_IT_IS})])  # whole, and byte for byte
        self.assertNotIn("cepeda-2006", self.text())
        self.assertEqual(self.beside("hippocampus"), [])

    def test_the_commands_leave_no_file_beside_the_ones_they_wrote(self):
        self.assertEqual(run_brain(self.root, "index").returncode, 0)
        self.assertEqual(run_brain(self.root, "forget", "senses/cepeda.md", "--yes").returncode, 0)
        self.assertEqual(run_brain(self.root, "resume").returncode, 0)
        tend.announcements(self.root, tend.digest(self.brain()))
        tend.announcements(self.root, tend.digest(self.brain()))  # read back, and written again
        self.assertLessEqual({"notified.json", "resume.md"}, set(os.listdir(os.path.join(self.root, ".cache"))))
        self.assertEqual([self.beside(folder) for folder in ("hippocampus", ".cache")], [[], []])
