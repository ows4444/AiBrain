"""Retrieval: search, co-recall weights, spreading activation, confidence, the answer test set. Run: brain test"""
import datetime
import json
import os
import re
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

from support import ENGINE, SCRIPTS, TempBrain, TODAY, ago, page, run_brain, vaultlib

import commands  # noqa: E402  (support puts engine/lib on the path)
import eval as eval_script  # noqa: E402
import synth  # noqa: E402
import vault_cache  # noqa: E402

FIXTURE = os.path.join(ENGINE, "eval", "fixture")


def concept(body, **fields):
    return page("concept", body, **dict(dict(status="established", created=ago(10), updated=ago(10)), **fields))


class Search(TempBrain):
    def test_words_rank_by_field_and_ignore_stop_words_and_suffixes(self):
        self.write("cortex/concepts/spacing.md", concept("Study spread over days.", title="Spacing effect"))
        self.write("cortex/concepts/other.md", concept("The spacing of rows in a table.", title="Layout"))
        self.write("cortex/concepts/none.md", concept("Nothing relevant at all.", title="None"))
        v = self.brain()
        ranked = [p.stem for p, _ in v.search("what is the spaced effect")]
        self.assertEqual(ranked[:2], ["spacing", "other"])  # a title match outranks a body match
        self.assertNotIn("none", ranked)
        self.assertEqual(v.search("the and of"), [])  # only stop words: nothing to find
        self.assertEqual(vaultlib.tokens("Forgetting forgets forget"), ["forget"] * 3)

    def test_the_summary_is_searched_and_counts_for_less_than_the_body(self):
        self.write("cortex/concepts/loci.md", concept("Items are placed along a route.", title="Method of loci",
                                                      summary="A way to memorise an ordered list."))
        self.write("cortex/concepts/lists.md", concept("How to memorise a list of words.", title="Word lists",
                                                       summary="Notes on rote learning."))
        v = self.brain()
        self.assertEqual([p.stem for p, _ in v.search("memorise")], ["lists", "loci"])
        self.assertEqual([p.stem for p, _ in v.search("ordered")], ["loci"])  # a word only the summary has

    def test_types_and_dormant(self):
        self.write("cortex/entities/anki.md", page("entity", "A flashcard app.", title="Anki"))
        self.write("cortex/concepts/cards.md", concept("Flashcard decks.", title="Cards"))
        self.write("dormant/old-cards.md", concept("Flashcard tips from long ago.", title="Old cards"))
        v = self.brain()
        self.assertEqual([p.stem for p, _ in v.search("flashcard", types=["entity"])], ["anki"])
        self.assertNotIn("old-cards", [p.stem for p, _ in v.search("flashcard")])
        self.assertIn("old-cards", [p.stem for p, _ in v.search("flashcard", dormant=True)])

    def test_system_pages_and_projects_are_never_results(self):
        self.write("hippocampus/index.md", page("index", "flashcard flashcard"))
        self.write("prefrontal/cards/CLAUDE.md", page("project", "flashcard", title="Cards", status="active"))
        self.assertEqual(self.brain().search("flashcard"), [])


class QuestionsAPageAnswers(TempBrain):
    """`answers:`: the questions a page answers, in its owner's words, searched as a field of its own."""

    def setUp(self):
        super().setUp()
        self.write("cortex/concepts/spacing.md", concept(
            "Study spread over days lasts longer than the same study massed into one sitting.\n", title="Spacing effect",
            summary="Spread study lasts.",
            answers="\n  - Is cramming the night before worse, or fine?\n  - Why: does leaving gaps help?"))
        self.write("cortex/concepts/other.md", concept("Rows and columns of a table.\n", title="Layout", summary="Tables."))

    def test_a_question_in_other_words_than_the_page_s_finds_it(self):
        v = self.brain()
        self.assertEqual(v.resolve("spacing").answers, ["Is cramming the night before worse, or fine?",
                                                        "Why: does leaving gaps help?"])  # commas and colons kept
        self.assertEqual([p.stem for p, _ in v.search("should I cram the night before?")], ["spacing"])
        self.assertEqual([r["page"].stem for r in v.recall("should I cram the night before?", abstain=True)], ["spacing"])
        without = vaultlib.Vault(self.root, today=TODAY, tuning={"weight_answers": 0.0})  # at 0 the field is not read
        self.assertEqual(without.search("should I cram the night before?"), [])
        self.assertIn("answers=2.0", v.tuning.cache_key)  # a cache filled before the field was searched is not this one's
        self.assertNotIn("answers", without.tuning.cache_key)

    def test_it_is_a_few_short_questions_and_stays_in_the_brain(self):
        def problems(answers):
            return vaultlib.schema_problems(concept("Text.\n", title="A page", summary="A page.", answers=answers))

        five = "".join(f"\n  - Question {n}?" for n in range(1, 6))
        self.assertEqual((problems(five), problems("Only one, on the line itself?"), problems("")), ([], [], []))
        self.assertEqual(problems(five + "\n  - A sixth?"), ["6 questions under 'answers'; at most 5"])
        self.assertEqual(problems("\n  - " + "why " * 30 + "so?"),
                         ["'answers' holds a question of 123 characters; each is one short question, at most 120"])
        out = os.path.join(self.root, "out")
        made = json.loads(run_brain(self.root, "export", "spacing", "--out", out, "--json").stdout)
        with open(os.path.join(out, made["exported"][0]), encoding="utf-8") as fh:
            exported = fh.read()
        self.assertNotIn("answers", exported)  # private, with its lines: how its owner asks is not for others
        self.assertNotIn("cramming the night", exported)
        self.assertIn("Study spread over days", exported)


class SeveralWordings(TempBrain):
    """`brain recall Q --also Q2`: other wordings of one question, searched each on its own and added up."""

    def setUp(self):
        super().setUp()
        for stem, title in (("alpha", "Alpha"), ("beta", "Beta"), ("gamma", "Gamma")):
            self.write(f"cortex/concepts/{stem}.md", concept(f"What {stem} is.\n", title=title, summary=f"On {stem}."))

    def stems(self, rows):
        return [(r["page"].stem, r["score"]) for r in rows]

    def test_a_page_only_another_wording_reaches_comes_in(self):
        v = self.brain()
        self.assertEqual(self.stems(v.recall("alpha")), [("alpha", 1.0)])
        self.assertEqual(self.stems(v.recall("alpha", also=())), self.stems(v.recall("alpha")))  # one wording: as before
        self.assertEqual(self.stems(v.recall("alpha", also=["beta"])), [("alpha", 1.0), ("beta", 1.0)])
        # The question as asked counts as much as its other wordings together: two of them count half each.
        self.assertEqual(self.stems(v.recall("alpha", also=["beta", "gamma"])), [("alpha", 1.0), ("beta", 0.5), ("gamma", 0.5)])
        self.assertEqual(self.stems(v.recall("alpha", also=["alpha beta", "alpha"])), [("alpha", 1.0), ("beta", 0.25)])

    def test_whether_the_brain_covers_the_question_is_judged_on_the_question_as_asked(self):
        v = self.brain()
        self.assertEqual(v.recall("zebra", also=["alpha"], abstain=True), [])  # no word of the question is here
        self.assertEqual(v.recall("zebra quartz violin alpha", also=["alpha"], abstain=True), [])  # too little of it is
        self.assertEqual(self.stems(v.recall("zebra", also=["alpha"])), [("alpha", 1.0)])  # --all: the other wording may find
        self.assertEqual(self.stems(v.recall("alpha", also=["zebra"], abstain=True)), [("alpha", 1.0)])

    def test_the_command_takes_them_and_says_them_back(self):
        r = run_brain(self.root, "recall", "what is alpha", "--also", "what is beta", "--also", "  ", "--json")
        found = json.loads(r.stdout)
        self.assertEqual((found["also"], [row["page"] for row in found["results"]]),
                         (["what is beta"], ["cortex/concepts/alpha.md", "cortex/concepts/beta.md"]))
        text = run_brain(self.root, "recall", "what is alpha", "--also", "what is beta").stdout
        self.assertEqual(text.splitlines()[:2], ['recall: "what is alpha"', '  also asked as: "what is beta"'])
        self.assertNotIn("also", json.loads(run_brain(self.root, "recall", "what is alpha", "--json").stdout))
        r = run_brain(self.root, "search", "alpha", "--also", "beta")
        self.assertEqual((r.returncode, r.stderr), (1, "brain search: --also is for recall, which fuses the wordings; "
                                                       "search takes one\n"))


