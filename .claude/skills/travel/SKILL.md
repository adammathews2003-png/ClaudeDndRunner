---
name: travel
description: Move the party between locations (a building's rooms, places in a town, or towns on the world map) with real route, time, encounter roll and the arrival scene. Use whenever the party goes somewhere.
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*), Read
---

# Travel

1. `python engine/gm.py travel <site[/area] or place id> [--pace fast|normal|slow] [--by foot|cart|horse|boat] [--night] [--light dim|dark]`
   - It finds the route (no teleporting), derives the time, rolls the encounter table
     secretly, advances the clock, moves the party and enters the destination scene.
   - A locked way refuses: the party must deal with it first (a key, a check, force),
     then repeat with `--unlocked`. A `hidden (DC N to notice)` note means the way only
     exists for them if they found it.
   - No route at all → offer the fiction ("there's no road; cross-country through the
     marsh?") and use `--overland` if they go.
   - A place with no file yet → `stub location "<name>" --in <area> [--at x,y]` first.
2. Read the output (never paste it):
   - `[TRAVEL]` route and time; `passes:` real landmarks for the journey's narration.
   - `Encounter [SECRET …]` rolls: an `ENCOUNTER …` result is a fight or event to run
     (scale it to the party; `/combat` if it comes to blows); flavour results are
     colour for the journey; "nothing" is a quiet road.
   - `[TIME]`: schedules that moved NPCs (someone on the same road may be met), expired
     conditions, fired CLOCK beats — act on what matters.
   - The `[SCENE]` packet for the arrival (see `/scene`).
3. Narrate: the journey in a sentence or two using the landmarks and the time of day
   (the party's own words about pace and caution colour it), then the arrival scene.
   Say how long it took in fiction ("a quarter hour up the mill road"), not minutes on a
   clock unless they ask.
