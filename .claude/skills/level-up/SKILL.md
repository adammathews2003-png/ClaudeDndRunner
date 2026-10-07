---
name: level-up
description: Level a PC up — at a story milestone (the GM announces it) or when XP crosses a threshold, or at session start when a level is pending. Works out what the level grants and asks only for the player's choices.
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*), Read
---

# Level-up flow

1. **Mark it** (milestone campaigns): `python engine/gm.py pc level-pending <pc>` at a story
   milestone. In xp campaigns `xp award` sets it itself. Narration may say "you feel
   ready to grow"; never quote XP unless a player asks (`xp show <pc>` is safe to paste).
2. **Plan:** `python engine/gm.py pc levelup <pc> --plan`.
   - GRANTED lines happen automatically (HP by the stored `hp-method` — never ask "max or
     roll?" again — proficiency, hit dice, slots, features).
   - CHOICE lines are what the player must answer: ASI (+2 to one score or +1 to two; a
     feat is recorded as custom), subclass at its level, new cantrips/spells, expertise,
     fighting style, other class choices.
3. **Ask** for the choices only, in one compact message with the options. If the PC's
   player is absent, use their autopilot line's spirit and keep it simple, or wait.
4. **Card + confirm:** say what changes ("Level 4 Kira: HP 30→38, DEX 18, …").
   "Looks good" → `python engine/gm.py pc levelup <pc> --choose asi="dex+2" spells="+guiding bolt" [--hp-roll N] --apply`
   - With `hp-method: roll` the tool rolls the hit die publicly (paste the roll line);
     `--hp-roll N` if the player rolled their own.
   - `--apply` refuses while a choice is unanswered and lists it: ask that, then retry.
5. **Magic items in the card.** After the level, `python engine/gm.py pc card <pc>` shows the
   written PC: live AC, saves and attacks with equipped (and attuned) magic items counted
   (`AC 15 (14 + items)`), `Magic items: … · attuned 2/3`, and the load under
   `encumbrance`. The file's `ac:` stays the base (armour and shield): never fold an item's
   `ac +1` into it or into `overrides`. A new magic item goes in with its tags (`srd item
   <name>` prints them: `item <pc> + "cloak of protection (uncommon, attune, ac +1, saves
   +1)"`), and attuning takes a short rest (`rest short --attune <pc>="<item>"`, three at
   most). Mention an unattuned or unequipped item if the player expects its bonus.
6. One level per flow; repeat while `level-pending` is still higher than the level.
   Multiclassing is custom: record it in Features and treat the PC as their primary class.
