#!/usr/bin/env python3
"""A web page as input: fetched, cut down to its readable text, saved in senses/.

Usage:
    brain fetch URL [--name SLUG] [--file PAGE.html] [--dry-run] [--json]

Writes senses/<today>-<slug>.md: frontmatter (`url`, `title`, `author`,
`published`, `fetched`) and the page's main content as Markdown: headings,
paragraphs, lists, links, code, quotes and tables. Navigation, scripts, forms,
footers and hidden elements are left out; an image is kept as its alt text. Prints the path and the sizes, so
only the saved file has to be read: the raw page never enters the conversation.

The main content is the largest <article>, failing that the largest <main>,
failing that the whole body. Under 400 characters of text is a fragment or a
paywall: reported, nothing saved, exit 1. A page that builds itself with
JavaScript arrives empty the same way.

--file PAGE.html extracts a page already on disk (URL is still recorded as
where it came from). --name sets the file's slug; otherwise it comes from the
title. A file in senses/ is never overwritten: a second fetch gets -2.
Standard library only; the extraction is cruder than a browser's reader view,
so `url:` stays on the file for fetching the original again.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

MAX_BYTES = 5_000_000
TIMEOUT = 20
MIN_TEXT = 400
AGENT = "Mozilla/5.0 (compatible; aibrain-fetch; a personal reading tool)"
SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "aside", "form", "button", "template", "iframe",
        "select", "dialog", "head"}
BLOCK = {"p", "div", "section", "article", "main", "header", "figure", "figcaption", "details", "summary", "dl",
         "dt", "dd", "address", "body"}
VOID = {"br", "hr", "img", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "track"}
MARKS = {"strong": "**", "b": "**", "em": "*", "i": "*", "code": "`", "kbd": "`"}
META = {"title": ("og:title", "twitter:title"), "author": ("author", "article:author", "og:article:author"),
        "published": ("article:published_time", "date", "og:article:published_time", "datepublished")}


class Reader(HTMLParser):
    """HTML to Markdown blocks, remembering where each <article> and <main> began and ended."""

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.blocks = []        # finished Markdown blocks
        self.line = []          # inline text of the block being built
        self.skip = 0           # depth inside a SKIP element
        self.skipped = []       # the tags that opened a skip, to close it on the right one
        self.pre = False
        self.heading = False    # inside <h1>-<h6>: blocks nested there do not break the line
        self.lists = []         # "ul" or a counter for "ol", innermost last
        self.quote = 0
        self.links = []         # (href, index in self.line where its text starts)
        self.row, self.rows, self.in_cell = None, None, False
        self.spans, self.open_spans = [], []
        self.meta, self.title, self.in_title = {}, "", False

    # -- blocks ---------------------------------------------------------------

    def flush(self, prefix=""):
        text = "".join(self.line)
        self.line = []
        if not self.pre:
            text = re.sub(r"[\s\u200b\u200c\u200d\ufeff]+", " ", text).strip()
        if not text:
            return
        if self.row is not None and self.in_cell:
            self.line = [text]  # a block inside a table cell stays in the cell
            return
        text = prefix + text
        if self.quote:
            text = "\n".join("> " + part for part in text.split("\n"))
        self.blocks.append(text)

    def item_prefix(self):
        depth = "\x01\x01" * (len(self.lists) - 1)  # folded whitespace would eat plain spaces
        if not self.lists:
            return ""
        if self.lists[-1] == "ul":
            return f"{depth}- "
        self.lists[-1] += 1
        return f"{depth}{self.lists[-1]}. "

    # -- parser events --------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content"):
                self.meta.setdefault(key, a["content"].strip())
            return
        if tag == "title" and not self.title:
            self.in_title = True
            return
        if self.skip:
            if tag not in VOID:
                self.skip += 1
                self.skipped.append(tag)
            return
        hidden = "hidden" in a or a.get("aria-hidden") == "true" or "display:none" in (a.get("style") or "").replace(" ", "")
        if tag in SKIP or (hidden and tag not in VOID) or (tag == "header" and not self.open_spans):
            self.skip, self.skipped = 1, [tag]
            return
        if tag in ("article", "main"):
            self.flush()
            self.open_spans.append((tag, len(self.blocks)))
        if self.heading and tag in BLOCK:
            self.line.append(" ")  # a heading wrapped around divs is still one line
            return
        if tag in BLOCK or tag in ("ul", "ol", "table", "blockquote", "tr") or re.fullmatch(r"h[1-6]", tag):
            self.flush()
        if tag == "ul":
            self.lists.append("ul")
        elif tag == "ol":
            self.lists.append(0)
        elif tag == "li":
            self.flush()
            self.line.append("\x00" + self.item_prefix())  # the marker survives whitespace folding
        elif re.fullmatch(r"h[1-6]", tag):
            self.line.append("\x00" + "#" * int(tag[1]) + " ")
            self.heading = True
        elif tag == "blockquote":
            self.quote += 1
        elif tag == "pre":
            self.flush()
            self.pre = True
        elif tag == "br":
            self.line.append("\n" if self.pre else " ")
        elif tag == "hr":
            self.flush()
            self.blocks.append("---")
        elif tag == "a":
            self.links.append((a.get("href") or "", len(self.line)))
        elif tag == "img":
            alt = re.sub(r"[\[\]]", "", a.get("alt") or "").strip()
            if alt:  # the words an image stands for; its address is of no use to a reader of text
                self.line.append(f"(image: {alt})")
        elif tag in MARKS and not self.pre:
            self.line.append(MARKS[tag])
        elif tag == "table":
            self.rows = []
        elif tag == "tr" and self.rows is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.line, self.in_cell = [], True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
            return
        if self.skip:
            if tag in self.skipped:
                while self.skipped.pop() != tag:
                    self.skip -= 1
                self.skip -= 1
            return
        if tag in ("td", "th") and self.row is not None:
            cell = re.sub(r"[\s\x00-\x02]+", " ", "".join(self.line)).replace("|", "\\|").strip()
            self.row.append(cell)
            self.line, self.in_cell = [], False
        elif tag == "tr" and self.row is not None:
            if any(self.row):
                self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.rows is not None:
            if self.rows:
                width = max(len(r) for r in self.rows)
                lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in self.rows]
                lines.insert(1, "|" + " --- |" * width)
                self.blocks.append("\n".join(lines))
            self.rows = None
        elif tag == "a" and self.links:
            href, start = self.links.pop()
            text = re.sub(r"\s+", " ", "".join(self.line[start:])).strip()
            del self.line[start:]
            if re.fullmatch(r"\(image: [^)]*\)", text):
                self.line.append(text)  # a picture that is a link: usually a badge or a link to itself
            elif text and href and not href.startswith(("#", "javascript:")):
                self.line.append(f"[{text}]({urllib.parse.urljoin(self.base, href)})")
            elif text:
                self.line.append(text)
        elif tag in MARKS and not self.pre:
            self.line.append(MARKS[tag])
        elif tag == "pre":
            code = "".join(self.line).strip("\n")
            self.line, self.pre = [], False
            if code.strip():
                self.blocks.append("```\n" + code + "\n```")
        elif tag in ("ul", "ol"):
            self.flush()
            if self.lists:
                self.lists.pop()
            if not self.lists:
                self.blocks.append("\x02")  # the list is over: the next item starts another
        elif tag == "blockquote":
            self.flush()
            self.quote = max(0, self.quote - 1)
        elif re.fullmatch(r"h[1-6]", tag):
            self.flush()
            self.heading = False
        elif (tag in BLOCK and not self.heading) or tag == "li":
            self.flush()
        if tag in ("article", "main") and self.open_spans and self.open_spans[-1][0] == tag:
            _, start = self.open_spans.pop()
            self.spans.append((tag, start, len(self.blocks)))

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.line.append(data)

    # -- result ---------------------------------------------------------------

    def markdown(self):
        """(text, which part of the page it is)."""
        self.flush()
        size = lambda span: sum(len(b) for b in self.blocks[span[1]:span[2]])  # noqa: E731
        for tag in ("article", "main"):
            spans = [s for s in self.spans if s[0] == tag]
            best = max(spans, key=size, default=None)
            if best and size(best) >= MIN_TEXT:
                return tidy(self.blocks[best[1]:best[2]]), tag
        return tidy(self.blocks), "body"


def tidy(blocks):
    out, previous_item = [], False
    for block in blocks:
        if block == "\x02":
            previous_item = False
            continue
        marked = block.startswith("\x00") or block.startswith("> \x00")
        block = block.replace("\x00", "").replace("\x01", " ")
        item = marked and bool(re.match(r"\s*(?:- |\d+\. )", block))
        # A heading or list item that held only something skipped leaves nothing behind
        # (its marker arrives without the space after it: flush strips the line).
        if block.strip() and not (marked and re.fullmatch(r"\s*(?:-|\d+\.|#+)\s*", block)):
            out.append(("\n" if item and previous_item else "\n\n") + block)
            previous_item = item
    return "".join(out).strip() + "\n"


def extract(html, url):
    """{title, author, published, text, part} from a page's HTML."""
    reader = Reader(url)
    reader.feed(html)
    reader.close()
    text, part = reader.markdown()
    found = {k: next((reader.meta[n] for n in names if n in reader.meta), "") for k, names in META.items()}
    heading = re.search(r"^# (.+)$", text, re.M)
    found["title"] = found["title"] or re.sub(r"\s+", " ", reader.title).strip() or (heading.group(1) if heading else "")
    found["published"] = found["published"][:10] if re.match(r"\d{4}-\d{2}-\d{2}", found["published"]) else ""
    return dict(found, text=text, part=part)


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        kind = response.headers.get_content_type()
        if kind not in ("text/html", "application/xhtml+xml", "text/plain", "text/markdown"):
            raise ValueError(f"not a page of text ({kind})")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError(f"larger than {MAX_BYTES // 1_000_000} MB")
        return raw.decode(response.headers.get_content_charset() or "utf-8", "replace"), kind


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")