class Association(TempBrain):
    def setUp(self):
        super().setUp()
        self.write("cortex/concepts/spacing.md", concept("Study spread over days. See [[forgetting]].",
                                                         title="Spacing effect"))
        self.write("cortex/concepts/forgetting.md", concept("Memory fades fast, then slowly. [[curve-data]]",
                                                            title="Forgetting curve"))
        self.write("cortex/concepts/curve-data.md", concept("Numbers from an old study.", title="Curve data"))
        self.write("cortex/concepts/island.md", concept("Unrelated, unlinked.", title="Island"))

    def test_co_recall_strengthens_pairs_and_fades(self):
        self.log(f"{ago(1)} recall q -> [[spacing]], [[forgetting]]",
                 f"{ago(91)} recall q -> [[spacing]], [[island]]",
                 f"{ago(1)} recall rehearse -> [[spacing]], [[curve-data]]")  # a quiz pairs nothing
        v = self.brain()
        w = v.edge_weights()
        pair = lambda a, b: w.get(frozenset((v.resolve(a), v.resolve(b))), 0)  # noqa: E731
        self.assertAlmostEqual(pair("spacing", "forgetting"), 0.5 ** (1 / 90), places=6)
        self.assertAlmostEqual(pair("spacing", "island"), 0.5 ** (91 / 90), places=6)
        self.assertEqual(pair("spacing", "curve-data"), 0)

    def test_recall_spreads_to_pages_the_question_never_names(self):
        rows = self.brain().recall("spacing effect")
        reached = {r["page"].stem: r for r in rows}
        self.assertTrue(reached["spacing"]["seed"])
        self.assertEqual((reached["forgetting"]["hop"], reached["forgetting"]["from"].stem), (1, "spacing"))
        self.assertEqual(reached["curve-data"]["hop"], 2)
        self.assertNotIn("island", reached)
        self.assertEqual(self.brain().recall("zebra"), [])

    def test_co_recall_links_unlinked_pages_weakly(self):
        self.log(f"{ago(1)} recall q -> [[spacing]], [[island]]")
        reached = {r["page"].stem for r in self.brain().recall("spacing effect")}
        self.assertIn("island", reached)

    def test_project_biases_recall(self):
        self.write("prefrontal/exam/CLAUDE.md", page("project", "Uses [[island]].", title="Exam", status="active"))
        plain = [r["page"].stem for r in self.brain().recall("spacing effect")]
        biased = [r["page"].stem for r in self.brain().recall("spacing effect", project="exam")]
        self.assertNotIn("island", plain)
        self.assertIn("island", biased)
        with self.assertRaises(ValueError):
            self.brain().recall("spacing", project="nope")

    def test_flags_stale_contradicted_and_dormant(self):
        self.write("cortex/concepts/forgetting.md", concept("Memory fades. [[curve-data]]", title="Forgetting curve",
                                                            updated=ago(200)))
        self.write("cortex/episodes/blog.md", page("episode", "Spacing is overrated (contradicts:: [[spacing]]).",
                                                   title="Blog", created=ago(1)))
        self.write("dormant/spacing-old.md", concept("Old spacing notes.", title="Spacing notes"))
        rows = {r["page"].stem: r for r in self.brain().recall("spacing", dormant=True)}
        self.assertIn("stale", rows["forgetting"]["flags"])
        self.assertIn("contradicted", rows["spacing"]["flags"])
        self.assertIn("dormant", rows["spacing-old"]["flags"])
        self.assertIsNone(rows["spacing-old"]["confidence"])

    def test_a_contradicted_page_names_what_says_the_opposite(self):
        # The flag alone left the other side to chance: a cut at --limit can drop the page that holds it.
        self.write("cortex/episodes/blog.md", page("episode", "Overrated (contradicts:: [[spacing]]).", title="Blog",
                                                   created=ago(1)))
        self.write("cortex/episodes/paper.md", page("episode", "No gain (contradicts:: [[spacing]]).", title="A paper",
                                                    created=ago(1)))
        rows = self.brain().recall("spacing effect", limit=1)
        self.assertEqual([(r["page"].stem, [p.stem for p in r["against"]]) for r in rows], [("spacing", ["blog", "paper"])])
        found = commands.call("recall", ["spacing", "effect", "--all"], root=self.root)["results"]
        self.assertEqual({r["page"]: r["against"] for r in found if r["against"]},
                         {"cortex/concepts/spacing.md": ["cortex/episodes/blog.md", "cortex/episodes/paper.md"]})
        out = run_brain(self.root, "recall", "spacing", "effect", "--limit", "1").stdout
        self.assertIn("\n           the opposite is said by: cortex/episodes/blog.md, cortex/episodes/paper.md\n", out)
        self.assertEqual(out.count("the opposite is said by"), 1)  # a page nothing contradicts has no such line

    def test_link_suggestions_and_at_hand(self):
        self.write("cortex/concepts/a.md", concept("[[spacing]] [[forgetting]]", title="A"))
        self.write("cortex/concepts/b.md", concept("[[spacing]] [[forgetting]]", title="B"))
        pairs = [(a.stem, b.stem) for a, b, _, _ in self.brain().link_suggestions()]
        self.assertIn(("a", "b"), pairs)
        self.assertEqual(self.brain().at_hand(), [])  # nothing recalled, no project: nothing to suggest
        self.log(f"{ago(1)} recall q -> [[spacing]]")
        self.assertIn("forgetting", [p.stem for p in self.brain().at_hand()])


class Confidence(TempBrain):
    def episode(self, slug, url, body="", **fields):
        self.write(f"cortex/episodes/{slug}.md", page("episode", body, title=slug, url=url, created=ago(5),
                                                      consolidated=ago(4), **fields))

    def test_levels_follow_independent_sources(self):
        self.write("cortex/concepts/idea.md", concept("From [[e1]], [[e2]] and [[e3]].", title="Idea"))
        self.episode("e1", "https://a.example/one")
        self.episode("e2", "https://a.example/two")
        level = lambda: (lambda v: v.confidence(v.resolve("idea")))(self.brain())  # noqa: E731
        self.assertEqual((level()["level"], level()["sources"], level()["independent"]), ("medium", 2, 1))
        self.episode("e3", "https://b.example/three")
        self.assertEqual(level()["level"], "high")
        self.episode("x", "https://c.example/x", origin="generated", body="[[idea]]")
        self.assertEqual(level()["sources"], 3)  # an /explore episode is never evidence

    def test_contradiction_flags_and_disputed_lowers(self):
        self.write("cortex/concepts/idea.md", concept("From [[e1]], [[e2]].", title="Idea"))
        self.episode("e1", "https://a.example/1")
        self.episode("e2", "https://b.example/2")
        self.write("cortex/episodes/blog.md", page("episode", "(contradicts:: [[idea]])", title="Blog"))
        v = self.brain()
        c = v.confidence(v.resolve("idea"))
        self.assertEqual((c["level"], c["sources"], c["contradicted"]), ("medium", 2, True))  # pending sleep
        self.write("cortex/concepts/idea.md", concept("From [[e1]], [[e2]].", title="Idea", tags="[disputed]"))
        v = self.brain()
        self.assertEqual(v.confidence(v.resolve("idea"))["level"], "low")

    def test_episodes_and_insights(self):
        self.episode("e1", "https://a.example/1")
        self.episode("e2", "https://b.example/2")
        self.write("cortex/concepts/idea.md", concept("From [[e1]], [[e2]].", title="Idea"))
        self.write("cortex/insights/big.md", page("insight", "Across [[idea]].", title="Big"))
        v = self.brain()
        self.assertEqual(v.confidence(v.resolve("e1"))["level"], "source")
        self.assertEqual(v.confidence(v.resolve("big"))["sources"], 2)  # through the pages it links


