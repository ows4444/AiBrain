"""Retrieval: search, co-recall weights, spreading activation, confidence, the answer test set. Run: brain test"""
import json
import os
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

from support import ENGINE, SCRIPTS, TempBrain, TODAY, ago, page, vaultlib

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
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "eval.py"), "--json", *args],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_fixture_passes_brain_check(self):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "link_check.py"), FIXTURE, "--json"],
                           capture_output=True, text=True)
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
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "link_check.py"), a, "--json"],
                               capture_output=True, text=True)
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
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "cache.py"), self.root, *args],
                               capture_output=True, text=True, env=dict(os.environ, **env))
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
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "cache.py"), self.root, "--json", *args],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)
        self.assertEqual(run("--rebuild")["pages"], 2)
        self.assertEqual(run()["pages"], 2)
        self.assertEqual(run("--clear")["result"], "cleared")
        self.assertFalse(os.path.exists(vault_cache.cache_path(self.root)))
