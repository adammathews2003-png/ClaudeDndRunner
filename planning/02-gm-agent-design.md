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
| `/map` | combat start, or a player asks | `gm.py space map --player-view --from <active>` and shows the grid + legend |
| `/overrule` | players agree to change something | Table authority: retcon what happened, or add a temporary/permanent table rule. Restate, confirm, apply (see *Overrule* below) |
| `/spoilers` | players want to peek behind the screen | Answers questions about secrets, or "what if" alternatives, from state + history. Consent card first; never creates canon (see *Spoilers* below) |
| `/end-session` | wrapping up | Writes summary + world tick, `gm.py session archive` (history, lint, git commit) |
| `/new-campaign` | scaffolding | Creates a campaign folder from the templates in 04-file-formats.md, sets `.campaign` |

Play runs through the table client (`python tools/table.py`, 06), which shows players
only the GM's narration. Tool calls, tool output, thinking and the injected brief stay
hidden. So **the GM's narration is the only thing players see**, and the
*Behind the screen* rules below govern it.

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
  pickpocket), the GM rolls silently and narrates only outcomes (see *Behind the screen*).

## Dice

Default: **players roll their own d20s and report totals; the GM rolls everything else**
(NPC attacks, damage, secret checks, random tables). GM rolls go through `gm.py roll` /
`atk` / `save` / `check` / `contest` (06), which use a real RNG and also do the
arithmetic, crits and the ties-go-to-PC rule. Results are never "picked" or added up by
the model, so outcomes are honest. Player-reported rolls go into the same commands
(`--d20 12` or `--total 19`). The GM pastes the tool's bracket line into narration
(`[Veskar → Kael: 13+5=18 vs AC 15 — HIT · 7 slashing]`), except for secret rolls.
`dice-mode: gm-rolls-all` in `current.md` switches to the GM rolling everything.

## Behind the screen (what narration may never contain)

The person at the keyboard is a player. The table client hides the machinery, but the
GM's own words are shown verbatim, so these rules are the last line of defense. They
go in the `/gm` skill near the top. **The single exception is a confirmed `/spoilers`
answer** (below), and the rules apply again immediately after it.

**Never say, in or out of character:**
- Beat names/numbers, triggers, Watch-for items, clocks the party doesn't know about,
  or that a beat "fired".
- DCs of hidden things (`## Hidden`, secret checks), or who *failed* to notice
  something. Only those who succeed get a narrated notice.
- True identities, factions, motives or plans the party hasn't uncovered ("Veskar,
  the Red Ledger agent").
- NPC intents before they act. In tense scenes the order may show ("Mara is faster —"),
  but not what she's about to do.
- File paths, section names, tool names, or "the scenario/notes say…".
- Monster stat blocks, exact enemy HP, or AC. Describe them in fiction ("bloodied",
  "barely standing"). PCs' own numbers are fine.
- Off-screen events the party has no way to know.

**Rolls.**
- Public rolls are pasted as the tool's bracket line. Secret rolls appear only as
  `[rolled behind the screen]`, or not at all when even the act of rolling would tip
  players off.
- **Decoy rolls:** now and then the GM makes a meaningless secret roll, so a
  behind-the-screen roll doesn't by itself signal that something is happening (a real
  GM's habit).

**Pasting tool output.** Only lines meant for players get pasted: public roll lines,
distances the character could judge (Spatial model below), and the
**`--player-view` map**. Never paste `scene enter`, `clock`, `brief`, `srd` or full-map
output. Turn them into fiction.

**Out-of-character questions.**
- "Why did that happen?" / "What's really going on?" → "That's behind the screen."
  The answer is friendly and final, and isn't evidence of GM error (05 #3). Players who
  want a different outcome have `/overrule`, which changes things without opening the
  screen. Players who want to *know* have `/spoilers`. The GM doesn't point either
  one out.
- Facts already recorded in `sessions/spoilers.md` may be discussed out of character
  without a new card.
- Overrule cards (*Overrule* above) list only visible consequences. Hidden ones are
  "adjusted behind the screen."
