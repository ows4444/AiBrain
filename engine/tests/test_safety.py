"""Trust: the schema bypass, the recall hook's holes, frozen expectations, fingerprints, credentials,
pre-write validation and the templates. Run: brain test"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import DECIDED, ENGINE, SCRIPTS, TempBrain, page, run_brain, vaultlib


def check(root, *args):
    r = run_brain(root, "check", "--json", *args)
    return r.returncode, json.loads(r.stdout)


class SchemaBypass(TempBrain):
    """F1: a system type is accepted only at its own file."""

    def test_system_type_elsewhere_is_a_problem(self):
        self.assertEqual(vaultlib.schema_problems(page("index"), rel="hippocampus/index.md"), [])
        problems = vaultlib.schema_problems(page("index"), stem="Bad Name", rel="cortex/notes.md")
        self.assertEqual(len(problems), 1)
        self.assertIn("type 'index' belongs only to hippocampus/index.md", problems[0])
        self.assertIn("belongs only to prefrontal",
                      vaultlib.schema_problems(page("project"), rel="cortex/concepts/x.md")[0])

    def test_the_brain_and_the_hook_both_refuse_it(self):
        path = self.write("cortex/notes.md", page("index", "[[ghost]]\n## Gaps\n- [[ghost]]\n"))
        v = self.brain()
        notes = v.resolve("notes")
        self.assertEqual(notes.type, "untyped")  # not a system page: it is in the graph and checked
        self.assertIn(notes, v.knowledge)
        self.assertEqual({t for _, t in v.broken}, {"ghost"})  # and its Gaps section whitelists nothing
        code, report = check(self.root)
        self.assertEqual((code, [s["page"] for s in report["schema"]]), (1, ["cortex/notes.md"]))
        hook = self.run_hook("validate_page.py", {"tool_input": {"file_path": path}})
        self.assertEqual(hook.returncode, 2)
        self.assertIn("belongs only to hippocampus/index.md", hook.stderr)


class PreWrite(TempBrain):
    """F10: a page that breaks the contract is stopped before it lands."""

    def pre(self, tool, **args):
        return self.run_hook("validate_page.py", {"tool_name": tool, "tool_input": args}).returncode

    def run_hook(self, name, payload, **env_vars):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.root, **env_vars)
        return subprocess.run([sys.executable, os.path.join(ENGINE, "hooks", name), "--pre"],
                              input=json.dumps(payload), capture_output=True, text=True, env=env)

    def test_a_bad_new_page_is_blocked_and_nothing_is_written(self):
        path = os.path.join(self.root, "cortex", "concepts", "a.md")
        self.assertEqual(self.pre("Write", file_path=path, content=page("concept", title="A")), 2)
        self.assertFalse(os.path.exists(path))
        good = page("concept", **dict(DECIDED, status="emerging"))
        self.assertEqual(self.pre("Write", file_path=path, content=good), 0)

    def test_a_broken_page_can_be_fixed_one_step_at_a_time(self):
        path = self.write("cortex/concepts/a.md", page("concept", title="A"))  # no dates, no status
        self.assertEqual(self.pre("Edit", file_path=path, old_string="title: A", new_string="title: A\nstatus: emerging"), 0)
        self.assertEqual(self.pre("Edit", file_path=path, old_string="title: A", new_string="title: A\nkind: tool"), 2)


class RecallHook(TempBrain):
    def transcript(self, *entries):
        return self.write("t.jsonl", "\n".join(json.dumps(e) for e in entries))

    @staticmethod
    def prompt(text):
        return {"type": "user", "message": {"content": text}}

    @staticmethod
    def tool(name, **args):
        return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": args}]}}

    def stops(self, *entries):
        r = self.run_hook("check_recall.py", {"transcript_path": self.transcript(*entries)})
        return r.returncode == 2

    def test_reading_the_log_is_not_logging(self):
        # F3: an earlier recall line today used to satisfy any later turn that merely named the log
        import datetime
        self.log(f"{datetime.date.today().isoformat()} recall an earlier question -> [[a]]")
        self.assertTrue(self.stops(self.prompt("q"), self.tool("Skill", skill="aibrain:ask"),
                                   self.tool("Bash", command="tail -3 hippocampus/log.md")))
        self.assertTrue(self.stops(self.prompt("q"), self.tool("Skill", skill="aibrain:ask"),
                                   self.tool("Bash", command='echo "$(date +%F) recall another -> [[b]]" >> '
                                                             'hippocampus/log.md')))  # claimed, not in the log

    def test_answering_from_pages_without_a_skill_must_log(self):
        # F4: reading memory to answer is a recall, skill or not
        read = self.tool("Read", file_path=os.path.join(self.root, "cortex", "concepts", "a.md"))
        self.assertTrue(self.stops(self.prompt("what do I know about a"), read))
        self.assertFalse(self.stops(self.prompt("q"), read, self.tool(
            "Edit", file_path="hippocampus/log.md", new_string="2026-10-03 recall a -> [[a]]\n")))
        self.assertFalse(self.stops(self.prompt("fix it"), read, self.tool("Edit", file_path="cortex/concepts/a.md")))
        self.assertFalse(self.stops(self.prompt("<command-name>/aibrain:sleep</command-name>"), read))
        self.assertFalse(self.stops(self.prompt("x"), self.tool("Read", file_path="engine/lib/vaultlib.py")))


class FrozenExpectation(TempBrain):
    """F5: a decided page's Expected rewritten outside the Edit tool fails brain check."""

    def git(self, *args):
        subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       capture_output=True, check=True)

    def test_shell_rewrite_and_reopening_are_caught(self):
        fields = dict(DECIDED, status="decided", review="2027-01-01", revisit_if="x")
        body = "## Expected\n- [hypothesis] Few leave.\n## Decision\n- [decision] Raise.\n"
        path = self.write("cortex/decisions/raise.md", page("decision", body, **fields))
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "one")
        self.assertEqual(check(self.root)[1]["history"], [])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(page("decision", body.replace("Few", "Many"), **fields))
        code, report = check(self.root)
        self.assertEqual((code, report["history"]),
                         (1, ["cortex/decisions/raise.md: its frozen ## Expected was rewritten since the last commit"]))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(page("decision", body, **dict(fields, status="open")))
        self.assertIn("reopened", check(self.root)[1]["history"][0])


