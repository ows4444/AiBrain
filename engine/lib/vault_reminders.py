"""Reminders: the lines of hippocampus/intentions.md as the brain stands toward them today.

Mixed into vaultlib.Vault; relies on its pages, events, tuning, root, today, now and kept().

What a line says is vault_intentions' to read, and it reads no file. Here each reminder is
held against the log and the clock: which are due, which repeat and when next, where one the
brain carries out itself stands, which wait for the owner's yes, and which are handed to
another program and have been reported on. The page is read once for a Vault, and so are the
steps the log holds: a command asks for them many times over.
"""
import datetime

from vault_events import moment
from vault_intentions import SPAN, STEP, handover, next_round, plan_said, read_course, read_intentions, words
from vault_policy import proposal, yes_of

# What vaultlib hands on to the commands. The rest is for the parts, which import it from here.
__all__ = ["RemindersMixin"]


class RemindersMixin:
    def intentions(self):
        """Every reminder in hippocampus/intentions.md, as vault_intentions.read_intentions gives them.

        `due` is the day of a dated one, `every` the round of a repeat; otherwise `event` holds
        the event to watch for, which `brain fit` holds new input against, as it does `revisit_if`.
        Read once for a Vault: the rows are for reading, and a caller that adds to one copies it first.
        The page says the same to a copy as_of makes, so the rows are shared with it.
        """
        return self.kept("intentions", lambda: [i for page in self.of_type("intentions")
                                                for i in read_intentions(page.body)])

    def _course(self):
        """{a reminder's words: the steps the log holds of it} (vault_intentions.read_course), read once.

        Kept as what the log taught, as the pair weights are: a copy as_of makes reads its own.
        """
        return self.kept("course", lambda: read_course(self.events), from_log=True)

    def _reminded(self):
        """{a reminder's words: the moment of the last `remind` log line naming it}: its adding, or the last time done.

        `brain log remind "<what>"` adds one and `brain log remind "done <what>"` closes one,
        in the words of the line, so the two are matched by those words, whatever their
        case and spacing. A line with no time of day stands for the end of its day.
        Read once, and kept as what the log taught: to a copy as_of makes, a reminder logged
        after its line was never logged.
        """
        def read():
            last = {}
            for e in self.events:
                step = STEP.match(e.what) if e.op == "act" else None
                if e.day and (e.op == "remind" or (step and step.group(1) == "finished")):
                    said = (step.group(2) if step else e.what).lower().split()
                    said = said[1:] if not step and said[:1] in (["done"], ["dropped"]) else said
                    last[" ".join(said)] = moment(e.day, e.time)
            return last
        return self.kept("reminded", read, from_log=True)

    def standing(self, intention):
        """Where a reminder the brain carries out itself stands: {state, part, attempt, attempts, ever, course,
        proposal}; None for one that only reminds.

        Read from the log alone (vault_intentions.read_course). `state` is scheduled (its
        time has not come), ready (it has, and nothing was done), or the last step said of
        it: started, finished, failed, waiting. A repeat that finished is over for that
        round and stands by what was said since; a dated one that finished is done.
        `part` is how many parts of its plan have passed, which is the one it is at.
        `attempt` names the last one started, `attempts` counts the starts of the part it is
        at, and `course` is the steps that count, each (day, time, step, attempt, note).
        `ever` counts every start the log holds of it, so an attempt's name is never used
        twice. `proposal` is the name it has while it waits, for the owner's yes
        (vault_policy.proposal).
        """
        if not intention.get("do"):
            return None
        course = self._course().get(words(intention["text"]), [])
        ever = sum(step[2] == "started" for step in course)
        ends = [n for n, step in enumerate(course) if step[2] == "finished"]
        if intention["every"] and ends:
            course = course[ends[-1] + 1:]  # an earlier round, done with
        due = (self.next_round(intention) if intention["every"] else intention["at"]) <= self.now
        state = course[-1][2] if course else "ready" if due else "scheduled"
        started = [step[3] for step in course if step[2] == "started"]
        passed = [n for n, step in enumerate(course) if step[2] == "passed"]
        here = course[passed[-1] + 1:] if passed else course  # what was said of the part it is at
        return {"state": state, "part": len(passed), "attempt": started[-1] if started else None,
                "attempts": sum(step[2] == "started" for step in here), "ever": ever, "course": course,
                "proposal": proposal(words(intention["text"]), plan_said(intention["steps"]), intention["when"], ever)}

    def proposals(self):
        """The reminders that wait and have no yes that holds: [{text, do, why, yes}], in the order they came due.

        `why` is what the last step said (the policy does not allow the action; it failed too
        often), `yes` the name the owner's line under `## Once` of the policy page gives it.
        """
        given = yes_of(self.root, self.today, self.tuning.yes_days)
        return [{"text": i["text"], "do": i["do"], "why": i["stands"]["course"][-1][4], "yes": i["stands"]["proposal"]}
                for i in self.due_intentions()
                if i["stands"] and i["stands"]["state"] == "waiting" and i["stands"]["proposal"] not in given]

    def next_round(self, intention):
        """When an open repeat next comes round, counted from the last log line naming it; one never logged is due."""
        since = self._reminded().get(words(intention["text"]))
        if since is None:
            since = self.now - datetime.timedelta(days=SPAN.get(intention["every"], 7))
        return next_round(since, intention["every"], intention["time"])

    def due_intentions(self):
        """Open intentions whose time has come, the longest due first; `since` is when each came due."""
        out = []
        back = {h["text"] for h in self.handed_over() if h["state"] == "returned"}  # reported on: it waits on no one
        for i in self.intentions():
            since = i["at"] or (self.next_round(i) if i["every"] else None)
            stands = self.standing(i) if since else None
            if (not i["ended"] and since and since <= self.now and not (stands and stands["state"] == "finished")
                    and i["text"] not in back):
                out.append(dict(i, since=since, stands=stands))
        return sorted(out, key=lambda i: i["since"])

    def handed_over(self):
        """Open reminders that are for another program: each with `name`, `state` and the `episode` that reports on it.

        `name` is what a report must say it is about (vault_intentions.handover). `state` is
        scheduled (its time has not come), handed (it has, and no report is here) or
        returned: an encoded input carries its name (`handed:` on the episode, which `brain
        new` takes from the note), and that episode is the evidence it is closed on. The
        brain does nothing about one but say it and read what comes back.
        """
        reports = {p.fields["handed"]: p for p in self.of_type("episode") if p.fields.get("handed") and not p.generated}
        out = []
        for i in self.intentions():
            if not i["ended"] and i["hand"]:
                name = handover(words(i["text"]), i["hand"], i["hand_until"], i["when"])
                report = reports.get(name)
                state = "returned" if report else "handed" if i["at"] <= self.now else "scheduled"
                out.append(dict(i, name=name, state=state, since=i["at"], episode=report.rel if report else None,
                                reported=report.came if report else None))
        return out

    def carried_out(self):
        """Open reminders the brain carries out itself, each with `stands`: where it is, from the log."""
        return [dict(i, stands=self.standing(i)) for i in self.intentions() if not i["ended"] and i["do"]]

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
