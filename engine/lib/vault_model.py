"""The brain's vocabulary: constants, the field registry, page parsing, and Page.

Nothing here walks the brain: owner_goals and tag_vocabulary read its
CLAUDE.md and is_brain looks for two folders. vaultlib re-exports it all.
"""
import datetime
import os
import re

LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)
BLOCK_ITEM = re.compile(r"^[ \t]*-(?:[ \t]+(.*?))?[ \t]*$")
# A memory page's file name; the capitals and spaces live in its title.
FILE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FENCE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]*`")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LOG_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\S+)\s(.*)$")
CANDIDATES = re.compile(r"^## Candidates\s*\n(.*?)(?=^## |\Z)", re.S | re.M)
GAPS = re.compile(r"^## Gaps\s*\n(.*?)(?=^## |\Z)", re.S | re.M)
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
# Working memory: each prefrontal/<name>/CLAUDE.md is a project page named
# <name>. Its links count (they keep what it depends on from fading, and are
# checked like any link), but it is not long-term memory, so it stays out of
# the graph metrics, as the index does.
PROJECTS_DIR = "prefrontal"
# Faded pages: out of the index and the graph, but an episode that named one
# still does, so a link to a dormant page is a known state, not a broken link.
DORMANT_DIR = "dormant"
SYSTEM_TYPES = ("index", "log", "metrics", "fingerprints", "intentions", "project")
# A system type names one fixed file. Declared anywhere else it would exempt a
# memory page from every check, so there it is a schema problem, and the page
# is treated as an ordinary (untyped) page. Projects get theirs from their folder.
SYSTEM_PATHS = {
    "index": "hippocampus/index.md",
    "log": "hippocampus/log.md",
    "metrics": "hippocampus/metrics.md",
    "fingerprints": "hippocampus/fingerprints.md",
    "intentions": "hippocampus/intentions.md",
}
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
# Below this many scored guesses, a Brier score is shown with its count and no verdict.
BRIER_MIN = 10
MAX_TAGS = 3
LOG_PATH = os.path.join("hippocampus", "log.md")

# Every frontmatter field the brain gives meaning to, in one place: the schema
# check, export and the field table in templates/README.md all follow it.
#   on        page types it may appear on (None: any)
#   values    allowed values (None: free text)
#   date      must be YYYY-MM-DD
#   required  every page needs it
#   private   describes the brain, not the content: never exported
ANY = None
FIELDS = {
    "title":         dict(required=True),
    "type":          dict(required=True, values=PAGE_TYPES),
    "created":       dict(required=True, date=True),
    "updated":       dict(required=True, date=True),
    "aliases":       dict(),
    "tags":          dict(private=True),
    "status":        dict(on=("concept", "decision"), private=True),
    "input":         dict(on=("episode",), private=True),
    "url":           dict(),
    "author":        dict(),
    "published":     dict(),
    "consolidated":  dict(on=("episode", "decision"), date=True, private=True),
    "origin":        dict(on=("episode",), values=(GENERATED,), private=True),
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
       "maintain", "health", "guard", "rehearse", "rollback", "owner", "engine", "remind")

STALE_DAYS = 90
STUB_WORDS = 40
DORMANT_DAYS = 180
# Graded salience: `salience: 1-5` (`high` is 5). From SALIENT up, a page never
# fades and one episode is enough for a concept, as `high` always was; below it,
# each level only stretches the time a page takes to fade by SALIENCE_STRETCH.
SALIENT = 4
SALIENCE_STRETCH = 0.5
# Owner goals: `- <goal> by YYYY-MM-DD -> [[page]], [[project]]` under
# `### Goals` in the Owner section of CLAUDE.md; the date and links are optional.
GOAL_LINE = re.compile(r"^[-*]\s+(.+?)(?:\s+by\s+(\d{4}-\d{2}-\d{2}))?\s*(?:->\s*(.*))?$")
# A goal ends when its line says `(done)` or `(dropped)`. One more than
# GOAL_STALE_DAYS past its date stops protecting its pages until it is closed
# or re-dated, so purpose cannot silently grow forever.
GOAL_END = re.compile(r"\s*\((done|dropped)\)", re.I)
GOAL_STALE_DAYS = 30
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

