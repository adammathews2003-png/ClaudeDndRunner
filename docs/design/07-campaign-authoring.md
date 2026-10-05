# 07 — Campaign Authoring, Scaled Difficulty and Campaign Mechanics

How a campaign gets built before play, by the same person who will then play it; two
play-loop changes every campaign gets (difficulty scaled to who's at the table, and the
danger-stone reading); and **campaign mechanics**: optional rule modules a campaign
switches on in `campaign.md`, of which the time loop is the first. Tools are specified
in 06 → Campaign authoring, encounters and mechanics; file additions in 04.

## The authoring problem

During play the driver's secrecy is the honor system plus a console that hides tool
output (01 → Secrets). Authoring is harder: the driver is the one asking for the
content, so if generation happens in their conversation they've read the villain's
plan before it's filed. **Decided (2026-10-04): generation runs in a forked context.**
Authoring skills hand the parameters and seed to a subagent that writes the campaign
files and returns only a player-safe **shape card**. The driver's conversation never
contains the truth, so there's nothing to not-read. Memory plugins are the known hole:
the table client already excludes them (06 → Table client), and authoring sessions
should run with them off.

## Parameters (`<campaign>/campaign.md` frontmatter)

```markdown
---
name: (generated or given)
slug: loop-play
length: 3-5 sessions
start-level: 3
players: up to 4
difficulty: hard            # the DMG ladder word the campaign aims at on average
shape: macguffin            # journey | boss | macguffin | mystery | sandbox | heist | siege (+ secondary)
secondary: [mystery, sandbox]
tone: comedic
weirdness: 3                # 1 grounded … 5 surreal: how strange the world is allowed to be
jokes: 3                    # 1 dry … 5 constant: how often a scene goes for a laugh
references: light           # none | light (≈1 in 4 named NPCs) | heavy
sidekick: either            # none | orphan | animal | either: an optional helper (below)
advancement: milestone      # milestone | xp: what triggers level-ups (04 → Advancement)
xp-tracking: on             # on | off: XP is awarded and kept even under milestone
xp-absent: full             # full | half | none of an award for absent PCs
wacky-juice: on             # on | off: random NPC chaos at the table (02 → Wacky Juice)
wacky-juice-value: 5        # % chance per eligible player prompt
wacky-juice-cooldown: 3     # player prompts before it can fire again
reveal-policy: paired       # shape-only | fill-in | outline | full | paired (see below)
mechanics: [time-loop]      # optional modules (below); empty for a standard campaign
seed-file: campaign-seed.md # the driver's own words, kept verbatim
status: outlined            # outlined | generated | in-play | finished
---
```

**Weirdness and jokes** are separate dials. Weirdness is about the world (a castle on
a chain is 2; a castle that is late is 4); jokes are about the scenes (how often NPCs,
situations and loot go for a laugh). Both are read by the generator per scene: at 3, one
in three scenes has a deliberate bit; at 5, every scene does and the world stops
apologising. The driver's seed words set the starting values; a critique like "more
weirdness" moves the dial, not individual jokes.

**Sidekick** (`sidekick:` not `none`): the generator places one obvious-to-adopt helper
near the opening, an orphan or an animal (or one of each when `either`, with the party
choosing). The sidekick is never required, but somewhere in the campaign there is a
**sidekick clause**: a place or beat where the sidekick has a use that becomes apparent
only on arrival (the dog smells the hollow wall; the orphan knows the kitchen door),
and the same obstacle can be solved without them at a cost (a harder check, a fight, a
lost hour). Rules: the sidekick has a statblock and a `## Sidekick` section in their
NPC file (what they're good at, what they're afraid of, the clause's location as a GM
note); they are never the solution to the campaign itself; they can die, and in a loop
campaign they reset like everyone else unless carried as a "possession" (a loop-campaign
joke the generator may use). The shape card names the sidekick and nothing else.

