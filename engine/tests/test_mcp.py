"""The read-only MCP server: another program lists the brain's five tools and calls them. Run: brain test"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

from support import BRAIN, ENGINE, TempBrain, ago, page, run_brain

import index  # noqa: E402  (support puts engine/lib on the path)
import mcp_server  # noqa: E402

VERSION = "io.modelcontextprotocol/protocolVersion"
MODERN = {VERSION: "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {},
          "io.modelcontextprotocol/clientInfo": {"name": "a test", "version": "0"}}
DATES = dict(created="2026-01-01", updated="2026-01-01")


class AnotherClient(TempBrain):
    """A client that is not Claude Code: it starts `brain mcp`, writes requests a line each, and reads the answers."""

    def setUp(self):
        super().setUp()
        shutil.copy(index.TEMPLATE, os.path.join(self.root, index.INDEX))
        self.write("cortex/concepts/spacing-effect.md", page(
            "concept", "\n# Spacing effect\n\n## In one paragraph\n\nStudy spread over days lasts longer; the best gap "
            "depends on the test.\n", title="Spacing effect", status="established",
            summary="Study spread over days is kept longer.", **DATES))
        self.write("dormant/old-idea.md", page("concept", "Cramming, long ago.\n", title="Old idea", status="emerging",
                                               summary="A faded page on cramming.", **DATES))
        self.log(f"{ago(40)} recall how long between sessions -> [[spacing-effect]]",
                 f"{ago(9)} recall which painters did picasso learn from -> none")

    def talk(self, *messages, root="the brain", raw=None, cwd=None):
        """What the server writes back, a parsed line each, for the requests sent (params given without `jsonrpc`)."""
        env = {k: v for k, v in os.environ.items() if k not in ("BRAIN_ROOT", "CLAUDE_PROJECT_DIR")}
        if root:
            env["BRAIN_ROOT"] = self.root if root == "the brain" else root
        sent = raw if raw is not None else "".join(json.dumps(dict(m, jsonrpc="2.0")) + "\n" for m in messages)
        r = subprocess.run([sys.executable, BRAIN, "mcp"], input=sent, capture_output=True, text=True, env=env, cwd=cwd)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(line) for line in r.stdout.splitlines()]

    @staticmethod
    def modern(request_id, method, **params):
        return {"id": request_id, "method": method, "params": dict(params, _meta=MODERN)}

    def test_it_lists_the_six_tools_and_calls_each(self):
        discover, listing, *called = self.talk(
            self.modern("d", "server/discover"), self.modern(1, "tools/list"),
            self.modern(2, "tools/call", name="search", arguments={"query": "spacing", "limit": 3}),
            self.modern(3, "tools/call", name="recall", arguments={"query": "what does the best gap depend on",
                                                                    "also": ["what sets the optimal interval"]}),
            self.modern(4, "tools/call", name="since", arguments={"start": "2026-01"}),
            self.modern(5, "tools/call", name="gaps", arguments={}),
            self.modern(6, "tools/call", name="waiting", arguments={}),
            self.modern(7, "tools/call", name="character", arguments={}))
        info = {"io.modelcontextprotocol/serverInfo": {"name": "aibrain", "version": "1"}}
        self.assertEqual((discover["id"], discover["result"]["resultType"], discover["result"]["_meta"]), ("d", "complete", info))
        self.assertEqual((discover["result"]["supportedVersions"][0], discover["result"]["capabilities"]),
                         ("2026-07-28", {"tools": {}}))
        self.assertIn("Read-only", discover["result"]["instructions"])
        tools = listing["result"]["tools"]
        self.assertEqual([t["name"] for t in tools],
                         ["search", "recall", "since", "gaps", "waiting", "character"])  # the same order every time
        self.assertIn("`character` says how this brain speaks", discover["result"]["instructions"])
        self.assertEqual((listing["result"]["resultType"], listing["result"]["ttlMs"], listing["result"]["cacheScope"]),
                         ("complete", 3600000, "public"))
        for tool in tools:
            self.assertEqual((tool["inputSchema"]["type"], tool["annotations"]["readOnlyHint"]), ("object", True), tool["name"])
            self.assertTrue(tool["description"])
        self.assertEqual(tools[0]["inputSchema"]["required"], ["query"])
        texts = [c["result"]["content"][0]["text"] for c in called]
        self.assertEqual([(c["id"], c["result"]["isError"], c["result"]["resultType"]) for c in called],
                         [(2, False, "complete"), (3, False, "complete"), (4, False, "complete"), (5, False, "complete"),
                          (6, False, "complete"), (7, False, "complete")])
        self.assertTrue(texts[0].startswith('search: "spacing"\n'))
        self.assertIn("cortex/concepts/spacing-effect.md\n           Study spread over days is kept longer.", texts[0])
        self.assertIn("read first: ## In one paragraph (lines ", texts[1])  # what `brain recall` prints, as it prints it
        self.assertIn("+ cortex/concepts/spacing-effect.md", texts[2])
        self.assertEqual(texts[3], "  1x  learn, painter, picasso  (last %s)\n        which painters did picasso learn from" % ago(9))
        # What `brain tend --check` prints, as it prints it: here the one question nobody has answered.
        self.assertEqual(texts[4], run_brain(self.root, "tend", "--check").stdout.rstrip("\n"))
        self.assertTrue(texts[4].startswith("tend check, "))
        self.assertIn("picasso", texts[4])
        # Who the brain is to its owner, for a host that answers for it. Without the page it says there is none.
        self.assertTrue(texts[5].startswith("character: this brain has no CHARACTER.md"))
        self.write("CHARACTER.md", "# Character\n\n## Voice\n\n- Plain and short.\n")
        said, = self.talk(self.modern(8, "tools/call", name="character", arguments={}))
        self.assertEqual(said["result"]["content"][0]["text"],
                         "Character (CHARACTER.md; the rules of CLAUDE.md come first):\n  Voice:\n  - Plain and short.")

    def test_a_client_of_the_earlier_protocol_is_served_after_its_handshake(self):
        opened, pinged, listing, called = self.talk(
            {"id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                         "clientInfo": {"name": "older", "version": "1"}}},
            {"method": "notifications/initialized"},  # no id: nothing comes back for it
            {"id": 1, "method": "ping"}, {"id": 2, "method": "tools/list"},
            {"id": 3, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "spacing"}}})
        self.assertEqual(opened["result"], {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                                            "serverInfo": {"name": "aibrain", "version": "1"},
                                            "instructions": mcp_server.INSTRUCTIONS})
        self.assertEqual((pinged, sorted(listing["result"])), ({"jsonrpc": "2.0", "id": 1, "result": {}}, ["tools"]))
        self.assertEqual(sorted(called["result"]), ["content", "isError"])  # as that protocol has it: no resultType
        unknown, = self.talk({"id": 0, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
        self.assertEqual(unknown["result"]["protocolVersion"], "2025-11-25")  # the latest it speaks that way

    def test_what_it_cannot_answer_is_an_error_and_what_a_tool_cannot_do_is_said_by_the_tool(self):
        old = {"id": 1, "method": "tools/list", "params": {"_meta": {VERSION: "2030-01-01"}}}
        replies = self.talk(
            old, {"id": 2, "method": "tools/list"},  # no version named, and no handshake before it
            self.modern(3, "tools/call", name="write", arguments={}), self.modern(4, "resources/list"),
            self.modern(5, "ping"), self.modern(6, "tools/call", name="search", arguments="spacing"),
            {"id": 7, "method": 5}, {"id": 8, "method": "tools/list", "params": []})
        errors = [(r["id"], r["error"]["code"]) for r in replies]
        self.assertEqual(errors, [(1, -32022), (2, -32602), (3, -32602), (4, -32601), (5, -32601), (6, -32602),
                                  (7, -32600), (8, -32600)])
        self.assertEqual(replies[0]["error"]["data"], {"supported": ["2026-07-28", "2025-11-25", "2025-06-18",
                                                                     "2025-03-26", "2024-11-05"], "requested": "2030-01-01"})
        self.assertIn("names no protocol version", replies[1]["error"]["message"])
        self.assertEqual(replies[2]["error"]["message"], "Unknown tool: write")  # there is no tool that writes
        said = [(r["result"]["isError"], r["result"]["content"][0]["text"]) for r in self.talk(
            self.modern(1, "tools/call", name="search", arguments={}),
            self.modern(2, "tools/call", name="search", arguments={"query": "spacing", "limit": "3"}),
            self.modern(3, "tools/call", name="search", arguments={"query": "spacing", "types": [1]}),
            self.modern(4, "tools/call", name="gaps", arguments={"query": "x"}),
            self.modern(5, "tools/call", name="recall", arguments={"query": "spacing", "project": "nope"}),
            self.modern(6, "tools/call", name="recall", arguments={"query": "-5 degrees", "limit": True}),
            self.modern(7, "tools/call", name="search", arguments={"query": "--dormant cramming"}))]
        self.assertEqual(said[:5], [
            (True, "search: `query` is required"), (True, "search: `limit` must be of type integer"),
            (True, "search: `types` must be of type array of strings"),
            (True, "gaps: `query` is not one of its arguments (it takes none)"),
            (True, "recall: no project named nope in prefrontal/")])
        self.assertEqual(said[5], (True, "recall: `limit` must be of type integer"))
        self.assertEqual(said[6], (False, 'search: nothing matches "--dormant cramming" (try --dormant)'))  # words, not a flag
        bad = self.talk(raw='not json\n\n[1, 2]\n{"jsonrpc": "2.0", "method": "notifications/cancelled"}\n')
        self.assertEqual([(r.get("id", "none"), r["error"]["code"]) for r in bad], [("none", -32700), ("none", -32600)])

    def test_options_reach_the_command(self):
        listed = lambda **arguments: self.talk(self.modern(1, "tools/call", name="search", arguments=arguments))[0][  # noqa: E731
            "result"]["content"][0]["text"]
        self.assertIn("nothing matches", listed(query="cramming"))
        self.assertIn("dormant/old-idea.md", listed(query="cramming", dormant=True))
        self.assertIn("nothing matches", listed(query="spacing", types=["episode"]))
        recalled = self.talk(self.modern(1, "tools/call", name="recall", arguments={"query": "spacing zebra quartz violin",
                                                                                  "everything": True, "limit": 1}),
                             self.modern(2, "tools/call", name="since", arguments={"start": "2026-01", "until": "2026-01-31"}))
        self.assertIn("cortex/concepts/spacing-effect.md", recalled[0]["result"]["content"][0]["text"])
        self.assertTrue(recalled[1]["result"]["content"][0]["text"].startswith("2026-01-01 .. 2026-01-31"))

    def test_nothing_it_does_writes_to_the_brain(self):
        def on_disk():
            return {os.path.join(folder, name): os.path.getmtime(os.path.join(folder, name))
                    for folder, _, names in os.walk(self.root) for name in names if ".cache" not in folder}

        before = on_disk()
        answers = self.talk(*(self.modern(n, "tools/call", name=name, arguments=arguments) for n, (name, arguments) in
                              enumerate((("search", {"query": "spacing"}), ("recall", {"query": "spacing"}),
                                         ("since", {"start": "2026-01"}), ("gaps", {}), ("waiting", {}),
                                         ("character", {})))))
        self.assertEqual([a["result"]["isError"] for a in answers], [False] * 6)
        self.assertEqual(on_disk(), before)  # no page, no index, and no recall line in the log

    def test_where_there_is_no_brain_it_starts_and_offers_nothing(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            listing, called = self.talk(self.modern(1, "tools/list"),
                                        self.modern(2, "tools/call", name="search", arguments={"query": "x"}),
                                        root=None, cwd=elsewhere)
        self.assertEqual(listing["result"]["tools"], [])
        self.assertEqual((called["result"]["isError"], called["result"]["content"][0]["text"][:14]), (True, "No brain here:"))
        inside = os.path.join(self.root, "cortex")  # started in a folder of the brain: it is found from there
        self.assertEqual(len(self.talk(self.modern(1, "tools/list"), root=None, cwd=inside)[0]["result"]["tools"]), 6)

    def test_a_request_that_breaks_the_server_does_not_end_it(self):
        out = io.StringIO()
        requests = [json.dumps(dict(self.modern(n, "tools/call", name="gaps", arguments={}), jsonrpc="2.0")) + "\n" for n in (1, 2)]
        with mock.patch.object(mcp_server, "call", side_effect=[RuntimeError("boom"), ("fine", False)]), \
                mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.root}):
            self.assertEqual(mcp_server.serve(requests, out, self.root), 2)
        first, second = map(json.loads, out.getvalue().splitlines())
        self.assertEqual(first["error"], {"code": -32603, "message": "Internal error: RuntimeError"})
        self.assertEqual(second["result"]["content"], [{"type": "text", "text": "fine"}])
        with open(os.path.join(self.root, ".cache", "errors.log"), encoding="utf-8") as fh:
            self.assertIn(" mcp error | RuntimeError: boom", fh.read())

    def test_the_plugin_declares_it_so_it_starts_with_the_plugin(self):
        with open(os.path.join(ENGINE, ".mcp.json"), encoding="utf-8") as fh:
            declared = json.load(fh)
        self.assertEqual(declared, {"mcpServers": {"brain": {"command": "python3",
                                                             "args": ["${CLAUDE_PLUGIN_ROOT}/bin/brain", "mcp"]}}})
        self.assertTrue(os.path.isfile(os.path.join(ENGINE, "bin", "brain")))
