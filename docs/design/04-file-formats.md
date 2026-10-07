# 04 — File Formats & Templates

Every game file uses YAML frontmatter for machine-scannable facts (grep-able without
reading the whole file) and markdown body for prose. Frontmatter fields are the contract;
body sections are conventions.

**Parsing contract (tools read and write these files, see 06):** frontmatter uses only
`key: scalar`, `key: [inline, list]`, `key: {one: 1, level: 2}` (one-level inline map;
a value inside it may be an inline list, `{spell: bless, on: [Kael, Kira]}`, Phase 13),
`# comments` and quoted strings. No nested blocks or multi-line values. Anything richer
goes in a markdown table in the body. Tables are read by header name, so extra columns
are always safe. Line endings: the working tree is mixed CRLF/LF (`core.autocrlf` is
`true`), so tools read with `encoding="utf-8"` + `splitlines()`, write back with the
newline the file already uses (`\r\n` if it contains one, else `\n`), and give new
files `\n`.

**Frontmatter is player-safe.** It's the first thing anyone sees in a file, and tools
print it freely, so it holds only the public face of things (e.g., an NPC's cover
`role` and public `faction`). True identities and allegiances go under the marked
secret sections (`## Knowledge & secrets`, `## The truth`, `## Hidden`).

**Anchor times to days.** Body text that says "two nights ago" goes stale as the clock
advances, so add the absolute day: "two nights before the party arrived (night of Day
-1)". Pre-campaign days are numbered ≤ 0. This also lets `gm.py trace` and `/spoilers`
treat them as Established facts.

## Location files — `locations/<slug>.md`

Places nest, and each place with a file has its own coordinate **frame**. A frame's
**tier** says what unit it uses and what it holds:

| tier | example | unit | holds | appears in its parent as |
|---|---|---|---|---|
| `world` | the realm; a region or duchy inside it | mi | world-tier children, areas, roads | a footprint row, in mi |
| `area` | Thornbury; a city, or one district of it | ft | areas (districts), sites, routes | a footprint row, in mi or ft |
| `site` | the Crossroads Inn | ft (5-ft cells) | sub-areas: rooms, floors, yards | a footprint row, in ft |

**Tiers are units, not depths.** A world-tier file may hold world-tier children (realm
→ region), and an area may hold areas (city → district), to any depth. Only two unit
changes exist: mi → ft when an area sits in a world-tier frame, and ft → 5-ft cells when
a site is laid out. Three levels is the POC's shape, not a rule, and the tools never
assume a depth. This keeps `world.md` from becoming one giant table once the campaign
has forty villages: the duchy gets its own file and its own routes.

**Frame rules** (these keep cross-tier math down to addition):
- Every frame is **north-up, +x east, +y north, +z up**. Never rotated.
- A child frame is placed in its parent by **offset only**. The child's row in the
  parent's `## Places` table has an `at` column: where the child's local `(0,0,0)`
  sits in the parent's frame. So `parent pos = at + local` (with ft↔mi conversion when
  the units differ). `from`/`to` are the footprint, which is separate because an origin
  needn't be a corner (Thornbury's is the well in the middle). For a site, put the
  origin at its SW corner at ground level, so `at` = `from`, and **a blank `at` means
  `= from`**. Cellars go negative and upper floors positive. Footprints constrain x/y
  only, so Places rows may use 2-D points `(x,y)`; the tools read z as 0.
- **A site has one frame.** All its sub-areas (rooms, floors, cellar, yard) share it.
  Floors and cellars are z values, not new frames.
- **The parent owns placement.** A child file names its `parent:`. Where it sits lives
  only in the parent's `## Places` row. Places without a file yet (the smithy) are just
  rows, which is enough canon to stay consistent about.
- **Coordinates are lazy.** Nothing needs a position until play asks a spatial
  question. An area can start with three rows. Lint complains only when placed things
  contradict each other.
- **Directions and distances are never authored, only derived.** "East side of the
  square", "15 min walk": tools compute these from the frames and routes (06 →
  `scene enter`, `where`), so they can't go stale or disagree.

Tier vs. `type`: `tier` decides geometry. `type` is flavor
(`realm | region | settlement | building | outdoor | wilderness | dungeon`).

### Site file

```markdown
---
name: The Crossroads Inn
tier: site
type: building
parent: thornbury       # area slug; its ## Places row places this site
tags: [social, safe]
---

# The Crossroads Inn

## Description
Sensory prose the GM can draw exposition from. 1–3 paragraphs.

## Areas
<!-- Sub-areas of this site and how they're reached from inside it. They live in one
     file, so there's no symmetry problem. Ways in and out of the site are the parent's
     ## Routes, not this list. These slugs are what `location: crossroads-inn/<area>`
     may name. -->
- **common-room** — front door from the square; the hub
- **cellar** — trapdoor behind the bar, locked (Mara has the key), not obvious (DC 12 Perception)
- **stable-yard** — side door past the kitchen; gate onto the back lane

## Routes
<!-- Optional. Same table as an area's Routes, with from/to = sub-area slugs or Layout
     exit ids. Write it when in-site movement matters (locked doors, a hidden way out,
     a path an NPC must take unseen). Without it, the ## Areas prose is the record and
     `move-party site/area` is unchecked. -->
| id       | from        | to          | via | kind     | access                       | time | notes               |
|----------|-------------|-------------|-----|----------|------------------------------|------|---------------------|
| trapdoor | common-room | cellar      |     | trapdoor | locked (Mara); DC 12 to notice | 1m | behind the bar      |
| kitchen  | common-room | stable-yard |     | door     | obvious                      | 1m   | through the kitchen |

## Items & features
- Bar (north wall): locked strongbox beneath (DC 15 Thieves' Tools), ~40 gp
- Notice board (by the door): three postings — see scenario
- Hearth (east wall): always lit; loose stone hides nothing (red herring)

## Hidden
<!-- Compared against passive Perception on entry; revealed to qualifying PCs.
     `DC N (area):` limits an entry to one sub-area (checked when the party enters it). -->
- DC 13: fresh mud tracked in leading to the cellar trapdoor
- DC 17: faint sound of scraping from below the floorboards
- DC 15 (cellar): a second, newer lock on the inner door

## Layout
<!-- Written the first time a tense scene or fight happens in a sub-area, then fixed.
     Only features with spatial or mechanical weight. One ### block per sub-area. All
     blocks share the site's frame, so every Bounds line repeats the same origin.
     Exit rows (effect starts "exit →") are the endpoints that routes and cross-area
     moves attach to. -->
### common-room
Bounds: x 0–45 · y 0–35 · z 0–10 · origin (0,0,0) = inside the front door, SW corner · +x east · +y north · +z up · ft

| id     | glyph | feature     | from      | to        | effect                           |
|--------|-------|-------------|-----------|-----------|----------------------------------|
| door   | d     | front door  | (0,0,0)   | (0,0,0)   | exit → square                    |
| bar    | b     | bar counter | (15,25,0) | (35,25,0) | half cover; crossing = difficult |
| stairs | s     | stairs up   | (0,15,0)  | (0,25,10) | stairs up to landing (z 10)      |

## Notes / current state
Running changes: damage, moved items, ambience shifts. GM appends here.
```

