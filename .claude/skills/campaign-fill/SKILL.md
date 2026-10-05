---
name: campaign-fill
description: Work through a campaign's fill-in queue with the driver (names, looks, a PC tie-in the generator left open); each answer becomes a promise the generator honours. The driver types /campaign-fill.
disable-model-invocation: true
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*), Read
---

# Fill-in queue

Campaign: $ARGUMENTS (default: the active campaign)

1. `python engine/gm.py [--campaign <slug>] campaign status --level fill-in` — shows the
   open questions with their defaults (and nothing secret).
2. Ask them in one compact, numbered message: question, the candidates, the default.
   "Keep the default" is a fine answer.
3. For each answer: `python engine/gm.py [--campaign <slug>] campaign fill F3 "<answer>"`
   (an empty answer takes the default).
4. Record what was asked: `python engine/gm.py [--campaign <slug>] campaign ledger add "fill-in answers F1–F7" --via campaign-fill`.
5. Tell the driver the answers are now promises: the next generated arc honours them.
   Applying a name to files already written is the next `/campaign-scenario` run's job,
   not this conversation's (it would mean reading secret files here).
