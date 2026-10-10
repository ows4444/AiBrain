"""`brain extract`: a PDF's or an image's text lands in senses/, read by a tool and not by the model. Run: brain test

The tools are stand-ins (support.readers): the tests hold what the engine does with what a tool prints, on a
machine that has neither. A "PDF" here is the text the stand-in prints for it, a form feed after each page.
"""
import json
import os
import tempfile
from unittest import mock

from support import TODAY, TempBrain, page, readers, run_brain, tool

import extract  # noqa: E402  (support puts engine/lib on the path)
import forget  # noqa: E402

DATES = dict(created="2026-01-01", updated="2026-01-01")
PAPER = ("Distributed practice in verbal recall tasks   \nA review of 254 studies with more than 14,000 participants.\n\n\n\n"
         "Spaced study gave better final recall.\n\f"
         "The best gap grows with the delay before the test.\nFor a test a week away, a day was best.\n\f")
TEXT = ("Distributed practice in verbal recall tasks\nA review of 254 studies with more than 14,000 participants.\n\n"
        "Spaced study gave better final recall.\n\n"
        "The best gap grows with the delay before the test.\nFor a test a week away, a day was best.\n")
BOARD = "Retrieval beats rereading: the testing effect, from the whiteboard of the reading group.\n\f"


class Tools(TempBrain):
    def setUp(self):
        super().setUp()
        self.beside = tempfile.TemporaryDirectory()
        self.addCleanup(self.beside.cleanup)
        self.out = os.path.realpath(self.beside.name)
        os.makedirs(os.path.join(self.root, "senses"))
        self.path = readers(os.path.join(self.out, "bin")) + os.pathsep + os.environ["PATH"]  # ahead of any real one
        patch = mock.patch.dict(os.environ, {"PATH": self.path})
        patch.start()
        self.addCleanup(patch.stop)

    def outside(self, name, text):
        path = os.path.join(self.out, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def take(self, source, **kw):
        return extract.extract(self.root, source, today=TODAY, **kw)


class WhereItLands(Tools):
    def test_a_pdf_from_outside_lands_as_text_and_its_original_in_assets(self):
        """Done when: a PDF lands in senses/ as text without the model reading the file."""
        source = self.outside("Cepeda 2006.pdf", PAPER)
        found = self.take(source)
        self.assertEqual(found, {"saved": "senses/2026-10-03-cepeda-2006.md", "path": "senses/2026-10-03-cepeda-2006.md",
                                 "original": "senses/assets/Cepeda 2006.pdf", "placed": "copy", "tool": "pdftotext",
                                 "pages": 2, "words": 43})
        self.assertEqual(self.read(found["saved"]), '---\ntranscribed_from: "assets/Cepeda 2006.pdf"\n'
                         "extracted_with: pdftotext\npages: 2\nextracted: 2026-10-03\n---\n\n" + TEXT)
        self.assertEqual(self.read("senses/assets/Cepeda 2006.pdf"), PAPER)
        self.assertTrue(os.path.exists(source))  # a copy: the owner's file is where it was
        self.assertEqual(self.brain().unencoded(), ["senses/2026-10-03-cepeda-2006.md"])  # the text is the input
        self.assertEqual(forget.asset_of(self.root, found["saved"]), "senses/assets/Cepeda 2006.pdf")  # they go together
        r = run_brain(self.root, "new", "episode", "--from", found["saved"])
        self.assertEqual((r.returncode, r.stderr), (1, "brain new: no title (give --title, or an input with a `title:` "
                                                       "or a first heading)\n"))
        r = run_brain(self.root, "new", "episode", "--from", found["saved"], "--title", "Cepeda 2006")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("input: senses/2026-10-03-cepeda-2006.md\n", self.read("cortex/episodes/cepeda-2006.md"))
        self.assertEqual(self.brain().unencoded(), [])

    def test_a_file_from_the_inbox_is_moved_and_one_in_assets_stays(self):
        self.write("inbox/paper.pdf", PAPER)
        found = self.take("inbox/paper.pdf", name="Distributed practice!")
        self.assertEqual((found["saved"], found["original"], found["placed"]),
                         ("senses/2026-10-03-distributed-practice.md", "senses/assets/paper.pdf", "move"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "inbox", "paper.pdf")))
        self.write("senses/assets/board.PNG", BOARD)
        found = self.take("senses/assets/board.PNG")
        self.assertEqual((found["saved"], found["original"], found["placed"], found["tool"], found["pages"]),
                         ("senses/2026-10-03-board.md", "senses/assets/board.PNG", None, "tesseract", 1))
        self.assertIn('transcribed_from: "assets/board.PNG"\nextracted_with: tesseract\npages: 1\n', self.read(found["saved"]))

    def test_an_input_is_never_moved_and_counts_once_with_its_text(self):
        self.write("senses/reading/scan.png", BOARD)
        self.assertEqual(self.brain().unencoded(), ["senses/reading/scan.png"])
        found = self.take("senses/reading/scan.png")
        self.assertEqual((found["saved"], found["original"], found["placed"]),
                         ("senses/reading/scan.png.md", "senses/reading/scan.png", None))
        self.assertIn('transcribed_from: "reading/scan.png"\n', self.read(found["saved"]))
        self.assertEqual(self.read("senses/reading/scan.png"), BOARD)
        self.assertEqual(self.brain().unencoded(), ["senses/reading/scan.png.md"])  # one input, the text
        self.assertEqual(forget.asset_of(self.root, found["saved"]), "senses/reading/scan.png")
        self.write("cortex/episodes/the-board.md", page("episode", "What the board said.\n", title="The board",
                                                        input="senses/reading/scan.png.md", **DATES))
        self.assertEqual(self.brain().unencoded(), [])

    def test_nothing_is_written_over_a_file_that_is_there(self):
        self.write("senses/assets/paper.pdf", "Another paper that happens to have the name.\n")
        self.write("senses/2026-10-03-paper.md", "A note that happens to have the name.\n")
        first = self.take(self.outside("paper.pdf", PAPER))
        self.assertEqual((first["saved"], first["original"]), ("senses/2026-10-03-paper-2.md", "senses/assets/paper-2.pdf"))
        self.assertEqual(self.read("senses/assets/paper.pdf"), "Another paper that happens to have the name.\n")
        other = self.take(self.outside("other.pdf", PAPER.replace("254", "317")), name="paper")
        self.assertEqual((other["saved"], other["original"]), ("senses/2026-10-03-paper-3.md", "senses/assets/other.pdf"))
        self.assertEqual(self.take(self.outside("¿?.pdf", PAPER.replace("254", "184")))["saved"], "senses/2026-10-03-document.md")

    def test_a_file_put_in_assets_by_hand_is_used_where_it_is(self):
        self.write("senses/assets/paper.pdf", PAPER)
        found = self.take(self.outside("paper.pdf", PAPER))  # the same file: no second copy
        self.assertEqual((found["original"], found["placed"]), ("senses/assets/paper.pdf", None))
        self.assertEqual(os.listdir(os.path.join(self.root, "senses", "assets")), ["paper.pdf"])

    def test_a_dry_run_reads_and_writes_nothing(self):
        self.write("inbox/paper.pdf", PAPER)
        r = run_brain(self.root, "extract", "inbox/paper.pdf", "--dry-run", env=dict(os.environ, PATH=self.path))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        day = json.loads(run_brain(self.root, "extract", "inbox/paper.pdf", "--dry-run", "--json",
                                   env=dict(os.environ, PATH=self.path)).stdout)["path"][len("senses/"):len("senses/") + 10]
        self.assertEqual(r.stdout, f"would save senses/{day}-paper.md\n"
                         "  2 pages -> 43 words, read with pdftotext; the original would be moved to senses/assets/paper.pdf\n"
                         "  read that file, not the original, and give the episode its title (`brain new episode --from ... "
                         "--title`); run `brain fingerprint` once it is in place\n")
        self.assertTrue(os.path.exists(os.path.join(self.root, "inbox", "paper.pdf")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "senses", "assets")))
        r = run_brain(self.root, "extract", "inbox/paper.pdf", env=dict(os.environ, PATH=self.path))
        self.assertEqual(r.stdout.splitlines()[:2], [
            f"saved senses/{day}-paper.md",
            "  2 pages -> 43 words, read with pdftotext; the original moved to senses/assets/paper.pdf"])
        self.assertIn("the original stays at senses/assets/paper.pdf", extract.render(
            dict(saved="senses/x.md", path="senses/x.md", original="senses/assets/paper.pdf", placed=None,
                 tool="pdftotext", pages=2, words=43), None))


