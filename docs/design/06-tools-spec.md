# 06 — Tools Spec (scripts that take work off the GM model)

Status: **planned, not built** (except `engine/space.py`). Build in Phase 2a, before the
GM skills — the skills are written against these commands. Play runs through the
**table client** (`engine/table.py`, last section before Format changes), which shows
the player only the GM's narration; everything in this doc happens behind it.

## Why

`engine/space.py` set the pattern: the model decides *what* happens; a script does the
math and reads state from the files, so it can't disagree with them. This doc extends
that to the whole turn loop. A turn today costs far more than the "one read + one
append" in 02 → Timeliness rules:

- **Dice:** one `Get-Random` call per die, then the model adds modifiers, applies the
  ties-go-to-PC rule, compares to AC, doubles crit dice. Slow, and arithmetic is where
  models quietly err.
- **Read-before-Edit tax:** Claude Code's Edit tool refuses a file not Read this
  conversation. One hit = HP change + condition + log line ≈ 6 tool calls over 3 files.
- **Scene entry:** location + grep for who's here + each NPC/PC file + scenario = 5–8
  reads, then a hand comparison of `## Hidden` DCs vs. passive Perception.
- **Time:** `"Day 1, evening"` can't be computed with, so clocks and NPC schedules rely
  on the model remembering to check them.

## Design principles

1. **One entry point:** `python engine/gm.py <command> ...`. One permission rule, one
   thing for skills to learn. `space.py` stays standalone and is also reachable as
   `gm.py space ...`.
2. **Batch a whole turn into one shell call:** `gm.py do "atk Veskar Kael; dmg Kael 7; log ..."`.
   Commands run in order, left to right; a failing command stops the batch and reports
   which step failed (earlier steps stay applied and are listed).
