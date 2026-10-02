# 06 — Tools Spec (scripts that take work off the GM model)

Status: **planned, not built** (except `tools/space.py`). Build in Phase 2a, before the
GM skills — the skills are written against these commands. Play runs through the
**table client** (`tools/table.py`, last section before Format changes), which shows
the player only the GM's narration; everything in this doc happens behind it.

## Why

`tools/space.py` set the pattern: the model decides *what* happens; a script does the
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

1. **One entry point:** `python tools/gm.py <command> ...`. One permission rule, one
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
`dnd-adventure/.campaign` holds the active campaign folder name (`poc`). Every command
defaults to it; `--campaign <dir>` overrides. `/new-campaign` and `/gm` set it.

### Names
Commands take a creature by display name, slug, or unique prefix (`Kael`, `veskar`,
`mara`). Resolution order: Combat block rows → On stage / Stage rows → `pcs/` → `npcs/`.
Ambiguous → error listing the candidates.

## Code layout

```
tools/
├── gm.py              # entry point: argument parsing, `do` batching, dispatch
├── space.py           # existing — spatial math + map (also: gm.py space ...)
├── lib/
│   ├── md.py          # frontmatter + markdown table read/write (shared with space.py)
│   ├── campaign.py    # locate files, resolve names, load PC/NPC/monster records
│   ├── dice.py        # expression parser, adv/dis, crits, SystemRandom
│   ├── resolve.py     # hit/save/check/contest outcomes, incl. ties-go-to-PC (one place)
│   ├── journal.py     # undo before-images + session-log delta writer
│   └── gametime.py    # "Day N HH:MM" parse/format/add
├── scene.py  combat.py  clock.py  travel.py  rest.py  lint.py  session.py  srd.py
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
the subset. (Alternative: depend on PyYAML — see Open questions.)

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
| `move-npc veskar old-mill` | sets `location:`; drops them from On stage if they left the scene | NPC frontmatter, `current.md` |
| `move-party village-square` | sets every PC's `location:` and `party-location` | PC files, `current.md` |
| `attitude mara friendly "paid for Tobin's drinks"` | sets attitude, appends to `## History with the party` | NPC file |
| `item Kira -dagger "taken by guard"` / `+ "brass key"` | inventory change | PC `## Inventory` |
| `coin Kira -5gp` | coin change | PC `## Inventory` Coin line |
| `res Kira -"spell slot 1"` | spend/restore a tracked resource | PC `## Resources` table |
| `time +20m` | alias for `clock advance` (Tier 3) | `current.md` |
| `log "Kira buys Tobin a drink; cart story told"` | closes the open turn block with this summary | session log |
| `undo` | rolls back the last `do` batch / single command | files in the journal |
| `rule add\|end\|list`, `retcon` | player overrules (below) | `state/table-rules.md`, session log |

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
Called by the `/overrule` skill **only after** the players confirm.
```
gm.py rule add "Crits on 19–20 for this fight" --scope combat --key crit-range=19 --by "Alex, Sam"
   → [rule R3 added · combat · crit-range=19]
gm.py rule add "Potions are a bonus action" --scope campaign --by Alex
gm.py rule add "No travel encounters" --scope "until we reach Thornbury" --by Alex
gm.py rule end R3 [--reason "boss down"]
gm.py rule list
gm.py retcon "Kira's climb went unseen" --turn 14 --by "Alex, Sam"
   → [retcon of turn 14 logged] (then corrective mutations in the same batch)
```
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
  rules set the same key, the newer wins, and `rule add` warns at confirm time.
- **Expiry:** `scene enter` ends `scene` rules, `combat end` ends `combat` rules, and
  `session archive` ends `session` rules. Each prints `[rule R3 ended — combat over]`
  for the GM to announce. `until …` rules end only with `rule end`.
- **Brief line:** `Rules: R1 potions=bonus (campaign) · R3 crit 19–20 (combat)`. This
  line is part of the heartbeat too, so active rules are always in context.
