"""`brain door`: a note saved in a synced folder away from the desk is in inbox/ at the next session. Run: brain test"""
import json
import os
import tempfile
from unittest import mock

from support import TempBrain, run_brain

import door  # noqa: E402  (support puts engine/lib on the path)


class Door(TempBrain):
    def setUp(self):
        super().setUp()
        self.beside = tempfile.TemporaryDirectory()
        self.addCleanup(self.beside.cleanup)
        self.synced = os.path.join(os.path.realpath(self.beside.name), "Brain Inbox")  # what the phone writes into
        os.makedirs(self.synced)
        self.write("inbox/README.md", "What this folder is for.\n")

    def save(self, name, text="A thought had on the train.\n"):
        with open(os.path.join(self.synced, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def inbox(self):
        return sorted(os.listdir(os.path.join(self.root, "inbox")))

    def brain_door(self, *args):
        r = run_brain(self.root, "door", *args)
        self.assertEqual((r.returncode, r.stderr), (0, ""), r.stderr)
        return r.stdout


class AwayFromTheDesk(Door):
    def test_a_note_saved_at_the_door_is_in_the_inbox_at_the_next_session(self):
        """Done when: a note taken away from the desk is in inbox/ at the next session."""
        self.assertEqual(self.brain_door(self.synced), f"door open: what is saved in {self.synced} comes into inbox/ at "
                                                       "the next session\n")
        self.assertEqual(os.readlink(os.path.join(self.root, "inbox", ".door")), self.synced)
        self.assertNotIn("Inbox:", self.run_hook("wake_up.py", {}).stdout)  # an empty door says nothing
        self.save("train.md")
        self.save("Scan 12.pdf", "%PDF")
        self.assertEqual(self.brain_door(), f"door: {self.synced}, 2 notes waiting there (the next session brings them in)\n")
        self.assertEqual(self.inbox(), [".door", "README.md"])  # looking moves nothing
        briefing = self.run_hook("wake_up.py", {}).stdout
        self.assertIn("Inbox: 2 notes waiting, 2 of them just in through the door (/ingest moves them into senses/)\n", briefing)
        self.assertEqual(self.inbox(), [".door", "README.md", "Scan 12.pdf", "train.md"])
        self.assertEqual(os.listdir(self.synced), [])  # moved, not copied: nothing comes in twice
        self.assertIn("Inbox: 2 notes waiting (/ingest moves them into senses/)\n", self.run_hook("wake_up.py", {}).stdout)
        sorted_notes = json.loads(run_brain(self.root, "inbox", "--json").stdout)
        self.assertEqual({row["note"]: row["kind"] for row in sorted_notes["notes"]},
                         {"inbox/Scan 12.pdf": "not_text", "inbox/train.md": "ready"})  # a note like any other from here

    def test_nothing_is_written_over_and_what_cannot_come_in_stays_and_is_said(self):
        self.brain_door(self.synced)
        self.write("inbox/train.md", "An earlier note of the same name.\n")
        self.write("inbox/train-2.md", "And another.\n")
        for name in ("train.md", "README.md", ".hidden.md", "half.md.tmp", "movie.mp4.part", "notes.icloud", "x.crdownload"):
            self.save(name)
        os.makedirs(os.path.join(self.synced, "A folder"))
        found = json.loads(run_brain(self.root, "door", "--pull", "--json").stdout)
        self.assertEqual(found, {"door": self.synced, "unreachable": False, "did": "pulled",
                                 "brought": ["inbox/train-3.md"], "left": ["A folder", "README.md"]})
        with open(os.path.join(self.root, "inbox", "train.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "An earlier note of the same name.\n")
        self.assertEqual(sorted(os.listdir(self.synced)), [".hidden.md", "A folder", "README.md", "half.md.tmp",
                                                           "movie.mp4.part", "notes.icloud", "x.crdownload"])
        self.assertIn("Door: 2 left there, not brought in (A folder, README.md)\n", self.run_hook("wake_up.py", {}).stdout)
        self.save("later.md")
        self.assertEqual(self.brain_door("--pull"), f"door: 1 notes brought into inbox/ from {self.synced}\n"
                                                    "  inbox/later.md\n  left there: A folder, README.md\n")
        self.assertEqual(self.brain_door(), f"door: {self.synced}, 0 notes waiting there (the next session brings them "
                                            "in)\n  left there: A folder, README.md\n")

    def test_a_file_that_cannot_be_moved_yet_waits_for_the_next_time(self):
        self.brain_door(self.synced)
        self.save("first.md")
        self.save("second.md")
        moved = door.shutil.move

        def not_yet(src, dst):
            if src.endswith("first.md"):
                raise PermissionError("not downloaded yet")
            return moved(src, dst)

        with mock.patch.object(door.shutil, "move", not_yet):
            found = door.pull(self.root)
        self.assertEqual((found["brought"], found["left"]), (["inbox/second.md"], ["first.md"]))
        self.assertEqual(door.pull(self.root)["brought"], ["inbox/first.md"])


class TheDoorItself(Door):
    def test_without_a_door_nothing_is_looked_for(self):
        self.assertEqual(self.brain_door(), "no door: `brain door FOLDER` opens one, for a folder that syncs to this machine\n")
        self.assertEqual(json.loads(run_brain(self.root, "door", "--pull", "--json").stdout),
                         {"door": None, "unreachable": False, "brought": [], "left": [], "did": "pulled"})
        self.assertEqual(self.brain_door("--close"), "no door was open\n")
        self.write("inbox/note.md", "A note.\n")
        self.assertIn("Inbox: 1 notes waiting (/ingest moves them into senses/)\n", self.run_hook("wake_up.py", {}).stdout)

    def test_it_is_moved_and_closed_and_the_folder_is_left_alone(self):
        other = os.path.join(os.path.realpath(self.beside.name), "Another")
        os.makedirs(other)
        self.brain_door(self.synced)
        self.save("kept.md")
        self.assertEqual(self.brain_door(other), f"door open: what is saved in {other} comes into inbox/ at the next "
                                                 f"session\n  it led to {self.synced} before\n")
        self.assertEqual(self.brain_door(other).count("\n"), 1)  # the same folder again: nothing to say about before
        self.assertEqual(self.brain_door("--close"), f"door closed: {other} and what is in it stay as they are\n")
        self.assertEqual(self.inbox(), ["README.md"])
        self.assertEqual(os.listdir(self.synced), ["kept.md"])
        self.assertTrue(os.path.isdir(other))

    def test_a_door_that_leads_nowhere_says_so_and_the_briefing_still_comes(self):
        self.brain_door(self.synced)
        self.write("inbox/note.md", "A note.\n")
        os.rmdir(self.synced)
        why = f"the door leads to {self.synced}, which cannot be read (not mounted, renamed, or closed to this program): " \
              "`brain door FOLDER` moves it\n"
        self.assertEqual(self.brain_door(), why)
        self.assertEqual(self.brain_door("--pull"), why)
        briefing = self.run_hook("wake_up.py", {}).stdout
        self.assertIn("Inbox: 1 notes waiting (/ingest moves them into senses/)\n"
                      f"Door: it leads to {self.synced}, which cannot be read (`brain door FOLDER` moves it)\n", briefing)
        self.assertIn("Last activity:", briefing)

    def test_what_is_not_a_door_is_refused(self):
        inside = os.path.join(self.root, "senses")
        os.makedirs(inside)
        missing = os.path.join(os.path.realpath(self.beside.name), "no such folder")
        for args, why in (([missing], f"not a folder: {missing}"),
                          ([inside], "that folder is inside this brain: the door leads in from somewhere else"),
                          ([self.synced, "--pull"], "one thing at a time: a FOLDER to open, --pull, or --close"),
                          (["--pull", "--close"], "one thing at a time: a FOLDER to open, --pull, or --close")):
            r = run_brain(self.root, "door", *args)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", f"brain door: {why}\n"))
        self.write("inbox/.door", "a file someone left under the door's name\n")
        r = run_brain(self.root, "door", self.synced)
        self.assertEqual((r.returncode, r.stderr), (1, "brain door: inbox/.door is there and is not a link: move it away first\n"))
        self.assertEqual(self.brain_door(), "no door: `brain door FOLDER` opens one, for a folder that syncs to this machine\n")