### Area file (and world file)

Same skeleton without `## Areas` and `## Layout`, plus `## Frame`, `## Places` and
`## Routes`. The world file uses the same pattern with two more sections (below).
A place or route the party doesn't know about yet carries the word `secret` in its
`effect`/`access`, exactly like terrain; `gm.py world reveal <id>` strips it.

```markdown
---
name: Thornbury
tier: area
type: settlement
parent:                 # world slug; empty until a world file exists
tags: [village]
---

# Thornbury

## Description
The area as a whole: what you see coming in, the lay of the land.

## Hidden
(same rules as a site; checked when the party is in the open parts of the area)

## Frame
origin (0,0,0) = the well at the center of the square · +x east · +y north · +z up · ft

## Places
<!-- One row per place. `at` = where that place's own (0,0,0) sits in THIS frame (blank
     for a row with no file). from/to = opposite corners of its footprint. `ref` = the
     place's slug, or `—` for a row with no file yet. `source`: see The world file.
     Same columns as Layout, plus at/ref/source. -->
| id     | glyph | feature        | at           | from         | to           | effect             | ref            | source   |
|--------|-------|----------------|--------------|--------------|--------------|--------------------|----------------|----------|
| square | .     | village square | (-60,-60,0)  | (-60,-60,0)  | (60,60,0)    | open ground        | village-square | scenario |
| inn    | I     | Crossroads Inn | (65,-20,0)   | (65,-20,0)   | (175,15,20)  | building + yard    | crossroads-inn | scenario |
| smithy | f     | smithy         |              | (-55,70,0)   | (-25,95,15)  | not yet detailed   | —              | scenario |
| mill   | M     | old mill       | (-20,4400,0) | (-20,4400,0) | (20,4440,25) | astride the stream | old-mill       | scenario |

## Routes
<!-- Ways between places, each written ONCE, in the lowest frame that contains both ends.
     This replaces the old per-file Connections. from/to = a place id, or `place.exit`
     (an exit row id in that site's Layout). Without an exit, the tool uses the
     footprint edge nearest the other end. `via` = waypoints in this frame, in order.
     `time` is blank (derived: path length ÷ pace × the kind's factor) or an override
     with a reason. `kind` sets a default pace factor: road/street/door 1 · path/lane
     1 · trapdoor/stairs/gate/ladder 1 · trail 1.5 · trackless/marsh/scree 2 (the
     DMG's difficult-terrain halving).
     `access`: obvious | DC N to notice | locked (who has the key) | secret. `secret`
     routes are left off player-facing output until discovered, like terrain.
     A route with its own dangers gets `tables/encounters-<route id>.md`; `travel`
     looks for that before the area's table. -->
| id       | from   | to          | via                                 | kind | access  | time | notes            |
|----------|--------|-------------|-------------------------------------|------|---------|------|------------------|
| inn-door | square | inn.door    |                                     | door | obvious |      |                  |
| mill-rd  | square | mill        | (0,60,0) (150,1500,0) (-100,3000,0) | road | obvious |      | along the stream |

## Notes / current state
```

### The world file — `locations/world.md` (always exists)

Every campaign has exactly one world file from day one, created by `/new-campaign`, even
when all anyone knows is one village. It holds the known places in relation to each
other. The rest of the world is open, to be filled in later by generation, player
choice or outside material. **A blank part of the world map means unknown, never
empty.**

- **Origin = the starting area.** The frame's `(0,0,0)` is the campaign's first area
  (its own origin, e.g. Thornbury's well). Coordinates grow outward in any direction as
  places are added, so there are no world bounds to outgrow.
- **Three states of knowledge, three sections:**
  1. **`## Places`**: placed, coordinates are canon. Moved only by fiction or `/overrule`.
  2. **`## Known, not placed`**: the place exists (someone named it) but has no
     coordinates yet. Instead it carries **constraints**, which is the relational
     metadata ("within 3 days of thornbury", "E of thornbury", "on a navigable river").
     Placing it later means choosing coordinates that satisfy every constraint.
  3. **`## Frontier`**: open leads off the edge of what's known (a road out of town, a
     river downstream). These are hooks for future places. A lead becomes a route
     once its far end is placed.
- **Rows are player-safe.** `world show --player-view` prints places, constraints and
  notes, so secrets about a place go in its own file's `## Hidden`, never in this table.
- **Every row records its `source`:** `scenario` (campaign material), `player:<pc>`
  (said at the table or in a backstory), `generated` (the GM made it up when it was
  needed), or `import:<resource>` (a published map or module).
- **Precedence when sources conflict:** placed canon > `import` / `scenario` >
  `player` > `generated`. A player's backstory claim ("my hometown is a river port")
  is honored unless it contradicts placed canon. In that case the GM asks the player
  once and adjusts the claim, not the canon. Generated content never overrides
  anything.
- **Constraints are spatial only**, in a small vocabulary so tools can check them:
  `within <dist|time> of <id>`, `beyond <dist|time> from <id>`, `<compass> of <id>`,
  `on <feature>` (a named river, road or coast; an unnamed one like `on a navigable
  river` is kept but unchecked until such a feature is placed), and `near (x,y)
  ±<dist>` (from imports). Anything else about the place ("has a temple of Chauntea",
  "a river port") is an attribute and goes in `notes`, so the parser never has to skip
  prose.
