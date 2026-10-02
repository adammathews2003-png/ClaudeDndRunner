# 01 — Architecture

## Goal
A D&D 5e adventure run by Claude Code acting as Game Master (GM). All game state lives
in markdown files. Each turn: players type actions/dialog → GM reads relevant state →
narrates the scene, adjudicates rules, drives NPCs → updates state files in the background.

## Directory layout

```
dnd-adventure/
├── planning/            # These design docs (not read during play)
├── rules/               # Condensed 5e rule references (read on demand, shared by all campaigns)
├── poc/                 # The proof-of-concept campaign — one folder per campaign
│   ├── state/
│   │   ├── current.md       # THE hot file: scene digest, party location, in-game time, active NPCs
│   │   └── table-rules.md   # Active player overrule rules (02 → Overrule)
│   ├── locations/           # One file per location
│   ├── npcs/                # One file per NPC
│   ├── pcs/                 # One file per player character
│   ├── scenarios/           # Story arcs: factions, motivations, secrets, planned beats
│   ├── sessions/
│   │   ├── session-current.md   # Running log of the active session
│   │   └── history/             # Compressed summaries of past sessions
│   ├── tables/              # Random/encounter tables (gm.py roll table:<slug>)
│   └── .gm/journal/         # Undo before-images written by tools (not canon)
├── tools/               # gm.py + modules: dice, state writes, scene, combat, clock… (06);
│                        #   table.py = the players' console (narration only)
├── data/srd/            # SRD 5.1 JSON: monsters, spells, conditions (CC-BY-4.0)
├── .campaign            # Name of the active campaign folder
└── .claude/
    ├── settings.json    # Hooks (brief injection) + tool permission allowlist (06)
    └── skills/          # GM skills (built in phase 2 — see 02-gm-agent-design.md)
```

## The latency problem, and the answer: `state/current.md`

Re-reading every location/NPC/scenario file every turn is slow and burns context. Instead,
`state/current.md` is a **scene cache** — a digest the GM maintains that contains everything
needed for a normal turn:

- Party location + one-paragraph scene summary
- Each present NPC: name, one-line disposition, current goal in this scene
- Active clocks/tension (e.g., "guards arrive in ~10 min game time")
- Pointers (file paths) to the full docs for everything on stage

**Normal turn:** the digest arrives as an injected `gm.py brief` (no read) → one
`gm.py do` call for mechanics + writes → narrate. Fast.
**Scene change** (party moves, new NPC enters, combat starts): one `gm.py scene enter`
call returns the new elements as a packet and rebuilds the digest in `current.md`.
**Scenario consult:** the GM re-reads the scenario doc when a story beat could trigger,
not every turn. `current.md` keeps a "watch for" list of trigger conditions so the GM
knows *when* a re-read is warranted.

## Turn loop

1. Players type what their characters do/say (one message can carry multiple PCs).
2. The brief hook has already injected the current state with the player's message (06).
   The GM doesn't read `current.md`.
3. **Order the actors** (see *Scene tempo* below): PC declarations + what each NPC
   intends this beat, sorted by the scene's tempo order.
4. **Resolve in order.** Walk the list; each actor acts against the world *as left by
   the actors before them*:
   - Rules adjudication: decide if the action needs a check and its DC (see 02); the
     roll and outcome come from `gm.py` (atk/save/check/contest).
   - NPC decisions: act from disposition/goal in the digest, **reacting to what earlier
     actors just did**; consult the full NPC file only if it goes beyond the digest.
   - If an earlier result invalidates a PC's declared action (the letter is already
     pocketed, the door already slammed), resolve the PC's closest sensible intent — or,
     if there's no sensible version, stop the walk there and hand the moment back to that
     player. Never silently discard a PC's action.
5. Narrate the result **in resolution order**, so cause → reaction reads naturally. End
   with a clear "what do you do?" affordance.
6. **Writes**: in practice steps 4–6 are a single `gm.py do "..."` batch. Rolls,
   HP/conditions, items, attitudes and NPC moves go to the canonical files, and each
   change auto-logs a delta line to `sessions/session-current.md`. The batch ends with
   `log "<turn summary>"`. Only *durable* changes touch location/NPC/PC files (item
   taken, attitude shifted, HP/conditions, someone moved). Scene-only facts stay in
   `current.md`.

