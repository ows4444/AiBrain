"""Purpose: the owner's goals and the projects in prefrontal/, and what they keep in use.

Mixed into vaultlib.Vault; relies on its pages, edges, goals and resolve().
"""
import datetime
import os
import re

from vault_model import ACTIVITY_DAYS, GOAL_END, GOAL_SLIP_DAYS, GOAL_STALE_DAYS, parse_date

# An intention in hippocampus/intentions.md: `- <what to do> when <YYYY-MM-DD or an event>`,
# closed by `(done)` or `(dropped)` at the end of the line, as goals are.
INTENTION = re.compile(r"^[-*]\s+(.+?)\s+when\s+(.+?)\s*$")


class PurposeMixin:
    def intentions(self):
        """[{text, when, due, event, ended}] from hippocampus/intentions.md.

        `due` is set when `when` is a date; otherwise `event` holds the event to
        watch for, which /ingest checks new input against, as it does `revisit_if`.
        """
        out = []
        for page in self.of_type("intentions"):
            for line in page.body.splitlines():
                end = GOAL_END.search(line)
                m = INTENTION.match(GOAL_END.sub("", line).strip())
                if m:
                    due = parse_date(m.group(2))
                    out.append({"text": m.group(1), "when": m.group(2), "due": due,
                                "event": None if due else m.group(2), "ended": end.group(1).lower() if end else None})
        return out

    def due_intentions(self):
        """Open intentions whose date has come, oldest first."""
        return sorted((i for i in self.intentions() if not i["ended"] and i["due"] and i["due"] <= self.today),
                      key=lambda i: i["due"])

    def waiting_intentions(self):
        """Open intentions waiting on an event rather than a date."""
        return [i for i in self.intentions() if not i["ended"] and i["event"]]


    def links_from(self, page):
        return self.out_links.get(page, frozenset())

    def active_projects(self):
        return [p for p in self.of_type("project") if p.fields.get("status", "active") != "done"]

    def goal_state(self, goal):
        """done | dropped | stale (past its date by more than GOAL_STALE_DAYS) | past-due | open."""
        if goal["ended"]:
            return goal["ended"]
        if goal["due"] and (self.today - goal["due"]).days > GOAL_STALE_DAYS:
            return "stale"
        if goal["due"] and goal["due"] < self.today:
            return "past-due"
        return "open"

    def live_goals(self):
        """Goals that still direct attention: open or only just past their date."""
        return [g for g in self.goals if self.goal_state(g) in ("open", "past-due")]

    def purpose(self):
        """Knowledge pages the owner's live goals and live projects depend on.

        A goal's links count, and so do the links of any project a goal names or
        that is still active. Attention goes here first; nothing here fades.
        Done, dropped and stale goals let go of their pages.
        """
        roots = set(self.active_projects())
        for goal in self.live_goals():
            roots |= {self.resolve(t) for t in goal["links"]} - {None}
        pages = set()
        for r in roots:
            pages |= {r} | (self.links_from(r) if r.type == "project" else set())
        return {p for p in pages if not p.is_system}

    def activity(self, pages, days=ACTIVITY_DAYS):
        """How much happened to these pages in the last `days`: edits (by `updated:`) plus recalls naming them."""
        since = self.today - datetime.timedelta(days=days)
        edits = sum(1 for p in pages if p.updated and since < p.updated <= self.today)
        recalls = sum(1 for p in pages for d in self.recall_dates.get(p, []) if since < d <= self.today)
        return edits + recalls

    def goal_report(self):
        """Each goal with its date, the pages behind it, what is missing, and whether it is slipping.

        `at_risk`: open, due within GOAL_SLIP_DAYS, and nothing behind it was
        edited or recalled in the last ACTIVITY_DAYS. A prediction from the log,
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
                        "at_risk": state == "open" and days_left is not None and days_left <= GOAL_SLIP_DAYS
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