class Fingerprints(TempBrain):
    def fingerprint(self):
        return run_brain(self.root, "fingerprint", "--json")

    def test_an_edited_input_fails_without_git(self):
        kept = self.write("senses/a.md", "as it arrived")
        self.write("senses/README.md", "docs")
        self.assertEqual(json.loads(self.fingerprint().stdout)["recorded"], ["senses/a.md"])
        self.assertEqual(json.loads(self.fingerprint().stdout)["recorded"], [])  # recorded once
        self.assertEqual(check(self.root)[1]["history"], [])
        self.assertEqual(self.brain().schema_problems(), [])  # the file is a valid system page
        with open(kept, "w", encoding="utf-8") as fh:
            fh.write("edited")
        self.fingerprint()  # running it again cannot bless the change
        code, report = check(self.root)
        self.assertEqual((code, report["history"]), (1, ["senses/a.md: input changed since it was fingerprinted"]))
        os.remove(kept)
        self.assertEqual(check(self.root)[1]["history"], ["senses/a.md: input removed since it was fingerprinted"])


class Credentials(TempBrain):
    KEY = "AKIA" + "ABCDEFGHIJKLMNOP"  # split so this file itself is not a finding

    def test_scan_names_kind_and_line_never_the_value(self):
        sys.path.insert(0, SCRIPTS)
        import secret_scan
        found = secret_scan.scan_text(f"intro\nkey = {self.KEY}\nmail me at someone@example.com\n")
        self.assertEqual(found, [("AWS access key", "critical", 2), ("email address", "personal", 3)])
        self.assertEqual(secret_scan.scan_text("sk-ant-" + "x" * 30)[0][0], "Anthropic API key")
        self.assertEqual(secret_scan.scan_text("postgres://admin:hunter22@db.internal/app")[0][0],
                         "connection string with password")
        self.assertEqual(secret_scan.scan_text("A normal note about keys and passwords."), [])

    def test_hook_and_guard(self):
        path = self.write("senses/paste.md", f"token {self.KEY}\n")
        hook = self.run_hook("scan_secrets.py", {"tool_input": {"file_path": path}})
        self.assertEqual(hook.returncode, 2)
        self.assertIn("AWS access key on line 1", hook.stderr)
        self.assertNotIn(self.KEY, hook.stderr)
        clean = self.write("cortex/concepts/a.md", page("concept", "write to me@example.com"))
        self.assertEqual(self.run_hook("scan_secrets.py", {"tool_input": {"file_path": clean}}).returncode, 0)
        self.assertEqual(check(self.root)[1].get("secrets"), [])  # only scanned with --guard
        code, report = check(self.root, "--guard")
        self.assertEqual((code, report["secrets"], report["personal"]),
                         (1, ["senses/paste.md:1: AWS access key"], ["cortex/concepts/a.md:4: email address"]))


class Templates(unittest.TestCase):
    """F9: every page template, filled in, passes the contract; a new brain passes brain check."""

    def test_every_template_fills_into_a_valid_page(self):
        folder = os.path.join(ENGINE, "templates")
        for name in ("episode", "concept", "entity", "insight", "decision"):
            with open(os.path.join(folder, f"{name}.md"), encoding="utf-8") as fh:
                text = fh.read()
            text = re.sub(r"^title:\s*$", "title: Filled", text, flags=re.M)
            text = re.sub(r"^(created|updated):\s*$", r"\1: 2026-10-03", text, flags=re.M)
            text = text.replace("kind: person | org | product | tool", "kind: tool")
            self.assertEqual(vaultlib.schema_problems(text, vocabulary=None, stem="filled",
                                                      rel=f"cortex/{name}s/filled.md"), [], name)

    def test_a_new_brain_passes_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            brain = os.path.join(tmp, "b")
            shutil.copytree(os.path.join(ENGINE, "templates", "brain"), brain)
            code, report = check(brain, "--guard")
            self.assertEqual((code, report["schema"], report["secrets"]), (0, [], []))
            v = vaultlib.Vault(brain)
            self.assertEqual(sorted(p.type for p in v.pages),
                             ["fingerprints", "index", "intentions", "log", "metrics", "tuning"])


if __name__ == "__main__":
    unittest.main()
