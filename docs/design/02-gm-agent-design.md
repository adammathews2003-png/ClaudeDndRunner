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
| `/new-campaign` | scaffolding | Creates a campaign folder from the templates in 04-file-formats.md (always including `locations/world.md` with the starting area at its origin), sets `campaigns/.active` |

Play runs through the table client (`python engine/table.py`, 06), which shows players
only the GM's narration. Tool calls, tool output, thinking and the injected brief stay
hidden. So **the GM's narration is the only thing players see**, and the
*Behind the screen* rules below govern it.

The main `/gm` skill's instructions ARE the Game Master brain — the sections below are
what goes into it. Every mechanical step goes through `engine/gm.py` (spec: 06). The
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
**Trigger** depends on the campaign's `advancement` (04 → Campaign file; default
`milestone`):
- **milestone:** the GM announces a level at a story milestone; `gm.py pc level-pending
  <pc>` marks it.
- **xp:** levels come from XP thresholds (PHB): when a PC's `xp` crosses the next
  threshold the tool sets `level-pending` itself and says so in its output.

**XP is tracked in both modes** unless the campaign sets `xp-tracking: off`. The GM
awards it with `gm.py xp award` (combat XP is offered by `combat end`; quest, discovery
and roleplay XP are the GM's call, always with a reason). In a milestone campaign the
total is kept for other uses (a campaign threshold that opens a door, a sequel, a
switch to xp leveling later) and a crossed PHB threshold is only noted, never
levelled.

Either way the flow runs immediately or at the next session start. Narration may say
"you feel ready to grow" but never quotes XP numbers unless a player asks; players can
always ask for their XP and the next threshold.

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

## Reading a declaration ("I do X")

**Decided (2026-10-07).** A player's "I do X" states **intent and approach**, not an
outcome. "I pick the lock, grab the ledger and slip out" says what they want and how
they mean to get it. The world still gets its say.

- **Resolve until the world gets a vote, then stop.** Narrate the declared chain up to
  the first point where something other than the player decides. That is an uncertain
  step (a check), an NPC who would react, or a reveal that could change the player's
  mind (the ledger isn't on the desk; someone is asleep in the chair). Hand the scene
  back there. Never narrate the character through to the outcome the player declared.
- **Fill in the implied steps, and charge what they cost.** Crossing the room, opening
  the drawer and finding the right page are trivial, so they just happen (Player plans →
  *Turning a plan into checks*). They still cost something: **time** (`time +…` in the
  same `do`; NPC schedules keep moving, and a split party's slice counts it),
  **position**, **noise or exposure**, and **resources** (a slot, the only rope).
  Mention the cost in passing in the narration.
- **Tense tempo and combat cut the chain to one turn.** A declared sequence becomes
  whatever fits in movement + action (+ bonus action): "You reach the desk *[that's your
  move]* and the lock is your action. The ledger waits for your next turn." The rest is
  kept as stated intent and is not resolved yet.
- **Pause before committing only when a hidden step changes the stakes.** Ask **once,
  before rolling**, only when both of these are true:
  - an implied step carries a risk the player probably didn't count (danger, noise, a
    running clock, leaving someone alone, provoking an attack);
  - the character would see that risk.
  > *"Searching the whole archive is about an hour, and the bell rang a while ago.
  > Still go?"*

  A cost that is only time, with nothing pressing, is never asked about. It just passes
  and gets mentioned (the GM names the elapsed time when the scene ends, so players can
  still object). If the character wouldn't see the risk, don't warn them; it lands as a
  blind consequence.
- **Vague intent.** For "I deal with the guard", ask "How?" only when the plausible
  approaches would use different checks or carry different risks. If the character and
  the moment make one reading obvious, take it. The GM never chooses a PC's approach
  when the choice matters (Failure & tone guardrails).
- **One clarifying beat at most**, whether it's a pause or a "How?". Then resolve.

**How long things take** (outside combat; in combat, the action economy decides). These
defaults keep the "Still go?" numbers and the clock consistent. Adjust for the place (a
cluttered study takes longer) and for clever methods (a plan that narrows the search
cuts the time). A retry after a failure costs the same time again.

| activity | time |
|---|---|
| open a door or drawer, grab something in reach, read a note | moments (no `time`) |
| pick a lock, disarm a simple trap, search one spot (a desk, a body) | 1 minute |
| search a room thoroughly, skim a ledger or book for one thing | 10 minutes |
| a conversation that's a scene of its own | about 10 minutes |
| cast a spell as a ritual | the casting time + 10 minutes |
| buy ordinary gear in a town | 30 minutes |
| search a building or an archive section, ask around a village | 1 hour |
| ask around a town for rumors, research one question in a library | 1–4 hours |
| short rest / long rest | 1 hour / 8 hours (`rest`) |
| deep research, crafting, recovery, a week of anything | days: *Not now* (Kinds of "no") |
| getting somewhere | `travel` / movement computes it |

## Player plans: answer with a roll, not a no

Creativity is rewarded. When a player proposes a plan, however odd, the GM's default
answer is **"roll for it"**, not "no". The dice and the fiction decide how it goes.

**When "no" is allowed.** Only when the plan would **break the core scenario**: it
would skip or expose the scenario's truth without doing the work, bypass a campaign
mechanic (a time loop can't be "ended by convincing the king"), or delete the finale.
Even then:
- First look for an **in-fiction reason** the attempt can't land. The door really is
  warded, or the king really can't. The character can still try, and the try still has
  consequences.
- If no fiction fits, give a short out-of-character no: "That one's off the table for
  this story." Don't explain why; the reason is behind the screen. The players'
  `/overrule` still applies, and the GM doesn't mention it.

**Kinds of "no" (decided 2026-10-07).** Most answers that sound like "no" are really
something else, and each kind has its own response. Breaking the core scenario (above)
is the only true refusal. Every other kind ends with **a way forward**: a route, the
nearest equivalent, the rule stated openly, or the time it would take.

- **Not here.** The target isn't in this scene ("I ask Garrick", and Garrick is at the
  mill). Say what the character perceives. If they'd know where the target is, offer
  the route and its cost: "He's at the mill, twenty minutes' walk. Head there?" A yes
  becomes a scene move or `travel`. The brief's *On stage* line says who is here.
- **Not here yet.** It plausibly exists ("I find a blacksmith" in a market town). The
  world is open (The open world): if the place would have it, it exists. **First check
  it isn't already named** (the scene's Description or its Nearby list). If it is, use
  that one. If not: when the party is going there now, `stub location "Brann's Smithy"
  --in thornbury` creates a file the party can enter. When it's only being mentioned,
  `stub place` adds a world row and nothing else. People there are stubbed with
  `--location <that location's slug>`. A row made by `stub place` isn't a location, so
  use its area. Without `--location`, a stubbed NPC lands in the party's current scene.
  Then answer as for *Not here*. Unknown is never empty.