3. **Scripts write the files.** Mutations go through `gm.py`, never through Read+Edit.
   Writes are atomic (write temp file, rename). Files remain canonical (05 #1).
4. **Every mutation auto-logs a delta** to the session log's open turn block. "If it
   happened, file it" stops being a discipline and becomes a side effect.
5. **Output is written for the model to paste:** short fixed-format bracket lines, e.g.
   `[Veskar → Kael: d20 13+5=18 vs AC 15 — HIT · 7 slashing · Kael 9→2/11]`.
   No JSON unless `--json` is passed (for tests and tool-to-tool use). Tool output is
   for the GM, not the players: the table client never displays it. Lines that are
   safe to repeat to players verbatim (public rolls, the player-view map) are the
   only ones the GM pastes into narration. Everything else is paraphrased in fiction
   or kept behind the screen (02 → Behind the screen).
6. **Python 3 stdlib only.** No install step. RNG = `random.SystemRandom`; `--seed N`
   on any command makes it deterministic for tests. (Sole exception: the table client,
   which needs the Claude Agent SDK. The game tools never import it.)
7. **Judgment stays with the model** (see the last section). Tools never decide whether
   a check is needed, what a DC is, or what an NPC wants.
8. **Fast:** every command should finish in < 200 ms (Python start-up is most of it).

### Campaign selection
`campaigns/.active` holds the active campaign folder name (`poc`). Every command
defaults to it; `--campaign <dir>` overrides. `/new-campaign` and `/gm` set it.

### Names
Commands take a creature by display name, slug, or unique prefix (`Kael`, `veskar`,
`mara`). Resolution order: Combat block rows → On stage / Stage rows → `pcs/` → `npcs/`.
Ambiguous → error listing the candidates.

## Code layout

```
engine/
├── gm.py              # entry point: argument parsing, `do` batching, dispatch
├── space.py           # existing — spatial math + map (also: gm.py space ...)
├── lib/
│   ├── md.py          # frontmatter + markdown table read/write (shared with space.py)
│   ├── campaign.py    # locate files, resolve names, load PC/NPC/monster records
│   ├── dice.py        # expression parser, adv/dis, crits, SystemRandom
│   ├── resolve.py     # hit/save/check/contest outcomes, incl. ties-go-to-PC (one place)
│   ├── journal.py     # undo before-images + session-log delta writer
│   ├── gametime.py    # "Day N HH:MM" parse/format/add
│   └── geo.py         # frames: site/area/world placement, offsets, routes, bearings, bands
├── scene.py  combat.py  clock.py  travel.py  rest.py  lint.py  session.py  srd.py  pc.py
├── table.py           # table client: the players' console (Agent SDK; not imported by the above)
└── tests/             # fixture campaign + seeded tests per command
data/srd/              # SRD 5.1 JSON (monsters, spells, conditions) + LICENSE/attribution
```

`scene.py`, `combat.py`, etc. are modules that `gm.py` dispatches to; they can also be
run directly.

### Parsing contract (`lib/md.py`)
To stay dependency-free (decided: no PyYAML), frontmatter is restricted to a YAML subset:
`key: scalar` · `key: [a, b]` (inline list) · `key: {a: 1, b: 2}` (one-level inline map,
whose values may be inline lists: `{spell: bless, on: [Kael, Kira]}`) · `# comments` ·
quoted strings. **No nested blocks, no multi-line values.** Anything
richer goes in a markdown table in the body (Attacks, Resources). Writers preserve
comments, key order and untouched lines byte-for-byte. `lint` flags frontmatter outside
the subset.

Tables are parsed by header name, so extra columns never break a reader (space.py
already works this way).

## Tier 1 — every turn

### `gm.py roll` — dice
```
gm.py roll 1d20+5            → [1d20+5: 14+5 = 19]
gm.py roll 1d20+3 adv        → [1d20+3 adv: (6, 17)→17+3 = 20]
gm.py roll 2d6+3 crit        → [2d6+3 crit: 4d6 (2,5,6,1)+3 = 17]
gm.py roll 3d6 --secret      → [SECRET 3d6: 11]   (logged as secret)
gm.py roll table:mill-road-encounters
```
- Expressions: `NdM`, `+/-` constants and further dice, `adv`/`dis`, `crit` (doubles
  dice, not modifiers), `kh/kl` (keep highest/lowest), `x3` (repeat).
- `table:<slug>` rolls on a markdown table in the campaign's `tables/` folder
  (`| roll | result |`, ranges like `1-3`).
- `--secret`: output prefixed `SECRET`, logged as a `(GM)` line. The GM narrates only
  the outcome, or just `[rolled behind the screen]` (02 → Behind the screen).

### `gm.py atk | save | check | contest` — resolve, apply house rules
```
gm.py atk Veskar Kael [--with scimitar] [adv|dis] [--cover half]
gm.py atk Kael Veskar --d20 12 [--with shortsword]    # player reports the natural roll
gm.py atk Kael Veskar --total 19                       # or the total
gm.py save Kael dex 14 [adv|dis]                       # GM-rolled or --d20/--total
gm.py check Mara insight 12 --secret
gm.py contest Kira stealth Mara perception --d20 15    # --d20 applies to the PC side
gm.py contest Kira stealth passive                     # vs. everyone's passive Perception on stage
```
- Bonuses come from: Attacks table / ability mods / skills in PC & NPC files, or the SRD
  stat block named by `statblock:` / the combat row's `ref`.
- **`lib/resolve.py` is the only place outcome rules live:** nat 20/1 on attacks, crit
  dice doubling, cover AC, active table-rule keys (overrules, below), and the full
  **ties-go-to-PC** rule set from `rules/house-rules.md` (NPC roll = PC AC → miss; contest tie → PC; NPC check = PC
  passive → PC wins). The output names a tie explicitly (`— MISS (tie→PC)`) so the GM
  can narrate it.
- **Margin:** `check`, `save` and `contest` end with the margin, e.g. `— SUCCESS by 6`
  / `— FAIL by 3` (a tie shows `by 0` with its tie note). The GM reads the outcome tier
  from it (02 → Player plans: beat by 5+, fail by 5+).
- Players roll their own d20s (02 → Dice): PC-side commands take `--d20` (the tool
  adds the bonus) or `--total`. Without either, the tool rolls only if
  `dice-mode: gm-rolls-all` is set in `current.md` frontmatter.
- `atk` on a hit rolls damage (doubled on a crit) and **applies it** unless `--no-apply`.
  Player-rolled damage: `dmg Veskar 8`.
- `atk` checks range/reach with `space.py` when both creatures have positions and
  reports `out of reach (15 ft)` instead of resolving.

### `gm.py` state mutations
| Command | Effect | Writes |
|---|---|---|
| `hp Kael -6` / `hp Kael +4` / `hp Kael =11` | HP change; clamps 0..max; temp HP absorbs first; `+temp 5` | combat row, else PC/NPC frontmatter |
| `dmg Veskar 8 [fire]` | alias for `hp -8`; reports resistance/immunity from the stat block | same |
| `cond Kael +prone` / `-prone` / `+poisoned 1m` | add/remove a condition; optional duration (rounds `3r`, minutes `10m`) | combat row / frontmatter `conditions` |
| `move-npc veskar old-mill` / `… crossroads-inn/cellar` | sets `location:` (site or site/area; both must resolve, area must be in the site's `## Areas`); drops them from On stage if they left the scene | NPC frontmatter, `current.md` |
| `move-party village-square` | sets every PC's `location:` and `party-location` (site or site/area) | PC files, `current.md` |
| `attitude mara friendly "paid for Tobin's drinks"` | sets attitude, appends to `## History with the party` | NPC file |
| `item Kira -dagger "taken by guard"` / `+ "brass key"` | inventory change | PC `## Inventory` |
| `coin Kira -5gp` | coin change | PC `## Inventory` Coin line |
| `res Kira -"spell slot 1"` | spend/restore a tracked resource | PC `## Resources` table |
| `time +20m` | alias for `clock advance` (Tier 3) | `current.md` |
| `log "Kira buys Tobin a drink; cart story told"` | closes the open turn block with this summary | session log |
| `undo` | rolls back the last `do` batch / single command | files in the journal |
| `rule add\|end\|list`, `retcon`, `overrule-undo` | player overrules (below) | `state/table-rules.md`, session log |

Group combat rows (`Thugs ×3`, `7/11 ea`): `hp Thugs -5` **splits one member into its
own row** (`Thug 1`, 2/11) — the same rule as 02 → Groups/swarms.

**Session-log turn blocks.** The first mutation after a `log` opens `[turn N]`. Each
mutation appends a delta line under it; `log "..."` writes the summary line and closes
it. Result:
```
[turn 14] Kira buys Tobin a drink; cart story told
  - coin Kira 35→30 gp
  - attitude Tobin neutral→friendly
  - (GM) roll SECRET 1d20+2 = 9 (Mara insight vs Kira deception 15) — fail
```
Delta lines carrying GM-only information (secret rolls, off-screen NPC moves, fired
clock beats, hidden-DC results) are tagged `(GM)`. The tag lets recaps and the history
summary leave them out of anything said to players. The file itself is protected by
the honor system.

### `gm.py rule` / `gm.py retcon` — player overrules (02 → Overrule)
Called by the `/overrule` skill as soon as someone invokes it (honor-based; no
confirmation step).
```
gm.py rule add "Crits on 19–20 for this fight" --scope combat --key crit-range=19
   → [rule R3 added · combat · crit-range=19]
gm.py rule add "Potions are a bonus action" --scope campaign
gm.py rule add "No travel encounters" --scope "until we reach Thornbury"
gm.py rule end R3 [--reason "boss down"]
gm.py rule list
gm.py retcon "Kira's climb went unseen" --turn 14
   → [retcon of turn 14 logged] (then corrective mutations in the same batch)
gm.py overrule-undo
   → reverses the most recent overrule batch (rule add or retcon + its corrections)
```
Each overrule is run as **its own `do` batch** and marked as one in the journal, so
`overrule-undo` (behind `/overrule undo`) can reverse exactly that overrule even if
ordinary turns came after it. If a later batch touched the same files, it refuses and
lists the conflicts instead.
- **Storage:** `<campaign>/state/table-rules.md` (format in 04). Ended rules stay in the
  table, marked ended, until `session archive` moves them to the session history.
- **Mechanical keys** are read by `lib/resolve.py` and the other tools. A rule without a
  key is free text the GM honors. v1 keys:

  | key | values | effect |
  |---|---|---|
  | `crit-range` | 18–20 | natural roll ≥ N crits (attacks) |
  | `crit-damage` | `double` · `max+roll` | crit damage mode |
  | `ties` | `pc` · `raw` | toggle the ties-go-to-PC house rule |
  | `flanking` | `off` · `adv` · `+2` | applied by `atk` when `space.py` finds an ally opposite the target |
  | `death-saves` | `on` · `off` (drop to 1 HP instead of 0) · `dc N` | PC death saves |
  | `potion` | `action` · `bonus` | reported in `combat next` reminders |
  | `dice-mode` | as in `current.md` | temporary override |
  | `encounters` | `on` · `off` | `travel` skips encounter rolls |

  New keys are added as tables invent them. `lint` warns on unknown keys, which still
  work as free text.
- **Precedence:** active table rules > `rules/house-rules.md` > RAW. When two active
  rules set the same key, the newer wins, and `rule add` reports the one it overrode.
- **Expiry:** `scene enter` ends `scene` rules, `combat end` ends `combat` rules, and
  `session archive` ends `session` rules. Each prints `[rule R3 ended — combat over]`
  for the GM to announce. `until …` rules end only with `rule end`.
- **Brief line:** `Rules: R1 potions=bonus (campaign) · R3 crit 19–20 (combat)`. This
  line is part of the heartbeat too, so active rules are always in context.
- **`retcon`** writes the public log line `[overrule] retcon turn 14: Kira's climb went
  unseen`. The corrections that follow are ordinary mutations, logged as usual. Hidden
  ones are tagged `(GM)`. When the target is the latest batch, the skill uses `undo`
  instead.

**Undo journal.** Before each command, `lib/journal.py` saves the before-image of every
file it touches to `<campaign>/.gm/journal/` (last ~50 batches). `undo` restores the
latest batch and logs `undo turn 14 step 2`. This covers "check the record" corrections
(05 #13) between git commits.

### `gm.py juice [on | off | <value> | cooldown <n> | waive | status]` — Wacky Juice (02)
- `on` / `off` / `<value>` (0–100) / `cooldown <n>` write the frontmatter keys (04 →
  Campaign file) and log a public `[juice]` line (`value 5 → 10`). The players change
  the rate by asking the GM; it's table configuration, not an overrule.
- `waive` (normally inside the turn's `do`) clears `pending` and logs
  `(GM) [juice] Tobin — waived`.
- `status` prints `Juice: on · 5% · cooldown 3 · 1 prompt since last · pending: —`,
  plus this session's used/waived/unlogged counts from the log (for play-test tuning).
- Every `do` batch that runs while `pending` is set and doesn't contain `juice waive`
  logs `(GM) [juice] Tobin` and clears `pending`, so a used juice costs the GM nothing.

### `gm.py brief` + hooks — state in context without a Read
`brief` prints a ≤ 20-line digest built from `current.md` + the files it points to:
```
[GM BRIEF] poc · Day 1 19:40 (evening) · crossroads-inn — Common room, dinner rush · tempo: tense
On stage: Mara (wary) goal: keep evening calm · Tobin (friendly) goal: tell cart story · Veskar (wary)
Order: Mara 17 · Kael 13 · Veskar 12 · Tobin 5
Party: Kael 9/11 AC15 · Kira 30/30 AC14 [poisoned 8m]
Sight (dark): Kael blind without a light · Kira sees to 60 ft (darkvision: grey, no colour; sight Perception at disadv.)
Setting: medieval tech, no gunpowder; magic known but rare and costly
Rules: R1 potions=bonus (campaign) · R3 crit 19–20 (combat)
Watch: Harl asked of Mara → beat 1 · mill → beat 3   Next clock: Day 3 04:00 (Red Ledger cart) in 1d 8h
Combat: — 
Log: turn 14 open (2 deltas)
```
The `Setting:` line is the campaign's `setting:` (04 → Campaign file), printed only when
it isn't empty. The GM judges *Not in the setting* against it (02 → Kinds of "no").
Hooks in the project `.claude/settings.json`:
- **`UserPromptSubmit`** → `gm.py brief --hook`: attaches context to each player
  message, so the GM never needs to Read `current.md` on a normal turn. Prints nothing
  (zero cost) unless `current.md` has `in-session: true` (set by `/gm`, cleared by
  `/end-session`). **Decided (2026-10-02): hybrid injection**, see below.
- **`SessionStart`** (sources `startup`, `resume`, `compact`) → `gm.py brief --hook --long`:
  adds the scene summary and the last 5 session-log turns. This replaces the "re-read
  after compaction" instruction (05 #8) with something automatic. It also resets the
  change-tracking state below, so the next prompt gets a full brief.

**Hybrid injection (full brief on change, one-line heartbeat otherwise).**
- The hook hashes the brief's content (excluding the `Log:` line, which changes every
  turn) and compares it with the hash it last injected, stored in `<campaign>/.gm/brief-hash`.
- **Changed** → inject the full brief and store the new hash. Changes come from `gm.py`
  writes, clock moves, and hand edits to files the brief draws on (it's built from the
  files, so hand edits are caught too).
- **Unchanged** → inject one heartbeat line (~30 tokens) carrying the facts that most
  often matter mid-scene:
  `[GM BRIEF] unchanged since turn 14 · Day 1 19:40 · tense · Kael 9/11 poisoned · up: Mara · R1 R3`
  (time · tempo · every PC below max HP or with a condition · whose turn, in combat ·
  active table-rule ids).
- **Forced full brief:** after any `SessionStart` (hash cleared); every 15 prompts
  regardless, so the full version never drifts too far back in context; and when the
  player message starts with `!brief`. (Covers a cancelled prompt whose brief the model
  never saw.)
- **Wacky Juice roll** (02 → Wacky Juice; config keys in 04 → Campaign file). On
  `UserPromptSubmit` only, after the brief is built: skip if `wacky-juice: off`, if
  the prompt starts with `/` or `!` (commands aren't play), or if `.gm/juice` says
  `prompts-since` < cooldown. Otherwise collect the on-stage NPCs (the `On stage:`
  names, minus any with a condition that stops action: unconscious, paralyzed,
  petrified, stunned, incapacitated, or `hp: 0`). With at least one, roll d100 with
  `SystemRandom`. On ≤ `wacky-juice-value`, pick one uniformly, write `pending: <slug>`
  and reset `prompts-since: 0`; otherwise increment `prompts-since`. A hit appends
  `Juice: Tobin — an unexpected, funny move this turn (02 → Wacky Juice)` to whatever
  the hook prints (full brief **or** heartbeat). The juice line is never part of the
  hash. A pending juice that no `do` consumes is cleared by the next prompt's roll
  and logged as `(GM) [juice] Tobin — no turn logged` (the GM may still have used it
  in narration; the line is written outside the undo journal). `log` consumes a
  pending juice the same way `do` does.
- Why: injecting the full brief every message costs ~350 tokens/prompt (~50k per
  150-turn session, all repeats on talk-heavy turns), which brings compaction sooner.
  Injecting only on change risks the model leaning on a brief 10–20 messages back. The
  hybrid keeps the critical facts beside every message for ~10% of the cost.

### Permissions
Project `.claude/settings.json` allowlist: `Bash(python engine/gm.py:*)`,
`Bash(python engine/space.py:*)` (plus `py` variants for Windows if `python` isn't on
PATH), and the same four as `PowerShell(...)` rules: on Windows the session may run
commands through the PowerShell tool, which Bash rules don't cover (found 2026-10-05).
The rules apply only once the folder is trusted (open Claude Code interactively in
`dnd-adventure/` once). A permission prompt mid-turn is the single slowest thing that
can happen.

## Tier 2 — scene changes & combat

### `gm.py scene enter <location> [--light dim|dark] [--area common-room]`
One call replaces the `/scene` read fan-out. Output packet:
```
[SCENE] crossroads-inn/common-room (site · building, in thornbury) · light: bright
Description: <body of ## Description>
Exits: front door → square (adjacent, W) · kitchen → stable-yard (E) · trapdoor → cellar (locked, hidden DC 12)
Nearby: village square adjacent W, 1 min · reeve's house 135 ft W, 1 min · old mill 0.8 mi N, 15 min (via square, mill road)
Present: Mara (npc, wary) · Tobin (npc, neutral) · Kael, Kira (party)
Not on stage but here: Veskar (room 3 — Movements: keeps to room by day)
Passive notices: Kira (PP 15) → DC 13 dried mud footprints to the trapdoor · Kael (PP 12) → nothing
Triggers mentioning this place/these NPCs: beat 1 (Mara), beat 2 (Tobin), beat 4 (inn cellar)
Layout: common-room (9 features) — `gm.py space map` to draw
```
- **Passive Perception is resolved by the tool:** each `## Hidden` DC vs. each PC's
  passive score, with light (`dim` −5 unless darkvision) and ties-go-to-PC.
- `--write` rebuilds `current.md`: frontmatter, On stage from NPC frontmatter
  (`attitude`, `default-goal`), Watch for from matching beats, Clocks, `Tempo: calm`.
  The GM then refines lines with `gm.py onstage mara --goal "..." --note "..."` rather
  than editing the file.
- Trigger matching here is only a **text filter** (beats that mention the slug or a
  present NPC). Whether a beat fires is the GM's call.
- **Exits and Nearby are derived** (`lib/geo.py`, 04 → Location files). Exits come from
  the site's `## Areas` plus every route in the parent frame that touches this site.
  Nearby lists the places in the same area (and, at an area's edge, routes out into the
  world): bearing as an 8-point compass word, exact distance edge to edge (ft under
  1,000 ft, then mi to 0.1), and route time at normal pace. The GM turns these into
  player-facing bands per 02 → Telling players distances. Places with no coordinates yet show as
  `(unplaced)` with their route time if one exists. `secret` routes and places are
  omitted until discovered, like terrain.

`scene enter --write` to a new location without `--scene` names the scene after the
place (`The Old Mill — main floor`), so the last place's scene name never carries
over.

### `gm.py tempo tense|calm [--adj "Mara +5 watching the room"] [--pos Mara @bar ...]`
- `tense`: passive initiative (10 + DEX mod ± adj, ties → PCs) for everyone on stage,
  written as a **Stage table** in `current.md` (Combatants columns; `init` = passive
  value; see 04). Positions come from `--pos`, or stay `?` and the GM places them with
  `gm.py pos Mara @bar`.
- **Names in, coordinates out.** The GM should almost never type a coordinate. `pos`
  and `--pos` accept `@<feature>` (a Layout/terrain row id: the nearest free cell of
  the feature if it's passable, else beside it), `@<feature> N|S|E|W` (the free cell
  on that side), `near <creature>` (the nearest free cell within 5 ft), or a raw
  `x,y,z` as the override. Coordinates are the storage format; names are the interface.
- `calm`: drops the Stage table, keeps positions in the moves history.
- `gm.py intent Mara "get the letter off the bar"` sets this beat's NPC intent.

### `gm.py combat start | next | end`
- `start [--surprised Tobin] [--add "srd:thug x3 @25,15,0"] [--frame <area>]`: promotes
  the Stage table (or On stage list) to the `## Combat` block; copies Bounds + terrain
  rows from the site's `## Layout` (or, with `--frame`, from the area's Places plus the
  offset Layouts of the sites involved); rolls initiative (d20 + DEX; PC values via `--init Kael=15`
  since players roll); seeds HP/AC from PC files / stat blocks; prints the order and the
  map (`space.py map --player-view`, below). New monsters from the SRD get a `ref` of
  `srd:<name>`.
- **Player-view map:** maps the GM pastes into narration are always rendered with
  `--player-view`. That leaves out combatants the party can't perceive (conditions
  `hidden` / `invisible` / `unseen`) and terrain rows whose effect contains `secret`
  (an unspotted trapdoor). The full map is the GM's, and is never pasted.
- `next`: advances `up:`; on wrap, increments the round, moves the moves log into the
  session log, ticks condition durations (`poisoned 3r` → `2r`, expiry reported). Prints
  who's up, their position, and the creatures within reach/range.
- **Moves by name** (`gm.py space move Kael --to landing` / `--to Veskar` /
  `--to @door`): `space.py` finds the path itself (Dijkstra over the cell grid:
  difficult terrain and climbing ×2, stairs/ramps as the only way to change height
  without a climb or fly speed, walls and enemies impassable, allies passable but not
  an end cell). A creature target means "stop adjacent"; `--stop 10` stops at reach.
  It prints the path as waypoints, the cost against speed, and the opportunity
  attacks provoked, and `gm.py` logs it as the move. `--path x,y,z ...` remains the
  override for a deliberately odd route.
- `reframe <area|site>`: mid-fight switch between a site frame and its parent area
  frame when the fight spills out of (or back into) a building. Adds or subtracts the
  site's `at` offset for every position, terrain row and moves-log entry and
  rewrites the `Map:`/`Bounds:` lines. Reframing into a site is refused while any
  combatant is still outside that site's footprint.
- `end`: writes HP/conditions back to PC/NPC files, marks dead NPCs
  (`status: dead` in frontmatter), leaves `## Combat (not in combat)`, sets tempo.
  Unless `xp-tracking: off`, it also prints the fight's award, un-applied: `[XP available: 700
  (wolf ×3 defeated, 1 fled) → 175 each for 4 present · award with: xp award
  from-combat]`. Base XP per monster (not the encounter multiplier, per the DMG) for
  foes defeated, routed, captured or talked down. Foes marked `+fled` or `+surrendered`
  count as defeated (Phase 14 morale); `--count-fled` counts every foe still standing.

### `gm.py split` — splitting the party (02 → Splitting the party; 04 → Split party)

```
gm.py split mill=Grusk inn=Kael,Kira [--active mill]  # form groups; current scene → the active one
gm.py split cut [<group>]          # park the active scene, load the next (default: furthest behind)
gm.py split status                 # the table + whose slice is due and why
gm.py split sense <group> on|off   # override "can sense the other group's fight"
gm.py split task <group> "<what>" <30m>  # a long task spanning slices
gm.py split join <group> <group>   # merge when they meet (same site required)
```
- **Forming** copies `current.md` to every new group (same place, time, light), puts
  the named PCs in each, and records the active one. Groups then move with the
  ordinary tools (`scene enter`, `travel`, `move-party`), which act on `current.md`, so
  a group must be active to move. `move-party` moves only the active group's PCs.
- **Counting.** The brief hook adds 1 to the exchange counter (`.gm/split-slice`) for
  each player prompt (not `/` or `!` lines, and not a prompt whose every `Name:`
  speaker — PC first/full name or player — is in a waiting group; each such speaker
  gets a `Held: Kael is in inn, which is waiting — don't resolve, roll for or time
  this…` line with the brief). The first `split cut` of a split also prints
  `[first cut: … don't know what just happened with mill …]`; combat rounds are read from the Combat
  block against `slice-round`. `split cut` resets both. Nothing cuts automatically:
  the brief says when a cut is due and the GM picks the moment.
- **Choosing the next group:** `split cut` with no group picks the one with the
  earliest clock (ties → the next in table order). It refuses a group more than
  `split-max-ahead` ahead of the earliest unless `--force`.
- **Sensing:** same site → yes; otherwise the route distance between the groups'
  locations (`geo.find_route`, in feet) ≤ `split-sense-ft`, or ≤ a special sense
  (blindsight, tremorsense, truesight) in a PC's `senses:`. No route → no. Long
  sightlines (a lit tower across a valley) are the GM's call: `split sense <group> on`.
- **Clocks:** `clock`/`time` advance the active group's `in-game-datetime` and tick its
  PCs' conditions. World CLOCK beats, NPC schedules, NPC conditions, restock and the
  time loop run on the **earliest** group clock (`World clock (earliest group): …`
  line). NPCs on stage in any group's scene are never moved by schedule. Past
  `split-max-ahead` (1 minute while a waiting group fights) it warns
  `[split: mill is now 40m ahead of inn — cut first or summarise their matching span]`.
- **Combat time.** Combat doesn't move the clock; while split, the rounds the active
  group fought this slice (6 s each, rounded up to the minute) are charged to its
  clock when the GM cuts away (`split cut`) or the fight ends (`combat end`).
- **Sessions.** `session archive` leaves a split in place, adds `## Split at session
  end` (one bullet per group: place, clock, tempo; plus open tasks) to the history file
  and says `still split (N groups, resumes next session)`. `session start` and `intro`
  print `[SPLIT] the party is still split: … open with inn (furthest behind; split cut
  inn first)`. Both reset the exchange counter.
- **Long tasks** finish when the active group's clock passes their end
  (`Long task done: …` in the `[TIME]` output) and leave the list.
- **join** requires both groups at the same site; the result's clock is the later of
  the two (the earlier group's gap is printed for the GM to summarise), On stage and
  Watch for are unioned, and an active combat on either side becomes the merged
  Combat block (the newcomers roll initiative and enter at the next round).
- **Active scene only.** `scene enter`, `tempo`, `combat start`, the brief's Sight line
  and `move-party` see only the active group's PCs (`campaign.scene_pcs()`). Absent
  (autopilot) PCs travel with whichever group they were put in.
- **Brief while split:** two lines after `Combat:`:
  `Split: ▶ mill (Grusk) · inn (Kael, Kira) crossroads-inn/yard Day 1 21:09 calm, 1m behind`
  and `Slice: exchange 2/3` (or `round 3 of 6`, or `round 2 of 1 (every round: inn can
  sense the fight)`) with a cue when one applies: `Cut due: 3 exchanges` · `Cut due: 6
  rounds played` · `Cut every round: inn can sense the fight` · `Cut due: inn is 35m
  behind` · `Play on: inn is 35m ahead (no cut until this group catches up)`. The
  `Slice:` line changes every prompt, so it's left out of the brief hash (like `Log:`);
  the heartbeat carries `mill exchange 2/3 · CUT DUE`.

### `gm.py monster new "<name>" --from "<base>" | list [--all] | show <name>`
Custom monsters (07 → Custom monsters; 04 → Custom-bestiary file), one `custom-bestiary/` per
campaign. `new --from "<SRD or this campaign's monster>"` copies the stat block into
`campaigns/<active>/custom-bestiary/<slug>.md` for editing; `--from "<other-campaign>:<monster>"`
copies another campaign's creature as it is (the only way creatures cross campaigns).
Every tool that looks up a monster (`srd monster`, `combat start --add "srd:<name>"`, `atk`,
`ENCOUNTER` rosters and `encounter`/`danger`, `statblock:`) finds it: the active
campaign's custom-bestiary first, then the SRD. `list` shows this campaign's; `list --all`
every campaign's; `show` = `srd monster`.

### `gm.py srd monster|spell|condition <name>`
- Data: SRD 5.1 JSON (from the 5e-bits `5e-database` project, CC-BY-4.0) stored in
  `data/srd/` with attribution. Downloaded once; no network during play.
- `srd monster "bandit captain"` prints a compact stat block (AC, HP, speed, mods,
  attacks with to-hit/damage, special traits). `--write npcs/veskar.md` puts it into the
  NPC file the first time it's used (02 → Combat mode) so later edits stick.
- `atk`, `combat start`, and `tempo` read stat blocks through this module, so monster
  numbers are looked up, never recalled from memory.
- Edition matters: SRD 5.1 = 2014 rules, SRD 5.2 = 2024 (README open decision 1).

## Tier 3 — between scenes, between sessions

### `gm.py clock advance <+20m|+2h|+1d|to 06:00|to dawn>`
Advances `in-game-datetime`, then reports everything it crossed:
```
[TIME] Day 1 19:40 → Day 2 00:10 (+4h30m)
  Movements: Veskar left crossroads-inn 00:00 by back-lane, mill-rd → old-mill, due 00:16  [off-stage — in transit]
  Conditions expired: Kira poisoned
  Clocks: none fired · next: Day 3 04:00 Red Ledger cart (in 1d 3h50m)
```
- **Off-stage** NPC moves are applied with `move-npc`. **On-stage** ones are listed as
  *intents* for the GM to narrate or override.
- **Nobody teleports.** A scheduled move is a departure at the schedule time; the tool
  finds the route (as `travel` does), and `location:` flips to the destination only on
  arrival. In between the NPC is `location: @mill-rd` (on that route, with a fraction
  done), so `where` and `trace` can say "on the mill road, about halfway", and a party
  on the same road at that time meets them. No route = instant move with a lint
  warning, so an unroutable schedule gets noticed rather than silently fixed.
- Clock beats that fire are printed in full (the scenario line). The GM decides what
  happens.
- Named times: dawn 06:00, morning 08:00, noon 12:00, afternoon 15:00, dusk 18:00,
  evening 19:00, night 22:00, midnight 00:00, pre-dawn 04:00.

### `gm.py travel <to> [--pace fast|normal|slow] [--by foot|cart|horse|boat] [--night]`
Finds a route from the party's location to `<to>`: `## Routes` rows chained through
site, area and world frames as needed (cellar → trapdoor → common room → front door →
square → mill road → mill; Thornbury → the king's road → the city). No route = error
(no teleporting); `--overland` allows a straight-line cross-country trip at trackless
pace and logs it. Time = path length ÷ pace × kind and conveyance factors (04 →
Deriving travel time) unless the row overrides it. Encounter table: the route's own
(`tables/encounters-<route id>.md`) if it exists, else the destination area's, chance
by time of day. Then runs `clock advance`, `move-party` and `scene enter <to>`. Output
= all three packets, plus a **landmarks line** listing the placed features the path
passes within 100 ft of (`passes: shrine, the fields, the willows`) so the GM narrates
the journey with real landmarks. Inside a site with a `## Routes` table, `travel
crossroads-inn/cellar` checks access (locked, DC to notice) and takes the row's time;
without one, `move-party site/area` is the unchecked fallback.

### `gm.py rest short|long [Kael ...]`
- **Long rest:** full HP, half hit dice back, `Resources` reset per their `recovers`
  column, 8 h on the clock (interrupted rests are the GM's call → `--interrupted`).
- **Short rest:** spend hit dice (`--hd Kael=2`, rolled), `short`-recovering resources
  back, 1 h on the clock.

### `gm.py lint [--fix-safe]`
Consistency sweep (05 #5 and more), exit code 1 on errors:
- geography (01 → World geometry): `parent:` naming a missing file or a file of the
  wrong tier; a site with a parent but no Places row there (warning: unplaced); Places
  `ref` naming a missing file; overlapping footprints of sibling sites; a site's Layout
  x/y bounds not fitting inside its footprint; route endpoints (`place`, `place.exit`) that
  don't resolve; a `time` override more than 2× off the derived time (warning); a
  Description that says `<placed id> … to the <compass>` against the geometry
  (warning; regex only, prose isn't policed beyond this); a `## Movements` line whose
  destination has no route from the previous one (warning)
- world: no `locations/world.md` (error); a `## Known, not placed` row whose
  constraints no longer have any satisfiable spot after a new placement (warning: the
  GM should reword a constraint or move the newcomer); a constraint naming an unknown
  id; a non-spatial constraint (warning: move it to notes); a placed row whose
  `placed:` note is broken by the route time now that a route exists (warning);
  frontier leads whose `from` isn't placed
- `location:` values naming missing sites, or sub-areas not in the site's `## Areas`
  (warning); PCs not all in one place (warning)
- frontmatter outside the parsing contract; missing required fields per 04
- combat: positions out of bounds, two creatures in one cell (non-group), HP > max,
  `up:` naming someone absent
- On stage pointing to missing files; Watch-for beats no longer in any active scenario
- `--fix-safe` only does mechanical fixes (e.g., add a missing sub-area to `## Areas`,
  marked `<!-- added by lint, check me -->`).

**When lint runs. Decided (2026-10-02): three layers, no `Stop` hook.**
1. **Write-time validation (always):** every `gm.py` mutation refuses or clamps bad
   writes before they happen (HP within 0..max, names must resolve, locations must
   exist, positions in bounds, frontmatter stays in the parsing contract). Tools can't
   create the errors lint looks for.
2. **Touched-files check (every `do` batch):** after a batch, `lint --files <touched>`
   runs only on the files the journal recorded for that batch (milliseconds). Problems
   are appended to the batch output as `[LINT] ...` lines, so the GM sees them in the
   same tool result and can fix them in the same turn. No extra round trip.
3. **Full sweep at boundaries:** `scene enter`, `combat end` and `session archive`
   run a full `lint` and print a short report. Those are natural pauses, and they're
   where cross-file problems (geography, missing files, stale Watch-for) matter.

Errors vs. warnings: unfinished-on-purpose things (an improvised NPC not stubbed yet,
terrain not placed) are **warnings** at layers 2–3 and never block. Only broken
references and unparseable files are **errors**. `session archive` refuses to commit
with errors unless `--force`.

Why not a `Stop` hook after every reply: it runs after the narration is already shown,
so any finding costs an extra model round trip and visible fix-up text mid-play; a full
sweep slows down as the campaign grows; and it would nag about deliberately-unfinished
canon. With layers 1–2, the only thing a per-reply sweep would catch sooner is a hand
edit to a file the current turn didn't touch, which can wait for the next scene boundary.

### `gm.py intro [--why "<reason>"]` — the session opening
Prints a block-letter title card for the GM to paste in a code block ("Our tale begins"
for the first session, "Our tale continues" after), then GM-only lines: `[INTRO first|resume
· session N]`, `[PREMISE] …`, and `[WHY fixed|options|chosen|none] …` from
`## Why you're here (player-safe)` (04). `--why` records the table's answer as a
`Chosen:` line and logs it.

**How to play (Phase 16; 02 → How to play).** On the first session, `intro` prints
`[HOW TO PLAY]` lines **before** the title card, for the GM to say in table voice once
the characters are settled: name prefixes, intent over outcome, the roll-ahead point
with an example drawn from a present PC (`Kira: I search the desk, rolled 16`), and
asking anything. It reads `dice-mode` (`gm-rolls-all` drops the roll-ahead line) and
`discord.md` (adds the Discord line when the bridge is on). The existing per-setting
`[TELL THE TABLE]` lines follow. `intro --how-to-play [--for <PC>]` prints the same
block on demand: for a new player at the end of intake (`--for` makes it the short
version addressed to them) or when someone asks again. It's logged once per campaign
as `[intro] how to play given` (the session log or a history file), so a second `/gm`
in session 1 doesn't repeat it; `--for` doesn't count as the talk and isn't logged.

### `gm.py turn` / `gm.py move` — the turn budget and real movement
The creature who's up has a budget, one line under `## Combat`:
`Turn: Kael · action yes · attacks 0/2 · bonus yes · object yes · move 30/30` (attacks per
Attack action from a PC's Extra Attack; `?` for NPCs). `combat start`/`next` reset it and
print `[Kael's turn: …]`. `atk` spends the action (counting Extra Attack) or, with
`--bonus`, the bonus action, and prints `[Kael still has: …]`. `turn use
action|bonus|object|dash` spends the rest; `turn` prints it. **Nothing ends a turn but
`combat next`**: the GM asks the player whether they're done.
`move <who> --to … | --path … [--stop N] [--dash]` finds the path, saves the position,
writes the Moves log in combat (the session log otherwise), charges the feet to the turn
of whoever is up (refusing more than is left), and lists opportunity attacks. `space move`
remains a preview that moves no one.

### Tactical map size and calm-scene sketches
`space map` draws the whole Layout of the party's area (the site's first Layout when
`party-location` names no area), framed, at the largest cell that fits 76 columns (4×2
characters per 5-ft cell, else 3×1, else 2×1). Creatures show as `[G]`; two creatures
never share a letter. In a calm scene (no Stage table) `--at "Name=<spec>"` places
creatures for that drawing only; nothing is saved.

### `gm.py session start | archive`
**Built (Phase 7):** `session start` sets `in-session: true` (what `/gm` runs);
`archive` takes `--summary-file` or `--summary`, and `--no-commit`.

`/end-session` mechanics: numbers the next `history/session-NN.md`, writes the
model-provided summary (`--summary-file`) plus the auto-extracted delta list (all
`  - ` lines from the log), resets `session-current.md` (`sessions/spoilers.md` is
never reset), clears `in-session`, runs
`lint`, then `git add -A && git commit -m "session NN"` if the folder is a repo (05 #4).
The model writes only the half-page summary and the world tick.

### `gm.py stub npc|location|place <name> [--location slug] [--in <area>] [--at x,y,z] [--note "..."]`
Creates a valid stub file from the 04 template (slug from the name, frontmatter filled,
body sections empty but present) and logs it. `stub location --in thornbury` also adds
its Places row (`--at` = the footprint's `from`; without it the row's coordinates stay
`?` and lint warns). `stub place` writes only the Places row with `ref —`: a smithy
that exists but needs no file yet. Makes "improvised canon → stub" (05 #6) a
single call. Refuses if the slug already exists (prints the existing file's path).

### `gm.py where [<name>] [--from <place>]`
Who's at a location / where someone is, from frontmatter only. Cheap answer to "check
the record". Given a place, it also prints the generated relational view, the same as
`scene enter`'s Nearby line but from any place:
```
[WHERE] old-mill (site, in thornbury) · from crossroads-inn
  bearing N (slightly W) · straight line 0.8 mi · by route 15 min (mill road, via square)
  here: (nobody)   scheduled: Veskar 00:00–04:00
```
This is the "no calculation needed" answer for planning ("can they get there before
the cart?") without anyone storing or hand-maintaining a distance table.

### `gm.py world init | show | add | place | lead | reveal | import`
Maintains `locations/world.md` (04 → The world file; 02 → The open world). Every write
records a `source` and is logged.
```
gm.py world show [--player-view]                    # placed / known-not-placed / frontier summary
gm.py world add "the market town" --near thornbury --within 3d --source player:kael       --note "temple of Chauntea; Kael was sent from here"     # → Known, not placed
gm.py world place market-town [--at 38,-12] [--size 1]  # → Places; without --at, suggests 3 spots
gm.py world lead thornbury --heading E --as "the east road" --source scenario   # → Frontier
gm.py world reveal <id>                              # strips `secret` from a Places/Routes row
gm.py world import maps/sword-coast.md --anchor Waterdeep=market-town --scale 1 [--anchor2 ...]
```
- **Constraint check:** `place` refuses coordinates that break a row's constraints
  (`within`/`beyond` measured straight-line between footprints; times converted at
  normal pace, 24 mi/day × 0.8 for road sinuosity; compass = within ±45° of the
  bearing). The constraints are copied into the new Places row's `notes` as
  `placed: …` so lint can re-check them against the real route later. It also refuses
  overlaps with placed footprints. `--force` exists for `/overrule` only.
- **Suggestions:** `place` with no `--at` prints three candidate spots that satisfy the
  constraints, spread apart, each with what it would be next to. The GM picks one for
  fictional reasons, not the tool.
- **Promotion:** placing the far end of a frontier lead turns the lead into a world
  `## Routes` row and removes it from `## Frontier`.
- **Import:** reads a `| name | x | y |` table (plus optional `type`/`notes`) and
  transforms it by the anchor(s): one anchor plus `--scale`, or two anchors (scale is
  then derived, still north-up, no rotation). Rows land in `## Known, not placed` with
  their transformed position as a `near (x,y) ±5mi` constraint, and a conflict report.
  Nothing is placed automatically.
- `/new-campaign` runs `world init <area-slug>`, which writes the world file with the
  starting area at `(0,0,0)`. A campaign never lacks a world map.

### `space.py map` at area and world tiers
`space.py map --place thornbury [--cell 50]` draws an area (or world, `--cell 1` mi)
from its Places and Routes: footprints as their glyph, routes as `·` paths, party/NPC
markers at their site's footprint. The default cell size fits the frame into ~60
columns. `--player-view` drops `secret` rows and places the party hasn't heard of. At world
tier, frontier leads draw as arrows off known places (`→ the east road ?`). Known-but-
unplaced rows are listed under the map, not drawn, and blank space is labeled
*unexplored*, not left looking empty.
Combat maps are unchanged (5-ft cells, Combat block).

### Spoiler support — `trace`, `odds`, `spoil` (02 → Spoilers)
These give `/spoilers` answers facts and numbers instead of model recall. `trace` and
`odds` are also useful to the GM in ordinary play.

**`gm.py trace <name|location> [--from "Day 1 18:00"] [--to "Day 2 06:00"]`**: a
reconstructed timeline. It merges:
- logged moves, including `(GM)` lines, from `session-current.md` and `history/`
- the `## Movements` schedule for periods not covered by the logs (labeled `scheduled`)
- `clock` firings
```
[TRACE] Veskar · Day 1 18:00 → Day 2 06:00
  Day 1 18:00–00:00  crossroads-inn (room 3)        scheduled
  Day 2 00:10        → old-mill via stable yard      logged (GM) turn 22
  Day 2 04:30        → crossroads-inn                scheduled
```
Each row carries its source (`logged` / `scheduled` / `inferred`), which maps directly
onto the GM's *Established* / *Likely* labels. A location argument lists everyone who
passed through it in the window.

**`gm.py odds <atk|save|check|contest> ...`**: the same arguments as the resolving
commands, but it returns **exact probabilities** instead of rolling, with active table
rules applied:
```
gm.py odds atk Kira Veskar --with dagger --sneak 2d6
  → [ODDS Kira → Veskar: hit 60% (crit 5%) · dmg avg 12.5 · drops him (22 HP) in 1 hit 0% · in 2 hits 41%]
gm.py odds check Mara insight 12   → [ODDS Mara insight ≥12: 55%]
gm.py odds contest Kira stealth Mara perception → [ODDS Kira wins 68% (ties→PC)]
```
Computed by enumerating the dice distributions (no simulation, deterministic). It's
also the basis for the "Guess" claims in what-ifs.

**`gm.py spoil log "<question>" --level none|minor|major --depth hint|answer|full --reveals "<one-line summary of what was revealed>"`**:
appends to `sessions/spoilers.md` (04) and writes a public `[spoilers]` line to the
session log. Called right after the answer is shown. Level-`none` what-ifs are logged
too, so the record of what the table explored is complete. What-if *guesses* are
recorded as "what-if (not canon)" and never as facts.

**`gm.py spoil list`** prints what's already spoiled, so the GM knows which facts no
longer need "behind the screen". The `brief --long` at session start includes the
count and the latest entries.

## Character tools — `gm.py pc` (intake & level-up, 02 → Session start & characters)

The model turns free text into fields. These commands do everything after that: fill
in what can be computed, check it, list exactly what's missing, and write the file.
It's the same split as dice: the model never adds up HP or works out spell slots.

```
gm.py pc draft <slug> --set race="half-orc" class=barbarian level=3 subclass=berserker \
                      --equip "greataxe; 4 javelins; explorer's pack"
gm.py pc draft <slug> --from-sheet <file>         # a pasted sheet the GM saved to .gm/drafts/
gm.py pc check <slug>                             # derive + validate the draft
gm.py pc card  <slug>                             # one-screen character card for confirmation
gm.py pc write <slug>                             # draft → pcs/<slug>.md (new or edit)
gm.py pc edit  <pc> --set ... / --item +"longbow" # between-session changes, same checks
gm.py pc level-pending <pc> [--to 4]              # mark a milestone level-up (xp campaigns: set automatically)
gm.py pc levelup <pc> --plan                      # what level N+1 grants + required choices
gm.py pc levelup <pc> --choose asi="dex+2" spells="+guiding bolt" --apply
gm.py pc roster [--present Kira,Kael] [--absent Bren]   # session attendance → present: flags
gm.py xp award <N | from-combat> [--to Kira,Kael | --present] --reason "..."   # unless xp-tracking: off
gm.py xp show [<pc>]                              # xp, level, next threshold, to go
gm.py xp set <pc> <N> --reason "..."              # correction; logged; journaled like any mutation
```

**`pc check` output** (fed back into the ask step):
```
[PC CHECK] grask · half-orc barbarian (berserker) 3
DERIVED   speed 30 · prof +2 · darkvision 60 · hit die d12 · saves STR, CON
          rage 3/long rest · reckless attack · danger sense · frenzy (berserker)
          half-orc: +2 STR +1 CON · relentless endurance · savage attacks · Intimidation
PENDING   HP, AC (unarmored), attack bonuses, save totals: need ability scores
          HP for levels 2–3: by hp-method (asked below if not set; level 1 = 12)
MISSING   1. ability scores (offer: standard array → STR 15 CON 14 DEX 13 WIS 12 CHA 10 INT 8
             before racial bonuses, so STR 17 CON 15 · point buy · roll 4d6 drop lowest)
          2. 2 barbarian skills from: Animal Handling, Athletics, Intimidation, Nature, Perception, Survival
          3. name
          4. hp-method: max or roll (asked once; stored, reused at every level-up)
DEFAULTS  background: none given → skills/equipment from background skipped (OK?)
CONFLICTS —
CUSTOM    —
```
Derived values are recalculated whenever a draft field changes. Values in
`overrides` are never recalculated.

**What `pc check` covers (SRD 5.1)**
- **Races/subraces:** score increases, speed, size, senses, proficiencies, traits.
- **Classes:** hit die, saves, skill choices, armor/weapon proficiencies, features by
  level, subclass level, spell slots / cantrips / spells known or prepared counts, ASI
  levels.
- **Subclasses:** the SRD's one per class (Berserker, Lore, Life, Land, Champion, Open
  Hand, Devotion, Hunter, Thief, Draconic, Fiend, Evocation). Any other subclass is
  `custom`.
- **Equipment:** armor → AC (DEX caps, STR requirements, stealth disadvantage); weapons
  → the Attacks table (finesse/versatile/thrown/ranges); shield; starting packages.
- **Checks:** point-buy ≤ 27 / standard array / plausible rolled scores; proficiency
  with equipped armor and weapons; known-spell counts vs. the class table; spells from
  the class list and of castable level. These are **warnings**, not blocks (02:
  player-stated values win).

**`pc levelup --plan`** reads the class table for N+1 and lists *granted* (applied
automatically) vs. *choices* (must be answered). HP is *granted*, computed from the
PC's `hp-method` (`roll` rolls publicly at `--apply`; `--hp-roll N` takes a
player-reported roll instead). It's only a choice if `hp-method` is somehow unset. `--apply` refuses while any choice
is unanswered and prints the missing list, which the GM turns into the next question.
On apply, it updates:
- HP max and current (current goes up by the same amount)
- hit dice, prof, slots and Resources, features, scores (ASI)
- recalculated Attacks and spell save DC/attack bonus
- a Journal line and a session-log delta

**`pc roster`** sets `present: true|false` on PC files for this session. Names are PC
names or player names: an exact `player:` match (case-insensitive) wins and marks all of
that player's PCs; a name matching neither is reported (`'Bob' is no PC or player here…`)
without failing the rest. `player:` is optional; blank or `(pregen)` means unclaimed. The
brief's party line shows the player beside the PC (`Grusk (Adam) 31/42 AC13`) and absent
PCs as `Bren (autopilot)`.

**Data:** extends `data/srd/` with the 5e-bits SRD classes, subclasses, levels,
features, races, subraces, traits, equipment, backgrounds and spells files (same
CC-BY-4.0 source as the monsters).

## Table client — `engine/table.py` (the players' console)

**Decided (2026-10-02).** The person running the game is also a player. Files are
protected by the honor system (they don't open them). The **console** must never show
GM-level information. Plain Claude Code is a developer console: it displays Bash
command lines (`gm.py move-npc veskar old-mill`), the first lines of tool output,
Write/Edit contents, permission prompts and subagent progress. The tools can't make
the GM's *own decisions* invisible there, because the command that carries out a
decision names it. So play doesn't run in the Claude Code terminal. It runs through a
small client that drives the same Claude Code session in the background and shows
only narration.

```
python engine/table.py [--campaign poc] [--new] [--model <id>] [--gm-view]
```

**How it works**
- Built on the **Claude Agent SDK** (Python). It runs a persistent Claude Code session
  with `cwd` = `dnd-adventure/`, loading **project** settings only: the GM skills,
  hooks (brief injection) and permission allowlist from `.claude/settings.json`. So
  the GM behaves exactly as designed in 02/06; only the display changes.
- On start: resumes the last session (id in `<campaign>/.gm/session-id`) or starts one
  (`--new`), then sends `/gm` automatically. The recap streams in.
- Each player line is sent as a prompt. The client receives the session's messages as
  structured data and **displays only the GM's narration text**, streamed as it arrives.

**What the client displays and hides**
| Shown | Hidden |
|---|---|
| GM narration text (streamed) | Tool calls and their command lines |
| Bracket lines the GM put *in its narration* (public dice, distances, the player-view map) | Tool results (all `gm.py` output, file reads) |
| A neutral activity line while tools run: `The GM consults their notes…` (no tool names, no counts) | Thinking |
| Client notices (`[saved]`, connection errors, in generic wording) | Hook-injected context (the brief), system messages, subagent activity |

**Input conventions**
- Prefix with the speaking PC, `Kira: I check the trapdoor` (05 #10). `:as Kira`
  sets a default prefix for lines typed without one. Unprefixed lines with no default
  are sent as table talk.
- `/end-session`, `/overrule`, other GM skills and `!brief` pass straight through. The
  overrule applied card is ordinary GM text, so the client shows it.
- Any other `/…` (not a skill under `.claude/skills/`, not `/compact` or `/context`) is
  sent to the GM wrapped as "a player typed `/x`, which isn't a table command: work out
  what they want". The GM never answers "I can't": it does the thing in play, or stages
  the real command.
- **Staged commands.** A GM reply line `<<STAGE /end-session>>` (any `/skill args`) is
  never printed. After the reply the client asks `Run /end-session? [y/N]`; yes sends it
  exactly as if typed, anything else prints `[not run]`. Player-owned skills (`/overrule`,
  `/spoilers`, `/end-session`, `/new-campaign`, `campaign-*`) stay
  `disable-model-invocation`, so the player's yes is the decision. The GM stages one only
  when the player's words ask for it (02 → Overrule: the GM never suggests them).
  Character intake and level-ups are the GM's to run directly when asked.
- `/spoilers` passes through the same way. The GM wraps the answer in
  `<<SPOILERS level/depth>>` … `<<END SPOILERS>>` markers. The client renders them as a
  full-width banner in a distinct color, with the spoiler-free header on the banner
  line (`── SPOILERS · major · answer ─────`), so anyone glancing at the shared screen
  can look away. If the markers are unbalanced (e.g., the answer was cut off), the
  client closes the banner at the end of the message.
- Client-local commands start with `:` and are never sent to the GM: `:quit`
  (ends the client without ending the session), `:as <PC>`, `:gm-view on|off`.

**Permissions without prompts.** The SDK session can't show interactive permission
prompts (and a prompt would itself leak). The allowlist from 06 → Permissions is the
complete set of what the GM may do: `gm.py`, `space.py`, Read within `dnd-adventure/`,
and the skills. Everything else is denied, and the GM is told so and works around it.
Denials go to `<campaign>/.gm/client.log`, never to the screen. **Built (Phase 5):**
the allowlist alone is not deny-by-default (Claude Code auto-approves read-only shell
commands), so the client gates every tool call with a PreToolUse hook: single
`gm.py`/`space.py` commands with no shell operators, Read/Glob/Grep inside the game
folder, and Skill (engine/tests/CLIENT-CHECKS.md). A frequent denial
means the allowlist or a skill needs fixing between sessions. A side benefit: the GM
can't wander outside the game folder mid-session.

**`--gm-view`** shows everything (tool calls, results, thinking), for building and
debugging. It falls under the honor system like the files. Prep, design and debugging
sessions keep using plain `claude`, which is effectively permanent GM view.

**Memory systems.** Loading project settings only should also keep user-level plugins
(e.g., claude-mem) and auto-memory out of play sessions, so play doesn't get recorded
and replayed as spoiler-laden summaries in later design sessions. Verify this when
building. If they do load, the client disables them for its session. **Checked (Phase 5):**
user plugins and MCP servers don't load; auto-memory did, so the client sets
`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` for its session.

**Failure behavior.** SDK/API errors show `The GM needs a moment…` and retry once, then
`[connection lost — :quit and restart; the game is saved]`. State is safe because it
lives in files written each turn; the session resumes by id and the SessionStart hook
re-injects the long brief.

### Discord bridge (Phase 17; decided 2026-10-07)

Remote players join through a Discord channel: they type there and read the narration
there. The person running `table.py` stays the host, and the bridge runs inside the
client (no separate service).

```
python engine/table.py --campaign poc --discord queue|auto
```

**Setup.** Uses `discord.py`, an optional pip install that is imported only when the
bridge is on. The bot token comes from the `DND_DISCORD_TOKEN` environment variable and
is never written to a file or a log. `<campaign>/discord.md` (04) holds the mode,
the channel id and the player map (`| discord user | player |`). The bot listens only to
that one channel, never to DMs. A message from a user who isn't in the map is ignored,
and the terminal says so once per user (`[discord: ignoring @sam (not on the map)]`).

**Output.** Everything the console shows is also posted to the channel: narration,
pasted bracket lines, and the player-view map in a code block. GM-view output never is.
Posts go out paragraph by paragraph as each one finishes, split under Discord's
2000-character limit. Spoiler banners become Discord spoiler text (the
`── SPOILERS · major ──` header line, then the answer inside `|| ||`), so each reader
chooses whether to reveal it. Client notices stay on the terminal, except `[the table
is open]` / `[the table is closed]`. Staged-command prompts (`Run /end-session? [y/N]`)
stay on the terminal too: the host decides.

**Input.** A Discord line is a player line, with the same conventions as the console.
`Kira: …` speaks for Kira. An unprefixed line from someone whose `player:` matches
exactly one PC speaks for that PC; otherwise it's table talk. Pre-rolls (02 → Dice)
work the same way, so remote players can roll their own dice and say so.

**Queue mode** (`queue`): Discord lines wait for the host.
- Each arriving line is shown in the terminal as a numbered queue entry:
  `[Q2 sam] Kira: I check the trapdoor (rolled 15)`.
- Lines the host types are **added to the queue too**. An **empty Enter** submits the
  whole queue as one prompt, in arrival order. That is one turn with several actors,
  which the turn loop already orders.
- `:q` lists the queue. `:edit 2 <new text>` replaces an entry. `:drop 2` removes it.
  `:clear` empties it. `:send` is the same as an empty Enter.
- Discord feedback: when the queue is sent, the bot reacts ✅ to each submitted message.
  It reacts 🗑 to a dropped one and ✏️ to one the host edited.
- A message edited on Discord before it's sent updates its queue entry (shown as
  `(edited)`). A message deleted there is dropped.

**Auto mode** (`auto`): Discord lines are sent without the host's review.
- Lines are batched, not sent one at a time. While the GM is replying, new lines collect
  and go out as one prompt when the reply ends. When the GM is idle, the bridge waits
  `debounce` seconds (default 4, in `discord.md`) after the last line, so posts made
  together become one turn. The host's typed lines go into the same batch.

**Both modes:**
- `!x` (the X-card, Phase 13) from Discord skips the queue and goes at once.
- Slash commands from Discord (`/overrule`, `/spoilers`, `/end-session`, any `/…`)
  **always queue for the host**, even in auto mode, marked `⚑`. The host submits or
  drops them. `:` client commands typed on Discord are ignored.
- `:discord queue|auto|off` at the terminal switches mode mid-session.
- Discord text gets no extra permissions: it reaches the GM as player speech and goes
  through the same PreToolUse gate as everything else.
- If the connection drops: `[discord: disconnected — retrying]`, then reconnect with
  backoff. The terminal keeps working throughout.

**Out of scope for v1:** private per-player messages (a split group's scene sent only
to its own players), voice, and dice-roller bots (players report their rolls as text).

**Deliberately out of scope for v1:** rich markdown rendering (plain text + light
ANSI: narration normal, bracket lines dim; `rich` can be added later), a public
transcript file, voice/GUI.

**Build-time checks** (the SDK API is confirmed when building, not assumed here):
1. Which message types to filter and how text streams (partial messages).
2. That project hooks fire in SDK sessions, including SessionStart after compaction.
3. That user-level plugins and memory stay off with project-only settings.
4. Permission configuration: an allowlist with deny-by-default, plus a denial callback
   for the log.
5. Slash commands (`/gm`, `/end-session`) work when sent as prompts.

## Format changes this requires (made in 04)

- **Time:** `in-game-datetime: "Day 1 19:30"` (absolute day count + 24 h clock).
- **NPC `## Movements`:** machine-readable lines `- 00:00–05:00 → old-mill (via stable yard)`;
  prose conditions stay as prose below them. Optional frontmatter `default-goal:`.
- **Scenario CLOCK beats:** `- CLOCK Day 3 04:00: <what happens>`.
- **PC files:** frontmatter `race`, `subclass`, `background`, `scores: {str: 8, dex: 17, ...}`
  (raw scores, the source of truth; modifiers are derived), `prof: 2`, `saves: [dex, int]`,
  `skills: {stealth: 7, perception: 5}`, `senses: [darkvision 60]`, `hit-dice: {die: d8, left: 3}`,
  `autopilot:` (05 #12), `present`, `level-pending`, `overrides: {}`; body tables
  `## Attacks`, `## Resources` and `## Spells`.
- **NPC files with custom stat blocks:** same fields/tables as PCs.
- **`current.md`:** frontmatter `in-session`, `light`, `dice-mode`; a **Stage table**
  under `## Tempo: tense`; Combatants table gains a `ref` column.
- **New `state/table-rules.md`** for player overrules; `[overrule]` log lines; `Erratum:`
  lines in history files.
- **New `sessions/spoilers.md`** (spoiler record); `[spoilers]` log lines.

## What stays with the model

Narration and pacing · whether an action needs a check, and its DC · NPC intents,
lies and decisions · whether a Watch-for beat has actually fired · rulings and
house-rule interpretation · scene summaries and session summaries · placing new terrain
plausibly. Tools give facts and outcomes; the model gives meaning.

## Campaign authoring, encounters and mechanics (07)

### `gm.py campaign new|fill|status|ledger`
Maintains `<campaign>/campaign.md` (07 → Parameters). `new <slug> --set length=…
start-level=… difficulty=… shape=… --seed-file <path>` writes the frontmatter and
copies the seed; `fill <id> "<answer>"` closes a fill-in-queue row and logs it; `status
[--level shape-only|…]` prints the campaign at a reveal level; `ledger add "<what>"
--via <skill>` records what the driver was told. The generation itself is skill work
in a forked context (07 → Skills), not a tool.

### `gm.py encounter budget|build|threat`
- `budget [--present Kira,Kael] [--power +1]`: per-character XP thresholds (2014
  DMG) summed for the PCs present at their levels, shifted by item power, with the
  small/large-party shift (07 → Difficulty scaled to the table). Prints the four
  thresholds, the effective party size and the power line.
- `build "<encounter name>" [--present …] [--seed N]`: finds the `ENCOUNTER` line, takes
  its absolute budget (the word at the campaign's `start-level` for 4 PCs = the place's
  `threat.xp`), and scales the template's `×n` counts for the effective party size and
  item power, never for level. Prints the roster as `--add` arguments for `combat
  start`. `fixed` encounters print their stored
  roster and a `[fixed L5 deadly — above the party]` warning when applicable.
- `threat <place>`: recomputes `threat: {xp, fixed}` in a location's frontmatter from
  its hardest `ENCOUNTER` line (used by the authoring skills and `lint`).

### `gm.py xp award | show | set` — unless `xp-tracking: off` (02 → Level-up flow)
- Thresholds: the PHB table (L2 300 · L3 900 · L4 2,700 · L5 6,500 · L6 14,000 · L7
  23,000 · L8 34,000 · L9 48,000 · L10 64,000 · L11 85,000 · L12 100,000 · L13 120,000 ·
  L14 140,000 · L15 165,000 · L16 195,000 · L17 225,000 · L18 265,000 · L19 305,000 ·
  L20 355,000), stored as data in `lib/xp.py`, never recalled.
- `award N` splits evenly among the recipients (`--present` default; `--to` names PCs);
  absent PCs get `xp-absent` (full/half/none) of a share. Remainders are dropped (DMG).
  `award from-combat` uses the last `combat end` tally (kept in `.gm/last-combat.json`)
  and refuses if there is none or it was already awarded.
- Output: `[XP +175 each → Kael 900→1,075 · Kira 2,650→2,825 ★ L4 at 2,700: level-up
  pending]`. With `advancement: xp`, crossing a threshold sets `level-pending` (to the
  highest level reached; one level-up flow per level). With `advancement: milestone` it
  is only noted (`★ past the L4 threshold (milestone: no level-up)`). Every award writes one delta with the reason; awards are
  journaled, so `undo` reverses them.
- `show` is safe to paste to players (`Kira: L3 · 2,825 XP · L4 at 2,700 — level-up
  pending`); `brief`'s Party line adds `· XP 2,825/2,700` while tracking is on.
- With `xp-tracking: off` every `xp` command refuses, and `combat end` prints no tally.

### `gm.py loot roll <table> [--seed N]` · `gm.py shop <merchant> [--buy|--sell <item>] [--restock]`
`loot roll` rolls a `tables/loot-*.md` table and prints the result as an `item +`
suggestion (it never adds to an inventory by itself). `shop` prints a merchant's `##
Stock` (set rows plus the current random rows), `--buy`/`--sell` move coin and items via
`coin` and `item` with the DMG rarity price bands when a row has no price, and
`--restock` re-rolls the random rows (also run by `clock advance` on a `daily`/`weekly`
boundary and by `loop reset` for `loop`). `encounter budget` counts item power from
inventory rarity tags (07 → Item power).

### `gm.py danger <place> | --bearing <N|NE|…> [--present …]`
Compares the place's `threat.xp` with the present party's thresholds and prints
`[DANGER old-mill: yellow]` (green ≤ medium · yellow ≤ deadly · red above deadly or
fixed above the party's unshifted level: item power never lowers a fixed wall).
`--bearing` lists every placed adventure place in that
45° wedge from the party's location with its colour, nearest first.

### `gm.py loop start|reset|status` — only when `mechanics: [time-loop]`
- `start`: commits, records `loop-baseline: <sha>`, `loop: 1`, `loop-start`,
  `loop-end`, and each PC's `loop-bed` location in `current.md`.
- `reset --by death|sleep|time`: restores `locations/`, `npcs/`, `scenarios/`,
  `tables/` and the world facts of `state/current.md` from the baseline (`git checkout
  <sha> -- …`), sets the clock to `loop-start`, moves PCs to `loop-bed` at full HP with
  no conditions, increments `loop`, marks regenerated pieces already carried as
  `hollow`, appends the `state/loops.md` row from the deltas since the last reset, and
  logs `(GM) loop N reset (death)` + a public `[loop]` line. Never touches `pcs/`,
  `state/loops.md`, `sessions/`, `campaign.md`.
- `status`: loop number, time left in the day, what `loops.md` says the party learned.
- `clock advance` reaching `loop-end` triggers `reset --by time`. `lint` errors on a
  loop campaign without a baseline, and warns on `## Memory across loops` sections in
  campaigns without the mechanic.

## Table mechanics (02 → Table mechanics; 04 → Table settings, Scene state added)

Every command here follows the usual contract: players roll their own d20s (a result
is passed in, as with `save`/`check`), the GM rolls everything else through the tool,
each write is a journaled mutation that `undo` reverses, and a setting at `off` makes
the command say so and do nothing.

### Phase 13 — state the table forgets

```
gm.py conc Kael bless [--on Kael,Kira] [1m|10r|1h]   # start concentrating (ends any other)
gm.py conc Kael end ["failed save"]                 # ends it and strips the targets' effect
gm.py deathsave Kael <d20>                          # record a death save (gm-rolls-all / secret: no d20)
gm.py stabilize Kael [--by Kira <d20>] [--kit] [--spell]   # Medicine DC 10, a healer's kit use, or spare the dying
gm.py light Kael torch|lantern|candle|cantrip|daylight|out
gm.py eat [Kael ...] [--bought "3 sp"]              # one day's food and water each
gm.py exhaust Kael +1|-1|=0 ["forced march"]
gm.py campaign boundaries --line "…" --veil "…" [--drop "…"] [--none]   # no flags: print them
gm.py item Kira +3 arrows                           # +N/-N: a counted entry (`quiver (17 arrows)` → `(20 arrows)`)
```
- **Concentration.** `conc` writes `concentration:` and adds `<spell>` as a condition
  on each `--on` target with the same duration. `hp -`/`dmg` on a concentrating
  creature appends `concentration: CON save DC 12 to keep bless (gm.py save Kael con
  12)`; a failed `save` that the tool can match to that line ends it. 0 HP,
  `+incapacitated` (or a condition that includes it: paralyzed, petrified, stunned,
  unconscious) and a new `conc` end it automatically. Expiry runs through the clock
  and `combat next` like any duration. The brief's party line shows `[conc bless 8r]`.
- **Dying.** `hp` to 0 on a PC sets `death-saves: {ok: 0, fail: 0}` and `+unconscious`
  (the death-saves table rule still decides whether that happens). `deathsave`: 10+
  is a success, 1 two failures, 20 is 1 HP (clears the state and `unconscious`); three
  successes → `stable`, three failures → `dead`. Damage at 0 HP adds a failure (two
  with `dmg --crit`, or an `atk` crit), or kills outright when it is at least the HP
  maximum; so does damage that drops a PC to 0 with at least the HP maximum left over
  (SRD massive damage). Any
  healing clears the state. `combat next` on a dying PC's turn prints `Kael is dying
  (✓1 ✗2): death save — ask for a d20 (gm.py deathsave Kael <d20>)`; with
  `death-save-rolls: secret` it says `roll it hidden (gm.py deathsave Kael)` and the
  result line is `(GM)`. A stable PC wakes with 1 HP after 1d4 hours (rolled at
  `stabilize`, fired by the clock). The resolve.py note `at 0 HP: death save failure`
  becomes this write.
- **Light.** `light` spends the item (`torches (4)` → `(3)`; a lantern spends a
  `flask of oil` and needs a lantern in the inventory; cantrips need the spell) and
  writes `lit: [torch 60m]`; `out` puts out the newest. Data (`lib/light.py`): bright
  / dim radius and duration per source (torch 20/20 1 h, hooded lantern 30/30 6 h per
  flask, bullseye lantern 60/60 cone 6 h, candle 5/5 1 h, *light* 20/20 1 h, *daylight*
  60/60 1 h). The clock counts `lit` down (`Light out: Kael's torch (Day 1 19:30)`) and
  warns at 10 minutes left. **Effective light** for a PC = the brighter of the ambient
  `light:` and the best source carried by anyone in the active group (in combat or a
  Stage, only within that source's radius of the PC's `pos`); `lib/sight.py` and the
  scene notices use it, and the Sight line names it: `Sight (dark · Kael's torch 40m:
  bright 20 ft, dim 40 ft): …`. `track-light: off` → `light` writes `lit: [torch]`
  with no time and spends nothing.
- **Ammo** (`ammo: special`, the default): `atk` with an Attacks row whose notes say
  `special ammo <thing>` (any `ammo <thing>` under `ammo: all`) spends one from the inventory (`quiver (20 arrows)` → `(19 arrows)`) and adds to the
  Combat block's `Ammo spent:`; it refuses at 0 (`Kira has no arrows`). `combat end`
  prints `Ammo: Kira spent 6 arrows; after a search, 3 can be recovered (gm.py item
  Kira +3 arrows)`. Plain `ammo <thing>` under `special`, or `ammo: off`: nothing is
  spent or printed. **Supplies** (food and water, `strict | loose | off`, default off):
  `eat` spends `rations` and a day of water (a waterskin goes full → half → empty;
  refilling is `item`), or coin with `--bought`, and sets `fed:` to today. `rest long`
  calls it for each PC (`loose`: only away from a settlement with an inn or market,
  i.e. not at a site tagged `services`). The clock, crossing each dawn, prints
  `Supplies: Grusk last ate Day 1 (2 days; exhaustion after 5)` for anyone behind;
  past the limit it applies the exhaustion (food) or asks for the CON save (water).
- **Exhaustion.** `exhaust` writes `exhaustion:` (6 → `dead`). `lib/resolve.py`
  applies the level's effects to `check`/`save`/`atk` (disadvantage, or the 2024
  penalty) and `turn`/`move` use the reduced speed; level 4 halves HP max in `hp`
  arithmetic (2014). `rest long` removes one if the PC ate (or `supplies: off`).
  Party line: `[exh 2]`.
- **Boundaries.** `campaign boundaries` edits `lines:`/`veils:` in campaign.md (the POC
  without one: `current.md`). The **full brief** adds `Table: lines — …; veils — …`
  after `Party:` (or `Table: boundaries not asked yet` until set; nothing once they're
  set to empty). The **`!x` prompt** (X-card): the hook prints `X-card: the last thing
  described is out — rewind it in one line and steer away; don't ask why`, logs `x-card`
  with no detail, and is not an exchange for split counting.

### Phase 14 — exploration, social pressure, hazards

```
gm.py travel <to> --plan [--activities Kira=navigate,Kael=watch,Grusk=forage]
gm.py travel <to> --nav <d20 total> [--forage Grusk=<total>] [--hours 10]
gm.py order front=Kael middle=Kira back=Grusk | order | order clear
gm.py check Kira persuasion --vs mara --ask none|free|minor|major [--leverage -5..5]
      [--flair 0-3 --pitch "goat grandfather" [--appeal audacity] [--grates]]
      [--why "…"] [--goal "get the ledger"] [--core] [--dc N] [<total> | --d20 N]
gm.py social status [<npc>] | social drop <npc> "<goal>" | social wall on|off|<n>
gm.py chase start --quarry Veskar [--pursuers Kael,Kira] [--lead 60] [--env urban|wild]
gm.py chase next [--no-dash] [--lose N] | chase dash <who> | chase end [caught|escaped|gave-up]
gm.py trap trigger <trap> [--who Kael] [<save total>] | trap disarm <trap> --who Kira <total> | trap status
gm.py hazard fall <who> <ft> | breath <who> | env extreme-cold|extreme-heat|underwater|thin-air|none
gm.py hide Kira <total> | hide Kael,Kira <t1>,<t2> --group | seek Veskar [<total>]
```
- **Travel activities** (`travel-detail: activities`). `--plan` is a dry run (nothing
  moves; `--activities` are remembered in `.gm/travel-plan.json` for the next call) and
  prints what the trip needs: `Navigate: Kira, Survival DC 15 (forest, trackless) ·
  Forage: Grusk, Survival DC 15 (limited) · Watch: Kael (passive 13; fast pace −5 → 8)
  · Forced march: 10 h > 8 h`, then one CON save line per hour from hour 9 (DC 11, +1
  each hour after: 10 + the hours past 8). A road leg says `Navigate: on the road (…) —
  no check`. The second call takes the rolled totals and runs the journey: a failed
  navigation (getting lost on) walks the road legs before the first trackless one,
  then picks a wrong bearing (d6: 1–2 60° left, 3–4 60° right, 5 120° left, 6 120°
  right of the intended one) and spends 1d6 h on it at trackless pace, then prints
  `Lost: … the navigator may check again`; the party ends up where that bearing led,
  measured in the top (`world`) frame, never at the destination:
  `party-location: "@lost"` with `lost: to hollow · at (x,y,0) world · bearing N (meant
  NE) · terrain forest · since …` (PCs `location: "@lost"`). `travel <to>` from there
  is straight-line cross-country at trackless pace (the navigator checks again); an
  arrival clears `lost:`. Forage yields `1d6 + WIS mod` lb (added as rations: 1 lb a
  day) and fills the waterskin; it is food, so under `supplies: off` (the default)
  nothing is counted or added. Encounter rolls print the watchers' passives (only they
  notice an ambush). Forced march hours ask for the CON saves (`gm.py save … con 11`,
  then `exhaust`); the hours marched are `--hours`, else the trip's length.
  `getting-lost` applies only to legs off the roads (kind trail, trackless, marsh,
  scree, and `--overland`), never to `road`, `street`, `path` or `lane`. Navigation
  DCs: grassland and coast 5; arctic, desert, hills, sea 10; forest, jungle, swamp,
  mountains 15; no `terrain:` → 10. `travel-detail: summary` (the default) keeps the
  one-packet journey and asks for nothing.
- **Marching order** `order` writes `marching-order:`; `travel` and `scene enter`
  print it; when an encounter is rolled on the road the travel output names the front
  and back rows (`Ambush: from ahead it meets Kael first; from behind, Grusk`), and
  `trap trigger` without `--who` springs on the front row.
- **Social DCs** (`social-dcs: dmg`; 02 → Social stakes). `check … --vs <npc> --ask
  <size>` reads the NPC's attitude (and faction renown, Phase 15) and takes the
  starting DC from the 02 table (no "won't": the hardest cell is 30). Then, in order:
  `--leverage` (−5..+5) adds; `--flair` with `moved-by:` applied (±1 step, 0–3: the
  GM names the kind of pitch with `--appeal <taste>`, +1 when the NPC is moved by it;
  `nothing` takes one off any flair pitch; `--grates` takes one off; a `--pitch` tag
  already in `state/social.md` for this NPC scores 0) takes off the `creativity` steps
  (light 2/5/8 + advantage at 3; generous 5/8/10 + advantage from 2; off 0); the wall
  stage takes one band (5) off when `fails` ≥ `social-wall` and this attempt's skill or
  `--why` isn't in `approaches`. DC floor 0. Under `social-dcs: gm` the GM's `--dc N`
  is the starting DC. With `--ask`, the number after the skill is the player's total
  (not a DC). A flair ≥ 1 without `--pitch` is an error (the repeat check needs it).
  The whole sum prints for the GM and logs as one `(GM)` line written **before** the
  roll result (the DC call and the roll call log it once):
  ```
  [social] Kira persuasion vs toll-keeper · hostile · major: DC 30
    leverage 0 · flair 3 (moved by audacity: 2→3, "goat grandfather"): −8, advantage
    wall: 2 fails on "cross the bridge" (stage 2: he names his price) → DC 22
  ```
  Without a `<total>` it stops there (the GM tells the player what to roll, foreseen
  or blind, with advantage when given); with one it resolves and prints the tier:
  `yes, and` (beat by 5+) · `yes` · `yes, but` (missed by < 5, flair ≥ 2) · `no, but`
  (missed by < 5) · `no, and — consider: attitude toll-keeper hostile` (missed by 5+;
  the attitude change stays the GM's `attitude` call).
- **The wall** (`social-wall: <n>`). With `--goal`, a failure adds to that row's
  `fails`, `approaches` and `pitches` in `state/social.md` and prints the stage cue:
  `stage 1: show a feeling` · `stage 2: have them name what it would take` · `stage
  3+: a different approach starts a band lower; offer a route around them`. A success
  removes the row (logged `[social] cross the bridge — won after 3 tries`). `social
  status` lists open goals (the brief adds `Social: toll-keeper "cross the bridge" 2
  fails` while that NPC is on stage); `social drop` closes one the party gave up on.
  `social-wall: off` → no goal rows, no stages (a pitch tried without a goal, or while
  the wall is off, goes on the NPC's `—` row so a repeat still scores 0).
  `social wall off|on|<n>` writes the setting
  (campaign.md, else `current.md`; `on` = 3) with a public log line `[social] wall
  off (table's choice)`; open rows are kept, so switching it back on resumes them.
  `intro` on the first session adds (after the `[INTRO …]` line) `[TELL THE TABLE] social-wall on: mention once,
  plainly, that repeated tries with an NPC can get easier and that they can ask to
  turn it off` (nothing when it's off).
- **The scenario guard.** An ask the GM marks `--core` (it would break the core
  scenario, 02 → Player plans) prints `[social] no roll: core scenario — steer to
  another route to the same goal` and exits 1; nothing else refuses.
- **Morale** (`morale: on`). `combat next` tracks, per foe unit (a group row and the
  members split off it, or a single creature), the triggers (a creature below half its
  HP, a `leader` (notes) down, half the side down) and prints `[Morale (half HP): Thugs
  — WIS save DC 10 (gm.py save Thugs wis 10); fail → flee or surrender (gm.py cond Thugs
  +fled | +surrendered)]` once per unit and trigger; the Combat block keeps `Morale: thug
  (half HP)`. Exempt: SRD type construct, ooze, undead (unless the stat block is an
  intelligent one: `morale` in its notes), and `morale: fearless` (row notes or NPC
  frontmatter). The party side never checks (a hireling does, against DC 20 − loyalty: Phase 15). `cond Thugs +fled` / `+surrendered`
  removes them from the turn order; `combat end` counts both as defeated for `xp
  award` and adds surrendered foes to On stage as `prisoner`; neither condition is
  written back to a file.
- **Chases** (`chases: dmg`). `chase start` writes `## Chase` (04) in the Combat
  block's place: quarry at `--lead` (default 60), pursuers (default: the scene's PCs) at
  0, speeds from the files (exhaustion applied), Dashes `used/free` with 3 + CON mod
  free; the order is quarry first, then pursuers as named. `chase next` is the turn of
  the participant who is up: they move their speed, doubled by a Dash (the default;
  `--no-dash`; `--lose N` for ground a complication cost). `chase dash <who>` is an
  extra Dash (a bonus action). A Dash past the free ones is a DC 10 CON save or
  `exhaust +1`: asked of a player, rolled for an NPC (a failure applies the level).
  Then the tool rolls d20 on `tables/chase-<env>.md` (the campaign's, else the engine's
  `engine/templates/tables/chase-urban.md` / `chase-wild.md`) for the next participant
  (1–10 complication; an `effect` of `los` hides a quarry), and after the quarry's
  turn, if it is out of the pursuers' sight (gap > their sight: bright 120 ft urban /
  300 ft wild, dim half that, dark their best darkvision; or a `los` complication),
  tests its Stealth against the pursuers' best passive Perception (rolled for an NPC;
  a PC quarry is asked, and the GM ends it `escaped` on a win). A pursuer reaching
  the quarry → `[chase end · caught: start combat or grapple]`; an escape → `[chase
  end · escaped]`. `chase end` moves the clock by the rounds run (6 s each, rounded up
  to the minute; while split, the active group's clock). Combat start and travel
  refuse while a chase runs.
- **Traps.** `trap trigger <id>` resolves the line's effect on `--who` (default: the
  marching order's front, else the first PC): it asks a player for the save total
  (nothing changes until it comes), then rolls damage, applies `hazard fall` and
  conditions. Effects: `<ABIL> save DC N or <consequence>` (`(half on a success)` for
  damage), `+N to hit, <damage>`, or a bare consequence; a consequence is `fall N ft`,
  `NdM <type>` or a condition (`poisoned 1h`). `trap disarm <id> --who Kira <total>`
  compares against the disarm DC (a miss by 5+ triggers it on the disarmer; an NPC's
  total is rolled), `trap status` lists the site's traps as `(GM)` lines. `state:` is
  written back on the `## Hidden` line. `scene enter` reveals an armed trap to a PC
  whose passive Perception beats its DC as `TRAP pit (<trigger>)` only. `(GM …)` notes
  on the line, the disarm and the effect text go only to `(GM)` lines.
- **Hazards.** `fall` rolls 1d6 per 10 ft (max 20d6), applies it and `+prone` (under
  10 ft: nothing). `breath` starts the clock on a creature: the condition
  `holding-breath 3m` (1 + CON mod minutes, min 30 s; rounds in combat), then
  `choking 2r` (CON mod rounds, min 1; out of combat it shows as `choking 1m`), then 0
  HP and dying; the clock and `combat next` turn one into the next.
  `env` sets `environment:` and `environment-since:`; with `extreme-cold`/`extreme-heat`
  the clock asks the hourly CON saves (cold DC 10; heat DC 5 the first hour, +1 each hour after,
  skipped by anyone with water while supplies are tracked) for every PC not exempt
  (cold-weather gear or cold resistance; heat: fire resistance, or heat adaptation in
  `senses:`/features). `thin-air` is recorded only. `underwater` adds the
  attack rules to `atk` (melee disadvantage except dagger, javelin, shortsword,
  spear, trident; ranged auto-miss past normal range and disadvantage within it
  except crossbows, nets and thrown javelin, spear, trident, dart) and fire
  resistance.
- **Hiding.** `hide` adds `hidden <total>` to the creature (its Combatants row, else
  frontmatter `conditions`; a Stage row has no conditions column, so an NPC needs a
  file) and prints every watcher whose passive Perception is at least the total
  (`spotted by Veskar (passive 14)`) and the rest (`unseen by …`); watchers are the
  other side in a fight, else the NPCs on stage for a PC and the PCs for an NPC. An
  NPC's total is rolled when none is given. With `--group`, the group is hidden if at
  least half beat the watchers' best passive (each stored at their own total), else
  nobody is. `seek` compares an active Perception total against every hidden creature
  on the other side and removes `hidden` from those it beats; who stays hidden is a
  `(GM)` line. An `atk` from a hidden creature has advantage and then removes
  `hidden`; `scene enter` (`Hidden: Kira (17) — unseen by …`) and `combat start`
  compare who is there against stored totals (reported; the GM acts on it).
  In bright light with no cover or obscurement within 5 ft on the map the tool warns
  `Kira is in plain view?` (the GM decides).

### Phase 15 — optional subsystems

```
gm.py inspire Kira ["the toast to the dead"] | atk|save|check … --insp
gm.py ready Kira "shoot whoever opens the door" [--spell hold-person] | ready Kira fire | ready Kira drop
gm.py attune Kira "<item>" --during-rest | unattune Kira "<item>" | charge Kira "<item>" -1|+2|=7
gm.py identify Kira "<item>" [--spell] | rest short [--attune Kira="<item>"] [--identify Kira="<item>"]
gm.py srd item "<magic item>"                       # the SRD text and the inventory tags it implies
gm.py downtime Kira craft "chain shirt" 10d [--lifestyle modest] [--value "50 gp"] [--goal 10d] [--no-clock] | downtime status
gm.py companion add Kira Ash srd:owl --acts own|with|mount [--hp 1/1] [--note "…"] | companion drop Kira Ash | companion list
gm.py hire "Bren" --wage "2 gp/day" [--by Kira|party] [--loyalty 10] [--statblock guard]
gm.py weather [roll | set "heavy rain, strong wind, cold" | clear]
gm.py renown ["Red Ledger" +1|-1|=3 "returned the ledger" [--who Kira] [--rank "…"]]
gm.py mount Kael Horse [--independent] | dismount Kael
gm.py injury Kael [--roll N]                        # lingering-injuries: on
gm.py pc card Kira                                  # a written PC: live numbers, items, load
```
- **Bookkeeping.** Anything that charges coin over time (lifestyle, crafting materials,
  training fees, hireling wages) moves money only under `upkeep: on` (default off, the
  table's preference); otherwise the line says what it would cost and nothing is taken.
- **Inspiration.** `inspire` sets `inspiration: true` (refuses a second; refuses under
  `inspiration: off`); `--insp` on a d20 command spends it (the key is removed): advantage
  (`advantage`), or under `reroll` the given d20 is the reroll and stands (after a roll
  the player wants back: `undo`, then the command again with the new d20). It is spent
  only once every other check passed. Party line: `★`.
- **Readied actions** (combat only). `ready` writes `ready: …` into the combatant's
  `conditions` (commas become `;`) and spends nothing until it fires; `ready fire`
  spends the reaction; `--spell` casts it now (the slot is spent when readied, the line
  says so) and holds it with `conc` until released (`fire` keeps concentration only for a
  concentration spell, which then runs its own duration). `combat next` clears an unfired
  ready at the start of its owner's turn (`lapsed (unused)`) and, before every other
  combatant's turn, prints `Readied: Kira — shoot whoever opens the door` (the tool can't
  judge the trigger; the GM does). `combat end` drops it.
- **Magic items.** `attune` refuses without `--during-rest` (naming the `rest short
  --attune` that does it), an item without `attune`, an unidentified item, one already
  attuned and a fourth. Bracketed numbers on an equipped (and attuned if needed) item feed
  the numbers live: AC, saves, and `attack`/`damage` for the Attacks row the item names
  (an item naming no weapon counts for every attack); the file's `ac:` stays the base and
  `overrides` win. `charge` spends or restores charges; spending the last one of a
  `destroy on 1` item rolls the d20 then (RAW), and a 1 removes the item. The clock rolls
  each item's recharge at its time (`dawn`, `dusk`, `midnight`, `noon`) for PCs' and NPCs'
  items below their maximum. `identify` (or `rest short --identify`) swaps the line to its
  `(GM: …)` true name with the SRD's tags; `(GM: …)` never reaches a public log line or
  `pc card`. Data: `data/srd/5e-SRD-Magic-Items.json` (fetched by `fetch_srd.py --only
  Magic-Items`). `pc card <pc>` on a written PC (no draft) prints the live AC (`AC 15 (14
  + items)`), saves, attacks, `Magic items: … · attuned n/3` and the load.
- **Downtime.** `downtime <pc> <activity> [subject] <days>` (light: craft, train,
  research, recuperate, work; full: plus campaign tables `tables/downtime-<activity>.md`,
  rolled once per call as a `(GM)` complication) adds progress to `## Downtime`, records the
  lifestyle (wretched 0, squalid 1 sp, poor 2 sp, modest 1 gp, comfortable 2 gp, wealthy
  4 gp, aristocratic 10 gp a day; none while working), and advances the clock by the days
  (the whole party; the usual `[TIME]` packet follows; `--no-clock` for all but the
  longest PC). Crafting: 5 gp of market value per day toward the SRD price (or `--value`),
  half the price in materials when the work starts; done → the item joins the pack.
  Training: 250 days at 1 gp a day; done → a Features line. Other activities count days
  toward `--goal`. Under `upkeep: on` the coin is taken (refused up front when the purse
  can't cover it).
- **Allied creatures.** `companion add` writes a `## Companions` row; `combat start` adds
  the companions of the PCs in the fight as `party` rows with `ctrl <PC>` (own init:
  rolled as a monster or `--init Ash=N`; `with` / `mount`: the controller's initiative,
  placed directly after them). `combat next` on a controlled row prints `up: Ash (Kira's)`,
  so the GM asks Kira; `combat end` writes its HP back to the row. `hire` makes (or
  updates) an NPC with `hired-by:`, `wage:` and `loyalty:` (hirelings join a fight on the
  party's side); under `upkeep: on` the clock charges wages each dawn (a PC employer pays
  from their coin; a party hire prints what is due). A hireling below half HP, or with
  half the party side down, checks morale once per trigger: WIS save DC 20 − loyalty.
- **Weather** (`weather: on`). At each dawn the clock rolls temperature, wind and
  precipitation (d20 each: 1–14 normal / 15–17 colder by 1d4×10 °F / 18–20 warmer;
  wind 1–12 calm / 13–17 light / 18–20 strong; precipitation 1–12 clear / 13–17 light
  / 18–20 heavy, snow at or below 32 °F) per the area's `climate:` (base °F: arctic 0,
  cold 30, mountain 40, temperate and coast 60, warm 75, tropical 85, desert 95; the roll
  detail is a `(GM)` log line) and writes `weather-now:`. Effects outdoors only:
  strong wind gives disadvantage on ranged weapon attacks (a thrown weapon beyond 5 ft),
  puts out open flames (`lit` torches and candles go out at once; lanterns don't;
  lighting one prints a warning) and grounds non-magical flight; Perception notes (heavy
  precipitation: by sight; strong wind: by hearing) are printed on Perception checks, not
  applied, since the tool can't know the sense. ≤ 0 °F / ≥ 100 °F set `environment:
  extreme-cold | extreme-heat` (Phase 14); a later non-extreme roll clears an environment
  the weather set. The brief header carries it: `· light rain, cool` (`calm`/`clear` left
  out).
- **Encumbrance** (`encumbrance: basic|variant`). Inventory weight from the SRD
  equipment data (bundles per item, `(N lb)` for custom items, coins at 50 per lb;
  unknown entries weigh nothing and are listed by `pc card`); the thresholds in 02. `pc
  card` shows `load 62/120 lb`; the speed change goes through `turn`/`move`/`chase`
  (turnstate.speed_of) and `travel` (on foot the trip takes base speed / the slowest
  loaded PC's speed times as long, with a note); `variant` heavy load adds the
  disadvantage in the resolver (attacks; STR/DEX/CON checks and saves). Party line
  `[enc]` / `[heavy]` (basic over capacity is `[heavy]`, speed 5).
- **Renown** (`renown: party|per-pc`). `renown` edits `state/factions.md` with a
  reason (public log line); rank names are the campaign's (`--rank`, free text). The
  attitude shift for the faction's NPCs (02) applies in `brief` (`Mara (wary→neutral,
  Red Ledger 3)`; per-pc: each PC's shifted attitude) and the social DC (`· wary→neutral
  (Red Ledger 3) · major: DC 25`; per-pc: the checking PC's standing).
- **Mounts.** `mount` links rider and mount (`mounted on Horse` / `ridden by Kael`); in
  combat both need rows, and a controlled mount (default; `--independent` otherwise) takes
  the rider's initiative right after them (`ctrl Kael`) and `combat next` reminds that it
  may only Dash, Disengage or Dodge; out of combat the mount is one of the rider's
  Companions (`acts: mount`), seated again by `combat start`. `cond <rider> +prone` asks
  for the DC 10 DEX save (fall prone within 5 ft); `cond <mount> +prone` drops the rider
  unless they spend their reaction. Forced movement isn't detected (the GM asks the same
  save). Vehicles are SRD equipment rows (cart, boat, ship speed and HP) used by `travel
  --by`.
- **Lingering injuries** (`lingering-injuries: on`). On a crit against a PC or a drop
  to 0 HP, `hp`/`dmg`/`atk` append `[consider: gm.py injury Kael]`; `injury` rolls on the
  campaign's `tables/injuries.md` (`| roll | result | effect | cure |`; the engine ships
  none) and writes the result to `## Features & abilities` as `(injury)` with its cure.

### Phase 16 — table extras (02 → Dice → Pre-rolls; 02 → Table mechanics → Phase 16)

- **Pre-rolls on `check`/`save`/`contest`:** `--total 17 --rolled-as perception` takes
  off the named skill's bonus and puts on the bonus of the skill being checked (when the
  difference is a die face 1–20 it becomes that die, so advantage still works; otherwise
  the total is shifted). `--rolled-as` takes a skill, an ability or `dex save`; on a
  contest it follows `--d20/--total`. The line shows both: `[Kira investigation
  (reported as perception total 17): d20 12+3=15 vs DC 15 — SUCCESS by 0 (tie→PC)]`.
  `--d20 14,6` gives two dice for advantage/disadvantage on every d20 command, `atk`
  included (two dice with neither: the first counts, `second die 6 unused`). With one die
  and advantage or disadvantage from any source (asked for, exhaustion, a load,
  inspiration), the tool rolls the second die publicly: `d20 (14, tool 9)→14+7=21 …
  (advantage: second die rolled)`. A total whose skill isn't stated is taken as reported.
- **`gm.py carouse <pc,pc> [--table carousing] | carouse --reroll <pc>`** (refused while
  `carousing: off`, the default): rolls the night's cost and one d100 per PC (GM-side
  output, never pasted). A row whose `tags` share a word with a campaign `lines:` entry
  is re-rolled automatically (`re-rolled 9 (line: harm to animals)`: erring towards the
  re-roll); one touching a `veils:` entry is marked `(veil: off screen)`. The tool
  applies the effect codes (`coin ±2d6x10 [sp]`, `item +"…"`, `item -"…"`, `item -random`
  — one whole pack entry, `clock +3d "…"` — a `## Clocks` bullet due that long from now,
  `no-rest`) and prints the rest as `[file for Kira: …]`. A cost or loss beyond the purse
  takes what there is and files the rest as a debt clock (7 days). Every delta it writes,
  coin and items included, is a `(GM)` log line, and `(GM) [carouse] Kira 47: "…"` names
  the row. The night per PC goes to `state/carousing.md`; `--reroll` reverses that row's
  applied codes (never the cost), rolls a different row and logs GM-only. The clock goes
  to the next morning only through the GM's own `clock advance` in the same batch.
- **`gm.py table import <file> --as <name> [--die d100]`:** normalizes pasted
  `01-05 text`, `01–05. text`, `7: text`, `1. text`, `00 text` or `| 01-05 | text |` lines
  into `tables/<name>.md` (`| roll | result | effect | tags |`; a line without a number
  continues the one before). `die:` is `--die`, else the highest roll; `--as carousing`
  adds `cost: 1d6x10gp`. It reports gaps, overlaps and rows past the die, and never
  guesses effect codes or tags; those are left blank for the driver to fill in. The
  shared reader is `lib/tables.py`.
- **Crit die in `atk`:** with `crit-die: on`, any crit rolls the campaign's
  `tables/crit-die.md` (else the engine's starter; die = number of rows; `--crit-die N`
  types in a physical die) and applies the known codes (`dice x2` — the `crit-damage`
  table rule still applies —, `dice x3`, `max+dice`, `prone`, `stunned 1t` — `1r` when the
  target still acts this round, `2r` when it already has —, `disarm` — a `dropped <weapon>
  at (x,y,z)` note on its row and a public log line —, `bleed 1d4` — the condition
  `bleeding 1d4`, rolled and applied by `combat next` at the start of each of its turns,
  ended by healing or `cond X -bleeding` —, `kill` — HP to 0). A row with no damage code
  and no `kill` deals `dice x2`. The output line gains `· CRIT DIE d10 → 6 dice x2;
  disarm`. A `kill` on a PC follows `crit-die-pcs` (dying: 0 HP and dying, or two death
  save failures when already down; dead: dead). A creature with Legendary Resistance
  left spends one: the kill becomes `dice x3` and `[LR: Veskar spends a Legendary
  Resistance: kill → dice x3]` follows (a tracked `legendary resistance` Resources row is
  spent). An effect that can't apply (no weapon to drop: an attack named bite, claw …;
  already prone or stunned) is dropped, the damage falls back to `dice x2`, and the line
  says so. Codes the tool doesn't know print as `[crit die: … — narrate and file it]`.
  With `crit-die: off` `atk` is unchanged. Checks and saves never roll it.

## Build order

| Step | Contents | Why first |
|---|---|---|
| 2a.1 | `lib/md.py`, `lib/campaign.py`, `lib/journal.py`, `gm.py` skeleton + `do` | everything else builds on these |
| 2a.2 | `roll`, `atk/save/check/contest`, mutations, `log`, `undo`, `rule`/`retcon` (+ resolve.py keys) | biggest per-turn saving; table rules change resolve.py, so they're built with it |
| 2a.3 | `brief` + hooks + permissions allowlist | removes the per-turn Read |
| 2a.4 | `lib/geo.py` (Places/Routes parsing, offsets, bearings, route times), `scene enter` (with Exits/Nearby), `tempo` + `pos` with `@feature` placement, `combat start/next/end`, `srd`; `space.py` reads the Stage table, honors walls, and does `move --to` pathfinding (done 2026-10-04), then moves its parsing onto `lib/md.py` | needed before the Phase 3 dry run: the inn fight uses named placement, named moves and walls |
| 2a.5 | `table.py` client + `space.py map --player-view` | the Phase 3 dry run is played through it, so console leaks surface early |
| 2a.5b | `gm.py pc` (draft/check/card/write/edit/levelup/roster) + SRD class/race/equipment data | the dry run creates one new PC and levels a pregen, to exercise both loops |
| 2a.6 | `clock` (with in-transit moves), `travel`, `rest`, `lint`, `session archive`, `stub`, `where`, `world add/place/lead/reveal`, `trace`, `odds`, `spoil` | build when the dry run shows the need (`odds` reuses the 2a.2 resolve/dice code) |
| 2a.7 | `combat reframe`, `world place` suggestions, `world import`, `space.py map --place` (area/world maps) | deferred until play asks for them; none is needed to run the POC |
| 2b | GM skills (02), written to call these commands | |
| 2c | `campaign`, `encounter budget/build/threat`, `danger`, `loop` (mechanic-gated); `/campaign new|scenario|fill|status` authoring skills (07); `rules/mechanics/time-loop.md` | the first real campaign is authored with these and uses the loop mechanic; `encounter build` replaces fixed rosters in the GM's `/combat` recipe |
| 2d | `split` (02 → Splitting the party) | built 2026-10-06 |
| 2e | `conc`, `deathsave`/`stabilize`, `light` + `lib/light.py`, `eat` + supply spending, `exhaust`, `campaign boundaries` + `!x` (Phase 13) | the state an AI GM most often loses or gets wrong, each plugging into existing tools (`dmg`, `combat next`, `clock`, `rest`, the brief) |
| 2f | travel activities + `order`, social DCs, morale, `chase`, `trap`, `hazard`, `hide`/`seek` (Phase 14) | more design per item; morale and travel first (the current scenario meets both) |
| 2g | `inspire`, `ready`, magic items, `downtime`, companions, `weather`, encumbrance, `renown`, mounts, injuries (Phase 15) | toggles and rarer situations; build on demand, in any order |
| 2h | pre-rolls (`--rolled-as`, two-die `--d20`), `carouse`, `table import`, crit die in `atk` (Phase 16) | table-requested extras; pre-rolls need nothing new and can go first |
| 2i | `table.py` Discord bridge: queue/auto modes, posting, player map (Phase 17) | remote players; needs only the Phase 5 client |

Each step ships with seeded tests in `engine/tests/` against a fixture copy of `campaigns/poc/`.
POC content files are migrated to the new formats (04) in step 2a.1.

## Open questions

1. ~~Frontmatter parser~~ **Decided (2026-10-02): stdlib YAML subset** (Parsing contract
   above). No PyYAML.
2. ~~Dice mode default~~ **Decided (2026-10-02): players roll their own d20s**
   (`dice-mode: players-roll-d20s`). The GM rolls everything else. `gm-rolls-all` stays
   available as a per-campaign switch.
3. ~~Brief verbosity~~ **Decided (2026-10-02): hybrid**: full brief on change,
   one-line heartbeat otherwise, forced full every 15 prompts (Tier 1 → brief + hooks).
4. ~~Lint timing~~ **Decided (2026-10-02): write-time validation + touched-files check
   per batch + full sweep at scene/combat/session boundaries; no `Stop` hook**
   (Tier 3 → lint).
5. ~~Secrets in tool output~~ **Decided (2026-10-02): honor system for files; the
   table client hides all tool output from the console** (Table client section).
   Tools print freely to the GM. Only narration rules (02 → Behind the screen) and
   player-view renders govern what players see.