# Spaced retrieval: days until the next rehearsal, by how many spaced
# rehearsals the owner has passed on a page (its strength). A pass raises
# strength only once the current interval has passed, so ten questions in one
# afternoon count once; a miss sets it back to the start. Only /rehearse moves
# this: a page the model read to answer a question was not recalled by the owner.
REHEARSAL_DAYS = (1, 3, 7, 14, 30, 60, 120)
HUB_MIN, HUB_FACTOR = 5, 3
# Exact betweenness costs pages x links; past this many pages it is estimated
# from a fixed, evenly spaced sample of starting pages, so results stay stable.
BRIDGES_EXACT_UP_TO, BRIDGES_SAMPLE = 500, 200
# Every threshold above is a guess until real use tests it. Once the brain has
# this many inputs and sleeps, the briefing asks for a calibration review from
# `brain introspect --usage` and the metrics; a `health calibration ...` log
# line records that it was done.
CHECKPOINT_INPUTS, CHECKPOINT_SLEEPS = 20, 4

# Healthy ranges
ORPHAN_HEALTHY, ORPHAN_BROKEN = 5, 15        # % of pages
DEGREE_WEAK, DEGREE_RANGE, DEGREE_DECORATIVE = 2, (3, 8), 10
MAIN_COMPONENT_MIN = 80                      # % of pages

# Retrieval (vault_retrieval). Guesses like every threshold above, tuned against
# the answer test set (`brain eval`), never by feel.
HEBBIAN_HALF_LIFE = 90       # days for a co-recall to lose half its weight
SPREAD_HOPS, SPREAD_DECAY = 2, 0.5
SEED_LIMIT = 5               # search hits that start the spread
PROJECT_BOOST = 1.5          # --project: its pages' seeds count this much more
NEAR_DUPLICATE = 0.6         # name or neighbour overlap that suggests a merge
SCHEMA_MIN = 4               # concepts in a cluster before it wants a framework page
GOAL_SLIP_DAYS = 30          # a goal this close with no activity in ACTIVITY_DAYS is at risk
ACTIVITY_DAYS = 28
RISK_MIN_ATTEMPTS = 3        # rehearsals before a page's miss rate is shown


def thresholds():
    """Every tunable number, for `brain introspect --usage` and the calibration review."""
    return {"stale_days": STALE_DAYS, "dormant_days": DORMANT_DAYS, "salient": SALIENT,
            "rehearsal_days": list(REHEARSAL_DAYS), "orphan_healthy_pct": ORPHAN_HEALTHY,
            "orphan_broken_pct": ORPHAN_BROKEN, "degree_range": list(DEGREE_RANGE),
            "main_component_min_pct": MAIN_COMPONENT_MIN, "hebbian_half_life": HEBBIAN_HALF_LIFE,
            "spread": [SPREAD_HOPS, SPREAD_DECAY], "near_duplicate": NEAR_DUPLICATE,
            "schema_min": SCHEMA_MIN, "brier_min": BRIER_MIN, "goal_slip_days": GOAL_SLIP_DAYS,
            "checkpoint": [CHECKPOINT_INPUTS, CHECKPOINT_SLEEPS]}


def verdicts(orphan_rate, avg_degree, main_share, pages):
    """One plain verdict per health metric; quiet until there is enough graph to judge."""
    if pages < 10:
        return {"overall": f"too small to judge ({pages} pages; read the numbers after about 10)"}
    orphan = ("healthy" if orphan_rate < ORPHAN_HEALTHY else
              "ingest is not linking: check the ingest skill" if orphan_rate > ORPHAN_BROKEN else "watch")
    degree = ("barely connected: retrieval cannot beat search" if avg_degree < DEGREE_WEAK else
              "check for decorative links" if avg_degree > DEGREE_DECORATIVE else
              "working range" if DEGREE_RANGE[0] <= avg_degree <= DEGREE_RANGE[1] else "acceptable")
    main = ("one main component" if main_share >= MAIN_COMPONENT_MIN else
            "fragmented: answers will be silently incomplete")
    return {"orphan_rate": orphan, "avg_degree": degree, "components": main}


