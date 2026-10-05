"""Purpose: projects as pages, owner goals, and the frozen expectation of a decision. Run: brain test"""
import json
import os
import subprocess
import sys
import unittest

from support import DECIDED, ENGINE, SCRIPTS, TempBrain, VALID, ago, page, project


class Purpose(TempBrain):
    """Working memory and goals: projects are pages, goals mark what is in use."""

    def owner(self, *goals):
        self.write("CLAUDE.md", "# Brain\n\n## Owner\n\nA writer.\n\n### Goals\n\n" + "\n".join(goals)
                   + "\n\n## Tags\n\n`disputed`\n")

    def check(self):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "link_check.py"), self.root, "--json"],
                           capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)

    def test_project_is_a_page_named_after_its_folder(self):
        self.write("prefrontal/launch/CLAUDE.md", project("Depends on [[pricing]] and [[nowhere]]."))
        self.write("cortex/concepts/pricing.md", page("concept", **VALID))
        self.write("cortex/decisions/raise.md", page("decision", "For [[launch]].", status="open", **DECIDED))
        v = self.brain()
        launch = v.resolve("launch")
        self.assertEqual((launch.type, launch.stem, launch.is_system), ("project", "launch", True))
        self.assertNotIn(launch, v.knowledge)  # not long-term memory: no graph metrics
        code, report = self.check()
        self.assertEqual((code, report["broken"]), (1, [{"page": "prefrontal/launch/CLAUDE.md", "target": "nowhere"}]))
        self.assertEqual(v.project_report()[0]["decisions"],
                         [{"page": "cortex/decisions/raise.md", "status": "open", "outcome": None}])

    def test_template_project_passes_check(self):
        import shutil
        shutil.copytree(os.path.join(ENGINE, "templates", "project"), os.path.join(self.root, "prefrontal", "x"))
        self.assertEqual(self.check()[0], 0)
        self.assertEqual(self.brain().resolve("x").type, "project")

    def test_live_project_and_goals_keep_pages_from_fading(self):
        old = ago(400)
        for name in ("used", "goal-page", "released", "faded"):
            self.write(f"cortex/concepts/{name}.md", page("concept", updated=old))
        self.write("prefrontal/live/CLAUDE.md", project("[[used]]"))
        self.write("prefrontal/old/CLAUDE.md", project("[[released]]", status="done"))
        self.owner("- Learn pricing by 2027-01-01 -> [[goal-page]]")
        v = self.brain()
        self.assertEqual({p.stem for p in v.purpose()}, {"used", "goal-page"})
        self.assertEqual(sorted(p.stem for p in v.dormant_candidates()), ["faded", "released"])

    def test_goals_parse_and_report(self):
        self.write("cortex/concepts/pricing.md", page("concept", **VALID))
        self.write("cortex/concepts/via-project.md", page("concept", **VALID))
        self.write("prefrontal/launch/CLAUDE.md", project("[[via-project]]"))
        self.owner("- Ship the course by 2027-01-01 -> [[launch]], [[pricing]]",
                   "- Read more", "* Learn Go by 2026-12-01 -> [[golang]]", "not a goal line")
        goals = {g["goal"]: g for g in self.brain().goal_report()}
        self.assertEqual(set(goals), {"Ship the course", "Read more", "Learn Go"})
        ship = goals["Ship the course"]
        self.assertEqual((ship["due"], ship["days_left"], ship["projects"]), ("2027-01-01", 90, ["launch"]))
        self.assertEqual(ship["pages"], ["cortex/concepts/pricing.md", "cortex/concepts/via-project.md"])
        self.assertEqual((goals["Read more"]["due"], goals["Read more"]["pages"]), (None, []))
        self.assertEqual(goals["Learn Go"]["missing"], ["golang"])

    def test_goals_outside_owner_are_ignored(self):
        self.write("CLAUDE.md", "# Brain\n\n## Owner\n\nx\n\n## Notes\n\n### Goals\n\n- not mine\n")
        self.assertEqual(self.brain().goals, [])

    def test_rehearsal_includes_insights_and_puts_goals_first(self):
        self.write("cortex/concepts/very-overdue.md", page("concept", updated=ago(50)))
        self.write("cortex/concepts/for-goal.md", page("concept", updated=ago(5)))
        self.write("cortex/insights/pattern.md", page("insight", updated=ago(20)))
        self.owner("- Win -> [[for-goal]]")
        self.assertEqual([p.stem for p in self.brain().due_for_rehearsal()], ["for-goal", "very-overdue", "pattern"])

    def test_introspect_goals_and_projects(self):
        self.write("prefrontal/launch/CLAUDE.md", project())
        self.owner("- Ship -> [[launch]]")
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "introspect.py"), self.root, "--goals",
                              "--projects"], capture_output=True, text=True, check=True).stdout
        self.assertIn("1 goals (1 with no pages)", out)
        self.assertIn("launch (active): 0 pages, 0 decisions, 0 feedback", out)


