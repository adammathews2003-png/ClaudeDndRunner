---
name: Kettlebrook
tier: area
type: settlement
parent: world
tags: [town, capital, hub]
---

# Kettlebrook

## Description
A walled town of perhaps two thousand, stacked up the east shore of Lake Kettle in
slate-roofed terraces, every chimney smoking. Kettle Square sits at the middle with the
market cross at its center and the Great Bell tower (Old Patience) on its north side,
silent since autumn. Above the town, on a shelf of rock, Kettle Keep's grey walls and the
tall thin Star Tower at its corner, with the brass dome of the Royal Observatory on top.
Midwinter bunting everywhere, frozen stiff. Snow shovelled into ramparts along every
street. The town smells of woodsmoke, wet wool and, faintly, cheese.

## Hidden
- DC 12 (square): the bell tower's door has a new brass plate screwed over the keyhole: "CLOSED FOR REPAIRS BY ORDER OF THE ASTRONOMER-ROYAL"
- DC 15 (square): the keep's gate guard sneezes at exactly 09:10, every day

## Frame
origin (0,0,0) = the market cross in Kettle Square · +x east · +y north · +z up · ft

## Places
| id            | glyph | feature                    | at              | from            | to               | effect                                                | ref                  | source   |
|---------------|-------|----------------------------|-----------------|-----------------|------------------|-------------------------------------------------------|----------------------|----------|
| square        | .     | Kettle Square              | (-80,-80,0)     | (-80,-80,0)     | (80,80,0)        | open ground; market cross at the center               | —                    | scenario |
| inn           | I     | the Stag & Kettle          | (90,-40,0)      | (90,-40,0)      | (200,20,30)      | inn, loft, stable yard behind                         | stag-and-kettle      | scenario |
| bell-tower    | B     | the Great Bell tower       | (-20,90,0)      | (-20,90,0)      | (20,130,110)     | stone tower, 110 ft; bell at the top                  | great-bell-tower     | scenario |
| keep          | #     | Kettle Keep                |                 | (-260,300,0)    | (140,700,60)     | walled; one gate on the S side; closed 20:00–06:00    | —                    | scenario |
| observatory   | O     | the Royal Observatory      | (100,600,120)   | (100,600,120)   | (160,660,150)    | brass dome atop the Star Tower (keep's NE corner)     | royal-observatory    | scenario |
| chapterhouse  | H     | the Society's chapterhouse | (-140,180,0)    | (-140,180,0)    | (-100,230,35)    | narrow townhouse under the keep wall                  | society-chapterhouse | scenario |
| temple        | c     | temple of St Oswin of the Thaw |             | (-200,-60,0)    | (-120,0,40)      | candle-lit; Father Lucan; not yet detailed            | —                    | scenario |
| market-hall   | m     | the market hall            |                 | (-80,-200,0)    | (80,-140,25)     | Midwinter market; cheese, wool, hot wine; Quist's curiosities stall 09:00–17:00 (npcs/wendel-quist.md) | — | scenario |
| menagerie     | w     | the Royal Menagerie        |                 | (200,300,0)     | (260,360,20)     | one owlbear (the Duchess), asleep; not yet detailed   | —                    | scenario |
| armoury       | A     | Brask & Daughter, Arms     |                 | (40,-130,0)     | (90,-90,20)      | forge and shop; SET merchant (npcs/ottoline-brask.md), 08:00–18:00 | — | scenario |
| apothecary    | a     | Lind's Remedies            |                 | (-120,20,0)     | (-90,60,25)      | shop; RANDOM-ISH merchant (npcs/hespera-lind.md), 07:00–19:00 | — | scenario |
| lake-stair    | =     | the lake stair             |                 | (-300,0,0)      | (-280,20,0)      | steps down to the ice; W edge of town                 | —                    | scenario |
| south-gate    | v     | the south gate             |                 | (-10,-1560,0)   | (10,-1540,25)    | the Notch road leaves here                            | —                    | scenario |
| coin-gate     | >     | the Coin Gate              |                 | (1540,300,0)    | (1560,320,25)    | NE gate; the mint road leaves here                    | —                    | scenario |

## Routes
| id            | from       | to                 | via                        | kind   | access                                           | time | notes                                                       |
|---------------|------------|--------------------|----------------------------|--------|--------------------------------------------------|------|-------------------------------------------------------------|
| inn-door      | square     | inn.door           |                            | door   | obvious                                          |      | the inn's front door faces the square                       |
| tower-door    | square     | bell-tower.door    |                            | door   | locked (arcane lock, Society; the King's Key opens it; DC 15 climb outside) |  | brass plate over the keyhole |
| keep-street   | square     | keep               | (0,100,0) (-60,290,0)      | street | obvious; gate guarded (Vane); shut 20:00–06:00   |      | Keep Street climbs to the gate                              |
| star-stair    | keep       | observatory.door   |                            | stairs | locked (Society; King's Key or Brahe's signet)   | 8m   | 300 steps inside the Star Tower                             |
| house-lane    | square     | chapterhouse       | (-100,100,0)               | lane   | obvious                                          |      | Fellows come and go                                         |
| temple-path   | square     | temple             |                            | path   | obvious                                          |      |                                                             |
| market-street | square     | market-hall        |                            | street | obvious                                          |      |                                                             |
| forge-lane    | square     | armoury            | (60,-85,0)                 | lane   | obvious                                          |      | follow the hammering                                        |
| shop-door     | square     | apothecary         |                            | door   | obvious; shuttered 19:00–07:00                   |      | west side of the square; a lamp upstairs at night           |
| stair-street  | square     | lake-stair         | (-200,10,0)                | street | obvious                                          |      | → world route `lake-ice`, `shore-road`                      |
| south-street  | square     | south-gate         | (0,-400,0) (-5,-1000,0)    | street | obvious                                          |      | → world route `notch-road`                                  |
| coin-street   | square     | coin-gate          | (400,100,0) (1000,250,0)   | street | obvious                                          |      | → world routes `coin-road`, `hollow-lane`                   |

## Notes / current state
(none yet)
