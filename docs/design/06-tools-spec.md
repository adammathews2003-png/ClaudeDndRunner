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
`key: scalar` · `key: [a, b]` (inline list) · `key: {a: 1, b: 2}` (one-level inline map)
· `# comments` · quoted strings. **No nested blocks, no multi-line values.** Anything
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
Rules: R1 potions=bonus (campaign) · R3 crit 19–20 (combat)
Watch: Harl asked of Mara → beat 1 · mill → beat 3   Next clock: Day 3 04:00 (Red Ledger cart) in 1d 8h
Combat: — 
Log: turn 14 open (2 deltas)
```
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
  foes defeated, routed, captured or talked down; fled foes count only if the GM says
  so (`--count-fled`).

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
- **Counting.** The brief hook adds 1 to `exchanges` for each player prompt (not `/`
  or `!` lines); `combat next` rounds are read from the Combat block. `split cut`
  resets both. Nothing cuts automatically: the brief says when a cut is due and the
  GM picks the moment.
- **Choosing the next group:** `split cut` with no group picks the one with the
  earliest clock (ties → the one that waited longest). It refuses a group more than
  one slice ahead of the earliest unless named explicitly with `--force`.
- **Sensing:** same site → yes; otherwise `geo` distance between the groups' locations
  ≤ `split-sense-ft`, or ≤ a PC's sight range when the other group's light makes it
  visible, or ≤ any special sense in `senses:`. Unknown distance → no, with a
  `[split: distance unknown, sense off; override with split sense]` note.
- **Clocks:** `clock`/`time` advance the active group's `in-game-datetime`. World
  CLOCK beats and NPC schedules fire only when the **earliest** group clock reaches
  them. A `time` that would put the active group more than one slice ahead of the
  earliest warns `[split: mill would be 40m ahead of inn — cut first or summarise]`.
- **join** requires both groups at the same site; the result's clock is the later of
  the two (the earlier group's gap is printed for the GM to summarise), On stage and
  Watch for are unioned, and an active combat on either side becomes the merged
  Combat block (the newcomers roll initiative and enter at the next round).
- **Brief while split:** the header shows the active group; one line per waiting group
  and the slice counter, e.g.
  `Split: ▶ mill (Grusk) exchange 2/3 · inn (Kael, Kira) crossroads-inn/yard Day 1 21:09 calm — 1m behind`
  and, when one is due, `Cut due: inn is behind` or `Cut every round: inn can hear the fight`.
  Absent (autopilot) PCs travel with whichever group they were put in.

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
