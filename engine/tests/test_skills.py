"""The skills are instructions, but their wiring to the engine can be checked. Run: brain test"""
import os
import re
import sys
import unittest

from support import ENGINE, HOOKS, SCRIPTS, SKILLS, vaultlib


class SkillWiring(unittest.TestCase):
    """The skills are instructions, but their connections to the engine can still be checked."""

    def skill(self, name):
        with open(os.path.join(SKILLS, name, "SKILL.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_every_recall_skill_says_how_to_log_recall(self):
        sys.path.insert(0, HOOKS)
        import check_recall
        for name in check_recall.RECALL_SKILLS:
            self.assertRegex(self.skill(name), r"brain log recall ", name)

    def test_every_skill_that_records_an_operation_names_the_command(self):
        # commit, start and tend write no line of their own: the skills and agents they run do.
        for name in sorted(set(os.listdir(SKILLS)) - {"commit", "start", "tend"}):
            self.assertIn("`brain log ", self.skill(name), name)

    def test_page_creating_skills_index_what_they_create(self):
        for name in ("ingest", "explore", "decide", "sleep"):
            self.assertIn("`brain index`", self.skill(name), name)
        for name in os.listdir(SKILLS):  # the listing is the command's: no skill adds a line to it by hand
            self.assertNotRegex(self.skill(name), r"(add|remove)[^.]*\b(to|from) the index", name)

    def everything(self):
        texts = {}
        for folder in ("skills", "agents"):
            for root, _, files in os.walk(os.path.join(ENGINE, folder)):
                for f in files:
                    if f.endswith(".md"):
                        with open(os.path.join(root, f), encoding="utf-8") as fh:
                            texts[os.path.relpath(os.path.join(root, f), ENGINE)] = fh.read()
        return texts

    def test_log_lines_are_written_by_the_command_with_a_known_operation(self):
        for name, text in self.everything().items():
            self.assertNotRegex(text, r"`DATE [a-z]", f"{name} writes a log line by hand: the command is `brain log`")
            for op in re.findall(r"brain log ([a-z-]+)", text):
                self.assertIn(op, vaultlib.OPS, f"{name}: brain log {op}")

    def test_introspect_flags_and_templates_exist(self):
        with open(os.path.join(SCRIPTS, "introspect.py"), encoding="utf-8") as fh:
            flags = set(re.findall(r"--([a-z]+)", fh.read()))
        for name, text in self.everything().items():
            for line in re.findall(r"brain introspect[^`\n]*", text):
                for flag in re.findall(r"--([a-z]+)", line):
                    self.assertIn(flag, flags, f"{name}: --{flag}")
            for tpl in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/templates/([\w./-]*)", text):
                self.assertTrue(os.path.exists(os.path.join(ENGINE, "templates", tpl)), f"{name}: {tpl}")

    def test_input_is_data_wherever_input_is_read(self):
        for rel in (os.path.join("skills", "ingest", "SKILL.md"), os.path.join("agents", "encoder.md")):
            with open(os.path.join(ENGINE, rel), encoding="utf-8") as fh:
                text = " ".join(fh.read().split())
            for fragment in ("Injected:", "ignore rules", "never"):
                self.assertIn(fragment, text, rel)

    def test_every_agent_names_its_model(self):
        # Scanning and counting on the smallest, writing from one input on the middle one, judging and
        # synthesis on the session's own. A cheaper model saves quota and time, not context.
        expected = {"curator": "haiku", "graph-analyst": "haiku", "watcher": "haiku", "encoder": "sonnet",
                    "reviewer": "sonnet", "consolidator": "inherit", "critic": "inherit", "researcher": "inherit"}
        found = {}
        for name in sorted(os.listdir(os.path.join(ENGINE, "agents"))):
            with open(os.path.join(ENGINE, "agents", name), encoding="utf-8") as fh:
                found[name[:-3]] = (re.search(r"^model: (\S+)$", fh.read().split("---")[1], re.M) or [None, None])[1]
        self.assertEqual(found, expected)

    def test_agent_skills_exist(self):
        for name, text in self.everything().items():
            for skill in re.findall(r"^skills: \[(.*)\]", text, re.M):
                for s in skill.split(","):
                    self.assertTrue(os.path.isdir(os.path.join(SKILLS, s.strip().split(":")[-1])), f"{name}: {s}")

    def test_descriptions_stay_short(self):
        # every description loads on every turn
        for name in os.listdir(SKILLS):
            m = re.search(r"^description:\s*(?:>-\s*\n)?(.*?)\n(?=[a-z-]+:|---)", self.skill(name), re.S | re.M)
            self.assertLessEqual(len(" ".join(m.group(1).split())), 201, name)


if __name__ == "__main__":
    unittest.main()
