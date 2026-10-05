---
name: Bellwether Keep
tier: site
type: building
parent: bellwether
tags: [royal, ceremony, danger]
threat: {xp: 4400, fixed: true}
---

# Bellwether Keep

## Description
A square grey keep on the rise above town, more manor than fortress, with a walled
courtyard, a chapel wing and a Great Hall whose doors are tall enough for a mounted
procession. Today it is garlanded for Midwinter: holly, straw crowns, two enormous
straw-and-snow effigies (the Winter King and Winter Queen) flanking the dais, and a
pair of empty ceremonial suits of armor standing guard by the throne. King Aldous IV is
in a wonderful mood. The crowning is at 21:00 and the whole town is invited.

## Areas
- **courtyard** — through the gate from Keep Way; the procession ends here; braziers; the kitchen door and the chapel door open onto it
- **great-hall** — the great doors from the courtyard (south); dais and throne at the north end; long tables; a minstrels' gallery along the east wall (z 15); the ceremony site
- **chapel** — small chapel off the courtyard's west side; the Crown of Misrule sits on a velvet stand on the altar between crownings, with two guards at the door
- **kitchens** — door on the courtyard's east side; connects to the Great Hall by a service door behind the dais
- **gallery** — minstrels' gallery over the Great Hall (z 15); reached by a stair from the kitchens
- **cellars** — under the kitchens (z −10); a bricked-up arch at the back is colder than it should be (DC 14 to notice)

## Routes
| id          | from       | to         | via | kind   | access                           | time | notes                                        |
|-------------|------------|------------|-----|--------|----------------------------------|------|----------------------------------------------|
| great-doors | courtyard  | great-hall |     | door   | obvious; shut 21:00–00:00 from inside | 1m | barred by the Court once the crowning begins |
| chapel-door | courtyard  | chapel     |     | door   | guarded (2 guards, 06:00–20:40)  | 1m   |                                              |
| kitchen-door | courtyard | kitchens   |     | door   | obvious                          | 1m   | cooks everywhere                             |
| service     | kitchens   | great-hall |     | door   | DC 12 to notice                  | 1m   | behind the dais tapestry                     |
| gallery-st  | kitchens   | gallery    |     | stairs | obvious                          | 1m   | the musicians' stair                         |
| cellar-st   | kitchens   | cellars    |     | stairs | obvious                          | 1m   |                                              |

