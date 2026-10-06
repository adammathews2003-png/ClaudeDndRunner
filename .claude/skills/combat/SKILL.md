---
name: combat
description: Run a fight — rolled initiative, positions on the grid, attacks, damage, conditions, movement and the end-of-fight write-back and XP offer. Use the moment violence starts.
allowed-tools: Bash(python engine/gm.py:*), Bash(python engine/space.py:*), PowerShell(python engine/gm.py:*), PowerShell(python engine/space.py:*), Read
---

# Combat

## Start
0. **Opening strike (house rule, rules/house-rules.md).** When a player (or an NPC) starts
   the fight against someone who isn't braced for it, **don't ask for initiative first**:
   - Braced (combat already running, a standoff with weapons out, Alert or a "can't be
     surprised" trait) → skip to step 1; their declared action is their first turn.
   - Telegraphed in plain view of a watchful target → `contest Grusk deception passive insight`
     (`contest Grusk stealth passive` if hidden first). It checks everyone present: the
     target wins → no opening strike; anyone who wins isn't surprised.
   - Otherwise resolve the declared action now: "Grusk, roll to hit." →
     `python engine/gm.py atk Grusk Tobin --with greataxe --d20 14` (advantage if unseen).
     **Paste the tool's roll line verbatim** (`[Grusk → Tobin: d20 14+5=19 vs AC 10 — HIT · …]`),
     then narrate the blow and, in the same message, ask **every player** for initiative
     (d20 + DEX). Nobody is "up" until `combat start` has printed the order. Everyone who didn't see it coming is
     `--surprised`; the attacker is `--opener` (their round-1 action is spent).
   - If nobody fights back, there's no combat: narrate the fallout instead.
1. If the scene isn't tense yet, place everyone by name first:
   `python engine/gm.py tempo tense --pos "Mara @bar" --pos "Kira near Tobin" …`
   (the Stage table's positions carry into combat).
2. **Authored fights** (an `ENCOUNTER "<name>"` line in the place or scenario): build the
   roster for who is actually present —
   `python engine/gm.py encounter build "<name>"` — and use the `--add` arguments it prints
   (a template scales its monster count to the table; a `fixed` fight keeps its roster
   and may warn that it is above the party: let it be a wall, and let them run).
   Improvised fights: pick monsters that fit the fiction (`monster list` shows this campaign's
   custom creatures; anything SRD works) and check the pressure with `encounter budget`.
3. Ask the players for their initiative rolls (d20 + DEX; they roll), then:
   `python engine/gm.py combat start --init Kael=15 --init Kira=12 [--add "srd:thug x3 @25,15,0"] [--add "srd:wolf @near Kira"] [--surprised Tobin] [--opener Grusk]`
   - `[X is surprised …]` / `[X struck first …]` notes print when that creature comes up:
     a surprised creature's turn passes with no move or action (narrate it reeling).
   - New monsters come from the SRD (`srd:<name>`; `xN` makes a group row). Their numbers
     are looked up, never recalled. `srd monster <name>` shows a stat block (for you only).
   - Anyone unplaced is listed: `python engine/gm.py pos <name> @<feature>`.
   - If there was no Layout for the room, describe the space and add what matters.
4. Show the map with the `/map` skill (only the `--player-view` render is ever pasted)
   and narrate the opening: who is where, who acts first (the order, not numbers).

## Each turn
A turn is an action, a bonus action, movement up to speed (split up however they like,
before, between and after attacks), one free object interaction, and a reaction once per
round. `combat start`/`next` print `[Kael's turn: …]`; the tools track what's spent.
- **A PC's turn isn't over until the player says so.** Resolve what they declared, then
  look at the `[Kael still has: …]` line the tool prints and offer it in a sentence:
  "You've still got your bonus action and 10 feet of movement. Anything else, or is that
  your turn?" Run `combat next` only when they're done, when nothing is left, or when their
  declaration already covered the whole turn ("I hit him and step back behind the bar":
  resolve all of it, then next).
- **PCs:** they declare; they roll their d20s; you resolve:
  `python engine/gm.py do "atk Kira Veskar --with dagger --d20 14; log \"…\""`
  (the tool rolls damage and applies it; a sneak attack / smite etc. is extra damage:
  `dmg Veskar 7`). It spends the action (Extra Attack counted); `--bonus` for a
  bonus-action attack. Saves: `save Kael dex 14 --d20 9`.
- **Other actions:** `turn use action` (Dash adds speed: `turn use dash`; Dodge, Disengage,
  Help, Hide, a spell), `turn use bonus`, `turn use object` (draw a second weapon, open a
  door, pick something up). `turn` alone prints what's left.
- **Movement by name:** `python engine/gm.py move Kael --to Veskar` (or `--to @door`,
  `--stop 10` for reach, `--path x,y,z …`, `--dash`). It finds the path, **saves the new
  position**, charges the feet to the mover's turn (refusing more than they have left), and
  lists opportunity attacks provoked: resolve those (`atk Veskar Kael`). `space move` is
  only a preview; it moves no one.
- **NPCs/monsters:** decide their whole turn (their goal, their fear, what just happened),
  move them with `move`, roll with the tools (`atk Veskar Kael`, `save …`, `space cone …`
  for areas), narrate, then `combat next`. Multiattack follows the stat block.
- **Conditions:** `cond Kael +poisoned 3r` (rounds tick down at round end), `-prone`.
- **Advance:** `python engine/gm.py combat next` — who's up, where, who is within reach,
  and the new turn's budget. A surprised creature's turn passes with no move or action.
  Moves of the round go to the session log automatically.
- Paste public roll lines; describe enemy HP in fiction only ("bloodied", "staggering").
- A PC at 0 HP makes death saves (d20, 10+ succeeds; three of either; nat 20 = up with
  1 HP; damage while down = a failure). Most monsters just die at 0.

## End
1. When it's over (dead, fled, surrendered): `python engine/gm.py combat end [--count "Bandit"] [--count-fled]`
   - Writes HP/conditions back to the files, marks dead NPCs, ends `combat` rules, runs
     lint, and prints `[XP available: …]` (foes at 0 HP; `--count` adds the routed,
     captured or talked-down; `--count-fled` all standing foes, if you judge so).
2. Award XP if the campaign tracks it: `python engine/gm.py xp award from-combat --reason "the inn brawl"`.
   Don't quote XP numbers in narration unless a player asks.
3. Narrate the aftermath and hand the scene back (tempo is calm again).
