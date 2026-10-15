"""The link graph: edges, orphans, components, hubs, bridges, clusters, typed links, and what its numbers say.

Mixed into vaultlib.Vault; relies on its pages, edges, tuning, resolve() and kept().
What is worked out from the links alone is kept for the life of the Vault (kept): the
edges, the adjacency, the inbound counts. One view of the graph asks for them many times.
"""
from itertools import combinations

from vault_model import LINKED_TO_TYPES, RELATIONS, as_list, tokens
from vault_tuning import Tuning

# What vaultlib hands on to the commands. The rest is for the parts, which import it from here.
__all__ = ["GraphMixin", "verdicts"]

# Pages that can be the same idea twice. Episodes are records of separate inputs,
# decisions separate choices: two of those that look alike are not a merge.
MERGEABLE_TYPES = ("concept", "entity", "insight")


def verdicts(orphan_rate, avg_degree, main_share, pages, tuning=None):
    """One plain verdict per health metric; quiet until there is enough graph to judge.

    `tuning` is the brain's thresholds (Vault.tuning); without it, the defaults.
    """
    t = tuning or Tuning()
    if pages < 10:
        return {"overall": f"too small to judge ({pages} pages; read the numbers after about 10)"}
    orphan = ("healthy" if orphan_rate < t.orphan_healthy else
              "ingest is not linking: check the ingest skill" if orphan_rate > t.orphan_broken else "watch")
    degree = ("barely connected: retrieval cannot beat search" if avg_degree < t.degree_weak else
              "check for decorative links" if avg_degree > t.degree_decorative else
              "working range" if t.degree_low <= avg_degree <= t.degree_high else "acceptable")
    main = ("one main component" if main_share >= t.main_component_min else
            "fragmented: answers will be silently incomplete")
    return {"orphan_rate": orphan, "avg_degree": degree, "components": main}


