---
name: The World
tier: world
type: realm
parent:
tags: []
---

# The World

## Description
Farm country: small villages strung along roads and streams, market towns a few days
apart, and cities somewhere beyond. The realm's name hasn't come up yet. Everything
past Thornbury's fields is unexplored, which means unknown, not empty.

## Frame
origin (0,0,0) = Thornbury's well (the starting area's origin) · +x east · +y north · +z up · mi

## Places
| id        | glyph | feature   | at      | from          | to          | effect                       | ref       | source   |
|-----------|-------|-----------|---------|---------------|-------------|------------------------------|-----------|----------|
| thornbury | T     | Thornbury | (0,0,0) | (-0.1,-0.1,0) | (0.1,0.9,0) | farming village; mill to the N | thornbury | scenario |

## Known, not placed
| id          | feature         | constraints                                                | source      | notes |
|-------------|-----------------|------------------------------------------------------------|-------------|-------|
| market-town | the market town | within 3d of thornbury; has a temple of Chauntea           | player:kael | Kael was sent from its temple to tend Thornbury's shrine |
| river-city  | a river city    | on a navigable river; has a dock district                  | player:kira | Kira grew up running errands for smugglers there |
| the-city    | "the city"      | —                                                          | scenario    | Veskar says he buys grain for it; may be the river city (decide when placed) |

## Frontier
| id       | from      | heading | known as                  | said to lead to | source    | notes |
|----------|-----------|---------|---------------------------|-----------------|-----------|-------|
| east-rd  | thornbury | E       | the east road             | (unknown)       | scenario  | Thornbury sits where it meets the stream |
| west-rd  | thornbury | W       | the west road             | (unknown)       | generated | the other half of the crossroads the inn is named for |
| stream-n | thornbury | N       | the stream path past the mill | (unknown)   | generated | the mill road continues upstream beyond the mill |

## Routes
(none yet — no second place is placed)

## Notes / current state
(none yet)
