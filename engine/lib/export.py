"""Export pages for use outside the brain, without leaking what was not exported.

Usage:
    brain export PAGE ... [--out motor/export] [--json]
    brain export --published [--out motor/export] [--json]

PAGE is a file name, title or alias. --published takes every page marked
`publish: true` (opt-in only; nothing is exported because it was not excluded).
Links to pages inside the export stay links; links to anything else become
plain text. A link written `[[page|label]]` leaves as its label. A bare link
would leave as the title of a page that was not exported, so the export stops
and lists those titles; --keep-titles lets them through. Frontmatter fields that
describe the brain rather than the content (those marked private in
`vaultlib.FIELDS`: input, tags, status, review, outcome, ...) are dropped.
A page that holds what looks like a credential stops the export: nothing is
written, and the file, the kind and the line are named, never the value.
Personal data (an email address, a phone number) in what was exported is
listed the same way; whether it may leave is the owner's call.
Writes only under --out; never modifies the brain.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commands import Refused  # noqa: E402
from secret_scan import scan_text  # noqa: E402
from vaultlib import LINK, PRIVATE_FIELDS, Vault  # noqa: E402
FIELD = re.compile(r"^([\w-]+):")


def strip_frontmatter(text):
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end < 0:
        return text
    kept, dropping = [], False
    for line in text[4:end].splitlines():
        field = FIELD.match(line)
        if field:
            dropping = field.group(1) in PRIVATE_FIELDS
        if not dropping:  # a private field's block-list items go with it
            kept.append(line)
    return "---\n" + "\n".join(kept) + text[end:]


def rewrite_links(text, vault, exported, leaked=None):
    """Links out of the export become text; `leaked` collects the unexported pages whose title that text is."""
    def replace(m):
        target, label = m.group(1).strip(), m.group(0)[2:-2]
        dest = vault.resolve(target)
        if dest in exported:
            return m.group(0)
        if "|" in label:
            return label.split("|", 1)[1]
        if dest is not None and leaked is not None:
            leaked.add(dest)
        return target
    return LINK.sub(replace, text)


def arguments(ap):
    ap.add_argument("pages", nargs="*")
    ap.add_argument("--published", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--keep-titles", action="store_true")


def run(root, args):
    vault = Vault(root)
    if args.published:
        chosen = [p for p in vault.knowledge if p.fields.get("publish") == "true"]
    else:
        chosen, missing = [], []
        for name in args.pages:
            page = vault.resolve(name)
            if page:
                chosen.append(page)
            else:
                missing.append(name)
        if missing:
            raise Refused(f"no page named: {', '.join(missing)}")
    if not chosen:
        raise Refused("nothing to export (pass page names, or --published with pages marked publish: true)")

    out = args.out or os.path.join(vault.root, "motor", "export")
    exported, unlinked, leaked = set(chosen), 0, set()
    texts = {page: rewrite_links(strip_frontmatter(page.text), vault, exported, leaked) for page in chosen}
    found = [(page.rel, kind, severity, line) for page in chosen for kind, severity, line in scan_text(page.text)]
    secrets = [f"{rel}:{line}: {kind}" for rel, kind, severity, line in found if severity == "critical"]
    if secrets:
        raise Refused("not exported: possible credential in " + ", ".join(secrets)
                      + ". Remove it at the source and rotate it; nothing was written.")
    if leaked and not args.keep_titles:
        raise Refused("not exported: these pages are not in the export, and their titles would leave as plain text: "
                      + ", ".join(sorted(p.title for p in leaked))
                      + ". Export them too, write the links as [[page|label]], or pass --keep-titles.")
    for page, text in texts.items():
        before = len(LINK.findall(page.text))
        unlinked += before - len(LINK.findall(text))
        dest = os.path.join(out, page.rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)
    return {"exported": [page.rel for page in chosen], "out": out, "unlinked": unlinked,
            "personal": [f"{rel}:{line}: {kind}" for rel, kind, severity, line in found if severity == "personal"]}


def render(result, args):
    said = (f"exported {len(result['exported'])} pages to {result['out']}; "
            f"{result['unlinked']} links to unexported pages made plain text")
    if result["personal"]:
        said += "\npersonal data in what was exported (the owner decides whether it may leave):\n" + \
            "\n".join(f"  {found}" for found in result["personal"])
    return said