Length → level range by milestone pacing (3–5 sessions ≈ 2 levels; 8 ≈ 4; 20 ≈ 9).
Difficulty is a ladder word, never a CR: the tools turn it into a budget for whoever is
at the table (below). `shape` picks a structural template that says what must exist:

| shape | must exist |
|---|---|
| journey | a route with stops, a reason to keep moving, a destination that changes |
| boss | a threat ladder (lieutenants → lair → reveal), a way to learn the boss's weakness |
| macguffin | the pieces, where each is, who else wants them, what assembling them does |
| mystery | truth, clue chain with redundancy, suspects, a clock (the POC pattern) |
| sandbox | a hub, 5+ hooks of mixed difficulty, factions that react |
| heist | the prize, the place, the crew's leverage, the twist |
| siege | the thing to hold, the waves, the way out |

## Reveal policy

One global level, with optional per-topic exceptions in `campaign.md ## Reveal
exceptions`. What the driver sees is recorded in `## Author ledger` so the GM knows
what the driver already knows (the mirror of `sessions/spoilers.md`).

| policy | the driver sees | stays in files |
|---|---|---|
| shape-only | the shape card: premise, opening, known places, perceived stakes, settings | everything else |
| fill-in | shape card + the fill-in queue (names, looks, a PC tie-in) and their answers | truth, twists, beats, clocks, NPC secrets |
| outline | the arcs and milestones, who the factions are, not what they're doing | the why, the twist, the dungeons' contents |
| full | everything; the driver is a co-author and plays knowingly | nothing |
| **paired** | **two distinct campaigns from one seed: A fully revealed for critique; B secret and played. Criticisms of A become rules applied to B unseen** | B entirely |

`paired` is the first campaign's policy. The second generation must be *distinctly*
different from the first (different answer to why, different villain shape, different
piece locations, different looper secret), not a reskin, or the critique leaks.

## Skills (separate from the GM set)

| skill | does |
|---|---|
| `/campaign new <seed>` | intake: extract parameters and constraints from the seed (the driver's words are promises, like world constraints), ask only for what's missing in one grouped message, write `campaign.md` + `campaign-seed.md`, then **fork** the outline generation → shape card |
| `/campaign scenario [arc]` | **fork**: expand the next arc into scenario, NPC, location and table files with encounter budgets and threat metadata → shape card for that arc. One arc at a time so later arcs react to play |
| `/campaign fill` | work through `## Fill-in queue` with the driver; answers go to files via `gm.py campaign fill <id> "<answer>"` |
| `/campaign status` | the campaign at the driver's reveal level: what's generated, what's outlined, the ledger |

What the generator produces for a new campaign: `campaign.md`, `locations/world.md`
(known-not-placed rows and frontier leads from the seed), the starting area and its
sites, the NPCs the opening needs, the first scenario, `tables/`, `state/current.md`,
`state/loops.md` when the campaign loops, and threat metadata on every adventure place.
Everything secret goes under the marked sections (04 → player-safe frontmatter).

**The shape card** (returned to the driver): premise as players hear it; opening scene;
places the party knows and the frontier leads; stakes as the party can perceive them;
length/difficulty/level settings; the fill-in queue. Never: truth, twists, beats, clocks,
NPC secrets, dungeon contents, piece locations.

## Difficulty scaled to the table (play-loop change)

Encounters are **authored as budgets, built at scene time**. A scenario or location line:

```
- ENCOUNTER hard "goblin raiders": goblin ×n, goblin boss, worg     # template; n scales
- ENCOUNTER fixed L5 deadly "the ceremony": <roster>               # never rescaled
```

**The difficulty word is pinned to the campaign's `start-level`.** A template's word
gives it an *absolute* XP budget (2014 DMG thresholds at `start-level` for the
campaign's nominal party of 4, times the monster-count multiplier: 1 ×1 · 2 ×1.5 · 3–6
×2 · 7–10 ×2.5 · 11–14 ×3 · 15+ ×4). That budget is the place's `threat.xp`, and it
never changes. Decided (2026-10-04) after both generated campaigns hit the same
contradiction: if the word were re-evaluated at the party's current level, a place would
stay "hard" forever while the danger stone said it had turned green, and levelling would
feel like nothing.

`gm.py encounter build "<name>"` fills the roster for the PCs **present**, keeping the
template's absolute budget but adjusting the *count* (`×n`) for **table strength**, not
level: the party's effective size = number present, shifted one step up under 3 and one
down over 5, then scaled by **item power** (below). A 2-PC night gets a 2-PC version of
the same fight; a well-equipped party gets the full roster. Level is what the stone
tracks: as the party levels, the same places get easier, and that is the progression.
`fixed` encounters are built once at their stated level and party size and never
rescaled: they are walls until the party is ready, which is what the danger stone is for.

**Item power.** Permanent magic items count toward table strength: uncommon ¼,
rare ½, very rare 1, legendary 2 "virtual levels", summed over the party and divided by
the number present; the result shifts the party's thresholds (used by both `build` and
`danger`) by that many levels, rounded to the nearest half-step. `gm.py encounter
budget` prints it (`power +0.5 (2 rare, 3 uncommon)`); the GM can override with
`--power`. Getting cool items is meant to show: a party that has looted well reads green
where it used to read yellow.