- **Not in the setting.** A pistol, a telegraph, germ theory. Answer in fiction with the
  nearest thing the world does have. Judge it from the campaign's `setting:` line (04 →
  Campaign file) and its `weirdness`: "No one's heard of such a thing. The closest is
  alchemist's fire, and the apothecary might stock it." When it's clearly a table joke,
  treat it as table talk: enjoy it and resolve nothing.
- **Not in the rules.** A 40 ft standing jump, or Fireball from a level-1 bard. This is
  different from a long shot: no roll exists for it (jump distance comes from Strength,
  not a check, and a spell the character doesn't have can't be cast). State the rule
  openly, since rules questions about PCs are always answered, and offer the nearest
  version they *can* attempt.
- **Lacking an ability or resource.** No spell slot, no rope. Handle it the same way:
  state the fact and offer the nearest attempt.
- **Long shot.** It gets a DC, not a no: Very hard 25, Nearly impossible 30. A natural
  20 on an ability check isn't an automatic success, so a 30 can stay out of reach for
  a given character. If it's out of reach, say so when the attempt is foreseen (below).
- **Hard ask of an NPC.** It starts from a long-shot DC the pitch can bring down (Table
  mechanics → Social stakes: leverage, flair and the stuck-table stages).
- **Not something the character knows.** The player acts on table knowledge, such as
  ambushing a secret meeting nobody in the fiction has mentioned. Allow it: play is
  honor-based, and the GM doesn't challenge it or ask where the idea came from. But the
  world is not rearranged to reward or punish the guess. What's behind the screen stays
  as written, so a right guess can land and a wrong one finds nothing. Never confirm or
  deny anything out of character.
- **Not now.** A time skip ("I spend a week in the archives"). Treat it as downtime or a
  montage: advance the clock, roll 1–2 checks for the stretch (`downtime` setting,
  Phase 15), and let the world move in the meantime. A split party follows *big skips
  wait* (Splitting the party). **Length is never a reason to refuse.** Scenario clocks
  firing during the skip are the world moving, not the story breaking. If the character
  would feel the urgency (a missing man, a cart due at dawn), that is the one pause, said
  in fiction ("A week? Whatever happened to Harl won't wait a week."). Then honor the
  choice and run the clock. Never talk about "the story" having no time for it.
- **Controlling another PC.** It isn't the GM's call. That player decides.

**Turning a plan into checks.**
1. **Split it into its uncertain steps** and roll only those. Use 1–3 checks; more turns
   one plan into a slog. Steps that are trivial for this character just happen.
