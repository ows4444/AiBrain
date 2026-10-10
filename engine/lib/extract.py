"""A PDF or an image as input: its text, read by a tool on this machine, saved in senses/.

Usage:
    brain extract FILE [--name SLUG] [--dry-run] [--json]

A PDF is read with `pdftotext` (poppler), an image (png, jpg, tiff, bmp, gif,
webp) with `tesseract`. Neither comes with the engine, which stays standard
library only. When the tool a file needs is not installed, nothing is written
and the command exits 1 saying so: the model then reads the file, as it did
before there was this command.

The text lands in senses/ with frontmatter (`transcribed_from`,
`extracted_with`, `pages`, `extracted`), and the path, the pages and the
words are printed, so only that file is read and the original never enters
the conversation. It has no `title:`: the tool cannot tell one, so the
episode is given its title by whoever read the text.

Where the original is kept, and its text:
    a file outside senses/     copied to senses/assets/ (moved, when it was in
                               this brain's inbox/); the text is
                               senses/<today>-<slug>.md
    a file in senses/assets/   stays; the text is senses/<today>-<slug>.md
    a file elsewhere in        stays: an input is never moved. The text is
    senses/                    written beside it as <file>.md, and from then
                               on the two count as one input, the text
`brain forget` removes a text and its original together.

Reported, nothing saved, exit 1: too few words for the pages (a scan, a PDF
of pictures, an image with no text), text the tool could not decode, a file
the tool cannot open, and a file that was extracted before.
"""
import datetime
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from fetch import quoted, slug  # noqa: E402
from fingerprint import inputs, sha256  # noqa: E402
from vault_model import parse_frontmatter  # noqa: E402

