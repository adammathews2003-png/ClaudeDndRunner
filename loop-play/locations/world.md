---
name: The Kingdom of Caldermont
tier: world
type: realm
parent:
tags: [mountain, snowed-in]
---

# The Kingdom of Caldermont

## Description
A kingdom the size of a large valley: one town, one keep, one monastery, a frozen lake,
a glacier, and three passes that are all snowed shut since the night of Day 0. The whole
of it fits inside a bowl of peaks a few miles across. Everything beyond the passes is
rumour until spring. A castle has been seen in the sky, circling, for as long as anyone
can remember this morning. Letters go by marmot: the post-marmots tunnel under the snow
between every door in the kingdom, and nobody finds this strange. In Caldermont you are
what your hat says you are, and the law agrees.

## Frame
origin (0,0,0) = the foot of the Great Bell in Bellwether's market square (the starting area's origin) · +x east · +y north · +z up · mi

## Places
| id             | glyph | feature                      | at            | from            | to             | effect                                                        | ref             | source   |
|----------------|-------|------------------------------|---------------|-----------------|----------------|---------------------------------------------------------------|-----------------|----------|
| bellwether     | B     | Bellwether, the capital      | (0,0,0)       | (-0.3,-0.3,0)   | (0.3,0.35,0)   | walled town; keep on the north rise; Midwinter today          | bellwether      | scenario |
| monastery      | b     | Monastery of the Patient Brewers | (-2.5,-1.4,0.2) | (-2.6,-1.5,0.2) | (-2.4,-1.3,0.2) | brewery-monastery on the south-west slope; famous ale     | patient-brewers | scenario |
| lake-vellum    | ~     | Lake Vellum                  | (4,1,-0.05)   | (3.4,0.4,-0.05) | (4.6,1.6,-0.05) | frozen lake; pipes heard from the lake-wood                  | lake-vellum     | scenario |
| glacier-mouth  | G     | the Hollow Glacier's mouth   | (0.5,3,0.4)   | (0.4,2.9,0.4)   | (0.7,3.2,0.6)  | ice cave mouth at the glacier's foot; groans heard from inside | hollow-glacier  | scenario |
| widows-ridge   | ^     | Widow's Ridge signal tower   | (3,4,0.5)     | (2.9,3.9,0.5)   | (3.1,4.1,0.55) | old signal tower on a bare ridge                               | widows-ridge    | scenario |
| castle-lark    | C     | Castle Lark (in the sky)     | (3,4.05,0.56) | (2.95,4,0.55)   | (3.05,4.1,0.6) | flying castle; circles the kingdom; lowest over the ridge about two in the afternoon | castle-lark | scenario |

## Known, not placed
| id          | feature                      | constraints                        | source    | notes                                                        |
|-------------|------------------------------|------------------------------------|-----------|--------------------------------------------------------------|
| hobs-rest   | Hob's Rest, the pass waystation | S of bellwether; within 4 mi of bellwether | scenario | snowed under; the caravan that turned back sheltered there; rumor; may be false that anyone is still inside |
| high-shrine | the High Shrine of the First Winter King | beyond 4 mi from bellwether; N of bellwether | generated | hermit said to keep it; rumor; may be false |

## Frontier
| id          | from       | heading | known as             | said to lead to        | source   | notes                                      |
|-------------|------------|---------|----------------------|------------------------|----------|--------------------------------------------|
| southgate   | bellwether | S       | the Southgate Pass   | the lowlands           | scenario | the party came in this way; snowed shut (unreachable today) |
| needle-pass | lake-vellum | E      | the Needle Pass      | the eastern duchies    | scenario | snowed shut (unreachable today)            |
| serpent-stair | monastery | W      | the Serpent's Stair  | the western valleys    | scenario | snowed shut (unreachable today)            |

## Routes
| id           | from          | to            | via                              | kind   | access  | time | notes                                                     |
|--------------|---------------|---------------|----------------------------------|--------|---------|------|-----------------------------------------------------------|
| bell-rd      | bellwether    | glacier-mouth | (0.2,1.5,0.1) (0.4,2.4,0.3)      | road   | obvious |      | the Bell Road north from the North Gate; wolf tracks at dawn; tables/encounters-bell-road.md |
| brewers-trk  | bellwether    | monastery     | (-1.2,-0.8,0.1)                  | road   | obvious |      | the Brewers' Track; sled-ruts; the sausage cart's route    |
| lake-rd      | bellwether    | lake-vellum   | (2,0.4,0)                        | road   | obvious |      | the Lake Road east; tables/encounters-lake-road.md         |
| ridge-trail  | glacier-mouth | widows-ridge  | (1.8,3.8,0.5)                    | trail  | obvious |      | switchbacks above the glacier; exposed                     |
| lake-climb   | lake-vellum   | widows-ridge  | (3.6,2.8,0.3)                    | trail  | DC 12 to notice |  | goat path up from the lake-wood                         |
| ladder       | widows-ridge  | castle-lark   |                                  | ladder | obvious; only 14:00–14:10 | 2m | a rope ladder dangles from the castle as it passes the tower roof |

## Notes / current state
(none yet)
