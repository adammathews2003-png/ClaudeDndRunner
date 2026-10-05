# House Rules & Table Conventions

Record any deviation from RAW (rules as written) here so rulings stay consistent
across sessions. The GM checks this file when a ruling feels contested.

## Dice
- Players roll their own d20s and report the natural roll or the total; the GM rolls
  NPC/monster/secret rolls via real RNG (`gm.py`) and shows them in brackets. Secret
  rolls show only as `[rolled behind the screen]`, and the GM sometimes makes decoy
  secret rolls.

## Hit points: max or roll
Each level after 1st gives **the hit die's maximum, or a roll of it**, plus CON mod.
*Overrides RAW "average (rounded up) or roll."* Level 1 is max (same as RAW).
- The player chooses **once per character**, at creation, stored as `hp-method`. It
  then applies automatically to every level, including levels a character starts above
  1st. The GM doesn't ask again at level-up.
- It's revisited **only if the player asks** in play ("switch me to rolling"), and the
  change applies to future levels only.
- A roll is final, even a 1, so rolling is a gamble against a guaranteed max. Rolls go
  through `gm.py roll` publicly, or the player reports their own.

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
The table can retcon events or add table rules with `/overrule` (honor-based: whoever
runs the session uses it when they choose; see `docs/design/02` → Overrule). Temporary rules live in the campaign's
`state/table-rules.md` and outrank this file while active. Campaign rules the table
wants everywhere get promoted into this file at `/end-session`.

## Rulings log
<!-- GM appends: date, situation, ruling made. Promote recurring ones to real house rules above. -->
