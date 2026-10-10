"""Thresholds: every number a judgment of the brain rests on, in one registry, and a brain's own values.

Each number here is a guess until real use tests it. A brain changes one without
touching the engine: a line under `## Overrides` in hippocampus/tuning.md,

    - recall_floor = 0.35 (2026-11-02: paraphrase hit@5 0.81 to 0.88 on my own questions)

and every command reads it from then on. `brain introspect --usage` lists each
threshold with its default, its range and the brain's value; `brain eval --set
recall_floor=0.35` measures a value before any line is written; `brain check`
fails on a name that is no threshold or a value outside its range, and the page
hook refuses the write that would leave one.

Not here: the numbers the documents state as rules (a concept needs two
sources, salience 4 and up never fades, a summary is at most 200 characters,
three tags at most). Those are the brain's contract and live in vault_model.

No dependencies. Nothing here walks the brain: the overrides are one file,
read by its path as the log is.
"""
import collections
import difflib
import os
import re

TUNING_PATH = os.path.join("hippocampus", "tuning.md")
OVERRIDES = re.compile(r"^## Overrides[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)
BULLET = re.compile(r"^[-*]\s+")
# `- name = value`, then anything in brackets: why the value was kept, and when.
OVERRIDE = re.compile(r"^[-*]\s+(?P<name>[^=\s]+)\s*=\s*(?P<value>[^(]*?)\s*(?:\(.*\)\s*)?$")

# default: a whole number, a number with a point, or a rising list of whole numbers (the kind
#          of the default is the kind every value must be)
# low, high: the range a value may take, both ends included; for a list, of each entry
# what: what the number does, for the calibration review
Threshold = collections.namedtuple("Threshold", "default low high what")

THRESHOLDS = {name: Threshold(*spec) for name, spec in {
    # -- what goes stale, and what fades ---------------------------------------
    "stale_days": (90, 1, 3650, "days without an edit before a concept counts as stale, and recall asks whether "
                                 "it or an insight still holds"),
    "stub_words": (40, 1, 1000, "a concept, entity or insight with fewer words than this and no links is a stub"),
    "dormant_days": (180, 1, 3650, "days unlinked, unrecalled and unedited before a page is proposed for dormant/"),
    "salience_stretch": (0.5, 0.0, 5.0, "each salience level from 1 to 3 adds this share of dormant_days before "
                                         "the page fades"),
    # -- rehearsal -------------------------------------------------------------
    # A pass raises a page's strength only once the current interval has passed, so ten
    # questions in one afternoon count once; a miss sets it back to the start.
    "rehearsal_days": ((1, 3, 7, 14, 30, 60, 120), 1, 3650, "days until the next rehearsal, by spaced rehearsals "
                                                             "passed; the last one holds from then on"),
    "risk_min_attempts": (3, 1, 100, "rehearsals of a page before its miss rate is shown"),
    # -- goals -----------------------------------------------------------------
    "goal_stale_days": (30, 0, 3650, "days past its date before a goal stops protecting its pages"),
    "goal_slip_days": (30, 0, 3650, "an open goal due within this many days, with nothing done lately, is at risk"),
    "activity_days": (28, 1, 3650, "how far back an edit or a recall counts as work toward a goal"),
    # -- decisions -------------------------------------------------------------
    "brier_min": (10, 1, 1000, "scored guesses before a Brier score is given with a verdict"),
    # -- the calibration checkpoint ----------------------------------------------
    # Once the brain has this many inputs and sleeps, the briefing asks for a review of
    # these numbers; a `health calibration ...` log line records that it was done.
    "checkpoint_inputs": (20, 1, 100000, "inputs encoded before the briefing asks for the calibration review"),
    "checkpoint_sleeps": (4, 1, 100000, "sleeps logged before the briefing asks for the calibration review"),
    # -- the graph's health ------------------------------------------------------
    "orphan_healthy": (5, 0, 100, "orphan rate, in percent of pages, under which linking is healthy"),
    "orphan_broken": (15, 0, 100, "orphan rate, in percent, over which ingest is not linking"),
    "degree_weak": (2, 0, 1000, "average degree under which the graph is barely connected"),
    "degree_low": (3, 0, 1000, "the working range of the average degree starts here"),
    "degree_high": (8, 0, 1000, "the working range of the average degree ends here"),
    "degree_decorative": (10, 0, 1000, "average degree over which links are probably decorative"),
    "main_component_min": (80, 0, 100, "share of pages, in percent, the main component must hold"),
    "hub_min": (5, 1, 100000, "inbound links a page needs before it can be a hub"),
    "hub_factor": (3, 1, 1000, "times the average inbound count that makes a page a hub"),
    # Exact betweenness costs pages x links; past this many pages it is estimated from a
    # fixed, evenly spaced sample of starting pages, so results stay stable.
    "bridges_exact_up_to": (500, 1, 1000000, "pages up to which betweenness is exact, not estimated"),
    "bridges_sample": (200, 1, 1000000, "starting pages the betweenness estimate is made from"),
    "near_duplicate": (0.6, 0.0, 1.0, "name or neighbour overlap from which two pages are listed as one idea twice"),
    "schema_min": (4, 2, 1000, "concepts in a cluster before it wants a framework page"),
    # Two held candidates, or a candidate and a page, are put to sleep as possibly one idea
    # when their names share half their words, or their names and notes share this much.
    "pair_overlap": (0.5, 0.0, 1.0, "share of the shorter one's words two held ideas must share to be paired"),
    "pair_min_words": (3, 1, 100, "words two held ideas must share to be paired"),
    # -- search: how much a word counts by where it stands -------------------------
    # The summary says what the page holds in other words than its title, so a question
    # in a person's words can reach it. It restates the body, so it counts for half: at
    # 1.0 and above the eval's `first` and standard sets fall. A weight of 0 leaves the
    # field out of search.
    "weight_title": (3.0, 0.0, 100.0, "how much a word in the title counts in search"),
    "weight_aliases": (2.0, 0.0, 100.0, "how much a word in an alias counts in search"),
    "weight_body": (1.0, 0.0, 100.0, "how much a word in the body counts in search"),
    "weight_summary": (0.5, 0.0, 100.0, "how much a word in the summary counts in search"),
    "bm25_k1": (1.2, 0.0, 10.0, "BM25: how fast a repeated word stops adding to a page's score"),
    "bm25_b": (0.75, 0.0, 1.0, "BM25: how much a long page is marked down"),
    # -- recall: seeds, then association along links ---------------------------------
    "seed_limit": (5, 1, 100, "search hits that start the spread"),
    "spread_hops": (2, 0, 6, "links activation is followed along from each seed"),
    "spread_decay": (0.5, 0.0, 1.0, "share of a page's activation each hop passes on"),
    "hebbian_half_life": (90, 1, 36500, "days for a co-recall to lose half its weight"),
    # How much a typed link carries activation, against 1.0 for a plain link. A
    # contradiction is followed like a plain link (the other side must be seen), and the
    # result is flagged. Never 0: a page's strongest link is what the others are measured by.
    "relation_supports": (1.2, 0.1, 10.0, "how much a `supports` link carries activation, against 1.0 for a plain one"),
    "relation_extends": (1.2, 0.1, 10.0, "how much an `extends` link carries activation"),
    "relation_part_of": (1.1, 0.1, 10.0, "how much a `part-of` link carries activation"),
    "relation_applies": (1.1, 0.1, 10.0, "how much an `applies` link carries activation"),
    "relation_contradicts": (1.0, 0.1, 10.0, "how much a `contradicts` link carries activation"),
    "unlinked_association": (0.5, 0.0, 10.0, "how strongly two pages only ever recalled together, with no link, "
                                              "associate"),
    "project_boost": (1.5, 0.0, 100.0, "--project: how much more a hit counts when the project links it"),
    "project_seed": (0.2, 0.0, 1.0, "--project: how strongly a page it links joins the seeds when it was no hit"),
    "strength_lift": (0.05, 0.0, 1.0, "how much each rehearsal level the owner holds lifts a page's score"),
    # `brain recall` stops where the match stops. Rows scoring under recall_floor of the
    # best row are cut: on the eval's fixture no expected page in the top five scores
    # under 0.47 of the first. And when the best page holds under min_coverage of the
    # question's words, weighted by how rare each is, nothing is returned: the words
    # reached a page, the question did not. This catches only a gross mismatch (a
    # retriever cannot know a question is uncovered).
    "recall_floor": (0.4, 0.0, 1.0, "recall cuts rows scoring under this share of the best row"),
    "min_coverage": (0.15, 0.0, 1.0, "recall lists nothing when the best page holds under this share of the question"),
    # -- recall on every prompt (the prompt_recall hook, off unless BRAIN_PROMPT_RECALL=1) --
    # It adds text to a prompt that did not ask for it, so its bar is higher than
    # `brain recall`'s.
    "prompt_coverage": (0.5, 0.0, 1.0, "prompt recall: share of the prompt the best page must hold"),
    "prompt_min_words": (4, 1, 100, "prompt recall: words a prompt needs before it is looked up"),
    "prompt_rows": (4, 1, 50, "prompt recall: summaries added at most"),
    "prompt_chars": (900, 100, 100000, "prompt recall: characters added at most"),
    # -- ideas held on an episode (a candidate with no page yet) -----------------------
    # Listed with a recall when the question names one: half or more of the words of its
    # name, and at least held_coverage of the question in its name and one-line note.
    "held_coverage": (0.5, 0.0, 1.0, "share of the question a held idea's name and note must hold to be listed"),
    "held_limit": (3, 1, 100, "held ideas listed with a recall at most"),
    # -- what an input bears on (`brain fit`) --------------------------------------------
    # Of the input's words that some page also holds, the ones that mark it most (often in
    # it, rare in the brain) are searched as one question.
    "fit_words": (12, 1, 100, "words of an input, the ones that mark it most, searched for the pages it bears on"),
    # -- what was asked and not answered (`brain introspect --gaps`) ---------------------
    # Questions no page answered are one gap when they share a rare word; a question with
    # no rare word is known by all of its words.
    "rare_word_share": (0.05, 0.0, 1.0, "a word under this share of the pages is rare: unanswered questions are "
                                        "grouped by the rare words they share"),
}.items()}
WEIGHT = "weight_"  # weight_<field>: the fields search reads, in the registry's order


def shown(value):
    """A value as tuning.md takes it and every listing prints it: `0.4`, `90`, `1, 3, 7`."""
    return ", ".join(str(v) for v in value) if isinstance(value, (tuple, list)) else str(value)


def plain(value):
    """A value as plain data, which is what a command's result carries: a ladder as a list."""
    return list(value) if isinstance(value, tuple) else value


def value_of(name, text):
    """`text` as a value of the threshold `name`; ValueError says what is wrong with it."""
    spec = THRESHOLDS.get(name)
    if spec is None:
        close = difflib.get_close_matches(name, THRESHOLDS, n=1)
        raise ValueError(f"'{name}' is not a threshold" + (f" (closest: {close[0]})" if close else "")
                         + "; `brain introspect --usage` lists them")
    ladder, whole = isinstance(spec.default, tuple), not isinstance(spec.default, float)
    try:
        values = [int(part) if whole else float(part) for part in (text.split(",") if ladder else [text])]
    except ValueError:
        kind = "whole numbers with commas between them" if ladder else "a whole number" if whole else "a number"
        raise ValueError(f"'{name} = {text.strip()}' is not {kind}") from None
    if not all(spec.low <= v <= spec.high for v in values):
        raise ValueError(f"'{name} = {text.strip()}' is outside {spec.low} to {spec.high}")
    if ladder and any(b <= a for a, b in zip(values, values[1:])):
        raise ValueError(f"'{name} = {text.strip()}' must rise: each number larger than the one before")
    return tuple(values) if ladder else values[0]


def setting(text):
    """(name, value) from `name=value`, as `brain eval --set` takes it; ValueError says what is wrong."""
    name, equals, value = text.partition("=")
    if not equals:
        raise ValueError(f"'{text}' is not name=value")
    return name.strip(), value_of(name.strip(), value)


def read_overrides(text):
    """({name: value}, [what is wrong]) from the `## Overrides` section of a tuning page.

    A line there is `- name = value`, with an optional note in brackets after it.
    A name that is no threshold, or a value outside its range, is not used: it is
    listed and the default holds. A name set twice is listed too; the later line holds.
    Lines that are not list items are prose, and ignored.
    """
    section = OVERRIDES.search(text)
    values, problems = {}, []
    for line in (section.group(1).splitlines() if section else []):
        line = line.strip()
        if not BULLET.match(line):
            continue
        m = OVERRIDE.match(line)
        if not m:
            problems.append(f"cannot read '{line}': an override is `- name = value (why)`")
            continue
        name = m.group("name").strip("`")
        try:
            value = value_of(name, m.group("value").strip("`"))
        except ValueError as why:
            problems.append(str(why))
            continue
        if name in values:
            problems.append(f"'{name}' is set twice; the later line is the one used")
        values[name] = value
    return values, problems


def tuning_problems(text):
    """What is wrong with the overrides in a tuning page's text; [] if nothing."""
    return read_overrides(text)[1]


class Tuning:
    """One brain's thresholds: the defaults, with its own values over them, read as `tuning.stale_days`.

    `overrides` holds the values that differ by the brain's own choice ({} for most brains);
    they are taken as valid, which read_overrides, value_of and setting make them.
    """

    def __init__(self, overrides=None):
        self.overrides = {name: tuple(value) if isinstance(value, list) else value
                          for name, value in (overrides or {}).items()}
        for name, spec in THRESHOLDS.items():
            setattr(self, name, self.overrides.get(name, spec.default))

    @property
    def field_weights(self):
        """((field, weight), ...) for the parts of a page search reads; a weight of 0 leaves the field out."""
        weights = ((name[len(WEIGHT):], getattr(self, name)) for name in THRESHOLDS if name.startswith(WEIGHT))
        return tuple((field, weight) for field, weight in weights if weight)

    @property
    def cache_key(self):
        """What the search cache's rows depend on: a row computed under other weights is not this brain's."""
        return " ".join(f"{field}={weight}" for field, weight in self.field_weights)

    def rows(self):
        """{name: {value, default, low, high, what}} for every threshold, in the registry's order, as plain data."""
        return {name: {"value": plain(getattr(self, name)), "default": plain(spec.default), "low": spec.low,
                       "high": spec.high, "what": spec.what} for name, spec in THRESHOLDS.items()}

    def changed(self):
        """{name: value} for the thresholds this brain overrides, as plain data: what a command's result carries
        so that its text can name the brain's own numbers. Tuning(changed()) is these thresholds again."""
        return {name: plain(value) for name, value in self.overrides.items()}


def tuning_of(root, trial=None):
    """The thresholds of the brain at `root`: its own overrides, with `trial` ({name: value}) laid over them.

    `trial` is how a value is tried before it is kept (`brain eval --set`): nothing is written.
    """
    path = os.path.join(root, TUNING_PATH)
    own = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            own = read_overrides(fh.read())[0]
    return Tuning(dict(own, **(trial or {})))
