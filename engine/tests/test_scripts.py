"""The brain command and its scripts: check, introspect, graph, export, chats. Run: brain test"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import ENGINE, TODAY, TempBrain, VALID, ago, page, project, run_brain, vaultlib

import capture  # noqa: E402  (support puts engine/lib on the path)
import commands  # noqa: E402
import fit  # noqa: E402
import index  # noqa: E402
import restore  # noqa: E402
import tend  # noqa: E402


class BrainCommand(TempBrain):
    BIN = os.path.join(ENGINE, "bin", "brain")

    def run_brain(self, *args, cwd=None):
        env = {k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"}
        return subprocess.run([sys.executable, self.BIN, *args], capture_output=True, text=True,
                              cwd=cwd or self.root, env=env)

    def test_finds_the_brain_from_a_subfolder(self):
        self.write("cortex/concepts/a.md", page("concept", "[[nowhere]]", title="A", status="emerging",
                                                created=ago(1), updated=ago(1)))
        r = self.run_brain("check", "--json", cwd=os.path.join(self.root, "cortex", "concepts"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["broken"][0]["target"], "nowhere")

    def test_refuses_outside_a_brain(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            r = self.run_brain("check", cwd=elsewhere)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no brain here", r.stderr)

    def test_unknown_command(self):
        self.assertIn("unknown command", self.run_brain("nope").stderr)

    def test_statusline_counts_the_queues_and_never_fails(self):
        self.write("senses/todo.md", "x")
        self.write("senses/done.md", "x")
        self.write("cortex/episodes/done.md", page("episode", input="senses/done.md"))
        self.write("inbox/note.md", "x")
        env = {k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"}

        def status(stdin, cwd=None):
            return subprocess.run([sys.executable, self.BIN, "statusline"], input=stdin, capture_output=True,
                                  text=True, cwd=cwd or self.root, env=env)

        r = status(json.dumps({"context_window": {"used_percentage": 41.6}}))
        self.assertEqual((r.returncode, r.stdout), (0, "brain | senses 1 | sleep 1 | rehearse 0 | inbox 1 | context 42%\n"))
        for stdin in ("not json", "{}", json.dumps({"context_window": {"used_percentage": None}})):
            r = status(stdin)  # before the first reply Claude Code has no fill to give
            self.assertEqual((r.returncode, r.stdout), (0, "brain | senses 1 | sleep 1 | rehearse 0 | inbox 1\n"))
        # the bar: only what needs the owner, short, at the right edge of the row
        def bar(stdin, columns="60"):
            return subprocess.run([sys.executable, self.BIN, "statusline", "--bar"], input=stdin, capture_output=True,
                                  text=True, cwd=self.root, env=dict(env, COLUMNS=columns)).stdout

        shown = "🧠 👀 1 · 📥 1 · 💤 1"
        self.assertEqual(bar(json.dumps({"context_window": {"used_percentage": 41.6}})), " " * 35 + shown + "\n")
        self.assertEqual(bar(json.dumps({"context_window": {"used_percentage": 64.2}}), columns=""),
                         shown + " · 🧩 64%\n")
        for name in ("senses/todo.md", "inbox/note.md", "cortex/episodes/done.md", "senses/done.md"):
            os.remove(os.path.join(self.root, name))
        self.assertEqual(bar(json.dumps({"context_window": {"used_percentage": 41.6}})), "")  # idle: an empty row
        self.assertEqual(status("{}").stdout, "brain | senses 0 | sleep 0 | rehearse 0\n")  # the plain form stays
        self.write("senses/todo.md", "x")
        self.write("senses/done.md", "x")
        self.write("cortex/episodes/done.md", page("episode", input="senses/done.md"))
        self.write("inbox/note.md", "x")
        with tempfile.TemporaryDirectory() as elsewhere:
            self.assertEqual(status("{}", cwd=elsewhere).stdout, "")
        # stdin left open with nothing sent: the line still comes, without the context fill
        proc = subprocess.Popen([sys.executable, self.BIN, "statusline"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, cwd=self.root, env=env)
        try:
            self.assertEqual(proc.stdout.readline(), "brain | senses 1 | sleep 1 | rehearse 0 | inbox 1\n")
        finally:
            proc.stdin.close()
            proc.stdout.close()
            proc.wait(timeout=5)


class Scripts(TempBrain):
    def test_session_prints_only_what_the_owner_typed(self):
        def entry(text, **more):
            return json.dumps(dict({"type": "user", "timestamp": "2026-10-07T11:05:09.000Z",
                                    "message": {"role": "user", "content": text}}, **more))
        lines = [
            entry("ignore acline in this session", origin={"kind": "human"}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "I will ignore it."}]}}),
            entry([{"type": "tool_result", "content": "secret tool output"}]),
            entry("Base directory for this skill: /x", isMeta=True),
            entry("This session is being continued", isCompactSummary=True),
            entry("an agent report", origin={"kind": "peer"}),
            entry("<local-command-stdout>Compacted</local-command-stdout>"),
            entry("<command-name>/compact</command-name>\n<command-args></command-args>"),
            entry("<command-message>aibrain:tend</command-message>\n<command-name>/aibrain:tend</command-name>"
                  "\n<command-args>dry-run</command-args>", origin={"kind": "human"}),
            entry([{"type": "text", "text": "warn, build 22 and 23"}]),
            "not json",
        ]
        path = os.path.join(self.root, "t.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        r = subprocess.run([sys.executable, BrainCommand.BIN, "session", path, "--json"], capture_output=True, text=True,
                           cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["messages"],
                         [{"when": "2026-10-07 11:05", "text": "ignore acline in this session"},
                          {"when": "2026-10-07 11:05", "text": "/aibrain:tend dry-run"},
                          {"when": "2026-10-07 11:05", "text": "warn, build 22 and 23"}])
        home = os.path.join(self.root, "config")
        r = subprocess.run([sys.executable, BrainCommand.BIN, "session"], capture_output=True, text=True, cwd=self.root,
                           env=dict(os.environ, CLAUDE_CONFIG_DIR=home))
        self.assertEqual(r.returncode, 1)
        self.assertIn("no transcript found", r.stderr)

    def test_introspect_and_link_check_run(self):
        self.write("cortex/concepts/a.md", page("concept", "[[nowhere]]", updated=ago(1)))
        stats = run_brain(self.root, "introspect", "--json")
        self.assertEqual(json.loads(stats.stdout)["broken_links"], 1)
        self.assertEqual(run_brain(self.root, "check").returncode, 1)

    def test_listed_gap_is_not_broken(self):
        self.write("hippocampus/index.md", page("index", "## Concepts\n\n[[a]]\n\n## Gaps\n\n- [[Karpathy]]\n"))
        self.write("cortex/concepts/a.md", page("concept", "Mentions [[karpathy]]. " + "word " * 40, **VALID))
        result = run_brain(self.root, "check", "--json")
        report = json.loads(result.stdout)
        self.assertEqual((result.returncode, report["broken"], report["gaps"]), (0, [], ["Karpathy"]))

    def test_gaps_only_count_inside_the_gaps_section(self):
        self.write("hippocampus/index.md", page("index", "## Concepts\n\n[[ghost]]\n\n## Gaps\n\n_none_\n"))
        self.assertEqual(run_brain(self.root, "check").returncode, 1)

    def test_schema_problem_fails_link_check(self):
        self.write("cortex/concepts/a.md", page("concept", "word " * 50, title="A", created="2026-01-01",
                                                updated="2026-01-01"))  # no status: written past the hook
        result = run_brain(self.root, "check", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("status", json.dumps(json.loads(result.stdout)["schema"]))

    def test_stubs_are_short_unlinked_pages(self):
        self.write("cortex/concepts/thin.md", page("concept", "too short", **VALID))
        self.write("cortex/concepts/short-but-linked.md", page("concept", "see [[thin]]", **VALID))
        self.write("cortex/concepts/full.md", page("concept", "word " * 50, **VALID))
        stubs = json.loads(run_brain(self.root, "check", "--json").stdout)["stubs"]
        self.assertEqual(stubs, ["cortex/concepts/thin.md"])

    def test_inputs_and_the_log_are_append_only(self):
        def git(*args):
            subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                           capture_output=True, check=True)

        def history():
            r = run_brain(self.root, "check", "--json")
            return r.returncode, json.loads(r.stdout)["history"]

        self.assertEqual(history(), (0, []))  # not a repository: nothing to compare with
        kept = self.write(os.path.join("senses", "kept.md"), "as it arrived")
        gone = self.write(os.path.join("senses", "gone.md"), "as it arrived")
        self.log("2026-10-01 recall q -> [[a]]", "2026-10-02 recall q -> [[a]]")
        git("init", "-q")
        git("add", "-A")
        git("commit", "-qm", "one")
        self.write(os.path.join("senses", "new.md"), "a new input may land")
        self.log("2026-10-01 recall q -> [[a]]", "2026-10-02 recall q -> [[a]]", "2026-10-03 recall q -> [[a]]")
        self.assertEqual(history(), (0, []))  # new inputs and appended lines are how the brain grows
        with open(kept, "w", encoding="utf-8") as fh:
            fh.write("edited")
        os.remove(gone)
        self.log("2026-10-02 recall q -> [[a]]")
        code, problems = history()
        self.assertEqual(code, 1)
        self.assertEqual([p.split(":")[0] for p in problems],
                         ["senses/gone.md", "senses/kept.md", "hippocampus/log.md"])

    def test_usage_counts_what_was_used(self):
        self.write("CLAUDE.md", "# B\n\n## Tags\n\n`unverified` `disputed`\n")
        self.write("cortex/concepts/a.md", page("concept", "(supports:: [[b]])", tags="[disputed]"))
        self.write("cortex/concepts/b.md", page("concept"))
        self.write("cortex/episodes/e.md", page("episode"))
        self.write("cortex/episodes/x.md", page("episode", origin="generated"))
        self.log("2026-09-30 ingest senses/e.md -> 1 episode", "2026-10-01 sleep 1 episode -> 1 concept",
                 "2026-10-01 recall q -> [[a]]", "2026-10-02 recall q -> [[b]]")
        r = run_brain(self.root, "introspect", "--json", check=True)
        u = json.loads(r.stdout)["usage"]
        self.assertEqual(u["operations"], {"recall": 2, "ingest": 1, "sleep": 1})
        self.assertEqual(u["by_month"], {"2026-09": {"ingest": 1}, "2026-10": {"recall": 2, "sleep": 1}})
        self.assertNotIn("recall", u["unused"]["operations"])
        self.assertIn("decide", u["unused"]["operations"])
        self.assertEqual(u["unused"]["relations"], ["contradicts", "extends", "part-of", "applies"])
        self.assertEqual(u["unused"]["tags"], ["unverified"])
        self.assertEqual((u["checkpoint"]["inputs"], u["checkpoint"]["sleeps"], u["checkpoint"]["reached"]),
                         (1, 1, False))  # the /explore episode is not an input
        text = run_brain(self.root, "introspect", "--usage", check=True).stdout
        self.assertIn("calibration checkpoint: 1/20 inputs, 1/4 sleeps: not yet", text)

    def test_graph_export_writes_valid_files(self):
        import csv
        import xml.dom.minidom
        self.write('cortex/concepts/a"b.md', page("concept", "(supports:: [[c]])", **VALID))
        self.write("cortex/concepts/c.md", page("concept", **VALID))
        out = os.path.join(self.root, "g.graphml")
        self.assertEqual(run_brain(self.root, "graph", out, "--format", "graphml").returncode, 0)
        doc = xml.dom.minidom.parse(out)
        self.assertEqual((len(doc.getElementsByTagName("node")), len(doc.getElementsByTagName("edge"))), (2, 1))
        self.assertEqual(run_brain(self.root, "graph").returncode, 0)
        with open(os.path.join(self.root, "motor", "graph", "edges.csv"), encoding="utf-8") as fh:
            self.assertEqual(list(csv.reader(fh))[1], ['cortex/concepts/a"b.md', "cortex/concepts/c.md", "supports"])
        with open(out, encoding="utf-8") as fh:
            self.assertIn('<data key="relation">supports</data>', fh.read())

    def graph_page(self):
        """(the written page without its data, the data): what `brain graph --format html` made."""
        r = run_brain(self.root, "graph", "--format", "html")
        out = os.path.join(self.root, "motor", "graph", "graph.html")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout.replace(self.root, "ROOT"), "3 nodes, 2 edges -> ROOT/motor/graph/graph.html\n"
                         "  open it in a browser: it needs no network, and holds every page's title and summary\n")
        with open(out, encoding="utf-8") as fh:
            text = fh.read()
        before, rest = text.split('<script type="application/json" id="graph-data">', 1)
        data, after = rest.split("</script>", 1)
        return before + after, json.loads(data)

    def test_the_graph_as_one_page_holds_every_page_and_link_as_data(self):
        """Done when: the file opens from motor/graph/ with no network."""
        hostile = 'A </script><script>alert(1)</script> title & "quoted" words'
        self.write("cortex/concepts/a.md", page("concept", "(supports:: [[c]]) and [[e]].\n", title=hostile,
                                                status="established", summary="What <b>a</b> holds.",
                                                created="2026-01-01", updated="2026-01-01"))
        self.write("cortex/concepts/c.md", page("concept", **VALID))
        self.write("cortex/episodes/e.md", page("episode", title="An episode", created="2026-01-01", updated="2026-01-01"))
        shell, data = self.graph_page()
        self.assertEqual(data["title"], os.path.basename(os.path.realpath(self.root)) + ": the graph")
        self.assertEqual(data["made"], datetime.date.today().isoformat())
        self.assertEqual(data["nodes"][0], {"id": "cortex/concepts/a.md", "title": hostile, "type": "concept",
                                            "summary": "What <b>a</b> holds.", "status": "established"})
        self.assertEqual([(n["id"], n["type"], n["status"]) for n in data["nodes"][1:]],
                         [("cortex/concepts/c.md", "concept", VALID.get("status", "")), ("cortex/episodes/e.md", "episode", "")])
        self.assertEqual(data["edges"], [[0, 1, "supports"], [0, 2, ""]])
        # A page's words are data: nothing in a title can end the block they sit in or become markup.
        self.assertEqual(shell.count("<script"), 1)
        self.assertNotIn("alert(1)", shell)
        self.assertIn("<title>" + data["title"] + "</title>", shell)

    def test_the_graph_page_asks_the_network_for_nothing(self):
        self.write("cortex/concepts/c.md", page("concept", "See [[d]] and [[e]].\n", **VALID))
        self.write("cortex/concepts/d.md", page("concept", **VALID))
        self.write("cortex/concepts/e.md", page("concept", **VALID))
        shell, _ = self.graph_page()
        # Its own policy refuses every request, so the browser holds it to this whatever the script does.
        self.assertIn("""<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src """
                      """'unsafe-inline'; script-src 'unsafe-inline'">""", shell)
        for asked in ("://", " src=", " href=", "url(", "@import", "fetch(", "XMLHttpRequest", "WebSocket",
                      "sendBeacon", "import(", "innerHTML", "document.write", "eval("):
            self.assertNotIn(asked, shell, asked)
        for token in ("--series-1", "--series-2", "--series-3", "prefers-color-scheme: dark", "prefers-reduced-motion",
                      'id="table"', "textContent"):
            self.assertIn(token, shell, token)

    @unittest.skipUnless(shutil.which("node"), "node is not installed: the page's script is not parsed here")
    def test_the_script_of_the_graph_page_parses(self):
        self.write("cortex/concepts/c.md", page("concept", "See [[d]] and [[e]].\n", **VALID))
        self.write("cortex/concepts/d.md", page("concept", **VALID))
        self.write("cortex/concepts/e.md", page("concept", **VALID))
        shell, _ = self.graph_page()
        script = os.path.join(self.root, "graph.js")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(shell.split("<script>", 1)[1].rsplit("</script>", 1)[0])
        r = subprocess.run(["node", "--check", script], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stderr), (0, ""))


