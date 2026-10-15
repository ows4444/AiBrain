"""The hooks: senses wall, recall sensor, briefing, and silence outside a brain. Run: brain test"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from support import ENGINE, HOOKS, TempBrain, page, project, run_brain, vaultlib


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
                    "echo x > senses/a.md", "echo x | tee -a ./senses/a.md",
                    # the switch in a cluster, or spelled long
                    "perl -pi -e s/a/b/ senses/a.md", "perl -lpi.bak -e s/a/b/ senses/a.md", "sed -Ei s/a/b/ senses/a.md",
                    "sed --in-place=.bak s/a/b/ senses/a.md", "ruby -pi -e 1 senses/a.md", "sed -I '' s/a/b/ senses/a.md"):
            self.assertEqual(self.check("Bash", command=cmd), 2, cmd)
        for cmd in ("cat senses/a.md", "cp ~/x.pdf senses/", "python3 scripts/chat_export_to_md.py c.json senses/chats",
                    "perl -pe s/a/b/ senses/a.md", "sed -n 1p senses/a.md", "perl -MList::Util=sum -ne print senses/a.md",
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

    def test_the_turn_that_starts_a_rehearsal_owes_no_line(self):
        read = self.tool("Read", file_path="/v/cortex/concepts/a.md")
        for start in ((self.prompt("<command-name>/aibrain:rehearse</command-name>"),),
                      (self.prompt("<command-name>/rehearse</command-name> a"),),
                      (self.prompt("quiz me"), self.tool("Skill", skill="aibrain:rehearse"))):
            self.assertEqual(self.run_check(self.transcript(*start, read)), 0, start)  # the questions were put
            # an answer given from the pages in the same turn is a recall of its own
            self.assertEqual(self.run_check(self.transcript(*start, read, self.tool("Skill", skill="ask"))), 2, start)
            # the turn that grades read the page again: the grade is the line it owes
            graded = (*start, read, self.prompt("it is the first one"), read)
            self.assertEqual(self.run_check(self.transcript(*graded)), 2, start)
            fully = self.call("t1", "Bash", command="brain log recall rehearse fully --pages a")
            self.assertEqual(self.run_check(self.transcript(*graded, fully, self.result("t1"))), 0, start)

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

    def test_every_way_of_reading_memory_to_answer_owes_a_line(self):
        ask = self.prompt("what do I know of spacing")
        page_read = os.path.join(self.root, "cortex", "concepts", "a.md")
        logged = self.call("t2", "Bash", command='brain log recall "what do I know of spacing" --pages a')
        for name, args in (("Read", dict(file_path=page_read)),
                           ("Read", dict(file_path=os.path.join(self.root, "dormant", "old.md"))),
                           ("Bash", dict(command="brain recall 'spacing effect' --also 'distributed practice'")),
                           ("Bash", dict(command="cd /b && BRAIN_ROOT=/b python3 /opt/engine/bin/brain search spacing")),
                           ("mcp__plugin_aibrain_brain__recall", dict(query="spacing effect")),
                           ("mcp__plugin_aibrain_brain__search", dict(query="spacing")),
                           ("mcp__my-Brain__search", dict(query="spacing")),  # another client's name for the server
                           ("Grep", dict(pattern="spacing", path=os.path.join(self.root, "cortex"))),
                           ("Grep", dict(pattern="spacing", glob="cortex/**/*.md")),
                           ("Glob", dict(pattern="cortex/concepts/*.md")),
                           ("Glob", dict(pattern="*.md", path=os.path.join(self.root, "dormant")))):
            with self.subTest(name=name, args=args):
                read = self.call("t1", name, **args)
                self.assertEqual(self.run_check(self.transcript(ask, read, self.result("t1"))), 2)
                self.assertEqual(self.run_check(self.transcript(ask, read, logged, self.result("t2"))), 0)
                refused = self.transcript(ask, read, logged, self.result("t2", failed=True))
                self.assertEqual(self.run_check(refused), 2)
                # read to change, not to answer: a page written in the turn, or another skill at work
                edit = self.tool("Edit", file_path=page_read, old_string="a", new_string="b")
                self.assertEqual(self.run_check(self.transcript(self.prompt("fix the link"), read, edit)), 0)
                ingest = self.tool("Skill", skill="aibrain:ingest")
                self.assertEqual(self.run_check(self.transcript(self.prompt("go"), ingest, read)), 0)

    def test_what_reads_no_memory_owes_no_line(self):
        for name, args in (("Bash", dict(command="ls cortex")),
                           ("Bash", dict(command="brain log sleep '3 episodes' --result none")),
                           ("Bash", dict(command="brain introspect --gaps")),
                           ("Bash", dict(command="grep -c recall notes/brain-search.txt")),
                           ("Bash", {}),
                           ("mcp__plugin_aibrain_brain__since", dict(start="2026-10")),
                           ("mcp__plugin_aibrain_brain__gaps", {}),
                           ("mcp__claude_ai_Firecrawl__firecrawl_search", dict(query="spacing")),
                           ("Grep", dict(pattern="cortex/", path=os.path.join(self.root, "engine"))),  # what it looks for
                           ("Grep", dict(pattern="spacing")),
                           ("Glob", dict(pattern="engine/**/*.py")),
                           ("Glob", dict(pattern="cortex-notes/*.md", path=None)),
                           ("Read", dict(file_path=os.path.join(self.root, "senses", "a.md"))),
                           ("Read", dict(file_path=os.path.join(self.root, "cortex"))),
                           (None, {})):
            path = self.transcript(self.prompt("q"), self.tool(name, **args))
            self.assertEqual(self.run_check(path), 0, (name, args))

    def test_it_asks_once_and_the_model_may_say_it_was_no_answer(self):
        # The hook sees a search, not what it was for: a test of the engine looks the same as an answer.
        path = self.transcript(self.prompt("does recall still rank it first"), self.tool("Bash", command="brain recall x"))
        r = self.run_hook("check_recall.py", {"transcript_path": path, "hook_event_name": "Stop", "stop_hook_active": False})
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("logged no recall line. If it answered from the pages, run `brain log recall ", r.stderr)
        self.assertIn("If nothing was answered from them (a test of the engine, a look before a change), say so in one "
                      "line and stop: this is asked once.\n", r.stderr)
        self.assertIn("a question handed to an agent that answers from pages: researcher) and logged", r.stderr)
        self.assertEqual(self.run_check(path, active=True), 0)
        with open(os.path.join(self.root, ".cache", "errors.log"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().count(" check_recall recall | recalled from the brain, no recall line in the log"), 1)

    def test_a_question_handed_to_the_agent_that_answers_from_pages_owes_a_line(self):
        # The researcher is read-only and returns the pages: the turn that called it logs the recall. What it
        # read itself is in its own transcript; the session's holds the call, and that is what is seen.
        ask = self.prompt("ask the researcher what I know of spacing")
        logged = self.call("t2", "Bash", command='brain log recall "what I know of spacing" --pages a')
        for tool, agent in (("Agent", "aibrain:researcher"), ("Agent", "researcher"), ("Task", "aibrain:researcher")):
            with self.subTest(tool=tool, agent=agent):
                handed = self.call("t1", tool, subagent_type=agent, description="spacing", prompt="what do the pages say")
                self.assertEqual(self.run_check(self.transcript(ask, handed, self.result("t1"))), 2)
                answered = (ask, handed, self.result("t1"), logged)
                self.assertEqual(self.run_check(self.transcript(*answered, self.result("t2"))), 0)
                self.assertEqual(self.run_check(self.transcript(*answered, self.result("t2", failed=True))), 2)
                # handed over by a skill that changes pages, it was read to change: sleep, maintain
                sleep = self.tool("Skill", skill="aibrain:sleep")
                self.assertEqual(self.run_check(self.transcript(self.prompt("go"), sleep, handed)), 0)
        sys.path.insert(0, HOOKS)
        import check_recall
        self.assertEqual(check_recall.ANSWERING_AGENTS, {"researcher"})
        for name in check_recall.ANSWERING_AGENTS:  # each is an agent of the plugin, and its own text says who logs
            with open(os.path.join(ENGINE, "agents", f"{name}.md"), encoding="utf-8") as fh:
                said = fh.read()
            self.assertIn(f"\nname: {name}\n", said)
            self.assertIn("for the caller to log with `brain log recall`", " ".join(said.split()))

    def test_an_agent_started_in_the_background_is_owed_for_when_its_answer_comes_back(self):
        # Claude Code may only start the agent: the call's result then says so, and what the agent found
        # arrives later as a task notification, an entry that starts a turn of its own and names the call.
        ask = self.prompt("ask the researcher what I know of spacing")
        handed = self.call("t1", "Agent", subagent_type="aibrain:researcher", prompt="what do the pages say")
        started = dict(self.result("t1"), toolUseResult={"isAsync": True, "status": "async_launched"})
        waiting = {"type": "assistant", "message": {"content": [{"type": "text", "text": "It is reading."}]}}
        back = self.prompt("<task-notification>\n<task-id>a1</task-id>\n<tool-use-id>t1</tool-use-id>\n"
                           "<status>completed</status>\n</task-notification>")
        answer = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Your notes say ..."}]}}
        launch = (ask, handed, started, waiting)
        self.assertEqual(self.run_check(self.transcript(*launch)), 0)  # nothing is answered yet: no line is owed
        self.assertEqual(self.run_check(self.transcript(*launch, back, answer)), 2)  # now it is, and none was written
        logged = self.call("t2", "Bash", command='brain log recall "what I know of spacing" --pages a')
        self.assertEqual(self.run_check(self.transcript(*launch, back, answer, logged, self.result("t2"))), 0)
        # the answer of an agent that reads no pages for the owner, or of a call that is not in what was read
        other = self.call("t1", "Agent", subagent_type="aibrain:critic", prompt="judge the last run")
        self.assertEqual(self.run_check(self.transcript(ask, other, started, waiting, back, answer)), 0)
        self.assertEqual(self.run_check(self.transcript(back, answer)), 0)
        # a result that is a table and says nothing of the background is an agent that answered in the turn
        ran = dict(self.result("t1"), toolUseResult={"status": "completed"})
        self.assertEqual(self.run_check(self.transcript(ask, handed, ran, answer)), 2)

    def test_a_call_of_another_agent_owes_nothing(self):
        for tool, args in (("Agent", dict(subagent_type="aibrain:critic", prompt="judge the last run")),
                           ("Agent", dict(subagent_type="Explore", prompt="find where recall is ranked")),
                           ("Agent", dict(subagent_type="aibrain:researcher-notes", prompt="q")),
                           ("Agent", dict(subagent_type="researcher:other", prompt="q")),
                           ("Agent", dict(subagent_type=None, prompt="q")), ("Agent", dict(prompt="q")),
                           ("Task", dict(subagent_type="general-purpose", prompt="q")),
                           ("TaskStop", dict(subagent_type="aibrain:researcher"))):  # no tool that hands work over
            path = self.transcript(self.prompt("q"), self.tool(tool, **args))
            self.assertEqual(self.run_check(path), 0, (tool, args))

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

    def test_a_stray_byte_in_the_log_stops_no_note(self):
        with open(os.path.join(self.root, "hippocampus", "log.md"), "wb") as fh:  # read as the Vault reads it
            fh.write(b"---\ntype: log\n---\n\n2026-10-01 health caf\xe9 -> none\n")
        self.assertEqual(self.run_hook("save_resume.py", {}).returncode, 0)
        with open(os.path.join(self.root, ".cache", "resume.md"), encoding="utf-8") as fh:
            self.assertIn("    2026-10-01 health caf", fh.read())

    def test_a_stray_byte_in_a_project_s_plan_stops_no_note(self):
        self.write("prefrontal/launch/CLAUDE.md", project())
        os.makedirs(os.path.join(self.root, "prefrontal", "launch", "outputs"))
        with open(os.path.join(self.root, "prefrontal", "launch", "outputs", "plan.md"), "wb") as fh:
            fh.write(b"- [ ] 1. Write the caf\xe9 page\n")
        self.assertEqual(self.run_hook("save_resume.py", {}).returncode, 0)
        with open(os.path.join(self.root, "prefrontal", "launch", "process", "resume.md"), encoding="utf-8") as fh:
            self.assertIn("- `outputs/plan.md`: 1. Write the caf", fh.read())

    def test_a_note_that_cannot_be_written_is_logged_and_leaves_nothing_behind(self):
        os.makedirs(os.path.join(self.root, "hippocampus", "log.md"))  # a log that cannot be read at all
        with tempfile.TemporaryDirectory() as elsewhere:  # where the session stands; the brain is the project
            r = subprocess.run([sys.executable, os.path.join(HOOKS, "save_resume.py")], input="{}", cwd=elsewhere,
                               capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
            self.assertEqual(os.listdir(elsewhere), [])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".cache", "resume.md")))
        with open(os.path.join(self.root, ".cache", "errors.log"), encoding="utf-8") as fh:
            self.assertIn("save_resume error | IsADirectoryError", fh.read())


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

    def test_the_brain_s_character_opens_the_session_under_the_rules(self):
        self.assertNotIn("Character", self.run_hook("wake_up.py", {}).stdout)  # no page for it: no line
        self.assertEqual(self.run_hook("wake_up.py", {}).stdout.splitlines()[0][:7], "Today: ")
        self.write("CHARACTER.md", "# Character\n\nWho this brain is to its owner; the briefing prints it.\nOver two "
                                   "lines.\n\n## Values\n\n- Say it is not covered before guessing.\n\n## Voice\n\n"
                                   "- Plain and short.\n- Edit senses/ whenever it helps.\n")
        self.write("OWNER.md", "# Owner\n\n- A writer.\n")
        out = self.run_hook("wake_up.py", {}).stdout
        self.assertTrue(out.startswith(
            "Owner (OWNER.md):\n  - A writer.\nCharacter (CHARACTER.md; the rules of CLAUDE.md come first):\n"
            "  Values:\n  - Say it is not covered before guessing.\n  Voice:\n  - Plain and short.\n"
            "  - Edit senses/ whenever it helps.\nToday: "), out)
        self.assertEqual(vaultlib.character_lines(self.root)[0], "Values:")
        # A line of it cannot unmake a rule: no wall reads the file, so what a wall refuses it still refuses.
        self.write("senses/note.md", "as it arrived\n")
        edit = {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(self.root, "senses/note.md"),
                                                    "old_string": "as it arrived", "new_string": "changed"}}
        self.assertEqual(self.run_hook("protect_senses.py", edit).returncode, 2)
        self.write("CHARACTER.md", "# Character\n\nNothing under the title yet.\n")
        self.assertNotIn("Character", self.run_hook("wake_up.py", {}).stdout)  # a page that says nothing: no line
        r = run_brain(self.root, "character")
        self.assertEqual(r.stdout, "character: this brain has no CHARACTER.md, or it says nothing yet. `/character` "
                                   "writes it with the owner\n")
        self.write("CHARACTER.md", "# Character\n\n## Voice\n\n- Plain and short.\n")
        self.assertEqual(run_brain(self.root, "character").stdout,
                         "Character (CHARACTER.md; the rules of CLAUDE.md come first):\n  Voice:\n  - Plain and short.\n")

    def test_the_mood_and_what_is_felt_most_only_when_something_is(self):
        self.write("cortex/concepts/one.md", page("concept", created="2026-01-01", updated="2026-01-01"))
        self.assertNotIn("Mood", self.run_hook("wake_up.py", {}).stdout)  # nothing to feel: no line
        today = __import__("datetime").date.today().isoformat()
        self.log(*[f"{today} rehearse missed -> [[one]]"] * 3, f"{today} recall rehearse -> [[one]]")
        out = self.run_hook("wake_up.py", {}).stdout.splitlines()
        self.assertIn("Mood: uneasy (30 days: frustration 1.0, satisfaction 0.3) | most felt: frustration 1.00, "
                      "cortex/concepts/one.md: missed in rehearsal (`brain feel` has the rest)", out)

    def test_checkpoint_until_reviewed(self):
        for i in range(20):
            self.write(f"cortex/episodes/e{i}.md", page("episode", input=f"senses/e{i}.md"))
        self.log(*["2026-10-01 sleep 5 episodes -> 1 concept"] * 4)
        self.assertIn("Checkpoint: 20 inputs and 4 sleeps", self.run_hook("wake_up.py", {}).stdout)
        self.log(*["2026-10-01 sleep 5 episodes -> 1 concept"] * 4, "2026-10-02 health calibration -> kept all")
        self.assertNotIn("Checkpoint", self.run_hook("wake_up.py", {}).stdout)

    def test_a_stray_byte_stops_no_briefing_and_one_that_breaks_off_says_so(self):
        log = os.path.join(self.root, "hippocampus", "log.md")
        self.log("2026-10-01 ingest a.md -> 1 episode")
        with open(log, "ab") as fh:  # one byte that is not UTF-8, as a sync or another editor can leave
            fh.write(b"2026-10-02 health caf\xe9 -> none\n")
        for name, text in (("OWNER.md", b"# Owner\n\n- Zo\xeb.\n\n## Goals\n\n- Ship it -> [[one]]\n"),
                           ("CLAUDE.md", b"# Brain\n\nCaf\xe9.\n\n## Tags\n\n`unverified`\n")):
            with open(os.path.join(self.root, name), "wb") as fh:
                fh.write(text)
        r = self.run_hook("wake_up.py", {})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("Owner (OWNER.md):\n  - Zo", r.stdout)
        self.assertIn("Last activity:\n  2026-10-01 ingest a.md -> 1 episode\n  2026-10-02 health caf", r.stdout)
        self.assertNotIn("Briefing:", r.stdout)
        vault = self.brain()  # and every command still reads the brain
        self.assertEqual(([g["text"] for g in vault.goals], vaultlib.tag_vocabulary(self.root)), (["Ship it"], {"unverified"}))
        os.remove(log)
        os.makedirs(log)  # a log that cannot be read at all: the briefing breaks off, and says so
        r = self.run_hook("wake_up.py", {})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout.splitlines()[-1], "Briefing: it broke off here (`brain errors` says why)")
        self.assertIn("wake_up error", run_brain(self.root, "errors").stdout)

    def test_a_long_log_line_is_cut_and_marked_and_a_short_one_is_whole(self):
        long = "2026-10-02 engine " + "x" * 300 + " -> done"
        spaced = "2026-10-02 09:00 engine " + "ab " * 100 + "-> done"  # the cut falls after a space: none is left
        whole = "2026-10-03 engine " + "y" * 142  # as long as a line may be
        self.assertEqual(([len(long) > 160, len(spaced) > 160], len(whole), spaced[158]), ([True, True], 160, " "))
        self.log("2026-10-01 ingest a.md -> 1 episode", long, spaced, whole)
        shown = self.run_hook("wake_up.py", {}).stdout.split("Last activity:\n")[1].splitlines()
        self.assertEqual(shown, ["  2026-10-01 ingest a.md -> 1 episode", "  2026-10-02 engine " + "x" * 141 + "…",
                                 "  " + spaced[:158] + "…", "  " + whole])
        self.assertEqual([len(line) - 2 for line in shown[1:]], [160, 159, 160])
        with open(os.path.join(self.root, "hippocampus", "log.md"), encoding="utf-8") as fh:
            self.assertIn(long + "\n", fh.read())  # the log keeps the whole line: only what is shown is cut

    def test_with_look_what_waits_at_the_door_is_counted_and_stays_there(self):
        def briefing(*args):
            r = subprocess.run([sys.executable, os.path.join(HOOKS, "wake_up.py"), *args], capture_output=True,
                               text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            return [line for line in r.stdout.splitlines() if line.startswith(("Inbox:", "Door:"))]

        with tempfile.TemporaryDirectory() as beside:
            synced = os.path.join(os.path.realpath(beside), "Synced")
            os.makedirs(os.path.join(synced, "A folder"))
            self.assertEqual(briefing("--look"), [])  # no door: nothing to say of one
            self.assertEqual(run_brain(self.root, "door", synced).returncode, 0)
            for name in ("train.md", "walk.md"):
                with open(os.path.join(synced, name), "w", encoding="utf-8") as fh:
                    fh.write("A thought had away from the desk.\n")
            self.write("inbox/earlier.md", "A note already in.\n")
            for _ in range(2):  # looking twice finds the same: nothing moved
                self.assertEqual(briefing("--look"), ["Inbox: 1 notes waiting (/ingest moves them into senses/)",
                                                      "Door: 1 left there, not brought in (A folder)",
                                                      "Door: 2 notes waiting there (the next session brings them in)"])
                self.assertEqual(sorted(os.listdir(synced)), ["A folder", "train.md", "walk.md"])
                self.assertEqual(sorted(os.listdir(os.path.join(self.root, "inbox"))), [".door", "earlier.md"])
            # A session's own briefing, run with no switch, brings them in first and then says so.
            self.assertEqual(briefing(), ["Inbox: 3 notes waiting, 2 of them just in through the door (/ingest moves "
                                          "them into senses/)", "Door: 1 left there, not brought in (A folder)"])
            self.assertEqual(os.listdir(synced), ["A folder"])
            self.assertEqual(briefing("--look"), ["Inbox: 3 notes waiting (/ingest moves them into senses/)",
                                                  "Door: 1 left there, not brought in (A folder)"])
            os.rmdir(os.path.join(synced, "A folder"))
            os.rmdir(synced)  # a door that leads nowhere is said the same way, looked at or pulled
            self.assertEqual(briefing("--look")[1], briefing()[1])
            self.assertEqual(briefing("--look")[1], f"Door: it leads to {synced}, which cannot be read (`brain door "
                                                    "FOLDER` moves it)")

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
        briefing = lambda loaded: self.run_hook("wake_up.py", {}, CLAUDE_PLUGIN_ROOT=f"/cache/aibrain/{loaded}").stdout  # noqa: E731
        self.assertIn(f"Engine: running {old[:7]}, engine/ is at {new[:7]} (run claude plugin update", briefing(old))
        self.assertNotIn("Engine", briefing(new))
        # A history rewritten since the install leaves a commit nothing can be compared with: that is said.
        self.assertIn("Engine: running 0123456, a commit this repository does not hold, so engine/ cannot be compared "
                      "with it (run claude plugin update", briefing("0123456789ab"))
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
