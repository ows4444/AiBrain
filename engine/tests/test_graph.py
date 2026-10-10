"""The link graph and the health signals read from it. Run: brain test"""
import json
import unittest

from support import DECIDED, TempBrain, VALID, page, project, run_brain, vaultlib


class GraphViews(TempBrain):
    """Two triangles joined through one page: x is the bridge and a cut point."""

    def setUp(self):
        super().setUp()
        links = {"a1": "a2 a3 x", "a2": "a3", "a3": "", "x": "b1", "b1": "b2 b3", "b2": "b3", "b3": ""}
        for name, targets in links.items():
            body = " ".join(f"[[{t}]]" for t in targets.split())
            self.write(f"cortex/concepts/{name}.md", page("concept", body, title=name.upper(), tags="[disputed]"))
        self.write("hippocampus/index.md", page("index", "[[a1]] [[x]]"))

    def stems(self, pages):
        return [p.stem for p in pages]

    def test_bridges_are_estimated_on_large_graphs(self):
        v = self.brain()
        self.assertFalse(v.betweenness_estimated())
        self.assertTrue(v.betweenness_estimated(exact_up_to=6))
        sampled = v.betweenness(exact_up_to=6, sample=4)
        self.assertEqual(max(sampled, key=sampled.get).stem, "x")
        self.assertEqual(sampled, v.betweenness(exact_up_to=6, sample=4))  # the same sample every run

    def test_bridges_and_cut_points(self):
        v = self.brain()
        between = v.betweenness()
        self.assertEqual(max(between, key=between.get).stem, "x")
        self.assertAlmostEqual(between[v.resolve("a2")], 0.0)
        self.assertEqual(self.stems(v.cut_points()), ["a1", "b1", "x"])

    def test_clusters_find_the_two_triangles(self):
        clusters = sorted(sorted(self.stems(c)) for c in self.brain().clusters())
        # the bridge page x joins one side; the triangles never merge
        self.assertEqual(clusters, [["a1", "a2", "a3", "x"], ["b1", "b2", "b3"]])

    def test_hubs_need_outsized_inbound(self):
        self.assertEqual(self.brain().hubs(), [])
        for i in range(8):
            self.write(f"cortex/concepts/spoke{i}.md", page("concept", "[[a3]]"))
        self.assertEqual(self.stems(self.brain().hubs()), ["a3"])

    def test_tags_and_index_drift(self):
        v = self.brain()
        self.assertEqual(v.tag_counts(), {"disputed": 7})
        self.assertEqual(self.stems(v.missing_from_index()), ["a2", "a3", "b1", "b2", "b3"])

    def test_graph_flags_and_verdicts(self):
        out = run_brain(self.root, "introspect", "--json", "--graph", check=True)
        r = json.loads(out.stdout)
        self.assertEqual(r["cut_points"], ["cortex/concepts/a1.md", "cortex/concepts/b1.md", "cortex/concepts/x.md"])
        self.assertIn("too small", r["verdicts"]["overall"])
        self.assertNotIn("cut_points", json.loads(run_brain(self.root, "introspect", "--json").stdout))  # expensive views only on request

    def test_verdict_thresholds(self):
        self.assertEqual(vaultlib.verdicts(3, 4, 90, 50),
                         {"orphan_rate": "healthy", "avg_degree": "working range", "components": "one main component"})
        bad = vaultlib.verdicts(20, 1.5, 60, 50)
        self.assertIn("not linking", bad["orphan_rate"])
        self.assertIn("barely", bad["avg_degree"])
        self.assertIn("fragmented", bad["components"])
        self.assertIn("decorative", vaultlib.verdicts(3, 12, 90, 50)["avg_degree"])


