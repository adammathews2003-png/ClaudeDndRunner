---
name: Bellwether
tier: area
type: settlement
parent: world
tags: [town, hub, festival]
---

# Bellwether

## Description
A walled town of perhaps nine hundred people on the floor of the Caldermont bowl, built
around a market square with a bell tower at its heart. The Keep sits on a rise to the
north, the temple to the west, the Weather Tower leans over the east wall, and the
Sleeping Marmot squats by the South Gate where the caravans used to come in. Trade is
three stalls and a forge: Kettle's Smithy off the square, Agnes Nightingale's apothecary
stall under the green awning, and a snowed-in pedlar's cart in the Marmot's stable yard. Today it
is dressed for Midwinter: bunting stiff with frost, straw effigies on every corner, and
a Winter King's lottery barrel in the square. Snow is piled to the first-floor windows.

Two things a visitor notices and nobody else does. Every shadow in town falls toward the
Keep, whatever the sun is doing. And the hat law: in Caldermont you are what your hat
says you are. Put on a guardsman's helmet and the Guard will salute you and expect you
on the rota; put on a cook's cap and the Keep's kitchens will hand you a ladle; take off
your hat and you are, legally, nobody in particular, which is restful. Nobody thinks
this is odd. It is simply how one knows.

## Hidden
- DC 12: every straw effigy in town is wearing a paper crown, and every paper crown has a little goose drawn on it
- DC 15: the bunting, the snow piles, the frost on the bell: nothing has been disturbed since dawn, every day; no one has shovelled anything
- DC 12: the straw effigies' shadows point at the Keep too, which means every one of them is leaning very slightly, and has been built to

## Frame
origin (0,0,0) = the foot of the Great Bell in the market square · +x east · +y north · +z up · ft

## Places
| id       | glyph | feature                    | at            | from          | to            | effect                                         | ref                  | source   |
|----------|-------|----------------------------|---------------|---------------|---------------|------------------------------------------------|----------------------|----------|
| square   | .     | market square              | (-120,-120,0) | (-120,-120,0) | (120,120,0)   | open ground; bell tower at the center; lottery barrel | market-square    | scenario |
| inn      | I     | The Sleeping Marmot        | (60,-400,0)   | (60,-400,0)   | (170,-330,25) | inn; the party's beds (loft)                   | sleeping-marmot      | scenario |
| keep     | K     | Bellwether Keep            | (-100,900,0)  | (-100,900,0)  | (140,1100,60) | royal keep; Great Hall; the Midwinter ceremony | bellwether-keep      | scenario |
| temple   | t     | Temple of the Hearth       | (-500,0,0)    | (-500,0,0)    | (-430,60,30)  | temple; always a fire going                    | temple-of-the-hearth | scenario |
| wtower   | w     | the Weather Tower          | (560,120,0)   | (560,120,0)   | (600,160,80)  | the Royal Weather-Reader's tower; leans        | weather-tower        | scenario |
| ngate    | n     | North Gate and gate yard   | (-30,1250,0)  | (-30,1250,0)  | (30,1310,25)  | gatehouse; the Bell Road leaves here           | north-gate           | scenario |
| sgate    | s     | South Gate                 |               | (-20,-520,0)  | (20,-480,25)  | gatehouse; the Southgate Pass road, snowed shut beyond | —            | scenario |
| smithy   | f     | Kettle's Smithy            | (160,-60,0)   | (160,-60,0)   | (200,-20,15)  | smith's shop; weapons, armour, skates, crampons | kettle-smithy       | scenario |
| granary  | g     | royal granary              |               | (-220,200,0)  | (-160,260,30) | locked; the sausage cart unloads here          | —                    | scenario |

## Routes
| id         | from   | to          | via                              | kind   | access  | time | notes                                               |
|------------|--------|-------------|----------------------------------|--------|---------|------|-----------------------------------------------------|
| south-st   | square | inn         | (0,-200,0) (60,-380,0)           | street | obvious |      | South Street; the inn's front door faces it         |
| keep-way   | square | keep        | (0,200,0) (0,600,0)              | street | obvious |      | Keep Way, the procession route; climbs the rise to the courtyard gate |
| temple-ln  | square | temple      | (-250,0,0)                       | lane   | obvious |      | Temple Lane                                         |
| smithy-ln  | square | smithy      | (140,-40,0)                      | lane   | obvious |      | the smithy's shutter faces the lane                 |
| tower-ln   | square | wtower      | (300,60,0)                       | lane   | obvious |      | past the smithy to the east wall                    |
| north-st   | square | ngate.street-s | (0,400,0) (-60,800,0) (-30,1200,0) | street | obvious |   | North Street, skirting the keep's west wall         |
| keep-gate-n | keep  | ngate.street-se | (-30,1180,0)                 | street | obvious |      | the short way from the keep's courtyard gate to the gate yard |

## Notes / current state
(none yet)
