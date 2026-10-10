"""`brain ground`: a drafted answer or piece is held to the pages it cites. Run: brain test"""
import json
import os
import unittest

from support import ENGINE, TODAY, TempBrain, page, run_brain, vaultlib

import commands  # noqa: E402  (support puts engine/lib on the path)
import ground  # noqa: E402

FIXTURE = os.path.join(ENGINE, "eval", "fixture")
ANSWERS = os.path.join(ENGINE, "eval", "answers.json")
DATES = dict(created="2026-01-01", updated="2026-01-01")


class ReferenceAnswers(unittest.TestCase):
    """Done when: it flags nothing in the reference answers and catches a planted number."""

    def setUp(self):
        with open(ANSWERS, encoding="utf-8") as fh:
            self.answers = {qid: text for qid, text in json.load(fh).items() if qid != "about"}
        self.vault = vaultlib.Vault(FIXTURE, today=TODAY)

    def test_nothing_is_flagged_in_answers_written_from_the_pages(self):
        checked = {"links": 0, "numbers": 0, "quotes": 0}
        for qid, text in self.answers.items():
            found = ground.ground(self.vault, text)
            self.assertEqual(found["ungrounded"], [], qid)
            for kind in checked:
                checked[kind] += found["checked"][kind]
        self.assertEqual(checked, {"links": 10, "numbers": 11, "quotes": 1})  # it did read them: there was plenty to find

    def test_they_are_good_answers_by_the_other_measure_too(self):
        scored = commands.call("eval", ["--answers", ANSWERS])["answers"]
        self.assertEqual((scored["answered"], scored["citation_recall"], scored["citation_precision"],
                          scored["uncovered_passed"]), (len(self.answers), 1.0, 1.0, "2/2"))

    def test_a_planted_number_a_planted_quotation_and_a_planted_page_are_caught(self):
        answer = self.answers["q03"]
        self.assertIn("317 experiments", answer)
        self.assertEqual(ground.ground(self.vault, answer.replace("317", "417"))["ungrounded"], [
            {"line": 1, "kind": "number", "text": "417", "why": "not on [[spacing-effect]], [[cepeda-2006]]"}])
        misquoted = self.answers["q01"].replace("levels off", "never recovers")
        self.assertEqual(ground.ground(self.vault, misquoted)["ungrounded"], [
            {"line": 1, "kind": "quote", "text": '"falls steeply in the first hour after learning and then never recovers"',
             "why": "not on [[forgetting-curve]], [[ebbinghaus-1885]]"}])
        # The right numbers against the wrong page are no better than wrong ones. The 317 experiments are on
        # the concept's page too, which the paragraph still cites; the share of the interval is not.
        self.assertEqual([r["text"] for r in ground.ground(self.vault, answer.replace("[[cepeda-2006]]", "[[anki]]"))
                          ["ungrounded"]], ["10", "20"])
        self.assertEqual(ground.ground(self.vault, answer.replace("[[cepeda-2006]]", "[[cepeda-2016]]"))["ungrounded"][0],
                         {"line": 1, "kind": "link", "text": "[[cepeda-2016]]", "why": "no such page"})


