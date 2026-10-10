"""Policy: the brain's own actions in one registry, and what it may do with nobody there. Run: brain test"""
import json
import os
import subprocess
import sys
import unittest

from support import ENGINE, HOOKS, TempBrain, page, run_brain, vaultlib

import act  # noqa: E402  (support puts engine/lib on the path)
import commands  # noqa: E402
import index  # noqa: E402
import vault_policy  # noqa: E402
from vault_policy import ACTIONS, CHANGES, FINAL, OUTSIDE, READS, decide  # noqa: E402

DATES = dict(created="2026-01-01", updated="2026-01-01")
CHANGING = sorted(name for name, action in ACTIONS.items() if action.tier == CHANGES)
PAGE = "hippocampus/policy.md"


class Registry(unittest.TestCase):
    def test_every_action_has_a_tier_and_only_what_may_run_has_a_command(self):
        for name, action in ACTIONS.items():
            with self.subTest(name):
                self.assertIn(action.tier, (READS, CHANGES, OUTSIDE, FINAL))
                self.assertTrue(action.what and not action.what.endswith("."))
                self.assertRegex(name, r"^[a-z]+$")
                if action.tier in (READS, CHANGES):
                    self.assertIn(action.command[0], commands.COMMANDS)  # a `brain` command, called as any is
                else:
                    self.assertIsNone(action.command)  # nothing to call: it is here to be refused for its reason
        self.assertEqual(CHANGING, ["fingerprint", "graph", "index", "snapshot"])

    def test_the_one_place_that_says_whether_an_action_may_run(self):
        for name, action in ACTIONS.items():
            with self.subTest(name):
                bare, named = decide(name, frozenset()), decide(name, frozenset(ACTIONS))  # every name, as if forged
                if action.tier == READS:
                    self.assertEqual((bare, named), ((True, "it only reads"),) * 2)
                elif action.tier == CHANGES:
                    self.assertEqual(named, (True, "hippocampus/policy.md allows it"))
                    self.assertEqual(bare, (False, "it changes the brain, and hippocampus/policy.md does not allow it: "
                                                   f"a line `- {name} (why)` under `## Allowed` there, written by the "
                                                   "owner, lets it run with nobody there"))
                else:  # no page can allow it, whatever it says
                    self.assertEqual(bare, named)
                    self.assertFalse(bare[0])
        self.assertEqual(decide("fetch", {"fetch"})[1], "it reaches outside the brain, and no line of the policy can "
                                                         "allow that: it waits for the owner's yes")
        self.assertEqual(decide("forget", {"forget"})[1], "it cannot be undone: only the owner does it, in a session")

    def test_a_name_is_taken_as_given_and_nothing_else_is_an_action(self):
        allowed = frozenset(CHANGING)
        for worded in ("Index", "INDEX", "index ", " index", "index --yes", "index; rm -rf .", "../index", "index\n",
                       "brain index", "", "rm", "sleep", "tend", None, 7):
            with self.subTest(worded):
                may, why = decide(worded, allowed)
                self.assertFalse(may)
                self.assertTrue(why.startswith(f"'{worded}' is not an action"))
        self.assertEqual(decide("indx", allowed)[1], "'indx' is not an action (closest: index); `brain act` lists them")


class Page(TempBrain):
    def policy(self, *lines):
        """Write the policy page holding these lines under `## Allowed`, as the owner would by hand."""
        return self.write(vaultlib.POLICY_PATH, page("policy", "\n# Policy\n\nWhat may run with nobody there.\n\n"
                                                     "## Allowed\n\n" + "".join(f"- {line}\n" for line in lines),
                                                     title="Policy"))


