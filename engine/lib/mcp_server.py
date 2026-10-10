"""A read-only MCP server over the brain's instruments, for programs other than Claude Code.

Usage:
    brain mcp                 serve on stdin and stdout until stdin closes

Another host (a desktop client, an editor, a script) starts this as a
subprocess and gets six tools, each one a `brain` command called in this
process (lib/commands.py), its text returned as it would print:

    search   pages by their words
    recall   words, then association along links; confidence, flags, the section to read first
    since    what was made, changed, asked and rehearsed in a period
    gaps     what was asked and not answered
    waiting  what needs the owner: reminders and rehearsals due, queues, decisions, goals
    character  who the brain is to its owner: what it holds to and how it speaks, to answer in that voice

No tool writes: no page, no index, and no line in the log, so a page read this
way does not count as used. The brain is $BRAIN_ROOT, else the nearest one at
or above $CLAUDE_PROJECT_DIR or the folder it is started in. Started where
there is no brain (the plugin may be enabled in any project), it lists no
tools and says so when one is called.

The protocol is the Model Context Protocol on stdio: one JSON-RPC message a
line, nothing else on stdout. Both eras are served. A request that carries
its protocol version in `_meta` (revision 2026-07-28 and later) is answered
on its own, with no handshake: `server/discover`, `tools/list`, `tools/call`.
A client that opens with `initialize` (2025-11-25 and earlier) is served that
way for the life of the process. Standard library only.

For a client's configuration:

    {"mcpServers": {"brain": {"command": "python3",
                              "args": ["/path/to/engine/bin/brain", "mcp"],
                              "env": {"BRAIN_ROOT": "/path/to/the/brain"}}}}
"""
import contextlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import commands  # noqa: E402
from errlog import note  # noqa: E402
from vault_model import PAGE_TYPES, find_brain  # noqa: E402

NAME, VERSION = "aibrain", "1"
MODERN = ("2026-07-28",)                                            # served a request at a time
LEGACY = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")   # served after an `initialize`
META = "io.modelcontextprotocol/"
INSTRUCTIONS = ("Read-only access to one person's knowledge base (an AiBrain). `recall` finds the pages that bear on "
                "a question and is the place to start; `search` finds pages by exact words; `since` lists what "
                "changed in a period; `gaps` lists what was asked and never answered; `waiting` lists what the brain is "
                "waiting on its owner for; `character` says how this brain speaks and what it holds to: read it "
                "before answering for it. Answer from the pages and name them. Nothing here writes: a page read this "
                "way leaves no trace in the brain's log.")
TTL_MS = 3600000  # the tool list and the server's description do not change while it runs
PARSE_ERROR, INVALID_REQUEST, NO_METHOD, INVALID_PARAMS, INTERNAL, UNSUPPORTED = -32700, -32600, -32601, -32602, -32603, -32022
READ_ONLY = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}


def schema(required=(), **properties):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


