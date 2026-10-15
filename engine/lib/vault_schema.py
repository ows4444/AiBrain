"""The page contract: what breaks CLAUDE.md > Page contracts in one page's text.

The rules themselves are vocabulary and live in vault_model: the field registry, the
statuses, the claim tags, the limits on a summary and on tags. Three system pages have
lines of their own, and each is checked by the module that reads it: a threshold that is
none (vault_tuning), a reminder that cannot fire (vault_intentions), an action no line can
allow (vault_policy). Those modules take names from vault_model, so the check that calls
all three stands here, above them, and vault_model imports none of them.

Nothing here walks the brain: a page's text is handed in. Vault.schema_problems holds
every page against it, the page hook the one being written. The character page is no
memory page and has no frontmatter: vault_tuning.character_problems reads its traits.
"""
from names import slug
from vault_intentions import intention_problems
from vault_model import (ANSWER_MAX, CLAIM_SECTIONS, CLAIM_TAGS, DATE, DECISION_STATUSES, FIELDS, FILE_NAME, LINK,
                         MAX_ANSWERS, MAX_TAGS, OUTCOMES, OWNER_SAW, PAGE_TYPES, PROBABILITY_TAGS, PROJECT_FIELDS,
                         REQUIRED_FIELDS, STATUSES, SUMMARY_BODY_WORDS, SUMMARY_MAX, SYSTEM_PATHS, SYSTEM_TYPES,
                         as_list, claims_in, parse_frontmatter, system_type_at)
from vault_policy import policy_problems
from vault_tuning import tuning_problems

# What vaultlib hands on to the commands. The rest is for the parts, which import it from here.
__all__ = [
    "check_fields", "file_name_problems", "schema_problems", "summary_problems", "decision_problems", "claim_problems",
]


def check_fields(fields, specs):
    problems = []
    for name, spec in specs.items():
        value = fields.get(name)
        if not value or name == "type":
            continue
        if spec.get("on") and fields.get("type") not in spec["on"]:
            problems.append(f"'{name}' belongs on {' or '.join(spec['on'])} pages only")
        elif spec.get("date") and not DATE.match(str(value)):
            problems.append(f"'{name}' must be YYYY-MM-DD")
        elif spec.get("values") and value not in spec["values"]:
            problems.append(f"'{name}' must be one of {', '.join(spec['values'])}, or absent")
    return problems


def file_name_problems(stem):
    """The file name rule: lowercase-hyphenated, so links and URLs stay stable."""
    if stem is None or FILE_NAME.match(stem):
        return []
    return [f"file name '{stem}' is not lowercase-hyphenated: rename it to '{slug(stem) or 'page'}', keep the title"]


def schema_problems(text, vocabulary=None, page_type=None, stem=None, rel=None):
    """What breaks CLAUDE.md > Page contracts in this page; [] if nothing.

    `page_type` is set for pages whose type comes from where they live (projects).
    `stem` is the file name (a project's folder name), checked when given.
    `rel` is the root-relative path: a system type is accepted only at its own path.
    """
    fields, body = parse_frontmatter(text)
    if page_type == "project":  # an old project without frontmatter is fine
        return file_name_problems(stem) + check_fields(fields or {}, PROJECT_FIELDS)
    if fields is None:
        return ["missing frontmatter block"]
    kind = fields.get("type", "")
    if system_type_at(kind, rel):
        # The system pages with lines of their own: a threshold that is none, a reminder that cannot fire, an
        # action no line can allow. Any other system page has no contract to break.
        return {"tuning": tuning_problems, "intentions": intention_problems,
                "policy": policy_problems}.get(kind, lambda _: [])(body)
    if kind in SYSTEM_TYPES:
        where = SYSTEM_PATHS.get(kind, "prefrontal/<name>/CLAUDE.md, where the folder sets it")
        return [f"type '{kind}' belongs only to {where}; a memory page here is one of {', '.join(PAGE_TYPES)}"]
    problems = file_name_problems(stem)
    if kind not in PAGE_TYPES:
        problems.append(f"type '{kind}' is not one of {', '.join(PAGE_TYPES)}")
    problems += [f"missing '{k}'" for k in REQUIRED_FIELDS if not fields.get(k)]
    if isinstance(fields.get("title"), list):
        problems.append("'title' reads as a list: quote it if it starts with '['")
    problems += check_fields(fields, FIELDS)
    if kind == "concept" and fields.get("status") not in STATUSES:
        problems.append(f"concept 'status' must be one of {', '.join(STATUSES)}")
    if kind == "decision":
        problems += decision_problems(fields)
        if fields.get("status") in ("decided", "reviewed"):  # an open one is still being framed
            problems += claim_problems(body)
    summary = fields.get("summary")
    if isinstance(summary, str) and len(summary) > SUMMARY_MAX:
        problems.append(f"'summary' is {len(summary)} characters; one sentence, at most {SUMMARY_MAX}")
    answers = [str(a) for a in as_list(fields.get("answers"))]
    if len(answers) > MAX_ANSWERS:
        problems.append(f"{len(answers)} questions under 'answers'; at most {MAX_ANSWERS}")
    if any(len(a) > ANSWER_MAX for a in answers):
        problems.append(f"'answers' holds a question of {max(map(len, answers))} characters; each is one short "
                        f"question, at most {ANSWER_MAX}")
    tags = as_list(fields.get("tags"))
    if len(tags) > MAX_TAGS:
        problems.append(f"{len(tags)} tags; at most {MAX_TAGS}")
    unknown = [t for t in tags if vocabulary and t not in vocabulary]
    if unknown:
        problems.append(f"tags {unknown} are not in the vocabulary; propose new tags in CLAUDE.md first")
    return problems


