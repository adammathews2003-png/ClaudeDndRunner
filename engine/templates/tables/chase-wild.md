---
die: d20
---
# Chase complications — wilderness
<!-- Engine default (docs/design/02 → Table mechanics → Phase 14 → Chases). A campaign's own
     tables/chase-wild.md replaces it. Rolled by `gm.py chase next` for the participant
     whose turn comes next. `effect`: `los` = a quarry rolling it slips out of the pursuers'
     sight (the escape test follows its turn); anything else is applied by the GM
     (`chase next --lose 10` for lost ground). -->

| roll  | result                                                                                         | effect |
|-------|------------------------------------------------------------------------------------------------|--------|
| 1     | Thick brambles: DC 10 STR (Athletics) to push through, or lose 10 ft                            | -10 ft on a fail |
| 2     | A hidden root or rabbit hole: DC 10 DEX save or fall prone                                      | prone on a fail |
| 3     | A stream with slick stones: DC 10 DEX (Acrobatics) or lose 10 ft                                | -10 ft on a fail |
| 4     | A steep bank: DC 10 STR (Athletics) to climb it, or lose 15 ft                                  | -15 ft on a fail |
| 5     | Low branches whip across the path: DC 10 DEX save or 1d4 bludgeoning                            | 1d4 bludgeoning on a fail |
| 6     | Stinging insects swarm up from a rotten log: DC 10 CON save or lose 10 ft                       | -10 ft on a fail |
| 7     | Tall reeds or a fold in the ground: the quarry drops out of sight                               | los |
| 8     | Mud underfoot: DC 10 STR save or lose 10 ft                                                     | -10 ft on a fail |
| 9     | A startled herd scatters across the way                                                         | narrate |
| 10    | Mist rolls in off low ground: the quarry is lost to view                                        | los |
| 11-20 | No complication                                                                                |        |
