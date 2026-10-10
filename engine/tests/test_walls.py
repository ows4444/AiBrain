"""The walls hold from a subfolder, whatever the case of the path, and for a shell that steps in first;
one process runs every wall of an event, and a wall that fails does not open the others. Run: brain test"""
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from support import DECIDED, ENGINE, HOOKS, VALID, TempBrain, page, project, vaultlib

sys.path.insert(0, HOOKS)
import errlog  # noqa: E402  (support puts engine/lib on the path)
import gate  # noqa: E402
import link_check  # noqa: E402
import protect_log  # noqa: E402
import shared  # noqa: E402

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

    def test_the_log_is_still_written_only_by_its_command(self):
        log = self.write("hippocampus/log.md", "---\ntype: log\n---\n")
        line = "2026-10-03 recall q -> [[a]]\n"
        for payload in ({"tool_name": "Edit", "tool_input": {"file_path": log, "old_string": "", "new_string": line}},
                        {"tool_name": "Write", "tool_input": {"file_path": "../../hippocampus/log.md", "content": line}},
                        {"tool_name": "MultiEdit", "tool_input": {"file_path": log, "edits": [{"new_string": line}]}}):
            r = self.hook("protect_log.py", payload)
            self.assertEqual(r.returncode, 2, payload)
            self.assertIn("Run `brain log <operation> <what> --pages <page> ...", r.stderr)
        self.assertEqual(self.hook("protect_log.py", payload, start=self.root).returncode, 2)  # the brain itself
        with open(os.path.join(self.root, ".cache", "errors.log"), encoding="utf-8") as fh:
            self.assertIn(" protect_log log | Blocked: hippocampus/log.md is append-only", fh.read())
        for quiet in ({"tool_name": "Read", "tool_input": {"file_path": log}},
                      {"tool_name": "Bash", "tool_input": {"command": "tail hippocampus/log.md"}},
                      {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(self.root, "hippocampus/index.md")}},
                      {"tool_name": "Write", "tool_input": {"file_path": os.path.join(self.root, "motor/log.md")}},
                      {"tool_name": "Edit", "tool_input": {}}, {"tool_name": "Edit"}):
            self.assertEqual(self.hook("protect_log.py", quiet).returncode, 0, quiet)
        r = subprocess.run([sys.executable, os.path.join(ENGINE, "hooks", "protect_log.py")], input="not json",
                           capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))
        self.assertEqual(r.returncode, 0)  # input it cannot read is not a reason to stop a write

    def test_outside_any_brain_the_hooks_stay_silent(self):
        outside = os.path.dirname(os.path.realpath(self.root))
        edit = {"tool_name": "Edit", "tool_input": {"file_path": self.input, "old_string": "hi", "new_string": "x"}}
        self.assertEqual(self.hook("protect_log.py", {"tool_name": "Edit", "tool_input": {
            "file_path": os.path.join(self.root, "hippocampus", "log.md")}}, start=outside).returncode, 0)
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

    def test_the_log(self):
        self.write("hippocampus/log.md", "---\ntype: log\n---\n")
        for path in ("Hippocampus/log.md", "HIPPOCAMPUS/Log.MD"):
            edit = {"tool_name": "Edit", "tool_input": {"file_path": path, "old_string": "", "new_string": "x"}}
            self.assertEqual(self.run_hook("protect_log.py", edit).returncode, 2, path)


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