- **Time constraints are checked twice.** "Three days" means by road, and roads wind.
  At placement, `within 3d` admits a straight-line radius of 3 × 24 mi × 0.8; when a
  route to the place is later added, the derived route time is re-checked against the
  original constraint (kept in the Places row's `notes` as `placed: within 3d of
  thornbury`) and lint warns if the road broke the promise.

```markdown
---
name: The World
tier: world
type: realm
parent:
tags: []
---

# The World

## Description
What's generally known: the realm's name if anyone's said it, climate, the big
picture. Fine to leave nearly empty.

## Frame
origin (0,0,0) = Thornbury's well (the starting area's origin) · +x east · +y north · +z up · mi

## Places
| id        | glyph | feature   | at      | from            | to            | effect          | ref       | source   |
|-----------|-------|-----------|---------|-----------------|---------------|-----------------|-----------|----------|
| thornbury | T     | Thornbury | (0,0,0) | (-0.1,-0.1,0)   | (0.1,0.9,0)   | farming village | thornbury | scenario |

## Known, not placed
| id          | feature         | constraints                                   | source      | notes                    |
|-------------|-----------------|-----------------------------------------------|-------------|--------------------------|
| market-town | the market town | within 3d of thornbury                        | player:kael | temple of Chauntea; Kael was sent from here |

## Frontier
| id       | from      | heading | known as | said to lead to | source   |
|----------|-----------|---------|----------|-----------------|----------|
| east-rd  | thornbury | E       | the east road | (unknown)  | scenario |

## Routes
(world-tier routes between placed places; same format as an area's Routes, in mi)

## Notes / current state
```

**Filling it in (02 → The open world; 06 → `gm.py world`).** Placing a known row or
generating a new place goes through `gm.py world place|add`. It checks the constraints
and refuses overlaps with placed footprints. Placing a frontier lead's far end turns the
lead into a route. Importing a map (`world import`) aligns its coordinates to ours by
one shared place plus a scale, or by two shared places.

**Deriving travel time.** Path length (from → via → to) is measured in a straight line
(Euclidean, z included). This is overland travel, not the combat grid rule. Pace follows
the PHB: normal is 300 ft/min in ft frames and 3 mi/h in mi frames. Fast is ×4/3 speed
(time ×0.75); slow is ×2/3 (time ×1.5). The route's `kind` factor multiplies the time
(trail ×1.5, trackless ×2). Conveyance (`travel --by`): foot ×1, cart/wagon ×1 on
road/street and ×2 elsewhere, horse ×0.5 on road and ×1 elsewhere, boat downstream
×0.5 on a river route. Round up to a whole minute (minimum 1); over an hour, round to
5 min. Set `time` by hand only when the line still lies (`45m — switchbacks`). Lint
flags an override more than 2× off the derived value as a probable typo.

**Where people are.** `location:` in PC/NPC frontmatter and `party-location:` in
`current.md` take `site` or `site/area` (`crossroads-inn/common-room`). The area part
is optional and doesn't need a Layout yet; it should be listed in the site's `## Areas`.
Exact `(x,y,z)` positions exist only in the Stage table and Combat block, in the frame
named on the block's `Map:` line.

Layout, Places and terrain tables use the same format everywhere (site Layout, area/world
Places, Combat block), so `engine/space.py` can read them and the GM can copy rows across.
`from`/`to` are opposite corner cells (inclusive); a single cell has `to` = `from`.
`effect` is free text, but the helper keys on the words *difficult*, *stairs*, *ramp*,
*wall* (impassable, total cover, blocks line of sight; glyph `#` by convention), *door*
(a gap in a wall; add *closed*, *locked* or *barred* to block it until opened), *hazard*
or any damage dice (`1d10 fire`: passable, but pathfinding avoids it and a move through
it is flagged), and *secret* (left off `--player-view` maps until the party discovers it;
then the word is removed), and on a leading *exit →*. Walls matter as soon as two sub-areas of a site are laid out,
or a fight is reframed to the area tier: without them, movement and cones pass through
buildings. A single-room Layout can still rely on its Bounds.

Who-is-here is NOT stored in the location file. It's derived by grepping NPC/PC
frontmatter for `location: <slug>` (single source of truth for positions).

## Campaign file — `<campaign>/campaign.md`

Frontmatter and body per 07 → Parameters (name, slug, length, start-level, players,
difficulty, shape, secondary, tone, references, reveal-policy, mechanics, seed-file,
status); sections `## Premise (player-safe)`, `## Why you're here (player-safe)`,
`## Author notes (GM-only)`, `## Reveal exceptions`, `## Fill-in queue` (`| id | question | default | status |`), `## Author
ledger` (`| when | what the driver was told | via |`).

**`## Why you're here (player-safe)`** (campaign.md, else the active scenario): why the
party is in the opening. One `- ` bullet = the fixed reason; several = options the
players choose from at the first session; none = the GM invents 2–4 and asks. The
answer is recorded as a `Chosen: …` line by `gm.py intro --why "…"` (06).

**Advancement** (frontmatter, defaults shown): `advancement: milestone` (`milestone |
xp`: what triggers level-ups), `xp-tracking: on` (`on | off`: whether XP is awarded and
kept at all; independent of advancement), `xp-absent: full` (`full | half | none`: what
an absent PC gets of an award), `xp-split: even`. A campaign without `campaign.md` (the
POC) reads the same keys from `state/current.md` frontmatter, with the same defaults.
`advancement: xp` requires tracking on. Switching to `xp` mid-campaign keeps each PC's
tracked total, raised to at least the threshold of their current level; switching to
`milestone` keeps the total and stops auto-levelling.

**Setting** (frontmatter): `setting: "<one line>"`, what the world has: tech level,
how common magic is, anything unusual (07 → Setting). Empty = standard D&D fantasy. The
brief's `Setting:` line carries it (06), and the GM judges *Not in the setting* against it (02 → Kinds of
"no").

