#!/usr/bin/env python3
"""UserPromptSubmit: put the pages a question is about in front of the model, or nothing.

Off unless BRAIN_PROMPT_RECALL=1 (set it under `env` in .claude/settings.json).
When on, a prompt that reads as a question and is well covered by a page gets
up to four lines, `path: summary`, at most 900 characters; anything else gets
nothing (Vault.prompt_recall holds the rule). It adds text to a prompt, it
never removes any, so every decision is one line in .cache/prompt-recall.log:
`TIME <chars added> <why> | <first words of the prompt>`. Read that log after a
week to judge whether it earns its place.

What it prints is a pointer, not an answer: the model still reads the pages
and still logs its recall line. Fails silent on any error: a prompt is never
blocked or delayed by this.
"""
import datetime
import json
import os
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
LOG = os.path.join(".cache", "prompt-recall.log")
SHOWN = 60  # characters of the prompt kept in the log


def record(root, added, why, prompt):
    path = os.path.join(root, LOG)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M} {added} {why} | {' '.join(prompt.split())[:SHOWN]}\n")


def main():
    if os.environ.get("BRAIN_PROMPT_RECALL") != "1":
        return
    prompt = json.load(sys.stdin).get("prompt") or ""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    from vaultlib import Vault, find_brain
    root = find_brain(ROOT)  # the brain may be above the folder the session started in
    if not root:
        return
    rows, why = Vault(root).prompt_recall(prompt)
    text = ""
    if rows:
        text = ("Pages here that may bear on this (summaries only; read a page before answering from it, "
                "and log the recall):\n" + "\n".join(line for _, line in rows))
        print(text)
    record(root, len(text), why, prompt)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001  never in the way of a prompt
        pass
    sys.exit(0)
