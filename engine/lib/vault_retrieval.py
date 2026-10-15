"""Retrieval: keyword search, links that strengthen with use, and spreading activation.

Mixed into vaultlib.Vault; relies on its pages, dormant_pages, events, edges, tuning, resolve(),
typed_edges(), contradicted_by(), strength(), confidence(), links_from(), kept() and let_go().
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
from collections import Counter

from vault_cache import TermCache
from vault_events import is_rehearsal_pass
from vault_model import QUESTION, RELATIONS, SECTION, as_list, prose, tokens

# What vaultlib hands on to the commands. The rest is for the parts, which import it from here.
__all__ = ["RetrievalMixin", "rarity_of"]


def rarity_of(pages, holding):
    """How much a word counts for being rare, when `holding` of `pages` pages hold it: BM25's idf.

    A word no page holds weighs most. Search, coverage, the section to read first, the ideas held on an
    episode and `brain fit` all weigh a word by this, so they agree on what a telling word is.
    """
    return math.log(1 + (pages - holding + 0.5) / (holding + 0.5))


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

    def _term_frequencies(self, page):
        memo = self.kept("term_frequencies", dict)
        if page not in memo:
            tf = Counter()
            for field, weight in self.tuning.field_weights:
                for t in tokens(field_text(page, field)):
                    tf[t] += weight
            memo[page] = tf
        return memo[page]

    def _term_frequencies_many(self, pages):
        """{page: tf} for many pages at once, through the SQLite cache (vault_cache) when it opens."""
        memo = self.kept("term_frequencies", dict)
        missing = [p for p in pages if p not in memo]
        if missing:
            cache = self.kept("term_cache", lambda: TermCache(self.root, self.tuning.cache_key))
            memo.update(cache.get_many(missing, self._term_frequencies))
        return {p: memo[p] for p in pages}

    def close_cache(self):
        """Let go of the search cache's file, when this Vault opened it; a later search opens it again."""
        opened = self.let_go("term_cache")
        if opened is not None:
            opened.close()

    # -- keyword search -----------------------------------------------------

    def _searchable(self, types=None, dormant=False):
        """({page: tf}, {page: its length}, {word: the pages that hold it}) for the pages a search may return.

        Kept for the life of the Vault, which reads its pages once: a second search, the
        coverage of its best hit and a recall of the same question do not weigh every page again.
        The third table starts empty and is _holders' to fill, a word at a time.
        """
        def weigh():
            pool = [p for p in self.knowledge if p.type != "project"]
            if dormant:
                pool += self.dormant_pages
            if types:
                pool = [p for p in pool if p.type in types]
            docs = self._term_frequencies_many(pool) if pool else {}
            return docs, {p: sum(tf.values()) for p, tf in docs.items()}, {}
        return self.kept(("searchable", tuple(types) if types else None, dormant), weigh)

    def _holders(self, terms, types=None, dormant=False):
        """{word: the pages that hold it}, in the pool's order, for these words and any asked for before.

        One pass over the pool for the words not asked for before, and none after: the table is kept with
        its pool (_searchable). So a question's words are looked up once, however often search, rarity,
        coverage and the section to read first ask, and search scores only the pages one of them is in.
        Filled by the words asked for and not for every word of every page: one question in one process is
        the common run, and it would pay for the whole table to use a few rows of it.
        """
        docs, _, held = self._searchable(types, dormant)
        new = set(terms).difference(held)
        if new:
            found = {t: [] for t in new}
            for p, tf in docs.items():
                for t in new & tf.keys():  # walks the shorter of the two: a question's few words, or the page's own
                    found[t].append(p)
            held.update((t, tuple(pages)) for t, pages in found.items())
        return held

    def fill_cache(self):
        """Weigh every page a search may return, the dormant ones too, which fills the search cache; how many pages.

        `brain cache --rebuild` calls it on an emptied cache. The cache's file is let go of at the end, so
        that the command can open it again and say what it holds. A brain with no page yet opened none.
        """
        docs, _, _ = self._searchable(dormant=True)
        self.close_cache()
        return len(docs)

    def holding(self, terms, types=None, dormant=False):
        """(how many pages a search may return, {term: how many of them hold it}) for these search terms.

        The pages are the ones `search` reads for the same `types` and `dormant`. A term none holds counts 0.
        """
        docs, _, _ = self._searchable(types, dormant)
        held = self._holders(terms, types, dormant)
        return len(docs), Counter({t: len(held[t]) for t in terms if held[t]})

    def rarity(self, terms, types=None, dormant=False):
        """{term: weight}: how much each of these search terms counts for being rare among those pages (rarity_of)."""
        pages, held = self.holding(terms, types, dormant)
        return {t: rarity_of(pages, held[t]) for t in terms}

    def coverage(self, query, page, dormant=False):
        """How much of the question `page` holds: the share of its words found there, each weighted by its rarity.

        A word no page has weighs most, so a question mostly about something
        the brain never mentions scores low however well one common word matches.
        """
        terms = set(tokens(query))
        docs, _, _ = self._searchable(dormant=dormant)
        if not terms or page not in docs:
            return 0.0
        idf = self.rarity(terms, dormant=dormant)
        return sum(w for t, w in idf.items() if t in docs[page]) / sum(idf.values())

    def search(self, query, types=None, dormant=False, limit=10):
        """[(page, score)] by BM25 over title, aliases, answers, body and summary, best first; [] when no word matches.

        `types` limits the page types; `dormant` adds the pages in dormant/.
        System pages (index, log, ...) and projects are never results.
        Only the pages that hold one of the question's words are scored (_holders): no other
        page can score. A page's words are added up in one order whatever the pool's size,
        so its score is the same to the last bit as when every page was passed over.
        """
        terms = set(tokens(query))
        docs, lengths, _ = self._searchable(types, dormant) if terms else ({}, {}, {})
        if not docs:
            return []
        average = sum(lengths.values()) / len(docs) or 1.0
        idf = self.rarity(terms, types, dormant)
        held = self._holders(terms, types, dormant)
        k1, b = self.tuning.bm25_k1, self.tuning.bm25_b
        scores = {}
        for p in set().union(*(held[t] for t in terms)):
            tf, score = docs[p], 0.0
            for t in terms:
                f = tf.get(t)
                if f:
                    score += idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * lengths[p] / average))
            scores[p] = score  # above 0: the page holds one of the words, and every part of the sum is above 0
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0].rel))[:limit]

    # -- Hebbian weights ----------------------------------------------------

    def _pairs_recalled(self):
        """[(day, pairs)] for each event of the log: the pairs of pages a recall line names together, else ().

        Rehearsal lines are left out: quizzing two pages in one session is the owner being
        tested, not the two ideas being used together. Worked out once and shared with every
        copy as_of makes, as _event_pages is: as_of asks for it before it makes one, so what
        is kept is the whole log's, and a copy reads its own lines from the front of it.
        """
        def read():
            out = []
            for e, named in zip(self.events, self._event_pages()):
                pairs = ()
                if e.op == "recall" and e.day and e.arrow and not is_rehearsal_pass(e):
                    pages = sorted(set(named) - {None}, key=lambda p: p.rel)
                    pages = [p for p in pages if not p.is_system]
                    pairs = tuple(frozenset((a, b)) for i, a in enumerate(pages) for b in pages[i + 1:])
                out.append((e.day, pairs))
            return out
        return self.kept("pairs_recalled", read)

    def edge_weights(self, half_life=None):
        """{frozenset({a, b}): weight} from recall lines naming both pages, each halving every `half_life` days.

        `half_life` is the brain's hebbian_half_life unless given. Folded from the log, once
        for each half-life asked for: a copy as_of makes works out its own (kept).
        """
        half_life = self.tuning.hebbian_half_life if half_life is None else half_life

        def fold():
            weights = {}
            for _, (day, pairs) in zip(self.events, self._pairs_recalled()):
                if pairs:
                    w = 0.5 ** (max(0, (self.today - day).days) / half_life)
                    for pair in pairs:
                        weights[pair] = weights.get(pair, 0.0) + w
            return weights
        return self.kept(("pair_weights", half_life), fold, from_log=True)

    def use_weights(self):
        """{page: weight} from the recall lines naming each page, each halving every hebbian_half_life days.

        What a page's own history of answering comes to. A rehearsal line is left out, as it
        is for pairs: it is the owner being tested, and strength() counts it. A page a line
        names twice was used once. What use teaches fades at one rate, for a pair and a page.
        Folded from the log once, as the pair weights are: a copy as_of makes works out its own.
        """
        half_life = self.tuning.hebbian_half_life

        def fold():
            weights = {}
            for e, named in zip(self.events, self._event_pages()):
                if e.op == "recall" and e.day and e.arrow and not is_rehearsal_pass(e):
                    w = 0.5 ** (max(0, (self.today - e.day).days) / half_life)
                    for p in dict.fromkeys(named):
                        if p is not None and not p.is_system:
                            weights[p] = weights.get(p, 0.0) + w
            return weights
        return self.kept("use_weights", fold, from_log=True)

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
        def weigh():
            graph = {p: {} for p in self.knowledge}
            # relation_<name> for each relation of the vocabulary; one outside it carries like a plain link
            carries = {rel: getattr(self.tuning, "relation_" + rel.replace("-", "_")) for rel in RELATIONS}
            relation = {}
            for a, rel, b in self.typed_edges():
                pair = frozenset((a, b))
                relation[pair] = max(relation.get(pair, 1.0), carries.get(rel, 1.0))
            for a, b in self.knowledge_edges():
                graph[a][b] = graph[b][a] = relation.get(frozenset((a, b)), 1.0)
            return graph
        return self.kept("link_weights", weigh)

    def association_graph(self):
        """{page: {neighbour: weight}}: links (typed ones weighted), strengthened by co-recall.

        Built once. The co-recalls are the log's, so a copy as_of makes builds its own over the same links.
        """
        def build():
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
            return graph
        return self.kept("association_graph", build, from_log=True)

    # -- spreading activation -----------------------------------------------

    def activate(self, seeds, hops=None, decay=None):
        """({page: activation}, {page: (seed, hop)}) after spreading `hops` times from `seeds` ({page: score}).

        Each hop passes on `decay` of a page's new activation along each link,
        by the link's weight relative to the page's strongest and damped by the
        square roots of the link counts of both its ends. The sender's keeps a
        hub from flooding every answer with its neighbours, the receiver's keeps
        it from gathering from all of them. Damped at the sender alone, a page
        of n links hands on sqrt(n) times `decay` of what it holds: more than
        it holds past a few links, so in a densely linked brain each hop was
        stronger than the last and the pages with the most links came first.
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
                strongest = max(links.values())
                for b, w in links.items():  # b links back to a, so it has a link to count
                    damp = math.sqrt(len(links) * len(graph[b]))
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
        idf = self.rarity(terms, dormant=dormant)
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

    def named_by(self, query):
        """The pages whose name is the whole question: its words, stop words aside, are those of a title, an alias
        or a file name, as search stems them. `What is the forgetting curve?` names the page Forgetting curve;
        `Why does the forgetting curve flatten?` names none, since it asks more than what the page is."""
        return self._names_of_pages().get(frozenset(tokens(query)), frozenset())

    def _names_of_pages(self):
        """{the words of a name, as search stems them: the pages called so}, for every title, alias and file name.

        Worked out once. Every page's table, which a question is held against; the one a reminder's line is
        held against is the people's (PeopleMixin._names_of_people).
        """
        def table():
            names = {}
            for p in self.knowledge:
                for name in (p.title, *p.aliases, p.stem):
                    names.setdefault(frozenset(tokens(name)), set()).add(p)
            names.pop(frozenset(), None)  # a name of stop words alone is no name to ask by
            return names
        return self.kept("names_of_pages", table)

    def recall(self, query, project=None, limit=10, hops=None, dormant=False, floor=0.0, abstain=False, also=(),
               types=None):
        """Ranked pages for a question: [{page, score, seed, hop, from, confidence, flags, against, section}].

        `floor` cuts rows scoring under that share of the best row; `abstain`
        returns nothing when the best search hit holds under min_coverage of
        the question. `brain recall` uses both (recall_floor) unless given --all.

        `types` keeps only the rows whose page is of one of those types
        (`("entity",)`). Nothing before the rows is narrowed by it: the hits
        that seed the spread and the spread itself are of every type, so a
        concept is still reached through an episode, and each score is what
        it is without `types`. The floor is a share of the best row of any
        type; the rows are cut by type after it and before `limit`, so
        `limit` rows of those types come back when that many stand. A page
        the question names is left out too when its type is not asked for.

        `also` is other wordings of the same question (the field's own terms,
        plainer words). Each wording is searched on its own and a page's
        scores are added up, the other wordings sharing one vote between
        them: the question as the owner asked it counts as much as all of
        them together. So a word every wording keeps counts most, and a page
        only one wording reaches still comes in. The best seed_limit of the
        sums seed one spread. Whether to abstain is judged on the question
        as it was asked: another wording can change which pages lead, never
        whether the brain covers the question.

        A page the question names (named_by) is its subject. It seeds the
        spread wherever it stands among the hits, no floor cuts it, and it
        is listed first, flagged `named`. Its score is not raised for it.
        One that was a seed already changes no score at all; one that was
        not passes on what any seed does, so the pages it links gain a
        little. Asked "what is X?", every page about X holds the one word
        the question has, so its own scores are nearly level and the other
        wordings, which are longer, decided the order: the page called X
        stood below the seed_limit and was not among the rows.

        Search hits seed the spread (scaled so the best is 1.0). With `project`
        (a prefrontal/ folder name), its pages count project_boost times more
        when they are hits, and join as weak seeds when they are not: what is
        recalled depends on what the owner is working on. A page's score is
        the activation that reached it, lifted by each rehearsal level the
        owner holds (strength_lift) and, in a brain that sets use_lift, by
        its own recalls (lift_from_use).
        flags: named (the question is this page's name), disputed, contradicted,
        stale (a concept or insight not updated in stale_days: ask whether it
        still holds), generated (/explore), dormant.
        against: the pages whose typed link says they contradict this one, whether or
        not they are among the rows: an answer from a contradicted page reads both.
        section: the part of the page to read first, when one stands out (best_sections).
        """
        t = self.tuning
        # Before anything is searched: a project that is not there is refused, whatever the question's words reach.
        focus = self.resolve(project) if project else None
        if project and (focus is None or focus.type != "project"):
            raise ValueError(f"no project named {project} in prefrontal/")
        wordings = [query, *also]
        asked = self.search(query, limit=1, dormant=dormant)
        if abstain and (not asked or self.coverage(query, asked[0][0], dormant=dormant) < t.min_coverage):
            return []
        summed = {}  # with no other wording: the question's own scores, as `search` gives them
        for wording, share in [(query, 1.0), *((other, 1 / len(also)) for other in also)]:
            for p, s in self.search(wording, limit=None, dormant=dormant):
                summed[p] = summed.get(p, 0.0) + s * share
        named = self.named_by(query)
        hits = sorted(summed.items(), key=lambda kv: (-kv[1], kv[0].rel))
        hits = hits[:t.seed_limit] + [hit for hit in hits[t.seed_limit:] if hit[0] in named]
        seeds = {p: s / hits[0][1] for p, s in hits}
        if focus and seeds:
            for p in self.links_from(focus):
                if p.is_system:
                    continue
                seeds[p] = seeds[p] * t.project_boost if p in seeds else t.project_seed
        if not seeds:
            return []
        activation, via = self.activate(seeds, hops=hops)
        rows, faded = [], set(self.dormant_pages)
        for p, a in activation.items():
            score = a * (1 + t.strength_lift * self.strength(p) + self.lift_from_use(p))
            seed, hop = via.get(p, (p, 0))
            flags = [f for f, on in (
                ("named", p in named),
                ("disputed", "disputed" in as_list(p.fields.get("tags"))),
                ("contradicted", bool(self.contradicted_by(p))),
                ("stale", p.type in ("concept", "insight") and p.updated
                 and (self.today - p.updated).days > t.stale_days),
                ("generated", p.generated),
                ("dormant", p in faded),
            ) if on]
            rows.append({"page": p, "score": round(score, 4), "seed": hop == 0, "hop": hop,
                         "from": seed, "flags": flags,
                         "against": sorted(self.contradicted_by(p), key=lambda q: q.rel)})
        best = max(r["score"] for r in rows)
        rows = [r for r in rows if r["score"] >= floor * best or "named" in r["flags"]]
        if types:
            rows = [r for r in rows if r["page"].type in types]
        rows = sorted(rows, key=lambda r: ("named" not in r["flags"], -r["score"], r["page"].rel))[:limit]
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
        if not terms:
            return []
        idf = self.rarity(terms)
        rows = []
        for row, notes in self.held_candidates():
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
        docs, _, _ = self._searchable()
        asked = [(e, set(tokens(e.what))) for e in self.events
                 if e.op == "recall" and e.arrow and not is_rehearsal_pass(e)]
        # Only the words of the questions nothing answered are counted, all of them in one pass over the pages.
        held_by = self._holders(set().union(*(words for e, words in asked if not e.targets)))
        few = self.tuning.rare_word_share * len(docs)
        gaps = []  # each: [the words all its questions share, [(date, question)] in the order asked]
        for e, words in asked:
            if e.targets:  # answered: a gap it holds every word of is closed
                gaps = [gap for gap in gaps if not gap[0] <= words]
                continue
            known_by = {w for w in words if len(held_by[w]) < few} or words
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
