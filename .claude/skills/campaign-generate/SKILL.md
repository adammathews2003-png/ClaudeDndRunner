---
name: campaign-generate
description: Generate a campaign's first arc (truth, scenario, NPCs, places, tables, threat metadata) from its campaign.md and seed, in a forked context, and return only the player-safe shape card. Invoked by /campaign-new with the campaign slug.
context: fork
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*), Read, Write, Edit, Glob, Grep
---

# Generate a campaign (forked: the driver never sees this)

Campaign slug: $ARGUMENTS

Read first: `campaigns/<slug>/campaign.md`, `campaigns/<slug>/campaign-seed.md`, `docs/design/07-campaign-authoring.md`
(shapes, difficulty, items, mechanics), `docs/design/04-file-formats.md` (every file format:
follow them exactly), and as a worked example `campaigns/poc/` (scenario, NPCs, locations).

## Write
1. **The truth and the arcs** in `campaign.md ## Author notes (GM-only)`: what's really
   going on, the arcs, the finale, what stays open. The shape's "must exist" list (07) is
   a checklist. Write `## Premise (player-safe)`.
2. **The first scenario** `scenarios/<slug>.md` (04 → Scenario file): `## Premise
   (player-safe)`, `## The truth (SPOILERS — GM only)`, factions, `## Beats & triggers`
   with machine lines (`- WHEN … → …`, `- CLOCK Day N HH:MM: …`), resolution paths.
3. **The starting area and its sites** (04 → Location files): `## Places` with
   coordinates for what's placed (or `gm.py stub location|place … --in <area> --at x,y`),
   `## Routes`, `## Hidden` with DCs, `## Areas` for sites. Directions and distances are
   never written in prose against the geometry. The world: `gm.py world add|lead …` for
   known-not-placed places and frontier leads from the seed.
4. **NPCs** the opening needs (04 → NPC file): `statblock:` an SRD 5.1 monster name
   (check with `gm.py srd monster <name>`; a non-SRD creature needs `statblock: custom`
   with numbers), `default-goal`, secrets under `## Knowledge & secrets`, and
   `## Movements` lines in the exact form `- HH:MM–HH:MM → site[/area] (note)` (prose
   after; never "→ in transit"). A sidekick if `sidekick:` asks (07).
5. **Monsters: be creative.** When the theme wants a creature the SRD lacks, or a named
   one, make it: `gm.py --campaign <slug> monster new "<name>" --from "<closest SRD monster>"`,
   then edit the file in `campaigns/<slug>/bestiary/` — rename attacks thematically, add a
   fitting trait or damage rider, set `cr`/`xp`, write a Description and a Backstory
   (`bestiary/frost-yeti.md` and `campaigns/loop-open/bestiary/gerald.md` are examples).
   Reusable species can already exist in the shared `bestiary/` (`gm.py monster list`).
   **Encounters as budgets**: `- ENCOUNTER <easy|medium|hard|deadly> "<name>": <monster> ×n, …`
   or `- ENCOUNTER fixed L<level> <word> "<name>": <roster>`, every monster SRD or bestiary
   (lint warns otherwise). Then
   `gm.py --campaign <slug> encounter threat <place>` on every adventure place (it writes
   `threat:`), and check the readings with `encounter build "<name>"`.
6. **Loot and merchants** (07 → Items): `## Loot` tables (a treasure item in every
   yellow-or-harder place), `tables/loot-*.md`, three merchants with `## Stock` (one set,
   two random-ish with `tables/stock-*.md`). Rarity caps by level band.
7. **Tables**: `tables/encounters-<route id>.md` for dangerous roads, `| roll | result |`.
8. **The opening**: `state/current.md` via
   `gm.py --campaign <slug> scene enter <site/area> --write --summary "…"`, set the clock
   (`time`), Watch for and Clocks. A time-loop campaign also gets PCs' `loop-bed` in the
   PC template and `state/loops.md` (already created).
9. Queue anything the driver should decide (names, a PC tie-in) with
   `gm.py --campaign <slug> campaign fill --add "<question>" --default "<default>"`.
10. Set `status: generated` in `campaign.md` and run `gm.py --campaign <slug> lint`; fix
    every error (warnings about deliberately unfinished canon are fine).

Weirdness and jokes are dials (07): at 3, one scene in three has a deliberate bit.

## Return ONLY the shape card
Your final message is the only thing the driver sees. It contains, and nothing else:
- the premise as players hear it, and the opening scene in two or three sentences;
- the places the party knows and the frontier leads;
- the stakes as the party can perceive them;
- length / difficulty / start level / shape / tone settings;
- the danger-stone readings at the start level for the known places (green/yellow/red only);
- the fill-in queue questions with their defaults.
**Never** the truth, twists, beats, clocks, NPC secrets or motives, dungeon contents,
piece locations, or encounter rosters. Do not quote any `## The truth`, `## Author notes`,
`## Knowledge & secrets`, `## Hidden` or `## Beats` text.