**Wacky Juice** (frontmatter, defaults shown; 02 → Wacky Juice): `wacky-juice: on`
(`on | off`), `wacky-juice-value: 5` (percent chance per eligible player prompt, 0–100),
`wacky-juice-cooldown: 3` (player prompts). As with advancement, a campaign without
`campaign.md` reads the keys from `state/current.md` frontmatter. Hook state lives in
`<campaign>/.gm/juice` (not hand-edited): `prompts-since: N` and `pending: <npc slug>`
or blank. A firing is logged by the next `do` as a GM-only line
`  - (GM) [juice] Tobin` or `  - (GM) [juice] Tobin — waived`, and a rate change as a
public line `  - [juice] value 5 → 10`.

**Encounter lines** (scenarios and locations, 07 → Difficulty scaled to the table):
`- ENCOUNTER <easy|medium|hard|deadly> "<name>": <monster> ×n, <monster>, …` or
`- ENCOUNTER fixed L<level> <word> "<name>": <roster>`. Adventure places carry
`threat: {xp: N, fixed: false}` in frontmatter, computed by `gm.py encounter threat`.

**Loot and stock** (07 → Items, loot and merchants). A location may carry
`## Loot`: `| item | kind | rarity | where | guard | random | notes |` (`kind`:
campaign | treasure | consumable; `where` = sub-area or feature id; `guard` = an
ENCOUNTER name, a check like `DC 15 Investigation`, or `—`; `random` = a loot table
slug or blank). A merchant NPC carries `## Stock`: `| item | price | stock | restock |
random |` (`restock`: daily | weekly | loop | never; `random` = a stock table slug for
re-rolled rows). Tables: `tables/loot-<tier|place>.md` and `tables/stock-<merchant>.md`,
both `| roll | result |`. The `item` mutation and PC `## Inventory` are unchanged; a
magic item's rarity is written in its inventory line (`+1 longsword (uncommon)`) so
`encounter budget` can count item power.

**Time-loop campaigns** (`mechanics: [time-loop]`, 07 → Campaign mechanics): `current.md`
gains `loop`, `loop-baseline`, `loop-start`, `loop-end`; PCs gain `loop-bed: site/area`;
`state/loops.md` is `| loop | ended by | learned | gained | notes |`; an NPC may have
`## Memory across loops`; a regenerated piece already carried is marked `hollow` in
its `notes`.

**Table settings (Phases 13–15; 02 → Table mechanics).** Frontmatter, else
`state/current.md`, defaults shown:

| key | values | default | phase |
|---|---|---|---|
| `death-save-rolls` | `open \| secret` | open | 13 |
| `track-light` | `on \| off` | off | 13 |
| `supplies` | `strict \| loose \| off` (food and water) | off | 13 |
| `ammo` | `all \| special \| off` | special | 13 |
| `exhaustion` | `2014 \| 2024` | 2014 | 13 |
| `travel-detail` | `summary \| activities` | summary | 14 |
| `getting-lost` | `on \| off` | on | 14 |
| `social-dcs` | `dmg \| gm` | dmg | 14 |
| `creativity` | `off \| light \| generous` | light | 14 |
| `social-wall` | `off \| <n>` | 3 | 14 |
| `morale` | `on \| off` | on | 14 |
| `chases` | `dmg \| narrative` | dmg | 14 |
| `inspiration` | `advantage \| reroll \| off` | advantage | 15 |
| `downtime` | `off \| light \| full` | light | 15 |
| `weather` | `off \| on` | off | 15 |
| `encumbrance` | `off \| basic \| variant` | off | 15 |
| `renown` | `off \| party \| per-pc` | off | 15 |
| `lingering-injuries` | `off \| on` | off | 15 |
| `upkeep` | `off \| on` (coin for lifestyle, crafting materials, training fees, hireling wages) | off | 15 |
| `carousing` | `on \| off` | on | 16 |
| `crit-die` | `off \| on` | off | 16 |
| `crit-die-pcs` | `dying \| dead` | dying | 16 |

**Random tables (Phase 16)** live in `<campaign>/tables/<name>.md`, the same folder as
loot and stock tables. Header: `| roll | result | effect | tags |`. `roll` is a number or
a range (`01-03`, `7`). `effect` holds zero or more `;`-separated codes the tool applies
(02 → Phase 16; anything else is narrated). `tags` is a comma list matched against the
campaign's `lines:`/`veils:`. Frontmatter: `die: d100` (default: inferred from the
highest roll) and, for carousing, `cost: 1d6x10gp`. `carousing.md` and `crit-die.md`
are copied from `engine/templates/tables/` by `campaign new` (original starter text).
A table imported from elsewhere (`table import`) replaces the copy and stays in the
campaign folder.

**Discord bridge (Phase 17)** — `<campaign>/discord.md`, read by `table.py` only:
```markdown
---
discord: queue          # off | queue | auto
channel: 123456789012345678
debounce: 4             # auto mode: seconds of quiet before a batch is sent
---
| discord user | player |
|--------------|--------|
| sam_the_bard | Sam    |
```
`player` matches PC `player:` values. The bot token is never stored here; it comes from
the `DND_DISCORD_TOKEN` environment variable (06 → Discord bridge).

**Content boundaries** (Phase 13, campaign.md; a campaign without one, like the POC,
keeps them in `current.md`, as with every setting):
`lines: [harm to children, sexual violence]` (never appears) and `veils: [torture]`
(off screen only). Written by `gm.py campaign boundaries` (`--none` writes both empty);
an empty list means asked and none; a missing key means not yet asked.

**`services` tag** (Phase 13): a site whose `tags:` include `services` (an inn, a
market) is a place where the party eats without counting rations under `supplies:
loose`.

## Custom-bestiary file — `campaigns/<name>/custom-bestiary/<slug>.md`

A custom monster, made with `gm.py monster new "<name>" --from "<SRD or custom monster>"`
(07 → Custom monsters) and then edited. Each campaign keeps its own; everywhere a monster
is named (`srd:<name>`, `ENCOUNTER` rosters, `statblock:`) the lookup is the active
campaign's custom-bestiary, then the SRD. Creatures cross campaigns only by being copied
at creation (`--from "<other-campaign>:<monster>"`).
```markdown
---
name: Frost Yeti
kind: monster
based-on: Polar Bear (SRD), re-themed with ice affinity
size: L                 # T S M L H G
type: monstrosity
ac: 13
ac-note: natural (frost-matted hide)
hp: 59
hp-dice: 7d10+21
speed: 40 ft, climb 40 ft
scores: {str: 19, dex: 12, con: 17, int: 6, wis: 12, cha: 7}
prof: 2
saves: {con: 5}         # bonuses, as in a stat block
skills: {perception: 3, stealth: 3}
senses: [darkvision 60]
passive-perception: 13
resistances: []
immunities: [cold]
vulnerabilities: []
condition-immunities: []
cr: 3
xp: 700
---
## Description · ## Traits (`- **Name.** text`) · ## Attacks (`| name | hit | damage | range | notes |`,
damage parts joined with ` + `, e.g. `1d6+4 slashing + 1d6 cold`) · ## Actions (Multiattack and
non-attack actions as bullets) · ## Reactions · ## Backstory
```