## Items & features
- The Crown of Misrule (chapel, 06:00–20:45; on the king's head after 21:00): a circlet of black iron and holly leaves with five settings, four of them empty; one setting holds a dull chip of something grey. Warm to the touch. If carried off, it slips away at 20:45 ("like a cat getting down") and is on its stand at 20:46
- The lottery barrel's twin (great-hall): the straw drawn at 10:00 is displayed on the dais; it is always the long one
- The Winter King's throne (dais): a plain chair with a straw cushion; a goose-shaped dent in the cushion
- The effigies (dais, 06:00–21:00): the Winter King and Winter Queen in straw and packed snow, each 9 ft tall; the Queen's face is painted smiling. Inert until the crowning
- The Knights of Nothing (dais flanks): two empty suits of parade armor holding wooden cups. Inert until the crowning. A page refills the cups every hour and is paid for it; the cups are always full
- The hat rail (kitchens): cooks' caps on pegs by the door; anyone wearing one is a cook, by law, and will be handed a ladle and a job

## Hidden
- DC 13 (great-hall): the Queen effigy's painted eyes are following people around
- DC 15 (chapel): the four empty settings in the Crown have faint colour left in them: amber, red, grey, silver-blue
- DC 14 (cellars): a draught of glacier-cold air through the bricked arch; the Hollow Glacier's caves come this far south

## Encounters
- ENCOUNTER fixed L5 deadly "the Court of Misrule": flesh golem ×1 (the Queen of Misrule), animated armor ×2 (the Knights of Nothing)   # 21:00–00:00 only; adj 4,400; never rescaled; pieces remove parts of it (scenario)
- ENCOUNTER medium "the chapel guard": guard ×n, veteran   # if the party forces the chapel before 20:40
- ENCOUNTER medium "the kitchen alarm": guard ×n   # if the party is caught in the kitchens without a reason or a cook's cap; the cooks throw things first

## Loot
| item | kind | rarity | where | guard | random | notes |
|------|------|--------|-------|-------|--------|-------|
| the Crown of Misrule | campaign | very rare | chapel | the Court of Misrule | | on its stand 06:00–20:45, on the king's head from 21:00; cannot be kept: it gets down like a cat at 20:45 |
| the Knight's gauntlets (gauntlets of ogre power) | treasure | uncommon | great-hall | the Court of Misrule | | from a Knight of Nothing once it falls or stands down; empty, and they still grip; they applaud on their own at speeches |
| the royal indigestion cordials ×2 (potion of healing) | consumable | common | kitchens | DC 12 Sleight of Hand or DC 13 Persuasion (the cooks) | | kept on the kitchen shelf for the King |
| the King's purse | treasure | — | great-hall | DC 15 Persuasion (the King) | loot-tier-1-4 | "my dear fellow", for any service; the same purse every loop, which is a living |

## Layout
### great-hall
Bounds: x 0–80 · y 0–100 · z 0–30 · origin (0,0,0) = inside the great doors, SW corner · +x east · +y north · +z up · ft

| id         | glyph | feature                | from       | to          | effect                                                        |
|------------|-------|------------------------|------------|-------------|---------------------------------------------------------------|
| doors      | d     | great doors            | (35,0,0)   | (45,0,0)    | door; closed and barred 21:00–00:00; exit → courtyard         |
| wall-w     | #     | west wall              | (0,0,0)    | (0,100,30)  | wall                                                          |
| wall-e     | #     | east wall              | (80,0,0)   | (80,100,30) | wall; gallery above                                           |
| dais       | =     | dais                   | (10,85,0)  | (70,100,5)  | raised 5 ft; steps along the south edge                       |
| throne     | T     | the Winter King's throne | (40,95,5) | (40,95,5)   | the king sits here from 21:00                                 |
| service    | d     | service door           | (75,100,5) | (75,100,5)  | door; behind the tapestry; exit → kitchens; DC 12 to notice   |
| table-w    | t     | long table, west       | (10,20,0)  | (15,75,0)   | difficult; half cover if overturned                           |
| table-e    | t     | long table, east       | (65,20,0)  | (70,75,0)   | difficult; half cover if overturned                           |
| hearth     | h     | great hearth           | (0,45,0)   | (0,55,0)    | entering = 1d10 fire                                          |
| crowd      | :     | the hollow crowd       | (20,10,0)  | (60,80,0)   | difficult (packed townsfolk, cheering; they do not get out of the way) |
| gallery    | g     | minstrels' gallery     | (70,20,15) | (80,80,15)  | 4 ft rail: half cover from below; stair from kitchens         |
| pillar-w   | #     | pillar                 | (20,50,0)  | (20,50,30)  | wall                                                          |
| pillar-e   | #     | pillar                 | (60,50,0)  | (60,50,30)  | wall                                                          |

## Notes / current state
Sidekick clause (Pim): the kitchens are Midwinter chaos, but the cooks know the Marmot's
boot-boy, who ran their sausages last year; with Pim along (in his cook's cap) they wave
him and "his friends" through to the service door behind the dais tapestry, no check,
any time before 20:50. Without him: DC 15 Persuasion with the head cook (busy, furious)
or DC 13 group Stealth through the steam; a failure is "the kitchen alarm" (ENCOUNTER
above) and the half hour it takes to talk Bergmann down. Ysolde can tell the party the
door exists; only Pim gets them through the kitchens quietly. A cook's cap bought at the
hat stall also works, once, until someone asks what you are cooking.