class SearchCommand(TempBrain):
    def brain_cmd(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"}
        return subprocess.run([sys.executable, os.path.join(ENGINE, "bin", "brain"), *args], capture_output=True,
                              text=True, cwd=self.root, env=env)

    def test_search_recall_and_since_run_through_brain(self):
        self.write("cortex/concepts/spacing.md", concept("Spread study. [[forgetting]]", title="Spacing",
                                                         created="2026-09-01"))
        self.write("cortex/concepts/forgetting.md", concept("Memory fades.", title="Forgetting", created="2026-08-01"))
        self.log("2026-09-02 recall what is spacing -> [[spacing]]")
        found = json.loads(self.brain_cmd("search", "spacing", "--json").stdout)
        self.assertEqual(found["results"][0]["page"], "cortex/concepts/spacing.md")
        recalled = json.loads(self.brain_cmd("recall", "spacing", "--json").stdout)["results"]
        self.assertEqual([r["page"] for r in recalled][:2], ["cortex/concepts/spacing.md",
                                                             "cortex/concepts/forgetting.md"])
        self.assertIn("hop", self.brain_cmd("recall", "spacing").stdout)
        since = json.loads(self.brain_cmd("since", "2026-09", "--json").stdout)
        self.assertEqual((since["created"], since["questions"]),
                         ({"concept": ["cortex/concepts/spacing.md"]}, ["2026-09-02 what is spacing"]))
        self.assertIn("nothing matches", self.brain_cmd("search", "zebra").stdout)


class AnswerTestSet(unittest.TestCase):
    """The fixture brain is a brain in its own right, and retrieval must not get worse on it."""

    def run_eval(self, *args):
        r = run_brain(None, "eval", "--json", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_fixture_passes_brain_check(self):
        r = run_brain(FIXTURE, "check", "--json")
        report = json.loads(r.stdout)
        self.assertEqual((report["broken"], report["schema"], report["orphans"]), ([], [], []))

    def test_retrieval_does_not_fall_below_the_baseline(self):
        with open(os.path.join(ENGINE, "eval", "baseline.json"), encoding="utf-8") as fh:
            base = json.load(fh)
        now = self.run_eval()["retrieval"]
        for mode in ("search", "recall"):
            self.assertGreaterEqual(now[mode]["hit_at_k"], base[mode]["hit_at_k"], mode)
            self.assertGreaterEqual(now[mode]["mrr"], base[mode]["mrr"], mode)
        self.assertGreaterEqual(now["recall"]["hit_at_k"], now["search"]["hit_at_k"])  # association must help

    def test_every_set_is_held_to_its_own_baseline_on_the_same_brain(self):
        with open(os.path.join(ENGINE, "eval", "baseline.json"), encoding="utf-8") as fh:
            base = json.load(fh)
        now = self.run_eval()["retrieval"]
        # numbers from a changed fixture are not comparable: rerun `brain eval --save-baseline` on purpose
        self.assertEqual(now["brain"], base["brain"])
        self.assertEqual(sorted(now["sets"]), ["first", "paraphrase", "standard"])
        self.assertEqual(now["sets"]["standard"]["recall"], now["recall"])
        for name, sets in now["sets"].items():
            for measure in ("hit_at_1", "hit_at_k", "mrr"):
                self.assertGreaterEqual(sets["recall"][measure], base["sets"][name]["recall"][measure], (name, measure))

    def test_the_questions_pages_answer_and_other_wordings_reach_the_paraphrases(self):
        """Done when: paraphrase recall hit@1 is 0.875 or better (22); its hit@5 is 1.000 and q10 finds forgetting-curve (23)."""
        now, plain = self.run_eval()["retrieval"], self.run_eval("--no-also")["retrieval"]
        self.assertEqual((now["reworded"], plain["reworded"]), (37, 0))
        reached = now["sets"]["paraphrase"]["recall"]
        self.assertGreaterEqual(reached["hit_at_1"], 0.875)
        self.assertEqual((reached["hit_at_k"], reached["all_at_k"]), (1.0, 8))
        q10 = {row["id"]: row for row in now["per_question"]["recall"]}["q10"]
        self.assertIn("forgetting-curve", q10["top"])
        # What the other wordings buy, on the same pages: the last paraphrase, and q10. The field alone gives hit@1.
        self.assertEqual((plain["sets"]["paraphrase"]["recall"]["hit_at_1"], plain["sets"]["paraphrase"]["recall"]["hit_at_k"]),
                         (0.875, 0.938))
        self.assertNotIn("forgetting-curve", {row["id"]: row for row in plain["per_question"]["recall"]}["q10"]["top"])
        # No wording of a question the brain does not cover makes it look covered.
        listed = [[u["id"] for u in run["uncovered"] if u["recall_results"]] for run in (now, plain)]
        self.assertEqual(listed, [["u05", "u06"], ["u05", "u06"]])
        with open(os.path.join(ENGINE, "eval", "questions.json"), encoding="utf-8") as fh:
            asked = json.load(fh)["questions"]
        self.assertTrue(all(len(q["also"]) == 2 for q in asked))

    def recall_cmd(self, *args):
        r = run_brain(FIXTURE, "recall", *args, env=dict(os.environ, BRAIN_CACHE="0"))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_recall_stops_where_the_match_stops(self):
        vault = vaultlib.Vault(FIXTURE)
        every = vault.recall("What is the ease factor?")
        cut = vault.recall("What is the ease factor?", floor=vault.tuning.recall_floor, abstain=True)
        self.assertEqual(([r["page"].stem for r in cut], len(every)), (["wozniak-sm2"], 10))
        self.assertTrue(all(r["score"] < vault.tuning.recall_floor * every[0]["score"] for r in every[1:]))
        out = self.recall_cmd("What is the ease factor?")
        self.assertIn("wozniak-sm2.md", out)
        self.assertNotIn("supermemo.md", out)
        self.assertIn("weaker matches are cut (--all lists them)", out)
        self.assertIn("supermemo.md", self.recall_cmd("What is the ease factor?", "--all"))

    def test_recall_lists_nothing_when_the_best_page_holds_too_little_of_the_question(self):
        vault, asked = vaultlib.Vault(FIXTURE), "What did the 2024 sleep and memory consolidation trials find?"
        best = vault.search(asked)[0][0]
        self.assertLess(vault.coverage(asked, best), vault.tuning.min_coverage)
        self.assertEqual(vault.recall(asked, floor=vault.tuning.recall_floor, abstain=True), [])
        out = self.recall_cmd(asked)
        self.assertTrue(out.startswith("recall: no confident match for"), out)
        self.assertIn(f"its words barely reach {best.rel}", out)
        self.assertEqual(len(out.splitlines()), 1)  # one line, no summaries
        self.assertIn(best.rel, json.loads(self.recall_cmd(asked, "--json"))["weak"])
        self.assertIn("hit;", self.recall_cmd(asked, "--all"))
        self.assertEqual(vault.coverage("What is the forgetting curve?", vault.resolve("forgetting-curve")), 1.0)
        self.assertIn("nothing matches", self.recall_cmd("What is the capital of Australia?"))
        now = self.run_eval()["retrieval"]
        self.assertEqual([u["recall_results"] for u in now["uncovered"]], [0, 0, 0, 0, 3, 4])  # not every one is caught
        self.assertLess(now["recall"]["rows"], 5 * now["recall"]["questions"])

    def test_an_idea_held_on_an_episode_is_listed_when_the_question_names_it(self):
        vault = vaultlib.Vault(FIXTURE)
        held = vault.held_ideas("What is the illusion of fluency?")
        self.assertEqual([(h["name"], h["sources"], len(h["episodes"])) for h in held], [("Illusion of fluency", 2, 2)])
        self.assertEqual(held[0]["note"], "what feels easy while learning is taken for learning")
        self.assertEqual([h["name"] for h in vault.held_ideas("person action object")], ["Person-action-object"])
        # a common word of a name is not the name; an idea with a page is that page's business
        self.assertEqual(vault.held_ideas("Does the method work for learning?"), [])
        self.assertEqual(vault.held_ideas("What is the spacing effect?"), [])
        out = self.recall_cmd("What is the ease factor?")
        self.assertIn("held ideas (no page yet; cite the episode and say how many sources):", out)
        self.assertIn("  Ease factor - a per-card multiplier for the next review interval  "
                      "[cortex/episodes/wozniak-sm2.md; 1 source]", out)
        self.assertNotIn("held ideas", self.recall_cmd("What is the forgetting curve?"))
        self.assertEqual(json.loads(self.recall_cmd("ease factor", "--json"))["held"][0]["name"], "Ease factor")
        now = self.run_eval()["retrieval"]["held"]
        self.assertEqual((now["questions"], now["listed"]), (2, 2))
        self.assertLess(now["row_bytes"] * 10, now["episode_bytes"])

    def test_the_sets_are_what_they_say(self):
        with open(os.path.join(ENGINE, "eval", "questions.json"), encoding="utf-8") as fh:
            spec = json.load(fh)
        vault = vaultlib.Vault(FIXTURE)
        by_set = {}
        for q in spec["questions"]:
            by_set.setdefault(q.get("set", "standard"), []).append(q)
        for q in by_set["paraphrase"]:  # no word of the page's names in the question
            for stem in q["expect"]:
                page = vault.resolve(stem)
                names = set(vaultlib.tokens(page.title + " " + " ".join(page.aliases)))
                self.assertEqual(names & set(vaultlib.tokens(q["question"])), set(), q["id"])
        defined = {q["expect"][0] for q in by_set["first"] if vault.resolve(q["expect"][0]).type == "concept"}
        self.assertEqual(len(defined), 3)
        for stem in defined:  # a short page that defines the term, and longer ones that use it more
            page = vault.resolve(stem)
            uses = lambda p: p.body.lower().count(page.title.lower())  # noqa: E731
            rivals = [p for p in vault.of_type("episode") if len(p.body) > len(page.body) and uses(p) > uses(page)]
            self.assertGreaterEqual(len(rivals), 2, stem)
        sources = [q for q in by_set["first"] if vault.resolve(q["expect"][0]).type == "episode"]
        self.assertEqual(len(sources), 2)  # a question about one source wants that source first

    def test_bytes_read_per_question_are_fixed_on_the_fixture(self):
        with open(os.path.join(ENGINE, "eval", "baseline.json"), encoding="utf-8") as fh:
            base = json.load(fh)
        now = self.run_eval()["retrieval"]
        rows = {r["id"]: r for r in now["per_question"]["recall"]}
        sizes = {stem: os.path.getsize(os.path.join(FIXTURE, "cortex", kind, stem + ".md"))
                 for kind in os.listdir(os.path.join(FIXTURE, "cortex"))
                 for stem in (os.path.splitext(f)[0] for f in os.listdir(os.path.join(FIXTURE, "cortex", kind)))}
        q02 = rows["q02"]
        self.assertEqual(q02["bytes"], sum(sizes[stem] for stem in q02["top"]))
        self.assertEqual(q02["needed"], sizes["hermann-ebbinghaus"])
        for mode in ("search", "recall"):
            self.assertEqual(now[mode]["bytes_read"],
                             sum(r["bytes"] for r in now["per_question"][mode] if r["set"] == "standard"))
            # a change here is a change in what an answer costs: rerun `brain eval --save-baseline` on purpose
            self.assertEqual((now[mode]["bytes_read"], now[mode]["bytes_needed"], now[mode]["bytes_by_summary"]),
                             (base[mode]["bytes_read"], base[mode]["bytes_needed"], base[mode]["bytes_by_summary"]), mode)
            self.assertEqual((now[mode]["bytes_by_section"], now[mode]["sectioned"]),
                             (base[mode]["bytes_by_section"], base[mode]["sectioned"]), mode)
            self.assertEqual(now[mode]["unsummarised"], 0, "every fixture page says what it holds")
            self.assertLess(now[mode]["bytes_by_summary"], now[mode]["bytes_read"])  # or the summaries cost more than they save
        # Reading the section recall names, in place of its page: under 2,500 bytes a question, from 3,078.
        recall = now["recall"]
        self.assertEqual(recall["bytes_by_section"], sum(r["by_section"] for r in now["per_question"]["recall"]
                                                         if r["set"] == "standard"))
        self.assertLess(recall["bytes_by_section"] / recall["questions"], 2500)
        self.assertGreater(recall["bytes_read"] / recall["questions"], 3000)
        self.assertLess(q02["by_section"], q02["bytes"])
        self.assertIn("\n  recall  by section: 10528, 809 a question, when the section recall names is read in place of "
                      "its page (49 of 49 rows name one)   (baseline 10528)\n", run_brain(None, "eval").stdout)
        self.assertGreaterEqual(now["recall"]["bytes_read"], now["recall"]["bytes_needed"] * now["recall"]["hit_at_k"])

    def test_answers_are_scored_for_citations_and_admitted_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "answers.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"q01": "Retention drops fast [[forgetting-curve]], measured in [[ebbinghaus-1885]].",
                           "q09": "A multiplier [[wozniak-sm2]], see also [[anki]] and [[testing-effect]].",
                           "u01": "Not covered by any page here.",
                           "u02": "Probably helps, see [[testing-effect]]."}, fh)
            a = self.run_eval("--answers", path)["answers"]
        rows = {r["id"]: r for r in a["per_question"]}
        self.assertEqual((rows["q01"]["recall"], rows["q01"]["precision"]), (1.0, 1.0))
        self.assertEqual(rows["q09"]["extra"], ["anki", "testing-effect"])
        self.assertEqual((rows["u01"]["pass"], rows["u02"]["pass"]), (True, False))
        self.assertEqual(a["uncovered_passed"], "1/2")