def summary_problems(text):
    """Whether a memory page with text in it lacks its `summary:`; [] for any other file.

    Kept out of schema_problems: pages written before the field existed are
    listed by `brain check`, not failed, and the page hook blocks only a write
    that leaves a page in this state when it was not in it before.
    """
    fields, body = parse_frontmatter(text)
    if not fields or fields.get("type") not in PAGE_TYPES or fields.get("summary"):
        return []
    words = sum(len(line.split()) for line in body.splitlines() if not line.startswith("#"))
    if words < SUMMARY_BODY_WORDS:
        return []
    return [f"missing 'summary': one sentence, at most {SUMMARY_MAX} characters, saying what the page holds, "
            "so a reader of `brain recall` can tell whether to open it"]


def decision_problems(fields):
    status = fields.get("status")
    if status not in DECISION_STATUSES:
        return [f"decision 'status' must be one of {', '.join(DECISION_STATUSES)}"]
    problems = []
    if status in ("decided", "reviewed") and not fields.get("review"):
        problems.append(f"a {status} decision needs 'review: YYYY-MM-DD', when to check the outcome")
    if status in ("decided", "reviewed") and not fields.get("revisit_if"):
        problems.append(f"a {status} decision needs 'revisit_if:', the event that means look again before the date")
    if status == "reviewed" and fields.get("outcome") not in OUTCOMES:
        problems.append(f"a reviewed decision needs 'outcome' as one of {', '.join(OUTCOMES)}")
    if status != "reviewed" and fields.get("outcome"):
        problems.append("'outcome' is set only once the decision is reviewed")
    return problems


def claim_problems(body):
    """What breaks the claim-tag rule (CLAUDE.md > Page contracts) in a decision's body; [] if nothing."""
    problems = []
    claims = [c for c in claims_in(body) if c["section"] in CLAIM_SECTIONS]
    for section in CLAIM_SECTIONS:
        untagged = sum(c["section"] == section and c["tag"] not in CLAIM_TAGS for c in claims)
        if untagged:
            problems.append(f"{untagged} untagged lines under ## {section}: start each with "
                            f"- [{'], ['.join(CLAIM_TAGS)}]")
    for c in claims:
        if c["p"] is not None and c["tag"] not in PROBABILITY_TAGS:
            problems.append(f"[{c['tag']} {round(c['p'] * 100)}%]: only a "
                            f"{' or '.join(PROBABILITY_TAGS)} carries a probability")
        elif c["p"] is not None and c["p"] > 1:
            problems.append(f"[{c['tag']} {round(c['p'] * 100)}%]: a probability is 0-100%")
        if c["tag"] == "decision" and c["section"] != "Decision":
            problems.append(f"[decision] belongs under ## Decision only, found under ## {c['section']}")
        if c["tag"] == "observation" and not LINK.search(c["text"]) and not OWNER_SAW.search(c["text"]):
            problems.append(f"[observation] '{c['text'][:40]}' cites nothing: link the page, or add (owner, YYYY-MM-DD)")
    return problems
