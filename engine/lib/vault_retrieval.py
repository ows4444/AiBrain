"""Retrieval: keyword search, links that strengthen with use, and spreading activation.

Mixed into vaultlib.Vault; relies on its pages, events, edges, tuning, resolve(),
typed_edges(), contradicted_by(), strength(), confidence() and links_from().
Every number here is the brain's own (vault_tuning): the defaults are named below.

    search    BM25 over title (x3), aliases (x2), the questions a page says it
              answers (x2), body and summary (x0.5); dormant/ on request
    recall    search hits seed an activation that spreads along links, so a
              page the question never names, one or two links from what it
              does name, can still come back (associative recall)
    weights   every recall line naming two pages together strengthens their
              pair, fading with age (Hebbian; nothing is stored, the log is replayed)
    use       the recall lines naming a page lift its own score, up to a cap; off
              unless the brain sets use_lift, since no log has shown yet that it helps
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
from vault_model import DORMANT_DIR, QUESTION, RELATIONS, SECTION, Page, as_list, prose, same_idea, tokens


def field_text(page, field):
    """The text of one searched part of a page: a field named by a `weight_<field>` threshold."""
    if field == "title":
        return page.title
    if field == "aliases":
        return " ".join(page.aliases)
    if field == "answers":
        return " ".join(page.answers)
    if field == "summary":
        return page.summary or ""
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
            for field, weight in self.tuning.field_weights:
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
                self._term_cache = TermCache(self.root, self.tuning.cache_key)
            memo.update(self._term_cache.get_many(missing, self._term_frequencies))
        return {p: memo[p] for p in pages}

    # -- keyword search -----------------------------------------------------

    def _searchable(self, types=None, dormant=False):
        """({page: tf}, {page: its length}) for the pages a search may return.

        Kept for the life of the Vault, which reads its pages once: a second search, the
        coverage of its best hit and a recall of the same question do not weigh every page again.
        """
        kept = self.__dict__.setdefault("_searchable_kept", {})
        key = (tuple(types) if types else None, dormant)
        if key not in kept:
            pool = [p for p in self.knowledge if p.type != "project"]
            if dormant:
                pool += self.dormant_pages
            if types:
                pool = [p for p in pool if p.type in types]
            docs = self._term_frequencies_many(pool) if pool else {}
            kept[key] = docs, {p: sum(tf.values()) for p, tf in docs.items()}
        return kept[key]

    def coverage(self, query, page, dormant=False):
        """How much of the question `page` holds: the share of its words found there, each weighted by its rarity.

        A word no page has weighs most, so a question mostly about something
        the brain never mentions scores low however well one common word matches.
        """
        terms = set(tokens(query))
        docs, _ = self._searchable(dormant=dormant)
        if not terms or page not in docs:
            return 0.0
        n = len(docs)
        df = Counter(t for tf in docs.values() for t in terms if t in tf)
        idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in terms}
        return sum(w for t, w in idf.items() if t in docs[page]) / sum(idf.values())

    def search(self, query, types=None, dormant=False, limit=10):
        """[(page, score)] by BM25 over title, aliases, answers, body and summary, best first; [] when no word matches.

        `types` limits the page types; `dormant` adds the pages in dormant/.
        System pages (index, log, ...) and projects are never results.
        """
        terms = set(tokens(query))
        docs, lengths = self._searchable(types, dormant) if terms else ({}, {})
        if not docs:
            return []
        average = sum(lengths.values()) / len(docs) or 1.0
        df = Counter(t for tf in docs.values() for t in terms if t in tf)
        n = len(docs)
        k1, b = self.tuning.bm25_k1, self.tuning.bm25_b
        scores = {}
        for p, tf in docs.items():
            score = 0.0
            for t in terms:
                f = tf.get(t)
                if f:
                    idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                    score += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * lengths[p] / average))
            if score > 0:
                scores[p] = score
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0].rel))[:limit]

    # -- Hebbian weights ----------------------------------------------------

    def _pairs_recalled(self):
        """[(day, pairs)] for each event of the log: the pairs of pages a recall line names together, else ().

        Rehearsal lines are left out: quizzing two pages in one session is the owner being
        tested, not the two ideas being used together. Worked out once and shared with every
        copy as_of makes, as _event_pages is.
        """
        if "_pairs_recalled_kept" not in self.__dict__:
            out = []
            for e, named in zip(self.events, self._event_pages()):
                pairs = ()
                if e.op == "recall" and e.day and e.arrow and not is_rehearsal_pass(e):
                    pages = sorted(set(named) - {None}, key=lambda p: p.rel)
                    pages = [p for p in pages if not p.is_system]
                    pairs = tuple(frozenset((a, b)) for i, a in enumerate(pages) for b in pages[i + 1:])
                out.append((e.day, pairs))
            self._pairs_recalled_kept = out
        return self._pairs_recalled_kept

    def edge_weights(self, half_life=None):
        """{frozenset({a, b}): weight} from recall lines naming both pages, each halving every `half_life` days.

        `half_life` is the brain's hebbian_half_life unless given.
        """
        half_life = self.tuning.hebbian_half_life if half_life is None else half_life
        key = ("_hebbian", half_life)
        if key not in self.__dict__:
            weights = {}
            for _, (day, pairs) in zip(self.events, self._pairs_recalled()):
                if pairs:
                    w = 0.5 ** (max(0, (self.today - day).days) / half_life)
                    for pair in pairs:
                        weights[pair] = weights.get(pair, 0.0) + w
            self.__dict__[key] = weights
        return self.__dict__[key]

    def use_weights(self):
        """{page: weight} from the recall lines naming each page, each halving every hebbian_half_life days.

        What a page's own history of answering comes to. A rehearsal line is left out, as it
        is for pairs: it is the owner being tested, and strength() counts it. A page a line
        names twice was used once. What use teaches fades at one rate, for a pair and a page.
        """
        key = ("_use", self.tuning.hebbian_half_life)  # a tuple, as the pair weights are: as_of drops both
        if key not in self.__dict__:
            weights = {}
            for e, named in zip(self.events, self._event_pages()):
                if e.op == "recall" and e.day and e.arrow and not is_rehearsal_pass(e):
                    w = 0.5 ** (max(0, (self.today - e.day).days) / key[1])
                    for p in dict.fromkeys(named):
                        if p is not None and not p.is_system:
                            weights[p] = weights.get(p, 0.0) + w
            self.__dict__[key] = weights
        return self.__dict__[key]

    def lift_from_use(self, page):
        """The share of its score a page's own recalls add: use_lift once use_full of them stand, less before.

        0.0 while use_lift is 0, which it is unless the brain says otherwise: a page's recalls
        then keep it from fading and tie it to the pages it was recalled with, and no more.
        """
        t = self.tuning
        if not t.use_lift:
            return 0.0
        return t.use_lift * min(1.0, self.use_weights().get(page, 0.0) / t.use_full)

    def _link_weights(self):
        """{page: {neighbour: weight}} from the links alone: 1.0 for a plain one, more for a typed one.

        What the log teaches is laid over this (association_graph); the links themselves do not
        change with use, so this is worked out once and shared with every copy as_of makes.
        """
        if "_link_weights_kept" not in self.__dict__:
            graph = {p: {} for p in self.knowledge}
            # relation_<name> for each relation of the vocabulary; one outside it carries like a plain link
            carries = {rel: getattr(self.tuning, "relation_" + rel.replace("-", "_")) for rel in RELATIONS}
            relation = {}
            for a, rel, b in self.typed_edges():
                pair = frozenset((a, b))
                relation[pair] = max(relation.get(pair, 1.0), carries.get(rel, 1.0))
            for a, b in self.knowledge_edges():
                graph[a][b] = graph[b][a] = relation.get(frozenset((a, b)), 1.0)
            self._link_weights_kept = graph
        return self._link_weights_kept

    def association_graph(self):
        """{page: {neighbour: weight}}: links (typed ones weighted), strengthened by co-recall."""
        if "_associations" not in self.__dict__:
            graph = {p: dict(around) for p, around in self._link_weights().items()}
            for pair, h in self.edge_weights().items():
                a, b = tuple(pair)
                if b in graph.get(a, ()):  # linked: recalled together, the link carries more
                    graph[a][b] = graph[b][a] = graph[a][b] * (1 + math.log1p(h))
                else:
                    w = self.tuning.unlinked_association * math.log1p(h)
                    # A co-recall old enough to decay to 0.0 associates nothing; a zero
                    # weight would also be a page's strongest link and divide by zero.
                    if w > 0 and a in graph and b in graph:
                        graph[a][b] = graph[b][a] = w
            self._associations = graph
        return self._associations

    # -- spreading activation -----------------------------------------------

    def activate(self, seeds, hops=None, decay=None):
        """({page: activation}, {page: (seed, hop)}) after spreading `hops` times from `seeds` ({page: score}).

        Each hop passes on `decay` of a page's new activation, split by link
        weight relative to its strongest link and damped by the square root of
        its degree, so a hub does not flood every answer with its neighbours.
        Every weight in the association graph is positive, so every gain is.
        `hops` and `decay` are the brain's (spread_hops, spread_decay) unless given.
        """
        hops = self.tuning.spread_hops if hops is None else hops
        decay = self.tuning.spread_decay if decay is None else decay
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

    def best_sections(self, query, pages, dormant=False):
        """{page: {heading, line, end, bytes} or None}: the `## ` section of each page to read first for a question.

        The words that count are the question's that the page's own names (title, aliases) do
        not hold: a page named by the question is its subject and is read from the top, so it
        gets no section, and neither does a page none of whose sections holds such a word (one
        reached by a link). Among the rest, the section holding the rarest of those words wins,
        its heading included; the first one, when two hold as much. `line` and `end` are the
        lines of the file it spans, for a reader that opens a part of a file.
        """
        terms = set(tokens(query))
        docs, _ = self._searchable(dormant=dormant)
        n = len(docs)
        df = Counter(t for tf in docs.values() for t in terms if t in tf)
        idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in terms}
        out = {}
        for page in pages:
            wanted = terms - set(tokens(" ".join([page.title, *page.aliases])))
            best, top = None, 0.0
            for m in SECTION.finditer(page.body):
                held = set(tokens(m.group(1) + " " + prose(m.group(2))))
                weight = sum(idf[t] for t in wanted if t in held)
                if weight > top:
                    best, top = m, weight
            out[page] = None
            if best:
                text = best.group(0).rstrip()
                line = page.text[:len(page.text) - len(page.body) + best.start()].count("\n") + 1
                out[page] = {"heading": best.group(1), "line": line, "end": line + text.count("\n"),
                             "bytes": len(text.encode("utf-8"))}
        return out

    def recall(self, query, project=None, limit=10, hops=None, dormant=False, floor=0.0, abstain=False, also=()):
        """Ranked pages for a question: [{page, score, seed, hop, from, confidence, flags, against, section}].

        `floor` cuts rows scoring under that share of the best row; `abstain`
        returns nothing when the best search hit holds under min_coverage of
        the question. `brain recall` uses both (recall_floor) unless given --all.

        `also` is other wordings of the same question (the field's own terms,
        plainer words). Each wording is searched on its own and a page's
        scores are added up, the other wordings sharing one vote between
        them: the question as the owner asked it counts as much as all of
        them together. So a word every wording keeps counts most, and a page
        only one wording reaches still comes in. The best seed_limit of the
        sums seed one spread. Whether to abstain is judged on the question
        as it was asked: another wording can change which pages lead, never
        whether the brain covers the question.

        Search hits seed the spread (scaled so the best is 1.0). With `project`
        (a prefrontal/ folder name), its pages count project_boost times more
        when they are hits, and join as weak seeds when they are not: what is
        recalled depends on what the owner is working on. A page's score is
        the activation that reached it, lifted by each rehearsal level the
        owner holds (strength_lift) and, in a brain that sets use_lift, by
        its own recalls (lift_from_use).
        flags: disputed, contradicted, stale (a concept or insight not updated in
        stale_days: ask whether it still holds), generated (/explore), dormant.
        against: the pages whose typed link says they contradict this one, whether or
        not they are among the rows: an answer from a contradicted page reads both.
        section: the part of the page to read first, when one stands out (best_sections).
        """
        t = self.tuning
        wordings = [query, *also]
        asked = self.search(query, limit=1, dormant=dormant)
        if abstain and (not asked or self.coverage(query, asked[0][0], dormant=dormant) < t.min_coverage):
            return []
        summed = {}  # with no other wording: the question's own scores, as `search` gives them
        for wording, share in [(query, 1.0), *((other, 1 / len(also)) for other in also)]:
            for p, s in self.search(wording, limit=None, dormant=dormant):
                summed[p] = summed.get(p, 0.0) + s * share
        hits = sorted(summed.items(), key=lambda kv: (-kv[1], kv[0].rel))[:t.seed_limit]
        seeds = {p: s / hits[0][1] for p, s in hits}
        focus = self.resolve(project) if project else None
        if project and (focus is None or focus.type != "project"):
            raise ValueError(f"no project named {project} in prefrontal/")
        if focus and seeds:
            for p in self.links_from(focus):
                if p.is_system:
                    continue
                seeds[p] = seeds[p] * t.project_boost if p in seeds else t.project_seed
        if not seeds:
            return []
        activation, via = self.activate(seeds, hops=hops)
        rows = []
        for p, a in activation.items():
            score = a * (1 + t.strength_lift * self.strength(p) + self.lift_from_use(p))
            seed, hop = via.get(p, (p, 0))
            flags = [f for f, on in (
                ("disputed", "disputed" in as_list(p.fields.get("tags"))),
                ("contradicted", bool(self.contradicted_by(p))),
                ("stale", p.type in ("concept", "insight") and p.updated
                 and (self.today - p.updated).days > t.stale_days),
                ("generated", p.generated),
                ("dormant", p.rel.startswith(DORMANT_DIR + os.sep) or p.rel.startswith(DORMANT_DIR + "/")),
            ) if on]
            rows.append({"page": p, "score": round(score, 4), "seed": hop == 0, "hop": hop,
                         "from": seed, "flags": flags,
                         "against": sorted(self.contradicted_by(p), key=lambda q: q.rel)})
        rows.sort(key=lambda r: (-r["score"], r["page"].rel))
        rows = [r for r in rows if r["score"] >= floor * rows[0]["score"]][:limit]
        sections = self.best_sections(" ".join(wordings), [r["page"] for r in rows], dormant)
        for r in rows:
            r["confidence"] = None if "dormant" in r["flags"] else self.confidence(r["page"])
            r["section"] = sections[r["page"]]
        return rows

    def prompt_recall(self, prompt):
        """(rows, why) for a prompt nobody asked to recall on: [(page, summary)] or [] and the reason.

        Stricter than `recall`: a command, a short prompt, a prompt that is not
        a question, or one whose best page holds under prompt_coverage of its
        words gets nothing. Rows are cut to prompt_rows and prompt_chars.
        """
        t = self.tuning
        text = prompt.strip()
        if text.startswith(("/", "<")):
            return [], "command"
        if len(text.split()) < t.prompt_min_words:
            return [], "short"
        if not QUESTION.search(text):
            return [], "not a question"
        hits = self.search(text, limit=1)
        if not hits:
            return [], "no word matches"
        covered = self.coverage(text, hits[0][0])
        if covered < t.prompt_coverage:
            return [], f"weak match ({covered:.2f})"
        rows, used = [], 0
        for r in self.recall(text, limit=t.prompt_rows, floor=t.recall_floor, abstain=True):
            page = r["page"]
            line = f"{page.rel}: {page.summary or page.title}"
            if rows and used + len(line) > t.prompt_chars:
                break
            rows.append((page, line[:t.prompt_chars]))
            used += len(line)
        return rows, f"match ({covered:.2f})"

    # -- ideas held on episodes ---------------------------------------------

    def held_ideas(self, query, limit=None):
        """Candidates with no page yet that the question names: [{name, note, episodes, sources}], best first.

        An idea waits on its episode until a second source names it. Until
        then it is one line, and an answer about it can use that line, cite
        the episode and say it rests on one source, without opening the
        episode. Ideas raised only by /explore are not listed: they are not
        evidence. Nothing here makes a page or lowers the bar for one.
        At most `limit`: the brain's held_limit unless given.
        """
        limit = self.tuning.held_limit if limit is None else limit
        terms = set(tokens(query))
        docs, _ = self._searchable()
        if not terms:
            return []
        n = len(docs)
        df = Counter(t for tf in docs.values() for t in terms if t in tf)
        idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in terms}
        rows = []
        for row in self.candidate_tally():
            if row["page"] or not row["episodes"]:
                continue
            notes = [note for src in row["episodes"] for name, note in src.candidate_notes
                     if same_idea(name) == same_idea(row["name"]) and note]
            named, noted = set(tokens(row["name"])), set(tokens(" ".join(notes)))
            if 2 * len(terms & named) < len(named):  # the question has to name it: half the name's words or more
                continue
            if sum(w for t, w in idf.items() if t in named | noted) < self.tuning.held_coverage * sum(idf.values()):
                continue
            score = sum(w * (3.0 if t in named else 1.0) for t, w in idf.items() if t in named | noted)
            rows.append({"name": row["name"], "note": notes[0] if notes else "", "episodes": row["episodes"],
                         "sources": row["sources"], "score": round(score, 3)})
        return sorted(rows, key=lambda r: (-r["score"], r["name"].lower()))[:limit]

    # -- what was asked and not answered ------------------------------------

    def unanswered(self):
        """Gaps the log shows: [{words, asked, first, last, questions, held, index_gaps}], most asked first.

        A recall line that named no page (`-> none`) is a question the brain could not
        answer. A question is known by its rare words: the ones fewer than rare_word_share
        of the pages hold, or all of its words when it has none. One that shares a rare
        word with a gap joins it, and the gap is then known by the words all its questions
        share (`words`); so a question asked twice is one gap, and so are two wordings about
        one subject. A later question that did name pages closes the gaps all of whose words
        it holds. With each gap come the ideas held on an episode and the pages listed under
        the index's Gaps that its questions name: where to start reading. Read from the
        log; nothing is written.
        """
        in_index = {name: set(tokens(name)) for name in set().union(*(p.gap_targets for p in self.of_type("index")))}
        out = []
        for shared, asked in self.open_gaps():
            questions = list(dict.fromkeys(question for _, question in asked))
            every = set(tokens(" ".join(questions)))
            out.append({"words": sorted(shared), "asked": len(asked), "first": asked[0][0], "last": asked[-1][0],
                        "questions": questions,
                        "held": list(dict.fromkeys(h["name"] for q in questions for h in self.held_ideas(q))),
                        "index_gaps": sorted(name for name, named in in_index.items()
                                             if 2 * len(every & named) >= len(named) > 0)})
        out.sort(key=lambda g: g["words"])
        out.sort(key=lambda g: g["last"], reverse=True)  # of two asked as often, the one asked last
        return sorted(out, key=lambda g: -g["asked"])

    def open_gaps(self):
        """[(the words all its questions share, [(date, question)] in the order asked)] for each gap still open."""
        docs, _ = self._searchable()
        held_by = Counter(t for tf in docs.values() for t in tf)
        few = self.tuning.rare_word_share * len(docs)
        gaps = []  # each: [the words all its questions share, [(date, question)] in the order asked]
        for e in self.events:
            if e.op != "recall" or not e.arrow or is_rehearsal_pass(e):
                continue
            words = set(tokens(e.what))
            if e.targets:  # answered: a gap it holds every word of is closed
                gaps = [gap for gap in gaps if not gap[0] <= words]
                continue
            known_by = {w for w in words if held_by[w] < few} or words
            nearest = max(gaps, key=lambda gap: len(gap[0] & known_by), default=None)
            if nearest and nearest[0] & known_by:
                nearest[0] &= known_by
                nearest[1].append((e.date, e.what))
            elif known_by:
                gaps.append([known_by, [(e.date, e.what)]])
        return [(shared, asked) for shared, asked in gaps]

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
