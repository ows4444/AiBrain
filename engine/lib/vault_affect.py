"""Feelings: what the record gives the brain to feel, worked out from the log and the pages.

Mixed into vaultlib.Vault; relies on its pages, events, rehearsals, goals, intentions and tuning.

A feeling here is a reading of the record, never a state that is kept. An event in the log, or a
state of the pages that stands today, is appraised by a rule (a rehearsal missed is frustration
toward that page). It counts for its weight and fades by half every feeling_half_life days; what
one target draws of one feeling is the sum, and feeling_full of it is that feeling at its
strongest. So every feeling names its causes, a log rolled back takes its feelings with it, and
none can be written into being. It is a model of affect for ordering attention: it says nothing
about what is true (confidence is from the evidence only), and nothing about experience.

    surprise      new input says the opposite of a page; a decision turned out other than expected
    frustration   a rehearsal missed; a question asked again and still not answered; a decision
                  that turned out worse; a reminder done after its day; an action of its own
                  that failed, or began and has no end
    curiosity     a question no page answers, each time it is asked
    satisfaction  a rehearsal passed; a decision that turned out as expected or better; a
                  reminder done by its day, one the brain carried out itself, or one handed
                  to another program that reported back
    worry         a goal at risk or past its date; a decision past its review; a reminder due,
                  or one of its own that waits for the owner

The mood is the same events read over a longer time (mood_half_life) and added up across every
target: how the last weeks lean, where a feeling is what one thing draws now.

Only the pages and the log are read. What sits in .cache/ (the error log) is no record: lose it
and a feeling would change with nothing having happened.
"""
from vault_intentions import read_course, words
from vault_model import LINK, parse_date

FEELINGS = ("surprise", "frustration", "curiosity", "satisfaction", "worry")
CALLING = ("surprise", "frustration", "curiosity", "worry")  # the ones that ask for something to be done
# How a reviewed decision turned out against what was expected: what it gives to feel, and how that is said.
OUTCOME_FELT = {"as-expected": (("satisfaction",), "turned out as expected"),
                "better": (("surprise", "satisfaction"), "turned out better than expected"),
                "worse": (("surprise", "frustration"), "turned out worse than expected"),
                "mixed": (("surprise",), "turned out mixed")}


