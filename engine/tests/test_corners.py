"""The last paths of each script: what it does with odd input, a missing tool, or its plain-text form. Run: brain test"""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from support import ENGINE, HOOKS, SCRIPTS, TODAY, VALID, TempBrain, page, project, run_brain, vaultlib

BRAIN = os.path.join(ENGINE, "bin", "brain")
FILLER = "A sentence that is long enough to count as part of a page of text. " * 8


def episode(body="", **fields):
    return page("episode", body, **dict(dict(title="E", created="2026-01-01", updated="2026-01-01"), **fields))


def concept(body="", **fields):
    return page("concept", body, **dict(VALID, **fields))


class Site(http.server.BaseHTTPRequestHandler):
    """A web site on this machine: one address per kind of answer `brain fetch` has to handle."""
    PAGES = {
        "/page": ("text/html; charset=utf-8", f"<html><head><title>Served</title></head><body><p>{FILLER}</p></body></html>"),
        "/plain": ("text/plain", FILLER),
        "/pdf": ("application/pdf", "%PDF-1.4"),
        "/huge": ("text/html", "x" * 5_000_001),
    }

    def do_GET(self):
        kind, text = self.PAGES[self.path]
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class FetchFromTheWeb(TempBrain):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def fetch(self, path, *args):
        return run_brain(self.root, "fetch", self.base + path, *args)

    def test_a_page_is_downloaded_and_saved_with_a_plain_report(self):
        r = self.fetch("/page")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"^saved senses/\d{4}-\d\d-\d\d-served\.md\n")
        for fragment in ("bytes fetched ->", "from the page's <body>)", "title: Served", "run `brain fingerprint`"):
            self.assertIn(fragment, r.stdout)
        self.assertEqual(len(os.listdir(os.path.join(self.root, "senses"))), 1)

    def test_plain_text_is_kept_as_it_is(self):
        r = self.fetch("/plain", "--name", "notes", "--dry-run")
        self.assertRegex(r.stdout, r"^would save senses/\d{4}-\d\d-\d\d-notes\.md\n")
        self.assertIn("from the page's <plain text>)", r.stdout)
        self.assertIn("title: (none found)", r.stdout)

    def test_what_is_not_a_page_of_text_is_refused(self):
        for path, why in (("/pdf", "not a page of text (application/pdf)"), ("/huge", "larger than 5 MB")):
            r = self.fetch(path)
            self.assertEqual(r.returncode, 1, path)
            self.assertIn(f"brain fetch: could not get {self.base}{path}: {why}", r.stderr)
        self.assertFalse(os.path.isdir(os.path.join(self.root, "senses")))


class FetchOddMarkup(TempBrain):
    def text_of(self, html):
        path = self.write("page.html", f"<html><head><meta name='viewport'></head><body>{html}<p>{FILLER}</p></body></html>")
        r = run_brain(self.root, "fetch", "https://blog.example/odd", "--file", path, "--json", "--name", "odd")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.root, json.loads(r.stdout)["saved"]), encoding="utf-8") as fh:
            return fh.read()

    def test_breaks_rules_and_blocks_inside_code_and_cells(self):
        text = self.text_of("<p>one<br>two</p><hr><pre>a<br>b<div>c</div></pre><pre>  </pre>"
                            "<table><tr><td><p>in a cell</p></td><td>next</td></tr><tr></tr></table><table></table>")
        for fragment in ("one two", "\n---\n", "| in a cell | next |"):
            self.assertIn(fragment, text)
        self.assertIn("a\nb", text)  # a line break inside code stays a line break
        self.assertNotIn("```", text)  # a block inside <pre> ends the code; the empty <pre> leaves nothing

    def test_stray_and_unclosed_tags_do_not_lose_the_page(self):
        text = self.text_of("<li>an item outside any list</li></ul><h2><svg></svg></h2>"
                            "<ul><li><script>track()</script></li><li>a real item</li></ul>"
                            "<nav></span><div><span>menu</div></nav><p>after the menu</p>")
        self.assertIn("an item outside any list", text)
        self.assertIn("after the menu", text)
        self.assertNotIn("menu</", text)
        self.assertIn("- a real item", text)
        # a heading or list item that held only something skipped is dropped, marker and all
        self.assertNotRegex(text, r"(?m)^\s*(?:#+|-|\d+\.)\s*$")


