---
name: overrule
description: The table's authority to change the game — retcon something that happened, or add a temporary or permanent table rule. Players type /overrule; the GM applies it immediately.
disable-model-invocation: true
allowed-tools: Bash(python tools/gm.py:*), PowerShell(python tools/gm.py:*), Read
---

# Overrule

The request: $ARGUMENTS

Honor-based: typing the command *is* the decision. No consent step, no "are you sure",
no record of who agreed. Apply it **now**, accurately, and keep everything else behind
the screen.

## Decide the kind
- **Retcon** (adjust what happened): "Kira wasn't spotted", "undo that round", "re-roll
  that, the die fell off the table", "Mara wouldn't know our names".
- **Table rule** (a rule change for a while): "crits on 19–20 this fight", "potions are
  a bonus action from now on". Scope: `scene` · `combat` · `session` · `campaign` ·
  `until <condition>`.
- **Undo the last overrule** (`/overrule undo`): `python tools/gm.py overrule-undo`.
- **"Tell us who took Harl"** is a request to reveal, not a change: say only that
  overrule can't reveal things (don't recommend anything else).
- **Genuinely ambiguous** ("undo that" — which of two turns?) → ask *which one*: a
  clarifying question, never a permission check.

## Apply
- *Retcon of the last turn:* `python tools/gm.py undo`, then re-resolve correctly if
  needed (a re-roll goes through the tools as normal).
- *Older retcon:* corrective changes going forward, in one batch:
  `python tools/gm.py do "retcon \"Kira's climb went unseen\" --turn 14; cond Kira -prone; hp Kira +6; …"`
  Hidden consequences are fixed with GM-only changes (e.g. `move-npc`, `attitude`) in the
  same batch; never described.
- *A past session:* the same, with `retcon "<what>" --session NN --turn N`: the tool
  appends an Erratum line to that session's history file; its original text is never
  edited.
- *Table rule:* `python tools/gm.py rule add "<the rule>" --scope <scope> [--key crit-range=19]`.
  Keys the tools apply themselves: `crit-range=19|18`, `crit-damage=double|max+roll`,
  `ties=pc|raw`, `flanking=off|adv|+2`, `death-saves=on|off|dc N`, `potion=action|bonus`,
  `dice-mode=players-roll-d20s|gm-rolls-all`, `encounters=on|off`. Any other rule is free
  text you honor. End an `until` rule when its condition is met:
  `python tools/gm.py rule end R4 --reason "we reached Thornbury"` (announce it in one line).
- **If a declared fact contradicts something hidden, the overrule wins**: make it true,
  adjust the hidden side as plausibly as possible behind the screen, and don't say what
  changed.

## Show the applied card, then resume
```
OVERRULE applied — retcon (turn 14)
Kira's climb went unseen: she's on the roof, not prone, at 30/30 HP.
…and whatever followed from it behind the screen is adjusted.
```
(For a rule: `OVERRULE applied — table rule R3 · crits on 19–20 · this combat`.)
List only *visible* consequences. Then pick the fiction up from the corrected state.
Never comment on how often the table overrules, and never suggest an overrule yourself.
