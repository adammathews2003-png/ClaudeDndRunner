---
name: The Still Hour
status: active
locations: [kettlebrook, stag-and-kettle, royal-observatory, great-bell-tower, society-chapterhouse, widows-notch, drowned-mint, castle-aloft, glacier-shrine, shackletons-folly, grubbs-cheese-caves]
---

# The Still Hour

## Premise (player-safe)
Midwinter morning in Kettlebrook. The party wake in the Stag & Kettle's loft with a rope
round their ankles, Dolorous Pike shouting in the yard that the pass is open, and a
stranger on the floor who says "Good. It worked, probably." By breakfast of the next
morning, which is the same morning, they know the stranger's name is Phil, that the day
repeats, that they died yesterday and will again, and that a ceremony in the keep's
observatory at nine tonight is what does it. Phil gives them a pebble that glows green,
yellow or red when pointed at a place, a list of four things that might help, and his
regrets. Everything they carry comes with them. Everything else comes back. Sleep is a
reset; so is dying; so is midnight. The passes are shut. The kingdom is eleven miles
across and they have eighteen hours, every day, forever, unless.

## The truth (SPOILERS — GM only)
See campaign.md → Author notes for the whole of it. In brief: the Society of the Still
Hour (Brahe, the Fellows, Ptolemy's skull) perform the Vigil of the Still Star every
night in the Royal Observatory, 21:00–24:00, believing it is the first time. At midnight,
with the Still Star in the great lens and the Great Bell unstruck (the Society sent its
clapper to Castle Aloft on Day -40), the Orrery of Hours folds the day back to 06:00.
Whatever is inside the Orrery's ring at the fold is fixed outside time. The Society stand
outside the ring (Brahe's diagram is mirrored). Phil, hired by Shackleton and running from
Ptolemy's fireball, fell into the ring on the first midnight and has been fixed for
~10,957 loops; he is the Working's anchor and does not know it. He fixed the party by rope
at the last fold before loop 0. Pieces, guardians and uses are below. Whoever is inside
the ring at a fold that is *not* broken becomes the next anchor.

## Factions & relationships
- **The Society of the Still Hour** (Brahe, Tibbs & Pook, Ptolemy, the Wardens, Sergeant Ambry's hired watch) → wants the Vigil completed tonight; fears outsiders in the keep and the bell ringing; will lock doors, hire watches, and in the dome, kill
- **The Crown** (Fitch, Vane, the King off-stage) → wants a quiet Midwinter; fears a scandal; will admit anyone with a signed order and arrest anyone without one. Vane distrusts the Society and can be turned by evidence
- **Phil** → wants the day to end; fears the Star Tower; will do anything except go up it
- **Dame Shackleton** → wants to be proven right about Brahe and to leave; fears nothing, says so; has the Almanac and a grudge; Phil is her unreported hired man
- **Brother Anselm & Toby** → want the Star left alone; have the Mirror; will give it against the Working, never for it
- **Belvedere** → wants nothing moved; has the Clapper; paperwork opens him, theft closes him
- **Clerk Tallow** (dead) → wants the audit balanced; has the Key; a signature or a royal order ends him peacefully
- **Pike, Hob, Marigold, Mother Grubb, Dottie** → the town; each a door into something, none of them know it
- **Gerald** → wants lunch; has the Notch; the kingdom's wall

## The pieces
| piece | where | guardian | how it helps |
|-------|-------|----------|--------------|
| **The King's Key** | drowned-mint/the-vault | Clerk Tallow (ghast) and his court | opens the Star Tower stair, the dome door and the bell tower; three turns at the Orrery's hub (23:30–24:00) unwind the Working |
| **The Clapper of Old Patience** | castle-aloft/the-workshop | Belvedere (gargoyle ×2 + flying sword) or paperwork | seated in Old Patience, lets midnight be struck; a struck midnight breaks the fold |
| **The Almanac of the Still Hour** | shackletons-folly/the-map-room (sea-trunk) | Shackleton (chess, a plan, or the stone) or her wolves | the Vigil's timetable; the chant-break (surprise + Fellows out two rounds); the lens-cover trick; "STEP OUT OF THE RING" |
| **The Mirror of the Still Star** | glacier-shrine/the-cell | Anselm (a cheese and a promise) or Toby and the mephits | in the lens cradle at midnight it reflects the Star; the Orrery over-winds and the Working collapses without a fight |
| **The danger stone ("Gary")** | Phil gives it at loop 1 06:00 | — | a Marchwarden's hazard stone: pointed at a place or told its name, after a minute it glows green (manageable), yellow (hard), red (almost certain death). Places only; never people; it went purple once |

## Beats & triggers  <!-- mirror active ones into state/current.md "Watch for" -->
- WHEN loop 0 begins → the rope; Phil leaves at 06:10 ("Go die, I'll see you at breakfast"); Pike shouts; if the party go, Gerald at 09:00 (widows-notch, fixed); if they do not, the day runs to sleep or any death
- WHEN loop 1 begins → Phil at the foot of the beds with porridge, the stone and the mission (npcs/phil-connery.md → Knowledge); from here the sandbox is open
- WHEN the party point the stone at a place → `gm.py danger <place>`; narrate the colour, never the number
- WHEN the party stop Pike leaving (DC 12 before 06:30, or the stone shown red) → Pike lives today; he drinks with them; Hob is relieved; Marigold writes a verse
- WHEN the party show Shackleton the live stone → attitude friendly; the Almanac; she asks after "a man called Connery"
- WHEN the party lift the hatbox lid (chapterhouse, 06:00–20:30) → Ptolemy talks; the mirrored diagram; the anchor warning at DC 16 or a bribe
- WHEN the party help the Fellows carry coal (07:00–09:00) → a Society pin; the Wardens let pin-wearers pass
- WHEN the party bring Anselm a cheese → the Mirror, with a promise; without one, DC 15; theft → Toby, then the mephits on the shelf
- WHEN the party present paperwork to Belvedere (Brahe's note, a forgery DC 14, a signet) → the Clapper; otherwise "not available"; theft → the Housekeeper's Welcome
- WHEN the party sign Tallow's audit (Hidden DC 15) or show a royal order → the Key handed over with a receipt; otherwise the Audit
- WHEN two pieces are carried → milestone: level-pending 4. WHEN four pieces (or three + a dungeon cleared) → level-pending 5
- WHEN a long rest is attempted → it is sleep; it is a reset (Phil warned them; short rests are fine)
- WHEN any piece is seen by Brahe in the dome → the Vigil becomes the fixed encounter at once
- WHEN a PC is inside the ring at 24:00 and the fold is not broken → that PC is the new anchor (campaign.md → the twist); Phil is released, remembers, and the loop continues
- CLOCK Day 1 06:00: loop start; the party wake in the loft; Phil present (loop 1+)
- CLOCK Day 1 06:30: Pike's sledge bell; he leaves for the Notch with or without the party
- CLOCK Day 1 09:00: Pike at the Notch; 09:15 Gerald, unless prevented
- CLOCK Day 1 09:10: the keep's gate guard sneezes
- CLOCK Day 1 10:00: Shackleton leaves the Folly by dog-sledge; the Folly is empty but for the wolves until 16:00; Toby goes for wood (shrine unguarded until 12:00)
- CLOCK Day 1 11:00: the King receives petitioners in the Great Hall and signs anything (a royal order: the keep gate at any hour; Tallow's audit)
- CLOCK Day 1 12:00: Gerald sleeps until 14:00 (the armory is reachable at DC 15 Stealth)
- CLOCK Day 1 13:00: the Sky Ferry basket comes down to the Spindle station; 13:30 it goes up; the only free ride
- CLOCK Day 1 14:00: the Fellows polish the Orrery in the dome until 16:00 under Vane's eye: the dome is unlocked by day only now (a Mirror can be planted under the dust cover; DC 14 Sleight of Hand with the Fellows present)
- CLOCK Day 1 15:00: Vane questions outsiders in Kettle Square
- CLOCK Day 1 17:00: Fitch hires extra servers for the feast (DC 10): a way inside the walls before the gate shuts
- CLOCK Day 1 20:00: the keep gate shuts; the tower stair and bell tower are arcane-locked
- CLOCK Day 1 20:30: Brahe, the Fellows and the hatbox climb the Star Tower; 21:00 the Vigil begins; the dome door locks
- CLOCK Day 1 22:00: Sergeant Ambry's watch takes post at the bell tower door
- CLOCK Day 1 23:00: a Fellow checks the great lens (finds an undisguised Mirror; the dust cover trick beats this)
- CLOCK Day 1 23:30: the Orrery reaches full spin; the ring glows; the Key can now unwind it (three turns)
- CLOCK Day 2 00:00: the fold (`loop reset --by time`) unless midnight was struck, the Mirror is in the cradle, or the Orrery was unwound. If broken: Day 2 dawns; the campaign ends (Resolution paths)

## Resolution paths
1. **Strike midnight.** Clapper seated in Old Patience (Dottie helps), the tower entered (Key, knock, the ivy and the louvre, or Ambry's watch dealt with from 22:00), the bell swung on the stroke of 24:00. The fold breaks across the whole kingdom; the Orrery over-spins and throws the Society across the dome (Brahe survives, bruised). Day 2: Vane arrests the Society on Shackleton's evidence; Phil sleeps; Pike attempts the pass. No deadly fight needed. **Consequences:** the Society alive and disgraced; Brahe escapes up the chain if not held (sequel hook).
2. **The Mirror.** The Mirror in the lens cradle at midnight (planted 14:00–16:00 under the dust cover, or after the 23:00 check via the balcony or with the Key). The Star looks at itself; the Orrery unwinds itself in a scream of brass; the Working collapses, Ptolemy's binding with it (the skull is at last quiet, and grateful). The Society never know what happened. Day 2: Brahe begins planning "next Midwinter" (sequel hook); Anselm is right; Phil sleeps. **Consequences:** quietest ending; the party may never be believed.
3. **Unwind the Orrery.** Enter the dome during the Vigil (Key or signet or the feast), fight the fixed L5 encounter, and turn the Key three times at the hub from 23:30. The Almanac gives a surprise round and takes the Fellows out of it. The turner must step out of the ring before the last stroke or become the anchor. Done right, the Working dies with the Society watching; Brahe may die, or kneel. **Consequences:** the loudest ending; the Crown owes the party; Phil is released and asks what day it is. If the fold is broken by any path while Phil is alive, he sleeps for the first time in thirty years and wakes on Day 2 an ordinary man with a goat and a straw hat.
