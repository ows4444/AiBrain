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
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from vaultlib import parse_frontmatter, schema_problems, tag_vocabulary  # noqa: E402

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
FOLDERS = {"episode": "episodes", "concept": "concepts", "entity": "entities", "insight": "insights",
           "decision": "decisions"}
COPIED = ("url", "author", "published", "handed")  # `handed`: the name of what a runtime reports on (brain handover)


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


def arguments(ap):
    ap.add_argument("type", choices=sorted(FOLDERS))
    ap.add_argument("--from", dest="source")
    ap.add_argument("--title")
    ap.add_argument("--name")
    ap.add_argument("--kind")


def run(root, args):
    values = {}
    if args.source:
        if args.type != "episode":
            raise Refused("brain new: --from is for an episode")
        source = os.path.relpath(os.path.join(root, args.source), root)
        if not source.startswith("senses" + os.sep) or not os.path.isfile(os.path.join(root, source)):
            raise Refused(f"brain new: {args.source} is not a file in senses/")
        with open(os.path.join(root, source), encoding="utf-8", errors="replace") as fh:
            fields, body = parse_frontmatter(fh.read())
        fields = {k: v for k, v in (fields or {}).items() if isinstance(v, str) and v}
        heading = re.search(r"^# (.+)$", body, re.M)
        values = {"input": source.replace(os.sep, "/"), **{k: fields[k] for k in COPIED if k in fields}}
        values["title"] = fields.get("title") or (heading.group(1).strip() if heading else "")
        if "published" not in values and re.match(r"\d{4}-\d{2}-\d{2}", fields.get("date", "")):
            values["published"] = fields["date"][:10]
    title = (args.title or values.get("title") or "").strip()
    if not title:
        raise Refused("brain new: no title (give --title, or an input with a `title:` or a first heading)")
    name = slug(args.name or title)
    if not name:
        raise Refused("brain new: the title gives no file name; give --name")
    today = datetime.date.today().isoformat()
    values.update(title=title, created=today, updated=today, **({"kind": args.kind} if args.kind else {}))
    with open(os.path.join(TEMPLATES, f"{args.type}.md"), encoding="utf-8") as fh:
        template = fh.read()
    _, head, body = template.split("---\n", 2)
    for key, value in values.items():
        head = set_field(head, key, value)
    text = "---\n" + head + "---\n" + body.replace("{{title}}", title)
    rel = os.path.join("cortex", FOLDERS[args.type], f"{name}.md")
    path = os.path.join(root, rel)
    if os.path.exists(path):
        raise Refused(f"brain new: {rel} already exists; open it, or give another --name")
    problems = schema_problems(text, tag_vocabulary(root), stem=name, rel=rel)
    if problems:
        raise Refused(f"brain new: {rel} would break the page contracts: " + "; ".join(problems))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(text)
    return {"page": rel.replace(os.sep, "/"), "filled": sorted(values)}


def render(result, args):
    return "\n".join([f"created {result['page']}", f"  filled: {', '.join(result['filled'])}",
                      "  write the sections with Edit; leave the frontmatter as it is, apart from fields the skill names"])
