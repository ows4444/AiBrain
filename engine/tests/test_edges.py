"""Edges: every command's text output and errors, every hook's quiet exits, and the corner cases of the model.

The other test files prove each feature works. This one proves the paths
around them: what each instrument prints for a person, what it says when
pointed at the wrong folder, how every hook stays silent outside a brain or on
input it cannot read, and the small branches of the model. Run: brain test
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from support import DECIDED, ENGINE, HOOKS, SCRIPTS, TODAY, TempBrain, ago, page, run_brain, vaultlib

FIXTURE = os.path.join(ENGINE, "eval", "fixture")


def concept(body="", **fields):
    return page("concept", body, **dict(dict(status="established", created=ago(10), updated=ago(10)), **fields))


class NotADirectory(unittest.TestCase):
    """Every command refuses a root that is not a folder, by name, instead of crashing."""

    def test_each_command_names_the_missing_folder(self):
        missing = os.path.join(tempfile.gettempdir(), "no-such-brain-here")
        for args in (["check"], ["introspect"], ["graph"], ["fingerprint"], ["export", "x"], ["since", "2026-01"],
                     ["search", "x"], ["statusline"], ["errors"], ["resume"]):
            r = run_brain(missing, *args)
            self.assertEqual(r.returncode, 1, args)
            self.assertEqual(r.stderr, f"not a directory: {missing}\n", args)


class TextReports(TempBrain):
    """What a person reads: the text form of each report, not only its JSON."""

    def populate(self):
        self.write("cortex/concepts/spacing.md", concept("Spread study. [[forgetting]] [[e1]]", title="Spacing",
                                                         tags="[disputed]", created="2026-09-01", updated=ago(200)))
        self.write("cortex/concepts/forgetting.md", concept("Memory fades. [[spacing]] [[e1]]", title="Forgetting"))
        self.write("cortex/concepts/lonely.md", concept("Nobody links here.", title="Lonely", updated=ago(400),
                                                        created=ago(400)))
        self.write("cortex/episodes/e1.md", page("episode", "## Candidates\n- Cramming - x\n", title="E1",
                                                 created=ago(3)))
        self.write("cortex/episodes/blog.md", page("episode", "(contradicts:: [[spacing]])\n## Candidates\n"
                                                   "- Cramming - y\n", title="Blog", created=ago(2),
                                                   origin="generated"))
        self.write("cortex/concepts/a.md", concept("[[spacing]] [[forgetting]]", title="A"))
        self.write("cortex/concepts/b.md", concept("[[spacing]] [[forgetting]]", title="B"))
        self.log("2026-09-02 recall what is spacing -> [[spacing]], [[lonely]]",
                 f"{ago(1)} recall rehearse -> [[forgetting]]")

    def test_introspect_prints_every_view(self):
        self.populate()
        out = run_brain(self.root, "introspect", "--queue", "--links", "--open", "--dormant", "--stale", "--graph", "--goals", "--remind").stdout
        for fragment in ("awaiting consolidation, oldest first: 2", "+1 generated",
                         "prediction errors", "blog.md contradicts cortex/concepts/spacing.md (established)",
                         "links that probably belong", "a.md ~ cortex/concepts/b.md",
                         "disputed pages: 1", "contradictions (typed links): 1", "tagged to-revisit: 0",
                         "dormant candidates", "stale concepts, oldest first: 2",
                         "hubs (inbound", "bridges (highest betweenness", "cut points", "clusters (size",
                         "schema candidates", "tags in use", "reminders due: 0"):
            self.assertIn(fragment, out)
        self.assertRegex(out, r"(?m)^links           \d+   broken \d+$")  # --links leaves the count of links alone
        data = json.loads(run_brain(self.root, "introspect", "--links", "--json").stdout)
        self.assertEqual(data["link_suggestions"][0]["pages"], ["cortex/concepts/a.md", "cortex/concepts/b.md"])
        self.assertIsInstance(data["links"], int)

    def test_introspect_computes_only_what_was_asked_for(self):
        self.populate()
        sys.path.insert(0, SCRIPTS)
        import introspect
        asked = json.loads(run_brain(self.root, "introspect", "--due", "--json").stdout)
        self.assertEqual(list(asked), [*introspect.SUMMARY[:13], "goals", "projects", "calibration", "most_recalled",
                                       "due", "risk", "tuning"])  # the summary and the flag's views, in the report's order
        whole = json.loads(run_brain(self.root, "introspect", "--json").stdout)
        self.assertEqual(list(whole), list(introspect.EVERYTHING))
        self.assertEqual({k: whole[k] for k in asked}, asked)  # a view is the same however it was asked for
        graph = json.loads(run_brain(self.root, "introspect", "--hubs", "--json").stdout)
        self.assertIn("hubs", graph)
        self.assertNotIn("bridges", graph)  # betweenness is not run for a list of hubs
        vault, calls = self.brain(), []
        due, pairs = vault.due_for_rehearsal, vault.candidate_pairs
        vault.due_for_rehearsal = lambda: calls.append("due") or due()
        vault.candidate_pairs = lambda: calls.append("pairs") or pairs()
        self.assertEqual(list(introspect.report(vault, ["due"]))[-3:], ["due", "risk", "tuning"])
        self.assertEqual(calls, ["due"])  # once for its three views, and the costly view of --queue not at all
        public = {name for name in introspect.VIEWS if not name.startswith("_")}
        self.assertEqual(public, set(introspect.ORDER))
        self.assertLessEqual(set(introspect.SUMMARY).union(*introspect.FLAG_VIEWS.values()), public)

    def test_snapshot_first_then_since_and_damaged_lines(self):
        self.populate()
        first = run_brain(self.root, "introspect", "--snapshot").stdout
        self.assertIn("snapshot recorded: the first one, nothing to compare yet", first)
        with open(os.path.join(self.root, "hippocampus", "metrics.md"), "w", encoding="utf-8") as fh:
            fh.write("2026-01-01 {not json}\n2026-01-02 " + json.dumps({"pages": 1, "links": 0}) + "\n")
        later = run_brain(self.root, "introspect", "--snapshot").stdout
        self.assertIn("snapshot recorded; since 2026-01-02: pages +", later)  # the damaged line is skipped

    def test_context_budget_is_measured_and_growth_is_flagged(self):
        sys.path.insert(0, SCRIPTS)
        import introspect
        self.assertEqual(introspect.tokens_estimate("x" * 2700), 1000)  # bytes over 2.7, as /context showed
        fields, body = introspect.definition(os.path.join(ENGINE, "skills", "ask", "SKILL.md"))
        self.assertTrue(fields["description"].startswith("Answer a question from the brain's pages"))
        self.assertNotIn("description:", body)
        root_file = "# Brain\n" + "A line of the root file.\n" * 200
        self.write("CLAUDE.md", root_file)
        data = json.loads(run_brain(self.root, "introspect", "--context", "--json").stdout)
        c = data["context"]
        first = c["every_session"][0]
        self.assertEqual((first["what"], first["bytes"], first["lines"]), ("CLAUDE.md", len(root_file), 201))
        self.assertEqual(c["session_bytes"], sum(x["bytes"] for x in c["every_session"]))
        self.assertEqual(c["warnings"], ["CLAUDE.md is 201 lines, past 200: move detail to where it is used"])
        self.assertIn("commit", c["hidden_skills"])  # hidden from the model, so its description is not counted
        self.assertFalse(any("commit" in line for line in c["every_session"][1]["what"].split()))
        self.assertIn("skill ingest", [x["what"] for x in c["on_use"]])
        self.assertIsNone(c["since"])
        with open(os.path.join(self.root, "hippocampus", "metrics.md"), "w", encoding="utf-8") as fh:
            fh.write("2026-01-02 " + json.dumps({"pages": 1, "session_bytes": c["session_bytes"] - 10}) + "\n")
        out = run_brain(self.root, "introspect", "--context").stdout
        for fragment in ("loads every session", "loads on use", "since the snapshot of 2026-01-02: every-session "
                         "bytes +10  GROWN", "WARNING: CLAUDE.md is 201 lines", "not counted: what the harness loads"):
            self.assertIn(fragment, out)
        snap = run_brain(self.root, "introspect", "--snapshot").stdout
        self.assertIn("session_bytes +10", snap)
        with open(os.path.join(self.root, "hippocampus", "metrics.md"), encoding="utf-8") as fh:
            self.assertIn(f'"session_bytes": {c["session_bytes"]}', fh.read().splitlines()[-1])

    def test_brier_line_once_there_are_enough(self):
        sys.path.insert(0, SCRIPTS)
        import introspect
        b = {"n": 12, "score": 0.18, "enough": True, "buckets": {"70%": {"n": 12, "held": 9}}}
        self.assertEqual(introspect.brier_line(b, 10), "probabilities: Brier 0.18 over 12 (0 perfect, 0.25 = always "
                                                       "50%); 70% said: 9/12 held")
        self.assertEqual(introspect.snapshots(os.path.join(self.root, "nowhere")), [])

    def test_check_shortens_long_lists(self):
        for i in range(45):
            self.write(f"cortex/concepts/s{i}.md", concept("short", title=f"S{i}"))
        out = run_brain(self.root, "check").stdout
        self.assertIn("stubs (<40 words, no links): 45", out)
        self.assertIn("... 5 more (use --json)", out)

    def test_search_and_recall_text(self):
        self.populate()
        cmd = lambda *a: run_brain(self.root, *a)  # noqa: E731
        recall = cmd("recall", "spacing").stdout
        self.assertIn("hit; ", recall)
        self.assertIn("ask the owner whether these still hold: cortex/concepts/spacing.md", recall)
        bad = cmd("recall", "spacing", "--project", "nope")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("no project named nope in prefrontal/", bad.stderr)
        self.assertIn("(try --dormant)", cmd("search", "zebra").stdout)
        self.assertNotIn("try --dormant", cmd("search", "zebra", "--dormant").stdout)

    def test_since_text_and_dates(self):
        self.populate()
        out = run_brain(self.root, "since", "2026-09-01", "--until", "2026-09-30").stdout
        for fragment in ("2026-09-01 .. 2026-09-30", "created  5  concept:4 episode:1", "  + cortex/concepts/spacing.md",
                         "operations  recall 1", "rehearsals  0 passed, 0 missed", "questions asked",
                         "  2026-09-02 what is spacing"):
            self.assertIn(fragment, out)
        self.write("cortex/concepts/old.md", concept("Edited lately.", title="Old", created="2025-01-01",
                                                     updated=ago(5)))
        changed = run_brain(self.root, "since", ago(30)).stdout
        self.assertIn("  ~ cortex/concepts/old.md", changed)
        bad = run_brain(self.root, "since", "last week")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("not a date or a month: last week", bad.stderr)

    def test_fingerprint_text(self):
        self.write("senses/a.md", "x")
        self.write("senses/b.md", "y")
        self.assertEqual(run_brain(self.root, "fingerprint").stdout,
                         "fingerprinted 2 inputs\n  senses/a.md\n  senses/b.md\n")
        self.assertEqual(run_brain(self.root, "fingerprint").stdout, "fingerprinted 0 inputs\n")


class EvalReport(unittest.TestCase):
    def test_text_report_answers_and_a_private_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers, base = os.path.join(tmp, "answers.json"), os.path.join(tmp, "base.json")
            with open(answers, "w", encoding="utf-8") as fh:
                json.dump({"q09": "See [[wozniak-sm2]] and [[anki]].", "u01": "Canberra, I believe."}, fh)
            saved = run_brain(None, "eval", "--save-baseline", "--baseline", base, "--answers", answers).stdout
            self.assertIn(f"baseline saved to {base}", saved)
            with open(base, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["k"], 5)
            out = run_brain(None, "eval", "--baseline", base, "--answers", answers).stdout
        for fragment in ("retrieval over 13 covered questions, top 5", "(baseline hit", "recall missed q13",
                         "uncovered: u01 (0 pages matched words, recall lists 0)", "answers: 2/35 given",
                         "uncovered questions recall still lists pages for: 2 of 6", "recall  rows returned", "held ideas: 2 of 2 questions list the idea they name;", "set paraphrase: 8 questions", "set first: 8 questions",
                         "hit@1", "recall buried f07: the first expected page is at rank 4;",
                         "q09: missing [], extra ['anki']", "u01: missing [], extra [], did not say it was not covered"):
            self.assertIn(fragment, out)


class SynthCommand(unittest.TestCase):
    def test_writes_a_new_folder_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "s")
            r = run_brain(None, "synth", out, "--pages", "49", "--days", "60", "--today", "2026-10-03")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("synthetic brain: 49 pages", r.stdout)  # 49 rounds the mix down: padded with episodes
            self.assertEqual(len(vaultlib.Vault(out, today=TODAY).knowledge), 49)
            again = run_brain(None, "synth", out)
            self.assertEqual(again.returncode, 1)
            self.assertIn("already exists", again.stderr)


class BenchCommand(unittest.TestCase):
    def test_times_every_instrument_on_a_brain_it_builds_and_removes(self):
        import bench
        import commands
        made = []
        build = bench.synth.build
        bench.synth.build = lambda root, *a, **kw: made.append(root) or build(root, *a, **kw)
        try:
            result = commands.call("bench", ["--pages", "12", "--seed", "3"])
        finally:
            bench.synth.build = build
        self.assertEqual((result["pages"], result["seed"], result["repeat"]), (12, 3, 1))
        self.assertEqual([r["what"] for r in result["commands"]], [label for label, _, _ in bench.COMMANDS])
        ran = result["commands"] + result["hooks"]
        self.assertEqual({r["exit"] for r in ran}, {0}, ran)  # a row that failed timed nothing
        self.assertEqual(len(result["hooks"]), len(bench.WRITE_HOOKS) + 2)  # the briefing first, the sum last
        self.assertEqual(result["hooks"][-1]["seconds"],
                         round(sum(r["seconds"] for r in result["hooks"][1:-1]), 3))
        self.assertEqual([r["what"] for r in result["vault"]][:2], ["Vault() load", "candidate_pairs"])
        self.assertTrue(all(r["seconds"] >= 0 for group in ("commands", "hooks", "vault") for r in result[group]))
        self.assertFalse(os.path.exists(made[0]))  # the brain it timed is gone
        text = bench.render(result, None)
        self.assertTrue(text.startswith("bench: 12 synthetic pages, "))
        self.assertNotIn("fastest of", text)
        self.assertNotIn("(exit", text)
        self.assertIn(" s  recall, cache empty\n", text)
        self.assertIn(f" s  the {len(bench.WRITE_HOOKS)} hooks of one Write or Edit, together\n", text)

    def test_the_hooks_it_times_are_the_ones_a_write_starts(self):
        import bench
        with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as fh:
            events = json.load(fh)["hooks"]
        started = [tuple(h["command"].split("/hooks/")[1].split())
                   for event in ("PreToolUse", "PostToolUse") for group in events[event]
                   if "Write" in group["matcher"] for h in group["hooks"]]
        self.assertEqual(list(bench.WRITE_HOOKS), started)

    def test_a_failed_row_and_repeated_runs_are_said(self):
        import bench
        text = bench.render({"pages": 50, "links": 9, "log_lines": 4, "repeat": 3,
                             "commands": [{"what": "check", "seconds": 0.5, "exit": 1}], "hooks": [], "vault": []}, None)
        self.assertIn("log lines; each row is the fastest of 3 runs\n", text)
        self.assertIn("     0.500 s  check  (exit 1)", text)

    def test_fastest_keeps_the_shortest_run_and_the_last_result(self):
        import bench
        waits = iter((0.02, 0.0, 0.01))
        seconds, out = bench.fastest(3, lambda: time.sleep(next(waits)) or "done")
        self.assertLess(seconds, 0.01)
        self.assertEqual(out, "done")

    def test_a_brain_too_small_to_time_is_refused_through_the_brain_command(self):
        r = subprocess.run([sys.executable, os.path.join(ENGINE, "bin", "brain"), "bench", "--pages", "5"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("--pages is at least 10", r.stderr)


class ExportEdges(TempBrain):
    def test_by_name_and_nothing_to_export(self):
        self.write("cortex/concepts/one.md", concept("Plain.", title="One"))
        out = os.path.join(self.root, "exp")
        r = run_brain(self.root, "export", "One", "--out", out)
        self.assertIn("exported 1 pages", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(out, "cortex/concepts/one.md")))
        none = run_brain(self.root, "export", "--published")
        self.assertEqual(none.returncode, 1)
        self.assertIn("nothing to export", none.stderr)

    def test_frontmatter_stripping_leaves_odd_text_alone(self):
        sys.path.insert(0, SCRIPTS)
        import export
        self.assertEqual(export.strip_frontmatter("no frontmatter"), "no frontmatter")
        self.assertEqual(export.strip_frontmatter("---\nnever closed"), "---\nnever closed")


class ChatShapes(TempBrain):
    def convert(self, data, *extra):
        src = self.write("export.json", json.dumps(data))
        out = os.path.join(self.root, "out")
        r = run_brain(None, "chats", src, out, "--min-words", "2", *extra)
        files = sorted(os.listdir(out)) if os.path.isdir(out) else []
        return r, files

    def test_generic_shape_wrapped_export_collisions_and_skips(self):
        conv = {"title": "Same", "messages": [{"role": "user", "content": {"text": "a generic message"}},
                                              {"sender": "bot", "text": "another reply here"},
                                              {"role": "x", "content": {"text": 5}}, {"role": "x", "content": 7},
                                              "not a message"]}
        r, files = self.convert({"conversations": [conv, conv, {"odd": True}, "nope",
                                                   {"title": "tiny", "messages": [{"role": "u", "content": "hi"}]}]},
                                "--min-words", "3")
        self.assertEqual(files, ["same-2.md", "same.md"])
        self.assertIn("wrote 2 files", r.stdout)
        self.assertIn("skipped 1 short, 2 in an unrecognised shape", r.stdout)
        with open(os.path.join(self.root, "out", "same.md"), encoding="utf-8") as fh:
            self.assertIn("**user**\n\na generic message", fh.read())

    def test_not_a_list_is_refused(self):
        r, _ = self.convert({"conversations": "nope"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("unrecognised export shape", r.stderr)


class QuietHooks(TempBrain):
    """Hooks act only inside a brain, on input they can read, on files they guard."""

    def hook(self, name, payload, *args, raw=None, **env_vars):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": self.root, **env_vars}
        return subprocess.run([sys.executable, os.path.join(HOOKS, name), *args],
                              input=raw if raw is not None else json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def test_unreadable_input_is_let_through(self):
        for name, args in (("protect_expected.py", ()), ("protect_senses.py", ()), ("scan_secrets.py", ()),
                           ("validate_page.py", ()), ("validate_page.py", ("--pre",))):
            self.assertEqual(self.hook(name, None, *args, raw="not json").returncode, 0, name)

    def test_outside_a_brain_every_hook_is_silent(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            for name in ("protect_expected.py", "scan_secrets.py", "check_recall.py"):
                r = self.hook(name, {"tool_name": "Write", "tool_input": {"file_path": "x"}},
                              CLAUDE_PROJECT_DIR=elsewhere)
                self.assertEqual((r.returncode, r.stdout), (0, ""), name)  # exit 0: nothing blocked or asked

    def test_files_a_hook_does_not_guard(self):
        new_decision = os.path.join(self.root, "cortex", "decisions", "new.md")
        self.assertEqual(self.hook("protect_expected.py", {"tool_name": "Write",
                                                           "tool_input": {"file_path": new_decision}}).returncode, 0)
        report = self.write("motor/report.md", "token AKIA" + "ABCDEFGHIJKLMNOP")  # motor/ is output, not memory
        self.assertEqual(self.hook("scan_secrets.py", {"tool_input": {"file_path": report}}).returncode, 0)
        page_path = self.write("cortex/concepts/a.md", concept(title="A"))
        self.assertEqual(self.hook("validate_page.py", {"tool_name": "NotebookEdit",
                                                        "tool_input": {"file_path": page_path}}, "--pre").returncode, 0)
        gone = os.path.join(self.root, "cortex", "concepts", "gone.md")
        self.assertEqual(self.hook("validate_page.py", {"tool_input": {"file_path": gone}}).returncode, 0)

    def test_sudo_copy_onto_an_input_is_blocked(self):
        self.write("senses/a.md", "as it arrived")
        r = self.hook("protect_senses.py", {"tool_name": "Bash", "tool_input": {"command": "sudo cp x.md senses/a.md"}})
        self.assertEqual(r.returncode, 2)

    def test_another_skill_reading_pages_is_not_a_recall(self):
        t = self.write("t.jsonl", "\n".join(json.dumps(e) for e in (
            {"type": "user", "message": {"content": "tidy up"}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Skill", "input": {"skill": "aibrain:maintain"}},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "cortex/concepts/a.md"}}]}})))
        self.assertEqual(self.hook("check_recall.py", {"transcript_path": t}).returncode, 0)

    def test_no_git_means_no_engine_line_and_no_history(self):
        self.write("engine/.claude-plugin/plugin.json", "{}")
        empty = tempfile.mkdtemp()
        try:
            r = self.hook("wake_up.py", {}, CLAUDE_PLUGIN_ROOT="/cache/aibrain/abcdef1234", PATH=empty)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("Engine", r.stdout)
            env = dict(os.environ, PATH=empty)
            check = run_brain(self.root, "check", "--json", env=env)
            self.assertEqual(json.loads(check.stdout)["history"], [])
        finally:
            os.rmdir(empty)


class Decisions(TempBrain):
    def git(self, *args):
        subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       capture_output=True, check=True)

    def test_open_decisions_may_change_and_removing_a_decided_one_is_caught(self):
        decided = dict(DECIDED, status="decided", review="2027-01-01", revisit_if="x")
        body = "## Expected\n- [hypothesis] Few leave.\n## Decision\n- [decision] Raise.\n"
        self.write("cortex/decisions/open.md", page("decision", "## Expected\nmaybe\n", **dict(DECIDED, status="open")))
        made = self.write("cortex/decisions/made.md", page("decision", body, **decided))
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "one")
        self.write("cortex/decisions/open.md", page("decision", "## Expected\nchanged\n", **dict(DECIDED, status="open")))
        os.remove(made)
        r = run_brain(self.root, "check", "--json")
        self.assertEqual(json.loads(r.stdout)["history"],
                         ["cortex/decisions/made.md: a decided decision was removed since the last commit"])


class ModelCorners(TempBrain):
    def test_frontmatter_comments_and_lines_without_a_colon_are_skipped(self):
        fields, _ = vaultlib.parse_frontmatter("---\n# a comment\njust words\ntitle: T\n---\n")
        self.assertEqual(fields, {"title": "T"})
        self.assertEqual(vaultlib.schema_problems("no frontmatter at all", stem="x", rel="cortex/concepts/x.md"),
                         ["missing frontmatter block"])

    def test_a_brain_without_claude_md(self):
        os.remove(os.path.join(self.root, "CLAUDE.md"))
        self.assertEqual((vaultlib.owner_goals(self.root), vaultlib.tag_vocabulary(self.root)), ([], None))

    def test_empty_brain_and_isolated_pages(self):
        v = self.brain()
        self.assertEqual((v.hubs(), v.clusters()), ([], []))
        self.write("cortex/concepts/alone.md", concept(title="Alone"))
        self.write("cortex/concepts/x.md", concept("[[y]]", title="X"))
        self.write("cortex/concepts/y.md", concept(title="Y"))
        self.assertEqual([[p.stem for p in c] for c in self.brain().clusters()], [["x", "y"]])

    def test_log_lines_without_an_arrow_or_a_real_date_strengthen_nothing(self):
        self.write("cortex/concepts/a.md", concept(title="A"))
        self.log("2026-10-01 recall something with no arrow", "2026-02-30 recall q -> [[a]]",
                 "2026-10-02 recall q -> [[a]]")
        v = self.brain()
        self.assertEqual(v.recall_dates[v.resolve("a")], [datetime.date(2026, 10, 2)])

    def test_secret_scan_skips_binary_and_huge_files(self):
        sys.path.insert(0, SCRIPTS)
        import secret_scan
        binary = self.write("senses/img.bin", "")
        with open(binary, "wb") as fh:
            fh.write(b"\xff\xfe\x00AKIA" + b"ABCDEFGHIJKLMNOP")
        huge = self.write("senses/huge.txt", "AKIA" + "ABCDEFGHIJKLMNOP\n" + "x" * (secret_scan.TEXT_LIMIT + 1))
        self.assertEqual((secret_scan.scan_file(binary), secret_scan.scan_file(huge)), ([], []))


class RetrievalCorners(TempBrain):
    def test_project_links_to_system_pages_are_not_seeds(self):
        self.write("hippocampus/index.md", page("index", "[[spacing]]"))
        self.write("cortex/concepts/spacing.md", concept("Spread study.", title="Spacing"))
        self.write("cortex/concepts/far.md", concept("Unrelated.", title="Far"))
        self.write("prefrontal/exam/CLAUDE.md", page("project", "[[index]] [[far]]", title="Exam", status="active"))
        rows = [r["page"].stem for r in self.brain().recall("spacing", project="exam")]
        self.assertEqual(rows, ["spacing", "far"])

    def test_pages_only_recalled_together_are_suggested_and_projects_are_at_hand(self):
        self.write("cortex/concepts/x.md", concept(title="X"))
        self.write("cortex/concepts/y.md", concept(title="Y"))
        self.log(f"{ago(1)} recall q -> [[x]], [[y]]")
        (a, b, score, why), = self.brain().link_suggestions()
        self.assertEqual((a.stem, b.stem, why), ("x", "y", "recalled together (1.0)"))
        self.log()
        self.write("prefrontal/p/CLAUDE.md", page("project", "[[x]] [[index]]", title="P", status="active"))
        self.write("hippocampus/index.md", page("index", "[[x]]"))
        self.assertEqual([p.stem for p in self.brain().at_hand()], ["x"])


if __name__ == "__main__":
    unittest.main()


class Branches(TempBrain):
    """The other side of each decision the code makes: the case the feature tests do not take."""

    def test_an_ancient_co_recall_associates_nothing_and_does_not_crash(self):
        # Regression: a co-recall decayed to 0.0 became a page's only link and divided by zero.
        self.write("cortex/concepts/alpha.md", concept("alpha words", title="Alpha"))
        self.write("cortex/concepts/beta.md", concept("beta words", title="Beta"))
        self.log("1700-01-01 recall old -> [[alpha]], [[beta]]")
        v = self.brain()
        self.assertEqual(v.association_graph()[v.resolve("alpha")], {})
        self.assertEqual([r["page"].stem for r in v.recall("alpha")], ["alpha"])

    def test_cached_views_are_computed_once(self):
        self.write("dormant/old.md", concept("faded", title="Old"))
        self.write("dormant/notes.txt", "not a page")
        self.write("dormant/README.md", "about dormant")
        v = self.brain()
        self.assertIs(v.dormant_pages, v.dormant_pages)
        self.assertEqual([p.stem for p in v.dormant_pages], ["old"])
        self.assertIs(v.edge_weights(), v.edge_weights())

    def test_pairs_that_need_no_suggestion(self):
        self.write("cortex/concepts/x.md", concept("[[y]]", title="X"))
        self.write("cortex/concepts/y.md", concept(title="Y"))
        self.write("cortex/episodes/e.md", page("episode", title="E"))
        self.log(f"{ago(1)} recall q -> [[x]], [[y]]", f"{ago(1)} recall q -> [[x]], [[e]]",
                 f"{ago(1)} recall q -> [[index]], [[ghost]]")
        v = self.brain()
        self.assertEqual(v.link_suggestions(), [])  # linked already, or an episode: nothing to propose
        self.assertEqual(sorted(p.stem for p in v.at_hand()), ["e", "x", "y"])  # unresolved and system names ignored

    def test_typed_links_to_nothing_or_to_itself_are_not_edges(self):
        self.write("cortex/concepts/a.md", concept("(supports:: [[a]]) (extends:: [[ghost]]) [[a]]", title="A"))
        v = self.brain()
        self.assertEqual((v.typed_edges(), v.edges), (set(), set()))

    def test_unresolved_rehearsals_and_repeated_candidates(self):
        self.write("cortex/episodes/e.md", page("episode", "## Candidates\n- Idea - one\n- Idea - again\n"
                                                "- : nameless\n"))
        self.log(f"{ago(1)} recall rehearse -> [[ghost]]")
        v = self.brain()
        self.assertEqual(v.rehearsals, {})
        (row,) = v.candidate_tally()
        self.assertEqual((row["name"], len(row["episodes"])), ("Idea", 1))

    def test_an_empty_block_list_item_is_dropped(self):
        fields, _ = vaultlib.parse_frontmatter("---\naliases:\n  -\n  - Real\n---\n")
        self.assertEqual(fields["aliases"], ["Real"])

    def test_label_propagation_stops_at_its_round_limit(self):
        for a, b in (("p", "q"), ("q", "r"), ("r", "s")):
            self.write(f"cortex/concepts/{a}.md", concept(f"[[{b}]]", title=a.upper()))
        self.write("cortex/concepts/s.md", concept(title="S"))
        self.assertEqual(sum(len(c) for c in self.brain().clusters(rounds=1)), 4)

    def test_claude_and_chatgpt_noise_is_skipped(self):
        src = self.write("export.json", json.dumps([
            {"name": "c", "chat_messages": ["not a message", {"sender": "human", "text": "hello there friend"}]},
            {"title": "g", "mapping": {"s": {"message": {"author": {"role": "system"}, "content": {"parts": ["rules"]}}},
                                       "u": {"message": {"author": {"role": "user"}, "content": {"parts": ["hi all"]}}}}}]))
        out = os.path.join(self.root, "out")
        run_brain(None, "chats", src, out, "--min-words", "2")
        with open(os.path.join(out, "g.md"), encoding="utf-8") as fh:
            self.assertNotIn("rules", fh.read())
        self.assertEqual(len(os.listdir(out)), 2)

    def test_reports_without_their_optional_parts(self):
        self.write("cortex/concepts/spacing.md", concept("Spread study.", title="Spacing"))
        fields = dict(DECIDED, status="reviewed", review="2026-01-01", revisit_if="x", outcome="better")
        self.write("cortex/decisions/d.md", page("decision", "## Expected\n- [hypothesis] Works.\n## Decision\n"
                                                 "- [decision] Go.\n## Outcome\n- [hypothesis] Works. -> held\n",
                                                 **fields))
        decisions = run_brain(self.root, "introspect", "--decisions").stdout
        self.assertIn("hypothesis lines in reviewed decisions: held 1", decisions)
        self.assertNotIn("assumption lines", decisions)  # nothing to say about a tag with no results
        found = run_brain(self.root, "search", "spacing").stdout
        self.assertRegex(found, r'^search: "spacing"\n +\d+\.\d{3}  cortex/concepts/spacing\.md\n'
                                r' +\(no summary: open the page to judge it\)\n$')  # no recall detail
        self.assertNotIn("answers:", run_brain(None, "eval").stdout)

    def test_on_a_case_sensitive_system_senses_is_spelled_exactly(self):
        sys.path.insert(0, HOOKS)
        import protect_senses
        saved = sys.platform
        try:
            sys.platform = "linux"
            root = protect_senses.ROOT
            self.assertTrue(protect_senses.in_senses(os.path.join(root, "senses", "a.md")))
            self.assertFalse(protect_senses.in_senses(os.path.join(root, "Senses", "a.md")))
        finally:
            sys.platform = saved


class BrainCommandPaths(TempBrain):
    BIN = os.path.join(ENGINE, "bin", "brain")

    def run_brain(self, *args, cwd=None, **env):
        clean = {k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"}
        return subprocess.run([sys.executable, self.BIN, *args], capture_output=True, text=True,
                              cwd=cwd or self.root, env={**clean, **env})

    def test_help_brain_root_and_commands_without_a_root(self):
        self.assertIn("brain recall QUERY", self.run_brain().stdout)
        self.assertIn("brain search QUERY", self.run_brain("help").stdout)
        with tempfile.TemporaryDirectory() as elsewhere:
            r = self.run_brain("check", "--json", cwd=elsewhere, BRAIN_ROOT=self.root)
        self.assertEqual(json.loads(r.stdout)["pages"], 0)  # BRAIN_ROOT wins over the working folder
        self.assertIn("usage:", self.run_brain("chats").stderr)  # needs no brain, passes its arguments through

    def test_test_passes_a_name_filter_to_unittest(self):
        r = self.run_brain("test", "-k", "no_such_test_anywhere")
        self.assertIn("Ran 0 tests", r.stderr)


class PreCommit(unittest.TestCase):
    """The git hook refuses a commit that breaks the brain, before running the slow tests."""

    def test_a_broken_link_stops_the_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "brain")
            shutil.copytree(os.path.join(ENGINE, "templates", "brain"), repo)
            shutil.copytree(ENGINE, os.path.join(repo, "engine"),
                            ignore=shutil.ignore_patterns("__pycache__", "eval", "tests"))
            with open(os.path.join(repo, "cortex", "concepts", "a.md"), "w", encoding="utf-8") as fh:
                fh.write(concept("[[nowhere]]", title="A"))
            git = lambda *a: subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", *a],  # noqa: E731
                                            capture_output=True, text=True)
            git("init", "-q")
            git("config", "core.hooksPath", "engine/githooks")
            git("add", "-A")
            r = git("commit", "-qm", "broken")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("pre-commit: brain check failed", r.stderr)
            self.assertIn("a.md -> [[nowhere]]", r.stderr)


class VerdictLine(TempBrain):
    def test_a_brain_big_enough_to_judge_gets_no_size_warning(self):
        for i in range(10):
            self.write(f"cortex/concepts/c{i}.md", concept(f"[[c{(i + 1) % 10}]] " + "word " * 40, title=f"C{i}"))
        out = run_brain(self.root, "introspect").stdout
        self.assertIn("avg degree      2.00   acceptable", out)
        self.assertNotIn("verdict:", out)