class GraphMixin:
    def knowledge_edges(self):
        # Links from the index would make every listed page look connected,
        # so system pages are left out of every graph metric. Computed once per Vault.
        return self.kept("knowledge_edges", lambda: frozenset(
            (a, b) for a, b in self.edges if not a.is_system and not b.is_system))

    def inbound(self):
        """{page: how many knowledge pages link to it}. Counted once per Vault: the table is for reading."""
        return self.kept("inbound", lambda: {p: sum(not a.is_system for a in self.in_links[p])
                                             for p in self.knowledge})

    def linked_to(self):
        """Pages something should link to: the denominator of the orphan rate."""
        return [p for p in self.knowledge if p.type in LINKED_TO_TYPES and not p.generated
                and not (p.type == "episode" and not p.consolidated)]

    def orphans(self):
        inbound = self.inbound()
        return [p for p in self.linked_to() if inbound[p] == 0]

    def components(self):
        """Connected components of the undirected knowledge graph, largest first."""
        parent = {p: p for p in self.knowledge}

        def find(p):
            while parent[p] is not p:
                parent[p] = parent[parent[p]]
                p = parent[p]
            return p

        for a, b in self.knowledge_edges():
            parent[find(a)] = find(b)
        groups = {}
        for p in self.knowledge:
            groups.setdefault(find(p), []).append(p)
        return sorted(groups.values(), key=len, reverse=True)

    def neighbours(self):
        """Undirected adjacency of the knowledge graph, with a stable node order.

        Built once per Vault: betweenness, cut points, clusters, near-duplicates and link suggestions all
        read it, and one view of the graph asks for them all. The table is for reading, and each page's
        neighbours are a frozenset; a caller that needs another set makes it (`adj[a] - {b}`).
        """
        def build():
            adj = {p: set() for p in sorted(self.knowledge, key=lambda p: p.rel)}
            for a, b in self.knowledge_edges():
                adj[a].add(b)
                adj[b].add(a)
            return {p: frozenset(around) for p, around in adj.items()}
        return self.kept("neighbours", build)

    def hubs(self):
        """Pages whose inbound degree is at least hub_min (5) and hub_factor (3) times the average: split candidates."""
        inbound = self.inbound()
        if not inbound:
            return []
        bar = max(self.tuning.hub_min, self.tuning.hub_factor * sum(inbound.values()) / len(inbound))
        return sorted((p for p, n in inbound.items() if n >= bar), key=lambda p: -inbound[p])

    def betweenness_estimated(self, exact_up_to=None):
        return len(self.knowledge) > (self.tuning.bridges_exact_up_to if exact_up_to is None else exact_up_to)

    def betweenness(self, exact_up_to=None, sample=None):
        """Brandes betweenness on the undirected graph, normalised to 0..1.

        Exact up to `exact_up_to` pages; above that, estimated from `sample`
        evenly spaced starting pages and scaled up (see betweenness_estimated).
        Both are the brain's (bridges_exact_up_to, bridges_sample) unless given.
        """
        exact_up_to = self.tuning.bridges_exact_up_to if exact_up_to is None else exact_up_to
        sample = self.tuning.bridges_sample if sample is None else sample
        adj = self.neighbours()
        score = dict.fromkeys(adj, 0.0)
        nodes = list(adj)
        sources = nodes
        if len(nodes) > exact_up_to and sample < len(nodes):
            sources = [nodes[i * len(nodes) // sample] for i in range(sample)]
        for s in sources:
            stack, preds = [], {v: [] for v in adj}
            sigma, dist = dict.fromkeys(adj, 0), dict.fromkeys(adj, -1)
            sigma[s], dist[s] = 1, 0
            queue = [s]
            for v in queue:
                stack.append(v)
                for w in sorted(adj[v], key=lambda p: p.rel):
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        preds[w].append(v)
            delta = dict.fromkeys(adj, 0.0)
            for w in reversed(stack):
                for v in preds[w]:
                    delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
                if w is not s:
                    score[w] += delta[w]
        n = len(adj)
        norm = (n - 1) * (n - 2) if n > 2 else 1  # undirected: each pair counted twice
        scale = n / len(sources) if sources else 1
        return {p: v * scale / norm for p, v in score.items()}

    def cut_points(self):
        """Pages whose removal disconnects the graph (articulation points)."""
        adj = self.neighbours()
        order, low, cuts, counter = {}, {}, set(), [0]
        for root in adj:
            if root in order:
                continue
            order[root] = low[root] = counter[0]
            counter[0] += 1
            children = 0
            stack = [(root, None, iter(sorted(adj[root], key=lambda p: p.rel)))]
            while stack:
                v, parent, it = stack[-1]
                w = next(it, None)
                if w is None:
                    stack.pop()
                    if parent is not None:
                        low[parent] = min(low[parent], low[v])
                        if parent is not root and low[v] >= order[parent]:
                            cuts.add(parent)
                elif w is parent:
                    pass
                elif w in order:
                    low[v] = min(low[v], order[w])
                else:
                    order[w] = low[w] = counter[0]
                    counter[0] += 1
                    if v is root:
                        children += 1
                    stack.append((w, v, iter(sorted(adj[w], key=lambda p: p.rel))))
            if children > 1:
                cuts.add(root)
        return sorted(cuts, key=lambda p: p.rel)

    def clusters(self, rounds=50):
        """Topic clusters by deterministic label propagation, largest first; singletons dropped."""
        adj = self.neighbours()
        label = {p: i for i, p in enumerate(adj)}
        for _ in range(rounds):
            changed = False
            for p in adj:
                if not adj[p]:
                    continue
                counts = {}
                for q in adj[p]:
                    counts[label[q]] = counts.get(label[q], 0) + 1
                best = max(counts.values())
                new = min(lab for lab, c in counts.items() if c == best)
                if new != label[p] and counts.get(label[p], 0) < best:
                    label[p], changed = new, True
            if not changed:
                break
        groups = {}
        for p, lab in label.items():
            groups.setdefault(lab, []).append(p)
        degree = {p: len(adj[p]) for p in adj}
        out = [sorted(g, key=lambda p: (-degree[p], p.rel)) for g in groups.values() if len(g) > 1]
        return sorted(out, key=lambda g: (-len(g), g[0].rel))

    def tag_counts(self):
        counts = {}
        for p in self.knowledge:
            for t in as_list(p.fields.get("tags")):
                counts[t] = counts.get(t, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def _typed(self):
        """(every typed link that resolves, {page: the pages that say they contradict it}), read once per Vault."""
        def read():
            out, against = set(), {}
            for p in self.knowledge:
                for rel, target in p.relations:
                    dest = self.resolve(target)
                    if dest is not None and dest is not p:
                        out.add((p, rel, dest))
                        if rel == "contradicts":
                            against.setdefault(dest, set()).add(p)
            return frozenset(out), against
        return self.kept("typed_edges", read)

    def typed_edges(self):
        """(source, relation, target) for every typed link that resolves. Computed once per Vault."""
        return self._typed()[0]

    def contradicted_by(self, page):
        """The pages whose typed link says they contradict this one: none, for most pages."""
        return self._typed()[1].get(page, frozenset())

    def near_duplicates(self, threshold=None):
        """(a, b, score, why) for same-type pages that may be one idea twice: merge candidates.

        Name overlap: Jaccard of the words in title and aliases. Neighbour
        overlap: Jaccard of the pages each links with, counted only when they
        share three or more. Only pairs sharing a name word or a neighbour are
        compared, so this stays fast on a large brain. Report only: /maintain merges.
        `threshold` is the brain's near_duplicate unless given.
        """
        threshold = self.tuning.near_duplicate if threshold is None else threshold
        pages = [p for p in self.knowledge if p.type in MERGEABLE_TYPES]
        names = {p: set(tokens(" ".join([p.title, *p.aliases]))) for p in pages}
        adj = self.neighbours()
        pairs = set()
        by_word = {}
        for p in pages:
            for w in names[p]:
                by_word.setdefault(w, []).append(p)
        for group in list(by_word.values()) + [[q for q in adj[p] if q in names] for p in adj]:
            for a, b in combinations(sorted(set(group), key=lambda p: p.rel), 2):
                if a.type == b.type:
                    pairs.add((a, b))
        out = []
        for a, b in pairs:
            na, nb = names[a], names[b]
            name = len(na & nb) / len(na | nb) if na | nb else 0.0
            around_a, around_b = adj[a] - {b}, adj[b] - {a}
            shared = around_a & around_b
            nbr = len(shared) / len(around_a | around_b) if len(shared) >= 3 else 0.0
            if max(name, nbr) >= threshold:
                why = f"names {name:.0%} alike" if name >= nbr else f"{len(shared)} neighbours shared ({nbr:.0%})"
                out.append((a, b, round(max(name, nbr), 2), why))
        return sorted(out, key=lambda t: (-t[2], t[0].rel, t[1].rel))

    def schema_candidates(self, min_size=None):
        """Clusters with at least `min_size` concepts that no insight yet frames: each wants a schema page.

        An insight frames a cluster when it links to half or more of its concepts.
        Sleep proposes an insight tagged `schema` for each; nothing is written here.
        `min_size` is the brain's schema_min unless given.
        """
        min_size = self.tuning.schema_min if min_size is None else min_size
        insights = [self.out_links[i] for i in self.of_type("insight")]
        out = []
        for cluster in self.clusters():
            concepts = [p for p in cluster if p.type == "concept"]
            if len(concepts) >= min_size and not any(2 * len(links & set(concepts)) >= len(concepts)
                                                     for links in insights):
                out.append(concepts)
        return out

    def relation_problems(self):
        """(page, relation) for typed links outside the vocabulary in CLAUDE.md > Rules."""
        return [(p, rel) for p in self.knowledge for rel, _ in p.relations if rel not in RELATIONS]

    def open_items(self):
        """What is unresolved: disputed pages, contradicts links, pages tagged to-revisit."""
        tagged = lambda tag: sorted((p for p in self.knowledge if tag in as_list(p.fields.get("tags"))),  # noqa: E731
                                    key=lambda p: p.rel)
        contradicts = sorted(((a, b) for a, rel, b in self.typed_edges() if rel == "contradicts"),
                             key=lambda e: (e[0].rel, e[1].rel))
        return {"disputed": tagged("disputed"), "contradicts": contradicts, "revisit": tagged("to-revisit")}
