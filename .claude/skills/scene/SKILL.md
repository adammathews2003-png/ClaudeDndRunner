---
name: scene
description: Enter a new location or a major scene shift in play — builds the scene packet, makes it the current scene, refines who is on stage, and narrates the establishing exposition. Use when the party arrives somewhere new or the situation changes a lot.
allowed-tools: Bash(python tools/gm.py:*), PowerShell(python tools/gm.py:*), Read
---

# Scene change

1. `python tools/gm.py scene enter <site[/area]> [--light dim|dark] --write [--summary "<2–4 sentences>"] [--scene "<name>"]`
   - Light: the real light there now (night outdoors → `dim`/`dark`; inside a lit inn → bright).
   - It moves the party, rebuilds On stage / Watch for / Clocks, resets tempo to calm,
     ends `scene`-scoped table rules and runs a full lint (a `[LINT]` report line).
   - If the party is travelling between places, use `/travel` instead (it ends with
     this same step).
2. Read the packet (it is GM-only, never pasted):
   - **Exits / Nearby** — what's around, by bearing, distance and route time.
   - **Present / Not on stage but here** — who is in the room, who is elsewhere in the site.
   - **Passive notices** — volunteer exactly these to the named PCs, in fiction. Never
     mention who noticed nothing.
   - **Triggers** — beats whose text mentions this place or these people. Read the
     scenario beat only if it might fire now; whether it fires is your call.
   - **Layout** — whether a map exists for this room.
3. Refine On stage lines with what the NPCs want *right now*:
   `python tools/gm.py onstage <npc> --goal "…" --note "…"`. Add someone who walks in the
   same way; `--remove` someone who leaves (or `move-npc` them).
4. Narrate the establishing exposition: short (2–4 sentences) for a familiar place,
   medium for a new one, long (3+ paragraphs) only for a big story moment. Use real
   details from the Description and the Nearby line. End with an affordance.
5. If the scene turns tense (a standoff, a grab, someone slipping away), switch tempo:
   `python tools/gm.py tempo tense [--adj "Mara +5 watching the room"] --pos "Mara @bar" --pos "Kira near Tobin"`.
   Place everyone by name (`@feature`, `@feature N|S|E|W`, `near <creature>`). If the room
   has no Layout yet, describe it and place what matters lazily; the first fight writes
   the Layout.
