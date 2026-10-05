---
name: campaign-status
description: Show a campaign at the driver's reveal level — settings, player-safe premise, known places, fill-in queue, and how much has been generated — without revealing anything the policy keeps hidden. The driver types /campaign-status.
disable-model-invocation: true
allowed-tools: Bash(python tools/gm.py:*), PowerShell(python tools/gm.py:*)
---

# Campaign status

Campaign: $ARGUMENTS (default: the active campaign)

1. `python tools/gm.py [--campaign <slug>] campaign status` — it prints at the campaign's
   own `reveal-policy` level. Only pass `--level outline` or `--level full` if the driver
   explicitly asks for more *and* accepts the spoilers; then record it:
   `campaign ledger add "status at <level>" --via campaign-status`.
2. Show the output as is. Add, from tools only: `python tools/gm.py [--campaign <slug>] lint`
   (counts only) and, if PCs exist, `danger --bearing <dir>` readings the driver asks for.
3. Never open scenario files, NPC files' secrets, `## Author notes` or `## Hidden` here.
