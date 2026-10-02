# House Rules & Table Conventions

Record any deviation from RAW (rules as written) here so rulings stay consistent
across sessions. The GM checks this file when a ruling feels contested.

## Dice
- Players roll their own d20s and report the natural roll or the total; the GM rolls
  NPC/monster/secret rolls via real RNG (`gm.py`) and shows them in brackets. Secret
  rolls show only as `[rolled behind the screen]`, and the GM sometimes makes decoy
  secret rolls.

## Ties go to the player
Any exact tie involving a PC resolves in the PC's favor: checks, contests, attacks,
saves, initiative (rolled or passive). Concretely:
- **PC roll = DC / AC** → PC succeeds / hits (same as RAW).
- **Contest tie** (grapple, Deception vs. Insight, etc.) → PC wins, whether attacker or
  defender. *Overrides RAW "defender wins ties."*
- **NPC roll = PC's AC, save DC, or passive score** → the PC's side wins: the attack
  misses, the PC resists, the sneaking NPC is spotted. *Overrides RAW "meets it, beats it."*
- **Initiative tie** (PC vs. NPC) → PC goes first.
- PC vs. PC ties: no house rule — re-roll or let the players decide.

## Overrules
Players can retcon events or add table rules by agreement with `/overrule` (see
`planning/02` → Overrule). Temporary rules live in the campaign's
`state/table-rules.md` and outrank this file while active. Campaign rules the table
wants everywhere get promoted into this file at `/end-session`.

## Rulings log
<!-- GM appends: date, situation, ruling made. Promote recurring ones to real house rules above. -->
