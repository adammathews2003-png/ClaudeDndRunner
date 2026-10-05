# Mechanic: the time loop

Loaded by `/gm` only when the campaign's `campaign.md` lists `mechanics: [time-loop]`
(docs/design/07 → Time loop). The first section may be told to players as is; the second is
the GM's.

## What the players know (say it plainly when they first notice the loop)
- **The day repeats.** At the loop's end, or when the whole party dies, or when you all
  fall asleep, you wake in your beds at the start of the same day.
- **You keep yourselves.** What you carry, what you learned, your levels and your scars
  of experience stay with you. Your bodies wake rested and whole.
- **The world forgets.** Everyone and everything else is back where it was that morning:
  doors relocked, conversations unsaid, the shops restocked, coin spent comes back to the
  till. A thing you carry from one day into the next is still in your pack; the world's
  copy of it is back where it was, but it is hollow.
- **One of you dying alone** isn't the end: they wake at the next reset, having missed
  the rest of the day.

## The GM's procedure
- **Start:** `python engine/gm.py loop start [--bed site/area]` at the loop day's first
  moment (sets the clock, the beds, and the git baseline).
- **Reset:** `python engine/gm.py loop reset --by death|sleep|time` the moment one of the
  triggers happens (the clock triggers `--by time` by itself at `loop-end`). Narrate the
  wake-up as the same morning, the same first sounds, word for word where you can.
- **Consistency across loops:** `state/loops.md` (one row per reset: what was learned and
  gained) and `python engine/gm.py loop status`. The world repeats exactly unless the
  party changes something: "the guard still sneezes at 09:10". NPC schedules repeat
  (`clock advance` runs them every loop).
- **NPCs don't remember**, except an NPC with `## Memory across loops`: append what they
  recall after each reset (by hand in a prep moment, or `log` it and fill it in later).
- **Pieces:** a carried piece persists; the regenerated copy is marked `duplicate; hollow`
  by `loop reset` — inert, and the GM describes it as subtly wrong when found again.
- **Spoilers and trace** treat each loop as its own day ("Loop 3 · Day 1 09:10").
- Never narrate the loop's cause or rules beyond the first section until the party learns
  them in play.