class OneProcessForEachEvent(TempBrain):
    """gate.py runs every wall of an event in turn, and says what each would have said on its own."""

    PRE = (("protect_senses.py",), ("protect_log.py",), ("protect_expected.py",), ("validate_page.py", "--pre"))
    POST = (("validate_page.py",), ("scan_secrets.py",))

    def setUp(self):
        super().setUp()
        self.input = self.write("senses/a.md", "as it arrived\n")
        self.log_path = self.write("hippocampus/log.md", "---\ntype: log\n---\n")
        self.decision = self.write("cortex/decisions/d.md", FROZEN)
        self.bad = self.write("cortex/concepts/bad.md", "no frontmatter, and a key AKIA" + "A" * 16 + "\n")
        self.good = self.write("cortex/concepts/good.md", page("concept", **VALID))

    def hook(self, payload, name, *args, raw=None, start=None):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=start or self.root)
        return subprocess.run([sys.executable, os.path.join(HOOKS, name), *args], capture_output=True, text=True,
                              input=json.dumps(payload) if raw is None else raw, env=env)

    def logged(self):
        """The error log's lines without their time, and the log cleared for the next reading."""
        path = os.path.join(self.root, errlog.LOG)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            lines = [line.split(" ", 2)[2] for line in fh.read().splitlines()]
        os.remove(path)
        return lines

    def same_as_each_alone(self, event, hooks, payload):
        alone = [self.hook(payload, *hook) for hook in hooks]
        alone_logged = self.logged()
        together = self.hook(payload, "gate.py", event)
        blocked = any(r.returncode == 2 for r in alone)
        self.assertEqual(together.returncode, 2 if blocked else 0, payload)
        self.assertEqual(together.stderr, "".join(r.stderr for r in alone), payload)
        self.assertEqual(together.stdout, "" if blocked else "".join(r.stdout for r in alone), payload)
        self.assertEqual(self.logged(), alone_logged, payload)
        return together

    def test_a_write_starts_one_process_before_and_one_after(self):
        with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as fh:
            events = json.load(fh)["hooks"]
        for event, short in (("PreToolUse", "pre"), ("PostToolUse", "post")):
            started = [h["command"].split("/hooks/")[1] for group in events[event]
                       if re.fullmatch(group["matcher"], "Write") for h in group["hooks"]]
            self.assertEqual(started, [f"gate.py {short}"])
        self.assertEqual([h["command"].split("/hooks/")[1] for group in events["PreToolUse"]
                          if re.fullmatch(group["matcher"], "Bash") for h in group["hooks"]], ["gate.py pre"])
        # Every wall the hooks used to start one by one is still run, in the same order.
        self.assertEqual([(f"{m}.py", "--pre") if f == "before" else (f"{m}.py",) for m, f, _ in gate.EVENTS["pre"]],
                         list(self.PRE))
        self.assertEqual([(f"{m}.py",) for m, _, _ in gate.EVENTS["post"]], list(self.POST))
        for module, function, _ in gate.EVENTS["pre"] + gate.EVENTS["post"]:
            self.assertTrue(callable(getattr(__import__(module), function)), (module, function))

    def test_before_a_call_the_gate_answers_as_each_wall_does_on_its_own(self):
        edit = dict(old_string="it works", new_string="it fails")
        cases = (
            ("Edit", dict(file_path=self.input, old_string="as", new_string="x"), "is in senses/"),
            ("Write", dict(file_path=os.path.join(self.root, "senses", "new.md"), content="lands"), None),
            ("NotebookEdit", dict(notebook_path=self.input), "is in senses/"),
            ("Edit", dict(file_path=self.log_path, old_string="", new_string="2026-10-03 recall q -> [[a]]"), "brain log"),
            ("Edit", dict(file_path=self.decision, **edit), "its ## Expected was written before"),
            ("Write", dict(file_path=self.decision, content="no frontmatter"), "a decision is never reopened"),
            ("Write", dict(file_path=os.path.join(self.root, "cortex/concepts/new.md"), content="no frontmatter"),
             "Blocked before writing cortex/concepts/new.md: missing frontmatter block"),
            ("Write", dict(file_path=self.good, content=page("concept", **VALID)), None),
            ("Write", dict(file_path=os.path.join(self.root, "motor", "report.md"), content="anything"), None),
            ("Bash", dict(command="rm senses/a.md"), "this command would change or remove a file in senses/"),
            ("Bash", dict(command="ls senses && git status"), None),
            ("Read", dict(file_path=self.input), None),  # not a tool any wall reads: the matcher never sends it
        )
        for tool, tool_input, said in cases:
            with self.subTest(tool=tool, tool_input=tool_input):
                payload = {"tool_name": tool, "tool_input": tool_input}
                hooks = self.PRE if tool != "Read" else ()
                r = self.same_as_each_alone("pre", hooks, payload)
                self.assertEqual(r.returncode, 2 if said else 0)
                self.assertIn(said or "", r.stderr)
        # Two walls refuse this one: both are said, in the walls' order, and both are logged.
        r = self.same_as_each_alone("pre", self.PRE, {"tool_name": "Write", "tool_input": {
            "file_path": self.decision, "content": "no frontmatter"}})
        self.assertRegex(r.stderr, r"(?s)\ABlocked: cortex/decisions/d.md is decided; a decision is never reopened.*\n"
                                   r"Blocked before writing cortex/decisions/d.md: missing frontmatter block")
        asked = self.same_as_each_alone("pre", self.PRE, {"tool_name": "Bash", "tool_input": {
            "command": "brain forget senses/a.md --yes"}})
        self.assertEqual(json.loads(asked.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_after_a_write_the_gate_answers_as_each_check_does_on_its_own(self):
        for path, said in ((self.bad, ("cortex/concepts/bad.md: missing frontmatter block",
                                       "cortex/concepts/bad.md: possible credential (AWS access key on line 1)")),
                           (self.good, ()), (self.input, ()), (os.path.join(self.root, "cortex/concepts/gone.md"), ())):
            with self.subTest(path=path):
                r = self.same_as_each_alone("post", self.POST, {"tool_name": "Write", "tool_input": {"file_path": path}})
                self.assertEqual(r.returncode, 2 if said else 0)
                for fragment in said:
                    self.assertIn(fragment, r.stderr)

    def test_it_is_as_silent_as_a_wall_where_a_wall_is_silent(self):
        edit = {"tool_name": "Edit", "tool_input": {"file_path": self.input, "old_string": "as", "new_string": "x"}}
        outside = os.path.dirname(os.path.realpath(self.root))
        for event in ("pre", "post"):
            for quiet in (dict(start=outside), dict(raw="not json"), dict(raw="[1, 2]")):
                r = self.hook(edit, "gate.py", event, **quiet)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""), (event, quiet))
        sub = os.path.join(self.root, "prefrontal", "launch")
        os.makedirs(sub)
        self.assertEqual(self.hook(edit, "gate.py", "pre", start=sub).returncode, 2)  # a subfolder is in its brain
        for args in ((), ("before",), ("pre", "post")):
            r = self.hook(edit, "gate.py", *args)
            self.assertEqual((r.returncode, r.stdout), (1, ""), args)  # wired wrongly: it says so, it refuses nothing
            self.assertIn("usage: gate.py pre | post", r.stderr)

    def test_a_shell_command_loads_the_senses_wall_and_no_other(self):
        self.assertEqual([name for name, _ in gate.walls("pre", "Bash")], ["protect_senses"])
        self.assertEqual([name for name, _ in gate.walls("pre", "NotebookEdit")], ["protect_senses"])
        self.assertEqual([name for name, _ in gate.walls("pre", "Edit")],
                         ["protect_senses", "protect_log", "protect_expected", "validate_page"])
        self.assertEqual([name for name, _ in gate.walls("post", "")], ["validate_page", "scan_secrets"])
        loaded = "import sys, gate; gate.main(['pre']); print(sorted(set(sys.modules) & {%r, %r, %r, %r, %r}))" % (
            "protect_senses", "protect_log", "protect_expected", "validate_page", "vaultlib")
        for tool, tool_input, modules in (
                ("Bash", {"command": "ls"}, ["protect_senses"]),
                ("Write", {"file_path": os.path.join(self.root, "motor", "x.md"), "content": "x"},  # no page: no library
                 ["protect_expected", "protect_log", "protect_senses", "validate_page"]),
                ("Write", {"file_path": self.good, "content": page("concept", **VALID)},
                 ["protect_expected", "protect_log", "protect_senses", "validate_page", "vaultlib"])):
            r = subprocess.run([sys.executable, "-c", loaded], input=json.dumps({"tool_name": tool, "tool_input": tool_input}),
                               capture_output=True, text=True, cwd=HOOKS, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))
            self.assertEqual(r.stdout.strip(), str(modules), r.stderr)