FILE = "{file}"
PDF = ("pdftotext", ["-enc", "UTF-8", "-eol", "unix", FILE, "-"])  # reading order, not -layout: prose over columns
OCR = ("tesseract", [FILE, "stdout"])
# the ending of a file -> (the tool that reads it, its arguments)
READERS = {".pdf": PDF, **{ext: OCR for ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp")}}
TIMEOUT = 120
MIN_WORDS = 8        # a page, on average: fewer is a scan, a PDF of pictures, or an image with no text
MAX_DAMAGED = 0.02   # of the words: more undecoded characters than this and the text is not the document's
DAMAGED = re.compile(r"�|\(cid:\d+\)")
SENSES, ASSETS, INBOX = "senses", "senses/assets", "inbox"


def read(path):
    """(the text, the tool that read it, how many pages). Refused when nothing here can read the file."""
    kind = os.path.splitext(path)[1].lower()
    if kind not in READERS:
        raise Refused(f"{os.path.basename(path)} is not a PDF or an image ({', '.join(sorted(READERS))})")
    tool, argv = READERS[kind]
    if not shutil.which(tool):
        raise Refused(f"no `{tool}` on this machine to read a {kind[1:]} file with; nothing saved. The model reads "
                      "the file")
    try:
        done = subprocess.run([tool, *(path if word == FILE else word for word in argv)], capture_output=True,
                              timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise Refused(f"`{tool}` did not finish: {err}") from None
    if done.returncode:
        said = done.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise Refused(f"`{tool}` could not read {os.path.basename(path)}: {said[0] if said else 'it says nothing'}")
    raw = done.stdout.decode("utf-8", errors="replace")
    pages = [re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in page.splitlines())).strip()
             for page in raw.split("\f")]  # both tools end a page with a form feed
    return "\n\n".join(page for page in pages if page), tool, max(1, raw.count("\f"))


def where(root, path):
    """(where the original is kept from the brain's root, how it gets there, where its text goes if not by date).

    How: "copy" from outside the brain, "move" from its inbox/, None for a file that stays where it is.
    """
    rel = os.path.relpath(os.path.realpath(path), os.path.realpath(root)).replace(os.sep, "/")
    if rel.startswith(ASSETS + "/"):
        return rel, None, None
    if rel.startswith(SENSES + "/"):
        return rel, None, rel + ".md"
    stem, kind = os.path.splitext(os.path.basename(path))
    kept, n = f"{ASSETS}/{stem}{kind}", 1
    while os.path.exists(os.path.join(root, kept)):
        if sha256(os.path.join(root, kept)) == sha256(path):  # the same file was put here before
            return kept, None, None
        n += 1
        kept = f"{ASSETS}/{stem}-{n}{kind}"
    return kept, "move" if rel.startswith(INBOX + "/") else "copy", None


def text_of(root, kept, beside):
    """The input that already holds the text of the original at `kept`, or None."""
    if beside and os.path.exists(os.path.join(root, beside)):
        return beside
    for rel in inputs(root):
        if rel.endswith(".md"):
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                fields = parse_frontmatter(fh.read(4096))[0] or {}
            if f"{SENSES}/{fields.get('transcribed_from')}" == kept:
                return rel
    return None


def extract(root, source, name=None, dry_run=False, today=None):
    """Read the file and land its text; {saved, path, original, placed, tool, pages, words}."""
    path = os.path.abspath(os.path.join(root, source))
    if not os.path.isfile(path):
        raise Refused(f"not a file: {source}")
    kept, how, beside = where(root, path)
    before = text_of(root, kept, beside)
    if before:
        raise Refused(f"{source} was extracted before: its text is {before}")
    body, tool, pages = read(path)
    words = len(re.findall(r"\w+", body))
    if words < MIN_WORDS * pages:
        raise Refused(f"{words} words on {pages} pages of {os.path.basename(path)}: a scan, or pictures with no text "
                      "to take. Nothing saved; the model reads the file")
    damaged = len(DAMAGED.findall(body))
    if damaged > MAX_DAMAGED * words:
        raise Refused(f"the text of {os.path.basename(path)} came out damaged ({damaged} characters the tool could "
                      f"not decode in {words} words). Nothing saved; the model reads the file")
    day = (today or datetime.date.today()).isoformat()
    stem, n = f"{day}-{slug(name or os.path.splitext(os.path.basename(path))[0]) or 'document'}", 1
    rel = beside or f"{SENSES}/{stem}.md"
    while not beside and os.path.exists(os.path.join(root, rel)):  # never over a file that is there
        n += 1
        rel = f"{SENSES}/{stem}-{n}.md"
    head = ["---", f"transcribed_from: {quoted(kept[len(SENSES) + 1:])}", f"extracted_with: {tool}", f"pages: {pages}",
            f"extracted: {day}", "---", "", ""]
    if not dry_run:
        if how:
            os.makedirs(os.path.join(root, ASSETS), exist_ok=True)
            (shutil.move if how == "move" else shutil.copyfile)(path, os.path.join(root, kept))
        with open(os.path.join(root, rel), "x", encoding="utf-8") as fh:
            fh.write("\n".join(head) + body + "\n")
    return {"saved": None if dry_run else rel, "path": rel, "original": kept, "placed": how, "tool": tool,
            "pages": pages, "words": words}


def arguments(ap):
    ap.add_argument("file")
    ap.add_argument("--name", help="the slug of the text's file name; else the file's own name")
    ap.add_argument("--dry-run", action="store_true")


def run(root, args):
    try:
        return extract(root, args.file, args.name, args.dry_run)
    except Refused as why:
        raise Refused(f"brain extract: {why}") from None


def render(r, args):
    placed = {"copy": "copied to", "move": "moved to", None: "stays at"}[r["placed"]]
    if r["placed"] and not r["saved"]:
        placed = "would be " + placed
    return "\n".join([
        f"{'saved' if r['saved'] else 'would save'} {r['path']}",
        f"  {r['pages']} pages -> {r['words']} words, read with {r['tool']}; the original {placed} {r['original']}",
        "  read that file, not the original, and give the episode its title (`brain new episode --from ... --title`); "
        "run `brain fingerprint` once it is in place"])
