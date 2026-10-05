---
name: The Society's Chapterhouse
tier: site
type: building
parent: kettlebrook
tags: [town, society, heist]
threat: {xp: 900, fixed: false}
---

# The Society's Chapterhouse

## Description
A narrow four-storey townhouse jammed under the keep wall, every window lit blue by
alchemical lamps, a brass star-in-a-circle on the door. The Society of the Still Hour
has owned it for three hundred years and never thrown anything away. The hall is lined
with two suits of ceremonial brass armor that turn their heads. Upstairs: the Fellows'
dormitory (two beds, one telescope, many socks), Brahe's study (a hatbox on the desk,
which talks), and a workroom full of instruments that all read backwards.

## Areas
- **the-hall** — front door from the lane; the Brass Wardens; stairs up
- **the-dormitory** — first floor; Fellows Tibbs and Pook; a window onto the keep wall
- **the-study** — second floor; Brahe's desk, the hatbox, the working diagram's master copy, a cabinet of spare brass noses
- **the-workroom** — third floor; instruments; a cold-cabinet labelled MEDICAL

## Routes
| id      | from      | to            | via | kind   | access                                  | time | notes                               |
|---------|-----------|---------------|-----|--------|-----------------------------------------|------|-------------------------------------|
| door    | lane      | the-hall      |     | door   | locked (Fellows have keys; DC 13 Thieves' Tools); open 07:00–09:00 and 18:00–20:00 when Fellows come and go | 1m | the brass star knocker |
| stairs  | the-hall  | the-study     |     | stairs | obvious; past the dormitory             | 2m   | the Wardens watch the stairs        |
| ladder  | the-study | the-workroom  |     | ladder | obvious                                 | 1m   |                                     |

## Items & features
- The Brass Wardens (hall): two suits of animated armor; they let in anyone wearing a Society pin or carrying a signet, and stop everyone else, politely at first
- The hatbox (study): Grandmaster Ptolemy, 06:00–20:30 (npcs/ptolemy.md); he will talk to anyone who lifts the lid
- The master diagram (study): the Working, drawn mirrored; a signed note from Brahe to Vexilla Bombast about "the bell's tongue" (proof the Society took the Clapper)
- Brahe's spare signet (study desk drawer, DC 12 Thieves' Tools): passes the keep gate after 20:00 as "Society business" and opens the Star Tower stair door
- The MEDICAL cabinet (workroom): potion of healing ×3; a bottle labelled "NOSE POLISH"

## Hidden
- DC 12 (the-hall): the Wardens' visors track movement; they are not decorative
- DC 14 (the-study): the diagram's lettering reads correctly in the polished bridge of a spare brass nose
- DC 15 (the-workroom): a ledger of payments to "Sgt. Ambry, for the tower, 22:00 to midnight"

## Encounters
- ENCOUNTER hard "the Brass Wardens": animated armor ×2, flying sword ×1 (from over the mantel)
<!-- adjusted: 400 + 50 = 450 × 2 = 900 -->
The Fellows (commoners) are not an encounter: Tibbs and Pook shriek and run for Brahe; cornered, they surrender and apologise.

## Loot
| item | kind | rarity | where | guard | random | notes |
|------|------|--------|-------|-------|--------|-------|
| the Spare Nose | treasure | uncommon | the-study | the Brass Wardens | | a brass nose on a ribbon; worn, it is *eyes of the eagle* (advantage on sight-based Perception); it polishes itself and sneezes at 09:10 |
| Brahe's spare signet | campaign | — | the-study | DC 12 Thieves' Tools (desk drawer) | | passes the keep gate after 20:00; opens the Star Tower stair; Belvedere accepts it as paperwork |
| potion of healing ×3 | consumable | common | the-workroom | the Brass Wardens | | the MEDICAL cabinet; the NOSE POLISH is not a potion |
| the Society's ledger and Brahe's note to Vexilla | campaign | — | the-workroom | DC 15 Investigation | | evidence for Vane; the note is paperwork for Belvedere |

## Notes / current state
Brahe is here 06:00–07:00 and 12:00–20:30; the Fellows 06:00–07:00, 09:00–12:00 and 18:00–20:30.
