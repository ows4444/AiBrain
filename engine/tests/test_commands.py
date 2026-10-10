"""One calling convention: every command is run(root, args) -> dict and render(dict, args) -> text. Run: brain test

`brain` prints the text, or the dict with --json; another program calls `commands.call` and reads the dict.
The keys of each command's dict are pinned here: a caller relies on them, so a change to one is made on purpose.
"""
import json
import os
import shutil
import tempfile
from unittest import mock

from support import TempBrain, page, run_brain

import commands  # noqa: E402  (support puts engine/lib on the path)
import index  # noqa: E402

DATES = dict(created="2026-01-01", updated="2026-01-01")
PAGE = "<html><head><title>Spacing</title></head><body><article><h1>Spacing works</h1><p>" \
       + "A paragraph long enough to count as a page of text. " * 12 + "</p></article></body></html>"
ROW = ["page", "score", "summary", "title", "type"]
STATS = ["bytes", "enabled", "open", "pages", "path", "version"]
SUMMARY = ["avg_degree", "awaiting_consolidation", "broken_links", "by_type", "calibration", "components",
           "decisions_due", "due_for_rehearsal", "goals", "links", "main_component_share", "most_recalled",
           "orphan_rate", "pages", "projects", "stale_concept_rate", "tuning", "verdicts"]
# label -> (command, its arguments, the keys of what it returns). {root} is the brain, {tmp} a folder beside it.
KEYS = {
    "check": ("check", [], [
        "ambiguous", "avg_degree", "broken", "claims", "gaps", "history", "links", "log", "log_unread", "log_unresolved",
        "near_duplicates", "no_summary", "not_in_index", "orphans", "pages", "personal", "relations", "schema",
        "secrets", "shared_names", "stubs", "to_dormant", "tuning", "undated", "untagged"]),
    "introspect": ("introspect", [], SUMMARY),
    "introspect --json": ("introspect", ["--json"], SUMMARY + [
        "candidate_pairs", "candidates", "contradictions", "decisions", "dormant", "due", "encoding", "gaps",
        "intentions", "open", "queue", "relations", "risk", "stale", "usage"]),
    "introspect --due": ("introspect", ["--due"], SUMMARY + ["due", "risk"]),
    "introspect --graph": ("introspect", ["--graph"], SUMMARY + [
        "bridges", "bridges_estimated", "clusters", "cut_points", "hubs", "schema_candidates", "tags"]),
    "introspect --context": ("introspect", ["--context"], SUMMARY + ["context", "session_bytes"]),
    "introspect --snapshot": ("introspect", ["--snapshot"], SUMMARY + ["session_bytes", "snapshot"]),
    "search": ("search", ["spacing"], ["mode", "query", "results"]),
    "recall": ("recall", ["spacing"], ["mode", "query", "results"]),
    "recall, too little of the question": ("recall", ["spacing", "zebra", "quartz", "violin", "harbour"],
                                           ["mode", "query", "results", "weak"]),
    "recall, an idea held": ("recall", ["cramming"], ["held", "mode", "query", "results"]),
    "since": ("since", ["2026-01"], ["created", "from", "operations", "questions", "rehearsals", "until", "updated"]),
    "log": ("log", ["recall", "a question", "--pages", "spacing-effect"], ["line", "pages", "written"]),
    "index": ("index", [], ["added", "changed", "listed", "removed", "written"]),
    "fingerprint": ("fingerprint", [], ["recorded"]),
    "ground": ("ground", ["senses/cepeda.md"], ["checked", "file", "ungrounded"]),
    "graph": ("graph", [], ["edges", "format", "nodes", "out"]),
    "export": ("export", ["spacing-effect", "--keep-titles", "--out", "{tmp}/exported"],
               ["exported", "out", "personal", "unlinked"]),
    "capture": ("capture", ["a", "line", "to", "keep"], ["bytes", "note"]),
    "restore --dry-run": ("restore", ["old-idea", "--dry-run"], ["line", "page", "restored", "was"]),
    "cache": ("cache", [], STATS),
    "cache --rebuild": ("cache", ["--rebuild"], STATS + ["result"]),
    "cache --clear": ("cache", ["--clear"], ["path", "result"]),
    "errors": ("errors", [], ["groups", "last", "path", "total"]),
    "errors --clear": ("errors", ["--clear"], ["cleared", "path"]),
    "fetch": ("fetch", ["https://blog.example/spacing", "--file", "{tmp}/page.html"], [
        "author", "headings", "part", "path", "published", "raw_bytes", "saved", "saved_bytes", "title", "url",
        "words"]),
    "fit": ("fit", ["senses/cepeda.md"], ["held", "input", "pages", "words"]),
    "import --dry-run": ("import", ["obsidian", "{tmp}/vault", "--dry-run"], [
        "already", "attachments", "changed", "duplicates", "empty", "forgotten", "from", "imported", "into",
        "not_inputs", "source", "written"]),
    "new": ("new", ["concept", "--title", "A new idea"], ["filled", "page"]),
    "chats": ("chats", ["{tmp}/chats.json", "{tmp}/chats"], ["out", "short", "unknown", "written"]),
    "resume": ("resume", [], ["note", "text"]),
    "session": ("session", ["{tmp}/transcript.jsonl"], ["messages", "transcript"]),
    "forget": ("forget", ["cepeda-2006"], ["asset", "candidates", "citing", "episodes", "input", "other_inputs"]),
    "forget --yes": ("forget", ["cepeda-2006", "--yes"], [
        "asset", "candidates", "citing", "episodes", "input", "other_inputs", "removed"]),
    "tend --check": ("tend", ["--check"], ["at_risk", "contradictions", "date", "gaps", "inbox", "late", "needs",
                                           "rehearse", "reminders", "review", "revisit", "senses", "sleep"]),
    "eval": ("eval", [], ["problems", "retrieval"]),
    "eval --answers": ("eval", ["--answers", "{tmp}/answers.json"], ["answers", "problems", "retrieval"]),
    "eval --draft": ("eval", ["--draft", "2"], ["questions"]),
    "eval --set": ("eval", ["--set", "recall_floor=0.3"], ["problems", "retrieval", "set"]),
    "eval --from-log": ("eval", ["--from-log", "--root", "{root}"], ["from_log", "problems", "retrieval"]),
    "synth": ("synth", ["{tmp}/made", "--pages", "12"], ["links", "log_lines", "out", "pages"]),
    "bench": ("bench", ["--pages", "10"], ["commands", "hooks", "links", "log_lines", "pages", "repeat", "seed", "vault"]),
}
STATUSLINE = ["context", "decisions", "inbox", "line", "rehearse", "reminders", "senses", "sleep"]
RECALL_ROW = sorted(ROW + ["confidence", "flags", "from", "hop", "section"])