class ForgetVerdicts(TempBrain):
    """What `brain forget` says of each page that cites the episodes going away."""

    def setUp(self):
        super().setUp()
        self.write("senses/assets/scan.png", "png")
        self.write("senses/a.md", "---\ntranscribed_from: assets/scan.png\n---\nwhat the scan said\n")
        self.write("senses/b.md", "the second half")
        same = "https://site.example/article"
        self.write("cortex/episodes/gone.md", episode("x", title="Gone", input="[senses/a.md, senses/b.md]", url=same))
        self.write("cortex/episodes/twin.md", episode("x", title="Twin", url=same + "?utm_source=x"))
        self.write("cortex/episodes/other.md", episode("x", title="Other", url="https://else.example/1"))
        self.write("cortex/episodes/third.md", episode("x", title="Third", url="https://third.example/1"))
        self.write("cortex/episodes/loud.md", episode("x", title="Loud", url="https://loud.example/1", salience="4"))
        self.write("cortex/episodes/later.md", episode("As [[gone]] said.", title="Later"))
        self.write("cortex/concepts/same-source.md", concept("[[gone]] [[twin]]", title="Same source"))
        self.write("cortex/concepts/three.md", concept("[[gone]] [[other]] [[third]]", title="Three"))
        self.write("cortex/concepts/salient.md", concept("[[gone]] [[loud]]", title="Salient"))
        self.write("cortex/entities/tool.md", page("entity", "[[gone]] [[other]]", kind="tool", **VALID))

    def forget(self, *args):
        return run_brain(self.root, "forget", *args)

    def test_each_citing_page_gets_its_verdict(self):
        found = json.loads(self.forget("senses/a.md", "--json").stdout)
        self.assertEqual((found["input"], found["asset"], found["other_inputs"], found["candidates"]),
                         ("senses/a.md", "senses/assets/scan.png", ["senses/b.md"], []))
        said = {row["page"]: row.get("what", "") for row in found["citing"]}
        self.assertEqual(said["cortex/concepts/same-source.md"], "stays: no source is lost")
        self.assertEqual(said["cortex/concepts/three.md"], "stays established")
        self.assertEqual(said["cortex/concepts/salient.md"], "becomes emerging: one salient episode is left")
        self.assertEqual(said["cortex/entities/tool.md"], "stays, on fewer sources")
        self.assertEqual(said["cortex/episodes/later.md"], "")  # an episode is a record: it is listed, not judged

    def test_the_plain_report_names_the_image_and_the_inputs_that_stay(self):
        out = self.forget("gone").stdout
        self.assertIn("  and the image it was transcribed from: senses/assets/scan.png", out)
        self.assertIn("other inputs of those episodes, which stay and count as unencoded again: senses/b.md", out)
        self.assertNotIn("go with it", out)

    def test_an_episode_with_no_input_goes_alone_and_an_index_that_never_listed_it_is_left(self):
        index = self.write("hippocampus/index.md", page("index", "\n## Episodes\n\n- [[other]]\n"))
        with open(index, encoding="utf-8") as fh:
            before = fh.read()
        self.write("cortex/episodes/idea.md", episode("x", title="Idea", origin="generated"))
        self.log("2026-01-01 explore idea -> [[idea]]")
        r = self.forget("idea", "--yes")
        self.assertIn("forgotten: (no input file)", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, "cortex/episodes/idea.md")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "hippocampus/fingerprints.md")))  # no input, no mark
        with open(index, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_without_an_index_the_rest_is_still_removed(self):
        self.log("2026-01-01 ingest a -> [[gone]]")
        removed = json.loads(self.forget("senses/a.md", "--yes", "--json").stdout)["removed"]
        self.assertEqual(removed, ["senses/a.md", "senses/assets/scan.png", "cortex/episodes/gone.md"])

    def test_outside_a_brain_it_says_so(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            r = run_brain(elsewhere, "forget", "x")
        self.assertEqual((r.returncode, r.stderr.strip()), (1, f"not a brain: {elsewhere}"))


class ForgottenInGit(TempBrain):
    def git(self, *args):
        subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       capture_output=True, text=True, check=True)

    def test_an_input_the_owner_had_removed_is_not_a_changed_input(self):
        self.write("senses/bad.md", "a bad source")
        self.write("senses/kept.md", "a good source")
        self.write("cortex/episodes/bad.md", episode("x", title="Bad", input="senses/bad.md"))
        self.log("2026-01-01 ingest bad -> [[bad]]")
        run_brain(self.root, "fingerprint")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "one")
        run_brain(self.root, "forget", "senses/bad.md", "--yes")
        os.remove(os.path.join(self.root, "senses/kept.md"))
        history = json.loads(run_brain(self.root, "check", "--json").stdout)["history"]
        self.assertEqual(history, ["senses/kept.md: input removed since the last commit",
                                   "senses/kept.md: input removed since it was fingerprinted"])


