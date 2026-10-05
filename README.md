# Claude GM — D&D 5e adventure run by Claude Code

State lives in markdown; Claude Code plays Game Master via skills; every number and
every write goes through the engine (`engine/gm.py`).

## Layout

| folder | what |
|---|---|
| `engine/` | the tools: `gm.py` (every command), `table.py` (the players' console), `space.py`, `lib/`, `templates/`, `tests/` (+ frozen `tests/fixtures/`) |
| `.claude/` | project settings (hooks, permission allowlist) and the GM + authoring skills |
| `campaigns/` | one folder **and git repository** per campaign (`poc`, `loop-play`, `loop-open`, `dryrun`, …); `campaigns/.active` names the default |
| `rules/` | condensed rule sheets the GM reads; `rules/mechanics/` for optional campaign mechanics |
| `data/srd/` | SRD 5.1 data (CC-BY-4.0, see its LICENSE.md) |
| `docs/design/` | the design (01–07) · `docs/build/` the build plan, status and notes |

## Running

- Play: `python engine/table.py --campaign <name>` (narration only; `/gm` starts the session).
- GM's eye / prep: plain `claude` in this folder; `python engine/gm.py --campaign <name> <command>`.
- Tests: `python -m unittest discover -s engine/tests`.
- Needs Python 3.10+; `pip install claude-agent-sdk` for `table.py` only. Trust this folder
  in Claude Code once (open `claude` here and accept) so the allowlist applies.

## Build phases

Status and notes: `docs/build/README.md`. Done: design, POC content, tools (Phases 1–7),
GM skills (9), campaign authoring + mechanics (11). Left: Phase 10, the verification
sweep and dry run (in `campaigns/dryrun`), and Phase 8 (deferred spatial features).

## Open decisions

1. **Edition:** assuming 2014 5e rules unless told otherwise.
2. ~~Secrets~~ **Decided:** honor system for files (the driver doesn't open them); play
   runs through `engine/table.py`, which shows only narration (docs/design/01 → Secrets).
3. ~~Dice~~ **Decided:** players roll their own d20s and report them; the GM rolls the rest via `gm.py`.
4. **Table size:** how many players/PCs will the real campaign have?
5. ~~Git~~ **Decided (2026-10-05):** `dnd-adventure/` is the engine repo (branch `main`),
   published at https://github.com/adammathews2003-png/ClaudeDndRunner. Each campaign
   under `campaigns/` is its own git repository: `gm.py session archive` and the time
   loop commit there, never in the engine repo (docs/design/05, item 4).
6. ~~Tools~~ **Decided:** stdlib frontmatter parser; hybrid brief injection; lint at
   write time, per batch on touched files, and fully at scene/session boundaries.
   Secrets in tool output: hidden by the table client (`docs/design/06-tools-spec.md`).
7. ~~Advancement~~ **Decided (2026-10-05): per campaign.** `advancement: milestone`
   (default; GM announces levels, `gm.py pc level-pending`) or `advancement: xp` (PHB
   thresholds flag level-ups automatically). **XP is tracked by default in both modes**
   (`xp-tracking: on`; `gm.py xp award`, combat XP offered at `combat end`) so the total
   is available for other thresholds or a later switch; `xp-tracking: off` disables it.
   Absent PCs' share is a campaign setting (`xp-absent`).
   HP per level **decided: max or roll**, chosen once per character (`hp-method`),
   revisited only if the player asks (house rule).
8. ~~Map model~~ **Decided (2026-10-04):** nested coordinate frames: world (mi) → area (ft)
   → site (5-ft cells), north-up, offset-only, same-unit nesting to any depth. Each
   route is stored once in the parent frame; sites may carry their own routes. The GM
   addresses places and creatures by name (`@bar`, `--to Veskar`) and the tools do the
   geometry. Directions, distances and travel times are derived by tools, never hand-written
   (docs/design/01 → World geometry, 04 → Location files). Every campaign has a world file
   from creation: known places are placed or constrained, and the rest is open frontier
   filled in by generation, player choice or imports (docs/design/02 → The open world).
