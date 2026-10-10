"""Pages, frontmatter and the registries: what a page is and what it may say. Run: brain test"""
import json
import os
import re
import subprocess
import sys
import unittest

from support import BRAIN_CLAUDE, DECIDED, ENGINE, HOOKS, TempBrain, page, run_brain, vaultlib

OBSIDIAN_NOTE = """---
title: "LLM wiki: a pattern"
type: concept
created: 2026-09-01
updated: 2026-09-02
status: established
aliases:
  - Karpathy wiki
  - llm wiki
tags:
  - disputed
related: []
---
A wiki kept by a language model.
"""


class Graph(TempBrain):
    def test_links_resolve_by_stem_title_and_alias(self):
        self.write("cortex/concepts/a.md", page("concept", "[[b]] [[Bee]] [[The C]] [[missing]]"))
        self.write("cortex/concepts/b.md", page("concept", aliases="[Bee]"))
        self.write("cortex/concepts/c.md", page("concept", title="The C"))
        v = self.brain()
        self.assertEqual({(a.stem, b.stem) for a, b in v.edges}, {("a", "b"), ("a", "c")})
        self.assertEqual([t for _, t in v.broken], ["missing"])

    def test_code_examples_are_not_links(self):
        self.write("cortex/concepts/a.md", page("concept", "`[[x]]`\n```\n[[y]]\n```\n"))
        self.assertEqual(self.brain().broken, [])

    def test_index_and_log_do_not_hide_orphans(self):
        self.write("hippocampus/index.md", page("index", "[[a]] [[b]]"))
        self.log("2026-10-01 recall q -> [[a]], [[gone]]")
        self.write("cortex/concepts/a.md", page("concept", "[[b]]"))
        self.write("cortex/concepts/b.md", page("concept"))
        v = self.brain()
        self.assertEqual([p.stem for p in v.orphans()], ["a"])
        self.assertEqual(len(v.components()), 1)
        self.assertEqual(v.broken, [])  # the log is history, not links

    def test_only_memory_folders_count(self):
        for folder in ("senses", "dormant", "motor", "templates", "prefrontal/x"):
            self.write(f"{folder}/x.md", page("concept"))
        self.write("cortex/README.md", "readme")
        self.assertEqual(self.brain().pages, [])

    def test_crlf_frontmatter(self):
        fields, body = vaultlib.parse_frontmatter("---\r\ntype: concept\r\n---\r\nbody")
        self.assertEqual((fields["type"], body), ("concept", "body"))

    def test_block_lists_parse_like_inline_lists(self):
        fields, _ = vaultlib.parse_frontmatter("---\naliases:\n  - A\n  - \"B: c\"\ntags:\n- x\nempty:\n"
                                              "none: []\nurl: https://e.com\n---\n")
        self.assertEqual(fields, {"aliases": ["A", "B: c"], "tags": ["x"], "empty": "", "none": [],
                                  "url": "https://e.com"})

    def test_comments_and_stray_lines_in_frontmatter_are_skipped(self):
        fields, _ = vaultlib.parse_frontmatter("---\n# a comment\ntype: concept\nno colon here\n"
                                              "  indented: x\n---\n")
        self.assertEqual(fields, {"type": "concept"})

    def test_page_edited_in_obsidian(self):
        # As Obsidian's Properties editor saves it: block lists, a quoted title, an empty list.
        self.write("cortex/concepts/llm-wiki.md", OBSIDIAN_NOTE)
        self.write("cortex/concepts/b.md", page("concept", "See [[Karpathy wiki]]."))
        v = self.brain()
        wiki = v.resolve("Karpathy wiki")
        self.assertEqual((wiki.stem, wiki.title), ("llm-wiki", "LLM wiki: a pattern"))
        self.assertEqual(v.broken, [])
        self.assertEqual([p.stem for p in v.open_items()["disputed"]], ["llm-wiki"])
        self.assertNotIn(wiki, [p for p, _ in v.schema_problems()])

    def test_tag_vocabulary_reads_only_tags_section(self):
        self.assertEqual(vaultlib.tag_vocabulary(self.root), {"unverified", "disputed"})


