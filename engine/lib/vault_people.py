"""People: what the pages hold of each person the brain has a page of.

Mixed into vaultlib.Vault; relies on its pages, links, typed links, claims_built(), intentions, today and kept().

A person is an entity page of `kind: person`. An episode is theirs when its `author` is one of
the page's names (title, alias or file name, compared without case or spacing), and relays
their work when its `relays` is. Four readings of one, each with what it rests on:

    known      the episodes that name them, are theirs or relay them, and the day of the last
    said       how the claims of their episodes fared, counted as a source's are (track_records)
    reminders  the reminders that name them, and how each one ended
    against    what one of their episodes says the opposite of; a decision is the owner's own choice

They are read from the pages when asked. None is stored and they are never added up: how a
claim fared says nothing of what was meant, and no reading is a verdict on the person. Each is
made from that person's own page, their own episodes and the lines that name them, so nothing
written about anyone else moves it.
"""
import re

from vault_memory import relayed

# What vaultlib hands on to the commands. The rest is for the parts, which import it from here.
__all__ = ["PeopleMixin"]


def spoken(name):
    """A name without case or spacing, as `origins` compares authors."""
    return " ".join(str(name or "").lower().split())


class PeopleMixin:
    def persons(self):
        """The pages of people: entities of `kind: person`, by path."""
        return sorted((p for p in self.of_type("entity") if p.fields.get("kind") == "person"), key=lambda p: p.rel)

    def names_of(self, person):
        """The names that reach this page and no other: its title, aliases and file name, without case or spacing."""
        return {spoken(name) for name in (person.title, *person.aliases, person.stem) if self.resolve(name) is person}

    def people_named(self, text):
        """The people a line names, each by one of their names as whole words: `ada` is not in `adam`, and is in `[[Ada]]`.

        The longest name is looked for first and what it matched is used up, so `Ada
        Lovelace` names that person and not another the brain knows as `Ada`.
        """
        text, found = spoken(text), set()
        for name, person in self._names_of_people():
            text, hits = name.subn(" ", text)
            found.update([person] * bool(hits))
        return found

    def _names_of_people(self):
        """[(a pattern for one name as whole words, the person it names)], the longest name first: worked out once.

        The people's table. The one a question is held against is every page's (RetrievalMixin._names_of_pages).
        """
        def table():
            whose = {name: person for person in self.persons() for name in self.names_of(person)}
            return [(re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])"), whose[name])
                    for name in sorted(whose, key=lambda name: (-len(name), name))]
        return self.kept("names_of_people", table)

    def reminders_naming(self, person):
        """The reminders whose words, or whose `when`, name this person: open and closed, in the page's order."""
        return [i for i in self.intentions() if person in self.people_named(f"{i['text']} {i['when']}")]

    def relationships(self):
        """What the pages hold of each person: [{person, name, known, said, reminders, against}], the best known first.

        `known`: {episodes, own, first, last, days}, the episodes that link their page, are
        theirs or relay them, oldest first; how many they wrote; the days of the first and
        the last, and how long ago that is. `said`: {own, relayed, claims}, the episodes
        that are theirs, the ones that relay them, and each page sleep built on those:
        {page, from, with, against}, `from` their episodes behind it, `with` the episodes of
        another independent origin that stand behind it too (none: no second source makes
        the claim), `against` the records that say the opposite of it. `reminders`: [{text,
        when, state, day, late}], `state` being done, dropped, due or open, `day` when it
        was closed or came due, `late` the days a done one was closed after its day.
        `against`: [{episode, page, date, choice}], `choice` true where the page is a
        decision. An /explore episode is in none of them.
        """
        _, of, claims = self.claims_built()
        episodes = sorted(of, key=lambda e: (str(e.came or ""), e.rel))
        opposed = sorted(((a, b) for a, rel, b in self.typed_edges() if rel == "contradicts"),
                         key=lambda edge: (edge[0].rel, edge[1].rel))
        due = {i["text"]: i["since"].date() for i in self.due_intentions()}
        naming = [(i, self.people_named(f"{i['text']} {i['when']}")) for i in self.intentions()]
        rows = []
        for person in self.persons():
            names = self.names_of(person)
            wrote = [e for e in episodes if spoken(e.fields.get("author")) in names]
            told = [e for e in episodes if spoken(relayed(e)) in names]
            own = [e for e in wrote if not relayed(e)]  # a relay is evidence from what it reports, whoever wrote it
            theirs = set(own) | set(told)
            named = [e for e in episodes if e in self.in_links[person] or e in wrote or e in told]
            days = [e.came for e in named if e.came]
            origins = {of[e] for e in theirs}  # one: an author's episodes, and the relays of them, are one origin
            said = {"own": [e.rel for e in own], "relayed": [e.rel for e in told],
                    "claims": [{"page": page.rel, "from": [e.rel for e in evidence if e in theirs],
                                "with": [e.rel for e in evidence if e in of and of[e] not in origins],
                                "against": [c.rel for c in against]}
                               for page, evidence, _, against in claims if theirs.intersection(evidence)]}
            reminders = [{"text": i["text"], "when": i["when"],
                          "state": i["ended"] or ("due" if i["text"] in due else "open"),
                          "day": day.isoformat() if day else None,
                          "late": max(0, (i["closed"] - i["due"]).days)
                          if i["ended"] == "done" and i["closed"] and i["due"] else None}
                         for i, named_in_it in naming if person in named_in_it
                         for day in [i["closed"] or due.get(i["text"])]]
            rows.append({"person": person.rel, "name": person.title,
                         "known": {"episodes": [e.rel for e in named], "own": len(wrote),
                                   "first": days[0].isoformat() if days else None,
                                   "last": days[-1].isoformat() if days else None,
                                   "days": (self.today - days[-1]).days if days else None},
                         "said": said, "reminders": reminders,
                         "against": [{"episode": a.rel, "page": b.rel, "date": str(a.came or ""),
                                      "choice": b.type == "decision"} for a, b in opposed if a in theirs]})
        return sorted(rows, key=lambda row: (-len(row["known"]["episodes"]), row["name"].lower(), row["person"]))