class Signals(TempBrain):
    """S1: what the brain reports about itself stays true when its features are used."""

    def check(self):
        r = run_brain(self.root, "check", "--json")
        return r.returncode, json.loads(r.stdout)

    def ring(self, n=10):
        for i in range(n):
            self.write(f"cortex/concepts/c{i}.md", page("concept", f"[[c{(i + 1) % n}]] " + "word " * 50, **VALID))

    def test_records_are_never_orphans(self):
        self.ring()
        self.write("cortex/decisions/d.md", page("decision", "About [[c1]].", status="open", **DECIDED))
        self.write("cortex/episodes/idea.md", page("episode", "On [[c2]].", origin="generated", **DECIDED))
        self.write("cortex/episodes/queued.md", page("episode", "On [[c3]].", **DECIDED))
        self.write("cortex/episodes/slept.md", page("episode", "On [[c4]].", consolidated="2026-02-01", **DECIDED))
        v = self.brain()
        self.assertEqual([p.stem for p in v.orphans()], ["slept"])  # sleep should have linked it back
        self.assertEqual(len(v.linked_to()), 11)
        r = json.loads(run_brain(self.root, "introspect", "--json", check=True).stdout)
        self.assertEqual(r["orphan_rate"], 9.1)  # 1 of 11, not 4 of 14

    def test_stubs_are_knowledge_pages_only(self):
        self.write("cortex/decisions/d.md", page("decision", "Which host?", status="open", **DECIDED))
        self.write("cortex/episodes/e.md", page("episode", "## Candidates\n- X\n", **DECIDED))
        self.write("cortex/concepts/thin.md", page("concept", "short", **VALID))
        self.assertEqual([p.stem for p in self.brain().stubs()], ["thin"])

    def test_a_name_two_pages_answer_to_fails(self):
        self.write("cortex/concepts/launch.md", page("concept", "x", **VALID))
        self.write("prefrontal/launch/CLAUDE.md", project())
        self.write("cortex/entities/acme.md", page("entity", title="Acme", aliases="[The Co]"))
        self.write("cortex/entities/the-co.md", page("entity", title="The Co"))
        self.write("cortex/concepts/deal.md", page("concept", "Signed with [[The Co]].", **VALID))
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(report["ambiguous"], [
            {"name": "launch", "pages": ["cortex/concepts/launch.md", "prefrontal/launch/CLAUDE.md"]},
            {"name": "the co", "pages": ["cortex/entities/acme.md", "cortex/entities/the-co.md"]}])

    def test_a_shared_title_no_link_uses_is_listed_not_failed(self):
        # Two clips of one article: one source, one title, linked by file name.
        clip = dict(DECIDED, title="The pricing article", url="https://example.com/pricing")
        self.write("cortex/episodes/pricing-article-part-1.md", page("episode", **clip))
        self.write("cortex/episodes/pricing-article-part-2.md", page("episode", **clip))
        self.write("hippocampus/index.md", page("index", "[[pricing-article-part-1]] [[pricing-article-part-2]]"))
        code, report = self.check()
        shared = [{"name": "the pricing article", "pages": ["cortex/episodes/pricing-article-part-1.md",
                                                            "cortex/episodes/pricing-article-part-2.md"]}]
        self.assertEqual((code, report["ambiguous"], report["shared_names"]), (0, [], shared))
        self.write("CLAUDE.md", "# B\n\n## Owner\n\n### Goals\n\n- Price -> [[The pricing article]]\n")
        code, report = self.check()
        self.assertEqual((code, report["ambiguous"], report["shared_names"]), (1, shared, []))

    def test_a_page_may_repeat_its_own_name(self):
        self.write("cortex/concepts/llm-wiki.md", page("concept", aliases="[llm-wiki, LLM wiki]", **VALID))
        self.assertEqual(self.brain().ambiguous_names(), ({}, {}))

    def test_project_fields_are_checked(self):
        bad = self.write("prefrontal/launch/CLAUDE.md", project(status="finished", due="soon"))
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(report["schema"], [{"page": "prefrontal/launch/CLAUDE.md", "problems": [
            "'status' must be one of active, paused, done, or absent", "'due' must be YYYY-MM-DD"]}])
        hook = self.run_hook("validate_page.py", {"tool_input": {"file_path": bad}})
        self.assertEqual(hook.returncode, 2)
        self.assertIn("status", hook.stderr)
        self.write("prefrontal/old/CLAUDE.md", "# An old project without frontmatter\n")
        self.write("prefrontal/launch/CLAUDE.md", project())
        self.assertEqual(self.check()[0], 0)

    def test_goal_links_are_checked(self):
        self.write("hippocampus/index.md", page("index", "## Gaps\n\n- [[Planned]]\n"))
        self.write("CLAUDE.md", "# B\n\n## Owner\n\n### Goals\n\n- Ship -> [[renamed-away]], [[planned]]\n\n"
                                "## Tags\n\n`disputed`\n")
        code, report = self.check()
        self.assertEqual((code, report["broken"]), (1, [{"page": "CLAUDE.md > Goals > Ship", "target": "renamed-away"}]))


if __name__ == "__main__":
    unittest.main()