class AffectMixin:
    def appraisals(self):
        """[(feeling, kind, target, day, weight, why)] for every event and standing state a rule reads.

        `kind` is what the target is: a `page` (its path), a `gap` (the words an unanswered
        question is known by), a `goal` or a `reminder` (its words). `day` is when it happened,
        None where the record does not say. A state that stands is of today, and weighs one
        more for every feeling_half_life days it has stood: what is left undone grows as fast
        as what is over fades.
        """
        out = []
        standing = lambda days: 1 + max(0, days) / self.tuning.feeling_half_life  # noqa: E731
        for a, rel, b in sorted(self.typed_edges(), key=lambda e: (e[2].rel, e[0].rel)):
            if rel == "contradicts" and not a.generated and not b.is_system:
                out.append(("surprise", "page", b.rel, parse_date(a.fields.get("created", "")) or a.updated, 1.0,
                            f"{a.rel} says the opposite"))
        for page, events in self.rehearsals.items():
            out += [("satisfaction" if passed else "frustration", "page", page.rel, day, 1.0,
                     "recalled in rehearsal" if passed else "missed in rehearsal") for day, passed in events]
        for known_by, asked in self.open_gaps():
            name = ", ".join(sorted(known_by))
            for n, (date, question) in enumerate(asked):
                out.append(("curiosity", "gap", name, parse_date(date), 1.0, f"asked and not answered: {question}"))
                if n:
                    out.append(("frustration", "gap", name, parse_date(date), 1.0, f"asked again, still no page: {question}"))
        reviewed = {}  # a decision -> the day of the last `review` line naming it
        for e in self.events:
            if e.op == "review" and e.day:
                reviewed.update({self.resolve(t): e.day for t in LINK.findall(e.rest)})
        for p in self.of_type("decision"):
            felt, said = OUTCOME_FELT.get(p.fields.get("outcome") if p.fields.get("status") == "reviewed" else None,
                                          ((), ""))
            out += [(feeling, "page", p.rel, reviewed.get(p) or p.updated, 1.0, said) for feeling in felt]
        for i in self.intentions():
            if i["ended"] == "done" and i["closed"]:
                late = (i["closed"] - i["due"]).days if i["due"] else 0
                out.append(("frustration" if late > 0 else "satisfaction", "reminder", i["text"], i["closed"], 1.0,
                            f"done {late} days after it was due" if late > 0 else
                            "done by its day" if i["due"] else "done"))
        written = {words(i["text"]): i["text"] for i in self.intentions()}  # a reminder as its line says it
        for said, course in read_course(self.events).items():  # what the brain did about one itself
            for day, _, kind, _, note in course:
                if kind in ("failed", "finished"):
                    out.append(("frustration" if kind == "failed" else "satisfaction", "reminder", written.get(said, said),
                                day, 1.0, ("its action failed" if kind == "failed" else "carried out")
                                + (f": {note}" if note else "")))
        for h in self.handed_over():  # what another program did for it, come back as an input
            if h["episode"]:
                out.append(("satisfaction", "reminder", h["text"], h["reported"], 1.0,
                            f"what was handed to {h['hand']} came back: {h['episode']}"))
        for i in self.due_intentions():
            if i["stands"] and i["stands"]["state"] == "waiting":  # its worry is the wait, counted from when it began
                day, _, _, _, note = i["stands"]["course"][-1]
                out.append(("worry", "reminder", i["text"], self.today, standing((self.today - day).days),
                            f"waits for the owner since {day.isoformat()}" + (f": {note}" if note else "")))
                continue
            out.append(("worry", "reminder", i["text"], self.today, standing((self.now - i["since"]).days),
                        f"due since {i['since'].date().isoformat()}"))
        for p in self.decisions_due():
            out.append(("worry", "page", p.rel, self.today, standing((self.today - parse_date(p.fields["review"])).days),
                        f"its review was due {p.fields['review']}"))
        for g in self.goal_report():
            if g["state"] in ("past-due", "stale"):
                out.append(("worry", "goal", g["goal"], self.today, standing(-g["days_left"]),
                            f"{-g['days_left']} days past its date"))
            elif g["at_risk"]:
                out.append(("worry", "goal", g["goal"], self.today, 1.0,
                            f"due in {g['days_left']} days, and nothing done toward it lately"))
        return out

    def feelings(self):
        """[{feeling, kind, target, intensity, causes}], the strongest first; one under feeling_floor has faded.

        `intensity` is 0 to 1. `causes` are what it rests on, the one that counts most first:
        {date, why, counts}, `counts` being what is left of its weight today. An event with no
        day, or one after the day this Vault stands at, is not felt.
        """
        t = self.tuning
        rows = []
        for (feeling, kind, target), causes in self._felt(t.feeling_half_life).items():
            intensity = min(1.0, sum(left for left, _, _ in causes) / t.feeling_full)
            if intensity >= t.feeling_floor:
                rows.append({"feeling": feeling, "kind": kind, "target": target, "intensity": round(intensity, 2),
                             "causes": [{"date": day.isoformat(), "why": why, "counts": round(left, 2)}
                                        for left, day, why in sorted(causes, key=lambda c: (-c[0], c[2]))]})
        return sorted(rows, key=lambda r: (-r["intensity"], FEELINGS.index(r["feeling"]), r["kind"], r["target"]))

    def _felt(self, half_life):
        """{(feeling, kind, target): [(what is left of its weight, its day, why)]}, an event fading by half every `half_life` days."""
        felt = {}
        for feeling, kind, target, day, weight, why in self.appraisals():
            if day and day <= self.today:
                left = weight * 0.5 ** ((self.today - day).days / half_life)
                felt.setdefault((feeling, kind, target), []).append((left, day, why))
        return felt

    def mood(self):
        """How the last weeks lean: {half_life, word, leaning, feelings}.

        The appraisals feelings() reads, fading over mood_half_life, added up across every
        target. One target counts for at most one, a feeling at its strongest, so an amount
        under `feelings` reads as how many things are felt that way in full. `leaning` runs
        from -1 to 1: what was done well (satisfaction) against what was missed or is overdue
        (frustration and worry). `word` names it: quiet when the record gives nothing to feel,
        curious when it gives only questions and surprises, content or uneasy when it leans
        by mood_lean or more, and even between the two.
        """
        t = self.tuning
        amount = dict.fromkeys(FEELINGS, 0.0)
        for (feeling, _, _), causes in self._felt(t.mood_half_life).items():
            amount[feeling] += min(1.0, sum(left for left, _, _ in causes) / t.feeling_full)
        pleasant, unpleasant = amount["satisfaction"], amount["frustration"] + amount["worry"]
        leaning = (pleasant - unpleasant) / (pleasant + unpleasant) if pleasant + unpleasant else 0.0
        word = ("quiet" if not any(amount.values()) else "curious" if not pleasant + unpleasant else
                "content" if leaning >= t.mood_lean else "uneasy" if leaning <= -t.mood_lean else "even")
        return {"half_life": t.mood_half_life, "word": word, "leaning": round(leaning, 2),
                "feelings": {feeling: round(a, 2) for feeling, a in amount.items()}}

    def mood_said(self):
        """The mood in a few words, `uneasy (30 days: worry 2.7, satisfaction 1.0)`; "" when it is quiet."""
        mood = self.mood()
        if mood["word"] == "quiet":
            return ""
        parts = sorted(((a, f) for f, a in mood["feelings"].items() if a), key=lambda p: (-p[0], FEELINGS.index(p[1])))
        return f"{mood['word']} ({mood['half_life']} days: " + ", ".join(f"{f} {a:.1f}" for a, f in parts) + ")"
