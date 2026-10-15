"""Shared brain model for the scripts and hooks. No dependencies.

One place decides what counts as a page, how frontmatter is read, how a
[[wikilink]] resolves, and how recall, consolidation and decay are measured,
so every script reports the same numbers. The parts live in their own modules:

    vault_model      constants, the field registry, parsing, Page; it imports no other part
    vault_tuning     the thresholds, and a brain's own values for them (hippocampus/tuning.md)
    vault_policy     the actions, and which a brain allows with nobody there (hippocampus/policy.md)
    vault_intentions the lines of hippocampus/intentions.md: what each reminder says, and when it comes round
    vault_schema     what breaks the page contract in one page's text, the three system pages above included
    vault_events     the log, parsed once into typed events
    vault_graph      links, orphans, components, hubs, bridges, clusters, near-duplicates, the health verdicts
    vault_memory     recall strength, the sleep queue, evidence, confidence, decay, calibration
    vault_purpose    goals and projects, and what they keep in use
    vault_reminders  the reminders: which are due, where one the brain carries out stands, what is handed over
    vault_retrieval  search, co-recall weights, spreading activation, link suggestions
    vault_affect     what the record gives the brain to feel: events and standing states, appraised
    vault_people     what the pages hold of each person: how well known, how their claims fared, what names them
    vault_cache      each page's search terms, kept between runs (.cache/search.sqlite); never the source of truth

Everything a command needs is importable from here, so a command imports vaultlib and no part of it.
Each part names what it offers in its `__all__`; those names and `Vault` are this module's own `__all__`,
and nothing else comes through: a part's other names are for the parts, which import them from each other.
Two things start before any brain is read and take `find_brain` from vault_model alone: the dispatcher
(commands) and the MCP server. And `brain cache` is the command over vault_cache itself.
"""
import copy
import datetime
import os

import vault_affect
import vault_events
import vault_graph
import vault_intentions
import vault_memory
import vault_model
import vault_people
import vault_policy
import vault_purpose
import vault_reminders
import vault_retrieval
import vault_schema
import vault_tuning
from vault_affect import *  # noqa: F403
from vault_events import *  # noqa: F403
from vault_graph import *  # noqa: F403
from vault_intentions import *  # noqa: F403
from vault_memory import *  # noqa: F403
from vault_model import *  # noqa: F403
from vault_people import *  # noqa: F403
from vault_policy import *  # noqa: F403
from vault_purpose import *  # noqa: F403
from vault_reminders import *  # noqa: F403
from vault_retrieval import *  # noqa: F403
from vault_schema import *  # noqa: F403
from vault_tuning import *  # noqa: F403
# What this module uses itself, by name: the star imports above are what it hands on.
from vault_affect import AffectMixin
from vault_events import MISSED, moment, read_events
from vault_graph import GraphMixin
from vault_memory import MemoryMixin
from vault_model import DORMANT_DIR, MEMORY_DIRS, PROJECTS_DIR, Page, owner_goals, tag_vocabulary
from vault_people import PeopleMixin
from vault_purpose import PurposeMixin
from vault_reminders import RemindersMixin
from vault_retrieval import RetrievalMixin
from vault_schema import schema_problems
from vault_tuning import tuning_of

# The parts a command reaches through here, in the order the list above describes them. No name is offered by two.
PARTS = (vault_model, vault_tuning, vault_policy, vault_intentions, vault_schema, vault_events, vault_graph,
         vault_memory, vault_purpose, vault_reminders, vault_retrieval, vault_affect, vault_people)
__all__ = [name for part in PARTS for name in part.__all__] + ["Vault"]