class ValidatePage(TempBrain):
    def check(self, rel, text):
        return self.run_hook("validate_page.py", {"tool_input": {"file_path": self.write(rel, text)}})

    def test_valid_pages(self):
        common = dict(title="A", created="2026-01-01", updated="2026-01-02")
        self.assertEqual(self.check("cortex/concepts/a.md", page("concept", status="established",
                                                                  tags="[unverified]", **common)).returncode, 0)
        self.assertEqual(self.check("cortex/episodes/a.md", page("episode", consolidated="", **common)).returncode, 0)

    def test_summary_is_required_once_a_page_has_text_and_kept_short(self):
        common = dict(title="A", created="2026-01-01", updated="2026-01-02", status="established")
        text = "Spacing spreads study over sessions. " * 8
        rel, path = "cortex/concepts/a.md", os.path.join(self.root, "cortex/concepts/a.md")

        def pre(tool, **tool_input):
            return subprocess.run([sys.executable, os.path.join(HOOKS, "validate_page.py"), "--pre"],
                                  input=json.dumps({"tool_name": tool, "tool_input": dict(file_path=path, **tool_input)}),
                                  capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))

        new = pre("Write", content=page("concept", text, **common))
        self.assertEqual(new.returncode, 2)
        self.assertIn("missing 'summary': one sentence, at most 200 characters", new.stderr)
        self.assertEqual(pre("Write", content=page("concept", text, summary="What spacing is.", **common)).returncode, 0)
        self.write(rel, page("concept", "\n# A\n\n## What it is\n\nBODY\n", **common))  # a scaffold: no text yet
        self.assertEqual(pre("Edit", old_string="BODY", new_string=text).returncode, 2)
        self.write(rel, page("concept", text, **common))  # written before the field existed
        self.assertEqual(pre("Edit", old_string="Spacing", new_string="Spaced study").returncode, 0)
        self.assertEqual(self.check(rel, page("concept", text, **common)).returncode, 0)  # the second pass lets it be
        long = pre("Write", content=page("concept", text, summary="x" * 201, **common))
        self.assertIn("'summary' is 201 characters; one sentence, at most 200", long.stderr)
        self.write("cortex/concepts/b.md", page("concept", text, summary="Said in one line.", **dict(common, title="B")))
        out = run_brain(self.root, "check")
        self.assertIn("pages without a summary (recall cannot say what they hold): 1\n  cortex/concepts/a.md", out.stdout)
        found = run_brain(self.root, "recall", "spacing", env=dict(os.environ, BRAIN_CACHE="0")).stdout
        self.assertIn("cortex/concepts/b.md\n           Said in one line.", found)
        self.assertIn("cortex/concepts/a.md\n           (no summary: open the page to judge it)", found)

    def test_readme_is_not_a_page(self):
        self.assertEqual(self.check("cortex/README.md", "# What lives here\n").returncode, 0)

    def test_list_title_is_reported_and_does_not_break_the_brain(self):
        text = page("concept", status="established", title="[WIP]", created="2026-01-01", updated="2026-01-02")
        self.assertIn("'title' reads as a list", self.check("cortex/concepts/wip.md", text).stderr)
        self.assertEqual(self.brain().resolve("wip").title, "wip")

    def test_system_pages(self):
        self.assertEqual(self.check("hippocampus/log.md", page("log")).returncode, 0)

    def test_problems_reported(self):
        result = self.check("cortex/concepts/a.md", page("idea", created="Jan 1", tags="[made-up]", salience="low"))
        self.assertEqual(result.returncode, 2)
        for fragment in ("type 'idea'", "missing 'title'", "'created' must be", "made-up", "'salience'"):
            self.assertIn(fragment, result.stderr)

    def test_concept_needs_status(self):
        result = self.check("cortex/concepts/a.md", page("concept", title="A", created="2026-01-01", updated="2026-01-01"))
        self.assertIn("status", result.stderr)

    def test_block_list_tags_are_checked(self):
        tags = "tags:\n" + "".join(f"  - t{i}\n" for i in range(5))
        result = self.check("cortex/concepts/a.md", OBSIDIAN_NOTE.replace("tags:\n  - disputed\n", tags))
        self.assertEqual(result.returncode, 2)
        self.assertIn("5 tags; at most 3", result.stderr)
        self.assertIn("not in the vocabulary", result.stderr)

    def test_file_names_are_lowercase_hyphenated(self):
        result = self.check("cortex/concepts/My Big Idea.md", OBSIDIAN_NOTE)
        self.assertEqual(result.returncode, 2)
        self.assertIn("rename it to 'my-big-idea', keep the title", result.stderr)
        self.assertEqual(self.check("cortex/concepts/llm-wiki-2.md", OBSIDIAN_NOTE).returncode, 0)
        self.assertEqual(self.check("prefrontal/Launch Plan/CLAUDE.md", "# no frontmatter\n").returncode, 2)
        self.assertEqual(self.check("hippocampus/index.md", page("index")).returncode, 0)
        problems = dict((p.rel, probs) for p, probs in self.brain().schema_problems())
        self.assertEqual(sorted(problems), ["cortex/concepts/My Big Idea.md", "prefrontal/Launch Plan/CLAUDE.md"])

    def test_outside_memory_ignored(self):
        self.assertEqual(self.check("templates/concept.md", "no frontmatter").returncode, 0)


