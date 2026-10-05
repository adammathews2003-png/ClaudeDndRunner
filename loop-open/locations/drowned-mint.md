---
name: The Drowned Mint
tier: site
type: dungeon
parent: world
tags: [dungeon, underground, piece]
threat: {xp: 1500, fixed: false}
---

# The Drowned Mint

## Description
The Royal Mint of Branholt stood on Coinwater Spur above the lake until the lake rose
eighty years ago and filled its lower galleries. The counting-house above ground is a
roofless shell full of snow. Below, a stair goes down into galleries where the water
stands waist-deep and black and very cold, lit by nothing. The old Mint never closed its
books: the last Clerk of the Mint, Ambrose Tallow, refused to leave until the audit was
done, and his staff refused to leave him, and none of them has left since. Coins lie in
the water everywhere. They are all the same dead king's face. The air tastes of pennies.

## Areas
- **counting-house** — ground level; roofless; the stair down in the NE corner under a fallen beam
- **the-stair** — 60 steps down into the dark; water from the fortieth step (z -40)
- **flooded-gallery** — a vaulted gallery 120 ft long, water waist-deep (difficult; cold: DC 10 Con per 10 min or 1 exhaustion); side cells; the Tellers' desks under the water
- **press-room** — up three steps and dry; the great coin press; the skeleton minters still working it, slowly, striking nothing
- **the-vault** — through the press-room's iron door (unlocked; it is the Clerk's court); dry; a dais; Tallow's desk; the King's Key on a chain round his neck

## Routes
| id       | from             | to               | via | kind   | access                                      | time | notes                                              |
|----------|------------------|------------------|-----|--------|---------------------------------------------|------|----------------------------------------------------|
| stair    | counting-house   | the-stair        |     | stairs | DC 10 to notice under the beam              | 2m   | ice on the top steps                               |
| gallery  | the-stair        | flooded-gallery  |     | wade   | obvious                                     | 10m  | waist-deep; difficult; cold                        |
| press    | flooded-gallery  | press-room       |     | stairs | obvious                                     | 1m   | three steps up out of the water                    |
| vault    | press-room       | the-vault        |     | door   | obvious; iron door, unlocked, very loud     | 1m   | the Clerk hears it and stands                      |
| drain    | the-vault        | lake-kettle      |     | tunnel | DC 14 to notice; secret; a drain to the lake ice | 15m | a crawl; comes out under the ice shelf 400 ft W   |

## Items & features
- Coins everywhere (gallery): old silver pennies, ~300 sp for an hour's cold wading
- The press (press-room): the die is still set; it strikes the dead king; a lever the skeletons pull in turn
- Tallow's desk (vault): the final audit, open, one line short of balancing; a +1 dagger (uncommon) used as a letter-opener ("the Letter Opener")
- **The King's Key** (vault): a brass key the length of a forearm, sun-shaped bow, on a chain round the ghast Clerk's neck; opens every royal lock in Branholt and fits the Orrery's socket. **Piece 1.**

## Hidden
- DC 12 (flooded-gallery): the water is moving, very slightly, toward the far end: there is a drain somewhere
- DC 13 (press-room): the skeletons pull the lever in strict rotation; they stop and turn if the rotation is broken
- DC 15 (the-vault): the audit is one line short because the King's Key was never signed back in; signing it ("received, by order of the King") makes Tallow sit down

## Encounters
- ENCOUNTER easy "the Tellers": skeleton ×4 (rising from under the water at the desks)
- ENCOUNTER easy "the Drowned": zombie ×3 (in the side cells; drawn by splashing)
- ENCOUNTER hard "the Audit": ghast ×1 (Clerk Ambrose Tallow), ghoul ×1 (his under-clerk), skeleton ×2 (the bailiffs)
<!-- adjusted: 450 + 200 + 100 = 750 × 2 = 1500. Tallow will not fight anyone who signs the audit (Hidden, DC 15) or who
     produces a royal order; he hands the Key over with a receipt and sits down forever. -->

## Loot
| item | kind | rarity | where | guard | random | notes |
|------|------|--------|-------|-------|--------|-------|
| **the King's Key** | campaign | rare | the-vault | the Audit (or sign the audit, DC 15 Hidden; or a royal order) | | Piece 1; on the chain round Tallow's neck; does not count toward item power |
| the Letter Opener (+1 dagger) | treasure | uncommon | the-vault | the Audit | | on Tallow's desk; engraved RECEIVED; it opens any sealed letter without a mark |
| the Clerk's Spectacles | treasure | uncommon | the-vault | DC 13 Investigation (Tallow's drawer) | | *goggles of night* as a pair of pince-nez; the wearer sees the dark "as the dead do," in grey |
| the Tellers' coin (~300 sp) | treasure | — | flooded-gallery | DC 12 Con per 10 min of cold wading | loot-tier-1-4 | one roll per hour; the dead king's face on everything |

## Notes / current state
Phil has been here "a hundred times, maybe. Don't drink the water. Don't sign anything.
Actually, maybe sign something." He got the Key out once and lost it at the Orrery.