## NPC file — `npcs/<slug>.md`

```markdown
---
name: Mara Fennick
location: crossroads-inn/common-room   # site or site/area; updated whenever she moves
role: innkeeper
faction: none
attitude-to-party: neutral    # hostile | wary | neutral | friendly | ally
statblock: commoner           # SRD name, or "custom: see below"
default-goal: keep the evening calm   # optional; seeds the On stage line on scene entry
moved-by: [honesty]           # optional (Phase 14): audacity | honesty | flattery | humour | piety | coin | nothing
status: alive                 # alive | dead | missing — set by tools (combat end)
---

# Mara Fennick

## Description
Appearance, voice, mannerisms — enough to play her distinctively.

## Personality & motivation
Traits, bond, flaw. What she wants generally; what she'd never do.

## Knowledge & secrets
What she knows that players might extract, with how hard it is to get:
- Freely shares: ...
- Needs persuasion (DC 12): ...
- Only under duress / never: ...

## History with the party
Append-only log of notable interactions. Drives attitude changes.

## Movements
<!-- Machine-readable schedule lines first (gm.py clock applies them); prose after.
     Target = site or site/area, as in `location:`; the (parenthetical) is a free note. -->
- 05:00–18:00 → crossroads-inn/kitchen
- 18:00–00:00 → crossroads-inn/common-room (behind the bar)
Scenario-driven or conditional moves in prose ("if suspicion rises, leaves by night").
```

Custom stat blocks (`statblock: custom`) use the same `scores`/`prof`/`saves`/`skills`
frontmatter and `## Attacks` table as PCs, below, plus `ac:` and `hp: {current, max}`.
Optional on NPCs and PCs alike: `resistances: [poison]`, `immunities: [fire]`,
`vulnerabilities: [radiant]` (inline lists of damage types; `gm.py dmg`/`atk` apply
them: half rounded down, 0, double).

## PC file — `pcs/<slug>.md`

Written and updated by `gm.py pc` (intake, edits, level-ups; 02 → Session start &
characters). Derived fields (hp max, ac, passives, prof, saves/skill totals, Attacks,
spell slots) are recomputed by the tools unless listed in `overrides`.

```markdown
---
name: Kira Thornwood
player: Alex                      # optional: who plays her; blank or (pregen) = unclaimed
location: crossroads-inn/common-room
race: high elf                    # race + subrace
class: rogue
subclass: thief                   # empty until the class's subclass level
level: 3
background: custom (dock runner)
hp: {current: 30, max: 30}     # {current, max, temp}: `temp` only while temp HP last (gm.py hp +temp)
ac: 14
passive-perception: 15        # GM reads this every scene entry
passive-investigation: 13
speed: 30
conditions: []
scores: {str: 8, dex: 17, con: 14, int: 12, wis: 13, cha: 10}   # raw scores; mods derived
prof: 2
saves: [dex, int]                 # proficient saves
skills: {stealth: 7, perception: 5, sleight-of-hand: 5}   # totals, only the ones used
senses: [darkvision 60]
hit-dice: {die: d8, left: 3}
hp-method: max                    # max | roll — asked once at creation; changed only on request
autopilot: follows the group, defends herself, makes no major decisions
present: true                     # this session's roster (gm.py pc roster)
level-pending:                    # e.g. 4 — set at a milestone or by an XP threshold, cleared by level-up
xp: 0                             # tracked unless xp-tracking: off; levels only when advancement: xp
overrides: {}                     # player-insisted values the tools won't re-derive, e.g. {ac: 17}
---

# Kira Thornwood

## Stats
STR 8 (-1) | DEX 17 (+3) | CON 14 (+2) | INT 12 (+1) | WIS 13 (+1) | CHA 10 (+0)
<!-- Human-readable mirror of the frontmatter; tools use the frontmatter. -->

## Attacks
| name     | hit | damage        | range  | notes                 |
|----------|-----|---------------|--------|-----------------------|
| dagger   | +5  | 1d4+3 pierce  | 20/60  | finesse, thrown       |
| shortbow | +5  | 1d6+3 pierce  | 80/320 | 20 arrows             |

## Resources
| resource      | current | max | recovers |
|---------------|---------|-----|----------|
| sneak attack  | 1       | 1   | turn     |
| spell slot 1  | 2       | 2   | long     |

## Spells
<!-- Casters only. source: cantrip | known | prepared | always (domain/oath/etc.) | custom -->
| spell         | level | source  | notes          |
|---------------|-------|---------|----------------|
| minor illusion| 0     | cantrip | high elf (INT) |

## Features & abilities
Sneak Attack 2d6, Cunning Action, Thieves' Cant... Non-SRD content is summarized here
and marked `(custom)`; the tools carry it but don't derive it.

## Inventory
- Equipped: leather armor, 2 daggers, shortbow (20 arrows)
- Pack: thieves' tools, 50 ft rope, 35 gp

## Background & story
Short backstory + goals the GM can hook.

## Journal
GM appends durable character developments here.
```

