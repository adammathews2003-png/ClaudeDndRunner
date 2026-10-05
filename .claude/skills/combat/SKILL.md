---
name: combat
description: Run a fight — rolled initiative, positions on the grid, attacks, damage, conditions, movement and the end-of-fight write-back and XP offer. Use the moment violence starts.
allowed-tools: Bash(python tools/gm.py:*), Bash(python tools/space.py:*), PowerShell(python tools/gm.py:*), PowerShell(python tools/space.py:*), Read
---

# Combat

## Start
1. If the scene isn't tense yet, place everyone by name first:
   `python tools/gm.py tempo tense --pos "Mara @bar" --pos "Kira near Tobin" …`
   (the Stage table's positions carry into combat).
2. Ask the players for their initiative rolls (d20 + DEX; they roll), then:
   `python tools/gm.py combat start --init Kael=15 --init Kira=12 [--add "srd:thug x3 @25,15,0"] [--add "srd:wolf @near Kira"] [--surprised Tobin]`
   - New monsters come from the SRD (`srd:<name>`; `xN` makes a group row). Their numbers
     are looked up, never recalled. `srd monster <name>` shows a stat block (for you only).
   - Anyone unplaced is listed: `python tools/gm.py pos <name> @<feature>`.
   - If there was no Layout for the room, describe the space and add what matters.
3. Show the map with the `/map` skill (only the `--player-view` render is ever pasted)
   and narrate the opening: who is where, who acts first (the order, not numbers).

## Each turn
- **PCs:** they declare; they roll their d20s; you resolve:
  `python tools/gm.py do "atk Kira Veskar --with dagger --d20 14; log \"…\""`
  (the tool rolls damage and applies it; a sneak attack / smite etc. is extra damage:
  `dmg Veskar 7`). Saves: `save Kael dex 14 --d20 9`.
- **Movement by name:** `python tools/gm.py space move Kael --to Veskar` (or `--to @door`,
  `--stop 10` for reach). It finds the path, costs it against speed, lists opportunity
  attacks provoked. The path is the move; resolve any OAs it reports.
- **NPCs/monsters:** decide what they do (their goal, their fear, what just happened),
  then roll with the tools: `atk Veskar Kael`, `save …`, `space cone …` for areas.
- **Conditions:** `cond Kael +poisoned 3r` (rounds tick down at round end), `-prone`.
- **Advance:** `python tools/gm.py combat next` — who's up, where, who is within reach.
  Moves of the round go to the session log automatically.
- Paste public roll lines; describe enemy HP in fiction only ("bloodied", "staggering").
- A PC at 0 HP makes death saves (d20, 10+ succeeds; three of either; nat 20 = up with
  1 HP; damage while down = a failure). Most monsters just die at 0.

## End
1. When it's over (dead, fled, surrendered): `python tools/gm.py combat end [--count "Bandit"] [--count-fled]`
   - Writes HP/conditions back to the files, marks dead NPCs, ends `combat` rules, runs
     lint, and prints `[XP available: …]` (foes at 0 HP; `--count` adds the routed,
     captured or talked-down; `--count-fled` all standing foes, if you judge so).
2. Award XP if the campaign tracks it: `python tools/gm.py xp award from-combat --reason "the inn brawl"`.
   Don't quote XP numbers in narration unless a player asks.
3. Narrate the aftermath and hand the scene back (tempo is calm again).
