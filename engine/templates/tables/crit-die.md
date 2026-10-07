---
die: d10
---
# Critical hit die
<!-- Engine starter table, original text (docs/design/02 → Table mechanics → Phase 16 →
     Critical hit die). Copied into a new campaign by `gm.py campaign new`; the campaign's
     own tables/crit-die.md is the one `atk` rolls while `crit-die: on`. One row per face:
     the die is as big as the table (8 rows = d8). Codes the tool applies: `dice x2`,
     `dice x3`, `max+dice`, `prone`, `stunned 1t`, `disarm`, `bleed 1d4`, `kill`. A row
     without a damage code (and without `kill`) deals `dice x2`. Anything else is
     narrated by the GM. -->

| roll | result | effect |
|------|--------|--------|
| 1 | A clean, brutal hit. | dice x2 |
| 2 | Right where the armour doesn't reach. | dice x2 |
| 3 | Textbook: the kind of blow they teach to recruits. | dice x2 |
| 4 | Everything behind it: the dice at their maximum, then rolled again on top. | max+dice |
| 5 | A blow for the songs: the dice tripled. | dice x3 |
| 6 | The weapon spins out of their grip and lands at their feet. | dice x2; disarm |
| 7 | Off their feet and onto the floor. | dice x2; prone |
| 8 | Ringing like a bell: stunned until the end of their next turn. | dice x2; stunned 1t |
| 9 | A deep, bleeding wound: 1d4 at the start of each of their turns until healed or a DC 10 Medicine check. | dice x2; bleed 1d4 |
| 10 | Slain outright. | kill |
