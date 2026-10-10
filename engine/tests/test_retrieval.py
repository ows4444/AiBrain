"""Retrieval: search, co-recall weights, spreading activation, confidence, the answer test set. Run: brain test"""
import json
import os
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

from support import ENGINE, SCRIPTS, TempBrain, TODAY, ago, page, run_brain, vaultlib

import vault_cache  # noqa: E402  (support puts engine/lib on the path)

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

    def recall_cmd(self, *args):
        r = run_brain(FIXTURE, "recall", *args, env=dict(os.environ, BRAIN_CACHE="0"))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_recall_stops_where_the_match_stops(self):
        vault = vaultlib.Vault(FIXTURE)
        every = vault.recall("What is the ease factor?")
        cut = vault.recall("What is the ease factor?", floor=vaultlib.RECALL_FLOOR, abstain=True)
        self.assertEqual(([r["page"].stem for r in cut], len(every)), (["wozniak-sm2"], 10))
        self.assertTrue(all(r["score"] < vaultlib.RECALL_FLOOR * every[0]["score"] for r in every[1:]))
        out = self.recall_cmd("What is the ease factor?")
        self.assertIn("wozniak-sm2.md", out)
        self.assertNotIn("supermemo.md", out)
        self.assertIn("weaker matches are cut (--all lists them)", out)
        self.assertIn("supermemo.md", self.recall_cmd("What is the ease factor?", "--all"))

    def test_recall_lists_nothing_when_the_best_page_holds_too_little_of_the_question(self):
        vault, asked = vaultlib.Vault(FIXTURE), "What did the 2024 sleep and memory consolidation trials find?"
        best = vault.search(asked)[0][0]
        self.assertLess(vault.coverage(asked, best), vaultlib.MIN_COVERAGE)
        self.assertEqual(vault.recall(asked, floor=vaultlib.RECALL_FLOOR, abstain=True), [])
        out = self.recall_cmd(asked)
        self.assertTrue(out.startswith("recall: no confident match for"), out)
        self.assertIn(f"its words barely reach {best.rel}", out)
        self.assertEqual(len(out.splitlines()), 1)  # one line, no summaries
        self.assertIn(best.rel, json.loads(self.recall_cmd(asked, "--json"))["weak"])
        self.assertIn("hit;", self.recall_cmd(asked, "--all"))
        self.assertEqual(vault.coverage("What is the forgetting curve?", vault.resolve("forgetting-curve")), 1.0)
        self.assertIn("nothing matches", self.recall_cmd("What is the capital of Australia?"))
        now = self.run_eval()["retrieval"]
        self.assertEqual([u["recall_results"] for u in now["uncovered"]], [0, 0, 0, 0, 4, 3])  # not every one is caught
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
            self.assertEqual(now[mode]["unsummarised"], 0, "every fixture page says what it holds")
            self.assertLess(now[mode]["bytes_by_summary"], now[mode]["bytes_read"])  # or the summaries cost more than they save
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
                             vaultlib.PROMPT_CHARS)

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
        self.assertIn("question o01: not a paraphrase, it uses spacing from [[spacing]]", report)
        self.assertNotIn("uncovered", report)
        self.assertIn("baseline saved to " + os.path.join(self.root, "motor", "eval-questions-baseline.json"),
                      run("--save-baseline").stdout)
        with open(os.path.join(ENGINE, "eval", "baseline.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["sets"]["standard"]["recall"]["questions"], 13)  # the engine's is untouched


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
        cache = vault_cache.TermCache(self.root)
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
        cache = vault_cache.TermCache(self.root)
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