class WhatIsRefused(Tools):
    def refused(self, source, why, **env):
        before = sorted(os.listdir(os.path.join(self.root, "senses")))
        r = run_brain(self.root, "extract", source, env=dict(os.environ, **env))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", f"brain extract: {why}\n"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "senses"))), before)  # nothing landed

    def test_with_no_tool_here_it_says_so_and_the_model_reads_the_file(self):
        """Falls back to the model when the tool is absent: exit 1, nothing written, and the reason."""
        empty = os.path.join(self.out, "no-tools")
        os.makedirs(empty)
        self.refused(self.outside("paper.pdf", PAPER), "no `pdftotext` on this machine to read a pdf file with; nothing "
                     "saved. The model reads the file", PATH=empty)
        self.refused(self.outside("board.jpeg", BOARD), "no `tesseract` on this machine to read a jpeg file with; nothing "
                     "saved. The model reads the file", PATH=empty)

    def test_what_is_not_a_document_with_text_is_reported(self):
        self.write("senses/scan.pdf", "\f\f\f")
        self.write("senses/slides.pdf", "Agenda\n\f" * 12)
        self.write("senses/garbled.pdf", "(cid:12) (cid:7) �� " + "words that came through " * 10 + "\n\f")
        self.write("senses/fine.pdf", "(cid:12) " + "words that came through " * 40 + "\n\f")
        self.write("senses/broken.pdf", "BROKEN")
        self.write("senses/silent.pdf", "SILENT")
        self.write("senses/notes.docx", "PK")
        for source, why in (
                ("senses/scan.pdf", "0 words on 3 pages of scan.pdf: a scan, or pictures with no text to take. Nothing "
                                    "saved; the model reads the file"),
                ("senses/slides.pdf", "12 words on 12 pages of slides.pdf: a scan, or pictures with no text to take. "
                                      "Nothing saved; the model reads the file"),
                ("senses/garbled.pdf", "the text of garbled.pdf came out damaged (4 characters the tool could not decode "
                                       "in 44 words). Nothing saved; the model reads the file"),
                ("senses/broken.pdf", "`pdftotext` could not read broken.pdf: Syntax Error: Couldn't read xref table"),
                ("senses/silent.pdf", "`pdftotext` could not read silent.pdf: it says nothing"),
                ("senses/notes.docx", "notes.docx is not a PDF or an image (.bmp, .gif, .jpeg, .jpg, .pdf, .png, .tif, "
                                      ".tiff, .webp)"),
                ("senses/no-such.pdf", "not a file: senses/no-such.pdf")):
            self.refused(source, why)
        self.assertEqual(self.take("senses/fine.pdf")["words"], 162)  # one stray character in a long text is no damage

    def test_a_tool_that_cannot_be_started_is_reported(self):
        stub = os.path.join(self.out, "stub")
        tool(stub, "pdftotext", "")
        with open(os.path.join(stub, "pdftotext"), "w", encoding="utf-8") as fh:
            fh.write("#!/no/such/interpreter\n")
        r = run_brain(self.root, "extract", self.outside("paper.pdf", PAPER), env=dict(os.environ, PATH=stub))
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertRegex(r.stderr, r"^brain extract: `pdftotext` did not finish: .*\n$")

    def test_a_file_is_extracted_once(self):
        source = self.outside("paper.pdf", PAPER)
        first = self.take(source)
        self.refused(source, f"{source} was extracted before: its text is {first['saved']}")
        self.refused("senses/assets/paper.pdf", f"senses/assets/paper.pdf was extracted before: its text is {first['saved']}")
        self.write("senses/scan.png", BOARD)
        self.write("senses/scan.png.md", "What someone typed from the scan, by hand.\n")
        self.refused("senses/scan.png", "senses/scan.png was extracted before: its text is senses/scan.png.md")
