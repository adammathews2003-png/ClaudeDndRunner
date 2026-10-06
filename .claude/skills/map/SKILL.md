---
name: map
description: Show the players the tactical map of the current fight or tense scene (top-down grid, legend, distances from the active creature). Use at combat start, when the layout changes meaningfully, or when a player asks for the map.
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*)
---

# Map

Never draw a map yourself: the tool's map is the only map (its distances are real).

1. `python engine/gm.py space map --player-view [--from <active creature>]`
   - **Always `--player-view`.** It leaves out secret terrain (an unspotted trapdoor) and
     creatures the party can't perceive (hidden, invisible, unseen). The full map
     (without the flag) is yours alone and is never pasted.
   - `--from` = whoever is up (combat) or the PC who asked; the legend then shows
     distances from them.
2. Paste the rendered grid and legend verbatim inside a code block, then one line of
   fiction to orient ("Veskar is on the landing above you; the thugs bunch by the tables").
3. **A calm scene** has no positions saved, so the map shows the room alone. Place
   everyone for this one drawing with `--at` (nothing is saved, the tempo stays calm),
   from what the fiction has established:
   `space map --player-view --from Grusk --at "Grusk=15,15" --at "Tobin=near Grusk" --at "Mara=@bar N" --at "Kael=@tables-w" --at "Kira=near Kael"`
   In tense or combat tempo the saved positions are used; adjust them with `pos`.
4. If it prints `nothing to draw`, the place has no `## Layout` yet: describe the space
   in words instead (no drawn map).