**Added by Phases 13–15** (frontmatter keys appear only while they mean something;
NPCs take the same keys, and in combat the Combatants row's `conditions` mirrors
them):
```yaml
concentration: {spell: bless, until: "Day 1 18:31", on: [Kael, Kira]}   # 13; until = game time, or "3r"
death-saves: {ok: 1, fail: 2}     # 13; only while dying at 0 HP; `stable` / `dead` are conditions
lit: [torch 40m]                  # 13; light sources this creature carries, lit, with time left
fed: "Day 1"                      # 13; last day with a full ration and water (supplies on)
exhaustion: 0                     # 13; 0–6
inspiration: false                # 15
attuned: [cloak of protection]    # 15; at most 3
```
- **Ammunition and supplies** (13) stay ordinary `## Inventory` text with counts:
  `quiver (20 arrows)`, `rations (5 days)`, `waterskin (full|half|empty)`, `flask of
  oil (2)`, `torches (4)`. The Attacks row's `notes` names the ammunition it uses
  (`ammo arrows`); `special ammo <thing>` marks ammunition worth tracking under the
  default `ammo: special` (ordinary arrows and bolts are endless). A leading count works too (`2 flasks of oil`, `5 days rations`); a
  bare `waterskin` is full. `stable` carries the hours until the PC wakes (`stable 3h`).
  Spell effects from `conc` are conditions named by the spell's slug (`bless 10r`,
  `hold-person 1m`). A combatant without a file keeps its concentration targets in its
  row's `notes` (`conc→Kael+Kira`, `conc-save 12` while a save is owed).
- **Magic items** (15) carry their tags in the inventory line:
  `wand of magic missiles (uncommon, charges 5/7, recharge 1d6+1 dawn, destroy on 1)`,
  `cloak of protection (uncommon, attune, ac +1, saves +1)`,
  `unidentified: smoky glass ring (GM: ring of mind shielding)`; the `(GM: …)` part
  is the true name and is stripped from player-facing output until identified.
- **Weight** (15) comes from the SRD equipment data; a custom item may carry `(5 lb)`.
- **`## Companions`** (15): `| name | ref | hp | acts | notes |` (`acts`: own init |
  with me | mount; e.g. `Ash | srd:owl | 1/1 | own init | familiar, telepathic link`).
  Written by `companion add`; `combat end` writes the HP back. A rider out of combat
  carries `mounted on Horse` in `conditions` (the mount being a `mount` companion).
- **Hirelings** (15) are NPC files with `hired-by: Kira | party`, `wage: 2 gp/day` and
  `loyalty: 10` (0–20; their morale save is DC 20 − loyalty), written by `hire`.
- **Equipped and attuned** (15): an item's bonuses count while it sits on the
  `- Equipped:` line (and is in `attuned:` when tagged `attune`); the file's `ac:` stays
  the base, the tools add the items live. Charge and recharge tags: `charges N/M`,
  `recharge <dice> dawn|dusk|midnight|noon`, `destroy on 1`.
- **`## Downtime`** (15): `| activity | progress | goal | cost/day | notes |` (e.g.
  `craft chain shirt | 25 gp | 50 gp | 1 gp | at Brannoc's forge`).

## Scenario file — `scenarios/<slug>.md`

```markdown
---
name: The Missing Miller
status: active            # planned | active | resolved
locations: [crossroads-inn, village-square, old-mill]
---

# The Missing Miller

## Premise (player-safe)
The hook as players encounter it.

## Why you're here (player-safe)
- Hired by Reeve Odell to find out what happened to Harl.
- Passing through on your own road; the inn is the only bed for ten miles.

## The truth (SPOILERS)
What's actually going on. GM-only by honor system.

## Factions & relationships
- Faction/NPC → wants X, fears Y, will do Z
- Relationship map in prose or a list: who owes/hates/protects whom

## Beats & triggers
The "watch for" list that gets mirrored into state/current.md:
- WHEN party mentions the miller to Mara → she deflects, DC 12 Insight catches the lie
- WHEN party enters old-mill at night → cellar encounter
- CLOCK Day 3 04:00: second disappearance if no progress
<!-- CLOCK lines use "CLOCK Day N HH:MM:" so gm.py clock can fire them. -->
<!-- Encounter/random tables live in <campaign>/tables/<slug>.md as | roll | result |. -->

## Resolution paths
2–3 ways this can plausibly end; consequences of each for the world docs.
```

## State file — `state/current.md` (the hot cache)

```markdown
---
campaign: poc
in-game-datetime: "Day 1 19:30"   # absolute day + 24 h clock; tools add to it
party-location: crossroads-inn/common-room   # site or site/area
scene: "Common room, dinner rush"
light: bright                     # bright | dim | dark — passive Perception uses it
in-session: false                 # true while playing; gates the brief hook (06)
dice-mode: players-roll-d20s      # players-roll-d20s | gm-rolls-all
---

# Current scene

## Summary
2–4 sentences: what's happening right now.

## On stage
- **Mara** (npcs/mara-fennick.md) — behind the bar; wary of miller questions; goal: keep the evening calm
- **Tobin** (npcs/tobin-hale.md) — corner table; drunk, talkative; goal: find someone to listen

## Watch for  <!-- mirrored triggers from active scenarios -->
- Miller mentioned to Mara → open scenarios/the-missing-miller.md (beat 1)

## Clocks
- Day 3 04:00: second disappearance if unresolved

## Tempo: calm  <!-- calm | tense | combat — see 01-architecture.md, Scene tempo -->

## Combat
(not in combat)
```

When tempo is **tense**, `gm.py tempo tense` adds a **Stage table** under the Tempo
heading. It has the Combatants columns (below) so `combat start` can promote it as is.
`init` holds the passive initiative, and `intent` holds the NPC's intent for this beat:

```markdown
## Tempo: tense
### Stage
| init | name      | glyph | side    | pos       | size | ref               | adj                 | intent                    |
|------|-----------|-------|---------|-----------|------|-------------------|---------------------|---------------------------|
| 17   | Mara      | M     | neutral | (25,30,0) | M    | npcs/mara-fennick | +5 watching room    | get the letter off the bar |
| 13   | Kael (PC) | K     | party   | (10,5,0)  | M    | pcs/kael          |                     |                           |
| 5    | Tobin     | T     | neutral | (35,5,0)  | M    | npcs/tobin-hale   | −5 drunk            | keep talking              |
```

### Combat block (replaces "(not in combat)" while fighting)

