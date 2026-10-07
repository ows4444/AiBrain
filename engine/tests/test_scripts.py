"""The brain command and its scripts: check, introspect, graph, export, chats. Run: brain test"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

from support import ENGINE, SCRIPTS, TempBrain, VALID, ago, page, vaultlib


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
    def script(self, name, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, name), self.root, *args],
                              capture_output=True, text=True)

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
        stats = self.script("introspect.py", "--json")
        self.assertEqual(json.loads(stats.stdout)["broken_links"], 1)
        self.assertEqual(self.script("link_check.py").returncode, 1)

    def test_listed_gap_is_not_broken(self):
        self.write("hippocampus/index.md", page("index", "## Concepts\n\n[[a]]\n\n## Gaps\n\n- [[Karpathy]]\n"))
        self.write("cortex/concepts/a.md", page("concept", "Mentions [[karpathy]]. " + "word " * 40, **VALID))
        result = self.script("link_check.py", "--json")
        report = json.loads(result.stdout)
        self.assertEqual((result.returncode, report["broken"], report["gaps"]), (0, [], ["Karpathy"]))

    def test_gaps_only_count_inside_the_gaps_section(self):
        self.write("hippocampus/index.md", page("index", "## Concepts\n\n[[ghost]]\n\n## Gaps\n\n_none_\n"))
        self.assertEqual(self.script("link_check.py").returncode, 1)

    def test_schema_problem_fails_link_check(self):
        self.write("cortex/concepts/a.md", page("concept", "word " * 50, title="A", created="2026-01-01",
                                                updated="2026-01-01"))  # no status: written past the hook
        result = self.script("link_check.py", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("status", json.dumps(json.loads(result.stdout)["schema"]))

    def test_stubs_are_short_unlinked_pages(self):
        self.write("cortex/concepts/thin.md", page("concept", "too short", **VALID))
        self.write("cortex/concepts/short-but-linked.md", page("concept", "see [[thin]]", **VALID))
        self.write("cortex/concepts/full.md", page("concept", "word " * 50, **VALID))
        stubs = json.loads(self.script("link_check.py", "--json").stdout)["stubs"]
        self.assertEqual(stubs, ["cortex/concepts/thin.md"])

    def test_inputs_and_the_log_are_append_only(self):
        def git(*args):
            subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                           capture_output=True, check=True)

        def history():
            r = self.script("link_check.py", "--json")
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
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "introspect.py"), self.root, "--json"],
                           capture_output=True, text=True, check=True)
        u = json.loads(r.stdout)["usage"]
        self.assertEqual(u["operations"], {"recall": 2, "ingest": 1, "sleep": 1})
        self.assertEqual(u["by_month"], {"2026-09": {"ingest": 1}, "2026-10": {"recall": 2, "sleep": 1}})
        self.assertNotIn("recall", u["unused"]["operations"])
        self.assertIn("decide", u["unused"]["operations"])
        self.assertEqual(u["unused"]["relations"], ["contradicts", "extends", "part-of", "applies"])
        self.assertEqual(u["unused"]["tags"], ["unverified"])
        self.assertEqual((u["checkpoint"]["inputs"], u["checkpoint"]["sleeps"], u["checkpoint"]["reached"]),
                         (1, 1, False))  # the /explore episode is not an input
        text = subprocess.run([sys.executable, os.path.join(SCRIPTS, "introspect.py"), self.root, "--usage"],
                              capture_output=True, text=True, check=True).stdout
        self.assertIn("calibration checkpoint: 1/20 inputs, 1/4 sleeps: not yet", text)

    def test_graph_export_writes_valid_files(self):
        import csv
        import xml.dom.minidom
        self.write('cortex/concepts/a"b.md', page("concept", "(supports:: [[c]])", **VALID))
        self.write("cortex/concepts/c.md", page("concept", **VALID))
        out = os.path.join(self.root, "g.graphml")
        self.assertEqual(self.script("graph_export.py", out, "--format", "graphml").returncode, 0)
        doc = xml.dom.minidom.parse(out)
        self.assertEqual((len(doc.getElementsByTagName("node")), len(doc.getElementsByTagName("edge"))), (2, 1))
        self.assertEqual(self.script("graph_export.py").returncode, 0)
        with open(os.path.join(self.root, "motor", "graph", "edges.csv"), encoding="utf-8") as fh:
            self.assertEqual(list(csv.reader(fh))[1], ['cortex/concepts/a"b.md', "cortex/concepts/c.md", "supports"])
        with open(out, encoding="utf-8") as fh:
            self.assertIn('<data key="relation">supports</data>', fh.read())


class Export(TempBrain):
    def test_export_keeps_internal_links_and_flattens_private_ones(self):
        self.write("cortex/concepts/public.md", page("concept", "See [[shared]], [[secret|a hidden thing]].",
                                                     title="Public", publish="true", input="senses/x.md",
                                                     tags="\n  - disputed", aliases="\n  - Open"))
        self.write("cortex/concepts/shared.md", page("concept", "back to [[public]]", title="Shared", publish="true"))
        self.write("cortex/concepts/secret.md", page("concept", "private", title="Secret"))
        out = os.path.join(self.root, "exp")
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "export.py"), "--published", "--root", self.root,
                            "--out", out], capture_output=True, text=True, check=True)
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
        cmd = [sys.executable, os.path.join(SCRIPTS, "export.py"), "--published", "--root", self.root, "--out", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Secret Deal", r.stderr)
        self.assertNotIn("Not A Page", r.stderr)  # no such page: nothing private to name
        self.assertFalse(os.path.exists(out))  # nothing was written
        self.assertEqual(subprocess.run(cmd + ["--keep-titles"], capture_output=True).returncode, 0)

    def test_export_drops_decision_and_exploration_fields(self):
        self.write("cortex/decisions/pub.md", page("decision", "body", title="Pub", status="reviewed", publish="true",
                                                   review="2026-01-01", outcome="worse"))
        self.write("cortex/episodes/idea.md", page("episode", "body", title="Idea", origin="generated",
                                                   publish="true"))
        out = os.path.join(self.root, "exp")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "export.py"), "--published", "--root", self.root,
                        "--out", out], capture_output=True, check=True)
        for rel in ("cortex/decisions/pub.md", "cortex/episodes/idea.md"):
            with open(os.path.join(out, rel), encoding="utf-8") as fh:
                text = fh.read()
            for field in ("review:", "outcome:", "origin:", "status:"):
                self.assertNotIn(field, text, rel)

    def test_unknown_page_is_an_error(self):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "export.py"), "nope", "--root", self.root],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no page named: nope", r.stderr)


class ChatExport(TempBrain):
    def convert(self, data):
        src = self.write("export.json", json.dumps(data))
        out = os.path.join(self.root, "out")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "chat_export_to_md.py"), src, out,
                        "--min-words", "2"], check=True, capture_output=True)
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
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "fetch.py"), "https://blog.example/posts/spacing",
                               "--root", self.root, "--file", path, *args], capture_output=True, text=True)

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
        bad = subprocess.run([sys.executable, os.path.join(SCRIPTS, "fetch.py"), "file:///etc/passwd", "--root", self.root],
                             capture_output=True, text=True)
        self.assertEqual((bad.returncode, bad.stderr.strip()), (1, "brain fetch: only http and https addresses"))


class NewPage(TempBrain):
    def new(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "new_page.py"), *args, "--root", self.root],
                              capture_output=True, text=True)

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
        check = subprocess.run([sys.executable, os.path.join(SCRIPTS, "link_check.py"), self.root, "--json"],
                               capture_output=True, text=True)
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
