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
BRAIN = os.path.join(ENGINE, "bin", "brain")
TODAY = datetime.date(2026, 10, 3)


def run_brain(root, *args, env=None, **kw):
    """`brain ARGS` on the brain at `root` (None: a command that needs none), in a process of its own."""
    env = {k: v for k, v in (os.environ if env is None else env).items() if k != "BRAIN_ROOT"}
    if root is not None:
        env["BRAIN_ROOT"] = root
    return subprocess.run([sys.executable, BRAIN, *args], capture_output=True, text=True, env=env, **kw)


def tool(folder, name, body):
    """An executable `name` in `folder` that runs `body` as Python: a stand-in for a system tool on the PATH."""
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name + ".py"), "w", encoding="utf-8") as fh:
        fh.write(body)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        fh.write(f"#!/bin/sh\nexec '{sys.executable}' '{os.path.join(folder, name)}.py' \"$@\"\n")
    os.chmod(os.path.join(folder, name), 0o755)
    return folder


# What `pdftotext FILE -` and `tesseract FILE stdout` do, as far as the engine relies on it: the text of the
# file on stdout, a form feed after each page. Here the "PDF" is its own text; BROKEN and SILENT are files
# the tool fails on, with and without a word on stderr. Arguments it does not expect are an error.
READER = """import os, sys
args = sys.argv[1:]
right = args[:4] + args[5:] == ["-enc", "UTF-8", "-eol", "unix", "-"] if "NAME" == "pdftotext" else args[1:] == ["stdout"]
if not right:
    sys.exit("unexpected arguments: " + " ".join(args))
data = open(next(a for a in args if os.path.isfile(a)), "rb").read()
if data.startswith(b"BROKEN"):
    sys.exit("Syntax Error: Couldn't read xref table\\nand more of the same")
if data.startswith(b"SILENT"):
    sys.exit(3)
sys.stdout.buffer.write(data)
"""


def readers(folder):
    """A folder for the PATH holding stand-ins for the two tools `brain extract` calls."""
    for name in ("pdftotext", "tesseract"):
        tool(folder, name, READER.replace("NAME", name))
    return folder


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
