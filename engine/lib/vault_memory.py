"""Memory over time: the log, recall strength, the sleep queue, evidence, decay.

Mixed into vaultlib.Vault; relies on its pages, edges and resolve().
"""
import re
from collections import Counter

from vault_events import is_rehearsal_pass, is_rehearsal_miss
from vault_model import (BRIER_MIN, CHECKPOINT_INPUTS, CHECKPOINT_SLEEPS, CLAIM_RESULTS, CLAIM_SECTIONS, CLAIM_TAGS,
                         DORMANT_DAYS, FADE_IGNORES_LINKS_FROM, LINK, OPS, OUTCOMES, PROBABILITY_TAGS, RELATIONS,
                         REHEARSAL_DAYS, REHEARSED_TYPES, SALIENCE_STRETCH, SALIENT, STALE_DAYS, STUB_TYPES,
                         STUB_WORDS, as_list, claim_problems, parse_date, tag_vocabulary, thresholds)

# Query parameters that say how a reader arrived, not which page it is.
TRACKING = re.compile(r"^(utm_\w+|fbclid|gclid|igshid|mc_[ce]id|ref|ref_src)$")


class MemoryMixin:
    def log_lines(self):
        """(date, op, rest) for every dated line in the log, in order."""
        return [(e.date, e.op, e.rest) for e in self.events]

    def log_problems(self):
        """Log lines whose operation is not in the vocabulary (CLAUDE.md > Log)."""
        return [f"{day} {op} {rest}" for day, op, rest in self.log_lines() if op not in OPS]

    def usage(self):
        """What has actually been used, from the log and the pages, to decide what stays.

        Operations by count and by month; the operations, typed-link relations
        and vocabulary tags never used; and progress to the calibration checkpoint.
        """
        lines = self.log_lines()
        ops = Counter(op for _, op, _ in lines)
        months = {}
        for day, op, _ in lines:
            months.setdefault(day[:7], Counter())[op] += 1
        relations = {r for p in self.knowledge for r, _ in p.relations}
        tags = {t for p in self.knowledge for t in as_list(p.fields.get("tags"))}
        inputs = sum(not p.generated for p in self.of_type("episode"))
        return {
            "operations": {op: ops[op] for op in sorted(ops, key=lambda o: (-ops[o], o))},
            "by_month": {m: dict(sorted(c.items())) for m, c in sorted(months.items())},
            "unused": {"operations": [op for op in OPS if not ops[op]],
                       "relations": [r for r in RELATIONS if r not in relations],
                       "tags": sorted((tag_vocabulary(self.root) or set()) - tags)},
            "checkpoint": {"inputs": inputs, "inputs_needed": CHECKPOINT_INPUTS,
                           "sleeps": ops["sleep"], "sleeps_needed": CHECKPOINT_SLEEPS,
                           "reached": inputs >= CHECKPOINT_INPUTS and ops["sleep"] >= CHECKPOINT_SLEEPS,
                           "reviewed": any(op == "health" and rest.startswith("calibration")
                                           for _, op, rest in lines)},
            "thresholds": thresholds(),
        }

    def _recalls(self):
        """Page -> sorted dates of every `DATE recall <question> -> [[page]], ...` line naming it."""
        dates = {}
        for e in self.events:
            if e.op != "recall" or not e.arrow or not e.day:
                continue
            for target in e.targets:
                page = self.resolve(target)
                if page:
                    dates.setdefault(page, []).append(e.day)
        return {p: sorted(d) for p, d in dates.items()}

    def _rehearsals(self):
        """Page -> sorted (date, passed) for every rehearsal of it by the owner.

        `DATE recall rehearse -> [[page]]` is a pass; `DATE rehearse missed -> [[page]]`
        is a miss. Any other recall line is the model reading the page, which
        keeps it from fading but is not the owner remembering it.
        """
        out = {}
        for e in self.events:
            passed, missed = is_rehearsal_pass(e), is_rehearsal_miss(e)
            if not e.day or not e.arrow or not (passed or missed):
                continue
            for target in e.targets:
                page = self.resolve(target)
                if page:
                    out.setdefault(page, []).append((e.day, passed))
        return {p: sorted(e) for p, e in out.items()}

    def strength(self, page):
        """Spaced rehearsals passed: one counts only once the interval earned so far has passed; a miss starts over."""
        level, anchor = 0, None
        for day, passed in self.rehearsals.get(page, []):
            if not passed:
                level, anchor = 0, day
            elif anchor is None or (day - anchor).days >= REHEARSAL_DAYS[min(level, len(REHEARSAL_DAYS) - 1)]:
                level, anchor = level + 1, day
        return level

    def missing_from_index(self):
        """Memory pages no index page links to: index drift."""
        listed = {b for a, b in self.edges if a.type == "index"}
        return sorted((p for p in self.knowledge if p not in listed), key=lambda p: p.rel)

    def stale_concepts(self, days=STALE_DAYS):
        concepts = self.of_type("concept")
        stale = [p for p in concepts if p.updated and (self.today - p.updated).days > days]
        return concepts, sorted(stale, key=lambda p: p.updated)

    def stubs(self):
        return [p for p in self.knowledge if p.type in STUB_TYPES and p.words < STUB_WORDS and not p.targets]

    def unconsolidated(self):
        """Episodes and reviewed decisions not yet replayed into the cortex, oldest first.

        A decision's evidence is its outcome, so it is dated by its review, not its creation.
        """
        def when(p):
            return p.fields.get("updated" if p.type == "decision" else "created", "")
        queue = [p for p in self.pages if p.replayed_by_sleep and not p.consolidated]
        return sorted(queue, key=lambda p: (when(p), p.rel))

    @staticmethod
    def source_of(page):
        """What an episode is evidence from: its url, else its input, else itself.

        Two episodes from one article (two clips, a re-encode) are one source;
        a decision is its own source.
        """
        url, _, query = str(page.fields.get("url") or "").strip().split("#", 1)[0].partition("?")
        kept = "&".join(p for p in query.split("&") if p and not TRACKING.match(p.split("=", 1)[0].lower()))
        host, slash, path = re.sub(r"^https?://(www\.)?", "", url.rstrip("/"), flags=re.I).partition("/")
        url = host.lower() + slash + path + ("?" + kept if kept else "")  # only the host ignores case
        if url and page.type == "episode":
            return "url:" + url
        if page.fields.get("input") and page.type == "episode":
            return "input:" + ",".join(sorted(str(i).removeprefix("./") for i in as_list(page.fields["input"])))
        return "page:" + page.rel

    def candidate_tally(self):
        """Candidate ideas: name -> pages naming them, and its page if any.

        `episodes` holds the evidence: encoded episodes and reviewed decisions;
        `sources` counts how many distinct sources those are, which is what the
        concept bar needs (two or more). `generated` holds /explore episodes,
        which raise an idea but never count, since imagining something is not
        evidence for it. Names that reach one page (its title or an alias) are
        one candidate; without a page, only the same spelling is.
        """
        tally = {}
        for src in self.pages:
            for name in src.candidates:
                page = self.resolve(name)
                row = tally.setdefault(("page", page.rel) if page else ("name", name.lower()),
                                       {"name": name, "episodes": [], "generated": [], "page": page})
                bucket = row["generated" if src.generated else "episodes"]
                if src not in bucket:
                    bucket.append(src)
        for row in tally.values():
            row["sources"] = len({self.source_of(p) for p in row["episodes"]})
            row["salient"] = any(p.salience >= SALIENT for p in row["episodes"])
        return sorted(tally.values(), key=lambda r: (-r["sources"], -len(r["episodes"]), -len(r["generated"]),
                                                     r["name"].lower()))

    def decisions_due(self):
        """Decided pages whose review date has come, most overdue first."""
        due = []
        for p in self.of_type("decision"):
            review = parse_date(p.fields.get("review", ""))
            if p.fields.get("status") == "decided" and review and review <= self.today:
                due.append((p, review))
        return [p for p, _ in sorted(due, key=lambda t: (t[1], t[0].rel))]

    def calibration(self):
        """How reviewed decisions turned out against what was expected: outcome -> count."""
        counts = dict.fromkeys(OUTCOMES, 0)
        for p in self.of_type("decision"):
            if p.fields.get("status") == "reviewed" and p.fields.get("outcome") in counts:
                counts[p.fields["outcome"]] += 1
        return counts

    def decision_report(self):
        """Each decided or reviewed decision: its revisit line, its claims by tag, whether it is tagged to-revisit."""
        out = []
        for p in sorted(self.of_type("decision"), key=lambda p: p.rel):
            if p.fields.get("status") in ("decided", "reviewed"):
                mix = Counter(c["tag"] for c in p.claims if c["section"] in CLAIM_SECTIONS and c["tag"] in CLAIM_TAGS)
                out.append({"page": p.rel, "status": p.fields["status"], "revisit_if": p.fields.get("revisit_if", ""),
                            "claims": {t: mix[t] for t in CLAIM_TAGS if mix[t]},
                            "triggered": "to-revisit" in as_list(p.fields.get("tags"))})
        return out

    def claim_results(self):
        """How the guesses in reviewed decisions turned out: tag -> {held, failed, unknown}."""
        counts = {t: dict.fromkeys(CLAIM_RESULTS, 0) for t in ("assumption", "hypothesis")}
        for p in self.of_type("decision"):
            for c in p.claims if p.fields.get("status") == "reviewed" else []:
                if c["section"] == "Outcome" and c["tag"] in counts and c["result"] in CLAIM_RESULTS:
                    counts[c["tag"]][c["result"]] += 1
        return counts

    def claim_link_problems(self):
        """(page, claim) for observations on a decision that cite only /explore episodes: imagining is not observing."""
        out = []
        for p in self.of_type("decision"):
            for c in p.claims:
                cited = [self.resolve(t) for t in LINK.findall(c["text"])]
                if c["tag"] == "observation" and any(cited) and all(d.generated for d in cited if d):
                    out.append((p, c["text"]))
        return out

    def untagged_open(self):
        """Open decisions whose reasoning is not tagged yet: it must be before they are decided."""
        return sorted((p for p in self.of_type("decision")
                       if p.fields.get("status") == "open" and claim_problems(p.body)), key=lambda p: p.rel)

    def last_touched(self, page):
        dates = [d for d in (page.updated, self.last_recall.get(page)) if d]
        return max(dates) if dates else None

    def last_rehearsed(self, page):
        """When the rehearsal clock last started: the owner's last rehearsal of the page, else its creation.

        Editing a page does not move it (CLAUDE.md > How memory forms > Rehearse):
        sleep touches every page it updates, and that is the model writing, not
        the owner remembering. A page with no `created:` falls back to `updated:`.
        """
        events = self.rehearsals.get(page, [])
        if events:
            return events[-1][0]
        return parse_date(page.fields.get("created", "")) or page.updated

    def miss_risk(self, page):
        """(risk, attempts): the share of the owner's rehearsals of this page that missed, smoothed.

        (misses + 1) / (attempts + 2), so an unrehearsed page sits at 0.5 and a
        single result moves it only part of the way. Shown only from
        RISK_MIN_ATTEMPTS attempts; used for ordering at any count.
        """
        events = self.rehearsals.get(page, [])
        misses = sum(not passed for _, passed in events)
        return (misses + 1) / (len(events) + 2), len(events)

    def due_for_rehearsal(self):
        """Concepts and insights whose spaced-retrieval interval has passed.

        Pages the owner's goals depend on come first, then the more salient,
        then those the owner most often misses, then the most overdue.
        """
        due = []
        purpose = self.purpose()
        for p in (p for p in self.pages if p.type in REHEARSED_TYPES):
            last = self.last_rehearsed(p)
            if not last:
                continue
            interval = REHEARSAL_DAYS[min(self.strength(p), len(REHEARSAL_DAYS) - 1)]
            overdue = (self.today - last).days - interval
            if overdue >= 0:
                due.append((p, overdue))
        return [p for p, _ in sorted(due, key=lambda t: (t[0] not in purpose, -t[0].salience,
                                                         -self.miss_risk(t[0])[0], -t[1], t[0].rel))]

    def fade_days(self, page, days=DORMANT_DAYS):
        """How long this page may go untouched before it is proposed for dormant/: longer the more salient."""
        return days * (1 + SALIENCE_STRETCH * min(page.salience, SALIENT - 1))

    def dormant_candidates(self, days=DORMANT_DAYS):
        """Unlinked, unrecalled, untouched for `days`: what sleep would scale down.

        Episodes and decisions are records of what happened, so they never fade;
        nor does anything a goal or a live project depends on. A link from an
        episode does not count: every page sleep builds has one. Salience 1-3
        stretches `days` (fade_days); 4 and up never fades.
        """
        linked = {b for a, b in self.knowledge_edges() if a.type not in FADE_IGNORES_LINKS_FROM}
        purpose = self.purpose()
        out = []
        for p in self.knowledge:
            last = self.last_touched(p)
            if (p.type not in ("episode", "decision") and not p.protected and p not in linked
                    and p not in purpose and last and (self.today - last).days > self.fade_days(p, days)):
                out.append(p)
        return sorted(out, key=self.last_touched)

    def evidence_for(self, page):
        """The records a page rests on: encoded episodes and reviewed decisions linked to or from it.

        An episode rests on itself; an insight on the evidence of the pages it
        links. /explore episodes are never evidence, and neither is a record
        that says it contradicts the page.
        """
        if page.type == "episode":
            return [] if page.generated else [page]
        against = {a for a, rel, b in self.typed_edges() if rel == "contradicts" and b is page}
        near = {b for a, b in self.edges if a is page} | {a for a, b in self.edges if b is page}
        found = {p for p in near if p.replayed_by_sleep and not p.generated and p not in against}
        if page.type == "insight":
            for p in (b for a, b in self.edges if a is page and b.type in ("concept", "entity")):
                found |= set(self.evidence_for(p))
        found.discard(page)
        return sorted(found, key=lambda p: p.rel)

    def confidence(self, page):
        """How well supported a page is: the feeling of knowing, from the evidence only.

        level: high (3+ sources from 2+ independent origins), medium (2+ sources),
        low (one or none, or tagged disputed); an episode is `source`: it reports
        what one source said and is as good as that source. Independent means a
        different site, or a different input. A contradiction sleep has not
        weighed yet is flagged (`contradicted`) without lowering the level; once
        sleep tags the page `disputed`, the level is low. `strength` is how well
        the owner remembers it, shown beside the level but not part of it:
        remembering a claim does not make it better supported.
        """
        sources = {self.source_of(p) for p in self.evidence_for(page)}
        origins = {s.split("/", 1)[0] if s.startswith("url:") else s for s in sources}
        contradicted = any(rel == "contradicts" and b is page for _, rel, b in self.typed_edges())
        disputed = "disputed" in as_list(page.fields.get("tags"))
        n, k = len(sources), len(origins)
        if page.type == "episode":
            level = "low" if page.generated else "source"
        else:
            level = "low" if disputed or n < 2 else "high" if n >= 3 and k >= 2 else "medium"
        why = ("an /explore hypothesis" if page.generated else "what one source said") if page.type == "episode" \
            else f"{n} source{'s' * (n != 1)}, {k} independent"
        why += (", disputed" if disputed else "") + (", contradicted by new input" if contradicted else "")
        return {"level": level, "sources": n, "independent": k, "disputed": disputed, "contradicted": contradicted,
                "strength": self.strength(page), "why": why}

    def contradiction_queue(self):
        """(episode, page) where an episode not yet consolidated says it contradicts a page.

        Prediction error: new input against what the brain already holds. Sleep
        records both positions and tags the page `disputed` (CLAUDE.md > Disagreement).
        """
        return sorted(((a, b) for a, rel, b in self.typed_edges()
                       if rel == "contradicts" and a.type == "episode" and not a.consolidated),
                      key=lambda e: (e[1].rel, e[0].rel))

    def _scored_guesses(self, decisions):
        """(p, held) for each reviewed hypothesis or assumption with a probability and a held/failed result.

        The probability is on the Outcome line, or on the identical line under a claim section.
        """
        out = []
        for page in decisions:
            if page.fields.get("status") != "reviewed":
                continue
            stated = {c["text"]: c["p"] for c in page.claims if c["section"] in CLAIM_SECTIONS and c["p"] is not None}
            for c in page.claims:
                if c["section"] == "Outcome" and c["tag"] in PROBABILITY_TAGS and c["result"] in ("held", "failed"):
                    p = c["p"] if c["p"] is not None else stated.get(c["text"])
                    if p is not None and 0 <= p <= 1:
                        out.append((p, c["result"] == "held"))
        return out

    @staticmethod
    def _brier(pairs):
        n = len(pairs)
        buckets = {}
        for p, held in pairs:
            row = buckets.setdefault(f"{int(round(p * 10)) * 10}%", {"n": 0, "held": 0})
            row["n"] += 1
            row["held"] += held
        return {"n": n, "score": round(sum((p - held) ** 2 for p, held in pairs) / n, 3) if n else None,
                "enough": n >= BRIER_MIN, "buckets": dict(sorted(buckets.items(), key=lambda kv: int(kv[0][:-1])))}

    def brier(self):
        """Calibration of the owner's stated probabilities on reviewed decisions.

        Brier score: the mean of (probability - outcome)^2, 0 is perfect, 0.25 is
        always saying 50%. Buckets show, of everything called 70%, how much held.
        `enough` is False below BRIER_MIN scored guesses: show the count, no verdict.
        """
        return self._brier(self._scored_guesses(self.of_type("decision")))

    def reference_class(self):
        """For each tag on reviewed decisions: how they turned out, and the Brier score of their guesses.

        What to look at before setting a probability on a new decision with that tag.
        """
        groups = {}
        for p in self.of_type("decision"):
            if p.fields.get("status") == "reviewed":
                for tag in as_list(p.fields.get("tags")) or ["(untagged)"]:
                    groups.setdefault(tag, []).append(p)
        out = {}
        for tag, pages in sorted(groups.items()):
            outcomes = Counter(p.fields.get("outcome") for p in pages if p.fields.get("outcome") in OUTCOMES)
            out[tag] = {"n": len(pages), "outcomes": {o: outcomes[o] for o in OUTCOMES if outcomes[o]},
                        "brier": self._brier(self._scored_guesses(pages))}
        return out
