"""The Stop sensor reads a session's transcript by its shape, which nobody documents: a transcript of that shape is
kept here and the sensor is run on it, so a change of shape fails a test before the hook falls silent. Run: brain test

fixtures/session.jsonl has the keys and the nesting of transcripts Claude Code 2.1.296 wrote in October 2026. One
real entry of each kind was the mould: every key was kept, every value replaced (ids and times renumbered, all
text and every path made up), so nothing in it is anyone's. To the hook the session is eight turns:

    1  a question answered from a page that was read                   a recall, no line
    2  `brain recall` in the shell, then `brain log recall` refused    a recall, no line (the call failed)
    3  the MCP recall tool, then `brain log recall`                    a recall, logged
    4  the question handed to the researcher agent, in the background  no recall yet
    5  what the agent found, come back as a task notification          a recall, no line
    6  `/model`, a command of Claude Code's own                        no recall
    7  what that command printed                                       no recall
    8  a skill that reads pages, called by the model, and a page read  a recall, no line

Turns 4 and 5 are how every call of an agent went in the transcripts at hand: it was started in the background
(the call's result says `async_launched`), and what it found came back later as a task notification: a user entry
not marked `isMeta`, so for the hook it starts a turn of its own. It names the call that started the agent, and the
line is owed by that turn, where the answer is: the turn that made the call has nothing to answer from yet.

When Claude Code changes the shape, take new moulds from a new transcript: these tests then say what the hook
no longer finds. A skill typed as a slash command (`/aibrain:ask`) was in no transcript at hand, so the
`<command-name>` entry is a built-in command's, and the notification carries a subset of the tags seen.
"""
import json
import os
import sys
import unittest

from support import HOOKS, TempBrain

sys.path.insert(0, HOOKS)
import check_recall  # noqa: E402

SESSION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "session.jsonl")
PROMPTS = ["what do my notes say about steeping time?", "and what about water temperature?",
           "which teas do I have notes on?", "ask the researcher what my notes say about oolong", "<task-notification>",
           "<command-name>/model</command-name>", "<local-command-stdout>Kept the model as it was</local-command-stdout>",
           "brief me on green tea"]


def entries(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def turns(transcript):
    """The entries cut where the hook finds a turn's start; what comes before the first start goes with it."""
    out = [[]]
    for entry in transcript:
        if check_recall.is_prompt(entry) and out[-1]:
            out.append([])
        out[-1].append(entry)
    return out


def blocks_of(transcript, kind):
    return [b for entry in transcript for b in check_recall.blocks(entry) if b.get("type") == kind]


class TheShapeTheSensorReads(unittest.TestCase):
    def test_the_fixture_holds_every_key_the_hook_reads(self):
        session = entries(SESSION)
        for entry in session:
            self.assertIn(entry["type"], ("user", "assistant", "system", "attachment"))
            if entry["type"] in ("user", "assistant"):  # what a turn is made of: `message.content`, text or blocks
                content = entry["message"]["content"]
                self.assertTrue(isinstance(content, str) or all(isinstance(b, dict) and b["type"] for b in content))
                self.assertTrue(check_recall.blocks(entry), entry)
            else:
                self.assertEqual(check_recall.blocks(entry), [])  # the rest is passed over, not tripped on
        calls = blocks_of(session, "tool_use")
        for call in calls:  # a call: its id, its name, and its arguments as a table
            self.assertEqual([type(call[key]) for key in ("id", "name", "input")], [str, str, dict])
        self.assertEqual([c["name"] for c in calls],
                         ["Read", "Bash", "Bash", "mcp__plugin_aibrain_brain__recall", "Bash", "Agent", "Skill", "Read"])
        named = {c["name"]: c["input"] for c in calls}
        self.assertEqual((sorted(named["Read"]), sorted(named["Bash"]), sorted(named["Skill"]), sorted(named["Agent"])),
                         (["file_path"], ["command", "description"], ["skill"], ["description", "prompt", "subagent_type"]))
        self.assertEqual(named["Agent"]["subagent_type"], "aibrain:researcher")  # a plugin's agent carries its prefix
        results = blocks_of(session, "tool_result")
        self.assertEqual([r["tool_use_id"] for r in results], [c["id"] for c in calls])  # each answers one call
        # A result says it failed with `is_error`; a Read's, an agent's and a Skill's carry no such key at all.
        self.assertEqual([r.get("is_error") for r in results], [None, False, True, None, False, None, None, None])
        # What the owner typed is text, and so is a command or a notification; none is marked `isMeta`, which a
        # skill's own text is.
        self.assertEqual([e["message"]["content"].splitlines()[0] for e in session if check_recall.is_prompt(e)], PROMPTS)
        meta = [e for e in session if e["type"] == "user" and e.get("isMeta")]
        self.assertEqual([type(e["message"]["content"]) for e in meta], [str, list])  # a command's caveat; a skill's text
        self.assertEqual(meta[1]["message"]["content"][0]["type"], "text")
        self.assertEqual(check_recall.ANY_COMMAND.findall("".join(b.get("text", "") for b in blocks_of(session, "text"))),
                         ["model"])

    def test_each_turn_of_the_session_is_judged_for_what_it_was(self):
        session = turns(entries(SESSION))
        self.assertEqual([len(turn) for turn in session], [7, 6, 6, 4, 3, 1, 1, 8])
        handed = check_recall.handed_over(entries(SESSION))  # the one call that asked the researcher
        self.assertEqual(len(handed), 1)
        self.assertEqual([check_recall.check(turn, handed) for turn in session],
                         [(True, False), (True, False), (True, True), (False, False), (True, False), (False, False),
                          (False, False), (True, False)])
        # The agent was only started in turn 4: its result says so, and the notification of turn 5 names that call.
        started, back, logged = session[3], session[4], session[2][3:5]  # the `brain log recall` of turn 3, its result
        call = blocks_of(started, "tool_use")[0]
        self.assertEqual((call["name"], {call["id"]}), ("Agent", handed))
        self.assertTrue(any(e.get("toolUseResult", {}).get("isAsync") for e in started))
        self.assertEqual(check_recall.NOTIFICATION.match(back[0]["message"]["content"]).group(1), call["id"])
        # The turn the answer came back in owes the line, and writing it there settles it; unnamed, it owes none.
        self.assertEqual(check_recall.check(back + logged, handed), (True, True))
        self.assertEqual(check_recall.check(back), (False, False))

    def test_the_turn_that_is_ending_is_found_from_the_end_of_the_file(self):
        turn = check_recall.turn_of(*check_recall.read_entries(SESSION))
        self.assertEqual(turn, turns(entries(SESSION))[-1])
        self.assertEqual(turn[0]["message"]["content"], PROMPTS[-1])
        self.assertEqual([e.get("isMeta") for e in turn], [None, None, None, True, None, None, None, None])


class TheHookOnIt(TempBrain):
    def test_it_asks_at_the_stop_of_the_session_it_was_taken_from(self):
        r = self.run_hook("check_recall.py", {"hook_event_name": "Stop", "transcript_path": SESSION,
                                              "stop_hook_active": False})
        self.assertEqual(r.returncode, 2)
        self.assertIn("logged no recall line", r.stderr)
        with open(os.path.join(self.root, ".cache", "errors.log"), encoding="utf-8") as fh:
            self.assertNotIn("check_recall error", fh.read())  # it read the file, and tripped on nothing in it


if __name__ == "__main__":
    unittest.main()
