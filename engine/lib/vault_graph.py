"""The link graph: edges, orphans, components, hubs, bridges, clusters, typed links.

Mixed into vaultlib.Vault; relies on its pages, edges and resolve().
"""
from itertools import combinations

from vault_model import (BRIDGES_EXACT_UP_TO, BRIDGES_SAMPLE, HUB_FACTOR, HUB_MIN, LINKED_TO_TYPES, NEAR_DUPLICATE,
                         RELATIONS, SCHEMA_MIN, as_list, tokens)

# Pages that can be the same idea twice. Episodes are records of separate inputs,
# decisions separate choices: two of those that look alike are not a merge.
MERGEABLE_TYPES = ("concept", "entity", "insight")


class GraphMixin:
    def knowledge_edges(self):
        # Links from the index would make every listed page look connected,
        # so system pages are left out of every graph metric. Computed once per Vault.
        if "_knowledge_edges" not in self.__dict__:
            self._knowledge_edges = frozenset((a, b) for a, b in self.edges if not a.is_system and not b.is_system)
        return self._knowledge_edges

    def inbound(self):
        return {p: sum(not a.is_system for a in self.in_links[p]) for p in self.knowledge}

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
        """Undirected adjacency of the knowledge graph, with a stable node order."""
        adj = {p: set() for p in sorted(self.knowledge, key=lambda p: p.rel)}
        for a, b in self.knowledge_edges():
            adj[a].add(b)
            adj[b].add(a)
        return adj

    def hubs(self):
        """Pages whose inbound degree is at least 5 and three times the average: split candidates."""
        inbound = self.inbound()
        if not inbound:
            return []
        bar = max(HUB_MIN, HUB_FACTOR * sum(inbound.values()) / len(inbound))
        return sorted((p for p, n in inbound.items() if n >= bar), key=lambda p: -inbound[p])

    def betweenness_estimated(self, exact_up_to=BRIDGES_EXACT_UP_TO):
        return len(self.knowledge) > exact_up_to

    def betweenness(self, exact_up_to=BRIDGES_EXACT_UP_TO, sample=BRIDGES_SAMPLE):
        """Brandes betweenness on the undirected graph, normalised to 0..1.

        Exact up to `exact_up_to` pages; above that, estimated from `sample`
        evenly spaced starting pages and scaled up (see betweenness_estimated).
        """
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

    def typed_edges(self):
        """(source, relation, target) for every typed link that resolves. Computed once per Vault."""
        if "_typed_edges" not in self.__dict__:
            out, against = set(), {}
            for p in self.knowledge:
                for rel, target in p.relations:
                    dest = self.resolve(target)
                    if dest is not None and dest is not p:
                        out.add((p, rel, dest))
                        if rel == "contradicts":
                            against.setdefault(dest, set()).add(p)
            self._typed_edges, self._contradicted = frozenset(out), against
        return self._typed_edges

    def contradicted_by(self, page):
        """The pages whose typed link says they contradict this one: none, for most pages."""
        self.typed_edges()
        return self._contradicted.get(page, frozenset())

    def near_duplicates(self, threshold=NEAR_DUPLICATE):
        """(a, b, score, why) for same-type pages that may be one idea twice: merge candidates.

        Name overlap: Jaccard of the words in title and aliases. Neighbour
        overlap: Jaccard of the pages each links with, counted only when they
        share three or more. Only pairs sharing a name word or a neighbour are
        compared, so this stays fast on a large brain. Report only: /maintain merges.
        """
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

    def schema_candidates(self, min_size=SCHEMA_MIN):
        """Clusters with at least `min_size` concepts that no insight yet frames: each wants a schema page.

        An insight frames a cluster when it links to half or more of its concepts.
        Sleep proposes an insight tagged `schema` for each; nothing is written here.
        """
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
        tagged = lambda tag: sorted((p for p in self.knowledge if tag in as_list(p.fields.get("tags"))),
                                    key=lambda p: p.rel)
        contradicts = sorted(((a, b) for a, rel, b in self.typed_edges() if rel == "contradicts"),
                             key=lambda e: (e[0].rel, e[1].rel))
        return {"disputed": tagged("disputed"), "contradicts": contradicts, "revisit": tagged("to-revisit")}
