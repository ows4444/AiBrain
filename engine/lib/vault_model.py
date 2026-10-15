"""The brain's vocabulary: constants, the field registry, page parsing, and Page.

Nothing here walks the brain: owner_goals and tag_vocabulary read its
CLAUDE.md and is_brain looks for two folders. vaultlib hands all of it on.
The numbers a brain may tune are not here: vault_tuning holds them.

It imports no part of the engine, so every part may import it. What breaks
the page contract is vault_schema's to say: that needs the modules that read
the system pages (tuning, intentions, policy), and each of them needs a name
from here.
"""
import datetime
import os
import re
import unicodedata

# The vocabulary is all for use: vaultlib hands on every name defined here.
__all__ = [
    "LINK", "FRONTMATTER", "BLOCK_ITEM", "FILE_NAME", "FENCE", "INLINE_CODE", "DATE", "LOG_LINE", "CANDIDATES",
    "GAPS", "TYPED_LINK", "SECTION", "CLAIM", "OWNER_SAW", "MEMORY_DIRS", "PAGE_TYPES", "TYPE_FOLDERS",
    "PROJECTS_DIR", "DORMANT_DIR", "SYSTEM_TYPES", "SYSTEM_PATHS", "STATUSES", "DECISION_STATUSES", "OUTCOMES",
    "GENERATED", "RELATIONS", "CLAIM_TAGS", "CLAIM_SECTIONS", "CLAIM_RESULTS", "PROBABILITY_TAGS", "MAX_TAGS",
    "SUMMARY_MAX", "SUMMARY_BODY_WORDS", "MAX_ANSWERS", "ANSWER_MAX", "LOG_PATH", "FIELDS", "PROJECT_STATUSES",
    "PROJECT_FIELDS", "REQUIRED_FIELDS", "PRIVATE_FIELDS", "OPS", "SALIENT", "OWNER_FILE", "CHARACTER_FILE",
    "GOAL_LINE", "END", "REHEARSED_TYPES", "LINKED_TO_TYPES", "FADE_IGNORES_LINKS_FROM", "STUB_TYPES", "QUESTION",
    "WORD", "STRETCH", "STOP_WORDS", "Page", "section", "system_path", "is_brain", "find_brain",
    "parse_frontmatter", "as_list", "prose", "links_in", "candidate_notes", "candidates_in", "same_idea",
    "system_type_at", "claims_in", "relations_in", "parse_date", "owner_file", "owner_text", "under_title",
    "character_text", "character_lines", "owner_goals", "salience_level", "stem", "spelled", "tokens",
    "tag_vocabulary",
]

LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)
BLOCK_ITEM = re.compile(r"^[ \t]*-(?:[ \t]+(.*?))?[ \t]*$")
# A memory page's file name; the capitals and spaces live in its title.
FILE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FENCE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]*`")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A line of the log: its date, the time of day when it has one (`brain log` writes it; older lines
# have none), the operation, and the rest.
LOG_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?: ((?:[01]\d|2[0-3]):[0-5]\d))? (\S+)\s(.*)$")


def section(heading):
    """A pattern for the text under one `## ` heading of a page, up to the next heading of its level."""
    return re.compile(rf"^## {heading}\s*\n(.*?)(?=^## |\Z)", re.S | re.M)