2. **Reward the cleverness itself.** A good plan earns at least one of: advantage, a
   lower DC band, an auto-succeeded step, or a free Help from the setup. Prep done in
   earlier scenes counts (the bribed guard, the oiled hinge).
3. **Chain the results.** A strong success can lower the next DC or grant advantage; a
   failure fails forward (Failure & tone guardrails) and changes the next step instead
   of ending the plan.
4. Use a **group check** when the whole party is in on one step (the sneak, the climb).

**Foreseen or blind.** Before the roll, the GM decides whether *this character* would
recognize what's at stake:
- **Foreseen** if they're proficient in the skill or tool, their background, class or
  history fits ("you were a sailor"), the party learned it in play (journal, NPC
  history), or their passive score in a relevant knowledge skill (10 + modifier) meets
  the DC. The GM names the check(s), the DC band, and **the outcomes the character can
  see coming**:
  > *Athletics, Hard. Make it and you're on the balcony before the guard turns. Miss
  > and you're hanging off the gutter in plain view. Miss badly (by 5+) and the gutter
  > comes with you.*
  The listed outcomes are what the character would expect. They never reveal hidden
  things (Behind the screen), and the GM may still add consequences the character
  couldn't have known about.
- **Blind** if it's outside anything the character knows (an unfamiliar ritual, a
  stranger's psychology, alien machinery). The GM names **only the check**: "Arcana.
  You're going in blind." No DC, no outcomes. Narrate the result when it lands.
- A multi-step plan can mix both: the climb is foreseen, and what's on the balcony is
  blind.

**Outcome tiers** (for describing foreseen outcomes and narrating results): success ·
**beat by 5+** (a bonus: faster, quieter, an extra detail) · fail (a complication or a
cost) · **fail by 5+** (the foreseen worst case). `check` prints the margin (06), so the
tier comes from the tool, not from the model reading the dice.

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
  something. Only those who succeed get a narrated notice. The DC or stakes of a
  **blind** check (Player plans above).
- That an NPC's moment was Wacky Juice, outside `/spoilers`.
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

## Wacky Juice (random NPC chaos)

Most of the time NPCs act logically, from the three inputs above. **Wacky Juice** lets
an on-stage NPC, now and then, do something unexpected that's funny because it's
unexpected. The ratbag stable boy tries to sell Kael's own boots back to him. The
stern abbess starts an arm-wrestling contest. The guard captain suddenly confesses a
lifelong fear of geese.

**Configuration** (campaign frontmatter, 04 → Campaign file; the players can change it
any time by asking, through `gm.py juice`, 06):
- `wacky-juice: on | off`. Default `on`.
- `wacky-juice-value: 5`. The percent chance, per eligible player prompt, that the
  juice fires. Rough feel: `2` is a rare treat, `5` is about 2–4 times a session, `10`
  is frequent, `25` is chaos. Tune it in play testing.
- `wacky-juice-cooldown: 3`. Player prompts after a firing during which it can't fire
  again, so moments don't come in clumps.

This is separate from the `jokes` dial (07), which governs *authored* comedy when the
campaign is generated. Wacky Juice is unscripted and rolled at the table, and it works
in any tone. A grim campaign gets dry, absurd juice.

**The roll is real, not the model's choice.** The `UserPromptSubmit` hook rolls it
(06 → brief): if the juice is on, the cooldown has passed, and at least one NPC who can
act is on stage, it rolls d100 ≤ value and picks one of those NPCs at random. On a hit,
the brief gets a line `Juice: Tobin`. That turn, Tobin does the thing. With no line,
the GM does not add juice on its own initiative: no hidden juice.

**What a juice moment is:**
- **Something this NPC could physically do, in this scene, in this world.** It's
  random in *what*, not in *physics*. In hindsight it should have a reading: the NPC's
  personality pushed to 11, a hidden hobby, a misunderstanding, a sudden bad idea.
- **Short-lived and self-contained.** It colors a scene. It can create a small
  complication or an opening (the arm-wrestling contest is also a chance to talk to
  the abbess), in the fail-forward spirit.
- **Canon once it happens.** The NPC owns it afterwards, and a notable one goes in
  their `## History with the party`.
- **Mechanics go through the tools** like anything else (an NPC who throws a pie makes
  an `atk`). In combat, a juice moment replaces that NPC's action on its turn.

**What it may never do** (the same line as *Player plans* above):
- Break the core scenario: reveal secrets or the truth, resolve or skip a beat, kill or
  remove an NPC a beat depends on, or move such an NPC out of reach.
- Control a PC, or do serious harm to a PC out of nowhere. Embarrassment and
  inconvenience are fine.
