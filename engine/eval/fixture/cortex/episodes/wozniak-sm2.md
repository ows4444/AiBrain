---
title: The SM-2 algorithm
summary: "Wozniak's description of SM-2: each card's interval grows after a successful review by its ease factor, and resets on a miss."
type: episode
created: 2026-06-09
updated: 2026-06-10
url: https://example.org/supermemo-sm2-algorithm
author: Piotr Wozniak
published: 1990
consolidated: 2026-06-10
aliases: []
answers:
  - How does a flashcard program decide when to show me a card again?
  - What happens to a flashcard's schedule when I get it wrong?
  - How long are the first two waits before a new flashcard comes back?
  - What scale are answers marked on when reviewing flashcards?
  - What makes a flashcard come back sooner if I find it hard?
tags: []
---

# The SM-2 algorithm

## What it is

A description of the scheduling rule in [[supermemo]], written by its author.

## Claims

- This source says each card gets an interval that grows after every
  successful review, multiplied by the card's ease factor, which starts at
  2.5 and drops when answers are graded hard (applies:: [[spacing-effect]]).
- It says answers are graded from 0 to 5, and a grade below 3 resets the
  card to an interval of one day.
- It says the first two intervals are fixed at one and six days.
- It mentions that [[anki]] adopted a variant of the rule.

## Candidates

- Ease factor - a per-card multiplier for the next review interval