class Brain(TempBrain):
    def setUp(self):
        super().setUp()
        shutil.copy(index.TEMPLATE, os.path.join(self.root, index.INDEX))
        self.write("senses/cepeda.md", "the paper\n")
        self.write("cortex/concepts/spacing-effect.md", page(
            "concept", "Study spread over days lasts longer, as [[cepeda-2006]] found.\n", title="Spacing effect",
            status="established", summary="Study spread over days is kept longer.", **DATES))
        self.write("cortex/episodes/cepeda-2006.md", page(
            "episode", "A review of 254 studies of spacing.\n\n## Candidates\n\n- Cramming - massed study fades fast\n",
            title="Cepeda 2006", input="senses/cepeda.md", summary="A review of 254 studies.", **DATES))
        self.write("dormant/old-idea.md", page("concept", "It faded.\n", title="Old idea", status="emerging", **DATES))
        self.log("2026-01-05 recall how long between sessions -> [[spacing-effect]]")
        self.beside = tempfile.TemporaryDirectory()
        self.addCleanup(self.beside.cleanup)
        self.tmp_dir = self.beside.name
        for name, text in (
                ("page.html", PAGE),
                ("chats.json", json.dumps([{"name": "A chat", "created_at": "2025-01-02T00:00:00Z",
                                            "chat_messages": [{"sender": "human", "text": "hello there " * 80}]}])),
                ("transcript.jsonl", json.dumps({"type": "user", "timestamp": "2026-10-07T11:05:09.000Z",
                                                 "message": {"role": "user", "content": "first words"}}) + "\n"),
                ("answers.json", json.dumps({"q01": "See [[spacing-effect]]."})),
                ("vault/A note.md", "A note kept in another tool.\n")):
            os.makedirs(os.path.dirname(os.path.join(self.tmp_dir, name)), exist_ok=True)
            with open(os.path.join(self.tmp_dir, name), "w", encoding="utf-8") as fh:
                fh.write(text)

    def argv(self, args):
        return [a.replace("{root}", self.root).replace("{tmp}", self.tmp_dir) for a in args]