class ProtectExpected(TempBrain):
    BODY = "## Expected\nFew customers leave.\n\n## Outcome\n\n## Lessons\n"

    def decision(self, status, body=None):
        extra = dict(review="2026-12-01") if status != "open" else {}
        return self.write("cortex/decisions/raise.md", page("decision", self.BODY if body is None else body,
                                                            status=status, **dict(DECIDED, **extra)))

    def guard(self, tool, **args):
        return self.run_hook("protect_expected.py", {"tool_name": tool, "tool_input": args}).returncode

    def test_decided_expectation_is_frozen(self):
        path = self.decision("decided")
        self.assertEqual(self.guard("Edit", file_path=path, old_string="Few customers", new_string="Many customers"), 2)
        self.assertEqual(self.guard("MultiEdit", file_path="cortex/decisions/raise.md",
                                  edits=[{"old_string": "leave.", "new_string": "leave, maybe."}]), 2)
        self.assertEqual(self.guard("Write", file_path=path, content=page("decision", "## Expected\nAll good.\n")), 2)

    def test_quoted_status_is_still_frozen(self):
        path = self.decision('"decided"')
        self.assertEqual(self.guard("Edit", file_path=path, old_string="Few customers", new_string="Many customers"), 2)

    def test_status_in_the_body_freezes_nothing(self):
        path = self.decision("open", body="status: decided\n\n" + self.BODY)
        self.assertEqual(self.guard("Edit", file_path=path, old_string="Few customers", new_string="Many customers"), 0)

    def test_other_sections_and_whitespace_may_change(self):
        path = self.decision("reviewed")
        self.assertEqual(self.guard("Edit", file_path=path, old_string="## Outcome\n", new_string="## Outcome\nThey stayed.\n"), 0)
        self.assertEqual(self.guard("Edit", file_path=path, old_string="Few customers leave.",
                                  new_string="Few customers\nleave."), 0)

    def test_open_or_empty_expectation_may_be_written(self):
        path = self.decision("open")
        self.assertEqual(self.guard("Edit", file_path=path, old_string="Few", new_string="No"), 0)
        path = self.decision("decided", body="## Expected\n\n## Outcome\n")
        self.assertEqual(self.guard("Edit", file_path=path, old_string="## Expected\n", new_string="## Expected\nGrowth.\n"), 0)

    def test_a_decided_page_is_never_reopened(self):
        for status in ("decided", "reviewed"):
            path = self.decision(status)
            self.assertEqual(self.guard("Edit", file_path=path, old_string=f"status: {status}",
                                        new_string="status: open"), 2, status)
        path = self.decision("decided")
        self.assertEqual(self.guard("Edit", file_path=path, old_string="status: decided",
                                    new_string="status: reviewed\noutcome: better"), 0)

    def test_other_pages_are_ignored(self):
        path = self.write("cortex/concepts/a.md", page("concept", "## Expected\nx\n", status="decided"))
        self.assertEqual(self.guard("Edit", file_path=path, old_string="x", new_string="y"), 0)


if __name__ == "__main__":
    unittest.main()