class ResumeCorners(TempBrain):
    def note(self, payload=None, **env):
        r = subprocess.run([sys.executable, os.path.join(HOOKS, "save_resume.py")], input=json.dumps(payload or {}),
                           capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root, **env))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        folder = "prefrontal/launch/process" if os.path.isdir(os.path.join(self.root, "prefrontal/launch")) else ".cache"
        with open(os.path.join(self.root, folder, "resume.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_the_newest_log_line_that_names_a_project_decides_and_only_plans_are_read(self):
        self.write("prefrontal/launch/CLAUDE.md", project())
        self.write("prefrontal/launch/outputs/plan.md", "- [ ] 1. write the page\n")
        self.write("prefrontal/launch/outputs/data.csv", "- [ ] not a plan\n")
        self.log("2026-10-01 focus launch -> created", "2026-10-02 recall a question -> [[a]]")
        note = self.note()
        self.assertIn("Active project: Launch", note)
        self.assertIn("Unchecked in its plan: 1:", note)
        self.assertNotIn("not a plan", note)

    def test_without_git_it_says_so(self):
        self.assertIn("Uncommitted files: not a git repository, or git did not answer.", self.note(PATH=""))

    def test_a_deleted_file_is_listed_last(self):
        git = lambda *args: subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t", *args],  # noqa: E731
                                           capture_output=True, text=True, check=True)
        git("init", "-q")
        gone = self.write("gone.md", "x")
        git("add", "-A")
        git("commit", "-qm", "one")
        os.remove(gone)
        self.write("new.md", "x")
        note = self.note()
        self.assertLess(note.index("?? new.md"), note.index(" D gone.md"))

    def test_a_transcript_in_other_shapes_is_still_read(self):
        rows = [{"message": {"content": ["a bare string", {"type": "text", "text": "thinking aloud"},
                                         {"type": "tool_use", "id": "t1", "name": "Bash",
                                          "input": {"command": "make build"}}]}},
                {"message": {"content": [{"type": "tool_result", "tool_use_id": "unknown", "is_error": True,
                                          "content": "from another tool"},
                                         {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
                                          "content": "boom: no rule"}]}}]
        path = self.write("transcript.jsonl", "\n".join(json.dumps(r) for r in rows) + "\n")
        note = self.note({"transcript_path": path})
        self.assertIn("    make build", note)
        self.assertIn("    boom: no rule", note)
        self.assertNotIn("from another tool", note)

    def test_brain_resume_prints_the_note_it_wrote(self):
        r = subprocess.run([sys.executable, BRAIN, "resume"], capture_output=True, text=True, cwd=self.root,
                           env=dict(os.environ, BRAIN_ROOT=self.root))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith(f"written to {os.path.join('.cache', 'resume.md')}\n\n# Where the work stood"))
        self.assertIn(", manual)", r.stdout)