## Custom monsters

The SRD is a floor, not a ceiling. When a scene wants a creature the SRD doesn't have (a
yeti, a flameskull, the queen's clockwork hounds), the author makes one by **copying the
closest SRD monster and re-theming it**: `gm.py monster new "Frost Yeti" --from "polar bear"`
writes an editable stat block with every number, trait and attack; rename the attacks,
add a damage rider or a trait that fits the theme (cold claws, ice walking, a fear of
fire), adjust resistances, set `cr`/`xp` by the DMG's rough math (damage per round and
HP decide the CR), and write a Description and a **Backstory**. A unique creature (a named
yeti with a grudge) is a custom monster too, with its own file in the campaign's
`bestiary/`; reusable species go in the shared `bestiary/`. Generators should prefer a
memorable custom creature over an off-the-shelf one whenever the theme asks for it, and
must never name a monster that is neither SRD nor in a bestiary (`lint` warns).

## Items, loot and merchants

Loot is authored into places, not improvised, so becoming formidable is something the
sandbox rewards on purpose. Three sources:

1. **Placed loot** (`## Loot` table in a location file, 04): fixed items with a `where`
   (sub-area or feature id), a `guard` (encounter name or check), and `kind:
   campaign | treasure | consumable`. *Campaign* items are unique and tied to the story
   (the pieces, a key); *treasure* is the cool stuff (a named weapon in the dungeon's
   armoury); *consumables* are potions, scrolls, ammunition. The generator places at
   least one treasure item in every yellow-or-harder place and a consumable or two in the
   green ones, so every reading on the stone has something behind it.
2. **Random loot** (`tables/loot-<tier>.md` and `tables/loot-<place>.md`, `| roll |
   result |`): rolled by `gm.py loot roll <table>` when a `## Loot` row says `random:
   <table>` or the GM wants a drop. Tiers follow the DMG hoard tables by level band
   (1–4, 5–10), filtered to SRD items.
3. **Merchants.** A merchant is an NPC with a `## Stock` table (04). Two kinds: **set**
   (fixed list, fixed prices, restocks per `restock`) and **random-ish** (a short fixed
   core plus `random: tables/stock-<merchant>.md` rows re-rolled on restock). A campaign
   has at least three: one set weapons/armour shop, and two random-ish merchants with
   different specialities (e.g. a curiosities dealer and an apothecary). Prices follow
   the DMG rarity bands; `gm.py shop <merchant> [--buy <item>] [--sell <item>]
   [--restock]` moves coin and items through the existing `coin`/`item` mutations. In a
   time-loop campaign, every reset is a restock (and coin spent comes back, which the
   generator may play for comedy, but items bought are carried and persist).