class Registry(TempBrain):
    """Fields, relations and log operations each have one definition in vaultlib."""

    def problems(self, page_type, **fields):
        return "; ".join(vaultlib.schema_problems(page(page_type, **dict(DECIDED, **fields))))

    def test_fields_follow_the_registry(self):
        self.assertEqual(self.problems("entity", kind="tool"), "")
        self.assertIn("'kind' must be one of", self.problems("entity", kind="thing"))
        self.assertIn("'kind' belongs on entity pages only", self.problems("concept", status="emerging", kind="tool"))
        self.assertIn("'review' belongs on decision", self.problems("episode", review="2026-01-01"))
        self.assertIn("'consolidated' must be YYYY-MM-DD", self.problems("episode", consolidated="soon"))
        self.assertIn("'publish' must be one of true", self.problems("episode", publish="yes"))
        self.assertEqual(self.problems("episode", custom="owner's own field"), "")  # unknown fields are allowed

    def test_every_field_is_documented(self):
        with open(os.path.join(ENGINE, "templates", "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        for name in vaultlib.FIELDS:
            self.assertRegex(readme, rf"`{name}[:`\s]", name)

    def test_typed_links_open_items_and_bad_relations(self):
        self.write("cortex/concepts/a.md", page("concept", "(contradicts:: [[b]]) (supports:: [[c]])", tags="[disputed]"))
        self.write("cortex/concepts/b.md", page("concept", "(rebuts:: [[a]])", tags="[to-revisit]"))
        self.write("cortex/concepts/c.md", page("concept"))
        v = self.brain()
        self.assertEqual({(a.stem, r, b.stem) for a, r, b in v.typed_edges()},
                         {("a", "contradicts", "b"), ("a", "supports", "c"), ("b", "rebuts", "a")})
        self.assertEqual([(p.stem, r) for p, r in v.relation_problems()], [("b", "rebuts")])
        items = v.open_items()
        self.assertEqual(([p.stem for p in items["disputed"]], [p.stem for p in items["revisit"]]), (["a"], ["b"]))
        self.assertEqual([(a.stem, b.stem) for a, b in items["contradicts"]], [("a", "b")])
        r = run_brain(self.root, "check", "--json")
        self.assertEqual((r.returncode, json.loads(r.stdout)["relations"]), (1, [{"page": "cortex/concepts/b.md",
                                                                                   "relation": "rebuts"}]))

    def test_unknown_log_operation_is_reported_not_fatal(self):
        self.log("2026-10-01 ingest senses/a.md -> 1 episode", "2026-10-02 tidy things -> done")
        self.assertEqual(self.brain().log_problems(), ["2026-10-02 tidy things -> done"])
        r = run_brain(self.root, "check", "--json")
        self.assertEqual((r.returncode, json.loads(r.stdout)["log"]), (0, ["2026-10-02 tidy things -> done"]))

    def test_claude_md_lists_every_op_and_relation(self):
        with open(os.path.join(ENGINE, "templates", "brain", "CLAUDE.md"), encoding="utf-8") as fh:
            text = fh.read()
        for word in vaultlib.OPS + vaultlib.RELATIONS:
            self.assertIn(f"`{word}`", text, word)


class TemplateSync(unittest.TestCase):
    @staticmethod
    def without_owner(path):
        with open(path, encoding="utf-8") as fh:
            return re.sub(r"^## Owner\n.*?(?=^## )", "", fh.read(), flags=re.S | re.M)

    @unittest.skipUnless(os.path.exists(BRAIN_CLAUDE), "the engine is not inside a brain")
    def test_brain_claude_md_matches_template_outside_owner(self):
        self.assertEqual(self.without_owner(BRAIN_CLAUDE),
                         self.without_owner(os.path.join(ENGINE, "templates", "brain", "CLAUDE.md")))


if __name__ == "__main__":
    unittest.main()
