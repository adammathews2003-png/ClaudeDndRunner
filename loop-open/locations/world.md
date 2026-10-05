---
name: The Kingdom of Branholt
tier: world
type: realm
parent:
tags: [mountain, snowed-in]
---

# The Kingdom of Branholt

## Description
A bowl of high valleys ringed by peaks, the frozen Lake Kettle at its floor and the capital,
Kettlebrook, on the lake's east shore. Small enough to cross in a day; this winter nobody
can leave at all: Widow's Notch, Thrain's Gate and the north col are under twenty feet of
snow. Over the lake, on a chain moored to the Spindle, hangs the castle of the archmage
Vexilla Bombast, said to be away. Beyond the passes is unknown this winter: unreachable, not empty.

## Frame
origin (0,0,0) = Kettlebrook's market cross (the starting area's origin) · +x east · +y north · +z up · mi

## Places
| id                | glyph | feature                       | at               | from              | to               | effect                                        | ref                | source   |
|-------------------|-------|-------------------------------|------------------|-------------------|------------------|-----------------------------------------------|--------------------|----------|
| kettlebrook       | K     | Kettlebrook, the capital      | (0,0,0)          | (-0.3,-0.3,0)     | (0.3,0.3,0)      | walled town on the lake's east shore          | kettlebrook        | scenario |
| lake-kettle       | ~     | Lake Kettle, frozen           |                  | (-5,-2,0)         | (-0.3,2,0)       | open ice; groans; safe except where marked    | —                  | scenario |
| shackletons-folly | F     | Shackleton's Folly            | (-1.5,0.4,0)     | (-1.5,0.4,0)      | (-1.45,0.45,0)   | stone tower built on the ice; dog kennels     | shackletons-folly  | scenario |
| the-spindle       | ^     | the Spindle                   |                  | (-4.6,1.1,0)      | (-4.4,1.3,0.3)   | rock pinnacle on the west shore; ferry station at the top; the castle's chain | — | scenario |
| castle-aloft      | C     | Castle Aloft                  | (-3.5,1.0,0.4)   | (-3.6,0.9,0.4)    | (-3.4,1.1,0.45)  | flying castle, hovering 2,000 ft over the ice | castle-aloft       | scenario |
| drowned-mint      | M     | the Drowned Mint              | (2.0,1.5,0.1)    | (2.0,1.5,0.1)     | (2.05,1.55,0.1)  | ruined mint on Coinwater Spur; galleries below | drowned-mint      | scenario |
| grubbs-caves      | g     | Mother Grubb's Cheese Caves   | (1.5,-1.2,0.1)   | (1.5,-1.2,0.1)    | (1.55,-1.15,0.1) | cheese caves in Goat Hollow                   | grubbs-cheese-caves | scenario |
| glacier-shrine    | S     | the Glacier Shrine            | (0.5,4.0,0.8)    | (0.5,4.0,0.8)     | (0.55,4.05,0.8)  | hermitage on Hermit's Shoulder, under the glacier | glacier-shrine | scenario |
| widows-notch      | N     | Widow's Notch tollhouse       | (-1.0,-6.0,0.7)  | (-1.0,-6.0,0.7)   | (-0.95,-5.95,0.7) | the last building before the south pass      | widows-notch       | scenario |

## Known, not placed
| id            | feature                    | constraints                          | source   | notes                                                       |
|---------------|----------------------------|--------------------------------------|----------|-------------------------------------------------------------|
| dunmarrow     | Dunmarrow, a lowland city  | beyond 1d from widows-notch; S of widows-notch | scenario | where Pike's cheese is due and the party's pay waits   |
| warden-lodge  | the old Marchwarden lodge  | within 4 mi of kettlebrook; N of kettlebrook | scenario | rumor; the kingdom's defunct ranger corps kept hazard stones there; may be false |
| geralds-larder | "the yeti's larder"       | within 1 mi of widows-notch          | scenario | rumor from Phil; a cave above the Notch; may be false       |

## Frontier
| id         | from           | heading | known as         | said to lead to | source   | notes                                          |
|------------|----------------|---------|------------------|-----------------|----------|------------------------------------------------|
| south-pass | widows-notch   | S       | the south pass   | dunmarrow       | scenario | snowed shut; impassable today                  |
| east-pass  | kettlebrook    | E       | Thrain's Gate    | (unknown)       | scenario | snowed shut; the road ends in a drift 9 mi out |
| north-col  | glacier-shrine | N       | the north col    | (unknown)       | scenario | glacier; nobody has crossed it in living memory |

## Routes
| id         | from        | to                | via                                  | kind      | access  | time | notes                                                        |
|------------|-------------|-------------------|--------------------------------------|-----------|---------|------|--------------------------------------------------------------|
| coin-road  | kettlebrook | drowned-mint      | (0.4,0.3,0) (1.2,1.0,0.05)           | road      | obvious |      | the old mint road; cleared to the Spur; tables/encounters-coin-road.md |
| hollow-lane | kettlebrook | grubbs-caves     | (0.3,-0.3,0) (1.0,-0.9,0.05)         | lane      | obvious |      | Mother Grubb's cart keeps it open                            |
| lake-ice   | kettlebrook | shackletons-folly | (-0.3,0.1,0) (-0.9,0.3,0)            | trackless | obvious |      | across the ice from the lake stair; tables/encounters-lake-ice.md |
| shore-road | kettlebrook | the-spindle       | (-0.3,0.3,0) (-2.0,1.8,0) (-4.0,1.6,0) | road    | obvious |      | the north-shore road; the Spindle's stair at its end         |
| spindle-stair | the-spindle | the-spindle    |                                      | trail     | obvious | 40m  | 300 ft of cut steps to the ferry station; icy               |
| sky-ferry  | the-spindle | castle-aloft      |                                      | chain     | obvious | 20m  | winched basket on the mooring chain; runs 13:00 down, 13:30 up; or climb the chain (DC 15 Athletics ×4, 2,000 ft) |
| high-trail | kettlebrook | glacier-shrine    | (0.2,0.5,0.05) (0.3,2.0,0.3) (0.6,3.2,0.6) | trail | obvious |    | switchbacks; above the tree line by the second mile          |
| notch-road | kettlebrook | widows-notch      | (-0.2,-0.4,0) (-0.6,-2.5,0.2) (-0.9,-4.8,0.5) | road | obvious |    | the south road; a sledge can take it; Pike leaves 06:30     |

## Notes / current state
