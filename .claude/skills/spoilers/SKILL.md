---
name: spoilers
description: Answer a player's question about the secrets behind the screen or a "what if" alternative, between spoiler banners, and record it. Players type /spoilers; it is the only exception to the behind-the-screen rules.
disable-model-invocation: true
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*), Read
---

# Spoilers

The question: $ARGUMENTS

Honor-based: typing the command is the decision. Answer right away.

## 1. Classify
- **Depth** (if the player gave one): `hint` (a nudge) · `answer` (default: just what was
  asked) · `full` (everything connected, up to the whole truth).
- **Level:** `none` (a what-if answerable from what the party already knows) · `minor`
  (a resolved thread or background detail) · `major` (touches an unresolved thread the
  campaign is built around).

## 2. Gather (you may read anything now)
Scenario `## The truth` and beats; NPC files (secrets, Movements); the session log
including `(GM)` lines and `sessions/history/`; clocks and state;
`python engine/gm.py trace <name|place> [--from "Day 1 18:00"]` for where someone was;
`python engine/gm.py odds atk|save|check|contest …` for exact chances;
`python engine/gm.py spoil list` for what's already been revealed.

## 3. Answer between the markers (the client draws them as a banner)
```
<<SPOILERS major/answer>>
…the answer…
<<END SPOILERS>>
```
- Label every claim: **Established** (in the files or logs: "Veskar left for the mill at
  midnight — that's logged"), **Likely** (follows from motives, schedules or clocks
  without dice), **Guess** (depends on rolls or choices nobody made; cite `odds`).
- Keep to the question at the requested depth. If related secrets were left out, the
  last line says so ("There's more connected to this — ask with `full`").
- **Honest, not flattering:** a what-if may show the party chose badly, or that it
  wouldn't have mattered.
- **Undecided stays undecided.** If it was never authored: "Not decided yet. Here's what
  I'd lean toward, but it isn't canon." Never write a guess into any file.
- What-ifs never change state; a what-if becomes canon only through `/overrule`.
  Secrets never change because they were revealed.

## 4. Record it, right after the answer
`python engine/gm.py spoil log "<the question>" --level <none|minor|major> --depth <hint|answer|full> --reveals "<one line of what was revealed>" [--what-if]`

## 5. Resume play under the normal rules
Characters don't learn what players learned; NPCs react to what the characters did. From
now on, facts in the spoiler record may be discussed out of character without a new
`/spoilers`. Never offer or suggest spoilers, ever.