class WhatCountsAsAClaim(TempBrain):
    def setUp(self):
        super().setUp()
        self.write("cortex/episodes/study.md", page(
            "episode", "\n# A study\n\nIt pooled 1,200 students over ten weeks, on 2026-03-04; 40% improved.\nThe authors "
            "wrote that spacing is \"the cheapest gain\nin all of education\".\n", title="A study", published="2019",
            summary="A study.", **DATES))
        self.write("dormant/old.md", page("concept", "It ran for 7 years.\n", title="Old idea", status="emerging", **DATES))

    def found(self, text):
        return [(r["line"], r["kind"], r["text"], r["why"]) for r in ground.ground(self.brain(), text)["ungrounded"]]

    def test_numbers_are_the_page_s_however_it_writes_them(self):
        ok = ("In 2019 a study of 1200 students ran for 10 weeks from 2026-03-04, and 40% improved [[study]].\n"
              "It also says 1,200 [[study]].")
        self.assertEqual(self.found(ok), [])
        self.assertEqual(self.found("It pooled 1,300 students for 11 weeks from 2026-03-05 [[study]]."), [
            (1, "number", "1,300", "not on [[study]]"), (1, "number", "11", "not on [[study]]"),
            (1, "number", "2026-03-05", "not on [[study]]")])
        self.assertEqual(self.found("Half of them, 50%, improved.\n\nA second paragraph cites it [[study]]."),
                         [(1, "number", "50%", "its paragraph cites no page")])  # a citation covers its own paragraph

    def test_a_quotation_is_three_words_or_more_and_is_matched_across_the_page_s_line_breaks(self):
        self.assertEqual(self.found('Spacing is "the cheapest gain in all of education" [[study]], or “the cheapest gain”.'), [])
        self.assertEqual(self.found('It calls spacing "a waste of time" [[study]], a "gain".'),
                         [(1, "quote", '"a waste of time"', "not on [[study]]")])
        self.assertEqual(self.found("A quotation\nover two lines, “the cheapest\ngain of all”, cites it [[study]]."),
                         [(2, "quote", '"the cheapest gain of all"', "not on [[study]]")])

    def test_what_is_labelled_the_writer_s_own_is_not_checked(self):
        draft = ("The study had 1,200 students [[study]]. Outside knowledge: most trials have under 100. "
                 "(This one cost 3 million, outside knowledge.) A third had 77.\n\n"
                 "Outside knowledge, all of this paragraph: 5 of 9 replications held. Another 4 did not.")
        self.assertEqual(self.found(draft), [(1, "number", "77", "not on [[study]]")])

    def test_what_is_no_claim_is_not_read(self):
        draft = ("---\ntitle: Draft 12\n---\n\n# 3 things about spacing\n\n"
                 "- The SM-2 rule, v2 of it, in its 2nd form, with COVID-19 as an aside [[study]].\n"
                 "- It is well supported (high: 3 sources, 2 independent) [[study]] and `uses 99 cards`.\n"
                 "1. A numbered point with 1,200 in it [[study]].\n"
                 "2. One citing a page that faded, which ran 7 years [[old]], or [[Old idea]].\n\n"
                 "```\ncode with 999 in it [[nowhere]]\n```\n\n"
                 "Read: [[study]], [[missing-page]]\nConfidence: study: source (1 sources)\nNot covered: the 2024 trials\n")
        self.assertEqual(self.found(draft), [(16, "link", "[[missing-page]]", "no such page")])
        counted = ground.ground(self.brain(), draft)["checked"]
        self.assertEqual(counted, {"links": 7, "numbers": 2, "quotes": 0})  # 1,200 and 7: the rest is not prose

    def test_the_command_lists_them_by_line_and_exits_1(self):
        path = self.write("motor/draft.md", "It had 1,200 students and 9 teachers [[study]].\n\nSee [[ghost]].\n")
        r = run_brain(self.root, "ground", "motor/draft.md")
        self.assertEqual((r.returncode, r.stdout), (1, (
            "ground: motor/draft.md: 2 links, 2 numbers and 0 quotations; 2 with no page behind them\n"
            "  line 1: number 9: not on [[study]]\n"
            "  line 3: [[ghost]]: no such page\n"
            "  for each: cite the page it is on in that paragraph, label the sentence outside knowledge, or take it out\n")))
        as_data = json.loads(run_brain(self.root, "ground", "motor/draft.md", "--json").stdout)
        self.assertEqual((as_data["file"], as_data["checked"], [u["line"] for u in as_data["ungrounded"]]),
                         ("motor/draft.md", {"links": 2, "numbers": 2, "quotes": 0}, [1, 3]))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("It had 1,200 students and 9 teachers [[study]].\n")
        self.assertIn("; 1 with no page behind it\n", run_brain(self.root, "ground", "motor/draft.md").stdout)
        piped = run_brain(self.root, "ground", "-", input="It had 1,200 students [[study]].\n")
        self.assertEqual((piped.returncode, piped.stdout),
                         (0, "ground: the draft: 1 links, 1 numbers and 0 quotations, each with a page behind it\n"))
        missing = run_brain(self.root, "ground", "motor/none.md")
        self.assertEqual((missing.returncode, missing.stderr), (1, "brain ground: no such file: motor/none.md\n"))


if __name__ == "__main__":
    unittest.main()