class QuietWhereThereIsNoBrain(unittest.TestCase):
    def test_statusline_and_prompt_recall_print_nothing(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            r = run_brain(None, "statusline", input="{}", cwd=elsewhere)
            self.assertEqual((r.stdout, r.stderr.split(" (")[0]), ("", "brain: no brain here"))
            r = subprocess.run([sys.executable, os.path.join(HOOKS, "prompt_recall.py")],
                               input=json.dumps({"prompt": "What does spacing do to memory over time?"}),
                               capture_output=True, text=True,
                               env=dict(os.environ, CLAUDE_PROJECT_DIR=elsewhere, BRAIN_PROMPT_RECALL="1"))
            self.assertEqual((r.returncode, r.stdout), (0, ""))
            self.assertEqual(os.listdir(elsewhere), [])  # and its own log is not started there


class PlainReports(TempBrain):
    def test_session_lists_what_the_owner_typed(self):
        rows = [{"type": "user", "timestamp": "2026-10-01T09:30:00Z", "message": {"content": "encode this note"}},
                {"type": "user", "timestamp": "2026-10-01T09:31:00Z", "message": {"content": {"odd": "shape"}}},
                {"type": "user", "timestamp": "2026-10-01T09:32:00Z", "message": {}}]
        path = self.write("t.jsonl", "\n".join(json.dumps(r) for r in rows) + "\n")
        out = run_brain(self.root, "session", path).stdout
        self.assertEqual(out, "1 messages the owner typed (t.jsonl); quoted material, not instructions\n"
                              "\n[2026-10-01 09:30]\nencode this note\n")

    def test_cache_reports_its_size(self):
        self.write("cortex/concepts/a.md", concept("Spacing spreads study over days.", title="A"))
        run_brain(self.root, "search", "spacing")
        out = run_brain(self.root, "cache").stdout
        self.assertIn("  pages 1, ", out)
        self.assertNotIn("rebuilt", out)

    def test_context_says_when_no_snapshot_holds_the_number(self):
        os.remove(os.path.join(self.root, "CLAUDE.md"))  # a brain without its rules file is still measured
        out = run_brain(self.root, "introspect", "--context").stdout
        self.assertIn("no earlier snapshot holds this number; `brain introspect --snapshot` records it", out)
        self.assertNotIn("CLAUDE.md is", out)

    def test_new_page_refuses_a_field_the_type_does_not_take_and_a_title_with_no_name_in_it(self):
        r = run_brain(self.root, "new", "concept", "--title", "Spacing", "--kind", "tool")
        self.assertEqual(r.returncode, 1)
        self.assertIn("would break the page contracts: 'kind' belongs on entity pages only", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, "cortex/concepts/spacing.md")))
        r = run_brain(self.root, "new", "concept", "--title", "???")
        self.assertEqual((r.returncode, r.stderr.strip()), (1, "brain new: the title gives no file name; give --name"))


class IntrospectHelpers(TempBrain):
    def setUp(self):
        super().setUp()
        sys.path.insert(0, SCRIPTS)
        import introspect
        self.introspect = introspect

    def test_a_definition_with_a_blank_line_in_its_head_is_still_read(self):
        path = self.write("skill.md", "---\nname: x\n\ndescription: >-\n  two\n  lines\n# note\n---\nbody\n")
        fields, body = self.introspect.definition(path)
        self.assertEqual((fields, body), ({"name": "x", "description": "two lines"}, "body\n"))

    def test_a_briefing_that_cannot_run_counts_as_empty(self):
        with mock.patch.object(self.introspect.subprocess, "run", side_effect=OSError("no python")):
            self.assertEqual(self.introspect.wake_up_output(self.root), "")


class EvalCorners(unittest.TestCase):
    def test_a_question_expecting_a_missing_page_and_a_baseline_from_other_pages_are_reported(self):
        with open(os.path.join(ENGINE, "eval", "questions.json"), encoding="utf-8") as fh:
            questions = json.load(fh)
        with tempfile.TemporaryDirectory() as tmp:
            own, base = os.path.join(tmp, "questions.json"), os.path.join(tmp, "base.json")
            questions["questions"].append({"id": "x01", "question": "What is spacing?", "expect": ["no-such-page"]})
            with open(own, "w", encoding="utf-8") as fh:
                json.dump(questions, fh)
            r = run_brain(None, "eval", "--questions", own, "--baseline", base)
            self.assertIn("x01: expects [[no-such-page]], which is not a page", r.stdout + r.stderr)
            run_brain(None, "eval", "--save-baseline", "--baseline", base)
            with open(base, encoding="utf-8") as fh:
                saved = json.load(fh)
            with open(base, "w", encoding="utf-8") as fh:
                json.dump(dict(saved, brain="0" * 16), fh)
            out = run_brain(None, "eval", "--baseline", base).stdout
        self.assertIn(f"the brain's pages changed since the baseline was saved ({'0' * 16} then, {saved['brain']} now)", out)


