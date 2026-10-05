"""The brain command and its scripts: check, introspect, graph, export, chats. Run: brain test"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from support import ENGINE, SCRIPTS, TempBrain, VALID, ago, page


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


class Scripts(TempBrain):
    def script(self, name, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, name), self.root, *args],
                              capture_output=True, text=True)

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
        self.assertIn('<data key="relation">supports</data>', open(out, encoding="utf-8").read())


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


if __name__ == "__main__":
    unittest.main()
