"""Purpose: the owner's goals and the projects in prefrontal/, and what they keep in use.

Mixed into vaultlib.Vault; relies on its pages, edges, goals, tuning and resolve().
The reminders, which were here too, are vault_reminders.
"""
import datetime
import os

# What vaultlib hands on to the commands. The rest is for the parts, which import it from here.
__all__ = ["PurposeMixin"]


class PurposeMixin:
    def links_from(self, page):
        return self.out_links.get(page, frozenset())

    def active_projects(self):
        return [p for p in self.of_type("project") if p.fields.get("status", "active") != "done"]

    def goal_state(self, goal):
        """done | dropped | stale (past its date by more than goal_stale_days) | past-due | open."""
        if goal["ended"]:
            return goal["ended"]
        if goal["due"] and (self.today - goal["due"]).days > self.tuning.goal_stale_days:
            return "stale"
        if goal["due"] and goal["due"] < self.today:
            return "past-due"
        return "open"

    def live_goals(self):
        """Goals that still direct attention: open or only just past their date."""
        return [g for g in self.goals if self.goal_state(g) in ("open", "past-due")]

    def serving(self):
        """{page: [what it serves]}: each knowledge page a live goal or a live project depends on, and their names.

        A goal's links count, and so do the links of any project a goal names or
        that is still active. A goal is named by its words; a live project that no
        live goal names is `project <name>`. Done, dropped and stale goals let go
        of their pages.
        """
        reach, named = [], set()
        for goal in self.live_goals():
            for root in sorted({self.resolve(t) for t in goal["links"]} - {None}, key=lambda p: p.rel):
                reach.append((goal["text"], root))
                named.add(root)
        reach += [(f"project {p.stem}", p) for p in self.active_projects() if p not in named]
        served = {}
        for name, root in reach:
            for page in {root} | (self.links_from(root) if root.type == "project" else set()):
                if not page.is_system and name not in served.setdefault(page, []):
                    served[page].append(name)
        return served

    def purpose(self):
        """Knowledge pages the owner's live goals and live projects depend on (serving() says which).

        Attention goes here first; nothing here fades.
        """
        return set(self.serving())

    def activity(self, pages, days=None):
        """How much happened to these pages in the last `days` (the brain's activity_days): edits (by `updated:`)
        plus recalls naming them."""
        days = self.tuning.activity_days if days is None else days
        since = self.today - datetime.timedelta(days=days)
        edits = sum(1 for p in pages if p.updated and since < p.updated <= self.today)
        recalls = sum(1 for p in pages for d in self.recall_dates.get(p, []) if since < d <= self.today)
        return edits + recalls

    def goal_report(self):
        """Each goal with its date, the pages behind it, what is missing, and whether it is slipping.

        `at_risk`: open, due within goal_slip_days, and nothing behind it was
        edited or recalled in the last activity_days. A prediction from the log,
        not from the world: it says the brain shows no work toward the goal.
        """
        out = []
        for goal in self.goals:
            linked = [self.resolve(t) for t in goal["links"]]
            pages = set()
            for p in linked:
                if p is not None:
                    pages |= self.links_from(p) if p.type == "project" else {p}
            pages = sorted((p for p in pages if not p.is_system), key=lambda p: p.rel)
            state = self.goal_state(goal)
            days_left = (goal["due"] - self.today).days if goal["due"] else None
            recent = self.activity(pages + [p for p in linked if p is not None and p.type == "project"])
            out.append({"goal": goal["text"], "state": state,
                        "due": goal["due"].isoformat() if goal["due"] else None,
                        "days_left": days_left,
                        "projects": [p.stem for p in linked if p is not None and p.type == "project"],
                        "pages": [p.rel for p in pages],
                        "missing": [t for t, p in zip(goal["links"], linked) if p is None],
                        "activity": recent,
                        "at_risk": state == "open" and days_left is not None
                        and days_left <= self.tuning.goal_slip_days
                        and recent == 0})
        return out

    def project_report(self):
        """Each project with its goal, the pages it uses and the decisions that name it."""
        out = []
        for proj in self.of_type("project"):
            decisions = sorted((a for a in self.in_links[proj] if a.type == "decision"), key=lambda p: p.rel)
            feedback = os.path.join(os.path.dirname(proj.path), "feedback")
            out.append({"project": proj.stem, "status": proj.fields.get("status", "active"),
                        "goal": proj.fields.get("goal", ""), "due": proj.fields.get("due", ""),
                        "pages": sorted(p.rel for p in self.links_from(proj) if not p.is_system),
                        "decisions": [{"page": d.rel, "status": d.fields.get("status"),
                                       "outcome": d.fields.get("outcome")} for d in decisions],
                        "feedback": sorted(f for f in os.listdir(feedback) if not f.startswith("."))
                        if os.path.isdir(feedback) else []})
        return out

    def goal_link_problems(self):
        """(goal, target) for goal links that reach no page and are not listed under the index's Gaps."""
        known_gaps = set().union(*(p.gap_targets for p in self.pages))
        return [(g["text"], t) for g in self.goals for t in g["links"]
                if self.resolve(t) is None and t.lower() not in known_gaps]
