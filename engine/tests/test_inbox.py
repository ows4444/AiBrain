"""`brain inbox`: what waits in inbox/ is sorted before any of it lands in senses/. Run: brain test"""
import hashlib
import json
import os
from unittest import mock

from support import TempBrain, page, run_brain

import inbox  # noqa: E402  (support puts engine/lib on the path)

KEY = "AKIA" + "A" * 16
GONE = "A thought the owner had removed.\n"


class MixedInbox(TempBrain):
    """Done when: /ingest on a mixed inbox encodes only what the scout passed. The scout starts from this list."""

    def setUp(self):
        super().setUp()
        self.write("senses/inbox/2026-10-01-idea.md", "An idea kept before.\n")
        self.write("hippocampus/fingerprints.md", page("fingerprints", "\n".join((
            f"2026-09-01 {hashlib.sha256(GONE.encode()).hexdigest()} senses/inbox/2026-09-01-gone.md",
            "2026-09-02 forgotten senses/inbox/2026-09-01-gone.md")) + "\n"))
        for name, text in (("README.md", "What this folder is for.\n"), (".DS_Store", "\n"),
                           ("a-thought.md", "Spacing beats cramming.\n"), ("b-copy.md", "An idea kept before.\n"),
                           ("c-again.md", "Spacing beats cramming.\n"), ("d-keys.md", f"The staging key\nis {KEY}\n"),
                           ("e-contact.md", "Ask about it.\nWrite to someone@example.org, or +44 20 7946 0958.\n"),
                           ("f-blank.md", " \n\t\n"), ("g-gone.md", GONE), ("k-keys-again.md", f"The staging key\nis {KEY}\n")):
            self.write(f"inbox/{name}", text)
        for name, data in (("h-photo.png", b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR"), ("i-latin.txt", b"Caf\xe9 notes\n"),
                           ("l-paper.PDF", b"%PDF-1.4\n\xe2\xe3\xcf\xd3\n"), ("m-paper-again.pdf", b"%PDF-1.4\n\xe2\xe3\xcf\xd3\n"),
                           ("n-nothing.md", b""), ("o-plain.pdf", b"%PDF-1.4\nA PDF written out in plain characters.\n")):
            with open(os.path.join(self.root, "inbox", name), "wb") as fh:
                fh.write(data)
        os.makedirs(os.path.join(self.root, "inbox", "j-folder"))

    def kinds(self, rows):
        return {row["note"][len("inbox/"):]: row["kind"] for row in rows}

    def test_each_note_is_sorted_and_only_new_text_is_ready(self):
        found = json.loads(run_brain(self.root, "inbox", "--json").stdout)
        self.assertEqual(self.kinds(found["notes"]), {
            "a-thought.md": "ready", "b-copy.md": "duplicate", "c-again.md": "duplicate", "d-keys.md": "secret",
            "e-contact.md": "ready", "f-blank.md": "empty", "g-gone.md": "forgotten", "h-photo.png": "not_text",
            "i-latin.txt": "not_text", "j-folder": "not_text", "k-keys-again.md": "secret", "l-paper.PDF": "not_text",
            "m-paper-again.pdf": "duplicate", "n-nothing.md": "empty", "o-plain.pdf": "not_text"})
        self.assertEqual(found["ready"], ["inbox/a-thought.md", "inbox/e-contact.md"])
        rows = {row["note"]: row for row in found["notes"]}
        self.assertEqual(rows["inbox/b-copy.md"]["same_as"], "senses/inbox/2026-10-01-idea.md")  # an input
        self.assertEqual(rows["inbox/c-again.md"]["same_as"], "inbox/a-thought.md")  # an earlier note here
        self.assertEqual(rows["inbox/m-paper-again.pdf"]["same_as"], "inbox/l-paper.PDF")  # by its hash, text or not
        self.assertEqual([rows[f"inbox/{name}"]["reader"] for name in ("h-photo.png", "i-latin.txt", "j-folder", "l-paper.PDF")],
                         ["tesseract", None, None, "pdftotext"])  # what `brain extract` reads, and what nothing does
        self.assertEqual(rows["inbox/d-keys.md"]["found"], [{"kind": "AWS access key", "line": 2}])
        self.assertEqual(rows["inbox/e-contact.md"]["personal"], [{"kind": "email address", "line": 2},
                                                                 {"kind": "phone number", "line": 2}])
        self.assertEqual(rows["inbox/a-thought.md"], {"note": "inbox/a-thought.md", "kind": "ready", "bytes": 24,
                                                      "personal": []})
        self.assertNotIn(KEY, json.dumps(found))  # the kind and the line, never the value

    def test_the_text_says_why_each_note_is_not_ready(self):
        before = sorted(os.listdir(os.path.join(self.root, "inbox")))
        r = run_brain(self.root, "inbox")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout, "\n".join((
            "inbox: 15 notes, 2 ready for /ingest",
            "  ready      inbox/a-thought.md",
            "  duplicate  inbox/b-copy.md: the same as senses/inbox/2026-10-01-idea.md",
            "  duplicate  inbox/c-again.md: the same as inbox/a-thought.md",
            "  secret     inbox/d-keys.md: AWS access key on line 2. Not for senses/, where nothing is edited again: "
            "take the value out first",
            "  ready      inbox/e-contact.md (personal: email address on line 2, phone number on line 2)",
            "  empty      inbox/f-blank.md: no text",
            "  forgotten  inbox/g-gone.md: an input removed on the owner's word",
            "  not text   inbox/h-photo.png: a PDF or an image: `brain extract` reads it where `tesseract` is installed, "
            "else the model does",
            "  not text   inbox/i-latin.txt: nothing here reads it: say what it is, or bring it in as text",
            "  not text   inbox/j-folder: nothing here reads it: say what it is, or bring it in as text",
            "  secret     inbox/k-keys-again.md: AWS access key on line 2. Not for senses/, where nothing is edited "
            "again: take the value out first",
            "  not text   inbox/l-paper.PDF: a PDF or an image: `brain extract` reads it where `pdftotext` is installed, "
            "else the model does",
            "  duplicate  inbox/m-paper-again.pdf: the same as inbox/l-paper.PDF",
            "  empty      inbox/n-nothing.md: no text",
            "  not text   inbox/o-plain.pdf: a PDF or an image: `brain extract` reads it where `pdftotext` is installed, "
            "else the model does")) + "\n")
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "inbox"))), before)  # it reads; it moves nothing

    def test_it_counts_the_notes_the_briefing_and_the_digest_count(self):
        digest = json.loads(run_brain(self.root, "tend", "--check", "--json").stdout)
        self.assertEqual(digest["inbox"], inbox.waiting(self.root))
        self.assertEqual(len(inbox.sort(self.root)), len(digest["inbox"]))

    def test_a_file_too_large_to_be_a_note_is_not_read(self):
        with mock.patch.object(inbox, "TEXT_LIMIT", 30):
            rows = {row["note"]: row for row in inbox.sort(self.root)}
        self.assertEqual(rows["inbox/d-keys.md"], {"note": "inbox/d-keys.md", "kind": "not_text", "bytes": 40,
                                                   "reader": None})  # not read, so nothing is found in it
        self.assertEqual(rows["inbox/a-thought.md"]["kind"], "ready")


class NothingWaiting(TempBrain):
    def test_an_empty_inbox_and_no_inbox_say_so(self):
        self.assertEqual(run_brain(self.root, "inbox").stdout, "inbox: nothing waiting\n")
        self.write("inbox/README.md", "What this folder is for.\n")
        self.assertEqual(run_brain(self.root, "inbox").stdout, "inbox: nothing waiting\n")
        self.assertEqual(json.loads(run_brain(self.root, "inbox", "--json").stdout), {"notes": [], "ready": []})