def quoted(value):
    return '"' + re.sub(r"\s+", " ", value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    ap = argparse.ArgumentParser(prog="brain fetch")
    ap.add_argument("url")
    ap.add_argument("--root", default=".")
    ap.add_argument("--name")
    ap.add_argument("--file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if urllib.parse.urlsplit(args.url).scheme not in ("http", "https"):
        sys.exit("brain fetch: only http and https addresses")
    try:
        if args.file:
            with open(args.file, encoding="utf-8", errors="replace") as fh:
                html, kind = fh.read(), "text/html"
        else:
            html, kind = download(args.url)
    except (OSError, ValueError, urllib.error.URLError) as err:
        sys.exit(f"brain fetch: could not get {args.url}: {err}")
    if kind in ("text/plain", "text/markdown"):
        page = {"title": "", "author": "", "published": "", "text": html.strip() + "\n", "part": "plain text"}
    else:
        page = extract(html, args.url)
    words = len(re.sub(r"[\W_]+", " ", page["text"]).split())
    if len(re.sub(r"\s+", " ", page["text"])) < MIN_TEXT:
        sys.exit(f"brain fetch: {args.url} gave {words} words of text: a fragment, a paywall, or a page built by "
                 "JavaScript. Nothing saved; report it, do not encode it.")
    today = datetime.date.today().isoformat()
    name = slug(args.name or page["title"]) or slug(urllib.parse.urlsplit(args.url).path) or "page"
    rel = os.path.join("senses", f"{today}-{name}.md")
    n = 1
    while os.path.exists(os.path.join(args.root, rel)):
        n += 1
        rel = os.path.join("senses", f"{today}-{name}-{n}.md")
    head = ["---", f"url: {quoted(args.url)}", f"title: {quoted(page['title'])}"]
    head += [f"{k}: {quoted(page[k])}" for k in ("author", "published") if page[k]]
    head += [f"fetched: {today}", "---", "", ""]
    body = "\n".join(head) + page["text"]
    result = {"saved": None if args.dry_run else rel, "url": args.url, "title": page["title"], "author": page["author"],
              "published": page["published"], "part": page["part"], "raw_bytes": len(html.encode("utf-8")),
              "saved_bytes": len(body.encode("utf-8")), "words": words,
              "headings": len(re.findall(r"^#+ ", re.sub(r"```.*?```", "", page["text"], flags=re.S), re.M))}
    if not args.dry_run:
        os.makedirs(os.path.join(args.root, "senses"), exist_ok=True)
        with open(os.path.join(args.root, rel), "x", encoding="utf-8") as fh:
            fh.write(body)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"{'would save' if args.dry_run else 'saved'} {rel}")
    print(f"  {result['raw_bytes']} bytes fetched -> {result['saved_bytes']} saved "
          f"({result['words']} words, {result['headings']} headings, from the page's <{page['part']}>)")
    print(f"  title: {page['title'] or '(none found)'}" + (f"   author: {page['author']}" if page["author"] else "")
          + (f"   published: {page['published']}" if page["published"] else ""))
    print("  read that file, not the page; run `brain fingerprint` once it is in place")


if __name__ == "__main__":
    main()