Rarity caps by level band keep the stone honest: through L4, uncommon with one rare
behind a red-at-L3 reading; L5+, rare freely, very rare only as campaign items.

## The danger stone (play-loop change)

A reading, never a label. Every adventure place carries `threat: {xp: N, fixed: false}`
in frontmatter, where `xp` is the adjusted XP of its hardest authored encounter (the
authoring tool computes it; `fixed: true` when that encounter is fixed). `gm.py danger
<place>` (or `--bearing N` for "pointing the stone north", which uses the world
geometry) compares `threat.xp` with the present party's thresholds:

- **green**: ≤ the party's *medium* total
- **yellow**: ≤ the party's *deadly* total
- **red**: above deadly, or `fixed` above the party's **unshifted** level (item power
  moves the XP thresholds, never the level a fixed wall is keyed to)

The GM narrates the colour; players never hear numbers. Because it's derived, levelling
up changes readings everywhere at once, which is the open-world steer the stone is for.

## Campaign mechanics (optional modules)

A mechanic is a rule module that is **not** part of the standard game: a campaign
declares it in `mechanics:`, and only then do its tools exist, its skill text loads
into `/gm`, and lint checks its files. The default campaign has none. Each mechanic
has its own section here; the first is the time loop, written so another campaign can
reuse it unchanged. Adding a mechanic later means adding a section here, its commands
to 06 under the same name, and a `mechanics/<name>.md` rules sheet the `/gm` skill
includes when the campaign lists it.

### Time loop (`mechanics: [time-loop]`)

The world resets; the PCs don't. State lives in files and the repo is git, so:

- `gm.py loop start` at the loop day's first moment: commits, and records the commit in
  `current.md` as `loop-baseline: <sha>` with `loop: 1`, `loop-start: "Day 1 06:00"`,
  `loop-end: "Day 2 00:00"`.
- `gm.py loop reset [--by death|sleep|time]`: restores every file under `locations/`,
  `npcs/`, `scenarios/`, `tables/` and `state/current.md`'s world facts from the
  baseline; sets the clock to `loop-start`; moves the PCs to their `loop-bed` location
  at full HP, no conditions; increments `loop`; appends a row to `state/loops.md`
  (`| loop | ended by | learned | gained | notes |`, written from the session log's
  deltas since the last reset). **Never touched:** `pcs/` (items, levels, journals
  persist), `state/loops.md`, `sessions/`, `campaign.md`. The session log gets a
  `(GM) loop N reset (death)` line and a public `[loop]` line.
- Triggers: death of the whole party, sleep, or the clock reaching `loop-end`. A single
  PC's death is a GM call (default: they wake in bed at the next reset, having "missed"
  the rest of the day).
- NPCs don't remember. One NPC may carry `## Memory across loops` (what they recall of
  the party from previous loops; the GM appends per loop). The GM remembers everything
  via `loops.md` and uses it to keep the world consistent across loops ("the guard still
  sneezes at 09:10").
- Pieces that persist: a carried piece survives the reset; the world's copy regenerates
  but is inert (`notes: duplicate; hollow`). `loop reset` marks regenerated pieces
  already in a PC's inventory as hollow.
- `trace` and `/spoilers` treat each loop as its own day (`Loop 3 · Day 1 09:10`).
- Rules sheet for the table: `rules/mechanics/time-loop.md` (what players are told:
  carried things and themselves persist; everything else resets; death or sleep ends
  the day). `/gm` includes it only when the campaign lists the mechanic.

## Fill-in queue and author ledger (`campaign.md` body)

```markdown
## Fill-in queue
| id | question | default | status |
|----|----------|---------|--------|
| F1 | Name of the kingdom (3 candidates: …) | Hollowmere | open |

## Author ledger
| when | what the driver was told | via |
|------|--------------------------|-----|
| 2026-10-04 | shape card for arc 1 | /campaign new |
```

The queue holds only things the generator *chose* to leave open (names, looks, a PC
tie-in it wants permission for). Answers are promises; the generator honours them in
later arcs.
