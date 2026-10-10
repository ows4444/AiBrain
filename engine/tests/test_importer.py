"""`brain import`: notes kept in another tool land in senses/, one input a note, and never twice. Run: brain test"""
import hashlib
import json
import os
import tempfile

from support import TempBrain, page, run_brain, vaultlib

import importer  # noqa: E402  (support puts engine/lib on the path)

DATES = dict(created="2026-01-01", updated="2026-01-01")
SPACING = b"# Spacing\r\n\r\nStudy spread over days lasts longer. See [[Cramming]].\r\n"  # CRLF: kept as it is
CAF = b"Caf\xe9 notes, saved in Latin-1 long ago.\n"  # not UTF-8: copied, not read


class Vault(TempBrain):
    """A vault beside the brain: notes in folders, Obsidian's own folders, an attachment, and what is left out."""

    def setUp(self):
        super().setUp()
        self.beside = tempfile.TemporaryDirectory()
        self.addCleanup(self.beside.cleanup)
        self.vault = os.path.join(os.path.realpath(self.beside.name), "My Vault")
        self.write("senses/held.md", "A thought kept twice.\n")
        for rel, data in (("Spacing.md", SPACING), ("Reading/Cepeda 2006.MD", b"A review of 254 studies.\n"),
                          ("Reading/old/caf.md", CAF), ("Twice.md", b"A thought kept twice.\n"),
                          ("Zettel/a.md", b"The same words in two notes.\n"), ("Zettel/b.md", b"The same words in two notes.\n"),
                          ("README.md", b"About this vault.\n"), ("blank.md", b" \n\t\n"), ("nothing.md", b""),
                          ("picture.png", b"\x89PNG"), ("board.canvas", b"{}"), (".hidden.md", b"A hidden note.\n"),
                          (".obsidian/app.json", b"{}"), (".obsidian/plugins/x/notes.md", b"A plugin's note.\n"),
                          (".trash/thrown.md", b"Thrown away.\n")):
            self.note(rel, data)

    def note(self, rel, data):
        path = os.path.join(self.vault, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)

    def bring(self, *args):
        r = run_brain(self.root, "import", "obsidian", self.vault, *args, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def senses(self):
        """{path from the brain: bytes} of everything in senses/."""
        out = {}
        for folder, _, files in os.walk(os.path.join(self.root, "senses")):
            for name in files:
                with open(os.path.join(folder, name), "rb") as fh:
                    out[os.path.relpath(os.path.join(folder, name), self.root)] = fh.read()
        return out


class ObsidianVault(Vault):
    INTO = "senses/obsidian/My Vault"
    NEW = [f"{INTO}/Reading/Cepeda 2006.MD", f"{INTO}/Reading/old/caf.md", f"{INTO}/Spacing.md", f"{INTO}/Zettel/a.md"]

    def test_each_note_lands_once_as_it_is_and_a_second_run_adds_nothing(self):
        """Done when: an import run twice adds nothing the second time."""
        first = self.bring()
        self.assertEqual(first, {
            "source": "obsidian", "from": self.vault, "into": self.INTO, "written": True, "imported": self.NEW,
            "already": 0, "changed": [], "forgotten": [], "not_inputs": ["README.md"], "empty": 2, "attachments": 2,
            "duplicates": [{"note": "Twice.md", "same_as": "senses/held.md"},
                           {"note": "Zettel/b.md", "same_as": f"{self.INTO}/Zettel/a.md"}]})
        landed = self.senses()
        self.assertEqual(sorted(landed), sorted(self.NEW + ["senses/held.md"]))  # nothing of .obsidian/ or .trash/
        self.assertEqual((landed[f"{self.INTO}/Spacing.md"], landed[f"{self.INTO}/Reading/old/caf.md"]), (SPACING, CAF))
        self.assertEqual(sorted(self.brain().unencoded()), sorted(self.NEW + ["senses/held.md"]))  # they wait for /ingest
        second = self.bring()
        self.assertEqual((second["imported"], second["already"], second["duplicates"]), ([], 4, first["duplicates"]))
        self.assertEqual(self.senses(), landed)
        self.note("Later.md", b"Written after the first import.\n")  # only what is new comes in
        self.assertEqual(self.bring()["imported"], [f"{self.INTO}/Later.md"])

    def test_a_dry_run_says_the_same_and_writes_nothing(self):
        before = self.senses()
        dry = self.bring("--dry-run")
        self.assertEqual((dry["imported"], dry["written"]), (self.NEW, False))
        self.assertEqual(self.senses(), before)
        self.assertFalse(os.path.exists(os.path.join(self.root, "senses", "obsidian")))
        self.assertEqual(run_brain(self.root, "import", "obsidian", self.vault, "--dry-run").stdout, (
            f"import obsidian: 4 notes -> {self.INTO}/ (dry run, nothing written)\n"
            "  left out: 0 already there, 0 changed since their import, 2 the same as another input, 0 forgotten, "
            "1 named README.md, 2 empty; 2 other files not copied\n"
            "  the same as senses/held.md: Twice.md\n"
            f"  the same as {self.INTO}/Zettel/a.md: Zettel/b.md\n"
            "  not read as an input under that name (rename it at the source): README.md\n"))

    def test_a_note_edited_since_is_listed_and_the_input_stays_as_it_landed(self):
        self.bring()
        self.note("Spacing.md", SPACING + b"\r\nA line added in the vault.\r\n")
        again = self.bring()
        self.assertEqual((again["imported"], again["already"], again["changed"]), ([], 3, [f"{self.INTO}/Spacing.md"]))
        self.assertEqual(self.senses()[f"{self.INTO}/Spacing.md"], SPACING)
        self.assertIn("  changed at the source since their import (an input is never edited, so not brought in again):\n"
                      f"    {self.INTO}/Spacing.md\n", run_brain(self.root, "import", "obsidian", self.vault).stdout)

    def test_what_the_owner_had_removed_does_not_come_back_under_its_path_or_another(self):
        self.write("hippocampus/fingerprints.md", page("fingerprints", "\n".join((
            f"2026-09-01 {hashlib.sha256(CAF).hexdigest()} senses/2019-notes.md",  # its text, under the name it had here
            "2026-09-02 forgotten senses/2019-notes.md",
            f"2026-09-02 forgotten {self.INTO}/Spacing.md",  # never recorded: known by its path alone
            f"2026-09-03 {'0' * 64} senses/kept.md")) + "\n"))
        found = self.bring()
        self.assertEqual(found["forgotten"], ["Reading/old/caf.md", "Spacing.md"])
        self.assertEqual(found["imported"], [f"{self.INTO}/Reading/Cepeda 2006.MD", f"{self.INTO}/Zettel/a.md"])
        text = run_brain(self.root, "import", "obsidian", self.vault).stdout
        self.assertIn("2 forgotten", text)
        self.assertIn("  forgotten on the owner's word, not brought back: Spacing.md\n", text)
        self.assertNotIn(f"{self.INTO}/Spacing.md", self.senses())

    def test_the_text_says_what_landed_and_what_comes_next(self):
        r = run_brain(self.root, "import", "obsidian", self.vault)
        self.assertEqual(r.stdout.splitlines()[0], f"import obsidian: 4 notes -> {self.INTO}/")
        self.assertEqual(r.stdout.splitlines()[-1], "  /ingest encodes them: nothing is memory until then")
        self.assertNotIn("/ingest", run_brain(self.root, "import", "obsidian", self.vault).stdout)  # nothing new the second time


class WhereTheNotesAre(Vault):
    def test_a_folder_that_is_not_there_or_is_inside_the_brain_is_refused(self):
        missing = os.path.join(self.vault, "no such folder")
        for where, why in ((missing, f"not a folder: {missing}"),
                           (os.path.join(self.vault, "Spacing.md"), f"not a folder: {os.path.join(self.vault, 'Spacing.md')}"),
                           (self.root, "that folder is inside this brain: an import brings notes in from somewhere else"),
                           (os.path.join(self.root, "senses"),
                            "that folder is inside this brain: an import brings notes in from somewhere else")):
            r = run_brain(self.root, "import", "obsidian", where)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", f"brain import: {why}\n"))
        self.assertEqual(sorted(self.senses()), ["senses/held.md"])

    def test_a_brain_kept_inside_the_vault_is_not_imported_into_itself(self):
        inside = os.path.join(self.vault, "Brain")
        for folder in vaultlib.MEMORY_DIRS:
            os.makedirs(os.path.join(inside, folder))
        self.note("Brain/CLAUDE.md", b"# Brain\n")
        self.note("Brain/cortex/concepts/spacing-effect.md", page("concept", "A page, not a note.\n", **DATES).encode())
        first = importer.bring_in(inside, "obsidian", self.vault)
        self.assertEqual(len(first["imported"]), 5)  # the four of the vault and the one held here only
        self.assertFalse([path for path in first["imported"] if "/Brain/" in path])
        self.assertEqual(importer.bring_in(inside, "obsidian", self.vault)["imported"], [])  # nor its own copies, next time

    def test_only_a_source_there_is_an_importer_for_is_taken(self):
        r = run_brain(self.root, "import", "notion", self.vault)
        self.assertEqual(r.returncode, 2)
        self.assertIn("argument source: invalid choice: 'notion'", r.stderr)
