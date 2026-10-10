"""Purpose: the owner's goals and the projects in prefrontal/, and what they keep in use.

Mixed into vaultlib.Vault; relies on its pages, edges, goals, tuning and resolve().
"""
import datetime
import os

from vault_intentions import SPAN, clock, next_round, read_intentions

LAST_MINUTE = datetime.time(23, 59)  # a log line with no time of day: the end of its day


class PurposeMixin:
    def intentions(self):
        """Every reminder in hippocampus/intentions.md, as vault_intentions.read_intentions gives them.

        `due` is the day of a dated one, `every` the round of a repeat; otherwise `event` holds
        the event to watch for, which `brain fit` holds new input against, as it does `revisit_if`.
        """
        return [i for page in self.of_type("intentions") for i in read_intentions(page.body)]

    def _reminded(self):
        """{a reminder's words: the moment of the last `remind` log line naming it}: its adding, or the last time done.

        `brain log remind "<what>"` adds one and `brain log remind "done <what>"` closes one,
        in the words of the line, so the two are matched by those words, whatever their
        case and spacing. A line with no time of day stands for the end of its day.
        """
        if "_reminded_kept" not in self.__dict__:
            last = {}
            for e in self.events:
                if e.op == "remind" and e.day:
                    words = e.what.lower().split()
                    words = words[1:] if words[:1] in (["done"], ["dropped"]) else words
                    last[" ".join(words)] = datetime.datetime.combine(e.day, clock(e.time) if e.time else LAST_MINUTE)
            self._reminded_kept = last
        return self._reminded_kept

    def next_round(self, intention):
        """When an open repeat next comes round, counted from the last log line naming it; one never logged is due."""
        since = self._reminded().get(" ".join(intention["text"].lower().split()))
        if since is None:
            since = self.now - datetime.timedelta(days=SPAN.get(intention["every"], 7))
        return next_round(since, intention["every"], intention["time"])

    def due_intentions(self):
        """Open intentions whose time has come, the longest due first; `since` is when each came due."""
        out = []
        for i in self.intentions():
            since = i["at"] or (self.next_round(i) if i["every"] else None)
            if not i["ended"] and since and since <= self.now:
                out.append(dict(i, since=since))
        return sorted(out, key=lambda i: i["since"])

    def waiting_intentions(self):
        """Open intentions waiting on an event rather than a date."""
        return [i for i in self.intentions() if not i["ended"] and i["event"]]

    def repeating_intentions(self):
        """Open repeats, each with `next`: the round it is due for now, or the one to come."""
        return [dict(i, next=self.next_round(i)) for i in self.intentions() if not i["ended"] and i["every"]]

    def reminder_record(self):
        """How the reminders that are over ended: {done, dropped, late}.

        `late` is, for each one done whose closing mark gives its day and that had a date,
        the days between the two, least first (0 for one closed on its day or before it).
        A bare `(done)` is counted and has no lateness; a repeat is never closed by one.
        """
        over = [i for i in self.intentions() if i["ended"]]
        return {"done": sum(i["ended"] == "done" for i in over), "dropped": sum(i["ended"] == "dropped" for i in over),
                "late": sorted(max(0, (i["closed"] - i["due"]).days) for i in over
                               if i["ended"] == "done" and i["closed"] and i["due"])}


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
