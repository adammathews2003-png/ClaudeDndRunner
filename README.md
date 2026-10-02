# Claude GM — D&D 5e adventure run by Claude Code

State lives in markdown; Claude Code plays Game Master via skills. Design docs in
`planning/`, condensed rules in `rules/`, first campaign in `poc/`, helper scripts in
`tools/` (`space.py`: combat distances, movement, areas of effect, ASCII map — Python 3,
no dependencies). The full tool set (`gm.py`: dice and outcomes, state writes, scene
packets, combat, clock, lint) is specified in `planning/06-tools-spec.md`.

## Build phases

- [x] **Phase 0 — Design.** Planning docs (`planning/01`–`06`).
- [ ] **Phase 1 — POC content.** Flesh out the sample scenario in `poc/` (skeleton and
      sample files exist; replace/extend with our real ideas). Write remaining `rules/` sheets.
      Migrate POC files to the tool-readable formats in `planning/04` (time, Movements,
      CLOCK lines, PC Attacks/Resources).
- [ ] **Phase 2a — Tools.** Build `tools/gm.py` per `planning/06-tools-spec.md` (build
      order there), plus hooks + permission allowlist in `.claude/settings.json`, and the
      table client `tools/table.py` (the console players play in).
- [ ] **Phase 2b — GM skills.** Build `.claude/skills/`: `gm`, `scene`, `travel`,
      `combat`, `map`, `overrule`, `end-session`, `new-campaign` per `planning/02-gm-agent-design.md`,
      calling the 2a tools.
- [ ] **Phase 3 — Dry run.** Two pregen PCs, run the POC scenario for a few scenes,
      note where the GM stalls or state drifts, tighten skill instructions.
- [ ] **Phase 4 — Real campaign.** `/new-campaign`, port in the group's actual PCs.

## Open decisions

1. **Edition:** assuming 2014 5e rules unless told otherwise.
2. ~~Secrets~~ **Decided:** honor system for files (the driver doesn't open them); play
   runs through `tools/table.py`, which shows only narration (planning/01 → Secrets).
3. ~~Dice~~ **Decided:** players roll their own d20s and report them; the GM rolls the rest via `gm.py`.
4. **Table size:** how many players/PCs will the real campaign have?
5. ~~Git~~ **Done (2026-10-02):** the whole ProjectX workspace is a git repo (root one level
   up, branch `main`). `gm.py session archive` commits there (see planning/05, item 4).
6. ~~Tools~~ **Decided:** stdlib frontmatter parser; hybrid brief injection; lint at
   write time, per batch on touched files, and fully at scene/session boundaries.
   Only secrets-in-tool-output remains open (`planning/06-tools-spec.md` → Open questions).
