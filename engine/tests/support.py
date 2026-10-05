"""Shared fixtures for the engine tests: a throwaway brain, page builders, paths."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ENGINE, "lib"))
import vaultlib  # noqa: E402

HOOKS = os.path.join(ENGINE, "hooks")
SCRIPTS = os.path.join(ENGINE, "lib")
TODAY = datetime.date(2026, 10, 3)


def ago(days):
    return (TODAY - datetime.timedelta(days=days)).isoformat()


def page(page_type, body="", **fields):
    lines = [f"type: {page_type}"] + [f"{k}: {v}" for k, v in fields.items()]
    return "---\n" + "\n".join(lines) + "\n---\n" + body


class TempBrain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        for folder in vaultlib.MEMORY_DIRS:  # what makes a folder a brain
            os.makedirs(os.path.join(self.root, folder))
        self.write("CLAUDE.md", "# Brain\n\n## Tags\n\n`unverified` `disputed`\n\n## Log\n\n`not-a-tag`\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def log(self, *lines):
        self.write("hippocampus/log.md", page("log", "\n" + "\n".join(lines) + "\n"))

    def brain(self):
        return vaultlib.Vault(self.root, today=TODAY)

    def run_hook(self, name, payload, **env_vars):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.root, **env_vars)
        return subprocess.run([sys.executable, os.path.join(HOOKS, name)], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)


VALID = dict(title="A", created="2026-01-01", updated="2026-01-01", status="established")
DECIDED = dict(title="D", created="2026-01-01", updated="2026-01-01")
SKILLS = os.path.join(ENGINE, "skills")
BRAIN_CLAUDE = os.path.join(os.path.dirname(ENGINE), "CLAUDE.md")


def project(body="", **fields):
    fields = dict(dict(title="Launch", status="active", goal="ship it", due="2027-01-01"), **fields)
    return page("project", body, **fields)