Only slow multi-file work (world tick, doc rewrites) goes to a background subagent.
Ordinary writes are faster as a script call than as an agent.

## Scene tempo (initiative outside combat)

Initiative isn't only a combat thing: in any scene, *who moves first* shapes what everyone
else is reacting to. The GM always resolves a turn in an order, scaled to the tension:

| Tempo | When | How order is set | Cost |
|---|---|---|---|
| **Calm** | Browsing a shop, casual chat | Narrative order — whoever the fiction says. PCs first by default. | None |
| **Tense** | A standoff, a lie about to unravel, a grab for the same item, someone trying to slip away | **Passive initiative**: 10 + DEX mod, ± situational adjustment (+5 already-alert/prepared, −5 distracted/drunk/caught off guard). Ties → PCs. Computed once when the scene turns tense (`gm.py tempo tense`), stored as the Stage table in `current.md` along with each creature's position (02, Spatial model). | One-time, no rolls |
| **Combat** | Violence starts | Rolled initiative per `rules/combat-basics.md`. Seed it from the tense order: anyone who was already acting first is the likely ambusher, not surprised. Positions carry over from the tense scene. | Normal combat |

Notes:
- **Readiness beats speed.** The ± adjustment is where the fiction lives: the barkeep who's
  been watching the rogue's hands all night acts before the rogue, regardless of DEX.
- **Order is sticky** for the scene; recompute only when tempo changes or a new actor
  enters. That keeps it a cache hit, not per-turn work.
- **NPCs get intents, not just reactions.** Each tense-scene NPC has a "this beat" intent
  (from their digest goal) that slots into the order. That's what lets an NPC *pre-empt* a
  PC rather than only respond to them.
- **Don't expose the machinery in calm scenes.** In tense scenes, the order may be
  visible in the narration ("Mara is faster —"), but no numbers unless players ask.

## Movement & the relational map

No coordinate grid. Every location file has a `## Connections` section listing adjacent/
known locations with direction, travel time, and how obvious the route is. Moving = follow
a connection, load the destination file, rebuild the scene digest. NPC files carry a
`location:` field; when an NPC moves (on-screen or off-screen per scenario logic), that
field changes and both location files' "who is here" awareness comes from querying NPC
frontmatter (grep `location: <name>`), not from lists duplicated inside location files —
one source of truth.

## Session lifecycle

- **Session start:** `python tools/table.py` resumes or starts the session and sends
  `/gm`, which sets `in-session: true`; the SessionStart hook injects the
  long brief (scene + recent log) → read the latest history summary → recap → play.
- **During:** `session-current.md` grows as a turn-by-turn log (written by `gm.py`).
- **Session end (a skill):** the GM writes the summary and does the world tick; then
  `gm.py session archive` files it in `sessions/history/`, resets the log, runs `lint`
  and commits to git. This keeps the hot path small forever.

## Secrets: honor-system files, clean console

**Decided (2026-10-02).** The person running Claude Code is also a player. Two
surfaces could leak:

1. **Files: honor system.** The driver doesn't open game files during a campaign.
   Spoilers stay in clearly marked sections (`## The truth`, `## Hidden`,
   `## Knowledge & secrets`, `## Beats & triggers`) so a top-half glance is safe
   (05 #11). No `gm-only/` folder and no obfuscation.
2. **The console: enforced.** Play runs through the **table client**
   (`python tools/table.py`, 06), not the Claude Code terminal. It shows only the GM's
   narration. Tool calls, command lines, tool output, thinking and the injected brief
   never reach the screen. Narration itself is governed by the *Behind the screen*
   rules (02), and maps shown to players are `--player-view` renders.

Plain `claude` stays the GM's-eye view, for building, prep and debugging. Don't play in it.

Players who *want* to peek use `/spoilers` (02), the one deliberate exception. Like
`/overrule`, it's honor-based: whoever runs the session uses it when they choose. It
answers questions about secrets and "what if" alternatives (never as facts), and
records what was revealed in `sessions/spoilers.md`.

Note: whoever authors a scenario knows its secrets. The POC is already known to its
author and is fine for dry runs. For a surprise campaign, someone other than the
driver (Claude in a prep session the driver doesn't read, or a friend) writes the
secret sections.
