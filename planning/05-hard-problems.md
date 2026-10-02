# 05 — Problems You Haven't Hit Yet (and proposed solutions)

Things the basic design doesn't cover but WILL bite us. Each has a proposed fix; most
fixes are cheap if built in from the start.

## 1. State drift — conversation vs. files diverging
The #1 failure mode. The GM narrates "the guard takes your dagger" but never writes it
to the PC file; three turns later (or after context compaction) the dagger is back.
**Fix:** the "if it happened, file it" rule baked into the turn loop — every turn ends
with a state-delta list in the session log, and the files are canonical, not the chat.
When conversation and files disagree, files win. Add a `/checkpoint` habit: state is
written every turn, so a crash or compaction loses nothing. **Tooling (06):** every
`gm.py` mutation writes the canonical file *and* auto-logs its delta, so filing is a side
effect rather than a habit. The injected brief shows the files' view of the world each
turn, so drift is visible right away.

## 2. LLMs are terrible (and biased) random number generators
If the model "rolls" mentally, results skew dramatic and generous — the game quietly
becomes storytime. **Fix:** all GM dice go through real RNG (`gm.py roll`/`atk`/`save`,
06). The tool also does the arithmetic and applies the house rules, so the model never
adds up or compares a roll. Non-negotiable, and stated in the GM skill so it survives
instruction drift.

## 3. The too-nice GM (sycophancy)
Models want to please: fudging in players' favor, telegraphing every trap, letting
persuasion always work, retconning when players complain. This kills tension.
**Fix:** explicit GM-skill directives: dice results are final; NPCs are allowed to say
no, lie, and win; failed checks have real costs (fail forward, not fail soft); player
displeasure is not evidence of GM error. The rulings log (rules/house-rules.md) resolves
disputes by precedent, not by whoever pushes hardest.

## 4. No save states → one bad write loses history
Files get overwritten in place; a confused update can trash an NPC's history.
**Fix:** `git init` the `dnd-adventure/` folder (it's currently not a repo). Auto-commit
at end of every session (and optionally every scene change) = free save states, diffable
"what changed this session," and rollback. Also enables branching for "what if" one-shots.
`gm.py session archive` does the end-of-session commit; `gm.py undo` (journal of
before-images) covers single bad writes between commits.

## 5. Relational maps go contradictory
Prose-only geography eventually produces "A is north of B, B is north of C, C is north
of A," or one-way doors (A links to B, B doesn't know A). **Fix:** connections must be
written symmetrically — adding a connection means editing BOTH files (the `/scene` /
world-edit skill enforces this), and each connection carries direction + travel time so
contradictions are checkable. A consistency sweep reports asymmetries and travel times
that disagree between the two ends. It's now a script (`gm.py lint`, 06) rather than a
background agent: deterministic, instant, and run by `/end-session`.

## 6. Improvised canon evaporates
Mid-scene the GM invents a barmaid, a street name, a rumor. If it's not filed, next
session it never existed — or worse, gets reinvented differently. **Fix:** the background
write step includes "new inventions → stub files" (a 3-line NPC/location stub is enough;
`gm.py stub npc "Jess" --location crossroads-inn` makes one in a single call).
Stubs get fleshed out only if they recur.

## 7. Time is fuzzy and everything depends on it
Rests, spell durations, NPC schedules, scenario clocks, torch burn — all need a clock,
and narration alone won't keep one. **Fix:** `in-game-datetime` in `state/current.md`
frontmatter, advanced explicitly every scene ("~20 minutes pass"). NPC `## Movements`
schedules and scenario CLOCK beats key off it. The GM states time passage at scene ends
so players can object before it's canon. **Tooling (06):** time is stored as
`Day N HH:MM`, and NPC movements / CLOCK beats use machine-readable lines (04).
`gm.py clock advance` then reports every schedule move, clock beat and condition expiry
it crossed, so nothing depends on the model remembering to check.

## 8. Long-session context limits
A 4-hour session outgrows the context window; auto-compaction will eat scene nuance.
**Fix:** already half-solved by `state/current.md` + per-turn session logging — after
compaction the GM re-reads those two files and loses nothing durable. Rather than
relying on a skill instruction ("re-read after compaction"), a `SessionStart` hook
(source `compact`) injects `gm.py brief --long` automatically (06).

## 9. The world freezes when players aren't looking
NPCs only act on stage; the village becomes a theme park. **Fix:** two mechanisms:
scenario CLOCK beats (world advances on schedule regardless of party), and a
**world tick** inside `/end-session` — the GM spends one pass moving off-screen NPCs
per their schedules/motivations and logging consequences. Cheap, and makes the world
feel alive at next session's recap.

## 10. Multiple players, one keyboard
Whose PC is acting? Cross-talk gets attributed wrong. **Fix:** convention — prefix input
with the PC name (`Kira: I check the trapdoor`). Unprefixed input = table talk, not
in-character. The GM also tracks spotlight (session log notes who's acted recently) and
deliberately turns to quiet PCs ("Bren, you're nearest the door — what are you doing?").

## 11. Player knowledge ≠ character knowledge
The user reads files (or just metagames). Partially unsolvable with honor-system
secrets; make it cheap to do the right thing. **Fix:** spoilers live ONLY under
clearly-marked sections (`## The truth (SPOILERS)`, `## Hidden`, NPC secrets) so a
player can safely open any file's top half; everything else is player-safe.
**Decided (2026-10-02):** files stay honor-system (no `gm-only/` split). The bigger leak
is the console: plain Claude Code shows command lines and tool output, which spell out
GM decisions. Play therefore runs through the table client (06), which shows only
narration, and the GM follows the *Behind the screen* rules (02).

## 12. Absent players
Real groups miss sessions. **Fix:** PC frontmatter gets an `autopilot:` note (one line:
how this PC behaves conservatively when unplayed — "follows the group, defends herself,
makes no major decisions"). GM runs absent PCs on autopilot; no XP/loot penalties.

## 13. Retcons and GM mistakes
The GM will misremember an AC or contradict established fact. **Fix:** a table rule —
anyone can call "check the record"; GM checks the files/log (`gm.py where`, the brief,
the delta lines); files win; the correction is logged (`gm.py undo` if it was a bad
write). For genuine narrative retcons the table agrees to, log them in
`house-rules.md` → Rulings log so they're deliberate and remembered.

## 14. Latency budget honesty
Even with the digest, a scene change = 3–5 file reads + narration + writes, and the
Edit tool's Read-before-Edit requirement roughly doubles every write. **Fix (06):**
move the mechanical work into scripts. A normal turn becomes: brief injected by hook
(0 reads) → one `gm.py do` batch (rolls, outcomes, writes, log) → narrate. A scene
change becomes one `gm.py scene enter` call. A permissions allowlist for `tools/` means
no mid-turn prompts. Only slow multi-file work that needs judgment (world tick, doc
rewrites) goes to background agents, on a faster model if latency is felt.

## 15. Rules edge cases mid-combat
Grapple-shove interactions, stacking conditions, ready-action timing — lookups stall
scenes. **Fix:** rulings-over-rules is already policy (02); the addition is: reconcile
AFTER the session — `/end-session` reviews the rulings log, checks contested rulings
against the rules sheets, and notes the going-forward answer.
