---
name: The Crossroads Inn
type: building
region: thornbury
tags: [social, safe]
---

# The Crossroads Inn

## Description
A two-story timber inn at the east end of Thornbury's square, smelling of woodsmoke and
mutton stew. The common room holds eight scarred tables, a long bar along the north wall,
and a hearth that never goes out. Rooms upstairs; kitchen and side door to the stable
yard in back. Evenings it fills with farmhands; by day it's near empty.

## Connections
- **Village square** (locations/village-square.md) — out the front door, 1 min, obvious
- **Stable yard** — side door past the kitchen, 1 min, obvious
- **Cellar** — trapdoor behind the bar, locked (Mara keeps the key on her belt), not obvious (DC 12 Perception)

## Items & features
- Bar (north wall): strongbox beneath, locked (DC 15 Thieves' Tools), ~40 gp and a brass key
- Notice board (by the door): posting offering 25 gp for word of Harl the miller, signed by Reeve Odell
- Hearth (east wall): always lit

## Hidden
- DC 13: dried mud footprints, days old, leading from the side door toward the bar — and stopping at the trapdoor
- DC 17: from below the floorboards, very faint, an occasional scrape

## Layout
### common-room
Bounds: x 0–45 · y 0–35 · z 0–10 · origin (0,0,0) = inside the front door, SW corner · +x east · +y north · +z up · ft

| id       | glyph | feature           | from      | to         | effect                                     |
|----------|-------|-------------------|-----------|------------|--------------------------------------------|
| door     | d     | front door        | (0,0,0)   | (0,0,0)    | exit → village square                      |
| bar      | b     | bar counter       | (15,25,0) | (35,25,0)  | half cover; crossing = difficult           |
| trapdoor | x     | cellar trapdoor   | (25,30,0) | (25,30,0)  | behind the bar; locked                     |
| tables-w | t     | tables & benches  | (10,10,0) | (15,15,0)  | difficult                                  |
| tables-e | t     | tables & benches  | (30,5,0)  | (35,10,0)  | difficult                                  |
| hearth   | h     | hearth            | (45,15,0) | (45,20,0)  | entering = 1d10 fire                       |
| kitchen  | k     | kitchen door      | (45,30,0) | (45,30,0)  | exit → kitchen → side door → stable yard   |
| stairs   | s     | stairs up         | (0,15,0)  | (0,25,10)  | stairs up to landing (z 10)                |
| landing  | l     | upstairs landing  | (0,30,10) | (10,35,10) | 3 ft rail: half cover from below; rooms off it |

## Notes / current state
(none yet)