class Synthetic(unittest.TestCase):
    def test_a_synthetic_brain_passes_every_contract_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            sys.path.insert(0, SCRIPTS)
            import synth
            a, b = os.path.join(tmp, "a"), os.path.join(tmp, "b")
            synth.build(a, pages=120, seed=7, days=200, today=TODAY)
            synth.build(b, pages=120, seed=7, days=200, today=TODAY)
            r = run_brain(a, "check", "--json")
            report = json.loads(r.stdout)
            self.assertEqual((r.returncode, report["broken"], report["schema"], report["claims"]), (0, [], [], []))
            v = vaultlib.Vault(a, today=TODAY)
            self.assertEqual(len(v.knowledge), 120)
            self.assertGreater(v.brier()["n"], 0)
            self.assertLess(len(v.orphans()) / len(v.linked_to()), 0.15)
            for rel in ("hippocampus/log.md", "cortex/concepts/concept-3.md"):
                with open(os.path.join(a, rel)) as x, open(os.path.join(b, rel)) as y:
                    self.assertEqual(x.read(), y.read(), rel)

    def test_large_brains_estimate_bridges(self):
        with tempfile.TemporaryDirectory() as tmp:
            sys.path.insert(0, SCRIPTS)
            import synth
            synth.build(os.path.join(tmp, "big"), pages=600, seed=1, days=300, today=TODAY)
            self.assertTrue(vaultlib.Vault(os.path.join(tmp, "big"), today=TODAY).betweenness_estimated())