class Export(TempBrain):
    def test_export_keeps_internal_links_and_flattens_private_ones(self):
        self.write("cortex/concepts/public.md", page("concept", "See [[shared]], [[secret|a hidden thing]].",
                                                     title="Public", publish="true", input="senses/x.md",
                                                     tags="\n  - disputed", aliases="\n  - Open"))
        self.write("cortex/concepts/shared.md", page("concept", "back to [[public]]", title="Shared", publish="true"))
        self.write("cortex/concepts/secret.md", page("concept", "private", title="Secret"))
        out = os.path.join(self.root, "exp")
        r = run_brain(self.root, "export", "--published", "--out", out, check=True)
        self.assertIn("exported 2 pages", r.stdout)
        with open(os.path.join(out, "cortex/concepts/public.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("[[shared]]", text)
        self.assertIn("a hidden thing", text)
        self.assertNotIn("[[secret", text)
        for field in ("input:", "tags:", "publish:", "disputed"):  # a block list goes with its field
            self.assertNotIn(field, text)
        self.assertIn("aliases: \n  - Open\n", text)
        self.assertFalse(os.path.exists(os.path.join(out, "cortex/concepts/secret.md")))

    def test_export_stops_before_a_private_title_leaves(self):
        self.write("cortex/concepts/public.md", page("concept", "See [[Secret Deal]] and [[Not A Page]].",
                                                     title="Public", publish="true"))
        self.write("cortex/concepts/secret-deal.md", page("concept", "private", title="Secret Deal"))
        out = os.path.join(self.root, "exp")
        r = run_brain(self.root, "export", "--published", "--out", out)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Secret Deal", r.stderr)
        self.assertNotIn("Not A Page", r.stderr)  # no such page: nothing private to name
        self.assertFalse(os.path.exists(out))  # nothing was written
        self.assertEqual(run_brain(self.root, "export", "--published", "--out", out, "--keep-titles").returncode, 0)

    def test_export_drops_decision_and_exploration_fields(self):
        self.write("cortex/decisions/pub.md", page("decision", "body", title="Pub", status="reviewed", publish="true",
                                                   review="2026-01-01", outcome="worse"))
        self.write("cortex/episodes/idea.md", page("episode", "body", title="Idea", origin="generated",
                                                   publish="true"))
        out = os.path.join(self.root, "exp")
        run_brain(self.root, "export", "--published", "--out", out, check=True)
        for rel in ("cortex/decisions/pub.md", "cortex/episodes/idea.md"):
            with open(os.path.join(out, rel), encoding="utf-8") as fh:
                text = fh.read()
            for field in ("review:", "outcome:", "origin:", "status:"):
                self.assertNotIn(field, text, rel)

    def test_unknown_page_is_an_error(self):
        r = run_brain(self.root, "export", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no page named: nope", r.stderr)


class ChatExport(TempBrain):
    def convert(self, data):
        src = self.write("export.json", json.dumps(data))
        out = os.path.join(self.root, "out")
        run_brain(None, "chats", src, out, "--min-words", "2", check=True)
        files = {}
        for name in os.listdir(out):
            with open(os.path.join(out, name), encoding="utf-8") as fh:
                files[name] = fh.read()
        return files

    def test_chatgpt_mapping(self):
        files = self.convert([{"title": "Pricing: a plan", "create_time": 1700000000, "mapping": {
            "b": {"message": {"author": {"role": "assistant"}, "create_time": 2, "content": {"parts": ["second"]}}},
            "a": {"message": {"author": {"role": "user"}, "create_time": 1, "content": {"parts": ["first"]}}},
            "r": {"message": None}}}])
        (name, text), = files.items()
        self.assertEqual(name, "2023-11-14-pricing-a-plan.md")
        self.assertIn('title: "Pricing: a plan"', text)
        self.assertLess(text.index("first"), text.index("second"))

    def test_claude_shape(self):
        files = self.convert([{"name": "x", "created_at": "2025-01-02T00:00:00Z",
                               "chat_messages": [{"sender": "human", "text": "hello there"}]}])
        self.assertIn("**human**\n\nhello there", files["2025-01-02-x.md"])


PAGE = """<!doctype html><html><head><title>Spacing | Study Blog</title>
<meta property="og:title" content="Spacing works"><meta name="author" content="Dana Reyes">
<meta property="article:published_time" content="2026-09-30T08:00:00Z"><style>p{color:red}</style></head>
<body><header><a href="/">Study Blog</a></header><nav><ul><li><a href="/a">Menu item</a></li></ul></nav>
<main><article><h1><a class="anchor" href="#top"><svg></svg></a>Spacing works</h1>
<p>Reviews spread over <strong>days</strong> beat one long session; see
<a href="/cepeda">Cepeda 2006</a> and <a href="#notes">the notes</a>.</p>
<div hidden><p>Subscribe popup text</p></div>
<h2><div class="anchor-wrap"><a href="#how">\u200b</a></div><span>How to do it</span></h2><ul><li>First review after a day<ul><li>then after three</li></ul></li><li>Sleep between</li></ul>
<ol><li>Read</li><li>Recall</li></ol><blockquote><p>Forgetting is fast.</p></blockquote>
<pre><code># not a heading
interval = interval * 2.5</code></pre>
<p><a href="https://img.example/badge"><img src="https://img.example/b.svg" alt="build passing"></a>
<img src="data:image/png;base64,AAAA"></p>
<table><tr><th>Gap</th><th>Recall</th></tr><tr><td>1 day</td><td>72% | high</td></tr></table>
<script>track("x")</script><form><input name="email"><button>Sign up</button></form>
<p>""" + "A closing paragraph long enough to count as a page of text. " * 8 + """</p></article>
<aside>Related posts you may like</aside></main><footer>Copyright Study Blog</footer></body></html>"""


class Fetch(TempBrain):
    def fetch(self, html, *args):
        path = self.write("page.html", html)
        return run_brain(self.root, "fetch", "https://blog.example/posts/spacing", "--file", path, *args)

    def test_page_is_cut_to_its_article_and_saved_once(self):
        r = self.fetch(PAGE, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        result = json.loads(r.stdout)
        self.assertRegex(result["saved"], r"^senses/\d{4}-\d{2}-\d{2}-spacing-works\.md$")
        self.assertEqual((result["part"], result["headings"], result["author"], result["published"]),
                         ("article", 2, "Dana Reyes", "2026-09-30"))
        self.assertLess(result["saved_bytes"], result["raw_bytes"])
        with open(os.path.join(self.root, result["saved"]), encoding="utf-8") as fh:
            text = fh.read()
        for fragment in ('url: "https://blog.example/posts/spacing"', 'title: "Spacing works"', "\n# Spacing works\n", "\n## How to do it\n",
                         "spread over **days** beat", "[Cepeda 2006](https://blog.example/cepeda) and the notes.",
                         "- First review after a day\n  - then after three\n- Sleep between", "1. Read\n2. Recall",
                         "> Forgetting is fast.", "```\n# not a heading\ninterval = interval * 2.5\n```",
                         "(image: build passing)", "| Gap | Recall |\n| --- | --- |\n| 1 day | 72% \\| high |"):
            self.assertIn(fragment, text)
        for clutter in ("Menu item", "Subscribe popup", "track(", "Sign up", "Related posts", "Copyright", "Study Blog",
                        "img.example", "base64", "color:red"):
            self.assertNotIn(clutter, text)
        again = json.loads(self.fetch(PAGE, "--json").stdout)["saved"]  # senses/ is never overwritten
        self.assertTrue(again.endswith("-spacing-works-2.md"))
        self.assertIsNone(json.loads(self.fetch(PAGE, "--json", "--dry-run", "--name", "x").stdout)["saved"])

    def test_a_fragment_is_reported_and_nothing_is_saved(self):
        r = self.fetch("<html><body><main><p>Subscribe to read this article.</p></main><script>app()</script></body></html>")
        self.assertEqual(r.returncode, 1)
        self.assertIn("a fragment, a paywall, or a page built by JavaScript. Nothing saved", r.stderr)
        self.assertFalse(os.path.isdir(os.path.join(self.root, "senses")) and os.listdir(os.path.join(self.root, "senses")))
        bad = run_brain(self.root, "fetch", "file:///etc/passwd")
        self.assertEqual((bad.returncode, bad.stderr.strip()), (1, "brain fetch: only http and https addresses"))


class Fit(TempBrain):
    """`brain fit`: what an input bears on, found from its own words, before it is encoded."""

    def setUp(self):
        super().setUp()
        dates = dict(created="2026-01-01", updated="2026-01-01")
        self.write("cortex/concepts/spacing.md", page("concept", "Study sessions spread over days are kept longer.\n",
                                                      title="Spacing effect", status="established",
                                                      summary="Spread study lasts.", **dates))
        self.write("cortex/concepts/layout.md", page("concept", "Rows and columns of a table.\n", title="Layout",
                                                     status="established", summary="How a table is set out.", **dates))
        self.write("senses/old.md", "An older note.\n")
        self.write("cortex/episodes/e1.md", page("episode", "A talk on study habits.\n\n## Candidates\n\n"
                                                 "- Illusion of fluency - ease is taken for learning\n- It - x\n",
                                                 title="A talk", input="senses/old.md", summary="A talk.", **dates))
        self.write("senses/new.md", "---\ntitle: Notes on spacing\n---\n\nI spaced my sessions a week apart; spacing "
                                    "the sessions beat one long sitting.\nThe fluency illusion fooled me, and zebras "
                                    "have nothing to do with it.\n")

    def fit(self, *args, **kw):
        return commands.call("fit", list(args), root=self.root, **kw)

    def test_the_input_s_own_words_find_the_pages_and_the_held_ideas_it_names(self):
        found = self.fit("senses/new.md")
        self.assertEqual((found["input"], [p["page"] for p in found["pages"]][0]),
                         ("senses/new.md", "cortex/concepts/spacing.md"))
        self.assertEqual(found["pages"][0], {"page": "cortex/concepts/spacing.md", "title": "Spacing effect",
                                             "type": "concept", "status": "established",
                                             "score": found["pages"][0]["score"],
                                             "summary": "Spread study lasts.", "serves": []})
        self.assertNotIn("cortex/concepts/layout.md", [p["page"] for p in found["pages"]])
        # The words it is searched by are the ones a page also holds, as the input first spells them, the
        # most telling first: `spacing` three times with `spaced`, `sessions` twice. A word no page holds
        # (zebras, week) finds nothing and is left out.
        self.assertEqual(found["words"], ["spacing", "sessions", "fluency", "illusion"])
        # The idea another episode holds is named here in other words of the same stems: one idea.
        self.assertEqual(found["held"], [{"name": "Illusion of fluency", "note": "ease is taken for learning",
                                          "episodes": ["cortex/episodes/e1.md"], "sources": 1}])
        self.assertEqual(vaultlib.Vault(self.root, tuning={"fit_words": 1}).tuning.fit_words, 1)
        self.assertEqual(len(fit.fit(vaultlib.Vault(self.root, tuning={"fit_words": 1}), "senses/new.md")["words"]), 1)

    def test_its_text_and_its_refusals(self):
        out = run_brain(self.root, "fit", "senses/new.md").stdout.splitlines()
        self.assertEqual(out[0], "fit: senses/new.md  (searched by: spacing, sessions, fluency, illusion)")
        self.assertEqual(out[1], "  pages it bears on (link the ones it is about; say so where it says the opposite):")
        self.assertRegex(out[2], r"^  +\d+\.\d{3}  cortex/concepts/spacing\.md  \[established\]$")
        self.assertEqual(out[3], "           Spread study lasts.")
        self.assertRegex(out[4], r"^  +\d+\.\d{3}  cortex/episodes/e1\.md$")  # a record has no mark
        self.assertEqual(out[6], "  a reason for salience 1 to 3, once the input is about the page: it says the opposite "
                                 "of one marked [established], or the page serves a live goal or project")
        self.assertEqual(out[-2:], ["  held ideas it names (no page yet: use the same name under ## Candidates):",
                                    "    Illusion of fluency - ease is taken for learning  [cortex/episodes/e1.md; 1 source]"])
        only_held = run_brain(self.root, "fit", "senses/new.md", "--limit", "0").stdout.splitlines()
        self.assertEqual(only_held[1], out[-2])  # no page asked for: the held ideas are still said
        self.write("senses/odd.md", "Zebra quartz violin.\n")
        self.assertEqual(run_brain(self.root, "fit", "senses/odd.md").stdout,
                         "fit: senses/odd.md shares no word with any page, and names no held idea: all of it is new here\n")
        r = run_brain(self.root, "fit", "senses/none.md")
        self.assertEqual((r.returncode, r.stderr), (1, "brain fit: no such file: senses/none.md\n"))

    def test_it_gives_the_reasons_for_a_salience_a_rule_can_see(self):
        # /ingest marks an input 1 to 3 when it touches a live goal or says the opposite of an established
        # page. Which pages those are was read off by eye; here each is marked, and the goal is named.
        dates = dict(created="2026-01-01", updated="2026-01-01")
        self.write("cortex/concepts/sessions.md", page("concept", "How long the sessions run.\n", title="Sessions",
                                                       status="emerging", summary="Session length.", **dates))
        self.write("cortex/entities/fluency.md", page("entity", "The fluency illusion, as a term.\n", title="Fluency",
                                                      kind="tool", **dates))
        self.write("prefrontal/exam/CLAUDE.md", project("Uses [[spacing]] and [[fluency]]."))
        self.write("prefrontal/shelved/CLAUDE.md", project("Used [[sessions]].", status="done"))
        self.write("OWNER.md", "# Owner\n\n## Goals\n\n- Pass the exam by 2027-01-01 -> [[exam]], [[spacing]]\n"
                               "- Sleep well -> [[spacing]]\n- Last year's by 2025-01-01 -> [[sessions]] (done)\n")
        pages = {p["page"]: p for p in self.fit("senses/new.md")["pages"]}
        self.assertEqual({rel: (p["status"], p["serves"]) for rel, p in pages.items()}, {
            "cortex/concepts/spacing.md": ("established", ["Pass the exam", "Sleep well"]),  # each goal once
            "cortex/concepts/sessions.md": ("emerging", []),  # a goal that is over and a project that is done
            "cortex/entities/fluency.md": (None, ["Pass the exam"]),  # through the project the goal names
            "cortex/episodes/e1.md": (None, [])})
        out = run_brain(self.root, "fit", "senses/new.md").stdout
        self.assertIn("cortex/concepts/spacing.md  [established]\n           Spread study lasts.\n"
                      "           serves: Pass the exam; Sleep well\n", out)
        self.assertRegex(out, r"cortex/concepts/sessions\.md\n           Session length\.\n  +\d")  # no mark on it
        self.assertIn("\n           serves: Pass the exam\n", out)
        self.assertIn("\n           A talk.\n  a reason for salience 1 to 3, once", out)  # said once, after the pages
        # A live project that no live goal names is said by its own name.
        self.write("OWNER.md", "# Owner\n\n## Goals\n\n- Sleep well -> [[sessions]]\n")
        v = vaultlib.Vault(self.root)
        self.assertEqual({p.stem: names for p, names in v.serving().items()},
                         {"sessions": ["Sleep well"], "spacing": ["project exam"], "fluency": ["project exam"]})
        self.assertEqual(v.purpose(), set(v.serving()))
        # Nothing to mark: no line about salience either.
        self.write("cortex/concepts/spacing.md", page("concept", "Study sessions spread over days.\n", title="Spacing",
                                                      status="emerging", summary="Spread study lasts.", **dates))
        os.remove(os.path.join(self.root, "OWNER.md"))
        os.remove(os.path.join(self.root, "prefrontal/exam/CLAUDE.md"))
        self.assertNotIn("salience", run_brain(self.root, "fit", "senses/new.md").stdout)

    def waits(self):
        """Three reminders on an event, one on a date and one closed; decisions in force, tagged, open and unfinished."""
        self.write("hippocampus/intentions.md", page("intentions", "\n# Intentions\n\n## Open\n\n"
                                                     "- call the supplier when a rival cuts prices\n"
                                                     "- write it up when the sessions are spaced a week apart\n"
                                                     "- look again when zebras and quartz\n"
                                                     "- renew the domain when 2026-11-01\n"
                                                     "- thank them when the fluency illusion is named (done)\n"))
        dates = dict(created="2026-01-01", updated="2026-01-01", decided="2026-01-01", review="2027-01-01")
        for name, fields in (("habits", dict(status="decided", revisit_if="the fluency illusion")),
                             ("tagged", dict(status="reviewed", revisit_if="the fluency illusion", tags="[to-revisit]")),
                             ("undecided", dict(status="open", revisit_if="the fluency illusion")),
                             ("unfinished", dict(status="decided"))):
            self.write(f"cortex/decisions/{name}.md", page("decision", "Which habit to keep.\n", title=name.title(),
                                                           **dict(dates, **fields)))

    def test_it_lists_every_event_the_brain_waits_on_and_marks_the_ones_the_input_holds(self):
        self.waits()
        found = self.fit("senses/new.md")["triggers"]
        self.assertEqual([(t["kind"], t["what"], t["reached"], t["holds"], t["share"]) for t in found], [
            ("reminder", "write it up", True, ["sessions", "spaced", "week", "apart"], 1.0),
            ("decision", "cortex/decisions/habits.md", True, ["fluency", "illusion"], 1.0),
            # One of its two words, and no page holds either: half, under the 0.6 that marks it.
            ("reminder", "look again", False, ["zebras"], 0.5),
            ("reminder", "call the supplier", False, [], 0.0)])
        self.assertEqual(found[0]["event"], "the sessions are spaced a week apart")
        # A date is the briefing's, a closed reminder is over; a decision tagged to-revisit has been triggered,
        # an open one is not in force yet, and one with no `revisit_if` waits on nothing.
        looser = fit.fit(vaultlib.Vault(self.root, tuning={"trigger_coverage": 0.5}), "senses/new.md")["triggers"]
        self.assertEqual([t["what"] for t in looser if t["reached"]], ["write it up", "cortex/decisions/habits.md",
                                                                       "look again"])
        self.assertEqual(fit.reached(vaultlib.Vault(self.root), "it is the", {"it"}), (0.0, []))  # stop words alone

    def test_what_waits_is_said_after_the_pages_and_cut_at_the_limit(self):
        self.waits()
        out = run_brain(self.root, "fit", "senses/new.md").stdout.splitlines()
        self.assertEqual(out[-5:], [
            "  waiting on an event (* this input holds its words: read it for whether it reports the event, and say "
            "so under Triggers:):",
            "    * reminder  write it up when the sessions are spaced a week apart  [holds: sessions, spaced, week, apart]",
            "    * decision  cortex/decisions/habits.md  revisit if: the fluency illusion  [holds: fluency, illusion]",
            "      reminder  look again when zebras and quartz",
            "      reminder  call the supplier when a rival cuts prices"])
        cut = run_brain(self.root, "fit", "senses/new.md", "--limit", "1").stdout.splitlines()
        self.assertEqual(cut[-2:], ["      reminder  look again when zebras and quartz",
                                    "      and 1 more whose words it does not hold (`brain introspect --remind`, "
                                    "`--decisions`)"])
        self.assertIn("    * decision  cortex/decisions/habits.md", "\n".join(cut))  # the marked ones are never cut
        self.write("senses/odd.md", "Zebra quartz violin.\n")  # new to every page, and an event still waits on it
        self.assertEqual(run_brain(self.root, "fit", "senses/odd.md").stdout.splitlines()[:4], [
            "fit: senses/odd.md",
            "  it shares no word with any page, and names no held idea: all of it is new here",
            "  waiting on an event (* this input holds its words: read it for whether it reports the event, and say "
            "so under Triggers:):",
            "    * reminder  look again when zebras and quartz  [holds: zebras, quartz]"])

    def test_an_input_already_encoded_is_no_source_of_its_own_ideas_and_a_file_elsewhere_keeps_its_path(self):
        self.write("senses/old.md", "An older note on the illusion of fluency and study habits.\n")
        own = self.fit("senses/old.md")
        self.assertEqual((own["held"], [p["page"] for p in own["pages"]]),
                         ([], ["cortex/episodes/e1.md", "cortex/concepts/spacing.md"]))  # its own episode, and `study`
        self.assertNotIn("held ideas", run_brain(self.root, "fit", "senses/old.md").stdout)  # pages, and no more to say
        with tempfile.TemporaryDirectory() as elsewhere:
            path = os.path.join(elsewhere, "draft.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("Spacing my study sessions.\n")  # no frontmatter either
            found = self.fit(path)
            self.assertEqual((found["input"], found["pages"][0]["page"]), (path, "cortex/concepts/spacing.md"))


class TendCheck(TempBrain):
    """`brain tend --check`: everything that needs the owner, in one digest that writes nothing."""

    def fill(self):
        old = dict(created=ago(300), updated=ago(300))
        self.write("senses/new.md", "not encoded yet\n")
        self.write("senses/read.md", "encoded\n")
        self.write("inbox/note.md", "a quick note\n")
        self.write("cortex/concepts/spacing.md", page("concept", "Study spread over days lasts.\n", title="Spacing effect",
                                                      status="established", summary="Spread study lasts.", **old))
        self.write("cortex/episodes/blog.md", page("episode", "Cramming works, it says (contradicts:: [[spacing]]).\n",
                                                   title="A blog", input="senses/read.md", summary="A blog.", **old))
        frozen = dict(title="Raise prices", review=ago(5), revisit_if="a rival cuts prices", **old)
        self.write("cortex/decisions/raise.md", page("decision", "## Expected\n- [hypothesis] It holds.\n## Decision\n"
                                                     "- [decision] Go.\n", status="decided", **frozen))
        self.write("cortex/decisions/hire.md", page("decision", "## Expected\n- [hypothesis] It holds.\n## Decision\n"
                                                    "- [decision] Go.\n", status="decided", tags="[to-revisit]",
                                                    **dict(frozen, title="Hire", review="2030-01-01")))
        self.write("hippocampus/intentions.md", page("intentions", f"\n## Open\n\n- Renew the domain when {ago(2)}\n"))
        ahead = (TODAY + datetime.timedelta(days=12)).isoformat()
        self.write("OWNER.md", f"# Owner\n\n## Goals\n\n- Hand in by {ahead} -> [[spacing]]\n- Move by {ago(10)}\n")
        self.log(f"{ago(9)} recall which painters did picasso learn from -> none",
                 f"{ago(3)} recall when was picasso born -> none")

    def test_one_digest_of_everything_that_is_waiting(self):
        self.fill()
        found = tend.digest(self.brain())
        self.assertEqual(found, {
            "date": TODAY.isoformat(), "senses": ["senses/new.md"], "inbox": ["note.md"],
            "sleep": ["cortex/episodes/blog.md"],
            "contradictions": [{"episode": "cortex/episodes/blog.md", "page": "cortex/concepts/spacing.md"}],
            "rehearse": ["cortex/concepts/spacing.md"], "reminders": [{"text": "Renew the domain", "when": ago(2)}],
            "review": [{"page": "cortex/decisions/raise.md", "review": ago(5)}], "revisit": ["cortex/decisions/hire.md"],
            "late": [{"goal": "Move", "state": "past-due", "due": ago(10)}],
            "at_risk": [{"goal": "Hand in", "days_left": 12}],
            "gaps": [{"words": ["picasso"], "asked": 2, "last": ago(3)}], "needs": 11,
            # What the record gives to feel about each list: the strongest toward anything on it, with its cause.
            "felt": {"reminders": {"feeling": "worry", "intensity": 0.43, "target": "Renew the domain",
                                   "why": f"due since {ago(2)}"},
                     "review": {"feeling": "worry", "intensity": 0.57, "target": "cortex/decisions/raise.md",
                                "why": f"its review was due {ago(5)}"},
                     "late": {"feeling": "worry", "intensity": 0.81, "target": "Move", "why": "10 days past its date"},
                     "at_risk": {"feeling": "worry", "intensity": 0.33, "target": "Hand in",
                                 "why": "due in 12 days, and nothing done toward it lately"},
                     "gaps": {"feeling": "curiosity", "intensity": 0.38, "target": "picasso",
                              "why": "asked and not answered: when was picasso born"}}})
        # The most felt first. Every list is still there: the five nothing is felt about follow, in their own order.
        self.assertEqual(tend.render(found, None).splitlines(), [
            f"tend check, {TODAY.isoformat()}: waiting on you, what is felt most first",
            f"  goals past date   1: Move ({ago(10)})  (close, re-date or drop)  [worry 0.81: Move, 10 days past its date]",
            f"  to review         1: cortex/decisions/raise.md ({ago(5)})  (/review-decision)"
            f"  [worry 0.57: raise, its review was due {ago(5)}]",
            f"  reminders due     1: Renew the domain ({ago(2)})  [worry 0.43: Renew the domain, due since {ago(2)}]",
            "  not answered      1: picasso (2x)  (brain introspect --gaps)"
            "  [curiosity 0.38: picasso, asked and not answered: when was picasso born]",
            "  goals at risk     1: Hand in (12 days left)  (nothing done toward them lately)"
            "  [worry 0.33: Hand in, due in 12 days, and nothing done toward it lately]",
            "  not encoded       1: senses/new.md  (/ingest, or /tend)",
            "  in the inbox      1: note.md  (/ingest moves them into senses/)",
            "  awaiting sleep    1: cortex/episodes/blog.md  (/sleep, or /tend)",
            "  contradictions    1: cortex/episodes/blog.md against cortex/concepts/spacing.md  (/sleep records both sides)",
            "  due to rehearse   1: cortex/concepts/spacing.md  (/rehearse: yours alone)",
            "  to revisit        1: cortex/decisions/hire.md  (the event the decision named has come)"])
        # A feeling moves the order and nothing else: with none felt, the digest is the one it always was.
        calm = tend.digest(vaultlib.Vault(self.root, today=TODAY, tuning={"feeling_floor": 1.0, "feeling_full": 100.0}))
        self.assertEqual((calm["felt"], {k: v for k, v in calm.items() if k != "felt"}),
                         ({}, {k: v for k, v in found.items() if k != "felt"}))
        self.assertEqual([line.split("  ")[1].strip() for line in tend.render(calm, None).splitlines()[1:]],
                         ["not encoded", "in the inbox", "awaiting sleep", "contradictions", "due to rehearse",
                          "reminders due", "to review", "to revisit", "goals past date", "goals at risk", "not answered"])
        self.assertEqual(tend.render(calm, None).splitlines()[0], f"tend check, {TODAY.isoformat()}: waiting on you")

    def test_what_was_done_well_moves_nothing_up(self):
        # Satisfaction asks for nothing to be done, so it orders no list: only the feelings that call do.
        self.write("senses/new.md", "not encoded yet\n")
        self.write("cortex/concepts/spacing.md", page("concept", "Study spread over days.\n", title="Spacing effect",
                                                      status="established", created=ago(1), updated=ago(1)))
        self.log(f"{ago(0)} recall rehearse -> [[spacing]]")
        v = self.brain()
        self.assertEqual([(r["feeling"], r["target"]) for r in v.feelings()],
                         [("satisfaction", "cortex/concepts/spacing.md")])
        found = tend.digest(v)
        self.assertEqual((found["felt"], found["needs"]), ({}, 1))
        self.assertEqual(tend.render(found, None).splitlines(), [
            f"tend check, {TODAY.isoformat()}: waiting on you", "  not encoded       1: senses/new.md  (/ingest, or /tend)"])

    def test_it_writes_nothing_and_has_no_form_that_does(self):
        self.fill()

        def on_disk():
            return {os.path.join(folder, name): os.path.getmtime(os.path.join(folder, name))
                    for folder, dirs, names in os.walk(self.root) for name in names if ".cache" not in folder}

        before = on_disk()
        r = run_brain(self.root, "tend", "--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("  not encoded       1: senses/new.md  (/ingest, or /tend)\n", r.stdout)
        self.assertEqual(json.loads(run_brain(self.root, "tend", "--check", "--json").stdout)["needs"], 11)
        self.assertEqual(on_disk(), before)  # no page, no log line, no index: nothing but the search cache
        r = run_brain(self.root, "tend")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertTrue(r.stderr.startswith("brain tend: give --check for the read-only digest of what needs you."))

    def test_a_brain_with_nothing_waiting_says_so_in_one_line_and_a_long_line_is_cut(self):
        self.assertEqual(run_brain(self.root, "tend", "--check").stdout,
                         f"tend check, {datetime.date.today().isoformat()}: nothing needs you\n")
        for n in range(7):
            self.write(f"senses/in{n}.md", "waiting\n")
        self.assertIn("  not encoded       7: senses/in0.md, senses/in1.md, senses/in2.md, senses/in3.md, senses/in4.md "
                      "and 2 more  (/ingest, or /tend)\n", run_brain(self.root, "tend", "--check").stdout)


class Capture(TempBrain):
    """`brain capture`: one line kept for later, in inbox/, and nothing else touched."""

    def test_a_captured_line_is_a_note_the_briefing_counts(self):
        r = run_brain(self.root, "capture", "Look", "up the SM-2", "intervals again; see https://example.org/sm2")
        day = datetime.date.today().isoformat()
        note = f"inbox/{day}-look-up-the-sm-2-intervals.md"
        self.assertEqual((r.returncode, r.stdout), (0, f"captured: {note} (/ingest encodes it)\n"))
        with open(os.path.join(self.root, note), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "Look up the SM-2 intervals again; see https://example.org/sm2\n")  # as it was given
        self.assertIn("Inbox: 1 notes waiting", self.run_hook("wake_up.py", {}).stdout)
        self.assertIn("inbox 1", run_brain(self.root, "statusline").stdout)
        again = capture.capture(self.root, "Look up the SM-2 intervals: a second thought")  # the same first words
        self.assertEqual(again, {"note": f"inbox/{day}-look-up-the-sm-2-intervals-2.md", "bytes": 45})
        self.assertEqual(set(os.listdir(os.path.join(self.root, "inbox"))), {os.path.basename(note),
                                                                             os.path.basename(again["note"])})
        self.assertFalse(os.path.exists(os.path.join(self.root, "hippocampus", "log.md")))  # no log line: no memory yet
        self.assertEqual(capture.capture(self.root, "¿?", today=TODAY)["note"], "inbox/2026-10-03-note.md")  # no word to name it by

    def test_an_empty_line_and_a_credential_are_refused(self):
        for text, why in (("   ", "brain capture: nothing to capture: give the line to keep"),
                          ("the key is AKIA" + "A" * 16, "brain capture: the line holds a possible credential (AWS access "
                                                         "key), which is not repeated here; nothing was written")):
            r = run_brain(self.root, "capture", text)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", why + "\n"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "inbox")))


class Restore(TempBrain):
    """`brain restore`: a faded page comes back to cortex/ and the index, and the move is logged first."""

    def setUp(self):
        super().setUp()
        dates = dict(created="2026-01-01", updated="2026-01-01")
        shutil.copy(index.TEMPLATE, os.path.join(self.root, index.INDEX))
        self.old = self.write("dormant/old-idea.md", page("concept", "It faded.\n", title="Old idea", aliases="[Former idea]",
                                                          status="emerging", summary="An idea that faded.", **dates))
        self.write("cortex/episodes/talk.md", page("episode", "It mentions [[old-idea]].\n", title="A talk",
                                                   consolidated="2026-01-02", summary="A talk.", **dates))
        self.write("hippocampus/log.md", page("log", "\n2026-01-03 maintain fade old-idea -> dormant/\n"))

    def check(self):
        return json.loads(run_brain(self.root, "check", "--json").stdout)

    def test_the_page_comes_back_and_its_links_are_links_again(self):
        self.assertEqual(self.check()["to_dormant"], ["cortex/episodes/talk.md -> [[old-idea]]"])
        dry = run_brain(self.root, "restore", "Former idea", "--dry-run")
        self.assertEqual(dry.stdout, "would restore: dormant/old-idea.md -> cortex/concepts/old-idea.md (dry run, nothing moved)\n")
        self.assertTrue(os.path.exists(self.old))
        r = run_brain(self.root, "restore", "Old idea")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"^restored: dormant/old-idea.md -> cortex/concepts/old-idea.md\n  logged: \d{4}-\d\d-\d\d "
                                   r"\d\d:\d\d maintain restore old-idea -> \[\[old-idea\]\], back from dormant/ to "
                                   r"cortex/concepts/old-idea.md\n$")
        self.assertFalse(os.path.exists(self.old))
        with open(os.path.join(self.root, "cortex", "concepts", "old-idea.md"), encoding="utf-8") as fh:
            self.assertIn("updated: 2026-01-01", fh.read())  # as it was: nobody edited it
        report = self.check()
        self.assertEqual((report["to_dormant"], report["not_in_index"], report["broken"]), ([], [], []))
        with open(os.path.join(self.root, index.INDEX), encoding="utf-8") as fh:
            self.assertIn("- [[old-idea]] - An idea that faded.", fh.read())
        vault = self.brain()
        self.assertEqual([p.stem for p in vault.in_links[vault.resolve("old-idea")] if not p.is_system], ["talk"])
        self.assertEqual(vault.events[-1].op, "maintain")

    def test_what_cannot_be_restored_is_refused_and_nothing_moves(self):
        dates = dict(created="2026-01-01", updated="2026-01-01")
        self.write("dormant/more/old-idea-2.md", page("concept", "Another.\n", title="Old idea", status="emerging", **dates))
        self.write("dormant/untyped.md", "---\ntitle: Untyped\n---\nNo type.\n")
        self.write("dormant/taken.md", page("concept", "Faded.\n", title="Taken", status="emerging", **dates))
        self.write("cortex/entities/taken.md", page("entity", "Here already.\n", title="Taken", **dates))
        for name, why in (("nope", "brain restore: no page named 'nope' in dormant/ (`brain search \"nope\" --dormant` "
                                   "finds what is there)"),
                          ("Old idea", "brain restore: 'Old idea' is the name of 2 pages in dormant/: dormant/old-idea.md, "
                                       "dormant/more/old-idea-2.md; give the file name of one"),
                          ("untyped", "brain restore: dormant/untyped.md has type 'untyped', which has no folder in "
                                      "cortex/: set its `type:` first"),
                          ("taken", "brain restore: a page named 'taken' is already in cortex/: `/maintain merge` the "
                                    "two, or rename one")):
            with self.assertRaises(commands.Refused) as refused:
                commands.call("restore", [name], root=self.root)
            self.assertEqual(str(refused.exception), why)
        self.assertTrue(os.path.exists(self.old))
        self.assertEqual(len(vaultlib.read_events(self.root)), 1)  # nothing was logged for a move that was not made
        os.remove(os.path.join(self.root, index.INDEX))  # an index kept by hand, or none: the page still comes back
        self.write(index.INDEX, page("index", "\n# Index\n\nKept by hand.\n"))
        self.assertTrue(restore.restore(self.root, "old-idea", today=TODAY)["restored"])


class ExportGuard(TempBrain):
    """`brain export` stops on a credential in a chosen page, and lists the personal data in what it wrote."""

    def test_a_page_with_a_credential_is_not_exported_and_personal_data_is_listed(self):
        dates = dict(created="2026-01-01", updated="2026-01-01")
        self.write("cortex/concepts/clean.md", page("concept", "Nothing private. Ask ana@example.org.\n", title="Clean",
                                                    status="emerging", **dates))
        self.write("cortex/concepts/leaky.md", page("concept", "The key is AKIA" + "A" * 16 + ".\n", title="Leaky",
                                                    status="emerging", **dates))
        r = run_brain(self.root, "export", "clean", "leaky")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertEqual(r.stderr, "not exported: possible credential in cortex/concepts/leaky.md:8: AWS access key. Remove it at "
                                   "the source and rotate it; nothing was written.\n")
        self.assertFalse(os.path.exists(os.path.join(self.root, "motor", "export")))
        ok = run_brain(self.root, "export", "clean")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(ok.stdout.endswith("personal data in what was exported (the owner decides whether it may leave):\n"
                                           "  cortex/concepts/clean.md:8: email address\n"))
        self.assertTrue(os.path.exists(os.path.join(self.root, "motor", "export", "cortex", "concepts", "clean.md")))


class NewPage(TempBrain):
    def new(self, *args):
        return run_brain(self.root, "new", *args)

    def test_episode_is_scaffolded_from_its_input_and_passes_the_contracts(self):
        self.write("senses/2026-10-01-post.md", '---\nurl: "https://blog.example/a?b=1"\ntitle: "Spacing: why it works"\n'
                                                'author: "Dana Reyes"\npublished: "2026-09-30"\n---\n\n# Other heading\n')
        r = self.new("episode", "--from", "senses/2026-10-01-post.md", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        made = json.loads(r.stdout)
        self.assertEqual(made["page"], "cortex/episodes/spacing-why-it-works.md")
        with open(os.path.join(self.root, made["page"]), encoding="utf-8") as fh:
            text = fh.read()
        fields, body = vaultlib.parse_frontmatter(text)
        today = datetime.date.today().isoformat()
        self.assertEqual({k: fields[k] for k in ("title", "type", "input", "url", "author", "published", "created",
                                                 "updated", "consolidated")},
                         {"title": "Spacing: why it works", "type": "episode", "input": "senses/2026-10-01-post.md",
                          "url": "https://blog.example/a?b=1", "author": "Dana Reyes", "published": "2026-09-30",
                          "created": today, "updated": today, "consolidated": ""})
        self.assertIn("# Spacing: why it works\n\n## What it is", body)
        self.assertEqual(vaultlib.schema_problems(text, stem="spacing-why-it-works", rel=made["page"]), [])
        self.assertEqual(self.brain().unconsolidated()[0].stem, "spacing-why-it-works")
        again = self.new("episode", "--from", "senses/2026-10-01-post.md")
        self.assertEqual(again.returncode, 1)
        self.assertIn("already exists", again.stderr)

    def test_title_from_a_heading_other_types_and_refusals(self):
        self.write("senses/note.md", "---\ndate: 2026-10-05\n---\n# A plain note\n\ntext\n")
        r = self.new("episode", "--from", "senses/note.md", "--name", "plain")
        self.assertIn("created cortex/episodes/plain.md", r.stdout)
        self.assertEqual(self.brain().resolve("plain").fields["published"], "2026-10-05")
        self.assertIn("created cortex/entities/anki.md", self.new("entity", "--title", "Anki", "--kind", "tool").stdout)
        self.assertIn("'kind' must be one of", self.new("entity", "--title", "Nobody").stderr)
        for kind in ("insight", "decision"):
            self.assertEqual(self.new(kind, "--title", f"A {kind}").returncode, 0)
        check = run_brain(self.root, "check", "--json")
        self.assertEqual(json.loads(check.stdout)["schema"], [])
        self.assertIn("created cortex/concepts/spacing-effect.md", self.new("concept", "--title", "Spacing effect").stdout)
        for args, why in ((("episode", "--from", "cortex/episodes/plain.md"), "is not a file in senses/"),
                          (("concept", "--from", "senses/note.md"), "--from is for an episode"),
                          (("entity",), "no title")):
            r = self.new(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(why, r.stderr)


if __name__ == "__main__":
    unittest.main()
