"""People: what the pages hold of each person, read when asked and never stored. Run: brain test"""
import json
import os
from unittest import mock

from support import TODAY, TempBrain, ago, page, run_brain, vaultlib

import commands  # noqa: E402  (support puts engine/lib on the path)
import feel  # noqa: E402
import introspect  # noqa: E402

DATES = dict(created=ago(40), updated=ago(40))
ADA, GRACE, BOHR = "Ada Lovelace", "Grace Hopper", "Niels Bohr"
E = "cortex/episodes/{}.md".format


def person(title, **fields):
    return page("entity", "Someone.\n", **dict(DATES, kind="person", title=title, **fields))


def concept(body, title):
    return page("concept", body, **dict(DATES, status="established", title=title))


class Readings(TempBrain):
    """Three people and an organisation. Today is 2026-10-03.

    Ada wrote e1 and e2; `note` relays that work, `seen` names Ada, and `dream` is an /explore
    episode under the same name. Grace wrote g1. Bohr is named by one episode that gives no day.
    """

    def episode(self, slug, body="", days=None, **fields):
        dated = dict(created=ago(days), updated=ago(days)) if days is not None else {}
        self.write(E(slug), page("episode", body, title=slug, **dict(dated, **fields)))

    def setUp(self):
        super().setUp()
        self.write("cortex/entities/ada-lovelace.md", person(ADA, aliases="[Ada]"))
        self.write("cortex/entities/grace-hopper.md", person(GRACE))
        self.write("cortex/entities/niels-bohr.md", person(BOHR))
        self.write("cortex/entities/acme.md", page("entity", "A firm.\n", **dict(DATES, kind="org", title="Acme")))
        self.write("cortex/concepts/shared.md", concept("From [[e1]] and [[g1]].", "Shared"))
        self.write("cortex/concepts/solo.md", concept("From [[e1]] and [[note]].", "Solo"))
        self.write("cortex/concepts/doubted.md", concept("From [[g1]].", "Doubted"))
        self.write("cortex/decisions/launch.md", page("decision", "A choice.\n", status="decided", title="Launch", **DATES))
        self.episode("e1", days=20, url="https://a.example/one", author=ADA)
        self.episode("e2", "No (contradicts:: [[launch]]), and no (contradicts:: [[doubted]]).", days=10,
                     input="senses/two.md", author="ada  LOVELACE")  # the same name, whatever its case and spacing
        self.episode("g1", days=5, url="https://b.example/g", author=GRACE)
        self.episode("note", days=3, input="senses/note.md", author="A Reader", relays=ADA)
        self.episode("seen", "With [[Ada]] at [[acme]].", days=2, url="https://c.example/seen", author="Bob")
        self.episode("dream", "[[ada-lovelace]] (contradicts:: [[shared]])", days=1, origin="generated", author=ADA)
        self.episode("old", "About [[niels-bohr]].")
        self.write("hippocampus/intentions.md", page("intentions", "\n# Intentions\n\n## Open\n\n"
                   "- ask Ada about the launch when 2026-09-20 (done 2026-09-23: agreed)\n"
                   "- thank Ada Lovelace when 2026-12-01\n"
                   "- send [[grace-hopper]] the draft when 2026-10-01\n"
                   "- call the bank when Grace Hopper confirms\n"
                   "- forget the idea Ada had when 2026-09-01 (dropped)\n"
                   "- write to Adam when 2026-10-01\n"
                   "- tell Ada the date when 2026-09-28\n"
                   "- pay Ada back when 2026-09-25 (done)\n"))

    def rows(self):
        return {row["name"]: row for row in self.brain().relationships()}

    def call(self, module, *args):
        """(what `brain <module> ARGS` returns, the text it prints), on the day the tests stand at."""
        with mock.patch.object(module, "Vault", lambda root: vaultlib.Vault(root, today=TODAY)):
            module, parsed = commands.prepare(module.__name__, list(args), self.root)
            result = module.run(self.root, parsed)
            return result, module.render(result, parsed)

    def test_four_readings_of_a_person_each_with_what_it_rests_on(self):
        rows = self.brain().relationships()
        self.assertEqual([row["name"] for row in rows], [ADA, GRACE, BOHR])  # the best known first; a firm is no person
        self.assertEqual(rows[0], {
            "person": "cortex/entities/ada-lovelace.md", "name": ADA,
            "known": {"episodes": [E("e1"), E("e2"), E("note"), E("seen")], "own": 2, "first": ago(20), "last": ago(2),
                      "days": 2},
            "said": {"own": [E("e1"), E("e2")], "relayed": [E("note")], "claims": [
                {"page": "cortex/concepts/shared.md", "from": [E("e1")], "with": [E("g1")], "against": []},
                {"page": "cortex/concepts/solo.md", "from": [E("e1"), E("note")], "with": [], "against": []}]},
            "reminders": [
                {"text": "ask Ada about the launch", "when": "2026-09-20", "state": "done", "day": "2026-09-23", "late": 3},
                {"text": "thank Ada Lovelace", "when": "2026-12-01", "state": "open", "day": None, "late": None},
                {"text": "forget the idea Ada had", "when": "2026-09-01", "state": "dropped", "day": None, "late": None},
                {"text": "tell Ada the date", "when": "2026-09-28", "state": "due", "day": "2026-09-28", "late": None},
                {"text": "pay Ada back", "when": "2026-09-25", "state": "done", "day": None, "late": None}],
            "against": [{"episode": E("e2"), "page": "cortex/concepts/doubted.md", "date": ago(10), "choice": False},
                        {"episode": E("e2"), "page": "cortex/decisions/launch.md", "date": ago(10), "choice": True}]})
        grace, bohr = rows[1], rows[2]
        self.assertEqual(grace["said"]["claims"], [  # what Ada's episode says the opposite of is named with the claim
            {"page": "cortex/concepts/doubted.md", "from": [E("g1")], "with": [], "against": [E("e2")]},
            {"page": "cortex/concepts/shared.md", "from": [E("g1")], "with": [E("e1")], "against": []}])
        self.assertEqual([(i["text"], i["state"], i["day"]) for i in grace["reminders"]], [
            ("send [[grace-hopper]] the draft", "due", "2026-10-01"), ("call the bank", "open", None)])
        self.assertEqual(bohr["known"], {"episodes": [E("old")], "own": 0, "first": None, "last": None, "days": None})
        self.assertEqual((bohr["said"], bohr["reminders"], bohr["against"]),
                         ({"own": [], "relayed": [], "claims": []}, [], []))

    def test_what_changes_a_reading_is_an_episode_it_names_and_it_says_nothing_of_anyone_else(self):
        before = self.rows()
        self.episode("g2", days=1, url="https://b.example/h", author=GRACE)
        after = self.rows()
        self.assertEqual((after[ADA], after[BOHR]), (before[ADA], before[BOHR]))
        self.assertEqual(after[GRACE]["known"], {"episodes": [E("g1"), E("g2")], "own": 2, "first": ago(5),
                                                  "last": ago(1), "days": 1})
        self.assertEqual(after[GRACE]["said"]["own"], [E("g1"), E("g2")])
        self.episode("g3", "No (contradicts:: [[solo]]).", days=0, url="https://b.example/i", author=GRACE)
        last = self.rows()
        self.assertEqual(last[BOHR], before[BOHR])
        self.assertEqual(last[ADA]["said"]["claims"][1],  # the one line of Ada's that moved names the episode that moved it
                         {"page": "cortex/concepts/solo.md", "from": [E("e1"), E("note")], "with": [], "against": [E("g3")]})
        self.assertEqual({k: v for k, v in last[ADA].items() if k != "said"},
                         {k: v for k, v in before[ADA].items() if k != "said"})
        self.assertEqual(last[GRACE]["against"][-1]["episode"], E("g3"))

    def test_a_name_two_pages_answer_to_is_the_first_one_s(self):
        self.write("cortex/entities/ada-byron.md", person("Ada Byron", aliases="[Ada]"))
        rows = self.rows()  # `Ada` reaches the page whose file name comes first, so it names nobody else
        self.assertEqual([i["text"] for i in rows["Ada Byron"]["reminders"]], [
            "ask Ada about the launch", "forget the idea Ada had", "tell Ada the date", "pay Ada back"])
        self.assertEqual([i["text"] for i in rows[ADA]["reminders"]], ["thank Ada Lovelace"])  # the whole name is still Lovelace's
        self.assertEqual(rows[ADA]["known"]["episodes"], [E("e1"), E("e2"), E("note")])  # [[Ada]] in `seen` reaches the other page now
        self.assertEqual(rows["Ada Byron"]["known"]["episodes"], [E("seen")])

    def test_it_stores_nothing(self):
        def tree():  # every file of the brain but the search cache, which is no record
            found = {}
            for folder, _, names in os.walk(self.root):
                for name in (names if ".cache" not in folder else []):
                    with open(os.path.join(folder, name), "rb") as fh:
                        found[os.path.join(folder, name)] = fh.read()
            return found
        before = tree()
        ran = run_brain(self.root, "introspect", "--people", "--json")
        self.assertEqual([row["name"] for row in json.loads(ran.stdout)["people"]], [ADA, GRACE, BOHR])
        run_brain(self.root, "feel", ADA)
        self.assertEqual(tree(), before)

    def test_the_view_and_its_text(self):
        found, out = self.call(introspect, "--people")
        self.assertIn(
            "\npeople (pages of `kind: person`; four readings of each, from the pages, never added up): 3\n"
            "  Ada Lovelace  (cortex/entities/ada-lovelace.md)\n"
            f"      known      4 episodes, 2 of them theirs; the last on {ago(2)}, 2 days ago\n"
            "      said       2 episodes of their own: 2 claims, 1 also made by a second independent source, "
            "1 by no second one, 0 contradicted; 1 more only relay them\n"
            "      reminders  2 done (1 after its day), 1 dropped, 1 due, 1 not yet due\n"
            "                 due since 2026-09-28: tell Ada the date\n"
            "      against    2 of their episodes say the opposite of a page\n"
            "                 cortex/episodes/e2.md says the opposite of cortex/concepts/doubted.md\n"
            "                 cortex/episodes/e2.md says the opposite of cortex/decisions/launch.md, a choice of the owner's\n"
            "  Grace Hopper  (cortex/entities/grace-hopper.md)\n"
            f"      known      1 episode, 1 of them theirs; the last on {ago(5)}, 5 days ago\n"
            "      said       1 episode of their own: 2 claims, 1 also made by a second independent source, "
            "1 by no second one, 1 contradicted (cortex/concepts/doubted.md)\n"
            "      reminders  0 done, 0 dropped, 1 due, 1 not yet due\n"
            "                 due since 2026-10-01: send [[grace-hopper]] the draft\n"
            "      against    0 of their episodes say the opposite of a page\n"
            "  Niels Bohr  (cortex/entities/niels-bohr.md)\n"
            "      known      1 episode, 0 of them theirs\n"
            "      said       0 episodes of their own: 0 claims, 0 also made by a second independent source, "
            "0 by no second one, 0 contradicted\n"
            "      reminders  0 done, 0 dropped, 0 due, 0 not yet due\n"
            "      against    0 of their episodes say the opposite of a page\n"
            "  --json names every episode a reading rests on. How a claim fared says nothing of what was meant, "
            "and no reading is a verdict on the person", out)
        self.assertEqual(found["people"], self.brain().relationships())
        self.assertEqual(self.call(introspect, "--json")[0]["people"], found["people"])  # in the whole report too

    def test_what_is_felt_toward_a_person_is_read_from_the_reminders_that_name_them(self):
        felt = self.call(feel, ADA)[0]["feelings"]
        self.assertEqual([(row["feeling"], row["kind"], row["target"]) for row in felt], [
            ("worry", "reminder", "tell Ada the date"),               # neither holds the word Lovelace
            ("frustration", "reminder", "ask Ada about the launch")])  # done three days after its day
        self.assertEqual([row["target"] for row in self.call(feel, GRACE)[0]["feelings"]],
                         ["send [[grace-hopper]] the draft"])
        self.assertEqual(self.call(feel, "acme")[0]["feelings"], [])  # a page that is no person's