class PromptRecall(TempBrain):
    def setUp(self):
        super().setUp()
        self.write("cortex/concepts/spacing.md", page("concept", "Study spread over days lasts longer.\n",
                                                      title="Spacing effect", summary="Spread study lasts longer."))
        self.write("cortex/concepts/testing.md", page("concept", "Recalling beats rereading.\n",
                                                      title="Testing effect", summary="Recall beats rereading."))

    def test_only_a_well_covered_question_gets_pages(self):
        v = self.brain()
        rows, why = v.prompt_recall("What is the spacing effect?")
        self.assertEqual(([p.stem for p, _ in rows][0], why), ("spacing", "match (1.00)"))
        self.assertEqual(rows[0][1], "cortex/concepts/spacing.md: Spread study lasts longer.")
        for prompt, why in (("/ask what is the spacing effect?", "command"), ("spacing effect?", "short"),
                            ("add the spacing effect to the plan", "not a question"),
                            ("What is the capital of France?", "no word matches"),
                            ("How does the spacing of kubernetes pods across nodes work?", "weak match")):
            rows, got = v.prompt_recall(prompt)
            self.assertEqual((rows, got.split(" (")[0]), ([], why), prompt)
        self.assertLessEqual(sum(len(line) for _, line in v.prompt_recall("What is the spacing effect?")[0]),
                             v.tuning.prompt_chars)

    def test_the_hook_is_off_by_default_bounded_and_logs_each_decision(self):
        asked = {"prompt": "What is the spacing effect?"}
        self.assertEqual(self.run_hook("prompt_recall.py", asked, BRAIN_PROMPT_RECALL="0").stdout, "")
        self.assertFalse(os.path.exists(os.path.join(self.root, ".cache", "prompt-recall.log")))
        out = self.run_hook("prompt_recall.py", asked, BRAIN_PROMPT_RECALL="1")
        self.assertEqual(out.returncode, 0)
        self.assertIn("cortex/concepts/spacing.md: Spread study lasts longer.", out.stdout)
        self.assertEqual(self.run_hook("prompt_recall.py", {"prompt": "continue next"}, BRAIN_PROMPT_RECALL="1").stdout, "")
        broken = subprocess.run([sys.executable, os.path.join(ENGINE, "hooks", "prompt_recall.py")], input="not json",
                                capture_output=True, text=True,
                                env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root, BRAIN_PROMPT_RECALL="1"))
        self.assertEqual((broken.returncode, broken.stdout), (0, ""))  # never in the way of a prompt
        with open(os.path.join(self.root, ".cache", "prompt-recall.log"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].endswith("match (1.00) | What is the spacing effect?"), lines[0])
        self.assertTrue(lines[1].endswith(" 0 short | continue next"), lines[1])


