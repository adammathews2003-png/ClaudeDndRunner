---
name: Widow's Notch Tollhouse
tier: site
type: outdoor
parent: world
tags: [frontier, danger, opening]
threat: {xp: 5000, fixed: true}
---

# Widow's Notch Tollhouse

## Description
The last building in Branholt: a squat stone tollhouse and a walled yard where the south
road squeezes between two cliffs before the pass. The pass itself is a white wall; the
snow stands twenty feet deep from here to the sky. A toll-bar across the road, a drift
against the yard wall, a sledge-turning circle trodden into the snow. The garrison of six
is nowhere. Their flag still flies. Something has gone through the tollhouse's north
wall and left a hole the shape of a very large person, and something snores inside
between noon and two.

## Areas
- **the-yard** — the road enters from the south through the toll-bar; stone walls either side; the tollhouse door on the west; the pass road leaves north and goes nowhere
- **the-tollhouse** — one long room: stove, six bunks, the toll chest; the hole in the north wall; Gerald sleeps here 12:00–14:00
- **the-armory** — a locked annex off the tollhouse (DC 15 Thieves' Tools, or the garrison key on a bunk-post); racks, a chest
- **the-pass-road** — north of the yard; walkable for 200 ft, then snow to the sky; impassable today

## Items & features
- The toll chest (tollhouse): 42 gp in tolls; the ledger's last entry is Day -3: "big weather coming. G. says he heard something."
- The armory: +1 longbow (uncommon; the garrison's prize, "Patience's Daughter"), potion of resistance (cold) ×2, a spyglass, 40 arrows, six winter cloaks
- The sledge-turning circle (yard): Pike's sledge arrives here at 09:00 and he gets down to argue with the snow
- The flag (yard): the kingdom's, frozen stiff; it points at the pass, like everything here

## Hidden
- DC 12 (the-yard): under the drift by the toll-bar, six helmets and what was in them
- DC 15 (the-yard): the hole in the tollhouse wall is 9 ft tall and the snow in front of it is yellow
- DC 10 (the-tollhouse, 12:00–14:00): the snoring is coming from the bunks and the bunks are the wrong shape

## Encounters
- ENCOUNTER fixed L3 deadly "The Pass Is Open": abominable yeti ×1 (Gerald)
<!-- adjusted: 5000 × 1 = 5000. The opening death. Gerald is awake 06:00–12:00 and 14:00–24:00 and attacks anything
     that enters the yard. He sleeps 12:00–14:00 (DC 15 Stealth to cross the yard and open the armory; a failed check
     wakes him). He does not leave the Notch: the pass is his, and the yard is his larder. -->

## Layout
### the-yard
Bounds: x 0–90 · y 0–60 · z 0–20 · origin (0,0,0) = SW corner of the yard, at the south wall's foot · +x east · +y north · +z up · ft

| id        | glyph | feature                | from       | to         | effect                                                    |
|-----------|-------|------------------------|------------|------------|-----------------------------------------------------------|
| road-in   | d     | the toll-bar           | (45,0,0)   | (45,0,0)   | exit → notch-road (south); bar is waist-high: difficult   |
| wall-s    | #     | south wall             | (0,0,0)    | (90,0,10)  | wall; the toll-bar is the gap                             |
| wall-e    | #     | east wall (cliff foot) | (90,0,0)   | (90,60,20) | wall                                                      |
| wall-w    | #     | tollhouse front wall   | (0,0,0)    | (0,60,15)  | wall; tollhouse door is the gap                           |
| house-door | h    | tollhouse door         | (0,30,0)   | (0,30,0)   | exit → the-tollhouse; door; closed                        |
| drift     | ~     | snowdrift              | (60,35,0)  | (90,60,5)  | difficult; 5 ft deep                                      |
| circle    | .     | sledge-turning circle  | (30,20,0)  | (60,40,0)  | packed snow; Pike's sledge stops here at 09:00            |
| road-out  | n     | the pass road          | (45,60,0)  | (45,60,0)  | exit → the-pass-road; 200 ft then impassable snow         |
| hole      | x     | hole in the north wall | (0,55,0)   | (0,55,10)  | exit → the-tollhouse; Gerald's door; secret               |
| flagpole  | f     | flagpole               | (20,50,0)  | (20,50,20) | climbable (DC 12); 20 ft                                  |

## Loot
| item | kind | rarity | where | guard | random | notes |
|------|------|--------|-------|-------|--------|-------|
| Patience's Daughter (+1 longbow) | treasure | uncommon | the-armory | The Pass Is Open (or DC 15 Stealth, 12:00–14:00, and DC 15 Thieves' Tools) | | the garrison's prize; its string hums the hour |
| the garrison's cold cordials | consumable | uncommon | the-armory | as above | | potion of resistance (cold) ×2, a spyglass, 40 arrows, six winter cloaks |
| the toll chest (42 gp) | treasure | — | the-tollhouse | as above; Gerald sleeps on it | loot-tier-1-4 | the ledger beside it is evidence the garrison is dead |

## Notes / current state
Gerald (abominable yeti) is here every day. Phil calls him Gerald. Gerald has not been
asked. The party reaches this yard at 09:00 on loop 0 with Dolorous Pike, and dies.
