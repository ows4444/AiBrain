"""A schedule that needs no session: `brain schedule` sets the job, `brain tend --check --notify` is what it runs. Run: brain test"""
import datetime
import json
import os
import plistlib
import stat
import sys
import tempfile
from unittest import mock

from support import TODAY, TempBrain, ago, page, vaultlib

import commands  # noqa: E402  (support puts engine/lib on the path)
import schedule  # noqa: E402
import tend  # noqa: E402

# Stand-ins for the system's own tools: each writes what it was called with to $CALLS, one argument a line.
RECORD = '#!/bin/sh\nfor a in "$@"; do printf \'%s\\n\' "$a" >> "$CALLS"; done\n'
LAUNCHCTL = RECORD + 'if [ "$1" = bootstrap ] && [ -n "$FAIL" ]; then echo "Bootstrap failed: 5: Input/output error" >&2; exit 5; fi\n'


class Unattended(TempBrain):
    def setUp(self):
        super().setUp()
        self.beside = tempfile.TemporaryDirectory()
        self.addCleanup(self.beside.cleanup)
        self.home = os.path.realpath(self.beside.name)
        self.calls = os.path.join(self.home, "calls")
        self.env(HOME=self.home, CALLS=self.calls, PATH=self.tools(launchctl=LAUNCHCTL, osascript=RECORD))

    def env(self, **values):
        patch = mock.patch.dict(os.environ, values)
        patch.start()
        self.addCleanup(patch.stop)

    def tools(self, **scripts):
        """A folder holding these stand-ins and nothing else, to be the whole PATH."""
        folder = tempfile.mkdtemp(dir=self.home)
        for name, text in scripts.items():
            path = os.path.join(folder, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        return folder

    def called(self):
        """What the stand-ins were called with since the last look, one argument a line."""
        if not os.path.exists(self.calls):
            return []
        with open(self.calls, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        os.remove(self.calls)
        return lines

    def schedule(self, *args):
        return commands.call("schedule", list(args), root=self.root)

    def text(self, *args):
        module, parsed = commands.prepare("schedule", list(args), self.root)
        return module.render(module.run(self.root, parsed), parsed)


class TheJob(Unattended):
    """`brain schedule`: a launchd job of the owner's own, one for each brain, set and removed by one command."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(schedule, "on_mac", lambda: True)
        patch.start()
        self.addCleanup(patch.stop)
        self.label, self.plist = schedule.job(self.root)
        self.target = f"gui/{os.getuid()}"

    def test_it_is_set_set_again_and_removed(self):
        self.assertEqual(self.plist, os.path.join(self.home, "Library", "LaunchAgents", self.label + ".plist"))
        none = self.schedule()
        self.assertEqual((none["did"], none["set"], none["plist"], none["minutes"]), ("looked", False, None, None))
        self.assertEqual(self.text(), "schedule: none set for this brain. `brain schedule --set` has this machine look "
                                      "every 15 minutes and say what waits")
        self.assertEqual(self.called(), [])  # looking asks launchd nothing
        made = self.schedule("--set")
        self.assertEqual((made["did"], made["set"], made["plist"], made["minutes"], made["runs"]),
                         ("set", True, self.plist, 15, "brain tend --check --notify"))
        self.assertEqual(self.called(), ["bootout", f"{self.target}/{self.label}", "bootstrap", self.target, self.plist])
        with open(self.plist, "rb") as fh:
            job = plistlib.load(fh)
        self.assertEqual((job["Label"], job["ProgramArguments"], job["StartInterval"], job["RunAtLoad"]),
                         (self.label, [sys.executable, schedule.BRAIN, "tend", "--check", "--notify"], 900, True))
        self.assertEqual((job["EnvironmentVariables"], job["WorkingDirectory"]), ({"BRAIN_ROOT": self.root}, self.root))
        self.assertTrue(os.path.isfile(schedule.BRAIN))
        again = self.schedule("--set", "--minutes", "5")
        self.assertEqual((again["did"], again["minutes"], again["cron"]),
                         ("set again", 5, f"*/5 * * * * cd {self.root} && brain tend --check --notify"))
        self.assertEqual(self.text().splitlines()[:2], ["schedule: set. Every 5 minutes this machine runs `brain tend --check "
                                                        "--notify`", f"  {self.plist}"])
        self.assertTrue(self.text("--set").startswith("schedule: set again. Every 15 minutes "))
        self.called()
        gone = self.schedule("--remove")
        self.assertEqual((gone["did"], gone["set"], os.path.exists(self.plist)), ("removed", False, False))
        self.assertEqual(self.called(), ["bootout", f"{self.target}/{self.label}"])
        self.assertEqual(self.text("--remove"), "schedule: there was none to remove")
        self.schedule("--set")
        self.assertEqual(self.text("--remove"), "schedule: removed. Nothing looks at this brain between sessions now")

    def test_a_job_launchd_will_not_start_is_not_left_behind(self):
        self.env(FAIL="1")
        with self.assertRaises(commands.Refused) as refused:
            self.schedule("--set")
        self.assertEqual(str(refused.exception), "brain schedule: launchctl would not start the job, and nothing is left "
                                                 "installed: Bootstrap failed: 5: Input/output error")
        self.assertFalse(os.path.exists(self.plist))
        self.env(PATH=self.tools())  # no launchctl at all
        with self.assertRaises(commands.Refused) as refused:
            self.schedule("--set")
        self.assertIn("launchctl would not start the job", str(refused.exception))
        self.assertFalse(os.path.exists(self.plist))
        for wrong, why in ((("--set", "--remove"), "brain schedule: --set or --remove, not both"),
                           (("--set", "--minutes", "0"), "brain schedule: --minutes is from 1 to 1440 (a day)")):
            with self.assertRaises(commands.Refused) as refused:
                self.schedule(*wrong)
            self.assertEqual(str(refused.exception), why)

    def test_elsewhere_nothing_is_installed_and_the_cron_line_is_given(self):
        with mock.patch.object(schedule, "on_mac", lambda: False):
            found = self.schedule("--set", "--minutes", "30")
            self.assertEqual((found["did"], found["set"], found["cron"]),
                             ("looked", False, f"*/30 * * * * cd {self.root} && brain tend --check --notify"))
            self.assertEqual(self.text(), "schedule: this machine is not macOS, so nothing is installed here. The line that "
                                          f"does the same, for `crontab -e`:\n  */15 * * * * cd {self.root} && brain tend "
                                          "--check --notify")
            self.assertEqual(self.schedule("--remove")["did"], "looked")
        self.assertEqual((self.called(), os.path.exists(self.plist)), ([], False))


class WhatItRuns(Unattended):
    """`brain tend --check --notify`: what waits is put on the screen, each thing once a day."""

    def remind(self, *lines):
        self.write("hippocampus/intentions.md", page("intentions", "\n## Open\n\n" + "".join(f"- {line}\n" for line in lines)))

    def on(self, day):
        return tend.digest(vaultlib.Vault(self.root, today=day))

    def test_the_first_run_of_a_day_says_everything_and_a_later_one_only_a_reminder_come_due(self):
        tomorrow = TODAY + datetime.timedelta(days=1)
        self.assertEqual(tend.announcements(self.root, self.on(TODAY)), [])  # nothing waits: nothing to say
        self.remind(f"Renew the domain when {ago(1)}")
        self.write("inbox/note.md", "a quick note\n")
        self.assertEqual(tend.announcements(self.root, self.on(TODAY)), ["Reminder: Renew the domain"])  # come due since
        self.assertEqual(tend.announcements(self.root, self.on(TODAY)), [])                              # said today
        with open(os.path.join(self.root, tend.NOTIFIED), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"date": TODAY.isoformat(), "shown": ["Renew the domain"]})
        self.remind(f"Renew the domain when {ago(1)}", f"Call DevOps when {ago(0)} 10:00")
        self.assertEqual(tend.announcements(self.root, self.on(TODAY)), ["Reminder: Call DevOps"])
        # A new day: everything that waits in one line, what is felt most first (a reminder two days due is a worry).
        self.assertEqual(tend.announcements(self.root, self.on(tomorrow)), ["reminders due 2, in the inbox 1"])
        self.write(tend.NOTIFIED, "not json")  # lost or spoiled: the day's line is said once more
        self.assertEqual(tend.announcements(self.root, self.on(tomorrow)), ["reminders due 2, in the inbox 1"])

    def test_the_line_is_shown_by_what_this_machine_has(self):
        self.remind('Say "hi" \\ now when 2026-01-01')
        found = commands.call("tend", ["--check", "--notify"], root=self.root)
        self.assertEqual(found["notified"], ["reminders due 1"])
        self.assertEqual(self.called(), ["-e", 'display notification "reminders due 1" with title "brain"'])
        self.assertEqual(commands.call("tend", ["--check", "--notify"], root=self.root)["notified"], [])  # said today
        self.assertEqual((commands.call("tend", ["--check"], root=self.root)["notified"], self.called()), ([], []))
        self.assertTrue(tend.show('Reminder: Say "hi" \\ now'))
        self.assertEqual(self.called(), ["-e", 'display notification "Reminder: Say \\"hi\\" \\\\ now" with title "brain"'])
        self.env(PATH=self.tools(**{"notify-send": RECORD}))
        self.assertTrue(tend.show("Reminder: Call DevOps"))
        self.assertEqual(self.called(), ["brain", "Reminder: Call DevOps"])
        self.env(PATH=self.tools())  # neither: nothing can be shown, and nothing is claimed
        self.assertFalse(tend.show("Reminder: Call DevOps"))
        self.assertEqual(schedule.on_mac(), sys.platform == "darwin")  # which of the two this machine is
        os.remove(os.path.join(self.root, tend.NOTIFIED))
        self.assertEqual(commands.call("tend", ["--check", "--notify"], root=self.root)["notified"], [])