class EveryCommand(Brain):
    def test_the_keys_of_each_command_s_result_are_pinned(self):
        for label, (name, args, keys) in KEYS.items():
            with self.subTest(label):
                result = commands.call(name, self.argv(args), root=self.root)
                self.assertEqual(sorted(result), sorted(keys))
                json.dumps(result)  # plain data: nothing in it that JSON cannot carry
        rows = commands.call("search", ["spacing"], root=self.root)["results"]
        self.assertEqual(sorted(rows[0]), ROW)
        rows = commands.call("recall", ["spacing"], root=self.root)["results"]
        self.assertEqual(sorted(rows[0]), RECALL_ROW)

    def test_the_status_line_s_keys_are_pinned_too(self):
        r = run_brain(self.root, "statusline", "--json", input=json.dumps({"context_window": {"used_percentage": 41.6}}))
        result = json.loads(r.stdout)
        self.assertEqual(sorted(result), STATUSLINE)
        self.assertEqual((result["context"], result["line"]), (42, "brain | senses 0 | sleep 1 | rehearse 1 | context 42%"))

    def test_no_command_is_left_out_of_the_pin_or_of_the_help(self):
        pinned = {name for name, _, _ in KEYS.values()} | {"statusline", "mcp"}  # mcp serves stdin: test_mcp.py
        self.assertEqual(pinned, set(commands.COMMANDS))
        listed = run_brain(None, "help").stdout
        for name in (*commands.COMMANDS, "test"):
            self.assertIn(f"\n    brain {name} ", listed, name)

    def test_every_module_keeps_the_convention(self):
        for name, (module, _, _) in commands.COMMANDS.items():
            module = commands.importlib.import_module(module)
            for part in ("arguments", "run", "render"):
                self.assertTrue(callable(getattr(module, part, None)), f"{name}: {part}")


