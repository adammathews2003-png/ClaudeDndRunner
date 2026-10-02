# 02 — GM Agent & Skills Design

## How the GM is packaged

The GM is a set of **Claude Code skills** plus a campaign-level `CLAUDE.md` that loads the
core protocol every session. Skills to build in phase 2:

| Skill | Trigger | What it does |
|---|---|---|
| `/gm` (core loop) | start of play / each session | Loads GM protocol, sets `in-session: true` (turns on the brief hook), runs the turn loop |
| `/scene` | party enters new location or major shift | `gm.py scene enter <loc> --write` → refine On stage goals → narrate establishing exposition (short/medium/long) |
| `/travel` | party moves between locations | `gm.py travel <to>` (connection, time, encounter roll, scene packet) → narrate |
| `/combat` | initiative starts | `gm.py combat start` → map → turn-by-turn with `atk`/`dmg`/`cond`/`combat next` |
| `/map` | combat start, or a player asks | `gm.py space map --from <active>` and shows the grid + legend |
| `/end-session` | wrapping up | Writes summary + world tick, `gm.py session archive` (history, lint, git commit) |
| `/new-campaign` | scaffolding | Creates a campaign folder from the templates in 04-file-formats.md, sets `.campaign` |

The main `/gm` skill's instructions ARE the Game Master brain — the sections below are
what goes into it. Every mechanical step goes through `tools/gm.py` (spec: 06). The
skills say *when* to call a command, and the tools do the math and the file writes.

## Exposition pacing

