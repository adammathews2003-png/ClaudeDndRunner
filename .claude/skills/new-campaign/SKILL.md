---
name: new-campaign
description: Scaffold a new, empty campaign folder (state, sessions, world map with the starting area at its origin) and optionally make it the active campaign. Players or the author type /new-campaign; content generation comes later.
disable-model-invocation: true
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*), Read
---

# New campaign

Request: $ARGUMENTS

1. Settle three things with whoever asked (one short question if they didn't say):
   - a folder slug (short, lowercase: `frostmere`),
   - the starting area's name (a village, a city district, a camp: "Brindle Ford"),
   - whether to make it the active campaign now.
2. `python engine/gm.py scaffold <slug> --area "<starting area>" [--type settlement|city|camp|wilderness] [--start "Day 1 08:00"] [--activate]`
   - It creates the folder from the 04 templates, the starting area file, and
     `locations/world.md` with that area at (0,0,0) — a campaign never lacks a world map —
     and lints the result (expect 0 errors).
3. Report back in two lines: the folder, the starting area, whether it's active, and the
   next steps: write the area's Description, Places and Routes; add NPCs
   (`python engine/gm.py stub npc …`) and a scenario; then PCs with `/character`, and play
   with `/gm`.
4. Generating a whole campaign (premise, scenario, NPCs, secrets) is a separate,
   author-side step (the campaign authoring tools); don't invent secrets here, at the table.
