# Combat Basics (table reference)

## Sequence
1. Determine surprise (unaware → surprised, no action/reaction on first turn).
   **House rule — Opening strike:** whoever starts the fight against someone not braced for
   it resolves that first action *before* initiative; see `house-rules.md`.
2. Roll initiative: d20 + DEX mod, once for the whole fight. GM may group identical monsters.
   PC/NPC ties → PC first.

**House rule — ties go to the player:** an NPC attack roll that exactly equals a PC's AC
misses (RAW: hits). See `house-rules.md`.
3. Rounds (~6 seconds each): everyone acts in initiative order until combat ends.

## On your turn
- **Move** up to your speed (splittable around your action).
- **Action(s) and Bonus Action(s):** normally one action and, if something grants one,
  one bonus action. Class features, level and other effects can change this (Action
  Surge gives an extra action; Extra Attack adds attacks to the Attack action; Cunning
  Action or a spell can grant bonus actions). Check the PC's features.
  - *Actions:* Attack, Cast a Spell, Dash, Disengage, Dodge, Help, Hide, Ready, Search,
    Use an Object, or an action a feature grants.
  - *Bonus actions:* only what a feature, spell or item names as one (off-hand attack
    with two light weapons, Cunning Action, *healing word*, Rage, …). There is no
    bonus action without such a source.
- **Reaction:** one per round (e.g., an opportunity attack when an enemy leaves your
  reach without Disengaging, or a reaction spell such as *shield*).
- Free: interact with one object (draw a sword, open a door), brief speech.

## Attacks
Attack roll: d20 + ability mod + proficiency vs. target AC. Natural 20 = crit (double
the damage dice); natural 1 = miss. Melee uses STR (DEX for finesse weapons); ranged
uses DEX. Ranged attacks in melee reach of an enemy: disadvantage. Unseen attacker:
advantage; attacking an unseen target: disadvantage.

## Cover
Half cover +2 AC/DEX saves · three-quarters +5 · total cover: untargetable.

## Positions & distance (house model — see docs/design/02, Spatial model)
- Space is a grid of 5-ft cells. A position `(x,y,z)` in feet, multiples of 5, names a
  **cell center**. +z is up.
- **Distance = max(|dx|, |dy|, |dz|).** (5e grid rule: diagonals cost 5 ft, extended to 3D.)
- Large+ creatures: `pos` = their lowest-x/y/z cell + size (Large 2×2, Huge 3×3,
  Gargantuan 4×4 cells). Distance to them = to their nearest cell.
- Reach: melee ≤ 5 ft (≤ 10 with reach). Ranged: ≤ normal range fine; ≤ long range at
  disadvantage; any hostile within 5 ft of the attacker → disadvantage.
- **Opportunity attack:** mover starts a step within an enemy's reach and ends it outside.
- **Walls** (terrain `effect` says *wall*) can't be entered or seen through: total cover,
  and areas of effect stop at them. A *door* row is the gap; *closed* or *locked* on it
  blocks movement until opened. A room with one laid-out area may rely on its Bounds
  instead.

## Movement costs
- 1 ft of speed per ft moved; **difficult terrain, climbing, swimming, crawling ×2**
  (no ×2 for climbing/swimming with that speed). Standing from prone: half speed.
- Stairs and ramps (terrain `effect` says so) = normal movement up or down. Any other
  rise (ladder, wall, bar top) = climbing; any other drop = a jump or a fall.
- Long jump: STR score in ft with a 10-ft run-up (half from standing). High jump:
  3 + STR mod ft (half standing). Every foot jumped costs movement.
- **Falling:** 1d6 bludgeoning per 10 ft fallen (max 20d6), land prone.

## Areas of effect
Every area has a **point of origin** and is tested against the **center of each cell** a
creature occupies (a creature is hit if any of its cells is in).

- **Sphere / cylinder / cube (radius or half-side r) from a point:** the origin is a grid
  *intersection* (coordinates ending in .5, e.g. `(22.5, 12.5, 0)`). A cell is in if
  **|dx| < r and |dy| < r** (and |dz| < r for spheres; cylinders use their height for z).
  A 20-ft-radius fireball = 8×8 cells.
- **Emanation from a creature** (aura, *spirit guardians*): every cell within r of any
  cell the creature occupies (Chebyshev distance ≤ r).
- **Cone (length L):** apex = midpoint of the caster's cell face (straight cone) or the
  caster's cell corner (diagonal cone). For a cell center at offset v from the apex,
  with f = distance along the aim and s = distance off the aim line:
  **in if 0 < f ≤ L and s ≤ f / 2** (5e: a cone's width equals its distance from the
  origin). Works in 3D unchanged. Templates below; anything else → `engine/space.py cone`.
- **Line (L × 5 ft):** cells whose center lies within 2.5 ft of the line segment from
  the caster's cell face out to L.

### Cone templates (`@` caster, `#` affected, aimed east / northeast; rotate/mirror)
```
15 ft straight (5)   15 ft diagonal (6)   30 ft straight (18)   30 ft diagonal (20)
   ...#                 ..#.                 .....##               ...#...
   @###                 .###                 ...####               ..###..
   ...#                 .##.                 @######               ..####.
                        @...                 ...####               ..#####
                                             .....##               .#####.
                                                                   .##....
                                                                   @......
```
Templates are the cells at the caster's height. Areas are 3D: a 30-ft cone also reaches
a few cells above/below the aim line, which matters for flyers and balconies. 60-ft
cones (61 / 70 cells), aims that aren't straight or diagonal, and anything with height
differences → `python engine/space.py cone ...`.

## Dropping to 0 HP
PCs fall unconscious and make death saves (d20: 10+ success, three successes stabilize,
three failures die; nat 1 = two failures, nat 20 = up on 1 HP). Damage while down = a
failure (crit = two). Most monsters simply die at 0 (GM's call to keep pace).

## Conditions cheat table (most common)
- **Prone:** melee attacks vs. you have advantage, ranged have disadvantage; your attacks
  have disadvantage; half movement to stand.
- **Grappled:** speed 0; escape via Athletics/Acrobatics vs. grappler's Athletics.
- **Restrained:** speed 0, attacks vs. you advantage, your attacks disadvantage, DEX saves disadvantage.
- **Poisoned:** disadvantage on attacks and ability checks.
- **Frightened:** disadvantage on checks/attacks while source in sight; can't move closer to it.
- **Stunned/Paralyzed/Unconscious:** incapacitated; attacks vs. you have advantage
  (paralyzed/unconscious: hits within 5 ft are crits).