class ThePage(Page):
    def test_a_line_is_an_action_and_an_optional_note_and_what_cannot_be_used_is_listed(self):
        text = "# Policy\n\n## Allowed\n\nWhat I let it do.\n\n- index (2026-10-12: derived, nothing is lost)\n- `snapshot`\n" \
               "- check (it may anyway)\n\n## Notes\n\n- fetch (prose here, not a line of the policy)\n"
        self.assertEqual(vault_policy.read_policy(text), (["index", "snapshot"], []))  # a reading one needs no line
        self.assertEqual(vault_policy.read_policy("# Policy\n\nNo heading for it.\n"), ([], []))
        allowed, problems = vault_policy.read_policy(
            "## Allowed\n\n- indx\n- fetch (I trust it)\n- forget\n- index\n- index (again)\n- graph and snapshot\n- zeal\n")
        self.assertEqual(allowed, ["index"])
        self.assertEqual(problems, [
            "'indx' is not an action (closest: index); `brain act` lists them",
            "'fetch' cannot be allowed here: it reaches outside the brain, and no line of the policy can allow that: "
            "it waits for the owner's yes",
            "'forget' cannot be allowed here: it cannot be undone: only the owner does it, in a session",
            "'index' is allowed twice; one line is enough",
            "cannot read '- graph and snapshot': a line here is `- action (why)`",
            "'zeal' is not an action; `brain act` lists them"])

    def test_the_template_page_allows_nothing_and_its_type_belongs_to_that_one_file(self):
        with open(os.path.join(ENGINE, "templates", "brain", vaultlib.POLICY_PATH), encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(vault_policy.read_policy(text), ([], []))
        self.assertEqual(vaultlib.schema_problems(text, rel=vaultlib.POLICY_PATH), [])
        self.assertEqual(vaultlib.schema_problems(text, stem="policy", rel="cortex/concepts/policy.md"), [
            f"type 'policy' belongs only to {PAGE}; a memory page here is one of episode, concept, entity, "
            "insight, decision"])
        self.assertEqual(vaultlib.policy_of(self.root), frozenset())  # a brain without the page allows none

    def test_check_fails_on_a_line_no_policy_can_hold_and_what_could_be_read_is_in_force(self):
        self.policy("index (derived)", "fetch", "indx")
        r = run_brain(self.root, "check", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["schema"], [{"page": PAGE, "problems": [
            "'fetch' cannot be allowed here: it reaches outside the brain, and no line of the policy can allow that: "
            "it waits for the owner's yes", "'indx' is not an action (closest: index); `brain act` lists them"]}])
        self.assertEqual(vaultlib.policy_of(self.root), frozenset({"index"}))
        self.policy("index (derived)")
        self.assertEqual(run_brain(self.root, "check").returncode, 0)


class Act(Page):
    def setUp(self):
        super().setUp()
        with open(index.TEMPLATE, encoding="utf-8") as fh:
            self.write("hippocampus/index.md", fh.read())
        self.write("cortex/concepts/spacing.md", page("concept", "Study spread over days lasts.\n", title="Spacing effect",
                                                      status="established", summary="Spread study lasts.", **DATES))

    def on_disk(self):
        found = {}
        for folder, _, names in os.walk(self.root):
            for name in names:
                if ".cache" not in folder:
                    with open(os.path.join(folder, name), encoding="utf-8") as fh:
                        found[os.path.relpath(os.path.join(folder, name), self.root)] = fh.read()
        return found

    def errors(self):
        path = os.path.join(self.root, ".cache", "errors.log")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return fh.read().splitlines()

    def test_one_that_reads_runs_without_a_word_from_the_page_and_leaves_no_trace(self):
        before = self.on_disk()
        found = commands.call("act", ["check"], root=self.root)
        self.assertEqual({k: found[k] for k in ("action", "tier", "why", "ran", "failed", "line")},
                         {"action": "check", "tier": "reads", "why": "it only reads", "ran": True, "failed": False,
                          "line": None})
        self.assertIn("pages missing from the index", found["said"])  # listed, and no failure of the check
        self.assertEqual((self.on_disk(), self.errors()), (before, []))
        self.assertEqual(run_brain(self.root, "act", "feel").stdout.splitlines()[-1], "act: feel ran (it only reads)")
        # What the action found is the command's own verdict: a broken link fails the check, and so the action.
        self.write("cortex/concepts/broken.md", page("concept", "See [[nowhere]].\n", title="Broken", status="established",
                                                     summary="It points nowhere.", **DATES))
        r = run_brain(self.root, "act", "check")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.endswith("act: check ran (it only reads), and it failed\n"))

    def test_one_that_changes_the_brain_is_refused_until_the_owner_s_line_allows_it(self):
        before = self.on_disk()
        r = run_brain(self.root, "act", "index")
        why = (f"it changes the brain, and {PAGE} does not allow it: a line `- index (why)` under "
               "`## Allowed` there, written by the owner, lets it run with nobody there")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", f"brain act: index was not run: {why}\n"))
        self.assertEqual(self.on_disk(), before)  # refused: nothing changed, and no line in the brain's log
        self.assertRegex(self.errors()[-1], r"^\d{4}-\d\d-\d\d \d\d:\d\d act policy \| index: it changes the brain")
        self.policy("index (the listing is worked out from the pages)")
        dry = commands.call("act", ["index", "--dry-run"], root=self.root)
        self.assertEqual((dry["ran"], dry["why"], dry["line"]), (False, f"{PAGE} allows it", None))
        self.assertNotIn("spacing", self.on_disk()["hippocampus/index.md"])
        self.assertEqual(run_brain(self.root, "act", "index", "--dry-run").stdout,
                         f"act: index would run ({PAGE} allows it); nothing was run\n")
        ran = run_brain(self.root, "act", "index")
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("[[spacing]]", self.on_disk()["hippocampus/index.md"])
        line = vaultlib.read_events(self.root)[-1]
        self.assertEqual((line.op, line.what), ("act", "index"))
        self.assertTrue(line.rest.startswith("index -> index: 1 pages listed"), line.rest)
        self.assertRegex(ran.stdout.splitlines()[-1],
                         r"^act: index ran \(hippocampus/policy\.md allows it\); logged: \d{4}-\d\d-\d\d \d\d:\d\d act index -> ")
        self.policy()  # the leave taken back: refused again at the next asking
        self.assertEqual(run_brain(self.root, "act", "index").returncode, 1)

    def test_what_reaches_outside_or_cannot_be_undone_is_refused_whatever_the_page_says(self):
        self.policy("index", "fetch (forged)", "forget (forged)")
        for name, why in (("fetch", "it reaches outside the brain"), ("forget", "it cannot be undone"),
                          ("door", "it reaches outside the brain"), ("Index", "'Index' is not an action (closest: index)"),
                          ("index; rm -rf .", "'index; rm -rf .' is not an action")):
            with self.subTest(name):
                with self.assertRaises(commands.Refused) as refused:
                    commands.call("act", [name], root=self.root)
                self.assertTrue(str(refused.exception).startswith(f"brain act: {name} was not run: {why}"))
        self.assertEqual(len(self.errors()), 5)  # one line a refusal, as a wall leaves one
        # No argument of the caller's goes with an action: a reason, a flag or a target is not read.
        for extra in (["index", "--yes"], ["index", "because", "the", "owner", "said", "so"], ["fetch", "https://x.example"]):
            r = run_brain(self.root, "act", *extra)
            self.assertEqual((r.returncode, r.stdout), (2, ""), extra)

    def test_the_listing_says_what_each_is_and_whether_it_may_run_now(self):
        self.policy("snapshot (a line of numbers a day)")
        found = commands.call("act", [], root=self.root)
        self.assertEqual((found["policy"], found["allowed"], [a["action"] for a in found["actions"]]),
                         (PAGE, ["snapshot"], list(ACTIONS)))
        self.assertEqual({a["action"]: a["may"] for a in found["actions"] if a["tier"] == CHANGES},
                         {"index": False, "fingerprint": False, "snapshot": True, "graph": False})
        text = run_brain(self.root, "act").stdout.splitlines()
        self.assertEqual(text[0], "actions, and whether each may run with nobody there:")
        self.assertIn("  runs         check        reads    broken links, schema problems, index drift, edited inputs", text)
        self.assertIn("  not allowed  index        changes  rewrite the listing of hippocampus/index.md from the pages", text)
        self.assertIn("  allowed      snapshot     changes  append today's metrics to hippocampus/metrics.md, once a day", text)
        self.assertIn("  never        forget       final    remove an input and everything that rests on it", text)
        self.assertEqual(len(text), 1 + len(ACTIONS) + 2)

    def test_an_action_that_ran_is_logged_whatever_it_said(self):
        key = "AKIA" + "ABCDEFGHIJKLMNOP"  # what the log refuses to hold
        self.assertRegex(act.logged(self.root, "index", "index: 1 pages listed, [[spacing]] and [[no-such-page]]\nmore"),
                         r" act index -> index: 1 pages listed, spacing and no-such-page$")
        self.assertRegex(act.logged(self.root, "graph", f"wrote it with {key}"), r" act graph -> done$")
        self.assertRegex(act.logged(self.root, "snapshot", ""), r" act snapshot -> done$")
        self.assertEqual([e.what for e in vaultlib.read_events(self.root)], ["index", "graph", "snapshot"])


