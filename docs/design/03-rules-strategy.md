# 03 — Rules Strategy (do we need the rulebooks?)

## Short answer: no purchase/scan needed

Three layers cover us:

1. **Model knowledge.** D&D 5e (2014) is extremely well represented in Claude's training:
   core mechanics, classes, spells, SRD monsters, conditions, combat flow. For live play
   this is 95% of what's needed.
2. **The SRD (System Reference Document).** Wizards of the Coast publishes SRD 5.1 (2014
   rules) and SRD 5.2 (2024 rules) under Creative Commons CC-BY-4.0. It's a free, legal
   reference containing the core rules, ~300 monsters, and all core spells. If we ever
   want verbatim text locally, we can download it — no rulebook copies required.
3. **Local condensed rule sheets (`rules/`).** Small files the GM reads on demand. These
   exist not because the model lacks the rules, but to (a) pin down *our table's*
   interpretations so rulings are consistent across sessions, and (b) make hot-path
   lookups cheap. Planned sheets:
   - `checks-and-dcs.md` — DC ladder, advantage/disadvantage, group checks, contests
   - `perception.md` — passive Perception, hiding, when to roll vs. volunteer info
   - `combat-basics.md` — turn structure, common actions, cover, conditions cheat table
   - `rests-and-recovery.md` — short/long rests, HP, exhaustion
   - `house-rules.md` — anything we decide to do differently

## Edition decision needed

Default assumption: **2014 5e rules** (the classic, best-covered ruleset). If you're
playing with the 2024 revised rules, say so — mostly it changes some class features and
a few action names; the architecture is identical.

## What full books would add (only if you own them)

Non-SRD subclasses, feats, and adventure-specific content. If a player wants, say, a
non-SRD subclass, the clean move is: you summarize its features into that PC's file
(personal-use notes of content you own) — the PC file format already has a
`## Features & abilities` section for exactly this. Same for non-SRD monsters in
scenario files. No wholesale book ingestion needed.

## Legal note

SRD content: CC-BY-4.0, fine to store in-repo with attribution. Non-SRD text: keep to
short personal-play summaries in your own files, don't republish the repo publicly with
that content included.