```markdown
## Combat — round 2 · up: Kael
Map: crossroads-inn / common-room (frame: site crossroads-inn; layout: locations/crossroads-inn.md)
Bounds: x 0–45 · y 0–35 · z 0–10 · origin (0,0,0) = inside the front door, SW corner · +x east · +y north · +z up · ft

### Terrain
| id       | glyph | feature          | from       | to          | effect                           |
|----------|-------|------------------|------------|-------------|----------------------------------|
| bar      | b     | bar counter      | (15,25,0)  | (35,25,0)   | half cover; crossing = difficult |
| tables-w | t     | tables & benches | (10,10,0)  | (15,15,0)   | difficult                        |
| stairs   | s     | stairs up        | (0,15,0)   | (0,25,10)   | stairs up to landing (z 10)      |
| landing  | l     | upstairs landing | (0,30,10)  | (10,35,10)  | 3 ft rail: half cover from below |

### Combatants
| init | name      | glyph | side  | pos       | size     | ref          | HP      | AC | conditions   | notes      |
|------|-----------|-------|-------|-----------|----------|--------------|---------|----|--------------|------------|
| 18   | Veskar    | V     | foe   | (5,30,10) | M        | npcs/veskar  | 22/22   | 14 | —            | on landing |
| 15   | Kael (PC) | K     | party | (10,5,0)  | M        | pcs/kael     | 9/11    | 15 | poisoned 3r  |            |
| 12   | Thugs ×3  | T     | foe   | (25,15,0) | group r5 | srd:thug     | 7/11 ea | 12 | —            |            |
| 9    | Brute     | B     | foe   | (40,25,0) | L        | srd:ogre     | 30/30   | 13 | —            | reach 10   |

### Moves log (this round; cleared at round end, summarized into the session log)
- r2 Veskar: (0,15,0) → stairs → (0,25,10) → (5,30,10) — 15/30 ft ✓, no OAs
```

Column notes: `side` (party / foe / neutral) drives opportunity-attack checks. `size` is
T/S/M/L/H/G or `group rN`. `ref` points tools to the creature's numbers: a PC/NPC file
(no `.md`) or `srd:<monster>`. Conditions may carry a duration (`3r` rounds, `10m`),
which `combat next` / `clock` count down. `notes` may carry `reach 10`, `climb speed`,
`fly speed`. HP `0/x` renders as a lowercase (down) glyph on the map. Temporary HP is
written after the HP as `9/11 (+5 temp)` (a group: `7/11 ea`).

### Split party — `state/split.md` and parked scenes (02 → Splitting the party)

Exists only while the party is split; `split join` of the last two groups deletes it.
`state/current.md` always holds the **active** group's scene, so every scene, tempo
and combat tool works unchanged. Each waiting group's scene is parked in
`state/split/<group>.md`, the same format as `current.md` (its own
`in-game-datetime`, `party-location`, `scene`, `light`, On stage, Tempo, Combat).
`split cut` swaps them. Written only by `gm.py split`.

```markdown
---
active: mill
slice-round: 0                    # the combat round the active slice began in (0 = not in combat)
cuts: 3                           # cuts so far (the first prints the who-knows-what reminder)
---

# Split party

| group | pcs         | location            | time        | tempo  | sense |
|-------|-------------|---------------------|-------------|--------|-------|
| mill  | Grusk       | old-mill/main-floor | Day 1 21:10 | combat | auto  |
| inn   | Kael, Kira  | crossroads-inn/yard | Day 1 21:09 | calm   | auto  |

## Long tasks
- inn: search the stable loft (30m) — Day 1 21:05 → Day 1 21:35
```

