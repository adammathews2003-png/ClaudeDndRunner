# Feats (5e, 2014 rules) — index

An index for character creation and level-up (docs/build/plan.md → Phase 18): every
published 5e feat with its source, prerequisite and a terse mechanical summary, plus
machine-readable **grants** for the parts that change a PC file (ability scores,
proficiencies, languages, saves, expertise). Only **Grappler** is in the SRD 5.1; the rest
are non-SRD. This file holds names and facts, not rules text: the GM summarises a feat's
full effect from model knowledge (or the player's book) into `## Features & abilities`.

**Columns.** `asi`: the ability increase (`str|dex` = pick one, `any` = any one, `—` none).
`grants` tokens (Phase 18 `feat-grants`): `skill:N` / `tool:N` / `language:N` / `weapon:N` /
`expertise:N` = choose N; `skill|tool:N` = N picks from either; `skill:a|b` = one of those;
`tool:<name>`, `armor:<kind>`, `weapon:<kind>`, `language:<name>` = fixed; `save:asi` = save
proficiency in the ability raised. Rows marked **[U]** are unofficial (Tal'Dorei Campaign
Setting, first edition). `4th` = 4th level or higher.

**Campaign fit.** Feats tied to a setting (Dragonlance, Planescape, Eberron, Strixhaven, Plane
Shift) need that setting or the GM's yes; the source says which. The source page notes the
Plane Shift feats were lightly playtested.

| feat | source | prereq | asi | grants | summary |
|------|--------|--------|-----|--------|---------|
| Aberrant Dragonmark | WGtE 112; ERtLW 52 | no other dragonmark | con | — | sorcerer cantrip + 1st-level sorcerer spell 1/rest; random flaw |
| Actor | PHB 165 | — | cha | — | advantage impersonating (Deception/Performance); mimic voices |
| Adept of the Black Robes | DSDQ 31 | 4th; Initiate of High Sorcery (Nuitari) | — | — | 2nd-level enchantment/necromancy spell 1/LR; hit dice into damage |
| Adept of the Red Robes | DSDQ 32 | 4th; Initiate of High Sorcery (Lunitari) | — | — | 2nd-level illusion/transmutation spell 1/LR; PB/LR turn a d20 of 9 or less into 10 |
| Adept of the White Robes | DSDQ 32 | 4th; Initiate of High Sorcery (Solinari) | — | — | 2nd-level abjuration/divination spell 1/LR; reaction ward from spell slots |
| Agent of Order | SatOP 10 | 4th; Scion of the Outer Planes (lawful) | any | — | PB/LR +1d8 force and a restrain attempt on hit |
| Alert | PHB 165 | — | — | — | +5 initiative; can't be surprised; unseen attackers gain no advantage |
| Artificer Initiate | TCoE 79 | — | — | tool:artisan:1 | artificer cantrip + 1st-level artificer spell 1/LR |
| Athlete | PHB 165 | — | str\|dex | — | stand from prone with 5 ft; climbing costs no extra; running jumps after 5 ft |
| Baleful Scion | SatOP 10 | 4th; Scion of the Outer Planes (evil) | any | — | PB/LR extra necrotic damage on hit and heal that much |
| Bountiful Luck | XGtE 73 | halfling | — | — | reaction: an ally within 30 ft rerolls a natural 1 |
| Cartomancer | BoMT 49 | 4th; spellcasting | — | — | prestidigitation; store a 1-action spell in a card 1/LR |
| Charger | PHB 165 | — | — | — | after Dash, bonus-action attack (+5 damage) or 10 ft shove |
| Chef | TCoE 79 | — | con\|wis | tool:cook's utensils | short-rest meal heals extra; treats give temp HP |
| Cohort of Chaos | SatOP 10 | 4th; Scion of the Outer Planes (chaotic) | any | — | chaos effect (d4) on a natural 1 or 20 |
| Crossbow Expert | PHB 165 | — | — | — | ignore loading; no disadvantage in melee range; hand crossbow bonus attack |
| Cruel [U] | TDCS 108 | — | — | — | PB cruelty points/LR: +1d6 damage, temp HP on crit, advantage to intimidate |
| Crusher | TCoE 79 | — | str\|con | — | bludgeoning hit moves target 5 ft; crit gives allies advantage on it |
| Defensive Duelist | PHB 165 | DEX 13 | — | — | reaction: +PB AC against one melee hit while wielding a finesse weapon |
| Divinely Favored | DSDQ 32 | 4th; Dragonlance | — | — | cleric cantrip, augury and an alignment spell, each 1/LR |
| Dragon Fear | XGtE 74 | dragonborn | str\|con\|cha | — | spend breath weapon to frighten (WIS save) |
| Dragon Hide | XGtE 74 | dragonborn | str\|con\|cha | — | unarmored AC 13 + DEX; 1d4 slashing claws |
| Drow High Magic | XGtE 74 | drow | — | — | detect magic at will; levitate and dispel magic 1/LR |
| Dual-Focused [U] | TDCS 108 | can cast a spell | — | — | concentrate on two spells; CON saves for each |
| Dual Wielder | PHB 165 | — | — | — | +1 AC with two weapons; non-light weapons; draw or stow two |
| Dungeon Delver | PHB 166 | — | — | — | advantage to find secret doors and traps, on trap saves; trap damage resistance |
| Durable | PHB 166 | — | con | — | hit-die healing at least twice CON mod |
| Dwarven Fortitude | XGtE 74 | dwarf | con | — | Dodge lets you spend a hit die to heal |
| Elemental Adept | PHB 166 | spellcasting | — | — | pick an element: ignore resistance; 1s on its damage dice count as 2 |
| Eldritch Adept | TCoE 79 | spellcasting or Pact Magic | — | — | one eldritch invocation, swappable on level-up |
| Elven Accuracy | XGtE 74 | elf or half-elf | dex\|int\|wis\|cha | — | reroll one die when attacking with advantage (DEX/INT/WIS/CHA) |
| Ember of the Fire Giant | GotG 17 | 4th; Strike of the Giants (fire) | str\|con\|wis | — | fire resistance; PB/LR burst (DEX save, blinds) |
| Fade Away | XGtE 74 | gnome | dex\|int | — | turn invisible after taking damage, 1/rest |
| Fey Teleportation | XGtE 74 | high elf | int\|cha | language:sylvan | misty step 1/rest |
| Fey Touched | TCoE 79 | — | int\|wis\|cha | — | misty step + a 1st-level divination/enchantment spell, each 1/LR |
| Fighting Initiate | TCoE 80 | martial weapon proficiency | — | — | one fighter fighting style, swappable at an ASI |
| Flames of Phlegethos | XGtE 74 | tiefling | int\|cha | — | reroll 1s on fire damage; flames after casting a fire spell |
| Flash Recall [U] | TDCS 109 | prepares spells | — | — | swap one prepared spell, 1/rest |
| Fury of the Frost Giant | GotG 17 | 4th; Strike of the Giants (frost) | str\|con\|wis | — | cold resistance; PB/LR reaction frost (CON save, slows) |
| Gambler [U] | TDCS 109 | — | cha | tool:gaming set:2 | advantage on some Deception/Persuasion; reroll carousing |
| Gift of the Chromatic Dragon | FTD 17 | — | — | — | 1/LR +1d4 elemental damage weapon for a minute; PB/LR reaction resistance |
| Gift of the Gem Dragon | FTD 17 | — | int\|wis\|cha | — | PB/LR reaction: 2d8 force and push (STR save) |
| Gift of the Metallic Dragon | FTD 17 | — | — | — | cure wounds 1/LR; PB/LR reaction +PB AC to an ally or you |
| Grappler (SRD) | PHB 167 | STR 13 | — | — | advantage attacking a creature you grapple; pin to restrain both |
| Great Weapon Master | PHB 167 | — | — | — | bonus attack after a crit or kill; −5 to hit for +10 damage (heavy) |
| Guile of the Cloud Giant | GotG 18 | 4th; Strike of the Giants (cloud) | str\|con\|cha | — | PB/LR reaction: resist the hit and teleport 30 ft |
| Gunner | TCoE 80 | — | dex | weapon:firearms | ignore loading; no disadvantage in melee range |
| Healer | PHB 167 | — | — | — | healer's kit stabilises to 1 HP; kit heals 1d6+4 + max HD, once per creature per rest |
| Heavily Armored | PHB 167 | medium armor proficiency | str | armor:heavy | — |
| Heavy Armor Master | PHB 167 | heavy armor proficiency | str | — | −3 nonmagical B/P/S damage in heavy armor |
| Infernal Constitution | XGtE 75 | tiefling | con | — | cold and poison resistance; advantage against poison |
| Initiate of High Sorcery | DSDQ 32 | Dragonlance; sorcerer/wizard or Mage of High Sorcery background | — | — | wizard cantrip + two moon-chosen 1st-level spells, 1/LR each |
| Inspiring Leader | PHB 167 | CHA 13 | — | — | 10-minute speech: up to 6 gain level + CHA mod temp HP |
| Keenness of the Stone Giant | GotG 18 | 4th; Strike of the Giants (stone) | str\|con\|wis | — | darkvision 60 ft; PB/LR thrown rock (1d10 force, prone) |
| Keen Mind | PHB 167 | — | int | — | always know north and the hour; recall the past month |
| Knight of the Crown | DSDQ 32 | 4th; Squire of Solamnia | str\|dex\|con | — | PB/LR an ally attacks with +1d8 |
| Knight of the Rose | DSDQ 33 | 4th; Squire of Solamnia | con\|wis\|cha | — | PB/LR temp HP to an ally |
| Knight of the Sword | DSDQ 33 | 4th; Squire of Solamnia | int\|wis\|cha | — | PB/LR frighten on hit (WIS save) |
| Lightly Armored | PHB 167 | — | str\|dex | armor:light | — |
| Linguist | PHB 167 | — | int | language:3 | create written ciphers |
| Lucky | PHB 167 | — | — | — | 3 luck points/LR: reroll a d20 of yours or one against you |
| Mage Slayer | PHB 168 | — | — | — | reaction attack on a caster in reach; concentration saves vs your hits at disadvantage; advantage on saves vs adjacent casters |
| Magic Initiate | PHB 168 | — | — | — | pick a class: 2 cantrips + one 1st-level spell 1/LR |
| Martial Adept | PHB 168 | — | — | — | 2 Battle Master maneuvers; one d6 superiority die per short rest |
| Medium Armor Master | PHB 168 | medium armor proficiency | — | — | no Stealth disadvantage in medium armor; DEX up to +3 |
| Mending Affinity [U] | TDCS 109 | — | con | — | extra healing from kits and healing effects |
| Metamagic Adept | TCoE 80 | spellcasting or Pact Magic | — | — | 2 metamagic options; 2 sorcery points/LR |
| Mobile | PHB 168 | — | — | — | +10 speed; Dash ignores difficult terrain; no opportunity attacks from creatures you attacked |
| Moderately Armored | PHB 168 | light armor proficiency | str\|dex | armor:medium, armor:shield | — |
| Mounted Combat | PHB 168 | — | — | — | advantage on smaller unmounted foes; redirect hits from your mount; mount evades on DEX saves |
| Mystic Conflux [U] | TDCS 109 | — | — | — | advantage on Arcana to identify magic items; attune 4 items |
| Observant | PHB 168 | — | int\|wis | — | read lips; +5 passive Perception and Investigation |
| Orcish Fury | XGtE 75 | half-orc | str\|con | — | extra weapon die 1/rest; attack after Relentless Endurance |
| Outlands Envoy | SatOP 10 | 4th; Scion of the Outer Planes (Outlands) | any | — | misty step and tongues 1/LR |
| Piercer | TCoE 80 | — | str\|dex | — | reroll one piercing damage die per turn; extra die on piercing crit |
| Planar Wanderer | SatOP 11 | 4th; Scion of the Outer Planes | — | — | choose acid/cold/fire resistance each LR; sense and force portals |
| Poisoner | TCoE 80 | — | — | tool:poisoner's kit | ignore poison resistance; bonus action to coat; brew potent poison |
| Polearm Master | PHB 168 | — | — | — | bonus 1d4 butt-end attack; opportunity attacks when foes enter reach |
| Prodigy | XGtE 75 | half-elf, half-orc or human | — | skill:1, tool:1, language:1, expertise:1 | — |
| Quicksmithing | PSK 13 | INT 13 | — | tool:artisan:1 | two 1st-level ritual spells as devices |
| Rapid Drinker [U] | TDCS 109 | — | — | — | potion as a bonus action; advantage on saves vs ingested poison |
| Resilient | PHB 168 | — | any | save:asi | — |
| Revenant Blade | WGtE 74; ERtLW 22 | elf | str\|dex | — | double-bladed scimitar: +1 AC, finesse |
| Righteous Heritor | SatOP 11 | 4th; Scion of the Outer Planes (good) | any | — | PB/LR reaction: reduce damage by 1d10 + PB |
| Ritual Caster | PHB 169 | INT or WIS 13 | — | — | ritual book of a class with two 1st-level rituals; copy more |
| Rune Shaper | GotG 18 | spellcasting or Rune Carver background | — | — | comprehend languages 1/LR; inscribe runes |
| Savage Attacker | PHB 169 | — | — | — | reroll melee weapon damage once per turn |
| Scion of the Outer Planes | SatOP 12 | Planescape | — | — | damage resistance + a cantrip by plane |
| Second Chance | XGtE 75 | halfling | dex\|con\|cha | — | reaction: an attacker rerolls, once per initiative or rest |
| Sentinel | PHB 169 | — | — | — | opportunity hit stops movement; Disengage doesn't help; punish attacks on allies |
| Servo Crafting | PSK 13 | INT 13 | — | — | find familiar as a mechanical servo |
| Shadow Touched | TCoE 80 | — | int\|wis\|cha | — | invisibility + a 1st-level illusion/necromancy spell, each 1/LR |
| Sharpshooter | PHB 170 | — | — | — | no long-range disadvantage; ignore half and three-quarters cover; −5 to hit for +10 damage |
| Shield Master | PHB 170 | — | — | — | bonus-action shield shove; shield AC to DEX saves; take no damage on a successful half-damage DEX save |
| Skilled | PHB 170 | — | — | skill\|tool:3 | — |
| Skill Expert | TCoE 80 | — | any | skill:1, expertise:1 | — |
| Skulker | PHB 170 | — | — | — | hide when lightly obscured; a miss doesn't reveal you; dim light doesn't hinder Perception |
| Slasher | TCoE 81 | — | str\|dex | — | slashing hit slows 10 ft; crit gives the target disadvantage on attacks |
| Soul of the Storm Giant | GotG 19 | 4th; Strike of the Giants (storm) | str\|wis\|cha | — | PB/LR aura: lightning and thunder resistance; slows foes (STR save) |
| Spelldriver [U] | TDCS 109 | level 8 | — | — | cast two leveled spells in a turn (only one above 2nd) |
| Spell Sniper | PHB 170 | spellcasting | — | — | an attack cantrip; double spell range; ignore some cover |
| Squat Nimbleness | XGtE 75 | dwarf or a Small race | str\|dex | skill:acrobatics\|athletics | +5 speed; advantage to escape grapples |
| Squire of Solamnia | DSDQ 34 | Dragonlance; fighter/paladin or Knight of Solamnia background | — | — | mount/dismount for 5 ft; PB/LR advantage and +1d8 damage |
| Strike of the Giants | GotG 19 | martial weapon proficiency or Giant Foundling background | — | — | one giant strike: PB/LR extra damage and an effect |
| Strixhaven Initiate | SCoC 36 | — | — | — | pick a college: 2 cantrips + one 1st-level spell 1/LR |
| Strixhaven Mascot | SCoC 37 | 4th; Strixhaven Initiate | — | — | find familiar as a mascot; swap places 1/rest |
| Svirfneblin Magic | EEPC 7 | deep gnome | — | — | nondetection at will; blindness/deafness, blur and disguise self 1/LR |
| Tavern Brawler | PHB 170 | — | str\|con | weapon:improvised | unarmed d4; bonus-action grapple after a hit |
| Telekinetic | TCoE 81 | — | int\|wis\|cha | — | invisible mage hand; bonus-action telekinetic shove |
| Telepathic | TCoE 81 | — | int\|wis\|cha | — | telepathy 60 ft; detect thoughts 1/LR |
| Thrown Arms Master [U] | TDCS 109 | — | str\|dex | — | better thrown range; light thrown weapons return |
| Tough | PHB 170 | — | — | — | +2 max HP per level |
| Vampiric Exultation | PSI 14 | Ixalan vampire | — | — | fly 30 ft for 10 minutes, 1/rest |
| Vigor of the Hill Giant | GotG 19 | 4th; Strike of the Giants (hill) | str\|con\|wis | — | resist being pushed or knocked prone; extra hit-die healing |
| War Caster | PHB 170 | spellcasting | — | — | advantage on concentration saves; somatic with full hands; spell as an opportunity attack |
| Weapon Master | PHB 170 | — | str\|dex | weapon:4 | — |
| Wood Elf Magic | XGtE 75 | wood elf | — | — | druid cantrip; longstrider and pass without trace 1/LR |

**Sources:** PHB Player's Handbook · XGtE Xanathar's Guide to Everything · TCoE Tasha's
Cauldron of Everything · FTD Fizban's Treasury of Dragons · DSDQ Dragonlance: Shadow of the
Dragon Queen · SatOP Sigil and the Outlands · GotG Bigby Presents: Glory of the Giants ·
SCoC Strixhaven: A Curriculum of Chaos · BoMT The Book of Many Things · WGtE Wayfinder's
Guide to Eberron · ERtLW Eberron: Rising from the Last War · EEPC Elemental Evil Player's
Companion · PSK Plane Shift: Kaladesh · PSI Plane Shift: Ixalan · TDCS Tal'Dorei Campaign
Setting.

## Credits

The list of feats, sources, page numbers and prerequisites comes from **"The Complete Feat:
All Dungeons & Dragons 5th Edition Feats"** by **Thomas Knight** at **Cheeky Kokako**
(https://www.cheekykokako.com/games/the-complete-feat-all-dd-5e-feats/), retrieved
2026-10-11. The summaries and grant tags are our own condensed wording, not the site's
text or the books'. The feats themselves belong to **Wizards of the Coast** (Tal'Dorei
feats: **Green Ronin Publishing / Critical Role**). Only Grappler is SRD 5.1 (CC-BY-4.0).
Collected here with credit for non-commercial play; if you're a rights holder and want
this out, open an issue and it will be removed.
