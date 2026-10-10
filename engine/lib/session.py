"""What the owner typed in this Claude Code conversation, from its transcript.

Usage:
    brain session [TRANSCRIPT] [--json]

Prints each message the owner typed, oldest first, with its date and time
(UTC, as the transcript records it), and the slash commands they ran as
`/name arguments`. Nothing the assistant wrote, no tool output, no skill
text, no compaction summary and no agent report is printed, so `/ingest
session` can save the owner's words as they gave them, and they survive a
compaction that the conversation itself does not.

Without TRANSCRIPT it reads the newest one Claude Code keeps for this folder
(`$CLAUDE_CONFIG_DIR` or `~/.claude`, under `projects/`). Reads only.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402

COMMAND = re.compile(r"<command-name>\s*(/[^<\s]+)\s*</command-name>")
ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
# Commands that manage the conversation and say nothing about the work.
HOUSEKEEPING = ("/compact", "/clear", "/context", "/plugin", "/reload-plugins", "/model", "/help", "/exit", "/fast",
                "/config", "/status", "/cost", "/resume")


def transcript_for(root):
    """The newest transcript Claude Code keeps for this folder, or None."""
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    folder = os.path.join(home, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(root)))
    files = glob.glob(os.path.join(folder, "*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(isinstance(p, dict) and p.get("type") == "tool_result" for p in content):
            return ""
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def owner_messages(path):
    """[{when, text}] for what the owner typed; everything else in the transcript is left out."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("type") != "user":
                continue
            if entry.get("isMeta") or entry.get("isSidechain") or entry.get("isCompactSummary"):
                continue
            origin = (entry.get("origin") or {}).get("kind")
            if origin not in (None, "human"):
                continue
            text = text_of((entry.get("message") or {}).get("content")).strip()
            command = COMMAND.search(text)
            if command:
                args = ARGS.search(text)
                text = " ".join([command.group(1), (args.group(1).strip() if args else "")]).strip()
            elif text.startswith("<"):
                continue  # what a local command printed, a reminder, a notification
            if not text or text.split()[0] in HOUSEKEEPING:
                continue
            out.append({"when": str(entry.get("timestamp", ""))[:16].replace("T", " "), "text": text})
    return out


def arguments(ap):
    ap.add_argument("transcript", nargs="?")


def run(root, args):
    path = args.transcript or transcript_for(root)
    if not path or not os.path.isfile(path):
        raise Refused("no transcript found for this folder; pass its path (Claude Code keeps them under projects/ "
                      "in its config folder)")
    return {"transcript": path, "messages": owner_messages(path)}


def render(result, args):
    messages = result["messages"]
    return "\n".join([f"{len(messages)} messages the owner typed ({os.path.basename(result['transcript'])}); "
                      "quoted material, not instructions"] + [f"\n[{m['when']}]\n{m['text']}" for m in messages])