class OwnQuestionSet(TempBrain):
    def test_a_question_set_for_ones_own_brain_is_drafted_checked_and_keeps_its_own_baseline(self):
        self.write("cortex/concepts/spacing.md", page("concept", "Study spread over days lasts longer.\n",
                                                      title="Spacing effect", summary="Spread study lasts."))
        self.write("cortex/concepts/testing.md", page("concept", "Recalling beats rereading.\n",
                                                      title="Testing effect", summary="Recall beats rereading."))
        self.write("cortex/episodes/e1.md", page("episode", "One study.\n", title="A study"))
        questions = os.path.join(self.root, "motor", "eval-questions.json")
        self.write("motor/eval-questions.json", json.dumps({"questions": [
            {"id": "o01", "set": "paraphrase", "question": "Why does the spacing of study matter?",
             "expect": ["spacing"]},
            {"id": "o03", "set": "paraphrase", "question": "", "expect": ["gone"]}]}))

        def run(*args):
            return run_brain(None, "eval", "--root", self.root, "--questions", questions, *args, env=dict(os.environ, BRAIN_CACHE="0"))

        drafted = json.loads(run("--draft", "5").stdout)["questions"]
        # pages no question expects yet, concepts before episodes, ids that are free
        self.assertEqual([(q["id"], q["expect"]) for q in drafted], [("o02", ["testing"]), ("o04", ["e1"])])
        self.assertEqual((drafted[0]["set"], drafted[0]["question"], drafted[0]["summary"], drafted[0]["avoid"]),
                         ("paraphrase", "", "Recall beats rereading.", ["effect", "testing"]))
        report = run().stdout
        self.assertIn("retrieval over 1 covered questions", report)  # the empty question is skipped
        self.assertEqual(json.loads(run("--json").stdout)["retrieval"]["reworded"], 0)  # no question carries another wording
        self.assertIn("question o01: not a paraphrase, it uses spacing from [[spacing]]", report)
        self.assertNotIn("uncovered", report)
        self.assertIn("baseline saved to " + os.path.join(self.root, "motor", "eval-questions-baseline.json"),
                      run("--save-baseline").stdout)
        with open(os.path.join(ENGINE, "eval", "baseline.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["sets"]["standard"]["recall"]["questions"], 13)  # the engine's is untouched
        # Another wording of a question is carried with it and passed to recall; one that is not text is said.
        self.write("motor/eval-questions.json", json.dumps({"questions": [
            {"id": "o01", "question": "Which study lasts longer?", "expect": ["testing"], "also": ["Does recalling beat rereading?"]},
            {"id": "o02", "question": "Why wait between sessions?", "expect": ["spacing"], "also": "spread study"}]}))
        found = json.loads(run("--json").stdout)
        self.assertEqual(found["problems"], ["o02: `also` is a list of other wordings of the question, each some text"])
        ranks = {row["id"]: row["rank"] for row in found["retrieval"]["per_question"]["recall"]}
        self.assertEqual(found["retrieval"]["reworded"], 1)
        self.assertIn(ranks["o01"], (1, 2))  # the page its own words reach, and the one the other wording does
        alone = json.loads(run("--json", "--no-also").stdout)["retrieval"]
        self.assertEqual((alone["reworded"], alone["per_question"]["recall"][0]["rank"]), (0, None))  # its own words miss it
        r = run("--no-also", "--save-baseline")
        self.assertEqual((r.returncode, r.stderr), (1, "brain eval: a baseline holds the numbers of the questions as they "
                                                       "are asked, their other wordings included; leave --no-also or "
                                                       "--save-baseline out\n"))


class TheSectionToReadFirst(TempBrain):
    """Recall names, for each page, the section that holds the words of the question its title does not."""

    FIRST = "## In one paragraph\n\nStudy spread over sessions lasts.\nThe best gap depends on the test."

    def setUp(self):
        super().setUp()
        self.spacing = self.write("cortex/concepts/spacing.md", concept(
            f"\n# Spacing effect\n\n{self.FIRST}\n\n## What argues against it\n\nNothing yet.\n\n## Related\n\n"
            "[[testing]]\n", title="Spacing effect", summary="Spread study lasts."))
        self.write("cortex/concepts/testing.md", concept("\n# Testing effect\n\n## In one paragraph\n\nRecalling beats "
                                                         "rereading.\n", title="Testing effect", summary="Recall wins."))
        self.write("cortex/concepts/sleep.md", concept("\n## Before\n\nRest helps.\n\n## After\n\nRest helps again.\n",
                                                       title="Sleep", summary="Rest."))

    def sections(self, question):
        return {r["page"].stem: r["section"] for r in self.brain().recall(question)}

    def test_it_is_where_the_question_s_own_words_are(self):
        asked = self.sections("how long should the gap be")
        self.assertEqual(asked["spacing"], {"heading": "In one paragraph", "line": 12, "end": 15,
                                            "bytes": len(self.FIRST.encode("utf-8"))})
        with open(self.spacing, encoding="utf-8") as fh:
            self.assertEqual("\n".join(fh.read().splitlines()[11:15]), self.FIRST)  # those lines are that section
        self.assertIsNone(asked["testing"])  # reached by a link: no word of the question is on it
        # A heading is part of its section, and says what the section answers.
        self.assertEqual(self.sections("what argues against the spacing effect")["spacing"]["heading"],
                         "What argues against it")
        # A page the question names is its subject: it is read from the top, whatever its sections repeat.
        self.assertIsNone(self.sections("What is the spacing effect?")["spacing"])
        self.assertEqual(self.sections("does rest help")["sleep"]["heading"], "Before")  # of two that hold as much, the first

    def test_recall_prints_it_with_its_lines_and_carries_it_as_data(self):
        out = run_brain(self.root, "recall", "how long should the gap be", "--all").stdout
        self.assertIn("\n           hit; low: 0 sources, 0 independent\n           read first: ## In one paragraph (lines 12-15)\n",
                      out)
        self.assertEqual(out.count("read first:"), 1)  # the page reached by a link has no line of the kind
        rows = json.loads(run_brain(self.root, "recall", "how long should the gap be", "--all", "--json").stdout)["results"]
        self.assertEqual([(r["page"], r["section"] and r["section"]["heading"]) for r in rows],
                         [("cortex/concepts/spacing.md", "In one paragraph"), ("cortex/concepts/testing.md", None)])
        self.assertNotIn("read first:", run_brain(self.root, "search", "gap").stdout)  # search lists pages, no more


class TheBrainAsItWas(TempBrain):
    """Vault.as_of: the same pages, and only what the log had taught up to one of its lines."""

    def setUp(self):
        super().setUp()
        for name in ("alpha", "beta", "gamma"):
            self.write(f"cortex/concepts/{name}.md", concept(f"{name.title()} is a word.", title=name.title()))
        self.log("2026-08-01 recall what is alpha -> [[alpha]], [[beta]]", "2026-08-10 recall rehearse -> [[gamma]]",
                 "2026-09-01 ingest senses/a.md -> 1 episode", "2026-09-10 recall alpha again -> [[alpha]]")

    def test_a_copy_knows_nothing_the_log_taught_after_its_line(self):
        v = self.brain()
        alpha, beta, gamma = (v.resolve(n) for n in ("alpha", "beta", "gamma"))
        pair = frozenset((alpha, beta))
        unused = v.as_of(0)
        self.assertEqual((unused.events, unused.recall_count, unused.edge_weights(), unused.strength(gamma)), ([], {}, {}, 0))
        self.assertEqual(unused.association_graph(), {alpha: {}, beta: {}, gamma: {}})
        self.assertIs(unused.pages, v.pages)  # nothing is read again
        first = v.as_of(1, today=datetime.date(2026, 8, 1))
        self.assertEqual((first.recall_count, first.edge_weights(), first.strength(gamma)),
                         ({alpha: 1, beta: 1}, {pair: 1.0}, 0))  # judged on its own day: nothing has faded yet
        self.assertEqual(v.as_of(1).edge_weights(), {pair: 0.5 ** (63 / 90)})  # judged from today
        self.assertEqual((v.as_of(2).strength(gamma), v.as_of(2).today), (1, TODAY))
        # The brain the copies were made from is as it was, and a copy of everything is its equal.
        self.assertEqual((v.recall_count, v.edge_weights(), len(v.events)), ({alpha: 2, beta: 1, gamma: 1},
                                                                              {pair: 0.5 ** (63 / 90)}, 4))
        whole = v.as_of(len(v.events))
        self.assertEqual((whole.recall_count, whole.association_graph()), (v.recall_count, v.association_graph()))
        self.assertEqual(v.as_of(3).as_of(1).recall_count, v.as_of(1).recall_count)
        tried = vaultlib.Vault(self.root, today=TODAY, tuning={"hebbian_half_life": 63}).as_of(1)
        self.assertEqual(tried.edge_weights(), {frozenset((tried.resolve("alpha"), tried.resolve("beta"))): 0.5})

    def test_a_copy_is_lifted_by_the_recalls_before_its_line_and_by_none_after(self):
        v = vaultlib.Vault(self.root, today=TODAY, tuning={"use_lift": 0.2, "use_full": 1})
        alpha, beta = v.resolve("alpha"), v.resolve("beta")

        def score(vault):
            return vault.recall("alpha", hops=0)[0]["score"]

        # Both of alpha's recalls, as they stand today; gamma's line is a rehearsal and counts for none.
        self.assertEqual(v.use_weights(), {alpha: 0.5 ** (63 / 90) + 0.5 ** (23 / 90), beta: 0.5 ** (63 / 90)})
        self.assertEqual(score(v), 1.2)  # more than use_full of them: the whole lift
        unused = v.as_of(0)  # the weights above were worked out for the whole log, and are not handed on
        self.assertEqual((unused.use_weights(), unused.lift_from_use(alpha), score(unused)), ({}, 0.0, 1.0))
        then = v.as_of(3, today=datetime.date(2026, 9, 10))  # as the last question was asked, its own line unknown
        self.assertEqual(then.use_weights(), {alpha: 0.5 ** (40 / 90), beta: 0.5 ** (40 / 90)})
        self.assertEqual(score(then), round(1 + 0.2 * 0.5 ** (40 / 90), 4))
        self.assertEqual(v.use_weights()[alpha], 0.5 ** (63 / 90) + 0.5 ** (23 / 90))  # the brain itself is as it was


class ReplayOfTheLog(TempBrain):
    """`brain eval --from-log`: every question the log holds, asked again of the brain as it was that day."""

    def setUp(self):
        super().setUp()
        self.write("cortex/concepts/alpha.md", concept("Alpha is a word.", title="Alpha", summary="What alpha is."))
        self.write("cortex/concepts/beta.md", concept("Nothing of the word here.", title="Beta", summary="What beta is."))
        # A page found only by association comes back at 0.4 of the best row, which is where recall cuts by
        # default: this brain cuts lower, so that what the test shows does not hang on the last decimal.
        self.write("hippocampus/tuning.md", page("tuning", "\n## Overrides\n\n- recall_floor = 0.3\n"))
        self.log("2026-08-01 recall what is alpha -> [[alpha]], [[beta]]",   # nothing ties beta to alpha yet
                 "2026-08-20 recall more on alpha -> [[alpha]], [[beta]]",   # the line above does
                 "2026-08-21 recall rehearse -> [[alpha]]", "2026-08-22 rehearse missed -> [[alpha]]",
                 "2026-08-25 recall the capital of australia -> none",
                 "2026-08-26 recall alpha and the weather -> none",
                 "2026-08-27 recall an old name -> [[renamed-away]]",
                 "2026-08-28 recall a third on alpha -> [[alpha]], [[renamed-away]]",
                 "2026-08-29 recall -> [[alpha]]", "2026-02-30 recall on a day that is none -> [[alpha]]",
                 "2026-08-30 recall with no arrow at all")

    def replay(self, *args):
        with mock.patch.dict(os.environ, {"BRAIN_CACHE": "0"}):  # a call in this process would leave the cache open
            return commands.call("eval", ["--from-log", "--root", self.root, *args])

    def text(self, *args, root=None, **kw):
        r = run_brain(root, "eval", "--from-log", *args, **kw)
        return r.returncode, r.stdout + r.stderr

    def test_a_question_is_asked_without_the_line_that_recorded_its_answer(self):
        result = self.replay()
        asked = result["from_log"]["questions"]
        self.assertEqual([(q["date"], q["question"], q["expect"]) for q in asked], [
            ("2026-08-01", "what is alpha", ["alpha", "beta"]), ("2026-08-20", "more on alpha", ["alpha", "beta"]),
            ("2026-08-25", "the capital of australia", []), ("2026-08-26", "alpha and the weather", []),
            ("2026-08-28", "a third on alpha", ["alpha"])])  # a rehearsal is no question; a page gone since is not expected
        # Its place among the log's lines in the order they happened: the line of no real day sorts first.
        self.assertEqual([q["id"] for q in asked], ["2026-08-01#2", "2026-08-20#3", "2026-08-25#6", "2026-08-26#7",
                                                    "2026-08-28#9"])
        r = result["retrieval"]
        rows = {row["id"]: row for row in r["per_question"]["recall"]}
        # On its day nothing had been recalled with alpha: beta is missed. Nineteen days on, the first line had
        # taught the pair, and beta comes back with alpha though no word of the question is on its page.
        self.assertEqual((rows["2026-08-01#2"]["top"], rows["2026-08-01#2"]["missed"]), (["alpha"], ["beta"]))
        self.assertEqual((rows["2026-08-20#3"]["top"], rows["2026-08-20#3"]["missed"]), (["alpha", "beta"], []))
        self.assertEqual((r["recall"]["questions"], r["recall"]["hit_at_1"], r["recall"]["hit_at_k"], r["recall"]["all_at_k"]),
                         (3, 1.0, 0.833, 2))
        self.assertEqual((r["search"]["hit_at_k"], r["search"]["all_at_k"]), (0.667, 1))  # words alone never reach beta
        self.assertEqual([(u["id"], u["search_results"], bool(u["recall_results"])) for u in r["uncovered"]],
                         [("2026-08-25#6", 0, False), ("2026-08-26#7", 1, True)])
        self.assertEqual(result["problems"], ["not replayed, it names only pages that are not here: "
                                              "2026-08-27 recall an old name -> [[renamed-away]]"])
        self.assertEqual((result["from_log"]["log_lines"], result["from_log"]["limits"]), (11, list(eval_script.LIMITS)))
        json.dumps(result)

    def test_the_text_gives_the_two_limits_then_the_scores_then_what_went_wrong(self):
        code, out = self.text("--root", self.root)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[:8], [
            "recall replayed from the log: 3 questions that named pages, 2 that named none, each as the brain was "
            "that day, top 5",
            "  limit: these are the questions recall already answered on the day they were asked: a fall is a "
            "regression, a high number is not quality",
            "  limit: each is replayed against the pages as they are now, not as they were that day",
            "  not replayed, it names only pages that are not here: 2026-08-27 recall an old name -> [[renamed-away]]",
            "  search  hit@1 1.000   hit@5 0.667   all 1/3   mrr 1.000",
            "  recall  hit@1 1.000   hit@5 0.833   all 2/3   mrr 1.000",
            "  recall missed a page of 1 of 3:",
            "    2026-08-01 what is alpha -> beta; alpha came first"])
        self.assertEqual(out.splitlines()[8:], ["  uncovered questions recall still lists pages for: 1 of 2",
                                                "    2026-08-26 alpha and the weather (2 pages)"])

    def test_it_is_the_brain_one_is_in_unless_another_is_named(self):
        self.assertEqual(self.text(cwd=self.root), self.text("--root", self.root))
        self.assertEqual(self.text(root=self.root), self.text("--root", self.root))  # $BRAIN_ROOT
        with tempfile.TemporaryDirectory() as elsewhere:
            code, out = self.text(cwd=elsewhere)
            self.assertEqual((code, out.split(" (")[0]), (1, "brain: no brain here"))
        for extra in (["--draft", "2"], ["--answers", "a.json"], ["--questions", "mine.json"]):
            with self.assertRaises(commands.Refused) as refused:
                self.replay(*extra)
            self.assertEqual(str(refused.exception), "brain eval --from-log: the questions are the log's own; it takes no "
                                                     "--questions, --answers or --draft")

    def test_its_baseline_is_kept_in_the_brain_and_a_longer_log_is_said(self):
        kept = os.path.join(self.root, "motor", "eval-from-log-baseline.json")
        code, out = self.text("--root", self.root, "--save-baseline")
        self.assertEqual((code, out.splitlines()[-1]), (0, f"baseline saved to {kept}"))
        with open(kept, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual((saved["recall"]["questions"], saved["recall"]["hit_at_k"], saved["k"]), (3, 0.833, 5))
        again = self.text("--root", self.root)[1]
        self.assertIn("  recall  hit@1 1.000   hit@5 0.833   all 2/3   mrr 1.000   (baseline hit 0.833, mrr 1.0)\n", again)
        self.assertNotIn("not comparable", again)
        commands.call("log", ["recall", "a fourth on alpha", "--pages", "alpha"], root=self.root)
        self.assertIn("  the pages or the log changed since the baseline was saved (3 questions then, 4 now): its numbers "
                      "are not comparable\n", self.text("--root", self.root)[1])
        with open(os.path.join(ENGINE, "eval", "baseline.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["sets"]["standard"]["recall"]["questions"], 13)  # the engine's is untouched

    def test_a_value_is_tried_on_the_log_s_questions_too(self):
        tried = self.replay("--set", "recall_floor=0.9")
        self.assertEqual(tried["set"], {"recall_floor": {"value": 0.9, "was": 0.3}})
        self.assertEqual(tried["retrieval"]["recall"]["hit_at_k"], 0.667)  # beta, found by association, is cut again
        self.assertIn("\n  tried with recall_floor = 0.9 (the brain's own: 0.3); nothing was written\n",
                      self.text("--root", self.root, "--set", "recall_floor=0.9")[1])
        with self.assertRaises(commands.Refused):
            self.replay("--set", "recall_floor=0.9", "--save-baseline")
        self.assertFalse(os.path.exists(os.path.join(self.root, "motor")))

    def test_a_long_list_is_cut_in_the_text_and_whole_in_the_data(self):
        lines = []
        for n in range(1, 13):  # twelve questions, each naming a page nothing had tied to alpha before
            self.write(f"cortex/concepts/z{n}.md", concept("Nothing of the word here.", title=f"Z{n}"))
            lines.append(f"2026-09-{n:02d} recall alpha number {n} -> [[alpha]], [[z{n}]]")
        self.log(*lines)
        out = self.text("--root", self.root)[1].splitlines()
        self.assertEqual(out[5:7], ["  recall missed a page of 12 of 12:", "    2026-09-01 alpha number 1 -> z1; alpha came first"])
        self.assertEqual((len(out), out[-1]), (17, "    and 2 more (--json lists them)"))  # and no uncovered question
        self.assertEqual(len([row for row in self.replay()["retrieval"]["per_question"]["recall"] if row["missed"]]), 12)

    def test_a_log_with_no_question_says_so_and_one_that_is_all_found_lists_nothing(self):
        self.log("2026-08-01 ingest senses/a.md -> 1 episode", "2026-08-21 recall rehearse -> [[alpha]]")
        self.assertEqual(self.text("--root", self.root), (0, "recall replayed from the log: no question in it yet (2 lines; "
                                                             "a question is a recall line that is not a rehearsal)\n"))
        self.log("2026-08-01 recall what is alpha -> [[alpha]]")
        self.assertEqual(self.text("--root", self.root)[1].splitlines()[3:], [
            "  search  hit@1 1.000   hit@5 1.000   all 1/1   mrr 1.000",
            "  recall  hit@1 1.000   hit@5 1.000   all 1/1   mrr 1.000"])

    def test_it_runs_on_a_synthetic_brain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "brain")
            synth.build(root, 60, seed=5, today=TODAY)
            with open(os.path.join(root, "hippocampus", "log.md"), encoding="utf-8") as fh:
                questions = [line for line in fh if re.match(r"\d{4}-\d\d-\d\d recall (?!rehearse )", line)]
            first = self.replay("--root", root)  # the last --root is the one that counts
            self.assertEqual(len(first["from_log"]["questions"]), len(questions))
            self.assertEqual((first["retrieval"]["recall"]["questions"], first["retrieval"]["uncovered"], first["problems"]),
                             (len(questions), [], []))
            self.assertEqual(self.replay("--root", root), first)  # the same log, the same numbers
            self.assertFalse(os.path.exists(os.path.join(root, "motor", "eval-from-log-baseline.json")))


class AskedAndNotAnswered(TempBrain):
    """`brain introspect --gaps`: the questions recall named no page for, grouped by the rare words they share."""

    def setUp(self):
        super().setUp()
        self.write("cortex/concepts/spacing.md", concept("Study spread over days lasts.", title="Spacing effect"))
        self.write("cortex/episodes/e.md", page("episode", "A talk.\n\n## Candidates\n\n- Cubism - a style in art\n",
                                                title="A talk", created=ago(20), updated=ago(20)))
        self.write("hippocampus/index.md", page("index", "\n# Index\n\n## Gaps\n\n- [[picasso]]\n"))
        self.log("2026-08-01 recall which painters did picasso learn from -> none",
                 "2026-08-02 recall rehearse -> [[spacing]]",
                 "2026-08-09 recall which painters did picasso learn from -> none",  # asked again: the same gap
                 "2026-08-12 recall when was picasso born -> none",                  # another wording about him
                 "2026-08-15 recall what is the capital of australia -> none",
                 "2026-08-20 recall where is canberra -> none",
                 "2026-08-25 recall is canberra the capital -> [[spacing]]",         # answered since
                 "2026-08-26 recall what is cubism -> none",
                 "2026-08-27 recall -> none", "2026-08-28 recall with no arrow at all")

    def test_a_question_asked_twice_is_one_gap_and_an_answer_closes_one(self):
        self.assertEqual(self.brain().unanswered(), [
            {"words": ["picasso"], "asked": 3, "first": "2026-08-01", "last": "2026-08-12", "held": [],
             "questions": ["which painters did picasso learn from", "when was picasso born"], "index_gaps": ["picasso"]},
            # Of two asked once, the one asked last comes first. Every page that holds the word is one of
            # two here, so `cubism` is not rare: the question is known by all its words, and names a held idea.
            {"words": ["cubism"], "asked": 1, "first": "2026-08-26", "last": "2026-08-26", "held": ["Cubism"],
             "questions": ["what is cubism"], "index_gaps": []},
            # `capital` was in the answered question; `australia` was not, so this one is still open.
            {"words": ["australia", "capital"], "asked": 1, "first": "2026-08-15", "last": "2026-08-15", "held": [],
             "questions": ["what is the capital of australia"], "index_gaps": []}])

    def test_the_text_lists_each_gap_with_where_to_start(self):
        out = run_brain(self.root, "introspect", "--gaps").stdout
        self.assertIn("\nasked and not answered (recall named no page; most asked first): 3\n"
                      "    3x  picasso  (last 2026-08-12)\n"
                      "        which painters did picasso learn from\n"
                      "        when was picasso born\n"
                      "        start with: a gap in the index: [[picasso]]\n"
                      "    1x  cubism  (last 2026-08-26)\n"
                      "        what is cubism\n"
                      "        start with: held on an episode: Cubism\n"
                      "    1x  australia, capital  (last 2026-08-15)\n"
                      "        what is the capital of australia\n", out)
        self.assertEqual(json.loads(run_brain(self.root, "introspect", "--gaps", "--json").stdout)["gaps"],
                         self.brain().unanswered())
        self.assertNotIn("asked and not answered", run_brain(self.root, "introspect").stdout)

    def test_many_wordings_of_one_gap_are_cut_in_the_text(self):
        self.log(*(f"2026-09-0{n} recall {what} picasso -> none" for n, what in enumerate(
            ("who was", "where lived", "what painted", "when died", "who taught"), 1)))
        gap, = self.brain().unanswered()
        self.assertEqual((gap["words"], gap["asked"], len(gap["questions"])), (["picasso"], 5, 5))
        out = run_brain(self.root, "introspect", "--gaps").stdout
        self.assertIn("    5x  picasso  (last 2026-09-05)\n        who was picasso\n        where lived picasso\n"
                      "        what painted picasso\n        and 2 more (--json has every wording)\n"
                      "        start with: a gap in the index: [[picasso]]\n", out)

    def test_what_counts_as_rare_is_the_brain_s_own(self):
        # With every word counted as rare, `cubism` is a rare word like any other; with none, each
        # question is known by all its words, and the two about Picasso still share his name.
        for share in (1.0, 0.0):
            tried = vaultlib.Vault(self.root, today=TODAY, tuning={"rare_word_share": share})
            self.assertEqual([(g["words"], g["asked"]) for g in tried.unanswered()],
                             [(["picasso"], 3), (["cubism"], 1), (["australia", "capital"], 1)])
        self.assertEqual(vaultlib.Vault(os.path.join(ENGINE, "eval", "fixture")).unanswered(), [])  # all its questions were answered


if __name__ == "__main__":
    unittest.main()


class SearchCache(TempBrain):
    """The SQLite term cache saves work and never changes an answer."""

    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ, {"BRAIN_CACHE": "1"})
        self.env.start()
        self.write("cortex/concepts/spacing.md", concept("Study spread over days.", title="Spacing effect"))
        self.write("cortex/concepts/layout.md", concept("The spacing of rows in a table.", title="Layout"))

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def counted_search(self, query):
        """(results as stems, how many pages were tokenized) on a fresh Vault."""
        v = self.brain()
        real, calls = v._term_frequencies, []
        v._term_frequencies = lambda p: calls.append(p.rel) or real(p)
        results = [(p.stem, round(s, 6)) for p, s in v.search(query)]
        v._term_cache.close()
        return results, len(calls)

    def test_second_run_reads_the_cache_and_gives_the_same_answer(self):
        first, computed = self.counted_search("spacing")
        self.assertEqual(computed, 2)
        self.assertTrue(os.path.exists(vault_cache.cache_path(self.root)))
        again, computed = self.counted_search("spacing")
        self.assertEqual((again, computed), (first, 0))
        with mock.patch.dict(os.environ, {"BRAIN_CACHE": "0"}):
            self.assertEqual(self.counted_search("spacing")[0], first)

    def test_an_edited_page_is_recomputed_and_a_deleted_one_dropped(self):
        self.counted_search("spacing")
        self.write("cortex/concepts/layout.md", concept("Grid gutters only.", title="Layout"))
        results, computed = self.counted_search("spacing")
        self.assertEqual(computed, 1)
        self.assertEqual([stem for stem, _ in results], ["spacing"])
        os.remove(os.path.join(self.root, "cortex/concepts/layout.md"))
        self.counted_search("spacing")
        cache = vault_cache.TermCache(self.root, self.brain().tuning.cache_key)
        self.assertEqual(cache.stats()["pages"], 1)
        cache.close()

    def test_a_corrupt_or_outdated_cache_starts_over(self):
        self.counted_search("spacing")
        with open(vault_cache.cache_path(self.root), "wb") as fh:
            fh.write(b"not a database at all" * 100)
        self.assertEqual(self.counted_search("spacing")[1], 2)
        with mock.patch.object(vault_cache, "CACHE_VERSION", "next"):
            self.assertEqual(self.counted_search("spacing")[1], 2)

    def test_off_writes_nothing(self):
        with mock.patch.dict(os.environ, {"BRAIN_CACHE": "0"}):
            self.assertEqual(self.counted_search("spacing")[1], 2)
        self.assertFalse(os.path.exists(os.path.join(self.root, vault_cache.CACHE_DIR)))

    def test_unwritable_cache_still_answers(self):
        cache_dir = os.path.join(self.root, vault_cache.CACHE_DIR)
        os.makedirs(cache_dir)
        os.chmod(cache_dir, 0o500)
        try:
            results, computed = self.counted_search("spacing")
        finally:
            os.chmod(cache_dir, 0o700)
        self.assertEqual(([stem for stem, _ in results], computed), (["spacing", "layout"], 2))

    def test_a_damaged_row_is_recomputed(self):
        self.counted_search("spacing")
        db = sqlite3.connect(vault_cache.cache_path(self.root))
        with db:
            db.execute("UPDATE terms SET tf = 'not json' WHERE rel LIKE '%spacing.md'")
        db.close()
        first, computed = self.counted_search("spacing")
        self.assertEqual(computed, 1)
        self.assertEqual(self.counted_search("spacing"), (first, 0))  # and written back

    def test_a_read_only_cache_file_is_read_but_not_written(self):
        self.counted_search("spacing")
        path = vault_cache.cache_path(self.root)
        self.write("cortex/concepts/new.md", concept("More spacing.", title="New"))
        os.chmod(path, 0o400)
        try:
            results, computed = self.counted_search("spacing")
            self.assertEqual(computed, 1)  # only the new page; the write fails quietly
            self.assertEqual(self.counted_search("spacing"), (results, 1))
        finally:
            os.chmod(path, 0o600)

    def test_a_cache_broken_after_opening_still_answers(self):
        self.counted_search("spacing")
        cache = vault_cache.TermCache(self.root, self.brain().tuning.cache_key)
        cache.db.execute("DROP TABLE terms")  # as if another process damaged it mid-run
        page_list = self.brain().knowledge
        out = cache.get_many(page_list, lambda p: {"x": 1.0})
        self.assertEqual(len(out), 2)
        self.assertEqual(cache.stats()["pages"], 0)
        cache.close()

    def test_brain_cache_command_text(self):
        def run(*args, **env):
            r = run_brain(self.root, "cache", *args, env=dict(os.environ, **env))
            return r.returncode, r.stdout + r.stderr
        code, out = run("--rebuild")
        self.assertEqual(code, 0)
        self.assertIn("pages 2", out)
        self.assertIn("rebuilt from 2 pages", out)
        self.assertIn("nothing to clear", run("--clear")[1] + run("--clear")[1])
        self.assertIn("off (BRAIN_CACHE=0)", run(BRAIN_CACHE="0")[1])
        code, out = run("--rebuild", BRAIN_CACHE="0")
        self.assertNotEqual(code, 0)
        self.assertIn("nothing rebuilt", out)
        cache_dir = os.path.join(self.root, vault_cache.CACHE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        os.chmod(cache_dir, 0o500)
        try:
            self.assertIn("cannot open", run()[1])
        finally:
            os.chmod(cache_dir, 0o700)

    def test_brain_cache_command(self):
        def run(*args):
            r = run_brain(self.root, "cache", "--json", *args)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)
        self.assertEqual(run("--rebuild")["pages"], 2)
        self.assertEqual(run()["pages"], 2)
        self.assertEqual(run("--clear")["result"], "cleared")
        self.assertFalse(os.path.exists(vault_cache.cache_path(self.root)))
