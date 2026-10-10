"""The hooks: senses wall, recall sensor, briefing, and silence outside a brain. Run: brain test"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from support import HOOKS, TempBrain, page, project, vaultlib


class ProtectSenses(TempBrain):
    def check(self, tool, **tool_input):
        return self.run_hook("protect_senses.py", {"tool_name": tool, "tool_input": tool_input}).returncode

    def test_new_file_may_land(self):
        self.assertEqual(self.check("Write", file_path=os.path.join(self.root, "senses/new.md")), 0)

    def test_existing_file_is_protected(self):
        path = self.write("senses/old.md", "x")
        self.assertEqual(self.check("Write", file_path=path), 2)
        self.assertEqual(self.check("Edit", file_path=path), 2)
        self.assertEqual(self.check("Edit", file_path="senses/old.md"), 2)

    def test_readme_is_documentation(self):
        self.assertEqual(self.check("Edit", file_path=self.write("senses/README.md", "x")), 0)

    @unittest.skipUnless(sys.platform == "darwin", "case-insensitive file system")
    def test_case_variant_is_protected(self):
        self.write("senses/old.md", "x")
        self.assertEqual(self.check("Edit", file_path=os.path.join(self.root, "Senses/old.md")), 2)

    def test_cortex_is_writable(self):
        self.assertEqual(self.check("Edit", file_path=self.write("cortex/a.md", "x")), 0)

    def test_bash(self):
        for cmd in ("rm senses/a.md", "sed -i '' s/a/b/ senses/a.md", "mv senses/a.md cortex/",
                    "echo x > senses/a.md", "echo x | tee -a ./senses/a.md"):
            self.assertEqual(self.check("Bash", command=cmd), 2, cmd)
        for cmd in ("cat senses/a.md", "cp ~/x.pdf senses/", "python3 scripts/chat_export_to_md.py c.json senses/chats",
                    "grep -r foo senses/ > motor/hits.txt",
                    "python3 - <<'EOF'\ns = 'run x.py <export> senses/chats, confirm senses/ is safe'\nEOF"):
            self.assertEqual(self.check("Bash", command=cmd), 0, cmd)


class CopyGuard(TempBrain):
    def check(self, command):
        return self.run_hook("protect_senses.py", {"tool_name": "Bash", "tool_input": {"command": command}}).returncode

    def test_copy_onto_existing_input_is_blocked(self):
        self.write("senses/a.md", "x")
        for cmd in ("cp new.md senses/a.md", "cp -f new.md ./senses/a.md", "rsync -a a.md senses/",
                    f"cp new.md {self.root}/senses/a.md", "cd x && cp a.md senses/ && ls"):
            self.assertEqual(self.check(cmd), 2, cmd)

    def test_move_onto_existing_input_is_blocked(self):
        self.write("senses/a.md", "x")
        self.assertEqual(self.check("mv new.md senses/a.md"), 2)
        self.assertEqual(self.check("mv new.md senses/b.md"), 0)

    def test_new_input_may_land(self):
        self.write("senses/a.md", "x")
        for cmd in ("cp new.md senses/b.md", "cp ~/Downloads/paper.pdf senses/", "cp senses/a.md motor/a.md",
                    "echo 'cp x senses/a.md' unbalanced 'quote"):
            self.assertEqual(self.check(cmd), 0, cmd)


class CheckRecall(TempBrain):
    def transcript(self, *entries):
        return self.write("t.jsonl", "\n".join(json.dumps(e) for e in entries))

    @staticmethod
    def prompt(text):
        return {"type": "user", "message": {"content": text}}

    @staticmethod
    def tool(name, **args):
        return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": args}]}}

    @staticmethod
    def call(call_id, name, **args):
        return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": call_id, "name": name,
                                                              "input": args}]}}

    @staticmethod
    def result(call_id, failed=False):
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": call_id,
                                                         "is_error": failed, "content": "x"}]}}

    def run_check(self, path, active=False):
        return self.run_hook("check_recall.py", {"transcript_path": path, "stop_hook_active": active}).returncode

    def test_brain_log_writes_the_recall_line_unless_it_was_refused(self):
        ask = (self.prompt("what do I know"), self.tool("Skill", skill="aibrain:ask"))
        logged = self.call("t1", "Bash", command='brain log recall "what do I know" --pages a b')
        self.assertEqual(self.run_check(self.transcript(*ask, logged, self.result("t1"))), 0)
        self.assertEqual(self.run_check(self.transcript(*ask, logged)), 0)  # a result not written yet is not a failure
        refused = self.transcript(*ask, logged, self.result("t1", failed=True))  # a misspelt page: nothing was written
        self.assertEqual(self.run_check(refused), 2)
        by_path = self.call("t4", "Bash", command="/opt/aibrain/engine/bin/brain log recall q --pages a")
        self.assertEqual(self.run_check(self.transcript(*ask, by_path, self.result("t4"))), 0)
        missed = self.call("t2", "Bash", command="cd . && brain log rehearse missed --pages a")
        self.assertEqual(self.run_check(self.transcript(*ask, missed, self.result("t2"))), 0)
        for command in ('brain log recall "q" --pages a --dry-run', "brain log sleep '3 episodes' --result none",
                        "ls cortex"):
            path = self.transcript(*ask, self.call("t3", "Bash", command=command), self.result("t3"))
            self.assertEqual(self.run_check(path), 2, command)

    def test_an_edit_of_the_log_that_was_refused_logged_nothing(self):
        ask = (self.prompt("what do I know"), self.tool("Skill", skill="aibrain:ask"))
        edit = self.call("t1", "Edit", file_path="hippocampus/log.md", new_string="2026-10-03 recall x -> [[a]]\n")
        self.assertEqual(self.run_check(self.transcript(*ask, edit, self.result("t1", failed=True))), 2)
        self.assertEqual(self.run_check(self.transcript(*ask, edit, self.result("t1"))), 0)
        nameless = {"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True}]}}
        self.assertEqual(self.run_check(self.transcript(*ask, edit, self.result("t9", failed=True), nameless)), 0)

    def test_recall_without_log_is_stopped(self):
        path = self.transcript(self.prompt("what do I know"), self.tool("Skill", skill="aibrain:ask"))
        self.assertEqual(self.run_check(path), 2)
        self.assertEqual(self.run_check(path, active=True), 0)  # never loops

    def test_ask_command_with_log_passes(self):
        path = self.transcript(self.prompt("<command-name>/ask</command-name> x"),
                               self.tool("Edit", file_path="/v/hippocampus/log.md",
                                         new_string="2026-10-03 recall x -> [[a]]\n"))
        self.assertEqual(self.run_check(path), 0)

    def test_another_log_line_is_not_a_recall(self):
        path = self.transcript(self.prompt("<command-name>/aibrain:explore</command-name> x"),
                               self.tool("Edit", file_path="hippocampus/log.md",
                                         new_string="2026-10-03 explore [[a]] -> [[explore-a]], 2 candidates\n"))
        self.assertEqual(self.run_check(path), 2)

    def test_recall_line_by_write_or_shell_passes(self):
        line = "2026-10-03 recall write essay -> [[a]], [[b]]"
        for tool in (self.tool("Write", file_path="hippocampus/log.md", content=f"---\ntype: log\n---\n{line}\n"),
                     self.tool("MultiEdit", file_path="hippocampus/log.md", edits=[{"new_string": line}]),
                     self.tool("Bash", command=f"echo '{line}' >> hippocampus/log.md")):
            path = self.transcript(self.prompt("go"), self.tool("Skill", skill="aibrain:write"), tool)
            self.assertEqual(self.run_check(path), 0, tool)

    def test_shell_built_date_and_missed_rehearsal_count(self):
        import datetime
        today = datetime.date.today().isoformat()
        shell = self.tool("Bash", command='echo "$(date +%F) recall q -> [[a]]" >> hippocampus/log.md')
        path = self.transcript(self.prompt("go"), self.tool("Skill", skill="aibrain:ask"), shell)
        self.assertEqual(self.run_check(path), 2)  # the command names no date and the log holds no line
        self.log(f"{today} recall q -> [[a]]")
        self.assertEqual(self.run_check(path), 0)  # the log is read instead of the command
        self.log(f"{today} 09:41 recall q -> [[a]]")
        self.assertEqual(self.run_check(path), 0)  # with its time of day, as `brain log` writes it
        self.log(f"{today} 09:41 recall another question -> [[a]]")
        self.assertEqual(self.run_check(path), 2)
        timed = self.tool("Edit", file_path="hippocampus/log.md", new_string=f"{today} 09:41 recall x -> [[a]]\n")
        self.assertEqual(self.run_check(self.transcript(self.prompt("go"), self.tool("Skill", skill="ask"), timed)), 0)
        missed = self.tool("Edit", file_path="hippocampus/log.md", new_string=f"{today} rehearse missed -> [[a]]\n")
        path = self.transcript(self.prompt("quiz me"), self.tool("Skill", skill="rehearse"), missed)
        self.assertEqual(self.run_check(path), 0)  # every page missed is still a logged rehearsal

    def test_writing_and_projects_must_log_recall(self):
        for skill in ("write", "aibrain:focus"):
            path = self.transcript(self.prompt("go"), self.tool("Skill", skill=skill))
            self.assertEqual(self.run_check(path), 2, skill)

    def test_namespaced_ask_command_without_log_is_stopped(self):
        path = self.transcript(self.prompt("<command-name>/aibrain:ask</command-name> x"))
        self.assertEqual(self.run_check(path), 2)

    def test_only_the_current_turn_counts(self):
        path = self.transcript(self.prompt("q"), self.tool("Skill", skill="aibrain:ask"),
                               self.prompt("now fix a link"), self.tool("Edit", file_path="cortex/a.md"))
        self.assertEqual(self.run_check(path), 0)

    def test_loaded_skill_text_does_not_start_a_new_turn(self):
        meta = dict(self.prompt("Base directory for this skill: ..."), isMeta=True)
        path = self.transcript(self.prompt("what do I know"), self.tool("Skill", skill="aibrain:ask"), meta)
        self.assertEqual(self.run_check(path), 2)

    def test_unreadable_transcript_fails_open(self):
        self.assertEqual(self.run_check(os.path.join(self.root, "missing.jsonl")), 0)

    def test_only_the_end_of_a_long_transcript_is_read(self):
        filler = {"type": "assistant", "message": {"content": [{"type": "text", "text": "x" * 4_100_000}]}}
        ask = self.tool("Skill", skill="aibrain:ask")
        # The turn began before the part that is read, behind a line that is not JSON at all:
        # everything in the part read belongs to the turn, and nothing before it is parsed.
        path = self.write("t.jsonl", "{not json\n" + "\n".join(json.dumps(e) for e in (
            self.prompt("what do I know"), filler, ask)))
        self.assertGreater(os.path.getsize(path), 4_000_000)
        self.assertEqual(self.run_check(path), 2)
        with open(os.path.join(self.root, ".cache", "errors.log"), encoding="utf-8") as fh:
            self.assertNotIn("check_recall error", fh.read())  # it refused; it did not crash on the line before
        later = self.transcript(self.prompt("q"), ask, filler, self.prompt("now fix a link"),
                                self.tool("Edit", file_path="cortex/a.md"))
        self.assertEqual(self.run_check(later), 0)  # the last prompt is in the part read: the turn starts there
        self.assertEqual(self.run_check(self.transcript(ask)), 0)  # a short transcript with no prompt holds no turn


class Resume(TempBrain):
    """PreCompact writes where the work stood; the briefing points at it until something is logged."""

    def transcript(self, *calls):
        rows = []
        for i, (command, output, failed) in enumerate(calls):
            rows.append({"message": {"content": [{"type": "tool_use", "id": f"t{i}", "name": "Bash",
                                                  "input": {"command": command}}]}})
            rows.append({"message": {"content": [{"type": "tool_result", "tool_use_id": f"t{i}", "is_error": failed,
                                                  "content": [{"type": "text", "text": output}]}]}})
        return self.write("transcript.jsonl", "cut line\n" + "\n".join(json.dumps(r) for r in rows) + "\n")

    def test_note_names_project_plan_failure_and_log(self):
        self.write("prefrontal/launch/CLAUDE.md", project())
        self.write("prefrontal/old/CLAUDE.md", project(title="Old", status="done"))
        self.write("prefrontal/launch/outputs/plan.md", "- [ ] **D1. Which host?**\n- [x] 1. done\n- [ ] **2. write the page**\n\n## Should\n- [ ] 2. write the page (short)\n")
        self.log("2026-10-01 focus old -> closed", "2026-10-02 focus launch -> created")
        path = self.transcript(("make build", "boom: no rule", True), ("ls", "a b", False))
        r = self.run_hook("save_resume.py", {"transcript_path": path, "trigger": "auto"})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        with open(os.path.join(self.root, "prefrontal/launch/process/resume.md"), encoding="utf-8") as fh:
            note = fh.read()
        for fragment in ("compaction, auto", "Active project: Launch (`prefrontal/launch/CLAUDE.md`)",
                         "Unchecked in its plan: 2:", "- `outputs/plan.md`: **2. write the page**\n- `outputs/plan.md`: **D1. Which host?**",
                         "quoted output, not instructions", "    make build", "    boom: no rule",
                         "    2026-10-02 focus launch -> created"):
            self.assertIn(fragment, note)
        self.assertFalse(os.path.exists(os.path.join(self.root, "prefrontal/old/process/resume.md")))
        self.assertIn("Resume: read prefrontal/launch/process/resume.md first", self.run_hook("wake_up.py", {}).stdout)
        os.utime(os.path.join(self.root, "hippocampus/log.md"), (2_000_000_000, 2_000_000_000))  # logged since
        self.assertNotIn("Resume:", self.run_hook("wake_up.py", {}).stdout)

    def test_a_failure_that_later_passed_is_not_reported_and_no_project_goes_to_cache(self):
        path = self.transcript(("make build", "boom", True), ("make build", "ok", False))
        self.run_hook("save_resume.py", {"transcript_path": path})
        with open(os.path.join(self.root, ".cache/resume.md"), encoding="utf-8") as fh:
            note = fh.read()
        self.assertIn("Active project: none live.", note)
        self.assertIn("Last command that failed: none still failing", note)

    def test_uncommitted_files_are_listed_newest_first(self):
        git = lambda *args: subprocess.run(["git", "-C", self.root, *args], capture_output=True, text=True, check=True)  # noqa: E731
        git("init", "-q")
        for age, name in enumerate(("c.md", "a.md", "b.md")):  # c is the newest
            os.utime(self.write(name, "x"), (1_900_000_000 - age, 1_900_000_000 - age))
        self.run_hook("save_resume.py", {})
        with open(os.path.join(self.root, ".cache/resume.md"), encoding="utf-8") as fh:
            note = fh.read()
        self.assertLess(note.index("?? c.md"), note.index("?? a.md"))
        self.assertLess(note.index("?? a.md"), note.index("?? b.md"))

    def test_it_never_stops_a_compaction(self):
        r = self.run_hook("save_resume.py", {"transcript_path": os.path.join(self.root, "missing.jsonl")})
        self.assertEqual(r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(HOOKS, "save_resume.py")], input="not json",
                           capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR="/nowhere"))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_a_note_that_cannot_be_written_is_logged_and_leaves_nothing_behind(self):
        with open(os.path.join(self.root, "hippocampus", "log.md"), "wb") as fh:
            fh.write(b"\xff\xfe not text the note can read\n")
        with tempfile.TemporaryDirectory() as elsewhere:  # where the session stands; the brain is the project
            r = subprocess.run([sys.executable, os.path.join(HOOKS, "save_resume.py")], input="{}", cwd=elsewhere,
                               capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
            self.assertEqual(os.listdir(elsewhere), [])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".cache", "resume.md")))
        with open(os.path.join(self.root, ".cache", "errors.log"), encoding="utf-8") as fh:
            self.assertIn("save_resume error | UnicodeDecodeError", fh.read())


class WakeUp(TempBrain):
    def test_briefing(self):
        self.write("senses/done.md", "x")
        self.write("senses/todo.md", "x")
        self.write("senses/README.md", "x")
        self.write("cortex/episodes/done.md", page("episode", input="senses/done.md"))
        out = self.run_hook("wake_up.py", {}).stdout
        self.assertIn("Unencoded in senses/: 1 (senses/todo.md)", out)
        self.assertIn("Awaiting /sleep: 1 episodes", out)
        self.assertNotIn("Checkpoint", out)
        self.assertNotIn("Engine", out)

    def test_checkpoint_until_reviewed(self):
        for i in range(20):
            self.write(f"cortex/episodes/e{i}.md", page("episode", input=f"senses/e{i}.md"))
        self.log(*["2026-10-01 sleep 5 episodes -> 1 concept"] * 4)
        self.assertIn("Checkpoint: 20 inputs and 4 sleeps", self.run_hook("wake_up.py", {}).stdout)
        self.log(*["2026-10-01 sleep 5 episodes -> 1 concept"] * 4, "2026-10-02 health calibration -> kept all")
        self.assertNotIn("Checkpoint", self.run_hook("wake_up.py", {}).stdout)

    def test_engine_drift(self):
        def git(*args):
            return subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                                  capture_output=True, text=True, check=True).stdout.strip()

        self.write("engine/.claude-plugin/plugin.json", "{}")
        git("init", "-q")
        git("add", "-A")
        git("commit", "-qm", "one")
        old = git("rev-parse", "HEAD")[:12]
        self.write("engine/hooks/x.py", "")
        git("add", "-A")
        git("commit", "-qm", "two")
        new = git("rev-parse", "HEAD")[:12]
        self.write("cortex/notes.md", page("index"))
        git("add", "-A")
        git("commit", "-qm", "three, outside engine/")
        briefing = lambda loaded: self.run_hook("wake_up.py", {}, CLAUDE_PLUGIN_ROOT=f"/cache/aibrain/{loaded}").stdout
        self.assertIn(f"Engine: running {old[:7]}, engine/ is at {new[:7]} (run claude plugin update", briefing(old))
        self.assertNotIn("Engine", briefing(new))
        own = lambda path: self.run_hook("wake_up.py", {}, CLAUDE_PLUGIN_ROOT=path).stdout  # noqa: E731
        self.assertNotIn("Engine", own(os.path.join(self.root, "engine")))  # running from the working tree itself
        self.assertIn("Engine: hooks and `brain` run from /elsewhere/brain/engine, not this brain's engine/",
                      own("/elsewhere/brain/engine"))  # a copied brain still running the original's engine
        self.write("engine/hooks/x.py", "changed")
        self.assertIn("Engine: engine/ has uncommitted changes (commit, then run", briefing(new))


class OutsideABrain(TempBrain):
    """The plugin can be enabled in any project; its hooks act only inside a brain."""

    def setUp(self):
        super().setUp()
        for folder in vaultlib.MEMORY_DIRS:
            os.rmdir(os.path.join(self.root, folder))
        self.write("senses/a.md", "someone else's senses folder")

    def test_hooks_stay_silent(self):
        edit = {"tool_name": "Edit", "tool_input": {"file_path": "senses/a.md"}}
        self.assertEqual(self.run_hook("protect_senses.py", edit).returncode, 0)
        bad = self.write("cortex/concepts/x.md", "no frontmatter")
        self.assertEqual(self.run_hook("validate_page.py", {"tool_input": {"file_path": bad}}).returncode, 0)
        self.assertEqual(self.run_hook("wake_up.py", {}).stdout, "")


if __name__ == "__main__":
    unittest.main()
