---
name: The Great Bell Tower
tier: site
type: building
parent: kettlebrook
tags: [town, piece-use]
threat: {xp: 1500, fixed: false}
---

# The Great Bell Tower

## Description
A square stone tower on the north side of Kettle Square, 110 ft tall, with a wooden
belfry at the top that houses Old Patience, a bronze bell the size of a cart that has
rung midnight over Kettlebrook for four hundred years and has not rung since Day -40,
when its clapper went away "for re-tuning." Dottie Varrow, the bell-ringer, still climbs
up every morning and knits beside it, because she is paid to be in the tower and nobody
has told her otherwise. The door at the bottom has a brass plate screwed over the lock.
A spiral stair of 180 steps; a ringing-room with the rope wheels; the belfry above.

## Areas
- **the-door** — ground floor; the arcane-locked door onto the square; a bench and Dottie's boots
- **the-stair** — 180 spiral steps, one slit window every twenty; a ringing-room halfway with the rope wheels (the rope is coiled; nothing to ring)
- **the-belfry** — the top; Old Patience on her yoke, the clapper socket empty; louvres on four sides, one of which opens (Dottie's window: she airs her knitting)

## Routes
| id      | from      | to          | via | kind   | access                                                   | time | notes                                      |
|---------|-----------|-------------|-----|--------|----------------------------------------------------------|------|--------------------------------------------|
| door    | square    | the-door    |     | door   | locked (arcane lock, Society); King's Key; knock; DC 15 Athletics to climb the outside to the belfry louvre | 1m | brass plate over the keyhole |
| stair   | the-door  | the-belfry  |     | stairs | obvious                                                  | 4m   | 180 steps; Dottie hears boots              |

## Items & features
- Old Patience (belfry): the clapper socket takes the Clapper (1 action to seat, 2 people or DC 13 Str); swinging the bell is DC 10 Athletics, 1 action; the stroke is heard across the whole kingdom
- The rope wheels (ringing-room): rope coiled; with the Clapper seated, the bell can also be rung from here (same check)
- Dottie's knitting (belfry): a scarf 40 ft long and growing; she will give it to anyone cold
- Dottie's window (belfry): one louvre opens inward; climbable from outside (DC 15), unlocked by day

## Hidden
- DC 12 (the-door): the brass plate was screwed on by someone who stripped two of the four screws; it would lever off
- DC 14 (the-belfry): the clapper's socket has fresh tool marks, forty days old, and a chalk note inside the bell: "V.B. — tune to the Still Star — I.B."

## Encounters
- ENCOUNTER hard "the tower watch": veteran ×1 (Sergeant Ambry, hired by the Society), guard ×2
<!-- adjusted: 700 + 50 = 750 × 2 = 1500. The watch takes post at the door at 22:00 and climbs at any sound from above. -->
Dottie (commoner) is not an encounter: she shouts, then helps whoever seems kindest.

## Loot
| item | kind | rarity | where | guard | random | notes |
|------|------|--------|-------|-------|--------|-------|
| Dottie's Scarf | treasure | uncommon | the-belfry | Dottie (she gives it to anyone cold; DC 10 Persuasion) | | 40 ft of grey wool; worn, a *cloak of protection* (+1 AC and saves); doubles as 40 ft of silk-strength rope; still growing |
| Dottie's grog flask | consumable | common | the-belfry | — | | one dose = *potion of climbing*; she will not say what is in it |
| the tower watch's purse | treasure | — | the-door | the tower watch | loot-tier-1-4 | Ambry's pay from the Society, in Society-stamped silver |

## Notes / current state
By day the tower is Dottie's. From 22:00 the Society's tower watch stands at the door.