- **`retcon`** writes the public log line `[overrule] retcon turn 14: Kira's climb went
  unseen (Alex, Sam)`. The corrections that follow are ordinary mutations, logged as
  usual. Hidden ones are tagged `(GM)`. When the target is the latest batch, the skill
  uses `undo` instead.
- `--by` records who agreed. Under the honor system it isn't verified, just remembered.

**Undo journal.** Before each command, `lib/journal.py` saves the before-image of every
file it touches to `<campaign>/.gm/journal/` (last ~50 batches). `undo` restores the
latest batch and logs `undo turn 14 step 2`. This covers "check the record" corrections
(05 #13) between git commits.

### `gm.py brief` + hooks — state in context without a Read
`brief` prints a ≤ 20-line digest built from `current.md` + the files it points to:
```
[GM BRIEF] poc · Day 1 19:40 (evening) · crossroads-inn — Common room, dinner rush · tempo: tense
On stage: Mara (wary) goal: keep evening calm · Tobin (friendly) goal: tell cart story · Veskar (wary)
Order: Mara 17 · Kael 13 · Veskar 12 · Tobin 5
Party: Kael 9/11 AC15 · Kira 24/24 AC14 [poisoned 8m]
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
- Why: injecting the full brief every message costs ~350 tokens/prompt (~50k per
  150-turn session, all repeats on talk-heavy turns), which brings compaction sooner.
  Injecting only on change risks the model leaning on a brief 10–20 messages back. The
  hybrid keeps the critical facts beside every message for ~10% of the cost.

### Permissions
Project `.claude/settings.json` allowlist: `Bash(python tools/gm.py:*)`,
`Bash(python tools/space.py:*)` (plus `py` variants for Windows if `python` isn't on
PATH). A permission prompt mid-turn is the single slowest thing that can happen.

## Tier 2 — scene changes & combat

### `gm.py scene enter <location> [--light dim|dark] [--area common-room]`
One call replaces the `/scene` read fan-out. Output packet:
```
[SCENE] crossroads-inn (building, thornbury) · light: bright
Description: <body of ## Description>
Exits: village-square (front door, 1 min, obvious) · stable-yard (side door, 1 min) · cellar (trapdoor, locked, hidden DC 12)
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

### `gm.py tempo tense|calm [--adj "Mara +5 watching the room"] [--pos Mara 25,30,0 ...]`
- `tense`: passive initiative (10 + DEX mod ± adj, ties → PCs) for everyone on stage,
  written as a **Stage table** in `current.md` (Combatants columns; `init` = passive
  value; see 04). Positions come from `--pos`, or stay `?` and the GM places them with
  `gm.py pos Mara 25,30,0`.
- `calm`: drops the Stage table, keeps positions in the moves history.
- `gm.py intent Mara "get the letter off the bar"` sets this beat's NPC intent.

### `gm.py combat start | next | end`
- `start [--surprised Tobin] [--add "srd:thug x3 @25,15,0"]`: promotes the Stage table
  (or On stage list) to the `## Combat` block; copies Bounds + terrain rows from the
  location `## Layout`; rolls initiative (d20 + DEX; PC values via `--init Kael=15`
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
- `end`: writes HP/conditions back to PC/NPC files, marks dead NPCs
  (`status: dead` in frontmatter), leaves `## Combat (not in combat)`, sets tempo.

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
  Movements: Veskar 00:00 → old-mill (via stable yard)  [off-stage — applied]
  Conditions expired: Kira poisoned
  Clocks: none fired · next: Day 3 04:00 Red Ledger cart (in 1d 3h50m)
```
- **Off-stage** NPC moves are applied with `move-npc`. **On-stage** ones are listed as
  *intents* for the GM to narrate or override.
- Clock beats that fire are printed in full (the scenario line). The GM decides what
  happens.
- Named times: dawn 06:00, morning 08:00, noon 12:00, afternoon 15:00, dusk 18:00,
  evening 19:00, night 22:00, midnight 00:00, pre-dawn 04:00.

### `gm.py travel <to> [--pace fast|normal|slow] [--night]`
Looks up the connection from the party location (error if none: no teleporting), adds
its travel time (pace ×0.75/1/1.5), rolls the destination's or region's encounter
table if one exists (`tables/encounters-<region>.md`, chance by time of day), runs
`clock advance`, `move-party`, then `scene enter <to>`. Output = all three packets.

### `gm.py rest short|long [Kael ...]`
- **Long rest:** full HP, half hit dice back, `Resources` reset per their `recovers`
  column, 8 h on the clock (interrupted rests are the GM's call → `--interrupted`).
- **Short rest:** spend hit dice (`--hd Kael=2`, rolled), `short`-recovering resources
  back, 1 h on the clock.

### `gm.py lint [--fix-safe]`
Consistency sweep (05 #5 and more), exit code 1 on errors:
- one-way connections; connections to missing files; travel times that disagree between
  the two ends
- `location:` values naming missing locations; PCs not all in one place (warning)
- frontmatter outside the parsing contract; missing required fields per 04
- combat: positions out of bounds, two creatures in one cell (non-group), HP > max,
  `up:` naming someone absent
- On stage pointing to missing files; Watch-for beats no longer in any active scenario
- `--fix-safe` only does mechanical fixes (e.g., add the reverse connection stub,
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
   where cross-file problems (connections, missing files, stale Watch-for) matter.

Errors vs. warnings: unfinished-on-purpose things (an improvised NPC not stubbed yet,
terrain not placed) are **warnings** at layers 2–3 and never block. Only broken
references and unparseable files are **errors**. `session archive` refuses to commit
with errors unless `--force`.

Why not a `Stop` hook after every reply: it runs after the narration is already shown,
so any finding costs an extra model round trip and visible fix-up text mid-play; a full
sweep slows down as the campaign grows; and it would nag about deliberately-unfinished
canon. With layers 1–2, the only thing a per-reply sweep would catch sooner is a hand
edit to a file the current turn didn't touch, which can wait for the next scene boundary.

### `gm.py session archive`
`/end-session` mechanics: numbers the next `history/session-NN.md`, writes the
model-provided summary (`--summary-file`) plus the auto-extracted delta list (all
`  - ` lines from the log), resets `session-current.md` (`sessions/spoilers.md` is
never reset), clears `in-session`, runs
`lint`, then `git add -A && git commit -m "session NN"` if the folder is a repo (05 #4).
The model writes only the half-page summary and the world tick.

### `gm.py stub npc|location <name> [--location slug] [--note "..."]`
Creates a valid stub file from the 04 template (slug from the name, frontmatter filled,
body sections empty but present) and logs it. Makes "improvised canon → stub" (05 #6) a
single call. Refuses if the slug already exists (prints the existing file's path).

### `gm.py where [<name>]`
Who's at a location / where someone is, from frontmatter only. Cheap answer to "check
the record".

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

**`gm.py spoil log "<question>" --level minor|major --depth hint|answer|full --by "Alex, Sam" --reveals "<one-line summary of what was revealed>"`**:
appends to `sessions/spoilers.md` (04) and writes a public `[spoilers]` line to the
session log. Called **after** the answer is shown (a cancelled card logs nothing).
Level-`none` what-ifs are logged too, with `--level none`, so the record of what the
table explored is complete.

**`gm.py spoil list`** prints what's already spoiled, so the GM knows which facts no
longer need "behind the screen". The `brief --long` at session start includes the
count and the latest entries.

## Table client — `tools/table.py` (the players' console)

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
python tools/table.py [--campaign poc] [--new] [--model <id>] [--gm-view]
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
  overrule card and its "All players agree?" question are ordinary GM text, so the
  client shows them. `yes` / `no` is typed as a normal line.
- `/spoilers` passes through the same way. The GM wraps a confirmed answer in
  `<<SPOILERS>>` … `<<END SPOILERS>>` markers. The client renders them as a full-width
  banner in a distinct color (`── SPOILERS ─────`), so nobody reads one by accident
  while glancing at the screen. If the markers are unbalanced (e.g., the answer was
  cut off), the client closes the banner at the end of the message.
- Client-local commands start with `:` and are never sent to the GM: `:quit`
  (ends the client without ending the session), `:as <PC>`, `:gm-view on|off`.

**Permissions without prompts.** The SDK session can't show interactive permission
prompts (and a prompt would itself leak). The allowlist from 06 → Permissions is the
complete set of what the GM may do: `gm.py`, `space.py`, Read within `dnd-adventure/`,
and the skills. Everything else is denied, and the GM is told so and works around it.
Denials go to `<campaign>/.gm/client.log`, never to the screen. A frequent denial
means the allowlist or a skill needs fixing between sessions. A side benefit: the GM
can't wander outside the game folder mid-session.

**`--gm-view`** shows everything (tool calls, results, thinking), for building and
debugging. It falls under the honor system like the files. Prep, design and debugging
sessions keep using plain `claude`, which is effectively permanent GM view.

**Memory systems.** Loading project settings only should also keep user-level plugins
(e.g., claude-mem) and auto-memory out of play sessions, so play doesn't get recorded
and replayed as spoiler-laden summaries in later design sessions. Verify this when
building. If they do load, the client disables them for its session.

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
- **PC files:** frontmatter `mods: {str: -1, dex: 3, ...}`, `prof: 2`, `saves: [dex, int]`,
  `skills: {stealth: 7, perception: 5}`, `senses: [darkvision 60]`, `hit-dice: {die: d8, left: 3}`,
  `autopilot:` (05 #12); body tables `## Attacks` and `## Resources`.
- **NPC files with custom stat blocks:** same fields/tables as PCs.
- **`current.md`:** frontmatter `in-session`, `light`, `dice-mode`; a **Stage table**
  under `## Tempo: tense`; Combatants table gains a `ref` column.
- **New `state/table-rules.md`** for player overrules; `[overrule]` log lines; `Erratum:`
  lines in history files.
- **New `sessions/spoilers.md`** (spoiler record); `[spoilers]` log lines; `current.md`
  frontmatter `spoilers: ask|off`.

## What stays with the model

Narration and pacing · whether an action needs a check, and its DC · NPC intents,
lies and decisions · whether a Watch-for beat has actually fired · rulings and
house-rule interpretation · scene summaries and session summaries · placing new terrain
plausibly. Tools give facts and outcomes; the model gives meaning.

## Build order

| Step | Contents | Why first |
|---|---|---|
| 2a.1 | `lib/md.py`, `lib/campaign.py`, `lib/journal.py`, `gm.py` skeleton + `do` | everything else builds on these |
| 2a.2 | `roll`, `atk/save/check/contest`, mutations, `log`, `undo`, `rule`/`retcon` (+ resolve.py keys) | biggest per-turn saving; table rules change resolve.py, so they're built with it |
| 2a.3 | `brief` + hooks + permissions allowlist | removes the per-turn Read |
| 2a.4 | `scene enter`, `tempo`, `combat start/next/end`, `srd`; `space.py` also reads the Stage table (tense scenes) and moves its parsing onto `lib/md.py` | needed before the Phase 3 dry run |
| 2a.5 | `table.py` client + `space.py map --player-view` | the Phase 3 dry run is played through it, so console leaks surface early |
| 2a.6 | `clock`, `travel`, `rest`, `lint`, `session archive`, `stub`, `where`, `trace`, `odds`, `spoil` | build when the dry run shows the need (`odds` reuses the 2a.2 resolve/dice code) |
| 2b | GM skills (02), written to call these commands | |

Each step ships with seeded tests in `tools/tests/` against a fixture copy of `poc/`.
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