CANDIDATES = section("Candidates")
GAPS = section("Gaps")
# A typed link states how one page bears on another: `(supports:: [[Page]])`.
TYPED_LINK = re.compile(r"\(([\w-]+)::\s*\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]\)")
SECTION = re.compile(r"^## (.+?)[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)
# A claim on a decision page: `- [assumption] text`, and under Outcome `... -> held`.
# A guess may carry the owner's probability inside the tag, `- [hypothesis 70%] text`:
# inside the brackets, so a claim that starts with a number ("70% of teams ...") is never misread.
CLAIM = re.compile(r"^[-*]\s+\[([\w-]+)(?:\s+(\d{1,3})%)?\]\s+(.*?)(?:\s+->\s+(\w+))?$")
OWNER_SAW = re.compile(r"\(owner, \d{4}-\d{2}-\d{2}\)")

# Long-term memory lives in cortex/; the hippocampus holds the index, the log
# and metrics, which point at memories but are not memories themselves.
MEMORY_DIRS = ("cortex", "hippocampus")
PAGE_TYPES = ("episode", "concept", "entity", "insight", "decision")
# The folder of cortex/ a page of each type lives in: `brain new` writes it there, `brain restore` brings it back.
TYPE_FOLDERS = {"episode": "episodes", "concept": "concepts", "entity": "entities", "insight": "insights",
                "decision": "decisions"}
# Working memory: each prefrontal/<name>/CLAUDE.md is a project page named
# <name>. Its links count (they keep what it depends on from fading, and are
# checked like any link), but it is not long-term memory, so it stays out of
# the graph metrics, as the index does.
PROJECTS_DIR = "prefrontal"
# Faded pages: out of the index and the graph, but an episode that named one
# still does, so a link to a dormant page is a known state, not a broken link.
DORMANT_DIR = "dormant"
SYSTEM_TYPES = ("index", "log", "metrics", "fingerprints", "intentions", "tuning", "policy", "project")
# A system type names one fixed file. Declared anywhere else it would exempt a
# memory page from every check, so there it is a schema problem, and the page
# is treated as an ordinary (untyped) page. Projects get theirs from their folder.
SYSTEM_PATHS = {
    "index": "hippocampus/index.md",
    "log": "hippocampus/log.md",
    "metrics": "hippocampus/metrics.md",
    "fingerprints": "hippocampus/fingerprints.md",
    "intentions": "hippocampus/intentions.md",
    "tuning": "hippocampus/tuning.md",
    "policy": "hippocampus/policy.md",
}


def system_path(kind):
    """Where the one file of a system type is, from the brain's root, as this machine writes a path."""
    return os.path.join(*SYSTEM_PATHS[kind].split("/"))


STATUSES = ("emerging", "established")
# A decision is weighed (open), made with a date to check how it went
# (decided), then compared against what was expected (reviewed).
DECISION_STATUSES = ("open", "decided", "reviewed")
OUTCOMES = ("as-expected", "better", "worse", "mixed")
# An episode the brain wrote itself (/explore) rather than encoded from input.
GENERATED = "generated"
RELATIONS = ("supports", "contradicts", "extends", "part-of", "applies")
# What each line of a decision's reasoning is, so evidence and guesses stay
# apart: an observation cites a page (or the owner, dated); the rest are the
# owner's reading, guesses and the choice itself.
CLAIM_TAGS = ("observation", "interpretation", "hypothesis", "assumption", "decision")
CLAIM_SECTIONS = ("Options", "Expected", "Decision", "Lessons")
# At review, each assumption and hypothesis is repeated under Outcome with one of these.
CLAIM_RESULTS = ("held", "failed", "unknown")
# Only a guess carries a probability; an observation is seen, not forecast.
PROBABILITY_TAGS = ("hypothesis", "assumption")
MAX_TAGS = 3
# `summary:` is one sentence a reader can decide on: open the page or not.
# Recall and search print it, so an answer reads five summaries and then only
# the pages it needs. A page whose sections are still empty (a scaffold from
# `brain new`) may lack it; one with SUMMARY_BODY_WORDS of text may not.
SUMMARY_MAX = 200
SUMMARY_BODY_WORDS = 30
# `answers:` holds the questions a page answers, in the words its owner asks them in: written
# with the page, when the writer has just read it, so a question that shares no word with the
# title can still find the page. A few short questions, not a second summary.
MAX_ANSWERS = 5
ANSWER_MAX = 120
LOG_PATH = system_path("log")

# Every frontmatter field the brain gives meaning to, in one place: the schema
# check, export and the field table in templates/README.md all follow it.
#   on        page types it may appear on (None: any)
#   values    allowed values (None: free text)
#   date      must be YYYY-MM-DD
#   required  every page needs it
#   private   describes the brain, not the content: never exported
FIELDS = {
    "title":         dict(required=True),
    "type":          dict(required=True, values=PAGE_TYPES),
    "created":       dict(required=True, date=True),
    "updated":       dict(required=True, date=True),
    "summary":       dict(),
    "aliases":       dict(),
    "answers":       dict(private=True),
    "tags":          dict(private=True),
    "status":        dict(on=("concept", "decision"), private=True),
    "input":         dict(on=("episode",), private=True),
    "url":           dict(),
    "author":        dict(),
    "published":     dict(),
    "relays":        dict(on=("episode",)),
    "consolidated":  dict(on=("episode", "decision"), date=True, private=True),
    "origin":        dict(on=("episode",), values=(GENERATED,), private=True),
    "handed":        dict(on=("episode",), private=True),
    "kind":          dict(on=("entity",), values=("person", "org", "product", "tool")),
    "review":        dict(on=("decision",), date=True, private=True),
    "outcome":       dict(on=("decision",), values=OUTCOMES, private=True),
    "revisit_if":    dict(on=("decision",), private=True),
    "salience":      dict(values=("high", "1", "2", "3", "4", "5"), private=True),
    "maintained_by": dict(values=("human",), private=True),
    "publish":       dict(values=("true",), private=True),
}
# A project page (prefrontal/<name>/CLAUDE.md) is a system page, outside the
# table above, but its status decides whether its links protect anything, so a
# typo there must not pass silently.
PROJECT_STATUSES = ("active", "paused", "done")
PROJECT_FIELDS = {
    "status":  dict(values=PROJECT_STATUSES),
    "due":     dict(date=True),
    "created": dict(date=True),
    "updated": dict(date=True),
}
REQUIRED_FIELDS = tuple(k for k, f in FIELDS.items() if f.get("required"))
PRIVATE_FIELDS = frozenset(k for k, f in FIELDS.items() if f.get("private"))

# Operations a log line may record (CLAUDE.md > Log). `recall` lines are what
# strengthen pages; `engine` records changes to the engine itself.
OPS = ("ingest", "recall", "sleep", "explore", "decide", "review", "write", "focus",
       "maintain", "health", "guard", "rehearse", "rollback", "owner", "engine", "remind", "forget", "act")

# Graded salience: `salience: 1-5` (`high` is 5). From SALIENT up, a page never
# fades and one episode is enough for a concept, as `high` always was; below it,
# each level only stretches the time a page takes to fade (salience_stretch).
# A rule the documents state (CLAUDE.md > How memory forms), so no brain tunes it.
# A page built on a marked episode takes its mark, never above SALIENT - 1
# (Vault.salience_of): `Page.salience` is only what the page itself carries.
SALIENT = 4
# Owner goals: `- <goal> by YYYY-MM-DD -> [[page]], [[project]]` under
# `## Goals` in OWNER.md; the date and links are optional. A brain from before
# OWNER.md keeps them under `### Goals` in the Owner section of CLAUDE.md.
OWNER_FILE = "OWNER.md"
CHARACTER_FILE = "CHARACTER.md"  # who the brain is to its owner; the rules of CLAUDE.md come before any line of it
GOAL_LINE = re.compile(r"^[-*]\s+(.+?)(?:\s+by\s+(\d{4}-\d{2}-\d{2}))?\s*(?:->\s*(.*))?$")
# The closing mark: a goal's line and a reminder's (vault_intentions) end the same way, with `(done)` or
# `(dropped)`, which may carry the day and what happened: `(done)`, `(done 2026-11-03)`,
# `(dropped: no longer needed)`, `(done 2026-11-03: confirmed)`.
END = re.compile(r"\s*\((done|dropped)(?:\s+(\d{4}-\d{2}-\d{2}))?(?:\s*:\s*([^)]*?))?\s*\)", re.I)
# A goal one more than goal_stale_days past its date stops protecting its pages until it is closed
# or re-dated, so purpose cannot silently grow forever.
REHEARSED_TYPES = ("concept", "insight")
# Pages something should link *to*. Decisions and /explore episodes are
# records: they link out to what they used, and nothing is expected to link
# back, so they are never orphans or stubs. Unconsolidated episodes are in the
# sleep queue, and sleep is what links them.
LINKED_TO_TYPES = ("concept", "entity", "insight", "episode")
# Sleep links every episode to the pages it supports, so a link from an
# episode says where a page came from, not that anything still uses it: it
# does not keep a page from fading.
FADE_IGNORES_LINKS_FROM = ("episode",)
STUB_TYPES = ("concept", "entity", "insight")
# What reads as a question, for recall on every prompt (the prompt_recall hook).
QUESTION = re.compile(r"\?\s*$|^\s*(?:what|why|how|which|who|whom|whose|when|where|does|do|did|is|are|was|were|can|"
                      r"could|should|would|will|has|have|explain|tell me|remind me)\b", re.I)


def is_brain(root):
    """A brain is a folder holding both cortex/ and hippocampus/; hooks stay silent anywhere else."""
    return all(os.path.isdir(os.path.join(root, d)) for d in MEMORY_DIRS)


def find_brain(start):
    """The nearest folder at or above `start` that is a brain, else None.

    A session opened in prefrontal/<name>/ is still inside its brain, so the
    hooks look upward the way the `brain` command does.
    """
    here = os.path.realpath(start)
    while True:
        if is_brain(here):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def parse_frontmatter(text):
    """Return (fields, body). Handles `key: value`, inline `[a, b]` lists, and block
    lists (`key:` then one `  - item` per line), which Obsidian's Properties editor writes."""
    m = FRONTMATTER.match(text)
    if not m:
        return None, text
    fields, list_key = {}, None
    for line in m.group(1).splitlines():
        item = BLOCK_ITEM.match(line)
        if item and list_key:
            if not isinstance(fields[list_key], list):
                fields[list_key] = []
            fields[list_key] += [item.group(1).strip("\"'")] if item.group(1) else []  # a bare `-` holds nothing
            continue
        list_key = None
        if ":" not in line or line.startswith((" ", "\t", "-", "#")):
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        else:
            value = value.strip("\"'")
            if not value:
                list_key = key  # items may follow
        fields[key] = value
    return fields, text[m.end():]


def as_list(value):
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def prose(body):
    return INLINE_CODE.sub("", FENCE.sub("", body))


def links_in(body):
    """Wikilink targets in prose. Code blocks and inline code are examples, not links."""
    return [t.strip() for t in LINK.findall(prose(body))]


def candidate_notes(body):
    """(name, note) for each line under `## Candidates` on an episode: `- Name - note` or `- [[Name]]`."""
    m = CANDIDATES.search(body)
    if not m:
        return []
    found = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith(("-", "*")):
            continue
        item = line[1:].strip()
        link = LINK.match(item)
        parts = re.split(r"\s+[-–—]\s+|:\s+", item[link.end():] if link else item, maxsplit=1)
        name = link.group(1) if link else parts[0]
        if name.strip():
            found.append((name.strip(), parts[-1].strip() if len(parts) > 1 else ""))
    return found


def candidates_in(body):
    """Names listed under `## Candidates` on an episode."""
    return [name for name, _ in candidate_notes(body)]


def same_idea(name):
    """What two names of one held idea have in common: the same words once stemmed, in any order.

    `Fluency illusion` and `Illusion of fluency` are one candidate, and so are `Desirable
    difficulty` and `Desirable difficulties`: two episodes naming it so are two sources for
    it. A name made only of stop words is known by its spelling.
    """
    return frozenset(tokens(name)) or name.strip().lower()


def system_type_at(kind, rel):
    """True when `kind` is a system type and `rel` is the one file allowed to declare it.

    `rel` None means the caller does not know where the page lives (a bare text
    check); then the declaration is taken at its word, as it always was.
    """
    if kind not in SYSTEM_PATHS:
        return False
    return rel is None or rel.replace(os.sep, "/") == SYSTEM_PATHS[kind]


def claims_in(body):
    """[{section, tag, p, text, result}] for each top-level line of a decision's reasoning.

    Covers the claim sections and Outcome. `tag` is None for a line that is not
    a `- [tag] text` bullet; indented lines and sub-headings belong to the line above.
    `p` is the stated probability (0..1) of a `- [hypothesis 70%] text` line, else None.
    """
    out = []
    for name, text in SECTION.findall(body):
        if name not in CLAIM_SECTIONS + ("Outcome",):
            continue
        for line in text.splitlines():
            if not line.strip() or line[0] in " \t#":
                continue
            m = CLAIM.match(line.rstrip())
            out.append({"section": name, "tag": m.group(1) if m else None,
                        "p": int(m.group(2)) / 100 if m and m.group(2) else None,
                        "text": m.group(3) if m else line.strip(), "result": m.group(4) if m else None})
    return out


def relations_in(body):
    """(relation, target) for every typed link in prose."""
    return [(r, t.strip()) for r, t in TYPED_LINK.findall(prose(body))]


def parse_date(value):
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def owner_file(root):
    """The file that holds the owner block: OWNER.md, or CLAUDE.md in a brain from before it."""
    return OWNER_FILE if os.path.exists(os.path.join(root, OWNER_FILE)) else "CLAUDE.md"


def owner_text(root):
    """The owner block: all of OWNER.md, or the Owner section of an older brain's CLAUDE.md."""
    path = os.path.join(root, owner_file(root))
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:  # as a page is read: a stray byte stops no command
        text = fh.read()
    if owner_file(root) == OWNER_FILE:
        return text
    owner = section("Owner").search(text)
    return owner.group(1) if owner else ""


def under_title(text):
    """A page of the owner's without its `# ` title and the note under it: what its lists and sections say."""
    return re.sub(r"\A# .*?\n(?:(?!^[-#_]).*\n)*", "", text, flags=re.M)


def character_text(root):
    """What CHARACTER.md holds, as text; "" for a brain without the file."""
    path = os.path.join(root, CHARACTER_FILE)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def character_lines(root):
    """What CHARACTER.md says, a line each: a heading as `Values:`, the rest as written; [] when it says nothing.

    Who the brain is to its owner: what it holds to and how it speaks. The title and the note
    under it are left out, as the briefing leaves them out of OWNER.md. A brain without the
    file has no character of its own: it speaks as the rules have it speak.
    """
    return [line.lstrip("#").strip() + ":" if line.startswith("#") else line.rstrip()
            for line in under_title(character_text(root)).splitlines() if line.strip()]


def owner_goals(root):
    """[{text, due, links, ended}] from the Goals section of the owner block."""
    section = re.search(r"^##+ Goals\s*\n(.*?)(?=^##+ |\Z)", owner_text(root), re.S | re.M)
    goals = []
    for line in (section.group(1).splitlines() if section else []):
        end = END.search(line)
        m = GOAL_LINE.match(END.sub("", line).strip())
        if m:
            goals.append({"text": m.group(1).strip(), "due": parse_date(m.group(2) or ""),
                          "links": [t.strip() for t in LINK.findall(m.group(3) or "")],
                          "ended": end.group(1).lower() if end else None})
    return goals


class Page:
    def __init__(self, path, rel, text, stem=None, forced_type=None):
        self.path = path
        self.rel = rel
        self.stem = stem or os.path.splitext(os.path.basename(path))[0]
        self.text = text
        fields, self.body = parse_frontmatter(text)
        self.fields = fields or {}
        declared = self.fields.get("type") or "untyped"
        if not forced_type and declared in SYSTEM_TYPES and not system_type_at(declared, rel):
            declared = "untyped"  # a system type away from its file exempts nothing; the check reports it
        self.type = forced_type or declared
        # `title: [WIP]` parses as a list; names must be text or every lookup breaks.
        title = self.fields.get("title")
        self.title = title if isinstance(title, str) and title else self.stem
        self.aliases = [str(a) for a in as_list(self.fields.get("aliases")) if a]
        self.answers = [str(a) for a in as_list(self.fields.get("answers")) if a]  # the questions it answers
        self.targets = links_in(self.body)
        self.relations = relations_in(self.body)
        self.words = len(self.body.split())

    @property
    def is_system(self):
        return self.type in SYSTEM_TYPES

    @property
    def summary(self):
        value = self.fields.get("summary")
        return value if isinstance(value, str) else ""

    @property
    def updated(self):
        return parse_date(self.fields.get("updated", ""))

    @property
    def came(self):
        """The day the page came into the brain: when it was made, else its last edit; None when it gives neither."""
        return parse_date(self.fields.get("created", "")) or self.updated

    @property
    def salience(self):
        """0 (unmarked) to 5; `high` is 5. See SALIENT."""
        return salience_level(self.fields.get("salience"))

    @property
    def protected(self):
        """Salient or hand-written pages never decay on their own."""
        return self.salience >= SALIENT or self.fields.get("maintained_by") == "human"

    @property
    def consolidated(self):
        return bool(self.fields.get("consolidated"))

    @property
    def generated(self):
        return self.fields.get("origin") == GENERATED

    @property
    def replayed_by_sleep(self):
        """Episodes (generated ones too), and decisions once their outcome is known."""
        return self.type == "episode" or (self.type == "decision" and self.fields.get("status") == "reviewed")

    @property
    def candidates(self):
        return candidates_in(self.body) if self.replayed_by_sleep else []

    @property
    def candidate_notes(self):
        return candidate_notes(self.body) if self.replayed_by_sleep else []

    @property
    def claims(self):
        return claims_in(self.body) if self.type == "decision" else []

    @property
    def gap_targets(self):
        """Links listed under the index's `## Gaps`: known missing pages, not broken links."""
        m = GAPS.search(self.body) if self.type == "index" else None
        return {t.lower() for t in links_in(m.group(1))} if m else set()


def salience_level(value):
    if value == "high":
        return 5
    return int(value) if isinstance(value, str) and value in ("1", "2", "3", "4", "5") else 0


WORD = re.compile(r"[a-z0-9]+")
# Where a word may be when the text is not plain ASCII: a to z, digits, and every character beyond ASCII.
# Which of those belong to a word (a letter, a digit, a mark) is `spelled`'s to say.
STRETCH = re.compile(r"[a-z0-9\u0080-\U0010ffff]+")
STOP_WORDS = frozenset(
    "a an and are as at be been but by can do does did for from had has have how i if in into is it its "
    "me my of on or our so than that the their them then there these they this to was we were what when "
    "where which who whom why will with would you your".split())


def stem(word):
    """A light suffix strip, the same on both sides of a match: spacing, spaced, space -> spac."""
    for suffix in ("ations", "ation", "ings", "ing", "edly", "ed", "ies", "ly", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            if suffix == "s" and word.endswith(("ss", "us", "is")):
                break
            word = word[:-len(suffix)] + ("y" if suffix == "ies" else "")
            break
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiouls":
        word = word[:-1]  # forgett -> forget
    return word


def spelled(text):
    """The words of lower-cased text in any alphabet, in order: what `tokens` reads when the text is not plain ASCII.

    A word is a run of letters, digits and the marks that belong to them (Unicode categories
    L, N and M); anything else ends it, a dash or a curly quote as a space does. A word whose
    accents fold away to plain a-to-z is given folded (café -> cafe, naïve -> naive, Schrödinger
    -> schrodinger), so it is one word with its plain spelling. Any other is given as written,
    in one composed form (NFC): the same word typed two ways is one word. A letter that is no
    accented a-to-z keeps its word as written (straße, smørrebrød, łódź).
    """
    out = []
    for stretch in STRETCH.findall(text):
        if not stretch.isascii() and not stretch.isalnum():  # something in it is no letter and no digit
            stretch = "".join(c if unicodedata.category(c)[0] in "LNM" else " " for c in stretch)
        for word in stretch.split():
            if word.isascii():
                out.append(word)
                continue
            plain = "".join(c for c in unicodedata.normalize("NFKD", word) if not unicodedata.combining(c)).lower()
            out += WORD.findall(plain) if plain.isascii() else [unicodedata.normalize("NFC", word)]
    return out


def tokens(text):
    """Search terms in text: lowercase words, stop words out, stemmed.

    Text in plain ASCII, which nearly every page and question is, is read as it always was: a
    word is a run of a to z and digits. Any other text is read by `spelled`, so a page or a
    question in another alphabet is found too. A Latin word whose accents fold away is stemmed
    as its plain form, so `cafe` finds `café`; a word in another script is kept as written and
    is not stemmed: the suffixes are English's, and so are the stop words.

    Not done: no word is split where a script writes none apart (Chinese, Japanese, Thai). A
    run of such characters is one term, and a question finds it by the same run only.
    """
    text = str(text).lower()
    if text.isascii():
        return [stem(w) for w in WORD.findall(text) if w not in STOP_WORDS]
    return [stem(w) if w.isascii() else w for w in spelled(text) if w not in STOP_WORDS]


def tag_vocabulary(root):
    """Tags allowed by the `## Tags` section of the root CLAUDE.md, or None."""
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        m = section("Tags").search(fh.read())
    if not m:
        return None
    tags = set(re.findall(r"`([a-z0-9-]+)`", m.group(1)))
    return tags or None
