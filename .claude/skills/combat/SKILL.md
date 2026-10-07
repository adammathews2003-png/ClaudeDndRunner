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
- **Concentration:** when a caster casts a concentration spell, `conc Kael bless --on
  Kael,Kira 1m` (it ends the caster's previous one; the targets get `bless 10r`). Damage
  to a concentrating creature prints `[concentration: CON save DC 12 to keep bless (gm.py
  save Kael con 12)]`: ask the player for that d20 (`save Kael con 12 --d20 9`); the tool
  rolls an NPC's. A failed save, 0 HP, an incapacitating condition or the duration ends
  it and strips every target: narrate the glow fading. Don't track it yourself.
- **Ammunition:** ordinary arrows and bolts are endless; never count them. Only a
  `special ammo <thing>` attack (or any ammo under `ammo: all`) is spent for you, and
  `Kira has no <thing>` means the attack doesn't happen; offer another weapon.
- **Advance:** `python engine/gm.py combat next` — who's up, where, who is within reach,
  and the new turn's budget. A surprised creature's turn passes with no move or action.
  Moves of the round go to the session log automatically.
- **Morale.** `[Morale (half HP): Thugs — WIS save DC 10 (gm.py save Thugs wis 10) …]`
  means the foes wonder whether this is worth it: run that save (you roll it). On a
  failure they flee (Dash and Disengage) or, if cornered, surrender: `cond Thugs +fled`
  / `+surrendered` takes them out of the turn order. Mark a boss `leader` in its row's
  notes so its fall shakes the rest. The tool never asks it of the party, nor of
  mindless undead, constructs and oozes. Fled and surrendered foes count for XP;
  surrendered ones are on stage as prisoners after the fight.
- **Readied actions.** "I wait for the door to open, then shoot": `ready Kira "shoot
  whoever opens the door"` (it spends nothing yet). Before every other creature's turn
  `combat next` prints `[Readied: Kira — …]`: if that turn meets the trigger, interrupt it
  and `ready Kira fire` (her reaction), then resolve the action (`atk …`). An unfired
  ready lapses at the start of her next turn by itself; `ready Kira drop` lets it go. A
  readied spell: `ready Kael "when Veskar moves" --spell "hold person"` — the slot goes
  now and he concentrates on it until it fires or lapses.
- **Companions and hirelings.** A PC's companions (`companion add Kira Ash srd:owl --acts
  own|with`) join `combat start` on the party's side with `ctrl Kira`; give one its own
  initiative with `--init Ash=N` (or the tool rolls it), and `with` places it right after
  its owner. `[round 1 · up: Ash (Kira's)]` means **ask Kira's player** what Ash does.
  Hired NPCs (`hire`) fight for the party and check morale against `DC 20 − loyalty` when
  hurt or when the party is losing; run that save yourself.
- **Mounts.** `mount Kael Horse` (in combat both need rows; out of combat the horse is one
  of Kael's companions with `--acts mount`, and the next fight seats him). A controlled
  mount moves to Kael's initiative right after him and may only Dash, Disengage or Dodge
  (the tool reminds you); move it and keep Kael on it with `pos`. Kael knocked prone →
  the tool asks for his DC 10 DEX save (a fail: `dismount Kael`, prone beside it); the
  horse knocked prone → he falls unless he spends his reaction. `--independent` for a
  mount that acts on its own initiative.
- **Inspiration / weather / load.** `--insp` on the player's `atk`/`save` spends their
  inspiration. Outdoors in a strong wind (`weather: on`) ranged attacks are at
  disadvantage by themselves; a heavy load (`[heavy]`) is too. Don't add them twice.
- **Hidden attackers.** A creature with `hidden 17` (from `hide`) attacks with advantage
  and is no longer hidden afterwards; the tool does both. `seek Thug 1 <total>` is an
  active search (an action).
- **Underwater** (`hazard env underwater`): the tool gives melee attacks disadvantage
  except daggers, javelins, shortswords, spears and tridents; ranged attacks miss past
  normal range and are at disadvantage within it (crossbows, nets and thrown javelins,
  spears, tridents and darts aside); fire damage is resisted. Just narrate the result.
- Paste public roll lines; describe enemy HP in fiction only ("bloodied", "staggering").
- **Dying.** A PC at 0 HP is dying; the tools write it (`DYING ✓0 ✗0` on the party line)
  and count damage while down (a failure; `dmg Kira 6 --crit` is two; damage of their HP
  maximum kills). On the dying PC's turn `combat next` prints `Kira is dying (✓1 ✗2):
  death save — ask for a d20`: ask the player, then `deathsave Kira 14` and narrate only
  what it looks like. With `roll it hidden` (`death-save-rolls: secret`), run `deathsave
  Kira` yourself and narrate the breathing, never the count. Help: `stabilize Kira --by
  Kael 12` (Medicine DC 10, the player's d20), `--kit` (a healer's kit use) or `--spell`
  (spare the dying); any healing brings them back. Most monsters just die at 0.
- **Split party:** only the active group fights; the others are in their own scenes.
  Watch the brief's `Slice:` line at each round's end: `Cut every round` (another group
  can sense the fight) → `split cut` after this round; `Cut due: 6 rounds played` →
  cut at this round's end. Close the round on a tense beat. The tools charge the
  rounds to the group's clock (6 s each) when you cut away or the fight ends.

## End
1. When it's over (dead, fled, surrendered): `python engine/gm.py combat end [--count "Bandit"] [--count-fled]`
   - Writes HP/conditions back to the files, marks dead NPCs, ends `combat` rules, runs
     lint, and prints `[XP available: …]` (foes at 0 HP or marked `fled` / `surrendered`;
     `--count` adds the routed, captured or talked-down; `--count-fled` all standing
     foes, if you judge so). Surrendered foes join On stage as prisoners. Companions' HP
     goes back to their owner's `## Companions` row; readied actions are dropped.
   - `[Ammo: Kira spent 6 arrows; after a search, 3 can be recovered (gm.py item Kira +3
     arrows)]`: if they search, run that `item`. Under `loose` it names who fired: estimate
     with them and spend it with `item Kira -4 arrows`.
2. Award XP if the campaign tracks it: `python engine/gm.py xp award from-combat --reason "the inn brawl"`.
   Don't quote XP numbers in narration unless a player asks.
3. Narrate the aftermath and hand the scene back (tempo is calm again).

## Chases
When someone runs and someone follows (`chases: dmg`; under `narrative` a contest or two
does it): `python engine/gm.py chase start --quarry Veskar [--pursuers Kael,Kira]
[--lead 60] [--env urban|wild]`. It replaces the Combat block; no fight runs alongside.
- Each turn: `chase next` moves whoever is up (a Dash by default; `--no-dash` for a plain
  move, `--lose 10` for ground lost to a complication). `chase dash Kira` is an extra
  Dash (Cunning Action). Past their free Dashes (3 + CON) a PC owes a DC 10 CON save
  (ask for the d20; a failure is `exhaust Kira +1 "chase"`); the tool rolls an NPC's.
- The tool rolls a **complication** for whoever is next: narrate it and ask for the
  check or save it names; a failure costs ground (`--lose`) or what it says.
- When the quarry is out of sight it tries to hide: the tool rolls an NPC's Stealth
  against the pursuers' best passive Perception; a PC quarry rolls their own, and on a
  win you run `chase end escaped`. A pursuer who reaches the quarry ends it: `[caught:
  start combat or grapple]` → `combat start` (or a grapple). `chase end gave-up` when
  the pursuers stop. The clock moves 6 s a round when it ends.
