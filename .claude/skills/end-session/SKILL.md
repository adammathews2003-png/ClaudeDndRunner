---
name: end-session
description: Wrap up a play session — write the party-facing summary, do the world tick, promote campaign rules if the table wants, then archive the session (history file, log reset, lint, git commit). Players type /end-session.
disable-model-invocation: true
allowed-tools: Bash(python tools/gm.py:*), PowerShell(python tools/gm.py:*), Read
---

# End the session

1. **Close the last turn:** if a turn is open, `python tools/gm.py do "log \"<last beat>\""`.
2. **Summary (half a page, the party's point of view):** what they did, learned, gained
   and lost; open threads as the *characters* see them. No `(GM)` facts, no beat names,
   no secrets. Keep it as plain prose without double quotes (it goes on the command line
   in step 5).
3. **World tick (behind the screen):** what moved off-screen because of this session —
   NPC plans advancing, rumors spreading, clocks drawing near. Apply durable changes
   with the tools (`move-npc`, `attitude`, `world lead` for frontier leads that play
   implied — never place new places in a tick). Note it with `log "(world tick) …"`.
4. **Table rules:** if the table wants a campaign-scoped rule in every campaign, note it
   in the summary ("promote R1 to house rules"): that file is edited between sessions in a
   prep session, not at the table. Session-scoped rules end on archive.
5. **Archive:** `python tools/gm.py session archive --summary "<the summary>"`
   - It runs lint and refuses on errors: fix them (most are one `stub`, a `--fix-safe`,
     or a typo) and run again. `--force` only if the table says to stop now.
   - It writes `sessions/history/session-NN.md`, resets the log, clears `in-session`, ends
     session rules and commits to git.
6. **Close at the table** with one or two lines of fiction (where the party rests, what
   hangs in the air) and "Next time…" if there's a natural hook. Don't recap mechanics.
