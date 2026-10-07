---
name: scene
description: Enter a new location or a major scene shift in play — builds the scene packet, makes it the current scene, refines who is on stage, and narrates the establishing exposition. Use when the party arrives somewhere new or the situation changes a lot.
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*), Read
---

# Scene change

1. `python engine/gm.py scene enter <site[/area]> [--light dim|dark] --write [--summary "<2–4 sentences>"] [--scene "<name>"]`
   - Light: the real light there now (night outdoors → `dim`/`dark`; inside a lit inn → bright).
     Set it honestly even when a PC has darkvision: the brief's `Sight` line works out who
     sees what from their `senses:`, and passive notices already account for it.
   - It moves the party, rebuilds On stage / Watch for / Clocks, resets tempo to calm,
     ends `scene`-scoped table rules and runs a full lint (a `[LINT]` report line).
   - If the party is travelling between places, use `/travel` instead (it ends with
     this same step).
2. Read the packet (it is GM-only, never pasted):
   - **Exits / Nearby** — what's around, by bearing, distance and route time.
   - **Present / Not on stage but here** — who is in the room, who is elsewhere in the site.
   - **Passive notices** — volunteer exactly these to the named PCs, in fiction. Never
     mention who noticed nothing. `TRAP pit (step on the loose boards)` means that PC
     spots the trap and what would set it off; describe what they see (a loose board,
     a thin wire), never the DC or the trap's effect.
   - **Marching order** (when set) — who walks first into this place.
   - **Hidden: Kira (17) — unseen by …** — the stored Stealth total against everyone
     here now. Someone listed under `spotted by` has seen her: play it (or `cond Kira
     -hidden`). Never re-roll stealth.
   - **Triggers** — beats whose text mentions this place or these people. Read the
     scenario beat only if it might fire now; whether it fires is your call.
   - **Layout** — whether a map exists for this room.
3. Refine On stage lines with what the NPCs want *right now*:
   `python engine/gm.py onstage <npc> --goal "…" --note "…"`. Add someone who walks in the
   same way; `--remove` someone who leaves (or `move-npc` them).
4. Narrate the establishing exposition: short (2–4 sentences) for a familiar place,
   medium for a new one, long (3+ paragraphs) only for a big story moment. Use real
   details from the Description and the Nearby line. End with an affordance.
5. **Traps.** A trap is a `TRAP` line under the location's `## Hidden`; the tool keeps
   its state. When someone sets it off: `python engine/gm.py trap trigger <id> --who Kael`
   (without `--who`, the marching order's front row). It asks for the player's save; run
   it again with their total and the tool rolls the damage, applies falls and conditions
   and marks it `triggered`. A disarm attempt: `trap disarm <id> --who Kira <total>` (a
   miss by 5 or more sets it off). `trap status` is for you only. Never invent a trap's
   damage, and never read its `(GM …)` notes or disarm details to the table.
   **Hazards:** `hazard fall Kael 30` (1d6 per 10 ft, lands prone) · `hazard breath Kael`
   (held breath, then choking, then 0 HP: the clock runs it) · `hazard env
   extreme-cold|extreme-heat|underwater|none` (the clock then asks the hourly CON saves;
   underwater changes weapon attacks and fire damage). Narrate the numbers it returns.
6. If the scene turns tense (a standoff, a grab, someone slipping away), switch tempo:
   `python engine/gm.py tempo tense [--adj "Mara +5 watching the room"] --pos "Mara @bar" --pos "Kira near Tobin"`.
   Place everyone by name (`@feature`, `@feature N|S|E|W`, `near <creature>`). If the room
   has no Layout yet, describe it and place what matters lazily; the first fight writes
   the Layout.
