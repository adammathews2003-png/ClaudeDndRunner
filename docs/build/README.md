# Implementation plan — index

The step-by-step build plan for everything specified in `docs/design/01`–`06`: the
`engine/gm.py` suite and its `lib/`, the `space.py` extensions, the SRD data, the hooks and
permissions, the `table.py` client, and the GM skills in `.claude/skills/`.

- **`plan.md`** — the plan. Phase 0 is the consolidated documentation discovery (exact
  contracts, allowed APIs, verified external facts). Phases 1–10 map one-to-one onto the
  build order in `docs/design/06-tools-spec.md` → Build order (2a.1 … 2a.7, 2b, then the
  Phase 3 dry run from `README.md`).
- Each phase is written to be run **in a fresh session**: it says what to read first,
  what to build (by copying from the cited spec lines, not by inventing), the exact
  function contracts later phases depend on, how to prove it worked, and what not to do.
- Line references are to the planning docs **as of commit `0bbce3d` (2026-10-04)**.
  If a doc has changed since, search for the quoted heading instead of trusting the line.

## Status

| Phase | Build step | Contents | Done |
|---|---|---|---|
| 0 | — | Documentation discovery (in `plan.md`) | [x] |
| 1 | 2a.1 | `lib/md.py`, `lib/campaign.py`, `lib/journal.py`, `lib/gametime.py`, `gm.py` skeleton + `do`, test harness, `campaigns/.active` | [x] `0bbce3d`→ see git log (2026-10-04) |
| 2 | 2a.2 | `lib/dice.py`, `lib/resolve.py`, `roll`, `atk/save/check/contest`, mutations, `log`, `undo`, `rule/retcon/overrule-undo` | [x] 2026-10-05 |
| 3 | 2a.3 | `brief` + hooks + permissions allowlist (`.claude/settings.json`), Wacky Juice, check margins | [x] 2026-10-05 |
| 4 | 2a.4 | `lib/geo.py`, `scene enter`, `tempo/pos/intent/onstage`, `combat start/next/end`, `srd` + data download, `space.py` on `md.py` + Stage table + `secret` | [x] 2026-10-05 |
| 5 | 2a.5 | `table.py` client, `space.py map --player-view` | [x] 2026-10-05 |
| 6 | 2a.5b | `gm.py pc` + SRD class/race/equipment data + `gm.py xp` (XP advancement, per campaign) | [x] 2026-10-05 |
| 7 | 2a.6 | `clock`, `travel`, `rest`, `lint`, `session archive`, `stub`, `where`, `world`, `trace`, `odds`, `spoil` | [x] 2026-10-05 |
| 8 | 2a.7 | `combat reframe`, `world place` suggestions, `world import`, `space.py map --place` | [ ] |
| 9 | 2b | GM skills in `.claude/skills/` | [x] 2026-10-05 |
| 11 | 2c | `campaign`, `encounter`, `danger`, `loop` tools; `/campaign` authoring skills; time-loop rules sheet (`docs/design/07`) | [x] 2026-10-05 |
| 10 | Phase 3 | Verification sweep + dry-run readiness | [ ] |
| 12 | 2d | `split` (splitting the party: groups, slices, per-group clocks, sensing, join) + `/gm` guidance (02 → Splitting the party) | [x] 2026-10-06 |
| 13 | 2e | Table bookkeeping: `conc`, dying/`deathsave`, carried light sources, supplies, exhaustion, content boundaries + `!x` (02 → Table mechanics) | [x] 2026-10-07 |
| 14 | 2f | Exploration and pressure: travel activities + getting lost, social DCs, morale, chases, traps and hazards, hiding as a state | [x] 2026-10-07 |
| 15 | 2g | Optional subsystems: inspiration, readied actions, magic items, downtime, companions, weather, encumbrance, renown, mounts, injuries | [ ] |
| 16 | 2h | Table extras: pre-rolls + first-session how-to-play talk, carousing (`carouse`, `table import`, starter table), critical hit die | [ ] |
| 17 | 2i | Discord bridge in `table.py`: queue and auto modes, channel output, player map | [ ] |

Tick a phase here when its verification checklist in `plan.md` passes. Phases 1→7 are
sequential; 8 can wait indefinitely; 9 needs 1–7; 11 needs 7 and 9; 10 needs 9 and 11; 12 needs 9; 13 needs 12; 14 needs 13 (exhaustion, light); 15 needs 13 and
the social DCs from 14 for renown, otherwise its items stand alone. 16 needs 13 (death
saves for the crit die's `kill`, `lines:` for carousing), except its pre-roll item, which
needs nothing and can be built any time. 17 needs only 5.