def is_brain(root):
    """A brain is a folder holding both cortex/ and hippocampus/; hooks stay silent anywhere else."""
    return all(os.path.isdir(os.path.join(root, d)) for d in MEMORY_DIRS)


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
            if item.group(1):
                fields[list_key].append(item.group(1).strip("\"'"))
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


def candidates_in(body):
    """Names listed under `## Candidates` on an episode: `- Name - note` or `- [[Name]]`."""
    m = CANDIDATES.search(body)
    if not m:
        return []
    names = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith(("-", "*")):
            continue
        item = line[1:].strip()
        link = LINK.match(item)
        name = link.group(1) if link else re.split(r"\s+[-–—]\s+|:\s+", item, maxsplit=1)[0]
        if name.strip():
            names.append(name.strip())
    return names


def check_fields(fields, specs):
    problems = []
    for name, spec in specs.items():
        value = fields.get(name)
        if not value or name == "type":
            continue
        if spec.get("on") and fields.get("type") not in spec["on"]:
            problems.append(f"'{name}' belongs on {' or '.join(spec['on'])} pages only")
        elif spec.get("date") and not DATE.match(str(value)):
            problems.append(f"'{name}' must be YYYY-MM-DD")
        elif spec.get("values") and value not in spec["values"]:
            problems.append(f"'{name}' must be one of {', '.join(spec['values'])}, or absent")
    return problems


def file_name_problems(stem):
    """The file name rule: lowercase-hyphenated, so links and URLs stay stable."""
    if stem is None or FILE_NAME.match(stem):
        return []
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "page"
    return [f"file name '{stem}' is not lowercase-hyphenated: rename it to '{slug}', keep the title"]


def system_type_at(kind, rel):
    """True when `kind` is a system type and `rel` is the one file allowed to declare it.

    `rel` None means the caller does not know where the page lives (a bare text
    check); then the declaration is taken at its word, as it always was.
    """
    if kind not in SYSTEM_PATHS:
        return False
    return rel is None or rel.replace(os.sep, "/") == SYSTEM_PATHS[kind]


def schema_problems(text, vocabulary=None, page_type=None, stem=None, rel=None):
    """What breaks CLAUDE.md > Page contracts in this page; [] if nothing.

    `page_type` is set for pages whose type comes from where they live (projects).
    `stem` is the file name (a project's folder name), checked when given.
    `rel` is the root-relative path: a system type is accepted only at its own path.
    """
    fields, body = parse_frontmatter(text)
    if page_type == "project":  # an old project without frontmatter is fine
        return file_name_problems(stem) + check_fields(fields or {}, PROJECT_FIELDS)
    if fields is None:
        return ["missing frontmatter block"]
    kind = fields.get("type", "")
    if system_type_at(kind, rel):
        return []
    if kind in SYSTEM_TYPES:
        where = SYSTEM_PATHS.get(kind, "prefrontal/<name>/CLAUDE.md, where the folder sets it")
        return [f"type '{kind}' belongs only to {where}; a memory page here is one of {', '.join(PAGE_TYPES)}"]
    problems = file_name_problems(stem)
    if kind not in PAGE_TYPES:
        problems.append(f"type '{kind}' is not one of {', '.join(PAGE_TYPES)}")
    problems += [f"missing '{k}'" for k in REQUIRED_FIELDS if not fields.get(k)]
    if isinstance(fields.get("title"), list):
        problems.append("'title' reads as a list: quote it if it starts with '['")
    problems += check_fields(fields, FIELDS)
    if kind == "concept" and fields.get("status") not in STATUSES:
        problems.append(f"concept 'status' must be one of {', '.join(STATUSES)}")
    if kind == "decision":
        problems += decision_problems(fields)
        if fields.get("status") in ("decided", "reviewed"):  # an open one is still being framed
            problems += claim_problems(body)
    tags = as_list(fields.get("tags"))
    if len(tags) > MAX_TAGS:
        problems.append(f"{len(tags)} tags; at most {MAX_TAGS}")
    unknown = [t for t in tags if vocabulary and t not in vocabulary]
    if unknown:
        problems.append(f"tags {unknown} are not in the vocabulary; propose new tags in CLAUDE.md first")
    return problems


