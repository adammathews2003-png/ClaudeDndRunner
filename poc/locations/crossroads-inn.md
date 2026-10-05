---
name: The Crossroads Inn
tier: site
type: building
parent: thornbury
tags: [social, safe]
---

# The Crossroads Inn

## Description
A two-story timber inn at the east end of Thornbury's square, smelling of woodsmoke and
mutton stew. The common room holds eight scarred tables, a long bar along the north wall,
and a hearth that never goes out. Rooms upstairs; kitchen and side door to the stable
yard in back. Evenings it fills with farmhands; by day it's near empty.

## Areas
- **common-room** — front door from the square; the hub. Bar along the north wall, hearth east, stairs up in the west
- **kitchen** — door in the common room's east wall; Mara's domain by day
- **upstairs** — landing above the common room; guest rooms 1–4 (Veskar has room 3)
- **cellar** — beneath the common room (z −10); trapdoor behind the bar, locked (Mara keeps the key on her belt), not obvious (DC 12 Perception)
- **stable-yard** — side door from the kitchen; gate on the south side onto the back lane; Tobin sleeps in the stable loft

## Routes
<!-- In-site ways between areas. Veskar's path with Harl (cellar → kitchen → yard) is the
     scenario's spine, so it's a table, not prose. -->
| id        | from        | to          | via | kind     | access                              | time | notes                                   |
|-----------|-------------|-------------|-----|----------|-------------------------------------|------|-----------------------------------------|
| stairs    | common-room | upstairs    |     | stairs   | obvious                             | 1m   | west wall; creaks on the fourth step    |
| kitchen   | common-room | kitchen     |     | door     | obvious                             | 1m   | east wall, by the hearth                |
| side-door | kitchen     | stable-yard |     | door     | obvious; barred from inside at night | 1m  |                                         |
| trapdoor  | common-room | cellar      |     | trapdoor | locked (Mara); DC 12 to notice      | 1m   | behind the bar; ladder down 10 ft       |
| yard-gate | stable-yard | back lane   |     | gate     | obvious                             | 1m   | → Thornbury route `back-lane`           |

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
<!-- Site frame: kitchen is x 50–65, stable yard x 70–110 (both y 0–35), cellar z −10. Not laid out yet. -->

| id       | glyph | feature           | from      | to         | effect                                     |
|----------|-------|-------------------|-----------|------------|--------------------------------------------|
| door     | d     | front door        | (0,0,0)   | (0,0,0)    | exit → square                              |
| bar      | b     | bar counter       | (15,25,0) | (35,25,0)  | half cover; crossing = difficult           |
| trapdoor | x     | cellar trapdoor   | (25,30,0) | (25,30,0)  | exit → cellar; behind the bar; locked; secret |
| tables-w | t     | tables & benches  | (10,10,0) | (15,15,0)  | difficult                                  |
| tables-e | t     | tables & benches  | (30,5,0)  | (35,10,0)  | difficult                                  |
| hearth   | h     | hearth            | (45,15,0) | (45,20,0)  | entering = 1d10 fire                       |
| kitchen  | k     | kitchen door      | (45,30,0) | (45,30,0)  | exit → kitchen (→ side door → stable-yard) |
| wall-se  | #     | east wall, south  | (45,0,0)  | (45,10,10) | wall                                       |
| wall-ne  | #     | east wall, north  | (45,25,0) | (45,35,10) | wall; kitchen door is the gap              |
| stairs   | s     | stairs up         | (0,15,0)  | (0,25,10)  | stairs up to landing (z 10)                |
| landing  | l     | upstairs landing  | (0,30,10) | (10,35,10) | 3 ft rail: half cover from below; rooms off it |

## Notes / current state
(none yet)
