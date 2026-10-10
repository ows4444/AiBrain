"""The index's listing is written from the pages by `brain index`; what is outside its markers is the owner's. Run: brain test"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from support import ENGINE, TODAY, TempBrain, page, run_brain, vaultlib

import commands  # noqa: E402  (support puts engine/lib on the path)
import index  # noqa: E402
import synth  # noqa: E402

BIN = os.path.join(ENGINE, "bin", "brain")
DATES = dict(created="2026-01-01", updated="2026-01-01")


class IndexCommand(TempBrain):
    def setUp(self):
        super().setUp()
        self.path = os.path.join(self.root, index.INDEX)
        shutil.copy(index.TEMPLATE, self.path)
        self.write("cortex/concepts/spacing-effect.md", page(
            "concept", "Study spread over days lasts longer.\n", title="Spacing effect", status="established",
            summary="Study spread over days is kept longer than the same study in one sitting.", **DATES))
        self.write("cortex/concepts/forgetting-curve.md", page("concept", title="Forgetting curve", status="emerging",
                                                               **DATES))
        self.write("cortex/episodes/cepeda-2006.md", page("episode", title="Cepeda 2006",
                                                          summary="A review of 254 studies of spacing.", **DATES))

    def text(self):
        with open(self.path, encoding="utf-8") as fh:
            return fh.read()

    def brain_index(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"}
        return subprocess.run([sys.executable, BIN, "index", *args], capture_output=True, text=True, cwd=self.root,
                              env=env)

    def check(self):
        r = run_brain(self.root, "check", "--json")
        return json.loads(r.stdout)

    def test_every_page_is_listed_by_type_with_its_summary_and_the_rest_is_left_alone(self):
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("\n## By theme\n\nA section of the owner's own, about [[spacing-effect]].\n")
        before = self.text()
        self.assertEqual(self.check()["not_in_index"],
                         ["cortex/concepts/forgetting-curve.md", "cortex/episodes/cepeda-2006.md"])
        out = index.rebuild(self.root, today=TODAY)
        self.assertEqual(out, {"listed": 3, "added": ["cepeda-2006", "forgetting-curve", "spacing-effect"],
                               "removed": [], "changed": True, "written": True})
        start, end = before.index(index.START), before.index(index.END)
        now = self.text()
        self.assertEqual(now[:now.index(index.START)], before[:start])  # the heading and the note under it
        self.assertEqual(now[now.index(index.END):], before[end:])     # Gaps, and the owner's section
        self.assertEqual(now[now.index(index.START) + len(index.START):now.index(index.END)], "\n".join([
            "", "", "## Concepts", "",
            "- [[forgetting-curve]]",
            "- [[spacing-effect]] - Study spread over days is kept longer than the same study in one sitting.", "",
            "## Entities", "", "_Nothing yet._", "", "## Insights", "", "_Nothing yet._", "",
            "## Decisions", "", "_Nothing yet._", "",
            "## Episodes", "", "- [[cepeda-2006]] - A review of 254 studies of spacing.", "", ""]))
        self.assertEqual(self.check()["not_in_index"], [])
        self.assertEqual(index.rebuild(self.root, today=TODAY)["changed"], False)  # a second run has nothing to do
        self.assertEqual(self.text(), now)

    def test_what_it_prints_added_removed_changed_and_a_dry_run(self):
        r = self.brain_index("--dry-run")
        self.assertEqual(r.stdout, "index: would list 3 pages (dry run, nothing written); "
                                   "added cepeda-2006, forgetting-curve, spacing-effect\n")
        self.assertNotIn("[[cepeda-2006]]", self.text())
        self.assertEqual(self.brain_index().stdout,
                         "index: 3 pages listed; added cepeda-2006, forgetting-curve, spacing-effect\n")
        self.assertEqual(self.brain_index().stdout, "index: up to date (3 pages listed)\n")
        os.remove(os.path.join(self.root, "cortex/episodes/cepeda-2006.md"))
        self.write("cortex/entities/anki.md", page("entity", title="Anki", kind="tool", **DATES))
        self.assertEqual(self.brain_index().stdout, "index: 3 pages listed; added anki; removed cepeda-2006\n")
        self.write("cortex/entities/anki.md", page("entity", title="Anki", kind="tool", summary="A flashcard program.",
                                                   **DATES))
        self.assertEqual(self.brain_index().stdout, "index: 3 pages listed; the lines changed, not the pages listed\n")
        self.assertIn("- [[anki]] - A flashcard program.\n", self.text())
        self.assertEqual(json.loads(self.brain_index("--json").stdout),
                         {"listed": 3, "added": [], "removed": [], "changed": False, "written": False})

    def test_a_long_list_of_names_is_cut_short(self):
        for n in range(12):
            self.write(f"cortex/entities/tool-{n:02d}.md", page("entity", title=f"Tool {n}", kind="tool", **DATES))
        self.assertTrue(self.brain_index().stdout.endswith("tool-02, tool-03, tool-04 and 7 more\n"))

    def test_a_page_of_no_known_type_is_still_listed(self):
        self.write("cortex/concepts/stray.md", page("note", title="Stray", **DATES))
        index.rebuild(self.root, today=TODAY)
        self.assertIn("## Other pages (not one of the five types: see `brain check`)\n\n- [[stray]]\n", self.text())
        self.assertEqual(self.check()["not_in_index"], [])

    def test_an_index_with_no_place_marked_is_not_touched(self):
        for body in ("[[spacing-effect]]\n", index.END + "\n## Concepts\n" + index.START + "\n",
                     index.START + "\n## Concepts\n"):
            self.write("hippocampus/index.md", page("index", body))
            before = self.text()
            r = self.brain_index()
            self.assertEqual(r.returncode, 1, body)
            self.assertIn("brain index: hippocampus/index.md has no place marked for the listing.", r.stderr)
            self.assertIn(index.START + "\n" + index.END, r.stderr)  # the two lines to put in
            self.assertEqual(self.text(), before)

    def test_a_brain_with_no_index_gets_the_template_s_filled_in(self):
        os.remove(self.path)
        self.assertEqual(index.rebuild(self.root, dry_run=True, today=TODAY)["written"], False)
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(index.rebuild(self.root, today=TODAY)["listed"], 3)
        self.assertIn("# Index\n", self.text())
        self.assertIn("- [[forgetting-curve]]\n", self.text())
        os.remove(self.path)
        for name in os.listdir(os.path.join(self.root, "cortex", "concepts")) + ["../episodes/cepeda-2006.md"]:
            os.remove(os.path.join(self.root, "cortex", "concepts", name))
        index.rebuild(self.root, today=TODAY)
        with open(index.TEMPLATE, encoding="utf-8") as fh:
            self.assertEqual(self.text(), fh.read())  # an empty brain's index is the template, to the letter

    def test_outside_a_brain_it_does_nothing(self):
        with self.assertRaises(commands.Refused) as stopped:
            commands.call("index", root=os.path.join(self.root, "cortex"))
        self.assertIn("not a brain", str(stopped.exception))

    def test_forgetting_a_source_rewrites_the_listing(self):
        self.write("senses/cepeda.md", "the paper\n")
        self.write("cortex/episodes/cepeda-2006.md", page("episode", title="Cepeda 2006", input="senses/cepeda.md",
                                                          **DATES))
        index.rebuild(self.root, today=TODAY)
        self.assertIn("## Episodes\n\n- [[cepeda-2006]]\n", self.text())
        r = run_brain(self.root, "forget", "senses/cepeda.md", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("## Episodes\n\n_Nothing yet._\n", self.text())  # as `brain index` leaves an empty section

    def test_a_synthetic_brain_s_index_is_the_command_s(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "s")
            synth.build(root, pages=40, seed=5, today=TODAY)
            self.assertEqual(index.rebuild(root, today=TODAY)["changed"], False)
            self.assertEqual(vaultlib.Vault(root, today=TODAY).missing_from_index(), [])