- Contradict established facts. It adds a weird fact, it doesn't overwrite one.

If the picked NPC can't act (asleep, gagged, unconscious), the GM may hand it to another
on-stage NPC who can. If nothing within these limits would be funny, the GM waives it
(`juice waive` in that turn's `do`). The waive is logged, so play testing shows how
often the rate is wasted.

**Behind the screen.** Narration never says "Wacky Juice", "the juice fired", or shows
the roll. The moment just happens. The feature itself isn't secret (the players set its
rate), so "was that juice?" may be confirmed with `/spoilers`; it's logged as a `(GM)`
line (04).

## Combat mode

Combat swaps the freeform loop for structure, tracked in a `## Combat` block inside
`state/current.md` (format in 04): initiative order, position, HP / AC / conditions per
combatant, round count, terrain, and a moves log. Monster stat blocks come from the local
SRD data (`gm.py srd monster <name>`, 06), not model memory. A named NPC's block is
written into their file the first time it's used (`--write`), so later edits stick.
Lifecycle: `combat start` → `atk`/`dmg`/`cond`/`space move` per turn → `combat next` →
`combat end`. Keep POC combat simple (few combatants, basic actions) before layering in
complexity.

## Splitting the party

**Decided (2026-10-06).** When the PCs go separate ways, each **group** gets its own
scene (location, light, tempo, On stage, combat) and its own game clock, and the GM
**cuts** between them so every group keeps moving and nobody waits long. The waiting
players are still at the same console, watching.

**The unit is the exchange:** one round of input from the active group's players plus
the GM's reply. A group's turn at the table is a **slice**.
- **Calm or tense slice:** at most `split-exchanges` (default 3). It's a cap, not a
  quota. Cut early on a hook: a door opening, a roll about to land, an NPC's "you
  shouldn't be here". End every slice on an affordance the players will come back to.
- **Combat slice, other groups can't sense the fight:** `split-combat-rounds` (default
  6 rounds = 1 minute) before cutting away.
- **Combat slice, another group can sense it** (sight, hearing, smell, any sense in
  range): cut **every round**. The fight is part of their scene now: they hear the
  steel, see the torchlight, and may come running.
- **Can sense** (`split` works it out, the GM may override): the groups share a site,
  or they're within `split-sense-ft` (default 300 ft, combat carries) of each other, or
  one can see the other within its sight range in the current light. Special senses in
  a PC's `senses:` (blindsight, a keen nose) extend it when their range reaches.
  Noticing is narrated to the sensing group at their next slice, without a check
  unless the fight is quiet (an assassination, a whispered struggle: passive
  Perception vs. the attacker's Stealth).

**Keep game time level.** This rule outranks alternation:
- Each group has its own clock. **The group furthest behind in game time goes next.**
- A slice may not run a group more than about one slice of the other's time ahead.
  While a group is in combat, the calm group's slice covers **about one minute** of
  game time, the same as six rounds.
- **Long tasks span slices.** "We search the archive" (30 min) starts in one slice and
  finishes when that group's clock reaches it. Until then their slices are progress,
  interruptions, and what they find along the way.
- **Big skips** (a long rest, travel) by one group wait until the others catch up, or
  the GM summarises the others' matching span in a few lines ("while they slept, you
  watched the docks: three carts, one of them twice").
- **World clocks and NPC schedules** fire against the **earliest** group clock, so
  nothing happens "ahead" of a group that hasn't lived through it yet.
- **Combat counts as time.** While split, a fight's rounds (6 s each, rounded up to
  the minute) go on that group's clock when the GM cuts away or the fight ends.
- If every other group is already far ahead, the fighting (or talking) group **plays
  on** past its cap until it catches up; the brief says so.

**What the waiting group knows.** Players see everything; characters don't. At the
first cut, one line of table voice ("Kira and Kael don't know any of this yet").
Afterwards the GM simply doesn't let characters act on what they couldn't know.
Contact between groups needs a means in the fiction: shouting distance, a *Sending*,
a signal arranged beforehand. Messages travel at fiction speed.

