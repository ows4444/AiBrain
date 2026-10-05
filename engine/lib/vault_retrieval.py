"""Retrieval: keyword search, links that strengthen with use, and spreading activation.

Mixed into vaultlib.Vault; relies on its pages, events, edges, resolve(),
typed_edges(), strength(), confidence() and links_from().

    search    BM25 over title (x3), aliases (x2) and body; dormant/ on request
    recall    search hits seed an activation that spreads along links, so a
              page the question never names, one or two links from what it
              does name, can still come back (associative recall)
    weights   every recall line naming two pages together strengthens their
              pair, fading with age (Hebbian; nothing is stored, the log is replayed)
    links     pairs that are not linked but probably should be (next links)

Read-only: none of this writes the log or a page. A skill that answers from
the results still logs its own recall line, naming the pages that contributed.
Search keeps each page's term frequencies in a disposable SQLite cache
(vault_cache, .cache/search.sqlite); results are the same with or without it.
"""
import math
import os
from collections import Counter

from vault_cache import TermCache
from vault_events import is_rehearsal_pass
from vault_model import (DORMANT_DIR, HEBBIAN_HALF_LIFE, PROJECT_BOOST, SEED_LIMIT, SPREAD_DECAY, SPREAD_HOPS,
                         STALE_DAYS, Page, as_list, prose, tokens)

FIELD_WEIGHTS = (("title", 3.0), ("aliases", 2.0), ("body", 1.0))
BM25_K1, BM25_B = 1.2, 0.75
# How much a typed link carries activation, against 1.0 for a plain link. A
# contradiction is followed like a plain link (the other side must be seen),
# and the result is flagged.
RELATION_WEIGHT = {"supports": 1.2, "extends": 1.2, "part-of": 1.1, "applies": 1.1, "contradicts": 1.0}
# A pair only ever recalled together, with no link, still associates, but weakly.
UNLINKED_ASSOCIATION = 0.5
# Pages a project links to join the seeds this strongly when they were not hits.
PROJECT_SEED = 0.2
# How much the owner's rehearsal strength (0-7) lifts a page at the end.
STRENGTH_LIFT = 0.05


def field_text(page, field):
    if field == "title":
        return page.title
    if field == "aliases":
        return " ".join(page.aliases)
    return prose(page.body)


