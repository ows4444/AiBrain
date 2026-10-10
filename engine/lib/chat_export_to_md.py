"""Convert an exported chat history JSON into one markdown file per conversation.

Usage:
    brain chats conversations.json senses/chats [--min-words 150] [--json]

Understands both common export shapes:
  Claude   a list of conversations with `name`, `created_at` and `chat_messages`
           (each with `sender` and `text` or `content`).
  ChatGPT  a list of conversations with `title`, `create_time` (unix seconds)
           and a `mapping` of message nodes (`author.role`, `content.parts`).
Conversations in any other shape are skipped and counted, never guessed at.
Existing files are never overwritten; a numeric suffix is added instead.

Run the privacy pass (/guard) before this on a real export. Chat history
is the single most sensitive thing most people keep.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402


def slug(text, limit=60):
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[\s_]+", "-", s)
    return s[:limit].strip("-") or "untitled"


def iso_date(value):
    """Accept ISO strings or unix seconds; return YYYY-MM-DD or ''."""
    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).date().isoformat()
    text = str(value or "")
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else ""


def yaml_str(text):
    return json.dumps(str(text), ensure_ascii=False)


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(t for t in (text_of(c) for c in content) if t)
    if isinstance(content, dict):
        if "parts" in content:
            return text_of(content["parts"])
        return content.get("text", "") if isinstance(content.get("text"), str) else ""
    return ""


def claude_messages(conv):
    for m in conv.get("chat_messages") or []:
        if isinstance(m, dict):
            yield m.get("sender") or "unknown", text_of(m.get("text") or m.get("content"))


def chatgpt_messages(conv):
    nodes = [n.get("message") for n in conv["mapping"].values() if isinstance(n, dict)]
    nodes = [m for m in nodes if isinstance(m, dict)]
    nodes.sort(key=lambda m: m.get("create_time") or 0)
    for m in nodes:
        role = (m.get("author") or {}).get("role") or "unknown"
        if role != "system":
            yield role, text_of(m.get("content"))


def generic_messages(conv):
    for m in conv.get("messages") or []:
        if isinstance(m, dict):
            yield m.get("role") or m.get("sender") or "unknown", text_of(m.get("content") or m.get("text"))


def messages_of(conv):
    if isinstance(conv.get("mapping"), dict):
        return chatgpt_messages(conv)
    if "chat_messages" in conv:
        return claude_messages(conv)
    if "messages" in conv:
        return generic_messages(conv)
    return None


def unique_path(outdir, stem):
    path = os.path.join(outdir, f"{stem}.md")
    n = 2
    while os.path.exists(path):
        path = os.path.join(outdir, f"{stem}-{n}.md")
        n += 1
    return path


def arguments(ap):
    ap.add_argument("export")
    ap.add_argument("outdir")
    ap.add_argument("--min-words", type=int, default=150, help="skip conversations shorter than this")


def run(root, args):
    with open(args.export, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("conversations", [])
    if not isinstance(data, list):
        raise Refused("unrecognised export shape: expected a list of conversations")

    os.makedirs(args.outdir, exist_ok=True)
    files, short, unknown = [], 0, 0

    for conv in data:
        messages = messages_of(conv) if isinstance(conv, dict) else None
        if messages is None:
            unknown += 1
            continue
        body = [f"**{role}**\n\n{text.strip()}\n" for role, text in messages if text.strip()]
        joined = "\n".join(body)
        if len(joined.split()) < args.min_words:
            short += 1
            continue

        title = str(conv.get("name") or conv.get("title") or "untitled")
        created = iso_date(conv.get("created_at") or conv.get("create_time"))
        front = (f"---\ntitle: {yaml_str(title)}\nsource: chat export\n"
                 f"created: {created}\n---\n\n# {title}\n\n")
        stem = f"{created}-{slug(title)}" if created else slug(title)
        path = unique_path(args.outdir, stem)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(front + joined)
        files.append(path)

    return {"out": args.outdir, "written": files, "short": short, "unknown": unknown}


def render(result, args):
    return (f"wrote {len(result['written'])} files to {result['out']}; skipped {result['short']} short"
            + (f", {result['unknown']} in an unrecognised shape" if result["unknown"] else ""))
