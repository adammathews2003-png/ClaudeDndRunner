# 04 — File Formats & Templates

Every game file uses YAML frontmatter for machine-scannable facts (grep-able without
reading the whole file) and markdown body for prose. Frontmatter fields are the contract;
body sections are conventions.

**Parsing contract (tools read and write these files, see 06):** frontmatter uses only
`key: scalar`, `key: [inline, list]`, `key: {one: 1, level: 2}` (one-level inline map),
`# comments` and quoted strings. No nested blocks or multi-line values. Anything richer
goes in a markdown table in the body. Tables are read by header name, so extra columns
are always safe.

**Frontmatter is player-safe.** It's the first thing anyone sees in a file, and tools
print it freely, so it holds only the public face of things (e.g., an NPC's cover
`role` and public `faction`). True identities and allegiances go under the marked
secret sections (`## Knowledge & secrets`, `## The truth`, `## Hidden`).

**Anchor times to days.** Body text that says "two nights ago" goes stale as the clock
advances, so add the absolute day: "two nights before the party arrived (night of Day
-1)". Pre-campaign days are numbered ≤ 0. This also lets `gm.py trace` and `/spoilers`
treat them as Established facts.

## Location file — `locations/<slug>.md`

```markdown
---
name: The Crossroads Inn
type: building          # region | settlement | building | room | wilderness | dungeon
region: thornbury       # parent location slug, if any
tags: [social, safe]
---

# The Crossroads Inn

## Description
Sensory prose the GM can draw exposition from. 1–3 paragraphs.

## Connections
- **Thornbury village square** — out the front door, 2 min walk, obvious
- **Stable yard** — side door past the kitchen, 1 min, obvious
- **Cellar** — trapdoor behind the bar, locked (Mara has the key), not obvious (DC 12 Perception)

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
<!-- Written the first time a tense scene or fight happens here; fixed afterwards.
     Only features with spatial/mechanical weight. One block per area for multi-room places. -->
### common-room
Bounds: x 0–45 · y 0–35 · z 0–10 · origin (0,0,0) = inside the front door, SW corner · +x east · +y north · +z up · ft

| id     | glyph | feature     | from      | to        | effect                           |
|--------|-------|-------------|-----------|-----------|----------------------------------|
| bar    | b     | bar counter | (15,25,0) | (35,25,0) | half cover; crossing = difficult |
| stairs | s     | stairs up   | (0,15,0)  | (0,25,10) | stairs up to landing (z 10)      |

## Notes / current state
Running changes: damage, moved items, ambience shifts. GM appends here.
```

Layout/terrain tables are the same format everywhere (location Layout, Combat block) so
`tools/space.py` can read them and the GM can copy rows across. `from`/`to` are opposite
corner cells (inclusive); a single cell has `to` = `from`. `effect` is free text, but the
helper keys on the words *difficult*, *stairs*, *ramp*, and *secret* (left off
`--player-view` maps until the party discovers it; then the word is removed).

Who-is-here is NOT stored in the location file — it's derived by grepping NPC/PC
frontmatter for `location: <slug>` (single source of truth for positions).

## NPC file — `npcs/<slug>.md`

```markdown
---
name: Mara Fennick
location: crossroads-inn      # slug; updated whenever she moves
role: innkeeper
faction: none
attitude-to-party: neutral    # hostile | wary | neutral | friendly | ally
statblock: commoner           # SRD name, or "custom: see below"
default-goal: keep the evening calm   # optional; seeds the On stage line on scene entry
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
<!-- Machine-readable schedule lines first (gm.py clock applies them); prose after. -->
- 05:00–18:00 → crossroads-inn (kitchen)
- 18:00–00:00 → crossroads-inn (bar)
Scenario-driven or conditional moves in prose ("if suspicion rises, leaves by night").
```

Custom stat blocks (`statblock: custom`) use the same `mods`/`prof`/`saves`/`skills`
frontmatter and `## Attacks` table as PCs, below.

## PC file — `pcs/<slug>.md`

```markdown
---
name: Kira Thornwood
player: Alex
location: crossroads-inn
class: rogue
level: 3
hp: {current: 24, max: 24}
ac: 14
passive-perception: 15        # GM reads this every scene entry
passive-investigation: 13
speed: 30
conditions: []
mods: {str: -1, dex: 3, con: 2, int: 1, wis: 1, cha: 0}
prof: 2
saves: [dex, int]                 # proficient saves
skills: {stealth: 7, perception: 5, sleight-of-hand: 5}   # totals, only the ones used
senses: []                        # e.g. [darkvision 60]
hit-dice: {die: d8, left: 3}
autopilot: follows the group, defends herself, makes no major decisions
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

## Features & abilities
Sneak Attack 2d6, Cunning Action, Thieves' Cant... (summarize non-SRD content here too)

## Inventory
- Equipped: leather armor, 2 daggers, shortbow (20 arrows)
- Pack: thieves' tools, 50 ft rope, 35 gp

## Background & story
Short backstory + goals the GM can hook.

## Journal
GM appends durable character developments here.
```

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
party-location: crossroads-inn
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
Map: crossroads-inn / common-room (layout: locations/crossroads-inn.md)
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
`fly speed`. HP `0/x` renders as a lowercase (down) glyph on the map.

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
- `dnd-adventure/.campaign` — name of the active campaign folder.
- `<campaign>/.gm/journal/` — undo before-images (last ~50 batches; not canon).
- `<campaign>/.gm/brief-hash` — brief change tracking (06).
- `<campaign>/.gm/session-id`, `<campaign>/.gm/client.log` — table client session to
  resume, and its denial/error log (never shown on the console).
- `<campaign>/tables/<slug>.md` — random/encounter tables, `| roll | result |`.
