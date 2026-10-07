"""The walls hold from a subfolder, whatever the case of the path, and for a shell that steps in first. Run: brain test"""
import filecmp
import json
import os
import subprocess
import sys
import unittest

from support import DECIDED, ENGINE, VALID, TempBrain, page, project, vaultlib

BRAIN = os.path.join(ENGINE, "bin", "brain")
TEMPLATE = os.path.join(ENGINE, "templates", "brain")
REPO = os.path.dirname(ENGINE)
FOLDS_CASE = sys.platform == "darwin"
FROZEN = page("decision", "\n## Expected\n\n- [hypothesis] it works\n", status="decided", review="2026-02-01",
              revisit_if="it breaks", **DECIDED)


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


class FromASubfolder(TempBrain):
    """A session opened in prefrontal/<name>/ is still inside its brain."""

    def setUp(self):
        super().setUp()
        self.sub = os.path.join(self.root, "prefrontal", "launch")
        os.makedirs(self.sub)
        self.input = self.write("senses/a.md", "hi\n")

    def hook(self, name, payload, *args, start=None):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=start or self.sub)
        return subprocess.run([sys.executable, os.path.join(ENGINE, "hooks", name), *args], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def test_find_brain_looks_upward_and_stops_at_the_top(self):
        self.assertEqual(vaultlib.find_brain(self.sub), os.path.realpath(self.root))
        self.assertEqual(vaultlib.find_brain(self.root), os.path.realpath(self.root))
        self.assertIsNone(vaultlib.find_brain(os.path.dirname(os.path.realpath(self.root))))

    def test_an_input_is_still_protected(self):
        edit = {"tool_name": "Edit", "tool_input": {"file_path": self.input, "old_string": "hi", "new_string": "x"}}
        self.assertEqual(self.hook("protect_senses.py", edit).returncode, 2)

    def test_a_relative_path_is_taken_from_where_the_session_started(self):
        edit = {"tool_name": "Edit", "tool_input": {"file_path": "../../senses/a.md", "old_string": "hi",
                                                    "new_string": "x"}}
        self.assertEqual(self.hook("protect_senses.py", edit).returncode, 2)
        self.assertEqual(self.hook("protect_senses.py", bash("cp /dev/null ../../senses/a.md")).returncode, 2)
        self.assertEqual(self.hook("protect_senses.py", bash("cp new.md ../../senses/new.md")).returncode, 0)

    def test_a_bad_page_is_still_blocked(self):
        write = {"tool_name": "Write", "tool_input": {"file_path": os.path.join(self.root, "cortex/concepts/bad.md"),
                                                      "content": "no frontmatter"}}
        r = self.hook("validate_page.py", write, "--pre")
        self.assertEqual(r.returncode, 2)
        self.assertIn("missing frontmatter", r.stderr)

    def test_a_frozen_expectation_is_still_frozen(self):
        path = self.write("cortex/decisions/d.md", FROZEN)
        edit = {"tool_name": "Edit", "tool_input": {"file_path": path, "old_string": "it works",
                                                    "new_string": "it fails"}}
        self.assertEqual(self.hook("protect_expected.py", edit).returncode, 2)

    def test_a_credential_is_still_reported(self):
        path = self.write("cortex/episodes/e.md", page("episode", "key AKIA" + "A" * 16 + "\n", **VALID))
        r = self.hook("scan_secrets.py", {"tool_name": "Write", "tool_input": {"file_path": path}})
        self.assertEqual(r.returncode, 2)

    def test_the_briefing_and_the_resume_note_are_the_brain_s(self):
        self.write("prefrontal/launch/CLAUDE.md", project())
        self.write("inbox/note.md", "a quick note")
        briefing = self.hook("wake_up.py", {}).stdout
        self.assertIn("Today:", briefing)
        self.assertIn("inbox", briefing.lower())
        r = self.hook("save_resume.py", {})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        note = os.path.join(self.root, "prefrontal", "launch", "process", "resume.md")
        with open(note, encoding="utf-8") as fh:
            self.assertIn("Active project: Launch (`prefrontal/launch/CLAUDE.md`)", fh.read())
        self.assertIn("Resume: read prefrontal/launch/process/resume.md first", self.hook("wake_up.py", {}).stdout)

    def test_outside_any_brain_the_hooks_stay_silent(self):
        outside = os.path.dirname(os.path.realpath(self.root))
        edit = {"tool_name": "Edit", "tool_input": {"file_path": self.input, "old_string": "hi", "new_string": "x"}}
        for name in ("protect_senses.py", "protect_expected.py", "validate_page.py", "scan_secrets.py", "wake_up.py",
                     "save_resume.py"):
            self.assertEqual(self.hook(name, edit, start=outside).returncode, 0, name)


@unittest.skipUnless(FOLDS_CASE, "only where the file system takes Cortex/ for cortex/")
class WhateverTheCase(TempBrain):
    def test_a_frozen_expectation(self):
        self.write("cortex/decisions/d.md", FROZEN)
        for path in ("Cortex/Decisions/d.md", "CORTEX/decisions/D.md"):
            edit = {"tool_name": "Edit", "tool_input": {"file_path": path, "old_string": "it works",
                                                        "new_string": "it fails"}}
            self.assertEqual(self.run_hook("protect_expected.py", edit).returncode, 2, path)

    def test_a_page_contract(self):
        for path in ("Cortex/concepts/bad.md", "CORTEX/concepts/bad.MD"):
            write = {"tool_name": "Write", "tool_input": {"file_path": path, "content": "no frontmatter"}}
            r = subprocess.run([sys.executable, os.path.join(ENGINE, "hooks", "validate_page.py"), "--pre"],
                               input=json.dumps(write), capture_output=True, text=True,
                               env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))
            self.assertEqual(r.returncode, 2, path)

    def test_a_credential(self):
        self.write("cortex/episodes/e.md", page("episode", "key AKIA" + "A" * 16 + "\n", **VALID))
        r = self.run_hook("scan_secrets.py", {"tool_name": "Write", "tool_input": {"file_path": "Cortex/episodes/e.md"}})
        self.assertEqual(r.returncode, 2)