class Wall(Page):
    """The page is the owner's to write: a run that could write it could allow itself anything."""

    def call(self, tool, *flags, hook="protect_policy.py", **tool_input):
        return subprocess.run([sys.executable, os.path.join(HOOKS, hook), *flags], text=True, capture_output=True,
                              input=json.dumps({"tool_name": tool, "tool_input": tool_input}),
                              env=dict(os.environ, CLAUDE_PROJECT_DIR=self.root))

    def test_no_tool_writes_the_page(self):
        path = self.policy()
        for tool, args in (("Write", dict(file_path=path, content="## Allowed\n- index\n")),
                           ("Edit", dict(file_path=PAGE, old_string="x", new_string="- index")),
                           ("MultiEdit", dict(file_path=path, edits=[])), ("NotebookEdit", dict(notebook_path=path))):
            with self.subTest(tool):
                r = self.call(tool, **args)
                self.assertEqual(r.returncode, 2)
                self.assertIn("only the owner writes it, by hand. Show them the line to add under `## Allowed`", r.stderr)
        for other in ("hippocampus/tuning.md", "cortex/concepts/policy.md", "policy.md"):
            self.assertEqual(self.call("Write", file_path=os.path.join(self.root, other), content="x").returncode, 0, other)
        self.assertEqual(self.call("Write").returncode, 0)  # a call that names no file
        gate = self.call("Edit", "pre", hook="gate.py", file_path=path, old_string="## Allowed\n",
                         new_string="## Allowed\n- index\n")
        self.assertEqual(gate.returncode, 2)
        self.assertIn("only the owner writes it", gate.stderr)

    @unittest.skipUnless(sys.platform == "darwin", "case-insensitive file system")
    def test_another_case_of_its_name_is_the_same_page(self):
        self.policy()
        other = os.path.join(self.root, "Hippocampus", "Policy.md")
        self.assertEqual(self.call("Write", file_path=other, content="x").returncode, 2)

    def test_a_shell_command_that_would_change_it_is_refused_and_one_that_reads_it_is_not(self):
        self.policy()
        target = "hippocampus/" + "policy.md"
        for command in (f'echo "- index" >> {target}', f"printf x > ./{target}", f"sed -i '' 's/^$/- index/' {target}",
                        f"rm {target}", f"cp /tmp/mine.md {target}", f"mv {target} /tmp/",
                        "cd hippocampus && tee policy.md < /tmp/mine.md", f"true; echo '- graph' | tee -a {target}"):
            with self.subTest(command):
                self.assertEqual(self.call("Bash", command=command).returncode, 2)
        for command in (f"cat {target}", f"git diff {target}", "brain act", "brain check", "rm notes/my-policy.md",
                        "echo x > policy.md.bak", "ls hippocampus"):
            with self.subTest(command):
                self.assertEqual(self.call("Bash", command=command).returncode, 0)

    def test_a_wall_that_fails_still_keeps_the_page(self):
        sys.path.insert(0, HOOKS)
        import shared
        path = os.path.join(shared.ROOT, "hippocampus", "policy.md")
        self.assertTrue(shared.irreversible({"tool_name": "Write", "tool_input": {"file_path": path}}))
        self.assertTrue(shared.irreversible({"tool_name": "Bash", "tool_input": {"command": "echo x >> policy.md"}}))
        self.assertFalse(shared.irreversible({"tool_name": "Bash", "tool_input": {"command": "ls hippocampus"}}))
        self.assertFalse(shared.irreversible({"tool_name": "Write", "tool_input": {
            "file_path": os.path.join(shared.ROOT, "hippocampus", "tuning.md")}}))
