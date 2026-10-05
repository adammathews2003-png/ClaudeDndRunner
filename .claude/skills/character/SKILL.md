---
name: character
description: Character intake — a new PC from free text or a pasted sheet, or changes to an existing PC (purchases, gear swaps, HP method, anything between sessions). Only the player (or the /gm session-start routine) invokes it.
disable-model-invocation: true
allowed-tools: Bash(python tools/gm.py:*), PowerShell(python tools/gm.py:*), Read
---

# Character intake loop

The player's words: $ARGUMENTS

Input can be at any level of detail: "half-orc barbarian 3, berserker, greataxe and
javelins", a pasted sheet, or a mix across several messages. **Player-stated values
win**; you never invent a value they didn't give; the tools compute everything else.

## New PC
1. **Extract** what was said into a draft (slug = their name or a working name):
   `python tools/gm.py pc draft <slug> --set name="…" race="…" class=… level=N subclass=… background=… "base-scores=str 15 dex 14 …" skills="athletics, perception" hp-method=max --equip "greataxe; 4 javelins; explorer's pack"`
   - `scores=` if they gave final scores, `base-scores=` if before racial bonuses.
   - A pasted sheet: save nothing yourself; pass the obvious fields with `--set`, or if it
     was saved under `.gm/drafts/`, `--from-sheet <file>`.
   - Non-SRD content (a book subclass, race or feat): accept it, ask the player to
     summarize what it does at this level, and record it as `custom-features="…"`.
2. **Check:** the draft command prints `[PC CHECK]`; `pc check <slug>` reprints it.
   - **MISSING** → ask for exactly these, in one compact numbered message, with the
     options the tool lists (standard array / point buy / 4d6 drop lowest for scores —
     rolled scores go through `roll 4d6kh3`, publicly).
   - **DEFAULTS** → show them as "I'll use X — OK?". A default never becomes final silently.
   - **CONFLICTS / warnings** → ask once ("you wrote AC 17; chain mail + shield is 18 —
     which?"). If the player insists, keep their value: `--set "overrides=ac:17"`.
   - `hp-method` is asked **once** (max or roll): it applies to every level after 1st,
     including levels they start above 1st (with `roll`, the tool rolls publicly).
3. Loop 1–2 with each answer until nothing required is missing.
4. **Confirm:** `python tools/gm.py pc card <slug>` → show the card to the player.
   "Looks good" → `python tools/gm.py pc write <slug>`. Corrections → back to step 1.
5. Optional, asked once and skippable: a look, personality, **a goal or bond**, and the
   autopilot line (propose one). Backstory places go on the world map:
   `world add "<place>" --near <id> [--within 3d] --source player:<pc> --note "…"`
   (the player's words are the constraints). Hooks you see in a backstory are woven in
   privately — never say so at the table.

## Changes to an existing PC
`python tools/gm.py pc edit <pc> --set … --item +"longbow" --item -"shortbow"` (same
checks; overrides survive). Purchases also move coin: `coin Kira -50gp`. Switching HP
method: `pc edit <pc> --set hp-method=roll` (future levels only).
