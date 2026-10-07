#!/usr/bin/env python3
"""A new page from its template, frontmatter filled in, sections left for the writer.

Usage:
    brain new TYPE --title TITLE [--name SLUG] [--kind KIND] [--json]
    brain new episode --from senses/FILE [--title TITLE] [--name SLUG] [--json]

TYPE is episode, concept, entity, insight or decision. The page lands in its
folder under cortex/ with `title`, `created` and `updated` set, and the
template's sections empty. With --from, an episode also gets `input` (the
file's path) and `url`, `author` and `published` copied from that file's
frontmatter (`brain fetch` writes them; a `date` there is taken as
`published`); its title is the input's `title`, else its first heading,
unless --title is given. An entity needs --kind (person, org, product, tool).

So no frontmatter is typed by hand: the writer fills the sections with Edit.
A page that already exists is never overwritten. Prints the path; exit 1 with
the reason when the result would break the page contracts.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import parse_frontmatter, schema_problems, tag_vocabulary  # noqa: E402

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
FOLDERS = {"episode": "episodes", "concept": "concepts", "entity": "entities", "insight": "insights",
           "decision": "decisions"}
COPIED = ("url", "author", "published")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70].strip("-")


def set_field(head, key, value):
    """The frontmatter with `key:` set; values that YAML would misread are quoted."""
    if re.search(r"[:#\[\]{}\"']|^[\s>|*&!%@`-]|\s$", value):
        value = '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    line = f"{key}: {value}"
    if re.search(rf"^{key}:.*$", head, re.M):
        return re.sub(rf"^{key}:.*$", lambda _: line, head, count=1, flags=re.M)
    return head.rstrip("\n") + "\n" + line + "\n"


def main():
    ap = argparse.ArgumentParser(prog="brain new")
    ap.add_argument("type", choices=sorted(FOLDERS))
    ap.add_argument("--root", default=".")
    ap.add_argument("--from", dest="source")
    ap.add_argument("--title")
    ap.add_argument("--name")
    ap.add_argument("--kind")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    values = {}
    if args.source:
        if args.type != "episode":
            sys.exit("brain new: --from is for an episode")
        source = os.path.relpath(os.path.join(args.root, args.source), args.root)
        if not source.startswith("senses" + os.sep) or not os.path.isfile(os.path.join(args.root, source)):
            sys.exit(f"brain new: {args.source} is not a file in senses/")
        with open(os.path.join(args.root, source), encoding="utf-8", errors="replace") as fh:
            fields, body = parse_frontmatter(fh.read())
        fields = {k: v for k, v in (fields or {}).items() if isinstance(v, str) and v}
        heading = re.search(r"^# (.+)$", body, re.M)
        values = {"input": source.replace(os.sep, "/"), **{k: fields[k] for k in COPIED if k in fields}}
        values["title"] = fields.get("title") or (heading.group(1).strip() if heading else "")
        if "published" not in values and re.match(r"\d{4}-\d{2}-\d{2}", fields.get("date", "")):
            values["published"] = fields["date"][:10]
    title = (args.title or values.get("title") or "").strip()
    if not title:
        sys.exit("brain new: no title (give --title, or an input with a `title:` or a first heading)")
    name = slug(args.name or title)
    if not name:
        sys.exit("brain new: the title gives no file name; give --name")
    today = datetime.date.today().isoformat()
    values.update(title=title, created=today, updated=today, **({"kind": args.kind} if args.kind else {}))
    with open(os.path.join(TEMPLATES, f"{args.type}.md"), encoding="utf-8") as fh:
        template = fh.read()
    _, head, body = template.split("---\n", 2)
    for key, value in values.items():
        head = set_field(head, key, value)
    text = "---\n" + head + "---\n" + body.replace("{{title}}", title)
    rel = os.path.join("cortex", FOLDERS[args.type], f"{name}.md")
    path = os.path.join(args.root, rel)
    if os.path.exists(path):
        sys.exit(f"brain new: {rel} already exists; open it, or give another --name")
    problems = schema_problems(text, tag_vocabulary(args.root), stem=name, rel=rel)
    if problems:
        sys.exit(f"brain new: {rel} would break the page contracts: " + "; ".join(problems))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(text)
    filled = sorted(values)
    if args.json:
        print(json.dumps({"page": rel.replace(os.sep, "/"), "filled": filled}, indent=2))
        return
    print(f"created {rel}")
    print(f"  filled: {', '.join(filled)}")
    print("  write the sections with Edit; leave the frontmatter as it is, apart from fields the skill names")


if __name__ == "__main__":
    main()