class RetrievalMixin:
    # -- corpus -------------------------------------------------------------

    @property
    def dormant_pages(self):
        """Pages in dormant/: not part of the graph, but searchable on request."""
        if "_dormant_pages" not in self.__dict__:
            pages = []
            for dirpath, dirnames, filenames in os.walk(os.path.join(self.root, DORMANT_DIR)):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                for name in sorted(filenames):
                    if name.endswith(".md") and name != "README.md":
                        path = os.path.join(dirpath, name)
                        with open(path, encoding="utf-8", errors="replace") as fh:
                            pages.append(Page(path, os.path.relpath(path, self.root), fh.read()))
            self._dormant_pages = pages
        return self._dormant_pages

    def _term_frequencies(self, page):
        cache = self.__dict__.setdefault("_tf", {})
        if page not in cache:
            tf = Counter()
            for field, weight in FIELD_WEIGHTS:
                for t in tokens(field_text(page, field)):
                    tf[t] += weight
            cache[page] = tf
        return cache[page]

    def _term_frequencies_many(self, pages):
        """{page: tf} for many pages at once, through the SQLite cache (vault_cache) when it opens."""
        memo = self.__dict__.setdefault("_tf", {})
        missing = [p for p in pages if p not in memo]
        if missing:
            if "_term_cache" not in self.__dict__:
                self._term_cache = TermCache(self.root)
            memo.update(self._term_cache.get_many(missing, self._term_frequencies))
        return {p: memo[p] for p in pages}

    # -- keyword search -----------------------------------------------------

    def search(self, query, types=None, dormant=False, limit=10):
        """[(page, score)] by BM25 over title, aliases and body, best first; [] when no word matches.

        `types` limits the page types; `dormant` adds the pages in dormant/.
        System pages (index, log, ...) and projects are never results.
        """
        pool = [p for p in self.knowledge if p.type != "project"]
        if dormant:
            pool += self.dormant_pages
        if types:
            pool = [p for p in pool if p.type in types]
        terms = set(tokens(query))
        if not terms or not pool:
            return []
        docs = self._term_frequencies_many(pool)
        lengths = {p: sum(tf.values()) for p, tf in docs.items()}
        average = sum(lengths.values()) / len(docs) or 1.0
        df = Counter(t for tf in docs.values() for t in terms if t in tf)
        n = len(docs)
        scores = {}
        for p, tf in docs.items():
            score = 0.0
            for t in terms:
                f = tf.get(t)
                if f:
                    idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                    score += idf * f * (BM25_K1 + 1) / (f + BM25_K1 * (1 - BM25_B + BM25_B * lengths[p] / average))
            if score > 0:
                scores[p] = score
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0].rel))[:limit]

    # -- Hebbian weights ----------------------------------------------------

    def edge_weights(self, half_life=HEBBIAN_HALF_LIFE):
        """{frozenset({a, b}): weight} from recall lines naming both pages, each halving every `half_life` days.

        Rehearsal lines are left out: quizzing two pages in one session is the
        owner being tested, not the two ideas being used together.
        """
        key = ("_hebbian", half_life)
        if key not in self.__dict__:
            weights = {}
            for e in self.events:
                if e.op != "recall" or not e.day or not e.arrow or is_rehearsal_pass(e):
                    continue
                pages = sorted({self.resolve(t) for t in e.targets} - {None}, key=lambda p: p.rel)
                pages = [p for p in pages if not p.is_system]
                w = 0.5 ** (max(0, (self.today - e.day).days) / half_life)
                for i, a in enumerate(pages):
                    for b in pages[i + 1:]:
                        pair = frozenset((a, b))
                        weights[pair] = weights.get(pair, 0.0) + w
            self.__dict__[key] = weights
        return self.__dict__[key]

    def association_graph(self):
        """{page: {neighbour: weight}}: links (typed ones weighted), strengthened by co-recall."""
        if "_associations" not in self.__dict__:
            graph = {p: {} for p in self.knowledge}
            relation = {}
            for a, rel, b in self.typed_edges():
                pair = frozenset((a, b))
                relation[pair] = max(relation.get(pair, 1.0), RELATION_WEIGHT.get(rel, 1.0))
            hebb = self.edge_weights()
            for a, b in self.knowledge_edges():
                pair = frozenset((a, b))
                w = relation.get(pair, 1.0) * (1 + math.log1p(hebb.get(pair, 0.0)))
                graph[a][b] = max(graph[a].get(b, 0.0), w)
                graph[b][a] = max(graph[b].get(a, 0.0), w)
            for pair, h in hebb.items():
                a, b = tuple(pair)
                w = UNLINKED_ASSOCIATION * math.log1p(h)
                # A co-recall old enough to decay to 0.0 associates nothing; a zero
                # weight would also be a page's strongest link and divide by zero.
                if w > 0 and a in graph and b in graph and b not in graph[a]:
                    graph[a][b] = graph[b][a] = w
            self._associations = graph
        return self._associations

    # -- spreading activation -----------------------------------------------

    def activate(self, seeds, hops=SPREAD_HOPS, decay=SPREAD_DECAY):
        """({page: activation}, {page: (seed, hop)}) after spreading `hops` times from `seeds` ({page: score}).

        Each hop passes on `decay` of a page's new activation, split by link
        weight relative to its strongest link and damped by the square root of
        its degree, so a hub does not flood every answer with its neighbours.
        Every weight in the association graph is positive, so every gain is.
        """
        graph = self.association_graph()
        activation = dict(seeds)
        via = {p: (p, 0) for p in seeds}
        frontier = dict(seeds)
        for hop in range(1, hops + 1):
            spread = {}
            for a, x in frontier.items():
                links = graph.get(a, {})
                if not links:
                    continue
                strongest, damp = max(links.values()), math.sqrt(len(links))
                for b, w in links.items():
                    spread[b] = spread.get(b, 0.0) + x * decay * (w / strongest) / damp
                    via.setdefault(b, (via[a][0], hop))
            for b, gain in spread.items():
                activation[b] = activation.get(b, 0.0) + gain
            frontier = spread
        return activation, via

    def recall(self, query, project=None, limit=10, hops=SPREAD_HOPS, dormant=False):
        """Ranked pages for a question: [{page, score, seed, hop, from, confidence, flags}].

        Search hits seed the spread (scaled so the best is 1.0). With `project`
        (a prefrontal/ folder name), its pages count PROJECT_BOOST times more
        when they are hits, and join as weak seeds when they are not: what is
        recalled depends on what the owner is working on.
        flags: disputed, contradicted, stale (a concept or insight not updated in
        STALE_DAYS: ask whether it still holds), generated (/explore), dormant.
        """
        hits = self.search(query, limit=SEED_LIMIT, dormant=dormant)
        seeds = {}
        if hits:
            top = hits[0][1]
            seeds = {p: s / top for p, s in hits}
        focus = self.resolve(project) if project else None
        if project and (focus is None or focus.type != "project"):
            raise ValueError(f"no project named {project} in prefrontal/")
        if focus and seeds:
            for p in self.links_from(focus):
                if p.is_system:
                    continue
                seeds[p] = seeds[p] * PROJECT_BOOST if p in seeds else PROJECT_SEED
        if not seeds:
            return []
        activation, via = self.activate(seeds, hops=hops)
        contradicted = {b for _, rel, b in self.typed_edges() if rel == "contradicts"}
        rows = []
        for p, a in activation.items():
            score = a * (1 + STRENGTH_LIFT * self.strength(p))
            seed, hop = via.get(p, (p, 0))
            flags = [f for f, on in (
                ("disputed", "disputed" in as_list(p.fields.get("tags"))),
                ("contradicted", p in contradicted),
                ("stale", p.type in ("concept", "insight") and p.updated
                 and (self.today - p.updated).days > STALE_DAYS),
                ("generated", p.generated),
                ("dormant", p.rel.startswith(DORMANT_DIR + os.sep) or p.rel.startswith(DORMANT_DIR + "/")),
            ) if on]
            rows.append({"page": p, "score": round(score, 4), "seed": hop == 0, "hop": hop,
                         "from": seed, "flags": flags})
        rows.sort(key=lambda r: (-r["score"], r["page"].rel))
        rows = rows[:limit]
        for r in rows:
            r["confidence"] = None if "dormant" in r["flags"] else self.confidence(r["page"])
        return rows

    # -- next links ---------------------------------------------------------

    def link_suggestions(self, limit=10):
        """[(a, b, score, why)]: unlinked concept/entity/insight pairs that probably belong together.

        Adamic-Adar over shared neighbours (a shared rare neighbour counts more
        than a shared hub), plus the co-recall weight of the pair. Proposals for
        /sleep stage 2; a link the owner would not agree with is noise.
        """
        kinds = ("concept", "entity", "insight")
        adj = self.neighbours()
        hebb = self.edge_weights()
        scores = {}
        for z, around in adj.items():
            if len(around) < 2:
                continue
            gain = 1 / math.log(len(around))
            members = sorted((p for p in around if p.type in kinds), key=lambda p: p.rel)
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    if b not in adj[a]:
                        scores[(a, b)] = scores.get((a, b), 0.0) + gain
        for pair, h in hebb.items():
            a, b = sorted(pair, key=lambda p: p.rel)
            if a.type in kinds and b.type in kinds and b not in adj.get(a, ()):
                scores[(a, b)] = scores.get((a, b), 0.0) + h
        out = []
        for (a, b), s in scores.items():
            shared = len(adj[a] & adj[b])
            together = hebb.get(frozenset((a, b)), 0.0)
            why = ", ".join(x for x in (f"{shared} neighbours shared" if shared else "",
                                        f"recalled together ({together:.1f})" if together else "") if x)
            out.append((a, b, round(s, 3), why))
        return sorted(out, key=lambda t: (-t[2], t[0].rel, t[1].rel))[:limit]

    def at_hand(self, limit=5, recent=3):
        """Pages the next session will probably need: spread from the last `recent` recall lines and live projects."""
        seeds = {}
        recalls = [e for e in self.events if e.op == "recall" and e.arrow and not is_rehearsal_pass(e)][-recent:]
        for e in recalls:
            for t in e.targets:
                p = self.resolve(t)
                if p is not None and not p.is_system:
                    seeds[p] = 1.0
        for proj in self.active_projects():
            for p in self.links_from(proj):
                if not p.is_system:
                    seeds.setdefault(p, 0.5)
        if not seeds:
            return []
        activation, _ = self.activate(seeds, hops=1)
        return [p for p, _ in sorted(activation.items(), key=lambda kv: (-kv[1], kv[0].rel))[:limit]]