PC `location:` stays single-sourced in the PC file (as now). `location`, `time` and
`tempo` are a snapshot refreshed on every `split` write; the brief reads the live
values from the scenes. `pcs` holds full PC names; a PC belongs to exactly one group.
`sense` is `auto` (worked out: same site, or route distance ≤ `split-sense-ft`, or a
special sense's range) or forced `on`/`off` by `split sense <group>`. The exchange
counter is hook scratch in `.gm/split-slice` (not canon, not undone).

**Settings** (campaign.md frontmatter, else `state/current.md`; defaults shown):
`split-exchanges: 3` (calm/tense slice cap), `split-combat-rounds: 6` (combat slice
when nobody can sense the fight), `split-sense-ft: 300` (how far a fight carries),
`split-max-ahead: 30` (minutes a group may run ahead of the others before a cut is
due; 1 while any waiting group is fighting).

### Scene state added by Phases 13–15 (02 → Table mechanics)

`current.md` frontmatter (parked split scenes carry the same keys):
```yaml
light: dark                       # still the AMBIENT light; carried sources are on creatures (lit:)
marching-order: {front: [Kael], middle: [Kira], back: [Grusk]}   # 14
weather-now: "light rain, light wind, cool"   # 15; rolled at dawn when weather: on (not `weather:`, the setting's key)
environment: extreme-cold         # 14; none | extreme-cold | extreme-heat | underwater | thin-air
environment-since: "Day 2 09:00"  # 14; when it was set (the hourly saves count from here)
party-location: "@lost"           # 14; off course in the wilds, with:
lost: "to hollow · at (1.2,7.5,0) world · bearing N (meant NE) · terrain forest · since Day 1 23:31"
```
- **Combatants `conditions`** gain `conc bless`, `dying ✓1 ✗2`, `stable`, `exh 2`,
  `hidden 17` (the Stealth total it must beat; out of combat it sits in the file's
  `conditions`), `fled` / `surrendered` (14: out of the turn order), `ready: shoot whoever opens the door`
  and `ctrl Kira` (an allied creature's controller). `notes` gains `leader` and
  `morale: fearless`. `side` is unchanged (familiars and hirelings are `party`).
- **Combat block** gains a line under the heading: `Ammo spent: Kira arrows 6 ·
  Grusk javelins 2` (13), and `Morale: thug (half HP) · thug (half the side down)` (14:
  each unit and trigger that has already asked for its check, keyed by the unit's
  singular name so a group splitting up doesn't ask again).
- **`## Chase`** (14) replaces `## Combat` while a chase runs (they don't overlap):
  ```markdown
  ## Chase — round 3 · up: Veskar · env: urban
  | name | role | pos ft | speed | dashes | exh | notes |
  |---|---|---|---|---|---|---|
  | Veskar | quarry | 140 | 30 | 1/3 | 0 | out of sight of Kira |
  | Kael | pursuer | 90 | 30 | 2/4 | 0 | |
  | Kira | pursuer | 100 | 35 | 0/5 | 1 | |
  ```
- **Traps** (14) are `## Hidden` lines with a `TRAP` tag:
  `- DC 15: TRAP pit (cellar) · trigger: step on the third stair · disarm: DC 12 thieves'
  tools · effect: DEX save DC 13 or fall 20 ft · state: armed` (`state`: armed |
  triggered | disarmed | spent; written by `gm.py trap`). The `(cellar)` after the id is
  the sub-area, like `DC 15 (cellar):` on any Hidden line (either place works). `effect:`
  clauses, joined by `;` or ` and `: `<ABIL> save DC N or <consequence>` (add `(half on
  a success)` for damage), `+N to hit, <damage>`, or a bare consequence: `fall N ft`,
  `NdM <type>`, or a condition (`poisoned 1h`). A `(GM: …)` note may sit anywhere on
  the line; it never reaches players.
- **Navigation** (14): a route row's `kind` (road / path / trail / trackless …) says
  whether a party can get lost on it (off the roads: `trail`, `trackless`, `marsh`,
  `scree`; never `road`, `street`, `path`, `lane`), and an area's or route's `terrain:`
  (grassland | arctic | desert | hills | forest | jungle | swamp | mountains | coast |
  sea) gives the navigation DC and foraging (`forage: abundant | limited | scarce`,
  default limited). On a route row they are a `terrain` / `forage` column or
  `terrain: forest; forage: scarce` in its `notes`; on an area (or the destination
  site) frontmatter keys. Area frontmatter `climate: temperate` drives weather (15):
  arctic | cold | temperate | warm | tropical | desert | mountain | coast, read on the
  party's site and then up its `parent:` chain. A site whose `type` is a building,
  dungeon, cave … or tagged `indoors`/`underground` is under a roof (weather effects off).
- **`state/social.md`** (14, unless `social-wall: off`): one row per open social goal,
  written by `check --vs … --goal`, removed on success:
  `| npc | goal | fails | approaches | pitches | since |`
  (`approaches` = the skills and arguments tried, so a "different approach" can be
  told; `pitches` = short tags of flair pitches already scored, so a repeat scores 0;
  `since` = game time of the first attempt). A split party shares it. A row whose goal
  is `—` is the NPC's pitch memory (flair pitches tried without a goal, or while the
  wall is off, so a repeat still scores 0). `npc` is the NPC's file slug.
- **`state/factions.md`** (15, `renown` on): `# Factions` and one table `| faction |
  renown | rank | who | notes |` (`who` = party or a PC's first name; `notes` = the last
  reason), written by `gm.py renown`; NPCs name theirs with `faction: red-ledger` (the
  faction's slug). A split party shares it.

## Table rules — `state/table-rules.md` (player overrules)

Written only by `gm.py rule` when someone invokes `/overrule` (02; honor-based). Read
by the tools (mechanical `key`s) and summarized in every brief.

```markdown
# Table rules
<!-- Active overrule rules. Precedence: these > rules/house-rules.md > RAW. -->

| id | rule                          | key            | scope                    | since  | status              |
|----|-------------------------------|----------------|--------------------------|--------|---------------------|
| R1 | Potions are a bonus action    | potion=bonus   | campaign                 | S1 t3  | active              |
| R3 | Crits on 19–20 for this fight | crit-range=19  | combat                   | S2 t14 | ended (combat over) |
| R4 | No travel encounters          | encounters=off | until we reach Thornbury | S2 t20 | active              |
```
`since` = session and turn. Ended rows are moved into the session history by
`session archive`. Campaign rules promoted at `/end-session` move to
`rules/house-rules.md` and leave this table.

## Spoiler record — `sessions/spoilers.md`

Append-only record of every `/spoilers` answer, written by `gm.py spoil log`.
Unlike the session log, it isn't reset each session: it's the permanent list of what
the *players* know out of character, which the GM consults so it doesn't keep facts
"behind the screen" that are already out.

```markdown
# Spoilers revealed (player knowledge, not character knowledge)

| when   | level | depth  | question                               | revealed                                         |
|--------|-------|--------|----------------------------------------|--------------------------------------------------|
| S2 t31 | major | answer | Was Mara lying about Harl?             | Yes — she fears something under the inn          |
| S3 t02 | none  | answer | What if we'd gone to the mill night 1? | what-if (not canon); no secrets beyond party knowledge |
```
What-if guesses are always recorded as "what-if (not canon)". This file never makes
anything a world fact.
`revealed` is a one-line summary of what was revealed, written so a later GM pass can
match it against secrets.

## Session log — `sessions/session-current.md`
Append-only, written by `gm.py` (06): each mutation adds a delta line to the open turn,
and `gm.py log "..."` writes the summary and closes it:
```
[turn 14] Kira buys Tobin a drink; cart story told
  - coin Kira 35→30 gp
  - attitude Tobin neutral→friendly
  - (GM) roll SECRET 1d20+2 = 9 (Mara insight vs Kira deception) — fail
```
`(GM)` marks delta lines players must not hear: secret rolls, off-screen moves, fired
clock beats, hidden-DC results. Recaps and history summaries leave them out.
Overrules log as public lines, e.g. `  - [overrule] rule R3 added: crits on 19–20 (combat)`
or `  - [overrule] retcon turn 14: Kira's climb went unseen`.
Spoilers log only the question and level publicly, e.g.
`  - [spoilers] major/answer: "Was Mara lying about Harl?"`.
The content goes to `sessions/spoilers.md`. Retcons of
past sessions also append an `Erratum:` line to that session's history file. The
original text is never edited.
`/end-session` compresses it into `sessions/history/session-NN.md` (a half-page summary +
list of durable changes made, which is the delta lines extracted).

## Tool-owned files
- `campaigns/.active` — name of the active campaign folder.
- `<campaign>/.gm/journal/` — undo before-images (last ~50 batches; not canon).
- `<campaign>/.gm/brief-hash` — brief change tracking (06).
- `<campaign>/.gm/drafts/<slug>.json` — in-progress character intake/level-up drafts
  (resumable; deleted on write).
- `<campaign>/.gm/session-id`, `<campaign>/.gm/client.log` — table client session to
  resume, and its denial/error log (never shown on the console).
- `<campaign>/tables/<slug>.md` — random/encounter tables, `| roll | result |`.
