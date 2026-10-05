---
name: map
description: Show the players the tactical map of the current fight or tense scene (top-down grid, legend, distances from the active creature). Use at combat start, when the layout changes meaningfully, or when a player asks for the map.
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*)
---

# Map

1. `python engine/gm.py space map --player-view [--from <active creature>]`
   - **Always `--player-view`.** It leaves out secret terrain (an unspotted trapdoor) and
     creatures the party can't perceive (hidden, invisible, unseen). The full map
     (without the flag) is yours alone and is never pasted.
   - `--from` = whoever is up (combat) or the PC who asked; the legend then shows
     distances from them.
2. Paste the rendered grid and legend verbatim inside a code block, then one line of
   fiction to orient ("Veskar is on the landing above you; the thugs bunch by the tables").
3. If it prints nothing, there is no placed creature or terrain yet: place them first
   (`tempo tense --pos …` or `pos <name> @<feature>`), or describe the space instead.