class ShellAgainstSenses(TempBrain):
    def setUp(self):
        super().setUp()
        self.write("senses/a.md", "hi\n")

    def test_the_folder_itself_and_a_step_inside_are_blocked(self):
        for command in ("rm -r senses", "rm -rf ./senses", "cd senses && rm a.md", "pushd senses; unlink a.md",
                        "cd ./senses && mv a.md b.md", "mv senses old-senses", "echo x > senses"):
            self.assertEqual(self.run_hook("protect_senses.py", bash(command)).returncode, 2, command)

    def test_a_name_that_only_contains_the_word_is_not_the_folder(self):
        for command in ("rm senses-old.txt", "rm notes/senses.md", "rm my-senses", "cd senses && ls",
                        "ls senses", "cd cortex && rm -f x.tmp"):
            self.assertEqual(self.run_hook("protect_senses.py", bash(command)).returncode, 0, command)


class BrainTestRunsOnlyTheEngine(unittest.TestCase):
    def run_brain(self, *args):
        return subprocess.run([sys.executable, BRAIN, "test", *args], capture_output=True, text=True)

    def test_discovery_cannot_be_pointed_elsewhere(self):
        for args in (("-s", "/tmp"), ("-t", "/tmp"), ("-p", "*.py"), ("--start-directory=/tmp",), ("/tmp",),
                     ("-k",)):
            r = self.run_brain(*args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertIn("is not accepted", r.stderr, args)

    def test_a_name_filter_is_still_accepted(self):
        r = self.run_brain("-k", "test_a_name_that_matches_no_test_at_all")
        self.assertNotIn("is not accepted", r.stderr)
        self.assertIn("Ran 0 tests", r.stderr)


class InitialState(unittest.TestCase):
    """The brain this engine ships with is the template: what `install.sh --new` copies is what a clone holds."""

    STATE = ("OWNER.md", os.path.join("hippocampus", "index.md"), os.path.join("hippocampus", "log.md"),
             os.path.join("hippocampus", "metrics.md"), os.path.join("hippocampus", "fingerprints.md"),
             os.path.join("hippocampus", "intentions.md"))

    def template_files(self):
        for dirpath, _, files in os.walk(TEMPLATE):
            for f in files:
                yield os.path.relpath(os.path.join(dirpath, f), TEMPLATE)

    def differing(self, wanted):
        return sorted(rel for rel in self.template_files() if wanted(rel)
                      and not (os.path.isfile(os.path.join(REPO, rel))
                               and filecmp.cmp(os.path.join(TEMPLATE, rel), os.path.join(REPO, rel), shallow=False)))

    def test_rules_and_folder_notes_match_the_template(self):
        self.assertEqual(self.differing(lambda rel: rel not in self.STATE), [])

    def test_an_unused_brain_matches_the_template(self):
        # Once anything is logged the brain is in use, and its owner, index and log are its own.
        if not vaultlib.is_brain(REPO) or vaultlib.read_events(REPO):
            self.skipTest("this brain is in use")
        self.assertEqual(self.differing(lambda rel: rel in self.STATE), [])


if __name__ == "__main__":
    unittest.main()
