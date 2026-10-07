---
name: campaign-new
description: Start authoring a new campaign from the driver's seed (their own words) — extract the parameters, ask only for what's missing, write campaign.md, then hand generation to a forked context that returns only a player-safe shape card. The driver types /campaign-new; run it in an authoring session with memory plugins off.
disable-model-invocation: true
allowed-tools: Bash(python engine/gm.py:*), PowerShell(python engine/gm.py:*), Read, Write, Skill
---

# New campaign (intake)

The driver's seed: $ARGUMENTS

The driver will **play** this campaign. Everything you write in this conversation they
read, so this conversation never contains secrets: you only collect parameters here,
and the generation runs in a forked context that returns a shape card.

1. **Extract the parameters** from the seed (docs/design/07 → Parameters). The driver's words
   are promises, like world constraints: a "fishing town" stays a fishing town.
   `length`, `start-level`, `players`, `difficulty` (easy | medium | hard | deadly — a word,
   never a CR), `shape` (journey | boss | macguffin | mystery | sandbox | heist | siege) and
   `secondary`, `tone`, `weirdness` 1–5, `setting` (one line on what the world has: tech,
   how common magic is; propose one with the defaults if the seed doesn't say),
   `jokes` 1–5, `references` (none | light | heavy),
   `sidekick` (none | orphan | animal | either), `advancement` (milestone | xp),
   `reveal-policy` (shape-only | fill-in | outline | full | paired), `mechanics`
   (`time-loop` or none), the starting area's name, and a folder slug.
2. **Ask only for what's missing**, in one grouped, numbered message with the options.
   Propose defaults ("I'll use medium difficulty — OK?"). No secrets, no plot ideas.
   Always include **content boundaries** in that message: "Anything you never want in
   this game (lines), or want kept off screen (veils)? 'None' is a fine answer." Ask
   **`social-wall`** in the same message, in one line, alongside advancement: "On by
   default; it can make social scenes easier when you're stuck, and you can turn it off
   any time." (on → leave the default 3; off → `--set social-wall=off`). The other
   table settings (`supplies` strict | loose | off, `ammo` all | special | off,
   `track-light` on | off, `death-save-rolls` open | secret, `exhaustion` 2014 | 2024,
   `travel-detail` summary | activities, `getting-lost` on | off, `social-dcs` dmg | gm,
   `creativity` off | light | generous (generous suits a comedy), `morale` on | off,
   `chases` dmg | narrative; Phase 15: `inspiration` advantage | reroll | off, `downtime`
   off | light | full, `weather` off | on, `encumbrance` off | basic | variant, `renown`
   off | party | per-pc, `lingering-injuries` off | on, `upkeep` off | on — lifestyle,
   materials and wages in coin; this table keeps bookkeeping off; Phase 16: `carousing`
   on | off (default on), `crit-die` off | on, `crit-die-pcs` dying | dead) keep their defaults
   unless the seed touches them (a faction-heavy seed: `renown=party`; a wilderness
   seed: `weather=on`; a grim or tavern-free seed: `carousing=off`; "brutal crits": `crit-die=on`).
   Lingering injuries need the campaign's own `tables/injuries.md`; `campaign new`
   copies the engine's `tables/carousing.md` (credited, combined) and `tables/crit-die.md`
   (a table the driver found elsewhere comes in with `table import <file> --as
   carousing` and stays in the campaign).
3. **Write the seed verbatim** to a scratch file (e.g. `<slug>-seed.md` in your scratch
   space, or pass the text you have), then:
   `python engine/gm.py campaign new <slug> --area "<starting area>" --set length="3-5 sessions" start-level=3 difficulty=hard shape=mystery tone=comedic … [--set "mechanics=time-loop"] --seed-file <seed file>`
   Then record the boundaries (the generator reads them and keeps every line out):
   `python engine/gm.py --campaign <slug> campaign boundaries --line "…" --veil "…"` (or
   `--none`).
4. **Generate in a fork:** invoke the `campaign-generate` skill with the slug as its
   argument. It writes every file and returns **only the shape card**.
5. Show the driver the shape card exactly as returned. Record it:
   `python engine/gm.py --campaign <slug> campaign ledger add "shape card for arc 1" --via campaign-new`
   (no leading slash in `--via`).
6. If the policy is `fill-in` or `paired`, offer `/campaign-fill` for the open questions.
   To play: `/character` for PCs, then `python engine/table.py --campaign <slug>`.

Never read the generated scenario, NPC secrets or `## Author notes` in this conversation.
