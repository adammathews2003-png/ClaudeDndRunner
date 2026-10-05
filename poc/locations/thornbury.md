---
name: Thornbury
tier: area
type: settlement
parent: world
tags: [village]
---

# Thornbury

## Description
A farming village of about two hundred souls where the east road meets a stream. A
dozen buildings ring a packed-dirt square with a dry stone well at its center. North of
the square, the mill road follows the stream for most of a mile, through willow and
hedgerow, to Harl's watermill. Beyond the last houses it's fields in every direction.

## Hidden
(none yet)

## Frame
origin (0,0,0) = the well at the center of the square · +x east · +y north · +z up · ft

## Places
| id     | glyph | feature            | at           | from         | to           | effect                               | ref            | source   |
|--------|-------|--------------------|--------------|--------------|--------------|--------------------------------------|----------------|----------|
| square | .     | village square     | (-60,-60,0)  | (-60,-60,0)  | (60,60,0)    | open ground; well at the center      | village-square | scenario |
| inn    | I     | Crossroads Inn     | (65,-20,0)   | (65,-20,0)   | (175,15,20)  | building + kitchen + stable yard (E) | crossroads-inn | scenario |
| reeve  | R     | reeve's house      |              | (-100,-15,0) | (-70,15,20)  | slate roof; not yet detailed         | —              | scenario |
| smithy | f     | smithy             |              | (-55,70,0)   | (-25,95,15)  | not yet detailed                     | —              | scenario |
| shrine | c     | shrine of Chauntea |              | (-15,-90,0)  | (15,-70,15)  | candle-lit, tended daily             | —              | scenario |
| mill   | M     | Harl's watermill   | (-20,4400,0) | (-20,4400,0) | (20,4440,25) | astride the stream                   | old-mill       | scenario |

## Routes
| id       | from   | to       | via                                  | kind | access  | time | notes                                         |
|----------|--------|----------|--------------------------------------|------|---------|------|-----------------------------------------------|
| inn-door | square | inn.door |                                      | door | obvious |      | the inn's front door, east side of the square |
| back-lane | square | inn      | (60,-25,0) (155,-25,0)               | lane | obvious |      | along the inn's south wall to the stable-yard gate |
| reeve-path | square | reeve  |                                      | path | obvious |      |                                               |
| mill-rd  | square | mill     | (0,60,0) (150,1500,0) (-100,3000,0)  | road | obvious |      | follows the stream north; nobody walks it after dark |

## Notes / current state
(none yet)