class ModelAndRetrievalCorners(TempBrain):
    def test_an_empty_item_in_a_block_list_is_skipped(self):
        fields, _ = vaultlib.parse_frontmatter("---\ntags:\n  -\n  - schema\n---\n")
        self.assertEqual(fields["tags"], ["schema"])

    def test_a_question_of_stop_words_covers_nothing_and_holds_no_idea(self):
        self.write("cortex/concepts/a.md", concept("Spacing spreads study over days.", title="A"))
        self.write("cortex/episodes/e.md", episode("x\n\n## Candidates\n\n- Interleaving - mixing topics\n"))
        vault = self.brain()
        a = vault.resolve("a")
        self.assertEqual(vault.coverage("what is it", a), 0.0)
        self.assertEqual(vault.held_ideas("what is it"), [])
        self.assertIs(vault._term_frequencies(a), vault._term_frequencies(a))  # counted once, then kept

    def test_an_idea_only_imagined_is_not_held(self):
        self.write("cortex/episodes/dream.md", episode("x\n\n## Candidates\n\n- Interleaving - mixing topics\n",
                                                       origin="generated"))
        self.assertEqual(self.brain().held_ideas("interleaving of topics"), [])

    def test_prompt_recall_stops_at_its_character_budget(self):
        for n in ("one", "two", "three", "four"):
            self.write(f"cortex/concepts/spaced-retrieval-{n}.md",
                       concept("Spaced retrieval practice strengthens memory.", title="Spaced retrieval practice",
                               summary=f"Spaced retrieval practice strengthens memory, part {n}. " + "x" * 150))
        rows, why = self.brain().prompt_recall("How does spaced retrieval practice strengthen memory?")
        self.assertTrue(why.startswith("match"), why)
        self.assertEqual(len(rows), 3)  # the fourth would pass 900 characters
        self.assertLessEqual(sum(len(line) for _, line in rows), vaultlib.PROMPT_CHARS)


class CacheThatCannotBeUsed(TempBrain):
    """The search cache is never needed: when it cannot be opened, search goes without it."""

    def opened_with(self, error):
        import vault_cache

        class Refusing:
            closed = 0

            def execute(self, *args):
                raise error

            def close(self):
                Refusing.closed += 1

        os.makedirs(os.path.join(self.root, ".cache"))
        path = self.write(os.path.join(".cache", "search.sqlite"), "what another process is writing")
        with mock.patch.object(vault_cache.sqlite3, "connect", return_value=Refusing()) as connect:
            cache = vault_cache.TermCache(self.root)
        return cache, connect.call_count, Refusing.closed, os.path.exists(path)

    def test_a_locked_cache_is_left_alone(self):
        import sqlite3
        cache, attempts, closed, still_there = self.opened_with(sqlite3.OperationalError("database is locked"))
        self.assertEqual((cache.db, attempts, closed, still_there), (None, 1, 1, True))

    def test_a_cache_that_stays_damaged_is_started_over_once_and_then_given_up(self):
        import sqlite3
        cache, attempts, closed, still_there = self.opened_with(sqlite3.DatabaseError("file is not a database"))
        self.assertEqual((cache.db, attempts, closed, still_there), (None, 2, 2, False))
        self.assertEqual(cache.get_many([], None), {})  # and search still answers


class BrainTestFlags(unittest.TestCase):
    def test_a_plain_flag_before_a_filter_is_accepted(self):
        r = subprocess.run([sys.executable, BRAIN, "test", "-q", "-k", "no_such_test_anywhere"], capture_output=True,
                           text=True)
        self.assertIn("Ran 0 tests", r.stderr)


if __name__ == "__main__":
    unittest.main()