On every scene the GM chooses short (2–4 sentences), medium (1–2 paragraphs), or long
(3+ paragraphs) exposition based on: novelty of the location, story weight, and whether
players are mid-task. Every narration block ends in an *affordance* — either an NPC
notices/engages the party, or an explicit opening for player action ("the ledger sits
open on the desk; Mara has her back turned"). Never narrate the players' own choices.

## When to call for checks (the core GM judgment)

- **Auto-succeed:** trivial actions, or anything where failure would be boring and stakes are nil.
- **Call for a check:** uncertainty + meaningful stakes. Name the check and DC band
  (Easy 10 / Medium 15 / Hard 20 — see rules/checks-and-dcs.md), let players roll or
  ask the GM to roll.
- **Passive Perception (rules/perception.md):** every PC file carries passive Perception
  in frontmatter. When the party enters a scene, hidden-detail DCs (listed in the
  location file under `## Hidden`) are compared against passive scores (`gm.py scene
  enter` does the comparison, including light), and the GM *volunteers* what qualifying
  PCs notice. No roll is requested; it just appears in the narration addressed to that
  character.
- **GM-prompted rolls:** when something dangerous/interesting is near but not automatic
  ("Kira, give me a Perception check"), the GM asks for the roll *before* revealing why.
- **Secret rolls:** for checks where asking would itself be a spoiler (e.g., noticing a
  pickpocket), the GM rolls silently and narrates only outcomes.

## Dice

Default: **players roll their own d20s and report totals; the GM rolls everything else**
(NPC attacks, damage, secret checks, random tables). GM rolls go through `gm.py roll` /
`atk` / `save` / `check` / `contest` (06), which use a real RNG and also do the
arithmetic, crits and the ties-go-to-PC rule. Results are never "picked" or added up by
the model, so outcomes are honest. Player-reported rolls go into the same commands
(`--d20 12` or `--total 19`). The GM pastes the tool's bracket line into narration
(`[Veskar → Kael: 13+5=18 vs AC 15 — HIT · 7 slashing]`), except for secret rolls.
`dice-mode: gm-rolls-all` in `current.md` switches to the GM rolling everything.

## NPC decision-making

Each turn, present NPCs act from three inputs, in priority order:
1. **Scene goal** (from the digest — what they're trying to do right now)
2. **Disposition + personality** (from their NPC file: traits, bonds, fears)
3. **Faction motivation** (from the scenario doc — only consulted at decision points
   flagged in the digest's "watch for" list)

NPCs must be allowed to: refuse, lie, have off-screen lives (scenario doc can schedule
NPC movements between locations), and react to reputation (NPC files log notable past
interactions with the party under `## History with the party`).

## Combat mode

Combat swaps the freeform loop for structure, tracked in a `## Combat` block inside
`state/current.md` (format in 04): initiative order, position, HP / AC / conditions per
combatant, round count, terrain, and a moves log. Monster stat blocks come from the local
SRD data (`gm.py srd monster <name>`, 06), not model memory. A named NPC's block is
written into their file the first time it's used (`--write`), so later edits stick.
Lifecycle: `combat start` → `atk`/`dmg`/`cond`/`space move` per turn → `combat next` →
`combat end`. Keep POC combat simple (few combatants, basic actions) before layering in
complexity.

## Spatial model (theater of the mind, backed by coordinates)

Players describe intent in fiction ("I rush the archer on the landing"); the GM keeps
the geometry honest underneath.

**Store positions, never distances.** Every combatant and every terrain feature that
matters gets one `(x,y,z)` in feet (multiples of 5 = a 5-ft cell's center). Distances
are derived on demand: `max(|dx|,|dy|,|dz|)` (rules/combat-basics.md). A pairwise
distance table is forbidden: it's O(n²) and the GM *will* write contradictory entries.

**When positions get logged:**
1. **Tense scene** (01, Scene tempo): when tempo goes tense, `gm.py tempo tense` writes
   a Stage table (04) and the GM gives each on-stage creature a `pos`, using the
   location's `## Layout`. That's one argument per creature, and combat starts with
   everyone already placed.
2. **Combat start:** `gm.py combat start` opens the `## Combat` block. It copies the
   layout's bounds/origin and terrain rows, promotes the Stage table's positions, and
   rolls initiative. The GM trims terrain to what's relevant (exits, cover, elevation,
   hazards, difficult terrain).
3. **Lazily, as play touches things:** "I dive behind the ale barrels" — if the barrels
   aren't logged, the GM checks the location description allows them, places them
   plausibly, and adds a terrain row. If it's a permanent feature, also add it to the
   location's `## Layout`.

**Consistency rules:**
- **Once logged, a feature never moves for convenience.** Only fiction moves it (kicked
  table, collapsing beam), and that's a logged move like any other.
- **Positions change only through the moves log.** Each move: start → waypoints → end,
  cost vs. speed (difficult terrain/climbing ×2), opportunity attacks provoked. One line.
- **First fight in a place writes its `## Layout`.** Every later fight there starts from
  it, so the tavern is the same shape in session 1 and session 9.

**Telling players distances.** The GM always works with exact numbers internally. What
players hear depends on whether their *character* could reasonably judge it:
- **Exact** ("Veskar is 25 ft away, 10 ft up") — the character can see the target in
  adequate light, and it's within ~120 ft, or it's something they've measured/paced.
- **Rough band** otherwise — heard-not-seen, darkness, fog, far off, or obscured. Bands:
  *adjacent* (5) · *close* (≤30) · *nearby* (≤60) · *far* (≤120) · *distant* (beyond).
  e.g. "footsteps above you, somewhere toward the stairs — close."
- Mechanics still use the exact value (an attack at an unseen target uses true range).

**Narration:** prose first; mechanics in brackets only where they matter —
"You take the stairs two at a time *[25 ft — that's your move]*." Players can always ask
"how far?" and get an answer per the rule above.

### Tools & add-ons

(Full tool set: 06-tools-spec.md. The spatial pieces are below.)

- **`tools/space.py`** (also `gm.py space ...`) reads the Combat block and does the math the GM shouldn't do by
  hand: `dist`, `move` (cost, over-speed, opportunity attacks, unplanned drops), `cone`,
  `line`, `sphere`, `emanation` (who's in the area), and `map`. Use it for anything
  beyond a simple distance; mental math is fine for "is the goblin within 5 ft?".
- **ASCII map** (`/map` → `space.py map --from <active>`): top-down grid drawn from the
  terrain and combatant tables, north up, legend with each combatant's position, height
  and distance from the active combatant. Shown at combat start, on request, and
  whenever the layout changes meaningfully. Because it's generated from state, it can't
  disagree with state. Add `--show` to any area command to overlay the affected cells.
- **Groups/swarms:** identical minions that move together can share one row with
  `size: group r5` (they fill every cell within r of `pos`). Split a member into its own
  row the moment it does something different.

## Failure & tone guardrails

- Fail forward: a failed check changes the situation, it doesn't dead-end it.
- The GM never controls PC dialog or decisions; it may narrate involuntary consequences.
- Rulings over rules: when a rule lookup would stall the scene, make a sensible ruling,
  note it in the session log, reconcile later.

## Timeliness rules (what keeps turns fast)

1. Normal turns need **zero file reads**: the `UserPromptSubmit` hook injects
   `gm.py brief` (06). All of a turn's mechanics and writes go in **one**
   `gm.py do "..."` call, and that call writes the session log too.
2. Narrate from the tool output. Don't Read+Edit game files during play; if no command
   covers a change, note it with `log` and add the command later.
3. Background subagents only for slow multi-file work (world tick, big doc rewrites).
   Ordinary writes are cheaper through `gm.py` than spawning an agent.
4. Scenario/rules files are read on trigger, not on schedule.
5. `/end-session` compression keeps every hot file small.
