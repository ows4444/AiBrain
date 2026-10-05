"""Find credentials and personal data in the brain's files, without ever repeating them.

Used by the scan_secrets hook (critical findings, as a page or input is
written) and by `brain check --guard` (everything, every file). A finding is
(kind, severity, line number): the value itself is never returned, so it
cannot end up in a report, a log line or a transcript.

    critical  a credential: remove it at the source and rotate it
    personal  someone's email address or phone number: the owner decides
"""
import os
import re

CRITICAL = (
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI API key", re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{32,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Stripe secret key", re.compile(r"\b[rs]k_live_[0-9A-Za-z]{24,}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
    ("connection string with password", re.compile(r"\b[a-z][a-z0-9+]*://[^\s:/@]+:[^\s@/]{3,}@[^\s/]+", re.I)),
)
PERSONAL = (
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone number", re.compile(r"(?<![\w+])\+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,4}(?!\w)")),
)
SCANNED = ("senses", "inbox", "cortex", "prefrontal", "hippocampus", "dormant", "motor")
TEXT_LIMIT = 2 * 1024 * 1024  # larger files are skipped: archives, media


def scan_text(text, personal=True):
    """[(kind, severity, line)] for each finding in text, in line order."""
    rules = [(k, "critical", r) for k, r in CRITICAL] + ([(k, "personal", r) for k, r in PERSONAL] if personal else [])
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for kind, severity, rule in rules:
            if rule.search(line):
                out.append((kind, severity, n))
    return out


def scan_file(path, personal=True):
    try:
        if os.path.getsize(path) > TEXT_LIMIT:
            return []
        with open(path, encoding="utf-8") as fh:
            return scan_text(fh.read(), personal)
    except (OSError, UnicodeDecodeError):
        return []  # binary or unreadable: not text a key would be pasted into


def scan_tree(root, personal=True):
    """[{path, kind, severity, line}] across the brain's folders (engine/ excluded: it holds the rules)."""
    found = []
    for top in SCANNED:
        for dirpath, dirnames, files in os.walk(os.path.join(root, top)):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for f in sorted(files):
                if f.startswith("."):
                    continue
                path = os.path.join(dirpath, f)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                found += [{"path": rel, "kind": k, "severity": s, "line": n} for k, s, n in scan_file(path, personal)]
    return found
