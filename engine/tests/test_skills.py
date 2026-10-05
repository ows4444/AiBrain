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
            self.assertRegex(self.skill(name), r"DATE recall ", name)

    def test_page_creating_skills_index_what_they_create(self):
        for name in ("ingest", "explore", "decide"):
            self.assertIn("index.md", self.skill(name), name)

    def everything(self):
        texts = {}
        for folder in ("skills", "agents"):
            for root, _, files in os.walk(os.path.join(ENGINE, folder)):
                for f in files:
                    if f.endswith(".md"):
                        with open(os.path.join(root, f), encoding="utf-8") as fh:
                            texts[os.path.relpath(os.path.join(root, f), ENGINE)] = fh.read()
        return texts

    def test_log_formats_use_known_operations(self):
        for name, text in self.everything().items():
            for op in re.findall(r"`DATE ([a-z-]+)", text):
                self.assertIn(op, vaultlib.OPS, f"{name}: DATE {op}")

    def test_introspect_flags_and_templates_exist(self):
        with open(os.path.join(SCRIPTS, "introspect.py"), encoding="utf-8") as fh:
            flags = set(re.findall(r"--([a-z]+)", fh.read()))
        for name, text in self.everything().items():
            for line in re.findall(r"brain introspect[^`\n]*", text):
                for flag in re.findall(r"--([a-z]+)", line):
                    self.assertIn(flag, flags, f"{name}: --{flag}")
            for tpl in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/templates/([\w./-]*)", text):
                self.assertTrue(os.path.exists(os.path.join(ENGINE, "templates", tpl)), f"{name}: {tpl}")

    def test_agent_skills_exist(self):
        for name, text in self.everything().items():
            for skill in re.findall(r"^skills: \[(.*)\]", text, re.M):
                for s in skill.split(","):
                    self.assertTrue(os.path.isdir(os.path.join(SKILLS, s.strip().split(":")[-1])), f"{name}: {s}")

    def test_descriptions_stay_short(self):
        # every description loads on every turn
        for name in os.listdir(SKILLS):
            m = re.search(r"^description:\s*(?:>-\s*\n)?(.*?)\n(?=[a-z-]+:|---)", self.skill(name), re.S | re.M)
            self.assertLessEqual(len(" ".join(m.group(1).split())), 380, name)


if __name__ == "__main__":
    unittest.main()