QUERY = {"type": "string", "description": "The question or the words, as a person would type them"}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 50, "description": "Pages returned at most (10 unless given)"}
DORMANT = {"type": "boolean", "description": "Also look in dormant/, the pages that faded out of the index"}
# name -> (what it is for, its arguments, how they become the words of a `brain` command)
TOOLS = {
    "search": ("Find pages by their words (BM25 over title, aliases, body and summary). Each result is a page with "
               "its one-sentence summary. Use it for an exact term; use recall for a question.",
               schema(("query",), query=QUERY, limit=LIMIT, dormant=DORMANT,
                      types={"type": "array", "items": {"type": "string", "enum": list(PAGE_TYPES)},
                             "description": "Only pages of these types"}),
               lambda a: ["search", *flag("--limit", a.get("limit")), *switch("--dormant", a.get("dormant")),
                          *(word for kind in a.get("types") or [] for word in ("--type", kind)), "--", a["query"]]),
    "recall": ("Find the pages that bear on a question: by its words, then along the links between pages. Each "
               "result says how it was reached, how well supported it is, and the section to read first. It lists "
               "nothing when no page holds enough of the question: that means the brain does not cover it.",
               schema(("query",), query=QUERY, limit=LIMIT, dormant=DORMANT,
                      project={"type": "string", "description": "A project in prefrontal/ to lean toward"},
                      also={"type": "array", "items": {"type": "string"},
                            "description": "Other wordings of the same question (the field's own terms for it, "
                                           "plainer words): each is searched and a page's scores are added up. Two "
                                           "is enough"},
                      everything={"type": "boolean", "description": "Every match, however weak; use before "
                                                                    "concluding that nothing answers"}),
               lambda a: ["recall", *flag("--limit", a.get("limit")), *switch("--dormant", a.get("dormant")),
                          *flag("--project", a.get("project")), *switch("--all", a.get("everything")),
                          *(word for wording in a.get("also") or [] for word in ("--also", wording)), "--", a["query"]]),
    "since": ("What happened in a period: pages made and changed, operations, questions asked, rehearsals.",
              schema(("start",), start={"type": "string", "description": "YYYY-MM-DD, or YYYY-MM for a whole month"},
                     until={"type": "string", "description": "YYYY-MM-DD or YYYY-MM; today when not given"}),
              lambda a: ["since", *flag("--until", a.get("until")), "--", a["start"]]),
    "gaps": ("What was asked of the brain and not answered, most asked first, with the held idea or the index gap "
             "each names: what to read next.", schema(), lambda a: ["introspect", "--gaps"]),
    "waiting": ("What the brain is waiting on its owner for: reminders whose time has come, pages due for rehearsal, "
                "input not yet encoded, decisions to review, goals slipping, questions not answered. One line for "
                "each kind that holds something, and one saying so when nothing does. A program that acts on a "
                "schedule asks this to learn what is due; doing it stays with the owner.",
                schema(), lambda a: ["tend", "--check"]),
    "character": ("Who this brain is to its owner: what it holds to and how it speaks, as its owner wrote it. Read it "
                  "before answering for this brain, and answer in that voice. It yields to the brain's rules: "
                  "answer from the pages, name them, and say when nothing covers the question.",
                  schema(), lambda a: ["character"]),
}


def flag(name, value):
    return [name, str(value)] if value is not None else []


def switch(name, on):
    return [name] if on else []


