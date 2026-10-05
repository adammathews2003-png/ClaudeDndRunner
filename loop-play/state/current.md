---
campaign: loop-play
in-game-datetime: "Day 1 06:18"   # absolute day + 24 h clock; tools add to it
party-location: north-gate/yard   # site or site/area
scene: "The North Gate yard at dawn, wolves at the door"
light: dim                        # bright | dim | dark; snow-dawn
in-session: false                 # /gm sets true (turns on the brief hook)
dice-mode: players-roll-d20s      # players-roll-d20s | gm-rolls-all
loop: 0                           # before the opening; loop 1 begins at the first reset
loop-baseline: pending            # gm.py loop start writes the commit sha here
loop-start: "Day 1 06:00"
loop-end: "Day 2 00:00"
---

# Current scene

## Summary
Midwinter morning, Day 1, snowed in. The party, stranded travellers who reached the
Sleeping Marmot last night, were woken at 06:15 by howling and the innkeeper's shouting
and have just run up North Street into the gate yard: the monastery's sausage cart is
on its side, barrels everywhere, the gate stands open on the Bell Road, and three white
wolves the size of ponies are coming through it. A man in a feathered cap is yelling
"NOT THE GATE" from somewhere behind them. This is the opening; it is meant to kill
them. When it does, run `loop start` at Day 1 06:00 with the party in sleeping-marmot/loft.

## On stage
- **The wolves** (srd:winter wolf ×3; north-gate.md fixed encounter) — through the gate at 06:20; after the sausages, then after anything that moves; goal: eat
- **Wil Groundsel** (npcs/wil-groundsel.md) — at the North Street end of the yard, out of reach; goal: get the new people back indoors, failing, as always
- **Pim** (npcs/pim.md) — under the overturned cart, screaming; goal: not be eaten; obvious to grab and run with
- **Horace** (npcs/horace.md) — on the gatehouse wall, watching; goal: watch
- (Captain Bergmann and the patrol arrive at 06:45, or in 10 minutes if the alarm bell is rung)

## Watch for
- Party dies or sleeps → loop reset; loop 1 begins at Day 1 06:00 in sleeping-marmot/loft; Wil at the bedside at 06:05 with the danger stone (scenario beat 1)
- Party rings the alarm bell (and shouts "BELL") → the patrol in 10 minutes (north-gate.md)
- Loop 1, 06:02 → Biscuit the post-marmot delivers Wil's letter to the loft (sleeping-marmot.md); Pim is at the kitchen door with the boots: both sidekick candidates are in the first five minutes
- Party shuts the gate (two people, one round) → the wolves already inside stay inside
- Party shows the stone to Fahrenheit or Temperance → scenario WHEN (the five stones named)
- Party heads for the Keep's chapel → scenario WHEN (the Crown; it gets down like a cat at 20:45)

## Clocks
- Day 1 06:20: the wolves at the door until 06:45 (scenario clock)
- Day 1 06:45: Bergmann's patrol drives the wolves up the Bell Road
- Day 1 07:00: Fahrenheit's forecast
- Day 1 10:00: the Winter King lottery in the square
- Day 1 14:00: Castle Lark passes Widow's Ridge (ladder down until 14:10)
- Day 1 18:00: the Great Toast begins at the monastery
- Day 1 20:00: the procession; 20:45 the Crown returns to its stand; 21:00 the crowning (fixed encounter until 00:00)
- Day 2 00:00: loop reset

## Tempo: calm  <!-- calm | tense | combat; the GM will go to tense the moment the wolves clear the gate -->

## Combat
(not in combat)