class OneSurface(Brain):
    def test_json_is_the_dict_and_the_text_is_its_rendering(self):
        for name, args in (("check", ["--guard"]), ("search", ["spacing"]), ("recall", ["spacing", "--all"]),
                           ("since", ["2026-01"]), ("introspect", ["--due", "--goals"]), ("forget", ["cepeda-2006"])):
            with self.subTest(name):
                module, parsed = commands.prepare(name, args, self.root)
                result = module.run(self.root, parsed)
                self.assertEqual(json.loads(run_brain(self.root, name, *args, "--json").stdout), result)
                self.assertEqual(run_brain(self.root, name, *args).stdout, module.render(result, parsed) + "\n")

    def test_every_command_takes_json_including_those_that_only_printed_before(self):
        made = json.loads(run_brain(self.root, "graph", "--format", "graphml", "--json").stdout)
        self.assertEqual((made["nodes"], made["edges"], made["format"]), (2, 1, "graphml"))
        self.assertTrue(os.path.exists(made["out"]))
        out = os.path.join(self.tmp_dir, "exp")
        sent = json.loads(run_brain(self.root, "export", "spacing-effect", "cepeda-2006", "--out", out, "--json").stdout)
        self.assertEqual(sent, {"exported": ["cortex/concepts/spacing-effect.md", "cortex/episodes/cepeda-2006.md"],
                                "out": out, "unlinked": 0, "personal": []})
        note = json.loads(run_brain(self.root, "resume", "--json").stdout)
        self.assertEqual(note["note"], os.path.join(".cache", "resume.md"))
        self.assertTrue(note["text"].startswith("# Where the work stood"))
        chats = json.loads(run_brain(None, "chats", os.path.join(self.tmp_dir, "chats.json"),
                                     os.path.join(self.tmp_dir, "chats"), "--json").stdout)
        self.assertEqual((chats["written"], chats["short"], chats["unknown"]),
                         ([os.path.join(self.tmp_dir, "chats", "2025-01-02-a-chat.md")], 0, 0))
        synth = json.loads(run_brain(None, "synth", os.path.join(self.tmp_dir, "s"), "--pages", "12", "--json").stdout)
        self.assertEqual((synth["pages"], synth["out"]), (12, os.path.join(self.tmp_dir, "s")))

    def test_a_dry_run_fetch_says_where_the_file_would_go(self):
        r = commands.call("fetch", ["https://blog.example/x", "--file", os.path.join(self.tmp_dir, "page.html"),
                                    "--dry-run", "--name", "x"], root=self.root)
        self.assertIsNone(r["saved"])
        self.assertRegex(r["path"], r"^senses/\d{4}-\d\d-\d\d-x\.md$")
        self.assertFalse(os.path.exists(os.path.join(self.root, r["path"])))

    def test_json_keeps_letters_as_they_are_written(self):
        self.write("cortex/concepts/cafe.md", page("concept", "Où l'on étudie.\n", title="Café", status="emerging",
                                                   summary="Où l'on étudie.", **DATES))
        out = run_brain(self.root, "search", "café", "--json").stdout
        self.assertIn('"title": "Café"', out)
        self.assertEqual(json.loads(out)["results"][0]["summary"], "Où l'on étudie.")

    def test_a_refusal_is_an_exception_for_a_caller_and_a_line_on_stderr_for_brain(self):
        for name, args, root, why, code in (
                ("nope", [], self.root, "brain: unknown command 'nope'; run `brain help`", 1),
                ("check", [], os.path.join(self.root, "cortex"), f"not a brain: {os.path.join(self.root, 'cortex')}", 1),
                ("check", [], None, "not a directory: None", 1),
                ("since", ["last-week"], self.root, "not a date or a month: last-week", 1),
                ("export", ["nope"], self.root, "no page named: nope", 1),
                ("recall", [], self.root, "brain recall: error: the following arguments are required: query", 2),
                ("check", ["--help"], self.root, "brain check: error: unrecognized arguments: --help", 2)):
            with self.subTest(name=name, args=args):
                with self.assertRaises(commands.Refused) as refused:
                    commands.call(name, args, root=root)
                self.assertEqual((str(refused.exception).splitlines()[-1], refused.exception.code), (why, code))
        r = run_brain(self.root, "recall")
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertTrue(r.stderr.startswith("usage: brain recall [-h] "))
        self.assertTrue(r.stderr.endswith("brain recall: error: the following arguments are required: query\n"))

    def test_help_for_one_command_names_its_arguments(self):
        r = run_brain(self.root, "since", "--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage: brain since [-h] [--until UNTIL] [--json] start", r.stdout)

    def test_a_call_leaves_the_working_directory_alone_and_brain_reads_paths_from_the_brain(self):
        here = os.getcwd()
        commands.call("graph", [os.path.join(self.tmp_dir, "g.csv")], root=self.root)
        self.assertEqual(os.getcwd(), here)
        with tempfile.TemporaryDirectory() as elsewhere:
            r = run_brain(self.root, "graph", "motor/graph/from-brain.csv", cwd=elsewhere)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(os.listdir(elsewhere), [])
        self.assertTrue(os.path.exists(os.path.join(self.root, "motor", "graph", "from-brain.csv")))

    def test_eval_leaves_the_cache_setting_as_it_found_it(self):
        for was in (None, "1"):
            env = {k: v for k, v in os.environ.items() if k != "BRAIN_CACHE"}
            with mock.patch.dict(os.environ, dict(env, **({"BRAIN_CACHE": was} if was else {})), clear=True):
                commands.call("eval", ["--k", "1"])
                self.assertEqual(os.environ.get("BRAIN_CACHE"), was)

    def test_a_status_line_that_crashes_prints_nothing_and_leaves_a_line_in_the_error_log(self):
        import statusline
        with mock.patch.object(statusline, "sent", side_effect=RuntimeError("boom")):
            self.assertEqual(commands.call("statusline", root=self.root), {"line": ""})
        with open(os.path.join(self.root, ".cache", "errors.log"), encoding="utf-8") as fh:
            self.assertIn("statusline error | RuntimeError: boom", fh.read())