class AWallThatFails(TempBrain):
    """It is logged; the call is blocked where nothing can be undone, and let through anywhere else."""

    def setUp(self):
        super().setUp()
        self.write("senses/a.md", "as it arrived\n")
        self.log_path = self.write("hippocampus/log.md", "---\ntype: log\n---\n")
        for name, value in (("START", os.path.realpath(self.root)), ("ROOT", os.path.realpath(self.root))):
            patch = mock.patch.object(shared, name, value)  # the walls judge this brain, in this process
            patch.start()
            self.addCleanup(patch.stop)
        env = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.root})
        env.start()
        self.addCleanup(env.stop)

    @staticmethod
    def broken(data):
        raise RuntimeError("boom")

    def call(self, tool, **tool_input):
        return {"tool_name": tool, "tool_input": tool_input}

    def logged(self):
        with open(os.path.join(self.root, errlog.LOG), encoding="utf-8") as fh:
            return fh.read()

    def test_where_the_call_writes_decides(self):
        closed = (self.call("Write", file_path="senses/new.md", content="x"),
                  self.call("Edit", file_path=os.path.join(self.root, "cortex", "decisions", "d.md")),
                  self.call("NotebookEdit", notebook_path="senses/a.ipynb"),
                  self.call("Bash", command="mv senses/a.md /tmp"))
        through = (self.call("Write", file_path="cortex/concepts/a.md", content="x"),
                   self.call("Write", file_path="senses-old/a.md", content="x"),
                   self.call("Edit", file_path="cortex/decisions.md"),
                   self.call("Bash", command="rm notes/senses.md"), self.call("Bash"), self.call("Edit"),
                   {"tool_name": "Edit", "tool_input": "not a call"}, {})
        for data in closed:
            verdicts = shared.judge([("broken", self.broken)], data)
            self.assertEqual([(v.decision, v.source, v.kind) for v in verdicts], [("block", "broken", None)], data)
            self.assertIn("broken failed before it could check this call", verdicts[0].message)
        for data in through:
            self.assertEqual(shared.judge([("broken", self.broken)], data), [], data)
        self.assertEqual(self.logged().count(" broken error | RuntimeError: boom at test_walls.py:"),
                         len(closed) + len(through))  # each failure is one line, whatever came of the call

    def test_the_other_walls_still_answer_and_the_refusal_is_said_once(self):
        edit = self.call("Edit", file_path=self.log_path, old_string="", new_string="x")
        verdicts = shared.judge([("broken", self.broken), ("protect_log", protect_log.check)], edit)
        self.assertEqual([(v.source, v.kind) for v in verdicts], [("protect_log", "log")])
        into_senses = self.call("Write", file_path="senses/new.md", content="x")
        with mock.patch("sys.stderr") as said:
            code = shared.settle(shared.judge([("broken", self.broken)], into_senses))
        self.assertEqual(code, 2)
        self.assertIn("nothing goes into senses/ or cortex/decisions/ unchecked", said.write.call_args_list[0][0][0])
        self.assertEqual(self.logged().count("broken"), 2)  # the two failures; the block adds no line of its own
        self.assertEqual(shared.settle([]), 0)

    def test_a_wall_that_cannot_be_loaded_has_failed(self):
        with mock.patch.dict(gate.EVENTS, {"pre": (("no_such_wall", "check", None), ("protect_log", "check", shared.WRITES))}):
            walls = gate.walls("pre", "Edit")
            self.assertEqual([v.source for v in shared.judge(walls, self.call("Edit", file_path=self.log_path))],
                             ["protect_log"])
            self.assertEqual([v.source for v in shared.judge(walls, self.call("Edit", file_path="senses/a.md"))],
                             ["no_such_wall"])
        self.assertIn(" no_such_wall error | ModuleNotFoundError: No module named 'no_such_wall'", self.logged())

    def test_a_broken_library_opens_no_wall_and_closes_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            hooks = shutil.copytree(HOOKS, os.path.join(tmp, "engine", "hooks"), ignore=shutil.ignore_patterns("__pycache__"))
            os.makedirs(os.path.join(tmp, "engine", "lib"))
            shutil.copy(os.path.join(ENGINE, "lib", "errlog.py"), os.path.join(tmp, "engine", "lib"))  # the log, nothing else

            def gate_pre(tool, **tool_input):
                return subprocess.run([sys.executable, os.path.join(hooks, "gate.py"), "pre"], capture_output=True,
                                      text=True, input=json.dumps(self.call(tool, **tool_input)),
                                      env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))

            page_text = page("concept", **VALID)
            r = gate_pre("Write", file_path=os.path.join(self.root, "cortex", "decisions", "new.md"), content=page_text)
            self.assertEqual(r.returncode, 2)
            self.assertIn("Blocked: validate_page failed before it could check this call", r.stderr)
            r = gate_pre("Write", file_path=os.path.join(self.root, "cortex", "concepts", "new.md"), content=page_text)
            self.assertEqual((r.returncode, r.stderr), (0, ""))  # `brain check` at the commit gate still reads the page
            self.assertEqual(self.logged().count(" validate_page error | ModuleNotFoundError: No module named 'vaultlib'"), 2)
            # The walls that need no library are as closed as ever.
            self.assertEqual(gate_pre("Edit", file_path=self.log_path, old_string="", new_string="x").returncode, 2)
            self.assertEqual(gate_pre("Edit", file_path=os.path.join(self.root, "senses", "a.md")).returncode, 2)
            self.assertEqual(gate_pre("Bash", command="rm senses/a.md").returncode, 2)