class Vault(GraphMixin, MemoryMixin, PurposeMixin, RemindersMixin, RetrievalMixin, AffectMixin, PeopleMixin):
    def __init__(self, root, today=None, tuning=None, now=None):
        """`tuning` ({name: value}) is laid over the brain's own thresholds for this Vault only: a value being tried.

        `now` is the moment a reminder with a time of day is judged from: the clock's, unless
        given. A Vault given only its day (`today`) stands at that day's last minute.
        """
        self.root = os.path.abspath(root)
        # What is worked out once and kept (kept): `_shared` is every copy's too, `_learned` is what the log
        # taught this one, which a copy made by as_of does not inherit.
        self._shared, self._learned = {}, {}
        self.now = now or (moment(today) if today else datetime.datetime.now())
        self.today = today or self.now.date()
        self.tuning = tuning_of(self.root, tuning)
        self.pages = list(self._load())
        self.names = self._build_names()
        # Faded pages: not part of the graph, but searchable on request, and a link to one is a known state.
        self.dormant_pages = list(self._pages_under(DORMANT_DIR))
        self.dormant_names = {name.lower() for p in self.dormant_pages for name in (p.stem, p.title, *p.aliases)}
        self.edges, self.broken, self.gaps, self.faded = self._resolve()
        self.out_links, self.in_links = self._adjacency()
        self.goals = owner_goals(self.root)
        self.events = read_events(self.root)
        self._fold_log()

    def _fold_log(self):
        """What is read off the log's events at once: when each page was recalled, and how each rehearsal went."""
        self.recall_dates = self._recalls()
        self.rehearsal_grades = self._rehearsal_grades()
        self.rehearsals = {page: [(day, grade != MISSED) for day, grade in went]
                           for page, went in self.rehearsal_grades.items()}
        self.recall_count = {p: len(d) for p, d in self.recall_dates.items()}
        self.last_recall = {p: d[-1] for p, d in self.recall_dates.items()}

    def kept(self, name, make, from_log=False):
        """What `make()` gives, worked out once for this Vault and kept under `name`: the one way a value is kept.

        `from_log` marks a value folded from the log: the pair weights, where a reminder stands. A copy
        made by as_of does not inherit such a value and works out its own, from the lines it holds. Every
        other value is shared with the copies, whichever of them asks for it first: the pages, their links
        and the thresholds are the same in all of them. So `make` reads nothing a copy has of its own
        (events, today, now) unless `from_log` is set. `name` is anything a dict takes as a key: a value
        that depends on an argument is kept under (what it is, the argument).
        """
        held = self._learned if from_log else self._shared
        if name not in held:
            held[name] = make()
        return held[name]

    def let_go(self, name):
        """Stop keeping a value that is shared with the copies, and return it: None when it was never worked out."""
        return self._shared.pop(name, None)

    def as_of(self, line, today=None):
        """This brain as it had been used when its log held only its first `line` dated lines.

        The pages are the ones here now. What the log taught after that point is unknown to the
        copy: recalls, rehearsals, the pairs recalled together. `today` is the day it judges
        from, for what fades with time; as_of(0) has been used for nothing. A question from
        the log is replayed on such a copy, so the line that recorded its answer cannot help
        to find it (`brain eval --from-log`). Cheap: pages, links and search terms are shared,
        and so is every value kept that the log did not teach (kept).
        """
        # The pages each line names are read off the whole log here, before there is a copy: a copy holds the
        # first events of the same log and reads its own from the front of them (_event_pages, _pairs_recalled).
        self._pairs_recalled()
        then = copy.copy(self)
        then.today = today or self.today
        then.now = moment(today) if today else self.now
        then.events = self.events[:line]
        then._learned = {}  # what the log taught is the copy's own to work out, from the lines it holds
        then._fold_log()
        return then

    def _pages_under(self, top):
        """A Page for each Markdown file under one folder of the brain, in a fixed order.

        A folder's own README.md is documentation and no page, and a hidden folder is not looked into.
        """
        for dirpath, dirnames, filenames in os.walk(os.path.join(self.root, top)):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for name in sorted(filenames):
                if name.endswith(".md") and name != "README.md":
                    path = os.path.join(dirpath, name)
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        yield Page(path, os.path.relpath(path, self.root), fh.read())

    def _load(self):
        for top in MEMORY_DIRS:
            yield from self._pages_under(top)
        projects = os.path.join(self.root, PROJECTS_DIR)
        for name in sorted(os.listdir(projects)) if os.path.isdir(projects) else []:
            path = os.path.join(projects, name, "CLAUDE.md")
            if not name.startswith((".", "_")) and os.path.isfile(path):
                with open(path, encoding="utf-8", errors="replace") as fh:
                    yield Page(path, os.path.relpath(path, self.root), fh.read(), stem=name, forced_type="project")

    def _build_names(self):
        # Obsidian resolves a link by file name first; titles and aliases fill in.
        names = {}
        for p in self.pages:
            names.setdefault(p.stem.lower(), p)
        for p in self.pages:
            for n in [p.title] + p.aliases:
                names.setdefault(n.lower(), p)
        return names

    def ambiguous_names(self):
        """Names more than one page answers to: a link to one silently reaches the first.

        Returns (clashes, unused). A file name two pages share is always a clash,
        e.g. a concept and a project both called `launch`: the file name is how
        links are written. A shared title or alias is a clash only once some link
        uses it; until then it is listed in `unused`, e.g. two clips of one article
        sharing its title. Each is {name: [pages]}.
        """
        claims, stems = {}, {}
        for p in self.pages:
            stems.setdefault(p.stem.lower(), []).append(p)
            for n in {p.stem.lower(), p.title.lower(), *(a.lower() for a in p.aliases)}:
                claims.setdefault(n, []).append(p)
        linked = {t.lower() for p in self.pages if p.type != "log" for t in p.targets}
        linked |= {t.lower() for g in self.goals for t in g["links"]}
        clashes, unused = {}, {}
        for n, ps in sorted(claims.items()):
            if len(ps) > 1:
                into = clashes if len(stems.get(n, [])) > 1 or n in linked else unused
                into[n] = sorted(ps, key=lambda p: p.rel)
        return clashes, unused

    def resolve(self, target):
        return self.names.get(target.strip().lower())

    def _resolve(self):
        edges, broken, gaps, faded = set(), [], [], []
        known_gaps = set().union(*(p.gap_targets for p in self.pages))
        for p in self.pages:
            if p.type == "log":
                continue  # the log names pages as history, not as connections
            for target in p.targets:
                dest = self.resolve(target)
                if dest is not None:
                    if dest is not p:
                        edges.add((p, dest))
                elif target.lower() in known_gaps:
                    gaps.append((p, target))
                elif target.lower() in self.dormant_names:
                    faded.append((p, target))
                else:
                    broken.append((p, target))
        return edges, broken, gaps, faded

    def _adjacency(self):
        """({page: the pages it links to}, {page: the pages linking to it}), from the edges, once.

        Asking what one page links, or what links it, is then a lookup, not a pass over every edge.
        """
        out, into = {p: set() for p in self.pages}, {p: set() for p in self.pages}
        for a, b in self.edges:
            out[a].add(b)
            into[b].add(a)
        return {p: frozenset(s) for p, s in out.items()}, {p: frozenset(s) for p, s in into.items()}

    def schema_problems(self):
        """(page, problems) for every page breaking the contract, however it was written."""
        vocabulary = tag_vocabulary(self.root)
        found = ((p, schema_problems(p.text, vocabulary, page_type=p.type if p.type == "project" else None,
                                     stem=p.stem, rel=p.rel))
                 for p in self.pages)
        return [(p, probs) for p, probs in found if probs]

    @property
    def knowledge(self):
        """Pages that are graph nodes: everything except index, log and metrics."""
        return [p for p in self.pages if not p.is_system]

    def of_type(self, kind):
        return [p for p in self.pages if p.type == kind]
