# 02 — GM Agent & Skills Design

## How the GM is packaged

The GM is a set of **Claude Code skills** plus a campaign-level `CLAUDE.md` that loads the
core protocol every session. Skills to build in phase 2:

| Skill | Trigger | What it does |
|---|---|---|
| `/gm` (core loop) | start of play / each session | Loads GM protocol, sets `in-session: true` (turns on the brief hook), runs the **session-start routine** (roster → intake/level-ups → recap), then the turn loop |
| `/character` | new player, new PC, or "I changed something" | **Character intake loop:** free text (sketchy or a full sheet) → draft → derived numbers → ask only for what's missing → write the PC file (see *Session start & characters* below) |
| `/level-up` | the GM announces a level, or at session start | Tool works out what the new level grants, then asks only for the player's choices (HP, ASI/feat, spells, subclass…), then updates the PC file |
| `/scene` | party enters new location or major shift | `gm.py scene enter <loc> --write` → refine On stage goals → narrate establishing exposition (short/medium/long) |
| `/travel` | party moves between locations | `gm.py travel <to>` (route, derived time, encounter roll, scene packet) → narrate |
| `/combat` | initiative starts | `gm.py combat start` → map → turn-by-turn with `atk`/`dmg`/`cond`/`combat next` |
| `/map` | combat start, or a player asks | `gm.py space map --player-view --from <active>` and shows the grid + legend |
| `/overrule` | the table wants to change something (honor-based) | Retcon what happened, or add a temporary/permanent table rule. Applied immediately, shown as a card, `/overrule undo` reverses (see *Overrule* below) |
| `/spoilers` | the table wants to peek behind the screen (honor-based) | Answers questions about secrets, or "what if" alternatives, from state + history. Answered immediately in a banner; never creates canon (see *Spoilers* below) |
| `/end-session` | wrapping up | Writes summary + world tick, `gm.py session archive` (history, lint, git commit) |
| `/new-campaign` | scaffolding | Creates a campaign folder from the templates in 04-file-formats.md (always including `locations/world.md` with the starting area at its origin), sets `.campaign` |

Play runs through the table client (`python tools/table.py`, 06), which shows players
only the GM's narration. Tool calls, tool output, thinking and the injected brief stay
hidden. So **the GM's narration is the only thing players see**, and the
*Behind the screen* rules below govern it.

The main `/gm` skill's instructions ARE the Game Master brain — the sections below are
what goes into it. Every mechanical step goes through `tools/gm.py` (spec: 06). The
skills say *when* to call a command, and the tools do the math and the file writes.

## Session start & characters