def decision_problems(fields):
    status = fields.get("status")
    if status not in DECISION_STATUSES:
        return [f"decision 'status' must be one of {', '.join(DECISION_STATUSES)}"]
    problems = []
    if status in ("decided", "reviewed") and not fields.get("review"):
        problems.append(f"a {status} decision needs 'review: YYYY-MM-DD', when to check the outcome")
    if status in ("decided", "reviewed") and not fields.get("revisit_if"):
        problems.append(f"a {status} decision needs 'revisit_if:', the event that means look again before the date")
    if status == "reviewed" and fields.get("outcome") not in OUTCOMES:
        problems.append(f"a reviewed decision needs 'outcome' as one of {', '.join(OUTCOMES)}")
    if status != "reviewed" and fields.get("outcome"):
        problems.append("'outcome' is set only once the decision is reviewed")
    return problems


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


def claim_problems(body):
    """What breaks the claim-tag rule (CLAUDE.md > Page contracts) in a decision's body; [] if nothing."""
    problems = []
    claims = [c for c in claims_in(body) if c["section"] in CLAIM_SECTIONS]
    for section in CLAIM_SECTIONS:
        untagged = sum(c["section"] == section and c["tag"] not in CLAIM_TAGS for c in claims)
        if untagged:
            problems.append(f"{untagged} untagged lines under ## {section}: start each with "
                            f"- [{'], ['.join(CLAIM_TAGS)}]")
    for c in claims:
        if c["p"] is not None and c["tag"] not in PROBABILITY_TAGS:
            problems.append(f"[{c['tag']} {round(c['p'] * 100)}%]: only a "
                            f"{' or '.join(PROBABILITY_TAGS)} carries a probability")
        elif c["p"] is not None and c["p"] > 1:
            problems.append(f"[{c['tag']} {round(c['p'] * 100)}%]: a probability is 0-100%")
        if c["tag"] == "decision" and c["section"] != "Decision":
            problems.append(f"[decision] belongs under ## Decision only, found under ## {c['section']}")
        if c["tag"] == "observation" and not LINK.search(c["text"]) and not OWNER_SAW.search(c["text"]):
            problems.append(f"[observation] '{c['text'][:40]}' cites nothing: link the page, or add (owner, YYYY-MM-DD)")
    return problems


def relations_in(body):
    """(relation, target) for every typed link in prose."""
    return [(r, t.strip()) for r, t in TYPED_LINK.findall(prose(body))]


def parse_date(value):
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def owner_goals(root):
    """[{text, due, links, ended}] from `### Goals` in the Owner section of the brain's CLAUDE.md."""
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        owner = re.search(r"^## Owner\s*\n(.*?)(?=^## |\Z)", fh.read(), re.S | re.M)
    section = owner and re.search(r"^### Goals\s*\n(.*?)(?=^##+ |\Z)", owner.group(1), re.S | re.M)
    goals = []
    for line in (section.group(1).splitlines() if section else []):
        end = GOAL_END.search(line)
        m = GOAL_LINE.match(GOAL_END.sub("", line).strip())
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
        self.targets = links_in(self.body)
        self.relations = relations_in(self.body)
        self.words = len(self.body.split())

    @property
    def is_system(self):
        return self.type in SYSTEM_TYPES

    @property
    def updated(self):
        return parse_date(self.fields.get("updated", ""))

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


def tokens(text):
    """Search terms in text: lowercase words, stop words out, stemmed."""
    return [stem(w) for w in WORD.findall(str(text).lower()) if w not in STOP_WORDS]


def tag_vocabulary(root):
    """Tags allowed by the `## Tags` section of the root CLAUDE.md, or None."""
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        m = re.search(r"^## Tags\s*\n(.*?)(?=^## |\Z)", fh.read(), re.S | re.M)
    if not m:
        return None
    tags = set(re.findall(r"`([a-z0-9-]+)`", m.group(1)))
    return tags or None
