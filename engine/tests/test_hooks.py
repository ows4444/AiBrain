"""The hooks: senses wall, recall sensor, briefing, and silence outside a brain. Run: brain test"""
import json
import os
import subprocess
import sys
import unittest

from support import TempBrain, page, vaultlib


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

    def run_check(self, path, active=False):
        return self.run_hook("check_recall.py", {"transcript_path": path, "stop_hook_active": active}).returncode

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
