---
name: The Royal Observatory
tier: site
type: building
parent: kettlebrook
tags: [ceremony, danger, society]
threat: {xp: 4400, fixed: true}
---

# The Royal Observatory

## Description
A brass dome sixty feet across on top of the Star Tower, the keep's tallest corner. Inside:
one round room under a ribbed ceiling, the great lens (a brass tube as long as a mast)
aimed through a slot in the dome at the northern sky, and in the middle of the floor the
Orrery of Hours: a ring of bronze thirty feet across, waist-high, set with planets on
arms, that turns about a hub where a sun-shaped socket waits for a key. Star charts cover
the west wall. A lectern. A plinth with a hatbox on it. A door to a narrow balcony with a
120-ft drop to the keep's yard. It is very cold and smells of brass polish and incense,
and at night, of ozone.

## Areas
- **the-dome** — the single round room; the door at the top of the Star Tower stair (300 steps)
- **the-balcony** — east door; iron rail; 120 ft above the keep yard; the lens slot's dust cover is reached from here

## Items & features
- The Orrery of Hours (center): the ring, the planet arms, the hub with the winding socket. From 23:30 the ring glows and the arms spin; three turns of the King's Key at the hub (three actions, DC 10 Str each, interruptible) unwind it
- The great lens (north): its cradle holds a dust cover by day; the Mirror of the Still Star fits the cradle exactly
- Star charts and the working diagram (west wall): the diagram is mirrored (DC 12 Investigation, or hold it to a mirror)
- Ptolemy's plinth (NW): the hatbox; Ptolemy is in it from 20:30
- Lectern (SW): the Almanac's reading-copy is **not** here (Shackleton has it); Brahe's cocoa is

## Hidden
- DC 13: a faint scorch mark on the floor inside the ring, man-shaped, thirty years old and never cleaned
- DC 15: the balcony door's bolt is on the outside, which is the wrong side
- DC 16 (the-dome): the dust cover can be fitted over the lens cradle with something behind it and still look right from the floor

## Encounters
- ENCOUNTER fixed L5 deadly "The Vigil of the Still Star": cult fanatic ×1 (Astronomer-Royal Isidore Brahe), flameskull ×1 (Grandmaster Ptolemy), gargoyle ×1 (the dome's stone sentinel), animated armor ×1 (the Brass Warden)
<!-- adjusted: 450 + 1100 + 450 + 200 = 2200 × 2 (4 monsters) = 4400. Fellows Tibbs and Pook are present
     21:00–24:00 as noncombatant chanters (commoners); attacking either breaks the chant (scenario). -->

## Layout
### the-dome
Bounds: x 0–60 · y 0–60 · z 0–30 · origin (0,0,0) = SW corner of the dome floor, at the top of the stair · +x east · +y north · +z up · ft

| id        | glyph | feature                 | from       | to         | effect                                                   |
|-----------|-------|-------------------------|------------|------------|----------------------------------------------------------|
| door      | d     | stair door              | (30,0,0)   | (30,0,0)   | exit → star-stair; door; locked at 21:00 (King's Key)   |
| wall-s    | #     | south wall              | (0,0,0)    | (60,0,30)  | wall; stair door is the gap                              |
| wall-n    | #     | north wall and lens slot | (0,60,0)  | (60,60,30) | wall; the slot at (30,60,20) is 3 ft wide                |
| wall-w    | #     | west wall               | (0,0,0)    | (0,60,30)  | wall                                                     |
| wall-e    | #     | east wall               | (60,0,0)   | (60,60,30) | wall; balcony door is the gap                            |
| balcony   | b     | balcony door            | (60,30,0)  | (60,30,0)  | exit → the-balcony; door; bolt on the outside            |
| ring      | o     | the Orrery ring         | (15,15,0)  | (45,45,0)  | difficult (bronze ring and arms); inside = the ring      |
| hub       | *     | the hub and socket      | (30,30,0)  | (30,30,0)  | the King's Key fits here; 3 actions to unwind            |
| lens      | L     | the great lens          | (30,45,10) | (30,60,20) | brass tube; half cover; cradle at (30,45,10)             |
| charts    | c     | star charts and lectern | (0,20,0)   | (5,40,0)   | half cover                                               |
| plinth    | p     | Ptolemy's plinth        | (5,50,0)   | (5,50,5)   | half cover; the hatbox                                   |
| brazier   | h     | incense braziers        | (10,10,0)  | (10,10,0)  | entering = 1d6 fire; a second at (50,10,0)               |

## Loot
| item | kind | rarity | where | guard | random | notes |
|------|------|--------|-------|-------|--------|-------|
| the Sun-Weight | treasure | uncommon | the-dome | the Vigil (or DC 14 Sleight of Hand, 14:00–16:00, with the Fellows present) | | a brass sun on a chain from the Orrery's hub; a *pearl of power*; it is warm at midnight |
| Brahe's cocoa | consumable | rare | the-dome | the Vigil | | one cup = potion of heroism; he drinks it at 23:30 |
| Ptolemy's hatbox | campaign | — | the-dome | the Vigil | | after the Working collapses, a quiet skull who will teach astronomy for a new hat |

## Notes / current state
Empty and locked by day (the Society keeps the only keys; the King's Key is a master).
Brahe, the Fellows and the hatbox arrive 20:30; the Vigil runs 21:00–24:00.
