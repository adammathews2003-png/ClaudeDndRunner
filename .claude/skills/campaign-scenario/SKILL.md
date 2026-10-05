---
name: campaign-scenario
description: Expand the next arc of an existing campaign into scenario, NPC, location and table files with encounter budgets and threat metadata, in a forked context, reacting to what happened in play; returns only that arc's shape card. The driver types /campaign-scenario between sessions.
disable-model-invocation: true
context: fork
allowed-tools: Bash(python tools/gm.py:*), PowerShell(python tools/gm.py:*), Read, Write, Edit, Glob, Grep
---

# Next arc (forked: the driver never sees this)

Request (campaign slug, optional arc): $ARGUMENTS

1. Read `<slug>/campaign.md` (Author notes: the arcs), the scenarios so far, the session
   history (`sessions/history/*.md` including `## Behind the screen`), `sessions/spoilers.md`
   and `campaign.md ## Author ledger` (what the driver already knows), and
   `planning/07-campaign-authoring.md` + `planning/04-file-formats.md`.
2. Write the next arc the same way `campaign-generate` writes the first (scenario with
   machine-readable beats and clocks, NPCs with SRD stat blocks and schedule lines,
   locations with Places/Routes/Hidden, `ENCOUNTER` budgets + `gm.py encounter threat`,
   loot, tables). **React to play**: the party's choices, who they befriended or killed,
   answered fill-ins (promises), what was spoiled. Never contradict placed canon.
3. Update `campaign.md ## Author notes` with the arc's place in the whole. Run
   `gm.py --campaign <slug> lint` and fix errors.
4. Return **only** the arc's shape card: new places the party could learn of, the
   perceived stakes, danger readings (colours only), new fill-in questions. Never the
   truth, beats, clocks, secrets, rosters or contents.
