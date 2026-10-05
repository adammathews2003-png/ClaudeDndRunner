---
name: Castle Lark
tier: site
type: dungeon
parent: world
tags: [dungeon, flying, piece]
threat: {xp: 2000, fixed: false}
---

# Castle Lark

## Description
A small, beautiful, impossible castle of white stone that flies: four towers, a
gatehouse, a music room with a great round window, all of it drifting in a slow circle
around the kingdom at the height of the peaks, trailing a rope ladder. It was built by
the royal architect Fitz Hawksmoor as a demonstration, rose on its first morning, and
has not come down since. The reason it cannot be steered is the singing: a flock of
harpies has roosted in the music room since Day 1, and their song never ends. Hawksmoor
has barricaded himself in the kitchen tower with a griffon, a great deal of flour, and a
plan. Reached only from Widow's Ridge at 14:00 (world route `ladder`).

## Areas
- **gatehouse** — where the ladder is tied off; a winch; a portcullis rusted open; the wind comes through
- **courtyard** — small, open to the sky; a dry fountain; everything tilts slightly as the castle banks
- **hall-of-portraits** — north range; Hawksmoor's ancestors and two suits of parade armor that salute
- **music-room** — the west tower's top (z 40); the round window; the harpies' roost; the Song
- **kitchen-tower** — the east tower; barricaded (DC 15 to force, or knock and say "pie"); Hawksmoor, the griffon Marchpane, the ovens, and the only quiet room in the castle
- **belfry** — the south tower (z 50); the castle's bell, which the harpies ring for fun; a few stragglers roost here

## Routes
| id         | from       | to                | via | kind   | access                               | time | notes                                      |
|------------|------------|-------------------|-----|--------|--------------------------------------|------|--------------------------------------------|
| gate       | gatehouse  | courtyard         |     | arch   | obvious                              | 1m   |                                            |
| north-door | courtyard  | hall-of-portraits |     | door   | obvious                              | 1m   |                                            |
| west-stair | hall-of-portraits | music-room |     | stairs | obvious; the song gets louder        | 2m   | WIS save DC 11 at the top or stand listening a round |
| east-door  | courtyard  | kitchen-tower     |     | door   | barricaded (DC 15), or the password  | 1m   | Hawksmoor will open it for pie, news, or a plan |
| south-stair | courtyard | belfry            |     | stairs | obvious                              | 2m   |                                            |

## Items & features
- The Song (piece; in the harpies' nest in the music room, among the eggs): a silver-blue stone that hums. Whoever holds it can be heard clearly over any noise, and can make one creature per round stop singing, shouting or cheering (CHA save DC 13); at the ceremony, pressed into the Crown, it silences the hollow crowd and lets the king speak his own words. Once carried, the regenerated copy is `duplicate; hollow` (a silver bead; the harpies keep singing anyway, from habit)
- The helm (gatehouse): a ship's wheel bolted to the floor; turns freely and does nothing while the song plays; with the Song gone, Hawksmoor can steer
- Hawksmoor's plan (kitchen-tower): forty pages of drawings for a pie large enough to tempt a harpy; he has been working on it all day
- Marchpane (kitchen-tower): a griffon, elderly, friendly to anyone Hawksmoor likes, and the castle's only way down besides the ladder (she will carry two, once, to the ridge)
- The bell (belfry): ringing it draws every harpy in the castle to the belfry in two rounds, which is a problem or a plan
- The suggestion box (gatehouse): Hawksmoor's; forty slips, all in his hand, all reading "land"; the newest adds "please"

## Hidden
- DC 12 (courtyard): feathers everywhere, and one goose feather, which is wrong at this altitude
- DC 14 (music-room): the harpies are not singing to lure anyone; they are trying to stop and cannot
- DC 16 (hall-of-portraits): the newest portrait is of Hawksmoor on the day the castle rose, and it is dated Day 1

## Encounters
- ENCOUNTER deadly "the roost": harpy ×n   # n=5 at L3×4 → 2,000 adj; the music room; their song charms (WIS save DC 11) toward the round window, which is open
- ENCOUNTER hard "the belfry stragglers": harpy ×n   # n=3 at L3×4 → 1,200 adj
- ENCOUNTER medium "the saluting armor": animated armor ×n   # n=2 at L3×4 → 600 adj; they attack anyone who fails to return the salute

## Loot
| item | kind | rarity | where | guard | random | notes |
|------|------|--------|-------|-------|--------|-------|
| The Song | campaign | uncommon | music-room | the roost | | in the harpies' nest among the eggs; see Items & features |
| the Griffon Cloak (wings of flying) | treasure | rare | music-room | the roost | | Hawksmoor's cloak of Marchpane's moulted feathers, stolen for the nest; it squawks when it opens and moults in a breeze; the one rare item in the kingdom |
| the castle's second ladder (rope of climbing) | treasure | uncommon | gatehouse | DC 13 Investigation (the winch) | | coiled in the winch housing; climbs on command and sulks if called "rope" |
| the harpies' nest | treasure | — | music-room | the roost | loot-harpy-nest | everything shiny in Caldermont, eventually; roll per visit |
| Hawksmoor's pie | consumable | — | kitchen-tower | — | | a day's rations for eight; a harpy will follow it anywhere |

## Notes / current state
Taking the Song quietly: the nest is reachable by the round window's ledge (Stealth vs the harpies' passive 12, with disadvantage while the song plays unless ears are stopped); or trade with the harpies, who will give it up for silence (a casting of *silence*, or the Morning-After's "right, that's enough"). Hawksmoor's pie plan works, eventually, if the party helps bake (two hours; the harpies come to the kitchen tower and the music room is empty for ten minutes).
