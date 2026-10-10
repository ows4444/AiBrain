"""Check a drafted answer or piece against the pages it cites: nothing in it without a page behind it.

Usage:
    brain ground FILE [--json]
    brain ground - [--json]         the draft on stdin

The core rule of /ask and /write is that every claim names the page it came
from, and that no number or quotation is introduced with no page behind it.
This reads a draft the way `brain check` reads a page and lists, by line, what
breaks that rule:

    link     a [[link]] that reaches no page (one in dormant/ is a page: say
             that it is dormant)
    number   a number that is on none of the pages its paragraph cites, or
             that stands in a paragraph citing none
    quote    three or more words in quotation marks that are on none of the
             pages their paragraph cites

A paragraph is a block of lines, or one list item, and a page is cited by a
[[link]] to it there. A number the page writes as a word is on it (`ten` for
10); so is a date. A sentence that says `outside knowledge` is the writer's
own, labelled as the rule asks, and is not checked; nor is a paragraph that
opens with those words.

Not read as claims: headings, code, the text of a link, a count of sources as
`brain recall` gives it (`3 sources, 2 independent`), a name with a number in
it (`SM-2`), and the closing lines `Read:`, `Confidence:` and `Not covered:`.

It reads digits and quotation marks, not meaning. A claim made in words alone
is not checked, and a line it lists may be sound (the page says ninety
minutes, the draft 1.5 hours): cite the page it is on, label the sentence, or
take it out, and say which. Exits 1 when it lists anything. Reads only.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from vaultlib import LINK, Vault  # noqa: E402

# A date, or digits with their thousands, decimals and percent sign; not part of a name or a word (SM-2, v2, 2nd).
NUMBER = re.compile(r"(?<![\w.,])(?<![A-Za-z]-)(\d{4}-\d{2}-\d{2}|\d+(?:,\d{3})*(?:\.\d+)?)%?(?!\w)")
QUOTE = re.compile(r"\"([^\"]+)\"|“([^”]+)”")
QUOTE_WORDS = 3  # fewer words in quotation marks are a term or a name, not a quotation
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK_TEXT = re.compile(r"\[\[[^\]]*\]\]")
SOURCE_COUNT = re.compile(r"\d+ (?:sources?|independent)\b")
OUTSIDE = re.compile(r"outside knowledge", re.I)
CLOSING = re.compile(r"^\s*(?:Read|Confidence|Not covered):")
ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
SENTENCE_END = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][)\]\"”]))\s+(?=[A-Z\[(\"“])")
SPELLED = {word: str(n) for n, word in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
SPELLED.update(thirty="30", forty="40", fifty="50", sixty="60", seventy="70", eighty="80", ninety="90",
               hundred="100", thousand="1000", million="1000000")


def blank(match):
    """The same length in spaces: what is taken out of a line leaves every other character where it was."""
    return " " * len(match.group(0))


def plain(text):
    """Lower case, one space between words, no link brackets: how a quotation and a page are compared."""
    return " ".join(re.sub(r"[\[\]]", "", text).lower().split())


def numbers_on(page):
    """Every number a page gives, as digits: the ones it writes in digits and the ones it spells out."""
    found = {m.group(1).replace(",", "") for m in NUMBER.finditer(page.text)}
    return found | {SPELLED[w] for w in re.findall(r"[a-z]+", page.text.lower()) if w in SPELLED}


def blocks(text):
    """[(its first line's number, its lines)] for each paragraph or list item; frontmatter, headings and code left out."""
    lines = text.splitlines()
    front = 0
    if lines and lines[0].strip() == "---":  # the draft's own frontmatter is not its prose
        front = next((n for n, line in enumerate(lines[1:], 2) if line.strip() == "---"), 0)
    out, current, fenced = [], None, False
    for number, line in enumerate(lines, 1):
        fence = line.lstrip().startswith(("```", "~~~"))
        fenced = fenced != fence
        if number <= front or fenced or fence or not line.strip() or line.lstrip().startswith("#"):
            current = None
            continue
        if current is None or ITEM.match(line):
            current = []
            out.append((number, current))
        current.append(line)
    return out


def ground(vault, text):
    """{checked: {links, numbers, quotes}, ungrounded: [{line, kind, text, why}]} for a draft's text."""
    dormant = {name.lower(): p for p in vault.dormant_pages for name in (p.stem, p.title, *p.aliases)}
    checked, rest = {"links": 0, "numbers": 0, "quotes": 0}, []
    for first, lines in blocks(text):
        block = INLINE_CODE.sub(blank, "\n".join(lines))
        cited = []
        for m in LINK.finditer(block):
            checked["links"] += 1
            page = vault.resolve(m.group(1)) or dormant.get(m.group(1).strip().lower())
            if page is None:
                rest.append({"line": first + block.count("\n", 0, m.start()), "kind": "link",
                             "text": f"[[{m.group(1).strip()}]]", "why": "no such page"})
            elif page not in cited:
                cited.append(page)
        why = ("not on " + ", ".join(f"[[{p.stem}]]" for p in cited)) if cited else "its paragraph cites no page"
        on_pages = set().union(*(numbers_on(p) for p in cited))
        pages = [plain(p.text) for p in cited]
        # What is left of the paragraph once its closing lines, list marks, links and the brain's own
        # counts are blanked out is what it claims.
        claims = "\n".join(" " * len(line) if CLOSING.match(line) else ITEM.sub(blank, line) for line in block.split("\n"))
        claims = SOURCE_COUNT.sub(blank, LINK_TEXT.sub(blank, claims))
        cuts = [0] + [m.end() for m in SENTENCE_END.finditer(claims)] + [len(claims)]
        labelled = [bool(OUTSIDE.match(claims.lstrip())) or bool(OUTSIDE.search(claims[a:b])) for a, b in zip(cuts, cuts[1:])]

        def claimed(m, kind, said):
            """Count one number or quotation, unless its sentence is labelled the writer's own; True when it counts."""
            if labelled[sum(cut <= m.start() for cut in cuts[1:-1])]:
                return False
            checked[kind + "s"] += 1
            return True

        for m in NUMBER.finditer(claims):
            if claimed(m, "number", m.group(0)) and m.group(1).replace(",", "") not in on_pages:
                rest.append({"line": first + claims.count("\n", 0, m.start()), "kind": "number", "text": m.group(0),
                             "why": why})
        for m in QUOTE.finditer(claims):
            said = " ".join((m.group(1) or m.group(2)).split()).strip(" .,;:!?")
            if len(said.split()) >= QUOTE_WORDS and claimed(m, "quote", said) and not any(plain(said) in page for page in pages):
                rest.append({"line": first + claims.count("\n", 0, m.start()), "kind": "quote", "text": f'"{said}"',
                             "why": why})
    return {"checked": checked, "ungrounded": sorted(rest, key=lambda r: (r["line"], r["kind"], r["text"]))}


def arguments(ap):
    ap.add_argument("file", help="the draft, from the brain's root; - for the text on stdin")


def run(root, args):
    if args.file == "-":
        text = sys.stdin.read()
    else:
        path = os.path.join(root, args.file)
        if not os.path.isfile(path):
            raise Refused(f"brain ground: no such file: {args.file}")
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    return dict(ground(Vault(root), text), file=args.file)


def render(result, args):
    c, rest = result["checked"], result["ungrounded"]
    what = f"{c['links']} links, {c['numbers']} numbers and {c['quotes']} quotations"
    name = "the draft" if result["file"] == "-" else result["file"]
    if not rest:
        return f"ground: {name}: {what}, each with a page behind it"
    out = [f"ground: {name}: {what}; {len(rest)} with no page behind {'it' if len(rest) == 1 else 'them'}"]
    out += [f"  line {r['line']}: {r['text'] if r['kind'] == 'link' else r['kind'] + ' ' + r['text']}: {r['why']}"
            for r in rest]
    out.append("  for each: cite the page it is on in that paragraph, label the sentence outside knowledge, or take it out")
    return "\n".join(out)


def exit_code(result):
    return 1 if result["ungrounded"] else 0