### Session-start routine (run by `/gm`)
1. **Roster:** "Who's at the table today?" Free text ("Alex is Kira, Sam's new,
   Jo's out"). Each name is matched to a PC file:
   - **Present, known PC** → continue.
   - **Absent PC** → marked `present: false` for the session. They're run on their
     `autopilot` line (05 #12).
   - **New player / new PC** → the character intake loop (below). A pregen is
     offered as the fast path ("or play Kira or Kael, ready now").
2. **Changes since last time:** one question to the whole table: "Anything change
   with your characters between sessions? Purchases, gear swaps, retirements?" Each
   answer goes through the same intake loop in *edit* mode, touching only what changed.
3. **Pending level-ups** (from `level-pending` in a PC file) → the level-up flow
   (below), one PC at a time.
4. **Recap** from the party's point of view (no `(GM)` lines), then the opening
   scene's narration.

Steps 1–3 are skipped quickly when nothing applies ("Same table as last time, no
changes" → straight to the recap). Each step is a short exchange, not a form.

### Character intake loop (`/character`)
**Input can be at any level of detail**, from "half-orc barbarian, level 3, berserker,
greataxe and javelins" to a pasted full character sheet, or a mix across several
messages.

**The loop:**
1. **Extract.** The GM turns everything said so far into a draft
   (`gm.py pc draft`, 06), field by field. It never invents a value the player didn't
   give.
2. **Derive and check.** `gm.py pc check` fills in everything computable from the SRD
   data and reports three lists:
   - **Missing (required):** must be asked for.
   - **Defaults proposed:** e.g., standard array assigned by class priority, the
     class's starting equipment. The GM shows them as "I'll use X — OK?". A default
     never becomes final silently.
   - **Conflicts:** stated value vs. derived ("you wrote AC 17; chain mail + shield
     comes to 18 — which is right?").
3. **Ask.** The GM asks **only** for what's missing or conflicting, in one compact
   message (grouped, numbered, with options where the SRD gives a short list). The
   player answers in free text, and the loop goes back to step 1.
4. **Confirm.** When nothing required is missing, the GM shows a one-screen
   **character card** (name, race, class/subclass/level, scores, HP, AC, speed,
   attacks, key features, spells, equipment). The player's "looks good" writes the
   file (`gm.py pc write`). Corrections loop back to step 1.

**Required before a PC can play:**

| Field | Notes |
|---|---|
| name | |
| race (+ subrace if the race has them) | |
| class + **subclass** | subclass only once the class reaches its subclass level (2014: cleric/sorcerer/warlock 1, druid/wizard 2, others 3) |
| level | |
| ability scores | missing → offer standard array (auto-assigned by class), point buy, or rolled 4d6-drop-lowest via `gm.py roll` |
| equipment | missing → offer the class + background starting equipment |
| HP method: **max or roll** | asked **once per character**, stored as `hp-method` (house rule). Applied to every level after 1st (level 1 is always max), including levels the character starts above 1st, and to all future level-ups. Never asked again; see *Level-up flow* |
| choices the class/race forces at this level | skill proficiencies, fighting style, expertise, cantrips/spells known or prepared, etc. `pc check` lists exactly which apply |

**Optional (asked once, can be skipped):** background, a one-line look, personality,
**a goal or bond**, and the `autopilot` line (a default is proposed).

**Rules for the loop**
- **Player-stated values win.** A conflict is asked about once. If the player
  insists, the value is kept and recorded in `overrides` (04), so the tools stop
  re-deriving it. It's the player's sheet, on the honor system.
- **Non-SRD content** (a subclass, race or feat from a book) is accepted. The GM
  asks the player to summarize what it does at this level, writes it under
  `## Features & abilities`, and marks it `custom`. The tools don't derive custom
  features; they just carry them.
- **Interrupted intake resumes:** drafts live in `.gm/drafts/<slug>.json` until written.
- **Behind the screen:** intake is player-facing. Backstory goals are woven into the
  world *privately*: the GM may note scenario hooks in GM-only sections, and never says
  so at the table.
- **Backstory places go on the world map.** A hometown, a temple, "the city where it
  happened": each becomes a `## Known, not placed` row with `source: player:<pc>` and
  whatever constraints the player gave (`gm.py world add`). The player's words are the
  constraints. The GM doesn't pin coordinates the player didn't imply.

### Level-up flow (`/level-up`)
**Trigger:** the GM announces a level at a story milestone (default: milestone
leveling; see Open decisions in the README). `gm.py pc level-pending <pc>` marks it,
and the flow runs immediately or at the next session start.

1. **Compute.** `gm.py pc levelup <pc> --plan` lists what level N+1 grants
   automatically (proficiency bonus, hit dice, spell slots, class and subclass
   features, cantrip damage tiers) and **which choices are required**.
   - **HP is not a choice here:** it follows the character's stored `hp-method`.
     With `max`, it's the hit die's max + CON. With `roll`, the tool rolls the hit die
     publicly (+ CON; the roll is final), or the player reports their own roll if they
     say so. The GM doesn't ask "max or roll?" again. The setting changes only when a
     player brings it up in play ("Kira: switch me to rolling HP") → `gm.py pc edit
     <pc> --set hp-method=roll`. That affects future levels only; past levels stay as
     they were unless the table uses `/overrule`.

   Choices that are required:
   - ASI or feat (levels 4/8/12/16/19, plus fighter 6/14 and rogue 10)
   - subclass, if this is the class's subclass level
   - new spells known/prepared, cantrips, expertise, fighting style, invocations,
     etc., per class
2. **Ask** for the choices only, in free text, in one compact message. Missing or
   invalid answers are asked again (same loop as intake).
3. **Card + confirm:** a short "Level 4 Kira" diff card listing what changed.
   "Looks good" → `gm.py pc levelup <pc> --apply`, which updates the PC file and adds
   a Journal line, a session-log delta, and `level-pending` cleared.
4. **Memory stays current:** the PC file is the single source; the brief's party
   line, combat seeding, and `odds` all read it, so nothing else needs updating.

Multiclassing is supported only as `custom` in v1. The GM records it in Features, and
the tools treat the PC as their primary class.

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
go in the `/gm` skill near the top. **The single exception is a `/spoilers`
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
  without a new `/spoilers`.
- Overrule applied cards (*Overrule* below) list only visible consequences. Hidden ones
  are "adjusted behind the screen."
- "Check the record" (05 #13) → answer from what the party knows. If the fact itself is
  secret: "Checked it behind the screen — it stands."
- Rules questions about the PCs' own capabilities are always answered openly.

**Recaps and summaries.** Session recaps, `/end-session` summaries and commit messages
are written from the party's point of view. Session-log lines tagged `(GM)` are left
out (06).

## Overrule and Spoilers are honor-based

**Decided (2026-10-02).** `/overrule` and `/spoilers` are table tools, not gated
features. Whoever is running the session can use them whenever they choose. Not using
them is also just a choice. Like the files, they run on the honor system:
- **No consent step:** no "all players agree?" card, no yes/no, no record of who
  agreed. Typing the command *is* the decision, and how a group decides to use it is
  up to the group.
- **No on/off switch:** a table that doesn't want them simply doesn't type them.
- What remains is what makes them work well: the GM applies or answers accurately,
  keeps everything else behind the screen, logs that it happened, and **never suggests
  either one** (that's GM behavior, not gating).

## Overrule (the players' table authority)

Players can change the game, and that's how the table keeps ownership of its fun.
`/overrule` is the **only** channel for it: dice results, rulings and outcomes are
otherwise final (05 #3).

**Two kinds**
1. **Retcon:** adjust something that happened. "Kira wasn't spotted on that climb";
   "Undo that last round, we misread the map"; "Mara wouldn't know our names, we never
   told her"; "Re-roll that, the die fell off the table."
2. **Table rule:** a rule change for a while, often from a game idea. "Crits on 19–20
   for this boss fight"; "Flanking gives advantage this session"; "No death saves in
   this tutorial fight"; "From now on, drinking a potion is a bonus action."
   Scopes: `scene` · `combat` · `session` · `campaign` · `until <condition>`
   (GM-judged, e.g., "until we leave the dungeon").

**Flow (one step)**
1. Someone types `/overrule <what>` (free text; it can carry the kind and scope
   explicitly, e.g., `/overrule rule crits on 19-20 for this combat`).
2. The GM applies it right away through `gm.py` (06), then shows a short **applied
   card**: kind, exact change, scope, and the *visible* consequences ("Kira gets her 6 HP
   back and isn't prone; the guard never raised the alarm"). Anything that followed
   from it behind the screen is adjusted silently, and the card just says so ("…and
   whatever followed from it behind the screen").
3. The fiction resumes from the corrected state.
4. If the GM misread the request, `/overrule undo` reverses the last overrule exactly
   (via the journal), and the table can rephrase. If the request is genuinely
   ambiguous ("undo that", when "that" could be two turns), the GM asks **which one**:
   a clarifying question, not a permission check.

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
- **Conflicts with hidden facts.** If a declared fact ("there's a back door out of the
  mill") contradicts something behind the screen, **the overrule wins**. The GM makes
  it true, adjusts the hidden side to fit as plausibly as it can (`(GM)`-tagged
  changes), and doesn't say what changed. The card notes only "adjusted behind the
  screen."
- **The GM never proposes, hints at, or invites an overrule**, especially after a bad
  roll. Complaints, groans and "that seems harsh" are not overrules, and not evidence of
  GM error. Only the explicit command counts. The GM may *answer* a rules question
  ("RAW, ties go to…") but doesn't suggest bending it.
- Overrules are logged publicly (`[overrule]` lines), so a table that overrules every
  bad roll can see it doing so.

## Spoilers (players opt in to peek behind the screen)

`/spoilers` is the **only** exception to *Behind the screen*: the GM reveals things only
when someone explicitly uses the command. It covers two kinds of question:

1. **Secrets:** "Who actually took Harl?" · "Was Mara lying to us?" · "What was
   Veskar doing the night we stayed at the inn?" · "Did we miss anything at the mill?"
2. **What-ifs:** "What would've happened if we'd gone to the mill the first night?" ·
   "What if Kira had attacked Veskar on the landing instead of talking?" · "What if
   we'd never bought Tobin that drink?"

**Flow (one step)**
1. Someone types `/spoilers <question>`. Optional depth: `hint` (a nudge in the right
   direction) · `answer` (default: just what the question asks) · `full` (everything
   connected to it, up to the whole `## The truth`).
2. The GM answers right away, between spoiler banners. The banner's first line is a
   spoiler-free **header** giving the level and depth, so anyone glancing at the shared
   screen can look away before the content:
   - **Level:** `none` (a what-if answerable entirely from what the party already
     knows) · `minor` (a resolved thread or background detail) · `major` (touches an
     unresolved thread, the kind of thing the campaign is built around).
   - The answer keeps to the question at the requested depth. If related secrets were
     left out, the last line says so ("There's more connected to this — ask with `full`").
3. Play resumes under the normal *Behind the screen* rules.

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
- **Undecided things stay undecided. Decided (2026-10-02): what-ifs and guesses are
  never facts.** If the answer was never authored (what's in the locked strongbox, who
  Harl's sister is), the GM says so: *"Not decided yet. Here's what I'd lean toward,
  but it isn't canon."* The guess is not written into any world file, and the GM
  isn't bound by it later, so the world stays open. Only an explicit `/overrule` can
  make it canon.

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
- **First fight in a place writes its `## Layout`** (one block per sub-area). Every later
  fight there starts from it, so the tavern is the same shape in session 1 and session 9.

**Which frame (01 → World geometry).** A Combat block works in one frame, named on its
`Map:` line. Normally that's the site the fight is in (all its rooms and floors share
it). When a fight spans places (the archer on the inn roof, the thugs in the square), it
switches to the shared parent area's frame. `combat start --frame thornbury` (or
`combat reframe` mid-fight) adds each site's `at` offset to positions and terrain,
then pulls in the area's Places rows as terrain. Sites and areas are both in feet, so
nothing rescales and the 5-ft grid still lines up. The reverse works the same way when
the fight collapses back inside one building.

**Outside combat** the GM doesn't track positions at all, only `location: site/area`.
For "how far / which way" it reads the generated Nearby block or asks `gm.py where`
(06). Those answers come from coordinates and routes, so they never need mental math.
Routes say how to get somewhere and how long it takes. Straight-line distance is for
sight, sound and range.

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

## The open world (filling in the map)

`locations/world.md` always exists (04 → The world file). It places what's known and
leaves the rest open. Places get filled in from three directions, all recorded with a
`source`:

- **Generation (`generated`).** The GM invents a place *when play needs it*. Triggers:
  the party heads down a frontier lead, an NPC needs a hometown, or a job needs a
  destination. Generate the one place and at most one hop beyond it, not a continent.
  Use `gm.py world add <name> --near <id> --within <dist> [--dir E] [--on <feature>]`,
  then `world place` once it needs coordinates. The tool picks or checks a spot that
  satisfies every constraint and doesn't overlap a placed footprint. The GM supplies
  the fiction (what the place is, and why the road bends there). A file is created only
  when the party will actually go there (`stub location`). Otherwise the row is enough.
- **Player choice (`player:<pc>`).** Backstory places come in at intake (Character
  intake loop). At the table, players may also propose things ("there'd be a ferry
  where the road meets the river, right?"). The GM accepts a proposal unless it
  contradicts placed canon or a live secret. In those cases the GM says "not that I
  know of" in fiction, without explaining. An accepted proposal is written the moment
  it's agreed.
- **Outside resources (`import:<resource>`).** A published module's town, or a map the
  group likes: `gm.py world import <file> --anchor <their-place>=<our-place> --scale
  <mi per unit>` (or two anchors). Imported rows land in `## Known, not placed` and
  are placed only after a conflict check against existing canon. The GM resolves
  clashes by adjusting the import, never the canon.

**Rules that keep it consistent:**
- **Placed is permanent.** Once a place has coordinates, only fiction (a flood moves the
  ford) or `/overrule` moves it.
- **Constraints are promises.** Everything said about an unplaced place ("three days
  east") is recorded as a constraint when it's said, so the eventual placement can't
  contradict it.
- **Unknown ≠ empty.** The GM never says "there's nothing out there", only what the
  characters know or have heard. Rumors are `## Known, not placed` rows, and a rumor
  can be wrong: note `rumor; may be false` in `notes`.
- **The end-of-session world tick** may add frontier leads that play implied, but it
  never places them. Placement waits until play needs it.

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