**Reuniting.** When groups reach the same place, the GM merges them (`split join`):
clocks level to the latest one (the earlier group's gap is summarised), scenes merge,
and a quick in-character recap covers anything the others need to hear.

**Ending a session while split.** The split carries over; don't force a reunion to
stop. `/end-session` writes a summary paragraph per group (each from that group's
point of view), a closing beat for each, and the archive records every group's place
and clock (`## Split at session end`). The next session recaps each thread and opens
with the group furthest behind in game time.

**Out-of-turn table talk** from a waiting player is fine. Character actions from a
waiting group are held for their next slice ("Hold that thought, Kael: we'll be with
you shortly").

## Table mechanics: what the GM must not forget (Phases 13–15)

**Planned (2026-10-06)**, from a gap analysis against the 5e play pillars (combat,
exploration, social), downtime and the SRD's environment rules. The test for each
item: how often it comes up, and how likely an AI GM is to get the number wrong or
lose the state without a tool. The answer is the same as everywhere else: **the tool
keeps the state and supplies the number; the GM narrates.** Every item that a table
might want to play loosely has a setting (04 → Campaign file → Table settings), and
`off` always means "the GM handles it in the fiction, as before".

### Phase 13: state the table forgets

**Concentration.** A caster has at most one concentration spell, recorded on them
(`conc Kael bless --on Kael,Kira 1m`). Targets get the effect as a condition with
the same duration. Damage to a concentrating creature prints the CON save it owes
(DC 10 or half the damage, whichever is higher); a failed save, a second
concentration spell, dropping to 0 HP or an incapacitating condition ends it, and
ending it strips the effect from every target. The GM never has to remember who is
still blessed.

**Dying.** A PC at 0 HP is **dying**, and the PC file holds the count (`death-saves:
{ok: 1, fail: 2}`) until they're healed, stable or dead. On the dying PC's turn the
brief asks for a death save (the player rolls it, as with every d20): 10+ is a
success, a 1 is two failures, a 20 is 1 HP and back up. Damage while down is a
failure (two on a crit); damage of at least their HP maximum is instant death.
Three successes or a Medicine DC 10 check (or a healer's kit use) make them stable;
a stable PC wakes with 1 HP after 1d4 hours. `death-save-rolls: secret` has the GM
roll them hidden and narrate only how the PC looks ("his breathing is getting
shallower"); the table-rule key `death-saves` (`on | off | dc N`) still governs
whether the rules apply at all.

**Light.** `light:` on the scene is the **ambient** light. Lit sources are carried
by a creature (`light Kael torch`) and burn down on the clock: torch 1 h (bright 20
ft, dim 20 more), lantern 6 h per flask of oil (30/30), candle 1 h (5/5), *light*
1 h (20/20), *daylight* 1 h (60/60). The brief's Sight line uses the best light
any member of the active group carries, so "do you have a light?" has an answer on
the page. A torch going out is a beat: the clock output says so, and the GM
narrates it. `track-light: off` keeps sources lit until put out, with nothing
counted down or used up.

**Supplies.** Ammunition, rations, water and light fuel are inventory lines with
counts (`quiver (20 arrows)`, `rations (5 days)`, `waterskin (full)`), and the tools
spend them:
- `supplies: strict`: every ranged `atk` spends one piece of ammunition; after the
  fight `combat end` offers back half of what was spent (if the party searches).
  Eating and drinking are a daily need: `rest long` spends one ration and one day of
  water per PC, and the clock flags anyone who misses a day.
- `supplies: loose` (default): ammunition is reckoned once at `combat end` (the GM
  estimates), and food and water count only away from towns (travel of a day or
  more, wilderness rests).
- `supplies: off`: nothing is counted; running out happens only when the story wants.
Missing food: a PC can go 3 + CON modifier days (at least 1) without food; each day
after that is one level of exhaustion. Missing water: less than half the day's need
is a DC 15 CON save or one level of exhaustion (automatic with none at all).

**Exhaustion.** Levels 0–6 on the creature, shown on the party line and applied by
the resolver (`exhaustion: 2014`: 1 disadvantage on ability checks · 2 speed halved ·
3 disadvantage on attacks and saves · 4 HP maximum halved · 5 speed 0 · 6 death;
`exhaustion: 2024`: −2 per level on every d20 test and −5 ft speed per level, death
at 6). A long rest with food and water removes one level. Sources: missed food and
water, forced marches and hazards (Phase 14), chase Dashes (Phase 14), spells and
monsters (the GM, by mutation).

**Content boundaries.** Session zero records what the table won't have:
`lines:` (never appears, not even off-screen) and `veils:` (may happen, but off
screen: fade out, summarise the result). They ride in the full brief, every time,
and rank with Behind the screen: nothing in the campaign, Wacky Juice or a player's
prompt overrides them. A player's prompt that drifts toward a line is steered away
without a lecture. `/campaign new` asks for them; `/gm` asks once if they're unset.
A player can type `!x` (the X-card) at any time: the hook tells the GM to rewind the
last thing described and steer away, no explanation asked, and logs it without a
reason.

### Phase 14: exploration, social pressure, hazards

**Travel as play.** With `travel-detail: activities`, each PC on a journey does one
thing: **navigate** (Survival against the terrain's DC to stay on course), **forage**
(Survival DC 10 / 15 / 20 for abundant / limited / scarce land; 1d6 + WIS modifier
lb of food and as much water), **track**, **map**, or **keep watch**. Only PCs keeping
watch (or doing nothing else) add their passive Perception against ambushes and
encounters; a fast pace costs −5 passive Perception, and only a slow pace allows
stealth. The **marching order** (front / middle / back) decides who meets trouble
first. A day of more than 8 hours on the march is a **forced march**: each extra hour
is a CON save (DC 10 + 1 per extra hour) or one level of exhaustion.
**Getting lost** (`getting-lost: on`) applies only off roads and paths: the navigator's
Survival check against the terrain DC (grassland 5; arctic, desert, hills 10; forest,
jungle, swamp, mountains 15), and a miss sends the party 1d6 hours on a wrong
bearing before anyone notices. The tool supplies the DC and the bearing; the GM makes
it a story ("the river should be on your left").
`travel-detail: summary` keeps today's one-packet journey.

**Social stakes.** **Decided (2026-10-07).** The same promise as Player plans
(above): the answer is a roll, not a no. With `social-dcs: dmg`, a persuasion,
deception or intimidation check against an NPC **starts** from a DC set by their
attitude and the size of the ask (the DMG's conversation table, mapped onto the five
attitudes, with the DMG's "won't" turned into long shots):

| attitude | stand aside / no harm | help at no cost | minor risk or cost | major risk |
|---|---|---|---|---|
| ally | 0 | 0 | 0 | 10 |
| friendly | 0 | 0 | 10 | 20 |
| neutral | 0 | 10 | 20 | 25 |
| wary | 5 | 15 | 25 | 30 |
| hostile | 10 | 20 | 25 | 30 |

That starting DC is a ceiling the players can bring down, never a wall. The only true
"no" is the one Player plans already allows: an ask that would break the core
scenario. Even then the GM turns the attempt toward another route to the same goal
(another NPC, a document, a better moment) rather than ending it.

Two things the GM scores **before** the roll, separately:
- **Leverage (−5 to +5):** does the pitch give this NPC a real reason? Coin, a threat
  they believe, a shared enemy, something they want, a promise they trust. A pitch
  that works against their interests is a positive number (it raises the DC).
- **Flair (0–3):** is it surprising, funny, true to the character, or built on
  something the table set up earlier? **It doesn't have to be logical.** The fiction
  supplies the reason: the NPC is thrown, amused, curious, or too baffled to say no.
  The rubric keeps it honest:
  - 0: a plain ask, or a pitch already tried on this NPC;
  - 1: a fresh angle, or a nice character touch;
  - 2: specific to this NPC or to details established in play, and in character;
  - 3: all of 2, and it surprised the table (the goat that is surely the toll-keeper's
    reincarnated grandfather).

  With `creativity: light` (default) flair takes 2 / 5 / 8 off the DC and a 3 also
  gives advantage; with `generous` (comedy campaigns) it takes 5 / 8 / 10 off and
  gives advantage from 2; with `off` flair is ignored.
- **NPC tastes.** An NPC may be `moved-by:` audacity, honesty, flattery, humour,
  piety, coin, or `nothing` (all business: every flair pitch counts one lower). A
  pitch that plays to it counts one flair
  higher (at most 3); one that grates (flattery on the honest magistrate, a joke to
  someone grieving) counts one lower. Creativity still pays, but it's aimed at a
  person, not at a number.

**Flair is behind the screen.** Players feel it in the DC band (when foreseen), the
result and the NPC's reaction, never as a score, so the table doesn't start pitching
for points. Each pitch earns flair once per NPC: the same trick twice scores 0. The
score and a reason go into a `(GM)` log line before the dice land, so the result
can't reshape it.

**When the table hits a wall.** The tool counts failed attempts per NPC per **goal**
(`--goal "get the ledger"`), so the GM can't lose track of a scene going in circles.
Asking again never wins by itself; failing teaches the way through:
- **After 1 failure:** the NPC shows a feeling (a glance at the door, "not here").
- **After 2:** the NPC says, in the fiction, what it would take ("bring me proof my
  brother's alive and we'll talk").
- **After `social-wall` failures (default 3):** an attempt with a **different
  approach** (another skill, a new argument, new leverage, another PC) starts one
  band lower. If the scene still stalls, the GM offers a route around the NPC (someone
  who owes them, a document, the right moment) instead of a fourth try at the same
  door.

Success clears the goal's count. `social-wall: off` drops the counting.

**The table chooses it, and can switch it off.** Some tables will find the wall
generous; some will find it cheap. So it's a campaign-creation question
(`/campaign-new` asks it alongside advancement, in a line: on by default), and the
first session's opening mentions it once, in plain words and without the machinery:
"If a conversation with someone keeps going nowhere, the game can make it a
little easier over repeated tries. If that ever feels too cheap, just say so and
I'll turn it off."
Players can switch it off (or back on) at any time by asking, the same way as Wacky
Juice; the GM runs `social wall off` and says it's done. The stages, the count and the
band are explained only if a player asks how it works (rules questions get honest
answers, 02 → Behind the screen), and never announced as they happen: the NPC simply
softens in the fiction.

**Results read as "yes, and".** The margin `check` already prints gives the tier:
beat by 5+ is **yes, and** (more than they asked: a favour, a name, a door left
open); success is **yes**; a miss by under 5 is **yes, but** on a flair 2+ pitch (they
get it at a cost or only part of it) and otherwise **no, but** (with something learned
toward the wall stages above); a miss by 5+ is **no, and** (attitude drops a step).
`social-dcs: gm` keeps picking DCs by judgment, but flair, tastes, the wall and the
tiers still apply.

**Morale.** Most creatures don't fight to the death. With `morale: on`, `combat next`
flags a morale check (WIS save DC 10) for a foe side or group the first time one of
these happens: a creature drops below half its HP, its leader falls, or half the side
is down. On a failure they flee (Dash and Disengage) or surrender if cornered.
Mindless creatures (constructs, oozes, most undead) and NPCs marked `morale: fearless`
never check. Foes who flee or surrender count as defeated for XP. A captured foe
joins On stage as a prisoner.

**Chases.** With `chases: dmg`, a chase is a block like combat: each participant's
position along the chase, speed, and **Dashes**: 3 + CON modifier free ones, each
more is a DC 10 CON save or a level of exhaustion. At the end of each turn the GM
rolls on the environment's complication table (urban or wilderness) for the next
participant. The quarry escapes when it breaks line of sight and wins Stealth against
the pursuers' best passive Perception, or when the pursuers give up; it's caught when
the gap closes, which becomes combat or a grapple. `chases: narrative` plays chases as
a contest or two, as today.

**Traps and hazards.** A trap is a `TRAP` line under a location's `## Hidden`: how
it's noticed (the passive Perception DC, as now), what disarms it, what triggers it,
and what it does. The tool keeps its state (armed / triggered / disarmed) and
resolves the effect, so the GM never invents a trap's damage. The SRD's environment
rules become commands with exact numbers:
- **falling:** 1d6 bludgeoning per 10 ft, at most 20d6, and the creature lands prone;
- **suffocating and drowning:** breath held for 1 + CON modifier minutes (at least 30
  s), then CON modifier rounds (at least 1), then 0 HP and dying;
- **extreme cold and heat:** a CON save each hour (cold DC 10; heat DC 5 + 1 per hour)
  or a level of exhaustion, with the gear and resistances that exempt it;
- **underwater combat:** melee at disadvantage except daggers, javelins, shortswords,
  spears and tridents; ranged attacks miss beyond normal range and are at disadvantage
  within it (crossbows, nets and thrown darts, javelins, spears and tridents aside);
  creatures underwater resist fire.

**Hiding as a state.** A hidden creature stays hidden at a known Stealth total (`hide
Kira 17`) until it attacks, makes noise, steps into plain view, or someone beats the
total with an active Perception check. Every creature that arrives or looks later is
compared against the **stored** total with its passive Perception, so the GM never
re-rolls stealth or forgets who saw what. A group moving quietly succeeds if at least
half of them succeed (the group check rule).

### Phase 15: optional subsystems

Cheap toggles and rarer situations. Each is off or minimal unless the campaign turns
it on.
- **Inspiration** (`inspiration: advantage | reroll | off`): the GM awards it for play
  that fits a character; one at a time per PC. The player spends it for advantage on
  one d20 (`advantage`, 2014) or a reroll (`reroll`, 2024).
- **Readied actions:** the trigger and the action are stored on the combatant, and
  `combat next` reminds the GM before each turn whose action could meet a trigger. A
  readied spell holds concentration until released.
- **Magic items:** attunement (3 items, a short rest to attune), charges with their
  recharge (rolled at dawn by the clock, with the "destroyed on a 1" roll where the
  item has one), and identification over a short rest. An item's numbers (`+1 AC`,
  `+1 saves`) feed the PC's derived stats while it's equipped (and attuned, if it
  needs to be).
- **Downtime** (`downtime: off | light | full`): days between adventures spent on an
  activity with progress tracked (crafting at 5 gp of value per day, training 250
  days at 1 gp a day, research, recuperating, working a profession), a lifestyle cost
  per day, and the clock moved by the days spent (with the world firing as usual).
  `full` adds campaign-supplied activity tables (carousing, crime, pit fights) with
  their complications.
- **Allied creatures:** familiars, animal companions, summons, mounts and hirelings
  are combatants on the party's side with a controller. Each acts on the turn the rules
  give it (its own initiative, or the controller's turn) and `combat next` names the
  controlling player. Hirelings are NPCs with a wage and a loyalty that feeds morale.
- **Weather** (`weather: off | on`): rolled each dawn per the region's climate
  (temperature, wind, precipitation). Heavy rain or snow lightly obscures sight;
  strong wind gives disadvantage on ranged attacks and puts out open flames; extreme
  temperatures are the Phase 14 hazard. The brief's header shows it.
- **Encumbrance** (`encumbrance: off | basic | variant`): weights from the SRD
  equipment data. `basic`: over STR × 15 lb, speed drops to 5 ft. `variant`: over
  STR × 5 lb is −10 ft speed; over STR × 10 lb is −20 ft and disadvantage on STR, DEX
  and CON checks, attacks and saves. Fifty coins weigh a pound.
- **Faction renown** (`renown: off | party | per-pc`): standing with each faction,
  raised and lowered with reasons. A faction's NPCs start a step warmer at renown 3+
  and a step colder below 0, which feeds the Phase 14 social DCs.
- **Rare situations:** mounted combat (a controlled mount moves on the rider's
  initiative and may only Dash, Disengage or Dodge; a rider knocked prone or whose
  mount is moved against its will makes a DC 10 DEX save or falls), vehicles (HP, AC
  and speed rows for carts and boats, which `travel --by` already names), and
  lingering injuries (`lingering-injuries: off | on`, from a campaign table, on a crit
  or a drop to 0 HP).

## Spatial model (theater of the mind, backed by coordinates)

Players describe intent in fiction ("I rush the archer on the landing"); the GM keeps
the geometry honest underneath.

**Store positions, never distances.** Every combatant and every terrain feature that
matters gets one `(x,y,z)` in feet (multiples of 5 = a 5-ft cell's center). Distances
are derived on demand: `max(|dx|,|dy|,|dz|)` (rules/combat-basics.md). A pairwise
distance table is forbidden: it's O(n²) and the GM *will* write contradictory entries.

**When positions get logged:**
1. **Tense scene** (01, Scene tempo): when tempo goes tense, `gm.py tempo tense` writes
   a Stage table (04) and the GM gives each on-stage creature a `pos` **by name**
   (`--pos Mara @bar --pos Tobin @tables-e`), using the location's `## Layout`. The
   tool turns names into cells. That's one argument per creature, and combat starts
   with everyone already placed.
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
- **The GM names destinations, not coordinates.** "I rush the archer on the landing" is
  `space move Kael --to Veskar`; the tool finds the path around tables and up the
  stairs, respects walls, and reports the cost and opportunity attacks. The GM only
  supplies waypoints to force an unusual route (vaulting the bar). This keeps the
  geometry out of the model's head, which is where the mistakes and the slow turns come
  from.
- **Walls are terrain.** Once a site has more than one sub-area laid out, or a fight is
  reframed to the area tier, interior and exterior walls are `wall` rows (04). Without
  them the tools would move creatures and cones through buildings.
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

- **`engine/space.py`** (also `gm.py space ...`) reads the Combat block and does the math the GM shouldn't do by
  hand: `dist`, `move` (`--to <creature|@feature|point>` pathfinding, or `--path`;
  cost, over-speed, opportunity attacks, unplanned drops), `cone`, `line`, `sphere`,
  `emanation` (who's in the area, stopping at walls), and `map`. Any point argument
  accepts `@<feature id>`. Use it for anything beyond a simple distance; mental math is
  fine for "is the goblin within 5 ft?".
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
  Use `gm.py world add <name> --near <id> --within <dist> [--dir E] [--on <feature>]
  --note "..."` (spatial facts become constraints, everything else goes in the note),
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
  contradict it. The promise survives placement: when the road to it is finally drawn,
  lint checks the road keeps it (04 → checked twice).
- **Travel is visible.** NPCs on a schedule are on the road between places, not
  teleported (06 → `clock`). The party can meet them, follow them, or miss them by an
  hour, and `trace` can say where someone was at 00:10.
- **Unknown ≠ empty.** The GM never says "there's nothing out there", only what the
  characters know or have heard. Rumors are `## Known, not placed` rows, and a rumor
  can be wrong: note `rumor; may be false` in `notes`.
- **The end-of-session world tick** may add frontier leads that play implied, but it
  never places them. Placement waits until play needs it.

## Failure & tone guardrails

- Fail forward: a failed check changes the situation, it doesn't dead-end it.
- "No" is rare: a player's plan gets checks, not a refusal, unless it would break the
  core scenario. Everything else that sounds like a no comes with a way forward (Player
  plans → Kinds of "no").
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