class TheLibraryKeepsItsOwnCopies(TempBrain):
    """shared.py is the hooks'; lib/ has the same things for the commands. Neither needs the other: this holds them equal."""

    def test_finding_the_brain(self):
        inside = os.path.join(self.root, "prefrontal", "launch")
        os.makedirs(inside)
        outside = os.path.dirname(os.path.realpath(self.root))
        for start in (self.root, inside, os.path.join(self.root, "cortex"), os.path.join(self.root, "not", "made", "yet"),
                      outside, os.sep):
            found = shared.find_brain(start)
            self.assertEqual((vaultlib.find_brain(start), errlog.brain_of(start)), (found, found), start)
            self.assertEqual(shared.is_brain(start), vaultlib.is_brain(start), start)
        self.assertEqual((shared.find_brain(inside), shared.find_brain(outside)), (os.path.realpath(self.root), None))
        self.assertEqual((shared.MEMORY_DIRS, shared.PROJECTS_DIR), (vaultlib.MEMORY_DIRS, vaultlib.PROJECTS_DIR))

    def test_the_case_of_a_path(self):
        for platform in ("darwin", "linux"):
            with mock.patch.object(sys, "platform", platform):
                for path in ("Cortex/Decisions/D.md", "senses/a.md", "HIPPOCAMPUS/Log.MD", ""):
                    self.assertEqual(shared.fold(path), vaultlib.fold_case(path), (platform, path))

    def test_what_a_decision_froze(self):
        body = "\n# D\n\n## Expected\n\n- [hypothesis]   it works\n  on two lines\n\n## Outcome\n\nstatus: reviewed\n"
        for text in (page("decision", body, status="decided"), page("decision", body, status='"reviewed"'),
                     page("decision", body, status="'open'"), page("decision", body), page("decision", "\n## Expected\n"),
                     page("decision", "\n## Options\n\nNo such section.\n", status="decided"),
                     page("decision", body, status="decided").replace("\n", "\r\n"), body, ""):
            self.assertEqual(shared.status_of(text), link_check.status_of(text), text)
            self.assertEqual(shared.expected_of(text), link_check.expected_of(text), text)
        self.assertEqual((shared.status_of(page("decision", body, status="decided")), shared.status_of(body)), ("decided", None))
        self.assertEqual(shared.expected_of(page("decision", body)), "- [hypothesis] it works on two lines")


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
             os.path.join("hippocampus", "intentions.md"), os.path.join("hippocampus", "tuning.md"))

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