- "Check the record" (05 #13) → answer from what the party knows. If the fact itself is
  secret: "Checked it behind the screen — it stands."
- Rules questions about the PCs' own capabilities are always answered openly.

**Recaps and summaries.** Session recaps, `/end-session` summaries and commit messages
are written from the party's point of view. Session-log lines tagged `(GM)` are left
out (06).

## Overrule (the players' table authority)

Players can change the game by agreement, and that's how the table keeps ownership of
its fun. `/overrule` is the **only** channel for it: dice results, rulings and outcomes
are otherwise final (05 #3).

**Two kinds**
1. **Retcon:** adjust something that happened. "Kira wasn't spotted on that climb";
   "Undo that last round, we misread the map"; "Mara wouldn't know our names, we never
   told her"; "Re-roll that, the die fell off the table."
2. **Table rule:** a rule change for a while, often from a game idea. "Crits on 19–20
   for this boss fight"; "Flanking gives advantage this session"; "No death saves in
   this tutorial fight"; "From now on, drinking a potion is a bonus action."
   Scopes: `scene` · `combat` · `session` · `campaign` · `until <condition>`
   (GM-judged, e.g., "until we leave the dungeon").

**Flow (two steps, never one)**
1. A player types `/overrule <what>` (free text; it can carry the kind and scope
   explicitly, e.g., `/overrule rule crits on 19-20 for this combat`).
2. The GM classifies it and **restates** it as a short card: kind, exact change,
   scope, and the *visible* consequences ("Kira gets her 6 HP back and isn't prone; the
   guard never raised the alarm"). Anything that followed from it behind the screen is
   adjusted silently, and the card just says so ("…and whatever followed from it behind
   the screen"). The card ends with: **"All players agree? (yes / no)"**.
3. On a `yes` covering all present players (one typed `yes` from the driver counts
   when they're the only player; otherwise name who agrees, e.g., `yes — Alex, Sam`),
   the GM applies it through `gm.py` (06) and resumes the fiction. `no`, or silence
   followed by new play, cancels it. Nothing is applied before confirmation.

**Applying it**
- *Retcon of the last GM turn:* `gm.py undo`, then a corrected re-resolution if needed.
- *Older retcons:* **corrective changes going forward**, never rewriting old turns:
  `gm.py retcon "<what>" --turn N` logs it, and ordinary mutations (`hp`, `cond`,
  `move-npc`, `attitude`…) fix the state in the same `do` batch. Hidden consequences
  are fixed with `(GM)`-tagged changes.
- *Past sessions:* allowed; the history file gets an appended **Erratum** line, and its
  original text is never edited.
- *Table rules:* `gm.py rule add` (06). Rules with a mechanical **key** (crit range,
  flanking…) are applied by the tools automatically. Free-text rules are the GM's to
  honor. Active rules appear in every brief, so they don't get forgotten.
- Scopes expire on their own: scene rules at `scene enter`, combat rules at
  `combat end`, session rules at `session archive`. `until` rules are ended by the GM
  with `gm.py rule end` when the condition is met, and announced in one line.
- At `/end-session`, campaign-scoped rules are offered for promotion to
  `rules/house-rules.md` (all campaigns) or stay campaign-only.

**Limits that keep it honest**
- **Overrule changes outcomes; it never opens the screen.** "Overrule: tell us who
  took Harl" is a request to reveal, not a change, so it belongs to `/spoilers`. The
  GM says only that overrule can't reveal things, without recommending the other
  command.
- **Conflicts with hidden facts.** If a player-declared fact ("there's a back door
  out of the mill") contradicts something behind the screen, the GM doesn't say what.
  It offers: *(a) make it true and adjust the hidden side to fit, or (b) decline and
  keep the world as is.* The table picks. (Choosing (a) reveals only that *something*
  was there, which is an accepted cost.)
- **Another player's PC** can't be changed (decisions, HP, items) without that
  player's own `yes`.
- **The GM never proposes, hints at, or invites an overrule**, especially after a bad
  roll. Complaints, groans and "that seems harsh" are not overrules, and not evidence of
  GM error. Only the explicit command counts. The GM may *answer* a rules question
  ("RAW, ties go to…") but doesn't suggest bending it.
- Overrules are logged publicly (`[overrule]` lines), so a table that overrules every
  bad roll can see it doing so.

## Spoilers (players opt in to peek behind the screen)

`/spoilers` is the **only** exception to *Behind the screen*. Players ask, and only
when they explicitly use the command. It covers two kinds of question:

1. **Secrets:** "Who actually took Harl?" · "Was Mara lying to us?" · "What was
   Veskar doing the night we stayed at the inn?" · "Did we miss anything at the mill?"
2. **What-ifs:** "What would've happened if we'd gone to the mill the first night?" ·
   "What if Kira had attacked Veskar on the landing instead of talking?" · "What if
   we'd never bought Tobin that drink?"

**Flow (the same two steps as Overrule)**
1. A player types `/spoilers <question>`. Optional depth: `hint` (a nudge in the right
   direction) · `answer` (default: just what the question asks) · `full` (everything
   connected to it, up to the whole `## The truth`).
2. The GM shows a **consent card** that describes the spoiler without spoiling it:
   - **Level:** `none` (a what-if answerable entirely from what the party already
     knows) · `minor` (a resolved thread or background detail) · `major` (touches an
     unresolved thread, the kind of thing the campaign is built around).
   - **Spill-over:** "Answering this also reveals related secrets; I'll keep to the
     question unless you ask for `full`."
   - **"All players agree? (yes / no)"**. As with overrule, a lone driver's `yes`
     counts; otherwise name who agrees. **Any one player's `no` cancels it.** A spoiler
     can't be un-seen, and it's shown to the whole table on one screen.
   - Level `none` skips the card and is answered directly.
3. On `yes` the answer is shown between spoiler banners, then play resumes under the
   normal *Behind the screen* rules.

**How the GM answers**
- **Sources:**
  - scenario `## The truth` and beats
  - NPC secrets and Movements
  - the session log **including `(GM)` lines**, plus history
  - clocks and current state
  - `gm.py trace` (where someone was, when) and `gm.py odds` (exact chances for
    checks and attacks) (06)
- **Every claim is labeled by certainty:**
  - **Established:** in the files or logs. *"Veskar left for the mill at midnight on
    Day 1, that's logged."*
  - **Likely:** follows from motives, schedules or clocks without dice. *"If you'd
    reached the mill that night, Veskar was there; he bargains before he fights."*
  - **Guess:** depends on rolls or choices nobody made. Cite odds where the tools
    can compute them. *"Kira's sneak attack hits him ~60% of the time; he'd likely
    have survived the first round and run."*
- **Honest, not flattering.** A what-if can show the party chose badly, or that it
  wouldn't have mattered. The GM doesn't soften a costly choice or inflate a lucky
  one (05 #3).
- **Undecided things stay undecided.** If the answer was never authored (what's in
  the locked strongbox, who Harl's sister is), the GM says so: *"Not decided yet.
  Here's what I'd lean toward, but it isn't canon."* The guess is not written down
  as fact, so the world stays open. Making it canon requires `/overrule`.

**Effects on the game**
- **What-ifs are never canon** and never change state. To turn a what-if into what
  actually happened, the table uses `/overrule` (a retcon) separately.
- **Secrets don't change because they were revealed.** The GM never swaps a twist to
  restore surprise. The world stays honest.
- **Characters don't learn it.** Spoiled facts are player knowledge, not character
  knowledge (05 #11). The table plays its characters as not knowing, and NPCs react
  to what the characters actually did.
- Every spoiler is recorded in `sessions/spoilers.md` (04). From then on, the GM no
  longer answers "that's behind the screen" for facts already spoiled; it can
  reference them out of character. In-fiction narration still treats them as unknown
  to the characters.
- The GM **never offers or suggests** spoilers, even when players are stuck. Being
  stuck is a pacing problem the GM solves in fiction (a new lead, an NPC's move, a
  clock), not with a peek.
- **Table switch:** `spoilers: ask` (default) or `off` in `current.md`. With `off`,
  `/spoilers` replies "the table has spoilers turned off" and nothing else, which
  suits groups who want to be protected from themselves. Changing the switch is an
  `/overrule` table rule.

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
- **ASCII map** (`/map` → `space.py map --player-view --from <active>`): top-down grid
  drawn from the terrain and combatant tables, north up, legend with each combatant's
  position, height and distance from the active combatant. `--player-view` leaves out
  what the party can't perceive (hidden/invisible creatures, `secret` terrain) and is
  the only version ever shown to players. Shown at combat start, on request, and
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
