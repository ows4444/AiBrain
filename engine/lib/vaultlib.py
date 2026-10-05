"""Shared brain model for the scripts and hooks. No dependencies.

One place decides what counts as a page, how frontmatter is read, how a
[[wikilink]] resolves, and how recall, consolidation and decay are measured,
so every script reports the same numbers. The parts live in their own modules:

    vault_model      constants, the field registry, parsing, Page
    vault_events     the log, parsed once into typed events
    vault_graph      links, orphans, components, hubs, bridges, clusters, near-duplicates
    vault_memory     recall strength, the sleep queue, evidence, confidence, decay, calibration
    vault_purpose    goals, projects and intentions, and what they keep in use
    vault_retrieval  search, co-recall weights, spreading activation, link suggestions

Everything is importable from here, so callers only ever import vaultlib.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_events import Event, is_rehearsal_miss, is_rehearsal_pass, read_events  # noqa: E402,F401
from vault_graph import GraphMixin  # noqa: E402
from vault_memory import MemoryMixin  # noqa: E402
from vault_model import *  # noqa: E402,F401,F403
from vault_model import (DORMANT_DIR, MEMORY_DIRS, PROJECTS_DIR, Page, as_list, owner_goals,  # noqa: E402
                         parse_frontmatter, schema_problems, tag_vocabulary)
from vault_purpose import PurposeMixin  # noqa: E402
from vault_retrieval import RetrievalMixin  # noqa: E402


class Vault(GraphMixin, MemoryMixin, PurposeMixin, RetrievalMixin):
    def __init__(self, root, today=None):
        self.root = os.path.abspath(root)
        self.today = today or datetime.date.today()
        self.pages = list(self._load())
        self.names = self._build_names()
        self.dormant_names = self._dormant_names()
        self.edges, self.broken, self.gaps, self.faded = self._resolve()
        self.goals = owner_goals(self.root)
        self.events = read_events(self.root)
        self.recall_dates = self._recalls()
        self.rehearsals = self._rehearsals()
        self.recall_count = {p: len(d) for p, d in self.recall_dates.items()}
        self.last_recall = {p: d[-1] for p, d in self.recall_dates.items()}

    def _load(self):
        for top in MEMORY_DIRS:
            for dirpath, dirnames, filenames in os.walk(os.path.join(self.root, top)):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                for name in sorted(filenames):
                    if name.endswith(".md") and name != "README.md":
                        path = os.path.join(dirpath, name)
                        with open(path, encoding="utf-8", errors="replace") as fh:
                            yield Page(path, os.path.relpath(path, self.root), fh.read())
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

    def _dormant_names(self):
        """Every name a page in dormant/ answers to: file name, title, aliases."""
        names = set()
        for dirpath, _, filenames in os.walk(os.path.join(self.root, DORMANT_DIR)):
            for name in filenames:
                if name.endswith(".md") and name != "README.md":
                    with open(os.path.join(dirpath, name), encoding="utf-8", errors="replace") as fh:
                        fields = parse_frontmatter(fh.read())[0] or {}
                    names |= {n.lower() for n in [name[:-3], fields.get("title"), *as_list(fields.get("aliases"))]
                              if isinstance(n, str) and n}
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
