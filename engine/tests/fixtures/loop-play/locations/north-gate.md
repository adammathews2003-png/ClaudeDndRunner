---
name: The North Gate
tier: site
type: building
parent: bellwether
tags: [gatehouse, danger, opening]
threat: {xp: 4200, fixed: true}
---

# The North Gate

## Description
A squat stone gatehouse in the north wall with a walled yard behind it, where the Bell
Road comes in from the glacier. The gate stands open at dawn for the monastery's sausage
cart, which is how the trouble gets in. Snow is drifted against the walls; the yard is
trampled, bloody and loud at a quarter past six, and empty and tidy by seven. The
guardhouse door in the east wall is shut until the morning patrol musters.

## Areas
- **yard** — walled yard inside the gate; North Street enters from the south; the keep gate's short street enters from the south-east corner
- **gatehouse** — the arch and the gate itself (north wall); portcullis rusted open
- **guardhouse** — east wall; the night watch sleeps here, heavily, until 06:45
- **wall-walk** — stairs in the west corner up to the wall (z 20); overlooks the yard and the Bell Road

## Items & features
- The sausage cart (yard, 06:15–06:45): overturned, one wheel spinning, the monastery's whole Midwinter delivery spilling out of it; the cart horse has bolted back up the road
- Barrels of sausages (yard): rolling loose; three wolves think they are the best thing that has ever happened
- The gate: open at 06:00 for the cart; can be swung shut by two people in a round (STR DC 13 for one)
- The alarm bell (gatehouse arch): cracked; standing orders are that whoever rings it must also shout "BELL" so the watch know it was the bell and not the crack; ringing it (and shouting) brings Captain Bergmann's patrol in 10 minutes instead of at 06:45
- Pim (06:15–06:20, loop 0): the boot-boy who ran the sausage cart's lantern; he is under the cart when the party arrives, and he is the one who screamed

## Hidden
- DC 12: the wolves' tracks come straight down the Bell Road from the glacier, not from the woods
- DC 14 (wall-walk): from up here you can see the whole pack arrive at 06:19, and that the goose on the far corner of the wall is watching them, not you
- DC 13 (yard): the wolves queue: the torn-eared one comes through the gate first and the other two wait their turn behind the arch, like a custom

## Encounters
- ENCOUNTER fixed L5 deadly "the wolves at the door": winter wolf ×3   # 06:20–06:45 every loop; the opening death; never rescaled
- ENCOUNTER easy "the morning patrol": guard ×n   # only if the party fights the Guard

## Loot
| item | kind | rarity | where | guard | random | notes |
|------|------|--------|-------|-------|--------|-------|
| the torn-eared wolf's luck (stone of good luck) | treasure | uncommon | yard | the wolves at the door | | swallowed years ago by the big wolf; the reason it is always the one that gets away; only recovered if the wolves are killed |
| the sausage cart's strongbox | treasure | — | cart | DC 13 Thieves' Tools | | 25 gp for the granary and the monks' delivery chit; the Guard will want it back, politely |
| the monastery's Midwinter sausages | consumable | — | barrels | — | | 40 lb; a week's rations for four; the wolves, the goose and Wil all want them |

## Layout
### yard
Bounds: x 0–60 · y 0–60 · z 0–25 · origin (0,0,0) = SW corner of the yard, inside the walls · +x east · +y north · +z up · ft

| id         | glyph | feature               | from      | to        | effect                                                  |
|------------|-------|-----------------------|-----------|-----------|---------------------------------------------------------|
| wall-w     | #     | west wall             | (0,0,0)   | (0,60,20) | wall                                                    |
| wall-e     | #     | east wall             | (60,0,0)  | (60,60,20) | wall; guardhouse door is the gap                       |
| wall-n     | #     | north wall and gatehouse | (0,60,0) | (60,60,25) | wall; the gate is the gap                              |
| gate       | d     | the North Gate        | (25,60,0) | (35,60,0) | door; open; exit → bell-rd                              |
| street-s   | d     | North Street          | (25,0,0)  | (35,0,0)  | exit → north-st                                         |
| street-se  | d     | keep gate street      | (60,5,0)  | (60,10,0) | exit → keep-gate-n                                      |
| guard-door | d     | guardhouse door       | (60,30,0) | (60,30,0) | door; closed (opens 06:45); exit → guardhouse           |
| cart       | c     | overturned sausage cart | (25,35,0) | (35,40,5) | half cover; crossing = difficult                       |
| barrels    | o     | spilled barrels       | (15,25,0) | (45,35,0) | difficult                                               |
| drift-w    | ~     | snowdrift             | (0,40,0)  | (10,60,0) | difficult                                               |
| drift-e    | ~     | snowdrift             | (50,40,0) | (60,60,0) | difficult                                               |
| wall-stair | s     | stairs to the wall-walk | (0,5,0) | (5,15,20) | stairs up to wall-walk (z 20)                           |

## Notes / current state
(none yet)