def brain():
    """The brain this server reads, or None: $BRAIN_ROOT, else the nearest one above where it was started."""
    if os.environ.get("BRAIN_ROOT"):
        return os.path.abspath(os.environ["BRAIN_ROOT"])
    return find_brain(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def listed(root):
    """The tools, in a fixed order; none where there is no brain to read."""
    return [{"name": name, "description": what, "inputSchema": takes, "annotations": READ_ONLY}
            for name, (what, takes, _) in TOOLS.items()] if root else []


def unfit(takes, arguments):
    """What is wrong with a tool's arguments, by its own schema; "" when nothing is."""
    kinds = {"string": str, "integer": int, "boolean": bool, "array": list}
    for name in takes["required"]:
        if name not in arguments:
            return f"`{name}` is required"
    for name, value in arguments.items():
        if name not in takes["properties"]:
            return f"`{name}` is not one of its arguments ({', '.join(takes['properties']) or 'it takes none'})"
        kind = takes["properties"][name]["type"]
        fits = isinstance(value, kinds[kind]) and not (kind == "integer" and isinstance(value, bool))
        if not fits or (kind == "array" and not all(isinstance(item, str) for item in value)):
            return f"`{name}` must be of type {kind}" + (" of strings" if kind == "array" else "")
    return ""


def call(root, name, arguments):
    """(one tool's text, whether it failed): the `brain` command behind it, run in this process."""
    if root is None:
        return "No brain here: start this server in a brain's folder, or set BRAIN_ROOT to one.", True
    wrong = unfit(TOOLS[name][1], arguments)
    if wrong:
        return f"{name}: {wrong}", True
    command, *argv = TOOLS[name][2](arguments)
    try:
        with contextlib.redirect_stdout(sys.stderr):  # stdout carries the protocol and nothing else
            module, args = commands.prepare(command, argv, root)
            result = module.run(root, args)
            if name == "gaps":
                return "\n".join(map(module.gap_line, result["gaps"])) or "Nothing was asked and left unanswered.", False
            return module.render(result, args), False
    except commands.Refused as why:  # what was asked cannot be done as asked: the reason is the answer
        return f"{name}: {why}", True


class Wrong(Exception):
    """A request this server will not answer with a result: the JSON-RPC error to send back."""

    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.error = dict({"code": code, "message": message}, **({"data": data} if data is not None else {}))


class Server:
    def __init__(self, root):
        self.root = root
        self.handshake = False  # True once a client has opened with `initialize`: the earlier way, for this process

    def result(self, method, params, modern):
        """What to answer `method` with; Wrong when it cannot be answered."""
        if method == "tools/list":
            return dict({"tools": listed(self.root)}, **({"ttlMs": TTL_MS, "cacheScope": "public"} if modern else {}))
        if method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments") or {}
            if name not in TOOLS or not isinstance(arguments, dict):
                raise Wrong(INVALID_PARAMS, f"Unknown tool: {name}" if name not in TOOLS else "arguments is not an object")
            text, failed = call(self.root, name, arguments)
            return {"content": [{"type": "text", "text": text}], "isError": failed}
        if method == "server/discover" and modern:
            return {"supportedVersions": list(MODERN + LEGACY), "capabilities": {"tools": {}}, "instructions": INSTRUCTIONS,
                    "ttlMs": TTL_MS, "cacheScope": "public"}
        if method == "ping" and not modern:
            return {}
        raise Wrong(NO_METHOD, f"Method not found: {method}")

    def answer(self, message):
        """The result for one request, in the era it was sent in; Wrong when there is none."""
        method, params = message.get("method"), message.get("params", {})
        if not isinstance(method, str) or not isinstance(params, dict):
            raise Wrong(INVALID_REQUEST, "a request is an object with a method, and params that are an object")
        meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
        if method == "initialize":
            self.handshake = True
            asked = params.get("protocolVersion")
            return {"protocolVersion": asked if asked in LEGACY else LEGACY[0], "capabilities": {"tools": {}},
                    "serverInfo": {"name": NAME, "version": VERSION}, "instructions": INSTRUCTIONS}
        if META + "protocolVersion" in meta:  # it says what it speaks: answered on its own
            asked = meta[META + "protocolVersion"]
            if asked not in MODERN:
                raise Wrong(UNSUPPORTED, "Unsupported protocol version",
                            {"supported": list(MODERN + LEGACY), "requested": asked})
            return dict(self.result(method, params, True), resultType="complete",
                        _meta={META + "serverInfo": {"name": NAME, "version": VERSION}})
        if not self.handshake:
            raise Wrong(INVALID_PARAMS, f"the request names no protocol version: send `_meta` with `{META}protocolVersion` "
                                        f"(one of {', '.join(MODERN)}), or open with `initialize` "
                                        f"({', '.join(LEGACY)})")
        return self.result(method, params, False)

    def reply(self, line):
        """The line to write back for one line read, or None: a notification, or a blank line."""
        try:
            message = json.loads(line)
        except ValueError:
            return {"jsonrpc": "2.0", "error": {"code": PARSE_ERROR, "message": "Parse error: not JSON"}}
        if not isinstance(message, dict):
            return {"jsonrpc": "2.0", "error": {"code": INVALID_REQUEST, "message": "one request a line; no batches"}}
        if "id" not in message:
            return None  # a notification (initialized, cancelled): nothing is sent back
        try:
            return {"jsonrpc": "2.0", "id": message["id"], "result": self.answer(message)}
        except Wrong as wrong:
            return {"jsonrpc": "2.0", "id": message["id"], "error": wrong.error}
        except Exception as crash:  # noqa: BLE001  one request that breaks must not end the others
            note("mcp", "error", root=self.root)
            return {"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": INTERNAL, "message": f"Internal error: {type(crash).__name__}"}}


def serve(lines, out, root):
    """Answer every line of `lines` on `out` until it ends; how many requests were answered."""
    server, answered = Server(root), 0
    for line in lines:
        reply = server.reply(line) if line.strip() else None
        if reply is not None:
            out.write(json.dumps(reply) + "\n")
            out.flush()
            answered += 1
    return answered


def arguments(ap):
    pass


def run(root, args):
    """`root` is not used: the brain is found here, since the server must also start where there is none."""
    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8")  # the protocol's encoding, whatever the locale says
    return {"answered": serve(sys.stdin, sys.stdout, brain())}


def render(result, args):
    return ""  # stdout carried the protocol; there is nothing to add to it
