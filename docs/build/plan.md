# Implementation plan — Claude GM tools, client and skills

How to use this file: pick the next unticked phase in `README.md`, open a fresh session,
and give it only that phase (plus Phase 0, which every phase assumes). Each phase lists
what to read, what to build, the contracts later phases depend on, how to verify, and the
guards. Build by copying what the planning docs specify, cited by file and line; where a
phase has to decide something the docs leave open, the decision is written here so every
session makes the same one.

Conventions used throughout:
- Paths are relative to `dnd-adventure/`, which is the git repo root (branch `main`,
  remote `origin` = github.com/adammathews2003-png/ClaudeDndRunner) since 2026-10-05.
- `04:68-130` means `docs/design/04-file-formats.md` lines 68–130 as of commit `0bbce3d`.
- Run tools as `python engine/gm.py …` from `dnd-adventure/` (Python 3.11.9 is installed;
  both `python` and `py` resolve to it).
- Every phase ends with its tests passing and a commit. Commit messages end with the
  attribution line the session is given.

---

## Phase 0 — Documentation discovery (consolidated; read before any phase)

### 0.1 Sources that govern the build
| Doc | What it owns | Read when |
|---|---|---|
| `docs/design/06-tools-spec.md` (773 lines) | every command's syntax, output, reads/writes; lib layout L60-81; build order L740-755; prohibitions | every tools phase |
| `docs/design/04-file-formats.md` (608 lines) | every file's frontmatter, sections, table header rows; terrain/route/constraint vocabularies; travel-time math; tool-owned files L600-608 | Phases 1, 4, 6, 7 |
| `docs/design/02-gm-agent-design.md` (548 lines) | skills table L8-20; session start L33-50; intake L52-108; level-up L110-140; dice L167-176; behind the screen L178-228; overrule L230-305; spoilers L307-372; spatial L397-486; open world L488-529; timeliness L538-548 | Phases 2, 5, 6, 9 |
| `docs/design/01-architecture.md` (187 lines) | directory layout + `campaigns/.active` L10-34; turn loop L55-79; scene tempo L84-104; world geometry L106-148; session lifecycle L150-160; secrets L162-187 | Phases 3, 4, 9 |
| `docs/design/05-hard-problems.md` | rules tools must enforce: #1 files win L6-15, #2 real RNG L17-22, #4 journal/undo + git L35-41, #5 lint L43-52, #6 stubs L54-60, #7 time L62-70, #8 compaction hook L72-77, #14 permissions L118-125 | Phases 1, 2, 7 |
| `rules/house-rules.md` | ties-go-to-PC L24-32; HP max-or-roll L13-21; dice L7-10; overrules L35-38 | Phases 2, 6 |
| `rules/combat-basics.md` | grid model L29-42 (walls at L38-41); movement L43-51; areas L52-85 | Phase 4 |
| `engine/space.py` (542 lines) | the one built tool; its parsing is what `md.py` must replace | Phases 1, 4, 5 |
| `campaigns/poc/` | the fixture campaign (copied for tests); see 0.5 | all |

### 0.2 Hard constraints (from 06, verbatim or near)
- Python 3 **stdlib only**, no install step (06:44-46). No PyYAML (06:759). The game
  tools never import the Agent SDK; only `table.py` does (06:76, 06:648).
- One entry point `python engine/gm.py <command>`; `space.py` stays standalone and is also
  reachable as `gm.py space …` (06:27-29).
- `do "a; b; c"` runs left to right; a failure stops the batch, earlier steps stay
  applied and are listed (06:30-32). Writes are atomic: temp file + rename (06:33-34).
- Every mutation auto-logs a delta line into the open turn block (06:35-36, 06:156-168).
- Output is short bracket lines; `--json` only on request (06:37-43). `--seed N` makes
  any command deterministic; RNG is `random.SystemRandom` otherwise (06:44-45).
- Every command < 200 ms (06:49).
- `campaigns/.active` holds the active campaign folder name; `--campaign <dir>` overrides
  (06:51-53). Name resolution order: Combat rows → Stage/On stage → `pcs/` → `npcs/`;
  ambiguous → error listing candidates (06:55-58).
- Tools never decide whether a check is needed, what a DC is, or what an NPC wants
  (06:47-48, 06:733-738).
- Frontmatter parsing contract (04:7-11, 06:83-92): `key: scalar`, `key: [a, b]`,
  `key: {a: 1, b: 2}` (one level), `# comments`, quoted strings. No nested blocks, no
  multi-line values. Writers preserve comments, key order and untouched lines
  byte-for-byte. Tables are read by header name.
- Frontmatter is player-safe (04:13-16); tools print it freely.
- **Line endings (decided here, not in the docs):** `git config core.autocrlf` is `true`
  and the working tree is mixed CRLF/LF. Readers use `open(encoding="utf-8")` +
  `splitlines()`; writers detect the file's existing newline (`\r\n` if the original
  contains one, else `\n`) and reuse it; new files use `\n`. Tests must pass on both.

### 0.3 File-format contracts (exact header rows; copy templates from 04)
| File | Template | Tables (header rows verbatim) |
|---|---|---|
| site | 04:68-130 | Layout: `\| id \| glyph \| feature \| from \| to \| effect \|`; optional Routes: `\| id \| from \| to \| via \| kind \| access \| time \| notes \|` |
| area | 04:139-189 | Places: `\| id \| glyph \| feature \| at \| from \| to \| effect \| ref \| source \|`; Routes as above; `## Frame` line `origin (0,0,0) = … · +x east · +y north · +z up · ft` |
| world | 04:234-271 | Places/Routes as area (unit `mi`); Known, not placed: `\| id \| feature \| constraints \| source \| notes \|`; Frontier: `\| id \| from \| heading \| known as \| said to lead to \| source \|` (POC adds `notes`) |
| NPC | 04:312-347 | `## Movements` lines `- HH:MM–HH:MM → site[/area] (note)`; frontmatter keys: name, location, role, faction, attitude-to-party, statblock, default-goal, status |
| PC | 04:358-424 | Attacks `\| name \| hit \| damage \| range \| notes \|`; Resources `\| resource \| current \| max \| recovers \|`; Spells `\| spell \| level \| source \| notes \|`; 26 frontmatter keys in the order shown at 04:358-384 |
| scenario | 04:428-457 | `## Beats & triggers` lines `- WHEN … → …` and `- CLOCK Day N HH:MM: …` |
| state | 04:461-491 | frontmatter campaign, in-game-datetime, party-location, scene, light, in-session, dice-mode; sections Summary, On stage (bullets), Watch for, Clocks, `## Tempo: calm`, `## Combat` |
| Stage table | 04:497-505 | `\| init \| name \| glyph \| side \| pos \| size \| ref \| adj \| intent \|` under `## Tempo: tense` / `### Stage` |
| Combat block | 04:509-532 | heading `## Combat — round N · up: X`; `Map:` and `Bounds:` lines; Terrain (Layout columns); Combatants `\| init \| name \| glyph \| side \| pos \| size \| ref \| HP \| AC \| conditions \| notes \|`; `### Moves log` lines |
| table-rules | 04:545-554 | `\| id \| rule \| key \| scope \| since \| status \|` |
| spoilers | 04:566-573 | `\| when \| level \| depth \| question \| revealed \|` |
| session log | 04:582-587 | `[turn N] summary` then `  - delta` lines; `(GM)` tag; `[overrule]`, `[spoilers]` lines; `Erratum:` lines in history |
| tool-owned | 04:600-608 | `campaigns/.active`; `<campaign>/.gm/{journal/, brief-hash, drafts/, session-id, client.log}`; `tables/<slug>.md` `\| roll \| result \|` |

Vocabularies: terrain `effect` keywords 04:297-305 (difficult, stairs, ramp, wall, door
+ closed/locked/barred, hazard or damage dice, secret, leading `exit →`); route `kind`
factors 04:176-178; `access` 04:179-180; constraints 04:221-232; `source` 04:213-220;
travel-time math 04:279-287; `location: site[/area]` 04:289-293; `at`/`from`/`to`
04:44-50 and 04:160-163.

### 0.4 Command inventory (where each is specified in 06)
roll 96-109 · atk/save/check/contest 111-134 · mutations table 137-151 (group split
153-154) · turn blocks 156-168 · rule/retcon/overrule-undo 170-217 (keys 194-204) ·
journal/undo 219-222 · brief + hooks 224-264 · permissions 266-269 · scene enter 273-301
· tempo/pos/intent 303-314 · combat start/next/moves/reframe/end 316-345 · srd 347-355 ·
clock advance 359-378 · travel 380-393 · rest 395-399 · lint 401-448 · session archive
450-456 · stub 458-464 · where 466-476 · world 478-506 (`world init` 505) · space.py map
--place 508-516 · trace/odds/spoil 518-557 · pc 559-630 · table.py 632-713 · format
changes 715-731 · build order 740-755 · decided questions 757-773.

### 0.5 Repo state at the start (verified 2026-10-04)
- Exists: `docs/design/`, `rules/` (4 sheets), `campaigns/poc/` (locations ×5, npcs ×3, pcs ×3 incl.
  `_template.md`, scenario ×1, `sessions/{session-current.md, spoilers.md, history/}`,
  `state/{current.md, table-rules.md}`), `engine/space.py`, `README.md`.
- Does **not** exist yet: `engine/lib/`, `engine/gm.py`, `engine/table.py`, `engine/tests/`,
  `data/`, `.claude/` (no settings.json, no skills), `campaigns/.active`, any `.gm/`.
- Repo root `.gitignore` already ignores `__pycache__/`, `*.pyc`, `.gm/`.
- `campaigns/poc/state/current.md` has `in-session: false`, `Tempo: calm`, `## Combat` =
  `(not in combat)`; `space.py` therefore finds nothing to parse there (fine).

### 0.6 External facts (verified against official docs on 2026-10-04)
**Hooks** (https://code.claude.com/docs/en/hooks.md): config is nested per event →
matcher group → hook entries. For `UserPromptSubmit` and `SessionStart`, **plain-text
stdout is added to Claude's context** (no JSON needed); JSON with
`hookSpecificOutput.additionalContext` is the alternative. Exit 0 = success; exit 2 =
block; stdout/additionalContext capped at 10,000 chars. Stdin JSON carries
`session_id`, `cwd`, `hook_event_name`, `permission_mode`; `UserPromptSubmit` adds
`prompt`; `SessionStart` adds `source` ∈ `startup | resume | clear | compact | fork`
and fires on compaction. Default timeouts: UserPromptSubmit 30 s, SessionStart 600 s.
A UserPromptSubmit hook that times out has its output discarded (prompt still goes
through). The exact `settings.json` to write is in Phase 3.

**Permissions** (https://code.claude.com/docs/en/permissions.md): `Bash(python engine/gm.py:*)`
and `Bash(python engine/gm.py *)` are equivalent prefix rules; project file is
`.claude/settings.json`, per-developer overrides in `.claude/settings.local.json`.

**Skills** (https://code.claude.com/docs/en/skills.md): `.claude/skills/<name>/SKILL.md`
with YAML frontmatter `name`, `description`, optional `disable-model-invocation: true`
(user-only), `user-invocable: false` (model-only), `allowed-tools`, `arguments`,
`model`, `context: fork`. `$ARGUMENTS` = all args; `$0`, `$1` positional.

**Agent SDK, Python** (https://code.claude.com/docs/en/agent-sdk/python.md): package
`claude-agent-sdk` (`pip install claude-agent-sdk`, Python ≥ 3.10). `ClaudeSDKClient(
options=ClaudeAgentOptions(...))` for multi-turn: `await client.query(text)` then
`async for message in client.receive_response()`. Message types from
`claude_agent_sdk.types`: `AssistantMessage` (`.content` of `TextBlock(.text)` /
`ToolUseBlock(.name, .input)`), `ResultMessage` (`.total_cost_usd`, `.num_turns`),
`UserMessage`. Options fields: `cwd`, `allowed_tools`, `permission_mode`
(`default | acceptEdits | plan | auto | dontAsk | bypassPermissions`), `system_prompt`,
`setting_sources=["project"]` (loads `.claude/settings.json` + skills), `hooks`,
`model`, `max_turns`. **Not verified:** that project `SessionStart` hooks fire inside an
SDK session after compaction, and the exact callback for logging permission denials.
Both are Phase 5 build-time checks (06:707-713 already lists them).

**Headless CLI fallback** (https://code.claude.com/docs/en/cli-reference.md): `claude -p
--output-format stream-json [--input-format stream-json] --resume <id> --allowedTools
"…"`. Use only if the SDK path fails Phase 5's checks.

**SRD data**: 5e-bits `5e-database` on GitHub, CC-BY-4.0 (06:348-349, 06:628-630). The
repo's 2014 files live under `src/2014/` named `5e-SRD-<Thing>.json` (Monsters, Spells,
Conditions, Classes, Subclasses, Levels, Features, Races, Subraces, Traits, Equipment,
Backgrounds). **List the directory before downloading** (Phase 4); don't hard-code
paths you haven't seen.

### 0.7 Spec gaps to close in Phase 1 (small doc edits, so later phases don't trip)
1. 06:478 heading lists `world show | add | place | lead | reveal | import` but
   `world init` (06:505) is missing from it. Add it.
2. 06:89 still says "(Alternative: depend on PyYAML — see Open questions.)" though
   06:759 decided against it. Delete the sentence.
3. 04:7-11 parsing contract says nothing about line endings. Add the 0.2 CRLF rule.
4. 04:176-178 `kind` factors omit `trapdoor`, `stairs`, `gate`, `ladder` (used in the
   POC inn Routes). Add them at factor 1.
5. `engine/space.py` has no `secret` handling yet (04:303 requires it for
   `--player-view`). Phase 4/5 adds it; note it in the docstring until then.

### 0.8 Anti-patterns (grep for these at every verification step)
- `import yaml`, `import requests`, any non-stdlib import in `engine/` except
  `claude_agent_sdk` inside `table.py`.
- `random.random`/`random.randint` module-level calls (must go through `dice.py`'s
  `SystemRandom`/seeded instance).
- Direct `open(..., "w")` on a campaign file outside `md.py`'s atomic writer.
- A pairwise distance table anywhere (02:402-405); distances are derived.
- A tool that decides a DC, whether a beat fires, or an NPC's intent (06:47-48).
- Printing `scene enter`/`brief`/`srd`/full-map output into narration (02:205-207).
- `print()` of JSON without `--json`.

---

## Phase 1 — Foundations (build step 2a.1)

**Goal:** the shared libraries every command uses, the `gm.py` entry point with `do`,
the test harness with a fixture copy of `campaigns/poc/`, and the spec nits from 0.7.

**Read first:** 06:25-58 (principles), 06:60-92 (layout + md.py contract), 06:156-168
(turn blocks), 06:219-222 (journal), 06:754-755 (tests), 04:7-21, 04:600-608,
05:6-15, 05:35-41, 05:62-70; `engine/space.py` L29-55 (`parse_point`, `table_rows`: the
behaviour `md.py` must reproduce) and L117-136 (`State.__init__`).

**Build:**
1. `engine/lib/__init__.py` (empty) and `engine/lib/md.py` with this contract:
   - `load(path) -> Doc`; `Doc.path`, `Doc.newline` (`"\r\n"` or `"\n"`),
     `Doc.front: dict` (insertion-ordered; values parsed per 04:7-11: int/float/bool/
     `None` for empty, `str`, `list`, one-level `dict`; quoted strings unquoted),
     `Doc.front_comments: dict[key, str]` (the trailing `# …` kept verbatim),
     `Doc.body: list[str]` (lines after the closing `---`).
   - `Doc.set_front(key, value)` rewrites only that line (preserving its comment and
     position; a new key appends before `---`), `Doc.save()` atomic (write
     `path + ".tmp"`, `os.replace`), using `Doc.newline`.
   - `Doc.section(heading) -> (start, end)` line range for a `## `/`### ` heading
     (prefix match on the heading text, so `## Tempo: tense` matches `## Tempo`).
   - `Doc.table(heading) -> Table | None`: first table under that heading.
     `Table.header: list[str]` (original case), `Table.rows: list[dict]` (keys
     lowercased, values stripped), `Table.set(i, col, value)`, `Table.append(row)`,
     `Table.remove(i)`, all rewriting the body lines in place with the column widths
     of the header row (pad, never truncate).
   - `Doc.append_line(heading, text)` for bullet sections (History, Journal, Notes).
   - `parse_point(text)` moved here verbatim from `space.py` L29-35 (space.py keeps a
     thin import in Phase 4).
2. `engine/lib/campaign.py`: `root()` (reads `campaigns/.active`, honours
   `--campaign`), `path(kind, slug)` for `pcs/npcs/locations/scenarios/tables`,
   `pcs()`, `npcs()`, `locations()` (loaded `Doc`s), `resolve(name, state=None)`
   implementing the lookup order 06:55-58 and raising `Ambiguous(candidates)`,
   `slugify(name)`, `who_is_at(site_or_area)` by grepping `location:` (04:307-308).
3. `engine/lib/journal.py`: `Batch` context manager that snapshots before-images of every
   file a command opens for writing into `<campaign>/.gm/journal/<NNNN>/` with a
   `manifest.json` (`files`, `command line`, `turn`, `overrule: bool`), keeps the last
   50, and exposes `touched` (for lint layer 2, 06:431-434). `undo()` restores the
   latest batch and appends `undo turn N step M` to the log (06:221-222). A
   `log_delta(text, gm=False)` writer that opens `[turn N]` on the first delta after a
   `log` and appends `  - ` lines (06:156-168; `(GM)` prefix when `gm=True`).
4. `engine/lib/gametime.py`: `parse("Day 1 19:30") -> (day:int, minute:int)`,
   `fmt(day, minute)`, `add(t, "+4h30m" | "+1d" | "to 06:00" | "to dawn")`, named times
   from 06:377-378, `period(t)` (dawn/morning/…/night for the brief line), and a
   `between(t, start, end)` helper for `## Movements` windows that may wrap midnight.
5. `engine/gm.py`: argparse with subcommands registered by the modules that exist
   (`space` forwards to `space.py`), global `--campaign`, `--seed`, `--json`; `do
   "<cmd>; <cmd>"` splits on `;`, runs each through the same dispatcher inside one
   `Batch`, stops on the first failure and prints which step failed and which earlier
   steps applied (06:30-32). Unknown commands print the usage line. Nothing else yet.
6. `engine/tests/`: `conftest.py`-free `unittest` layout (stdlib). `fixture.py` copies
   `campaigns/poc/` to a temp dir per test and points `campaigns/.active` at it. Tests for every md.py
   method against real POC files (round-trip a file unchanged byte-for-byte after
   `load`→`save`; `set_front` on a key with a comment keeps the comment; table edits
   keep widths; CRLF and LF inputs both round-trip), gametime arithmetic including
   midnight wrap, campaign resolution (`Kael`, `kael`, `ka` ok; `k` ambiguous), journal
   snapshot/undo, `do` stop-on-failure.
7. Write `campaigns/.active` containing `poc`.
8. Apply the doc edits in 0.7 items 1–4.

**Verify:** `python -m unittest discover engine/tests` green; `python engine/gm.py do
"nonexistent"` reports the failing step; `grep -rn "import yaml\|requests" engine/`
empty; `git diff --stat` on POC files after the round-trip tests is empty.

**Guards:** don't parse frontmatter with regex per key — parse once into `Doc.front`.
Don't rewrite whole files from parsed data (comments and spacing would be lost); edit
lines. No command logic in this phase beyond `do`.

---

## Phase 2 — Dice, outcomes, mutations, overrules (2a.2)

**Goal:** the per-turn commands: `roll`, `atk/save/check/contest`, the mutation table,
`log`, `undo`, and `rule/retcon/overrule-undo`.

**Read first:** 06:96-222 in full; 02:167-176 (dice policy); `rules/house-rules.md`
L7-10, L24-32; `rules/combat-basics.md` L20-27 (attacks, cover); 04:540-557
(table-rules); 04:358-424 (PC fields the commands read/write); 04:507-538 (combat rows
they mutate); 05:17-22.

**Build:**
1. `lib/dice.py`: grammar at 06:104-105 (`NdM`, `+/-` terms and more dice, `adv`,
   `dis`, `crit` doubles dice only, `kh/kl`, `x3`); `Roller(seed=None)` using
   `random.SystemRandom()` unless seeded; `roll(expr) -> Result(total, parts, text)`
   whose `text` matches the bracket formats at 06:97-102 exactly; `table:<slug>` reads
   `tables/<slug>.md` (`| roll | result |`, ranges `1-3`).
2. `lib/resolve.py`: the only place outcome rules live (06:123-127). Functions
   `attack(roll, bonus, ac, *, attacker_is_pc, cover)`, `save`, `check`, `contest`,
   each returning `(outcome, note)` where `note` names ties (`tie→PC`), nat 20/1, cover
   AC. Reads active table-rule keys (`crit-range`, `crit-damage`, `ties`, `flanking`,
   `death-saves`, `potion`, `dice-mode`, `encounters`; 06:194-204) from
   `state/table-rules.md` rows with `status` `active`. Ties-go-to-PC per house-rules
   L24-32: NPC roll = PC AC → miss; contest tie → PC; NPC check = PC passive → PC wins;
   PC roll = DC/AC → success.
3. `roll` command (06:96-109): `--secret` prints `SECRET` and logs a `(GM)` delta.
4. `atk`, `save`, `check`, `contest` (06:111-134): bonuses from the PC Attacks table /
   mods / skills, or the NPC `statblock:` → **until Phase 4 ships `srd`, NPC numbers
   come only from a `custom` block in the NPC file; `srd:` refs raise "srd not built
   yet"** (don't fake numbers). `--d20`/`--total` for the PC side; without them roll
   only if `dice-mode: gm-rolls-all`. `atk` applies damage unless `--no-apply`; range
   check via `space.py` when both have positions (06:133-134).
5. Mutations exactly as the table at 06:137-151: `hp` (clamp, temp HP, `+temp`), `dmg`
   (resistance/immunity note), `cond` (durations `3r`/`10m`), `move-npc` and
   `move-party` (validate `site[/area]` against `locations/` and the site's
   `## Areas`; drop from On stage when leaving), `attitude`, `item`, `coin`, `res`,
   `time` (alias; real `clock` arrives in Phase 7, so for now `time` only advances the
   frontmatter and reports nothing crossed), `log`. Group row split per 06:153-154.
   Each writes its delta line via `journal.log_delta`.
6. `rule add|end|list`, `retcon`, `overrule-undo` (06:170-217): rows in
   `state/table-rules.md` (04:545-554), `since` = `S<session> t<turn>`, newer-wins
   per key with the overridden rule reported, scope expiry hooks left as functions
   (`end_scope("scene"|"combat"|"session")`) for Phases 4 and 7 to call. Overrule
   batches are flagged in the journal manifest; `overrule-undo` refuses if a later batch
   touched the same files (06:185-188).

**Contracts for later phases:** `dice.Roller`, `resolve.*`, `rules.active_keys()`,
`mutations.hp(target, delta)` etc. callable from Python (combat/rest/pc reuse them).

**Verify:** seeded tests for every bracket format at 06:97-102 and 06:112-119 (string
equality); tie cases from house-rules L24-32 each have a test; `do "atk Veskar Kael
--seed 1; dmg Kael 3; log x"` produces a `[turn N]` block with three deltas in
`sessions/session-current.md`; `undo` restores the PC file byte-for-byte; `rule add
… --key crit-range=19` then a seeded `atk` that rolls 19 reports a crit; `grep -rn
"random\." engine/ | grep -v dice.py` is empty.

**Guards:** no outcome arithmetic outside `resolve.py`; no table-rule key not in
06:194-204 (lint later warns on unknown keys, 06:205-206); `--secret` output never
contains the number in the non-secret log line.

---

## Phase 3 — Brief, hooks, permissions (2a.3)

**Goal:** zero file reads per normal turn: `gm.py brief` and the two hooks.

**Read first:** 06:224-269; 05:72-77; 01:150-160; 02:538-548; 0.6 Hooks and
Permissions above.

**Build:**
1. `brief` (06:225-235): build the ≤ 20-line digest from `current.md` + the files it
   points to; line formats exactly as 06:227-234 (`[GM BRIEF] …`, `On stage:`, `Order:`
   (only when a Stage/Combat table exists), `Party:` (adds `· XP n/next` per PC while
   XP tracking is on), `Rules:`, `Watch:` + `Next
   clock:`, `Combat:`, `Log:`). `--long` adds the Summary and the last 5 turns of the
   session log plus spoiler count (06:555-557). Absent PCs show `(autopilot)`
   (06:625-626).
2. `--hook` mode (06:237-264): print nothing unless `in-session: true`; hash the brief
   minus the `Log:` line into `<campaign>/.gm/brief-hash` alongside a prompt counter;
   changed → full brief; unchanged → the one heartbeat line at 06:254; forced full on
   `SessionStart` (clear the hash), every 15 prompts, or when stdin JSON `prompt`
   starts with `!brief`. Read stdin JSON (`hook_event_name`, `source`, `prompt`); on
   `SessionStart` with any `source` run `--long`. Never exit non-zero from the hook
   (a failure must not block the prompt); on any exception print one line
   `[GM BRIEF] unavailable: <reason>`.
3. `.claude/settings.json` (project; create the directory):
   ```json
   {
     "permissions": {
       "allow": [
         "Bash(python engine/gm.py:*)",
         "Bash(python engine/space.py:*)",
         "Bash(py engine/gm.py:*)",
         "Bash(py engine/space.py:*)"
       ]
     },
     "hooks": {
       "UserPromptSubmit": [
         { "hooks": [ { "type": "command", "command": "python engine/gm.py brief --hook", "timeout": 10 } ] }
       ],
       "SessionStart": [
         { "matcher": "startup|resume|compact|clear",
           "hooks": [ { "type": "command", "command": "python engine/gm.py brief --hook --long", "timeout": 30 } ] }
       ]
     }
   }
   ```
   Working directory for hooks is the project dir Claude Code was started in; the plan
   assumes sessions start in `dnd-adventure/`. If the repo root is used instead, prefix
   `command` with `cd dnd-adventure &&` (check `cwd` from the stdin JSON at build time).
4. **Wacky Juice** (02 → Wacky Juice; 04 → Campaign file → Wacky Juice; 06 → `gm.py
   juice` and the brief's "Wacky Juice roll" bullet). Config readers in `lib/campaign.py`
   (`campaign.md`, falling back to `current.md`, with defaults `on` / 5 / 3); the roll in
   `brief --hook` on `UserPromptSubmit` only; `.gm/juice` state; `gm.py juice`
   subcommands; `do` consumes `pending` (logs `(GM) [juice] <npc>` unless the batch has
   `juice waive`). RNG goes through `lib/dice.py` so `--seed` makes tests deterministic.
5. **Check margins** (06 → atk/save/check/contest → Margin): `check`, `save` and
   `contest` lines end `— SUCCESS by N` / `— FAIL by N`. This is a small follow-up to
   Phase 2's `lib/resolve.py`; update its tests.

**Verify:** `python engine/gm.py brief` on the POC prints ≤ 20 lines matching the
06:227-234 shapes; piping `{"hook_event_name":"UserPromptSubmit","prompt":"hi"}` to
`brief --hook` prints nothing while `in-session: false`, the full brief once it's
`true`, and the heartbeat on the second identical call; a `SessionStart` JSON with
`"source":"compact"` prints the long form; a 200-ms timer around the hook. Then start a
real Claude Code session in `dnd-adventure/`, set `in-session: true`, and confirm the
brief appears as a system reminder (hooks debug log) and that `python engine/gm.py roll
1d20` runs without a permission prompt.
Juice: with `wacky-juice-value: 100` and an NPC on stage, the next `UserPromptSubmit`
hook prints a `Juice:` line (after both a full brief and a heartbeat); the next
`do` logs `(GM) [juice] <npc>`; the following 3 prompts never fire (cooldown); with
`value: 0`, `off`, no NPC on stage, only an unconscious NPC, or a prompt starting with
`/` or `!`, it never fires; `gm.py juice 10` rewrites the frontmatter and logs the public
line; the juice line doesn't change the brief hash. Margins: `check` on a fixed
`--d20` prints the right `by N` on both sides of the DC and on a tie.

**Guards:** the hook must never read the whole campaign (only `current.md` and the
files it names); never exit 2; never print the `Log:` line's content into the hash.

---

## Phase 4 — Geometry, scenes, combat, SRD (2a.4)

**Goal:** `lib/geo.py`; `scene enter` with derived Exits/Nearby; `tempo`/`pos`/
`intent`/`onstage` with named placement; `combat start/next/end`; `srd` with the data
download; `space.py` moved onto `md.py`, reading the Stage table, honouring `secret`.

**Read first:** 04:25-64 (tiers, frame rules), 04:132-189 (area), 04:191-271 (world),
04:273-308 (travel-time math, `location`, terrain keywords); 06:273-355; 01:84-104
(tempo, passive initiative); 02:397-486 (spatial model); `rules/combat-basics.md`
L29-51; `engine/space.py` whole file (it already does walls, doors, hazards, `--to`
pathfinding, `@feature`, LoS; see its docstring L1-16 and `Terrain` L84-100).

**Build:**
1. `lib/geo.py` contract:
   - `Frame(doc)` from a location file: `tier`, `unit` (`ft`|`mi`), `origin_text`,
     `places: list[Place]` (id, glyph, feature, at (blank → from, 04:48-50), from, to,
     effect, ref, source, `secret`), `routes: list[Route]` (id, from, to, via, kind,
     access, time, notes, `secret`), `parent` slug.
   - `to_parent(frame, point)` / `from_parent(frame, point)` = `at ± local` with ft↔mi
     (`5280`) only when units differ (04:44-47).
   - `bearing(a, b) -> "N" | "NE" | …` (8-point), `edge_distance(place_a, place_b)`
     (footprint-to-footprint), `band(ft)` per 02:447-452 for the GM's use.
   - `route_time(route, pace="normal", by="foot") -> minutes` per 04:279-287 (Euclidean
     along from→via→to, 300 ft/min or 3 mi/h, pace ×0.75/×1.5, kind factors
     04:176-178, conveyance factors, rounding rules); `time` override wins.
   - `find_route(frames, src_location, dst) -> list[Route]` chaining through site →
     area → world frames (06:381-384); raises `NoRoute`.
   - `nearby(frame, place_id) -> list[(id, bearing, distance_text, route_time_text)]`
     omitting `secret` rows (06:294-301), `(unplaced)` for rows with no coordinates.
   - `exits(site_doc, area=None)` from `## Areas`, the site's own Routes if any, and
     parent Routes touching the site (06:294-297).
2. `scene enter <location> [--light] [--area] [--write]` (06:273-301): the packet lines
   exactly as 06:276-284; passive Perception vs `## Hidden` with `dim −5 unless
   darkvision` and ties→PC (06:286-287); `--write` rebuilds `current.md` per
   06:288-291 and `onstage <npc> --goal --note` edits one On stage bullet; ends
   `scene` rules (Phase 2's `end_scope`); runs full `lint` once Phase 7 exists (stub a
   no-op until then and leave a `TODO(phase7)`).
3. `tempo tense|calm`, `pos`, `intent` (06:303-314, 01:84-104): passive initiative
   `10 + DEX mod ± adj`, ties → PCs, written as the Stage table (04:497-505) under
   `## Tempo: tense`. Position syntax resolution: `@<feature>`, `@<feature> N|S|E|W`,
   `near <creature>`, raw `x,y,z` — implement in `space.py` as `State.place(spec)` and
   call it from `pos`, so there's one resolver.
4. `combat start|next|end` (06:316-345): promote Stage → Combat block (04:509-532),
   copy Bounds + terrain from the sub-area's Layout, `--add "srd:thug x3 @25,15,0"`,
   `--init Kael=15`, `--surprised`; `next` advances `up:`, wraps rounds, moves the
   moves log into the session log, ticks `Nr` durations; `end` writes HP/conditions
   back, sets `status: dead`, restores `(not in combat)`, ends `combat` rules. **Write-back
   is required, not optional:** during combat HP, temp HP and conditions live only in the
   Combatants row (Phase 2 mutations write the row), so `end` must copy them to each PC/NPC
   file's frontmatter (`hp: {current, max, temp}`, `conditions`) or the files go stale. Unless
   `xp-tracking: off`, `end` also writes `.gm/last-combat.json` (foes, outcome,
   base XP from the stat blocks) and prints the un-applied `[XP available: …]` line
   (06 → combat end); Phase 6 applies it. `--frame`
   and `reframe` are Phase 8; reject with "not built yet".
5. `srd monster|spell|condition <name> [--write <npc file>]` (06:347-355) and a one-off
   `engine/fetch_srd.py` (stdlib `urllib`) that lists the 5e-bits repo directory first,
   downloads the 2014 Monsters/Spells/Conditions files into `data/srd/`, and writes
   `data/srd/LICENSE.md` with the CC-BY-4.0 attribution (03:17-22). Stat-block
   compaction: AC, HP (avg + dice), speed, six mods, attacks with to-hit/damage,
   traits. `atk` and `combat start` read through this module (06:353-354); remove the
   Phase 2 "srd not built yet" stub.
6. `space.py` changes: parse via `lib/md.py` (delete `table_rows`, import
   `parse_point`); read the Stage table when no Combat block exists (06:747); add the
   `secret` keyword (`Terrain.secret`, 04:303) and `Combatant.hidden` (conditions
   `hidden|invisible|unseen`, 06:324-327) so Phase 5's `--player-view` can filter;
   expose `State.place(spec)` for item 3; keep the CLI unchanged.
7. Update the POC: write Layout blocks only if a test needs them (the common-room one
   exists); no other content changes.

**Verify:** geo tests: inn↔mill route = 15 min and 0.8 mi (the numbers checked on
2026-10-04), reeve's house = 135 ft W of the inn, `to_parent` round-trips, kind/pace
factors; `scene enter crossroads-inn` on the POC prints `Exits:` and `Nearby:` lines
with no hand-typed direction anywhere in the code; `tempo tense --pos Mara @bar --pos
Tobin @tables-e` produces a Stage table whose `pos` cells are multiples of 5 inside the
bounds; `combat start --seed 1` then `space.py map` renders; `srd monster "bandit
captain"` prints AC 15 HP 65; all earlier phases' tests still green; `space.py` fixture
runs from 2026-10-04 (walls, `--to`, cones) unchanged.

**Guards:** no direction or distance literal in any output path (grep the geo and
scene modules for `"N"`-style constants outside `bearing()`); no network call in any
`gm.py` command (only `fetch_srd.py`); never pull SRD numbers from model memory.

---

## Phase 5 — Table client and player-view map (2a.5)

**Goal:** `engine/table.py`, the console players play in, and `space.py map
--player-view`.

**Read first:** 06:632-713 in full; 02:178-228 (what narration may never contain,
what the client hides); 01:162-187; 0.6 Agent SDK facts; the five build-time checks
at 06:707-713.

**Build:**
1. `space.py map --player-view [--from X]`: drop hidden combatants and `secret` terrain
   (06:324-327); everything else identical. `/map` skill uses only this form.
2. `engine/table.py` (the only file allowed to import `claude_agent_sdk`): CLI
   `[--campaign poc] [--new] [--model <id>] [--gm-view]` (06:645). Session: resume
   from `<campaign>/.gm/session-id` or start new, then auto-send `/gm` (06:648-656).
   Options: `cwd=dnd-adventure/`, `setting_sources=["project"]`, `allowed_tools=
   ["Bash(python engine/gm.py:*)", "Bash(python engine/space.py:*)", "Read"]`,
   `permission_mode="dontAsk"` (deny-by-default, 06:681-687), and a denial logger to
   `<campaign>/.gm/client.log` (verify the SDK callback name at build time: 0.6).
   Rendering per the table at 06:659-664: print `TextBlock.text` streamed; on a
   `ToolUseBlock` print the neutral `The GM consults their notes…` line once per turn;
   never print tool results, thinking or injected context. Input conventions
   06:666-679 (`Kira:` prefix, `:as`, `:quit`, `:gm-view on|off`, slash commands pass
   through, `<<SPOILERS …>>` banners). Failure handling 06:698-701.
3. Make sure user-level plugins and auto-memory are not loaded (06:693-696): the SDK
   session must use `setting_sources=["project"]` only; confirm with `--gm-view` that no
   memory/plugin context appears.

**Verify (the five checks at 06:707-713, each recorded in `engine/tests/CLIENT-CHECKS.md`):**
message types stream as expected; project hooks fire inside the SDK session, including
`SessionStart` after a forced compaction; plugins/memory absent; a disallowed tool is
denied silently and logged; `/gm` and `/overrule` arrive as skills. Plus: a run through
the POC opening scene shows only narration on screen, and `gm-view` shows the brief.
If a check fails because the SDK can't do it, fall back to the headless CLI (0.6) and
record why.

**Guards:** `grep -rn "claude_agent_sdk" engine/` returns only `table.py`; nothing in
`table.py` writes campaign files; GM-level text never reaches the console (02:178-228).

---

## Phase 6 — Character tools (2a.5b)

**Goal:** `gm.py pc draft|check|card|write|edit|level-pending|levelup|roster` and the
SRD class/race/equipment data behind them.

**Read first:** 06:559-630; 02:33-50 (session start), 02:52-108 (intake loop), 02:110-140
(level-up); 04:352-424 (PC file, derived fields, `overrides`); `rules/house-rules.md`
L13-21 (HP max-or-roll, `hp-method`); `campaigns/poc/pcs/_template.md` and `kael-ashford.md`.

**Build:**
1. Extend `fetch_srd.py` for Classes, Subclasses, Levels, Features, Races, Subraces,
   Traits, Equipment, Backgrounds, Spells (06:628-630), listing the repo dir first.
2. Drafts in `<campaign>/.gm/drafts/<slug>.json` (06:568, 04:605). `draft --set
   k=v … --equip "…"` and `--from-sheet <file>`; `check` prints the six sections at
   06:580-595 exactly; derived values recomputed on every change, `overrides` never
   (06:596-597); checks are warnings, never blocks (06:611-612). Required/optional
   fields per 02:79-96; subclass levels per 02:81; `hp-method` asked once (02:85).
3. `card`, `write` (draft → `pcs/<slug>.md` from the 04:358-424 template, deleting the
   draft), `edit --set … --item +"…"`, `roster --present … --absent …`
   (`present:` flags, 06:625-626).
4. `level-pending [--to N]`, `levelup --plan` and `--choose … --apply` (06:614-623,
   02:110-140): HP by `hp-method` (max: die max + CON; roll: public `dice.Roller`
   roll at `--apply`, or `--hp-roll N`), ASI/feat levels 4/8/12/16/19 + fighter 6/14 +
   rogue 10, subclass at its level, spells/expertise; refuse `--apply` with unanswered
   choices; on apply update HP, hit dice, prof, slots, Resources, features, scores,
   Attacks, spell DC/attack, a Journal line and a session delta; clear `level-pending`.
   Multiclassing is `custom` only (02:139-140).
5. **XP tracking and advancement** (06 → `gm.py xp`; 04 → Advancement; 02 → Level-up
   flow): `lib/xp.py` with the PHB threshold table as data; settings read from
   `campaign.md`, else `state/current.md` (defaults `advancement: milestone`,
   `xp-tracking: on`); `xp award|show|set` work unless tracking is off; even split,
   `xp-absent` handling, remainders dropped; crossing a threshold sets `level-pending`
   only under `advancement: xp` and is just noted under milestone;
   `award from-combat` reads `.gm/last-combat.json` (written by Phase 4's `combat end`,
   see below) and refuses double awards; `pc write`/`pc draft` always add `xp:` (the
   threshold of the starting level); switching modes per 04.

**Verify:** `pc draft grask --set race="half-orc" class=barbarian level=3
subclass=berserker --equip "greataxe; 4 javelins; explorer's pack"` then `pc check`
matches the DERIVED line at 06:581-582 (speed 30, prof +2, darkvision 60, d12, saves
STR/CON); `pc write` produces a file that `md.load` round-trips and that has all 26
frontmatter keys in template order; `pc level-pending kael --to 4` + `levelup --plan`
lists an ASI choice; `--apply` with `hp-method: max` raises Kael's max HP by 8 + CON
and adds a Journal line; `overrides: {ac: 17}` survives `edit`. XP: in a fixture with
`advancement: xp`, `xp award 1800 --present` with Kael and Kira at 900 gives 900 each
(1,800 < 2,700: no level-up); a second `xp award 1800` takes both to 2,700 and sets
`level-pending: 4`; the same awards in the POC (milestone, tracking on by default)
update `xp` but leave `level-pending` empty and print the milestone note; `xp-absent:
half` gives an absent PC half a share; `undo` reverses an award; with `xp-tracking: off`
every `xp` command refuses.

**Guards:** the model never adds up HP or slots (06:563): every number comes from the
SRD data + `hp-method`; player-stated values win after one question (02:92-95); no
non-SRD subclass is derived (mark `custom`).

---

## Phase 7 — Between scenes and sessions (2a.6)

**Goal:** `clock advance`, `travel`, `rest`, `lint` (all three layers wired), `session
archive`, `stub`, `where`, `world init|show|add|lead|place|reveal`, `trace`, `odds`,
`spoil`.

**Read first:** 06:359-506 and 06:518-557; 04:191-232 (world sections, constraints),
04:579-598 (session log/history), 04:540-577 (table-rules, spoilers); 02:230-372
(overrule/spoilers flows), 02:488-529 (open world); 05:43-60, 05:62-77; 01:150-160.

**Build:**
1. `clock advance` (06:359-378): report crossed `## Movements` departures with route
   and ETA (`location: @<route id>` while in transit; flip on arrival; no route →
   instant move + lint warning), condition expiries, CLOCK beats from active scenarios
   (`- CLOCK Day N HH:MM:` lines, 04:447-449) printed in full. Replace Phase 2's `time`
   alias body with this.
2. `travel <to> [--pace] [--by] [--night] [--overland]` (06:380-393): `geo.find_route`
   chain, time per `geo.route_time`, encounter table `tables/encounters-<route id>.md`
   then `-<area>.md` (skip when rule key `encounters=off`), then `clock advance`,
   `move-party`, `scene enter`, plus the `passes:` landmarks line (features within
   100 ft of the path). In-site `travel site/area` checks the site's Routes `access`.
3. `rest short|long` (06:395-399) using Phase 2 mutations and Resources `recovers`.
4. `lint [--fix-safe] [--files …]` (06:401-448): every check listed at 06:403-422,
   errors vs warnings per 06:439-442; wire layer 2 into `do` (append `[LINT]` lines
   from `journal.touched`) and layer 3 into `scene enter`, `combat end`, `session
   archive` (replace the Phase 4 stub). `--fix-safe` only adds missing `## Areas`
   entries, marked `<!-- added by lint, check me -->`.
5. `session archive` (06:450-456): next `history/session-NN.md` = `--summary-file` +
   extracted `  - ` deltas (minus `(GM)` lines for the recap portion), reset
   `session-current.md`, never touch `spoilers.md`, clear `in-session`, end `session`
   rules, run lint (refuse on errors unless `--force`), then `git add -A && git commit
   -m "session NN"` from the repo root (`dnd-adventure/`).
6. `stub npc|location|place` (06:458-464) from the 04 templates; `where [--from]`
   (06:466-476) with the `[WHERE]` lines; `world init|show|add|lead|place|reveal`
   (06:478-506 minus suggestions/import, which are Phase 8): constraint parser for the
   04:221-227 vocabulary, placement check (straight-line, 24 mi/day × 0.8, ±45°,
   overlap refusal, `--force` only via overrule), `placed:` note copy, frontier → route
   promotion.
7. `trace`, `odds`, `spoil log|list` (06:518-557): `odds` by exact enumeration of the
   d20 (and damage dice) outcomes through `resolve.py`, never simulation.

**Verify:** `clock advance to 00:10` on the POC prints Veskar's departure line in the
06:363 shape with `due 00:16`; `travel old-mill` from the inn reports 15 min, moves the
party, prints a scene packet; `lint` on the pristine POC exits 0 with only warnings for
unplaced rows (reeve/smithy/shrine) — if it reports anything else, fix the POC, not the
check; break a `parent:` on a fixture copy and confirm an error; `session archive
--summary-file x` creates `history/session-01.md`, resets the log, and makes a git
commit on the fixture repo (init a temp repo in the test); `world add "x" --near
thornbury --within 3d` then `world place x --at 100,0` is refused (72 × 0.8 = 57.6 mi)
and `--at 30,0` accepted; `odds atk Kira Veskar --with dagger` prints the 06:540 line
shape.

**Guards:** no teleport path (every move goes through a route or logs a warning);
`spoilers.md` is append-only; `session archive` never commits with lint errors; `world
place` never picks a spot itself (06:496-497).

---

## Phase 8 — Deferred spatial features (2a.7)

**Goal:** only when play asks: `combat start --frame` + `combat reframe`, `world place`
suggestions, `world import`, `space.py map --place`.

**Read first:** 06:317-323 and 06:339-343 (frames/reframe), 06:495-497 (suggestions),
06:500-504 (import), 06:508-516 (area/world maps); 02:426-436; 04:44-50.

**Build:** `reframe` = add/subtract the site's `at` for every position, terrain row and
moves-log entry, rewrite `Map:`/`Bounds:`, pull Places rows in as terrain (footprints
as `wall` rows), refuse reframing into a site while anyone is outside its footprint.
Suggestions = three spread-apart spots satisfying every constraint, each described by
what it's next to. Import = `| name | x | y |` rows transformed by one anchor + scale or
two anchors (no rotation), landing in Known-not-placed with `near (x,y) ±5mi`. `map
--place <area> [--cell N] [--player-view]` from Places/Routes, frontier arrows, blank
space labelled *unexplored*.

**Verify:** reframe round-trips (site → area → site leaves every position unchanged);
an import with two anchors reproduces the second anchor exactly; the Thornbury map shows
the mill ~88 cells north of the well at `--cell 50`.

---

## Phase 9 — GM skills (2b)

**Goal:** `.claude/skills/<name>/SKILL.md` for the eleven skills in 02:8-20, each a
short procedure that calls the Phase 1–7 commands.

**Read first:** 02 in full (every section is skill behaviour); 01:55-79 (turn loop);
01:150-160; 0.6 Skills format; `rules/*.md` for what `/gm` tells the model to apply.

**Build:** one directory per skill: `gm`, `character`, `level-up`, `scene`, `travel`,
`combat`, `map`, `overrule`, `spoilers`, `end-session`, `new-campaign`. Frontmatter:
`name`, `description` (the "trigger" column of 02:8-20), `disable-model-invocation:
true` on the player-facing ones (`overrule`, `spoilers`, `end-session`, `new-campaign`,
`character`) so only `/name` invokes them; `allowed-tools: Bash(python engine/gm.py:*)
Bash(python engine/space.py:*) Read`. Bodies:
- `/gm`: set `in-session: true` (`gm.py session start`, add this tiny command here),
  the session-start routine 02:33-50, then the turn loop 01:55-79 with the Timeliness
  rules 02:538-548 and Behind-the-screen rules 02:178-228 quoted, not paraphrased.
- `/character`, `/level-up`: the loops at 02:52-108 and 02:110-140 as numbered steps
  with the exact `pc` commands.
- `/scene`, `/travel`, `/combat`, `/map`: the one-line recipes in 02:11-15 expanded
  with when to narrate what; `/map` is the only place the map is pasted, always
  `--player-view`.
- `/overrule`, `/spoilers`: 02:230-305 and 02:307-372, including the card/banner
  formats and the `gm.py` calls.
- `/end-session`: summary + world tick (02:526-528 frontier leads) then `session
  archive`.
- `/new-campaign`: copy templates from 04, `world init <area>`, write `campaigns/.active`.

**Verify:** `claude` in `dnd-adventure/` lists all eleven under `/`; `/gm` on the POC
produces the roster → recap → opening scene without a permission prompt and without
pasting any `[SCENE]`/`[GM BRIEF]` line; `/map` output on a fixture with a `secret`
trapdoor omits it; a `/spoilers` answer is wrapped in the `<<SPOILERS …>>` markers
and appears in `sessions/spoilers.md`.

**Guards:** skills call commands, never Read+Edit game files (02:541-542); no skill
quotes a secret section into narration; no skill invents a command not in 06.

---

## Phase 11 — Campaign authoring, encounters, mechanics (2c)

**Goal:** `gm.py campaign|encounter|danger|loop`, the `/campaign` skills, and the
time-loop rules sheet, so the first real campaign (`loop-play`) can be run.

**Read first:** `docs/design/07-campaign-authoring.md` in full; 06 → Campaign authoring,
encounters and mechanics; 04 → Campaign file; 02:52-108 (the intake pattern the
`/campaign new` skill copies); 0.6 Skills (`context: fork` for the generation steps).

**Build:** (1) the 2014 DMG XP-threshold table and multipliers as data in
`lib/encounter.py` with `budget`, `build`, `threat`; (2) `danger` on top of `geo.py`
bearings; (3) `loop start|reset|status` using `git checkout <sha> -- <paths>` from the
repo root, gated on `mechanics`; `clock advance` calls `reset --by time` at `loop-end`;
`lint` rules from 06; (4) `campaign new|fill|status|ledger`; (5) skills
`.claude/skills/campaign-new`, `-scenario`, `-fill`, `-status` with `context: fork` on
the generating steps and a report template that is the shape card and nothing else;
(6) `rules/mechanics/time-loop.md`, included by `/gm` when the campaign lists it;
(7) `/combat` recipe switches to `encounter build` for non-fixed fights; (8) `loot
roll` and `shop` with the `## Loot`/`## Stock` table readers, rarity price bands and
restock hooks in `clock` and `loop reset`; item power in `budget` from inventory
rarity tags (07 → Items, loot and merchants).

**Verify:** `encounter budget --present Kira,Kael,Bren,Ash` at level 3 prints
easy 300 / medium 600 / hard 900 / deadly 1600; `build` of a `hard` template for 2
PCs yields a smaller roster with the same per-PC pressure, and for a party carrying two
rare items the full roster; `shop --buy` on a set merchant moves coin and adds the
item with its rarity tag; `danger` on the two generated
campaigns colours the ceremony red at level 3 and yellow or red at level 5; `loop
reset --by death` on a fixture restores an NPC's `location:` but leaves a PC's
inventory; a campaign without the mechanic rejects `loop` commands; `/campaign new`
on a toy seed returns only a shape card in the parent context (grep the transcript for
`## The truth`).

**Guards:** no secret text in any skill's returned report; `loop` never writes under
`pcs/`; thresholds come from the data table, never from the model.

## Phase 12 — Splitting the party (2d)

**Goal:** the party can split into groups that each keep their own scene and game
clock, with the GM cutting between them by slice (02 → Splitting the party).

**Read first:** 02 → Splitting the party; 04 → Split party; 06 → `gm.py split`;
06 → `gm.py brief` + hooks (the exchange counter rides the hook); `engine/clock.py`
and `engine/scene.py` (both act on `current.md`, which stays the active group's).

**Build:** (1) `engine/split.py` with form / cut / status / sense / task / join, parking
scenes in `state/split/<group>.md` and keeping `state/split.md`; (2) the brief hook
counts exchanges while split, and `brief` adds the `Split:` line and the `Cut due` /
`Cut every round` cue; (3) `clock`/`time` advance only the active group, fire world
CLOCK beats and NPC schedules on the earliest group clock, and warn past one slice
ahead; `move-party` moves only the active group's PCs; (4) sensing on `geo` distance,
`split-sense-ft`, sight ranges via `lib/sight.py`, and `senses:`; (5) settings
`split-exchanges`, `split-combat-rounds`, `split-sense-ft`; (6) `/gm` skill section on
splitting (when to cut, holding a waiting group's actions, the one-line knowledge
reminder, summarising skips) and the `combat` skill's per-round cut when sensed.

**Verify:** split dryrun into `mill=Grusk` and `inn=Kael,Kira`; three prompts → brief
says `Cut due`; `split cut` picks the group with the earlier clock; `time +40m` on one
group warns; a CLOCK beat between the two group times doesn't fire until the earlier
group reaches it; combat at the mill with the inn 2 miles away → `Cut due` after 6
rounds; with both groups at old-mill → `Cut every round`; `split join` at one site
levels clocks and prints the gap; `undo` reverses each split command.

**Guards:** `current.md` is always a complete, valid scene; no PC in two groups;
`split` never moves a PC the GM didn't name; nothing cuts without the GM.

## Phase 13 — State the table forgets (2e)

**Goal:** concentration, dying, light sources, supplies, exhaustion and content
boundaries are kept by the tools, so the GM never has to remember them or invent
their numbers (02 → Table mechanics → Phase 13).

**Read first:** 02 → Table mechanics (intro + Phase 13); 04 → Table settings, PC file
→ Added by Phases 13–15, Scene state added by Phases 13–15; 06 → Table mechanics →
Phase 13; `engine/lib/resolve.py` (`apply_hp`, the `death-saves` rule key),
`engine/mutations.py` (`hp`, `cond`), `engine/inventory.py` (count decrement),
`engine/lib/sight.py`, `engine/clock.py`, `engine/combat.py` (`next`, `end`),
`engine/rest.py`, `engine/brief.py`.

**Build:** (1) settings `death-save-rolls`, `track-light`, `supplies`, `exhaustion` in
`campaign.SETTINGS`; (2) `conc` (new `engine/conditions_ext.py` or inside
`mutations.py`): start/end, target effects, the CON-save line on `hp -`/`dmg`, auto
end on 0 HP / incapacitating conditions / a new `conc`, expiry via `clock` and
`combat next`; (3) dying: `apply_hp` writes `death-saves:` instead of the note,
`deathsave`, `stabilize`, massive damage, `combat next` prompt, `(GM)` lines when
secret, the stable wake-up as a clock event; (4) `lib/light.py` source data, `light`
command, `lit:` countdown in `clock`, effective light in `sight.effective` (the best
carried source in the active group; in combat by `pos` radius), the Sight line names
it; (5) supplies: `ammo <thing>` in Attacks notes, spending in `atk` (strict), `Ammo
spent:` line and the recovery offer in `combat end`, `eat`, `fed:`, the dawn check
in `clock`, `rest long` eating; (6) `exhaust`, its effects in `resolve.py` (2014 and
2024 tables), `turn`/`move` speed, level-4 HP max, `rest long` recovery; (7) `campaign
boundaries`, the `Table:` brief line (full brief only, in the hash), `!x` in the
brief hook (logged, not counted as a split exchange); (8) brief party-line tags
`[conc bless 8r]`, `DYING ✓1 ✗2`, `[exh 2]`, and the heartbeat carries dying PCs;
(9) skills: `/gm` (boundaries at session start when unset, the X-card, light and
supplies in narration), `/combat` (concentration saves, death saves on the dying PC's
turn), `/campaign-new` (asks lines and veils), `/end-session` (nothing new).

**Verify:** `conc Kael bless --on Kael,Kira 1m` then `dmg Kael 14` prints `CON save DC
10`; a failed `save Kael con 10 <roll>` strips `bless` from Kira; `hp Kira =0`, then
`deathsave Kira 1` → `✗2`, `deathsave Kira 20` → 1 HP, conscious; `dmg` of ≥ max HP
at 0 → `dead`; `light Kael torch` in a `light: dark` scene turns Kael's Sight line
bright and `time +61m` prints `Light out: Kael's torch`; `supplies: strict` → 3
shortbow `atk` rolls leave `quiver (17 arrows)` and `combat end` offers 1 back; a PC
not fed for 6 days with CON +2 gets `exhaustion: 1`; `exhaust Kira =3` → her next
`check` and `atk` roll with disadvantage; `!x` produces the X-card line and a log
entry with no text; every command undoes cleanly; `supplies: off` and `track-light:
off` change nothing in inventory.

**Guards:** the tool never decides a save for a player (it asks for the d20); no
boundary text in player-facing output (the brief is GM-side); the ambient `light:` is
never overwritten by a carried source; `death-saves` table rule still wins.

## Phase 14 — Exploration, social pressure, hazards (2f)

**Goal:** travel activities and getting lost, attitude-based social DCs, morale,
chases, traps and environmental hazards, and hiding as a stored state (02 → Table
mechanics → Phase 14).

**Read first:** 02 → Table mechanics → Phase 14; 04 → Scene state added (marching
order, `## Chase`, `TRAP` lines, navigation terrain, `environment:`); 06 → Table
mechanics → Phase 14; 06 → `travel`, `clock advance`, `combat start | next | end`;
`engine/lib/geo.py` (routes, bearings, frames), `engine/scene.py` (Hidden lines,
notices), `engine/lib/encounter.py` (XP for defeated foes).

**Build:** (1) settings `travel-detail`, `getting-lost`, `social-dcs`, `morale`,
`chases`; (2) `travel --plan` and the resolving call: activities, terrain DCs,
the wrong-bearing walk in the world frame, foraging, watchers-only encounter
passives, forced-march saves; `order`; (3) `lib/social.py`: the 02 DC table as data,
`check --vs --ask --leverage --flair --pitch --why --goal [--core]`, `moved-by:` on
NPCs, the `creativity` steps, `state/social.md` with the wall stages, the result
tiers, `social status|drop|wall`, the brief's `Social:` line, settings `creativity`
and `social-wall`, the first-session `[TELL THE TABLE]` line from `intro`; (4) morale triggers in `combat next`, exemptions
by SRD type, `+fled`/`+surrendered`, XP and prisoners in `combat end`; (5)
`engine/chase.py` with the `## Chase` block, Dashes, complication tables (ship
`tables/chase-urban.md` and `chase-wild.md` as engine defaults a campaign may
override), the escape test, 6 s rounds on the clock (and split charging like
combat); (6) `trap` over `TRAP` lines in `## Hidden`, `hazard fall|breath|env`, the
hourly environment saves in `clock`, underwater rules in `atk`; (7) `hide`/`seek`,
stored totals compared on `scene enter` and `combat start`, advantage-then-reveal on
`atk`; (8) `lint`: `TRAP` lines parse, `terrain:`/`forage:` values valid; (9) skills:
`/gm` (travel activities, social asks, hiding; the one plain-words line about the
wall at the first session, switching it off when a player asks, explaining it only
on request), `/campaign-new` (asks `social-wall` with the other settings: "on by
default; it can make social scenes easier when you're stuck, and you can turn it off
any time"), `/combat` (morale, chases, underwater), `/scene` (traps and the marching
order).

**Verify:** dryrun `travel old-mill --plan` with activities prints the navigation and
forage DCs; on the road no navigation check is asked; a trackless leg with a failed
`--nav` ends somewhere other than the destination and says `Lost`; `check Kira
persuasion --vs mara --ask major` with Mara wary prints DC 30 (no refusal); with
`--flair 3 --pitch x` under `creativity: light` DC 22 and advantage, and `moved-by:
[nothing]` on Mara makes it flair 2 (DC 25, no advantage); the same `--pitch` again
scores 0; three failed `--goal` attempts print stages 1–3, and a fourth with a new
skill starts a band lower while one with the same skill doesn't; success removes the
goal row; `--core` exits 1; `social wall off` writes the setting and stops the stages,
and a first-session `intro` prints the `[TELL THE TABLE]` line only while it's on; with Mara friendly `--ask major` prints DC 20; a bandit group dropping under half HP prints one morale line
and never again for that trigger; a fled bandit counts toward `xp award`; `chase
start --quarry Veskar --pursuers Kael` (Veskar with 2 free Dashes) → `chase next` × 4
spends Dashes and the 5th (Veskar's third Dash) asks for a CON save; `trap trigger` on a fixture pit applies the fall damage and `prone`, and `trap
status` shows `triggered`; `hazard breath Kael` with CON +1 → `holding breath 2m`;
`hide Kira 17` then `scene enter` with Veskar (passive 14) arriving → not spotted;
`seek Veskar 18` → spotted; each undoes.

**Guards:** getting lost never moves the party along a route it didn't take; the
social tool refuses only `--core`; flair is never shown to players and is logged
before the result; morale never fires for the party side (PCs and companions; Phase 15 hirelings check by loyalty); traps never show their
`(GM)` details in player output; no straight-line teleport while lost (world frame
travel only).

## Phase 15 — Optional subsystems (2g)

**Goal:** inspiration, readied actions, magic items, downtime, allied creatures,
weather, encumbrance, faction renown, mounts and lingering injuries, each behind a
setting and each buildable on its own (02 → Table mechanics → Phase 15).

**Read first:** 02 → Table mechanics → Phase 15; 04 → Table settings, PC file → Added
by Phases 13–15 (magic-item tags, `## Companions`, `## Downtime`), `state/factions.md`;
06 → Table mechanics → Phase 15; `engine/pc.py` (derivation, `overrides`),
`engine/inventory.py`, `engine/combat.py`, `engine/clock.py`.

**Build** (any order; tick each in the completion notes): (1) settings `inspiration`,
`downtime`, `weather`, `encumbrance`, `renown`, `lingering-injuries`; (2) `inspire`
and `--insp` on `atk/save/check`; (3) `ready` and the `combat next` reminders; (4)
magic items: download `5e-SRD-Magic-Items.json`, `attune`, `charge` + clock recharge,
`identify`, bracketed bonuses in `pc` derivation; (5) `downtime` with lifestyle costs
and the clock; (6) `companion add`, `hire`, companions in `combat start`, wages in
`clock`; (7) `weather` rolls at dawn per `climate:`, effects on light sources,
ranged attacks and the brief header; (8) encumbrance from SRD weights in `pc card`,
`turn`/`move`, `travel` and the resolver; (9) `renown` and `state/factions.md`, the
attitude shift in brief and social DCs; (10) `mount`/`dismount`; (11) `injury`; (12)
skills: `/gm` (inspiration awards, downtime between adventures), `/combat` (readied
actions, companions, mounts), `/level-up` (attunement and magic items in the card).

**Verify:** per item, a seeded test: inspiration spent once gives advantage and a
second `--insp` errors; a readied action prints before the matching turn and clears
at the owner's turn; a fourth attunement is refused; `charge` at 0 then dawn rolls
the recharge; `downtime Kira craft "chain shirt" 10d --lifestyle modest` adds 50 gp
of progress, spends 10 gp of lifestyle (under `upkeep: on`; by default the line only says so) and moves the clock 10 days; a familiar
enters `combat start` with `ctrl Kira`; strong wind puts out a lit torch; Kira at
STR 8 carrying 45 lb with `variant` shows `[enc]` and speed −10; renown 3 with the
Red Ledger makes a wary member's DC table read as neutral; a mounted fight keeps the
horse on Kael's initiative.

**Guards:** every subsystem's `off` leaves the existing commands unchanged
(regression-test the default settings against the Phase 1–12 suite); non-SRD tables
(carousing, injuries) are campaign-supplied, never shipped as rules text.

## Phase 16 — Table extras (2h)

**Goal:** pre-rolls applied to the right check, a first-session "how to play" talk
that teaches name prefixes and rolling ahead, carousing with a d100 table and real
consequences, and the optional critical hit die (02 → Dice → Pre-rolls; 02 → Table
mechanics → Phase 16).

**Read first:** 02 → Dice → Pre-rolls, 02 → Table mechanics → Phase 16, 02 → Wacky Juice
(the same limits apply to carousing); 04 → Table settings, Random tables; 06 → Table
mechanics → Phase 16; `engine/lib/resolve.py`, `engine/loot.py` (table parsing to
reuse), `engine/campaign_cmd.py` (copying templates).

**Build** (tick each in the completion notes): (1) `--rolled-as <skill>` on
`check/save/contest` and `--d20 a,b`, with the second die rolled publicly when one is
given and the roll has adv/dis; (2) settings `carousing`, `crit-die`, `crit-die-pcs`; (3)
the shared random-table reader (`| roll | result | effect | tags |`, ranges, `die:`
inference) and the effect-code applier, reusing `loot`'s parser where it fits; (4)
`table import` with gap/overlap reports; (5) an **original** starter
`engine/templates/tables/carousing.md` (100 results across d100 ranges, about 40 rows,
silly and weird, each with consequences that can be filed) and `crit-die.md` (the
starter d10 in 02), copied by `campaign new`; (5b) `[HOW TO PLAY]` in `intro` for the
first session plus `intro --how-to-play [--for <PC>]` (02 → How to play; 06 → `intro`),
with the session-start step in `/gm` and the new-player hand-off at the end of
`/character`; (6) `carouse` with cost, tag-based
re-rolls against `lines:`/`veils:`, `--reroll`, and GM-only log lines; (7) crit die in
`atk` with the codes in 06, `crit-die-pcs`, and the Legendary Resistance note; (8)
skills: `/gm` (pre-rolls, carousing: the pause, morning reveal, filing consequences),
`/combat` (the crit die line and narrating each effect).

**Verify:** seeded tests: `check Kira investigation 15 --total 17 --rolled-as perception`
uses Kira's Investigation bonus and prints both skills; `--d20 14` with `adv` rolls one
more die and keeps the higher; first-session `intro` prints `[HOW TO PLAY]` with the
roll-ahead line, `gm-rolls-all` drops it, a second `intro` in the same session doesn't
repeat it, and `--for Kira` prints the short version; `table import` of a pasted list
with a gap reports it;
`carouse Kira,Kael --seed N` charges the cost, applies a `coin` and an `item` code, and
re-rolls a row tagged with a campaign line; `atk` with `crit-die: on` on a natural 20 at
seed N gives `disarm` and logs the dropped weapon; a `kill` against a PC leaves them at 0
HP and dying under the default; `crit-die: off` leaves `atk` byte-identical to before.

**Guards:** no third-party table text in the engine repo, ever (starter tables are
original writing); carousing is GM-side until the morning reveal, so `carouse` output is
never pasted; the crit die never fires on ability checks or saves.

## Phase 17 — Discord bridge (2i)

**Goal:** remote players type and read in a Discord channel through `table.py`, with the
host reviewing a queue (queue mode) or lines going straight through in batches (auto
mode) (06 → Table client → Discord bridge).

**Read first:** 06 → Table client (the whole section, including Discord bridge); 04 →
Discord bridge; `engine/table.py` (`InputState`, `send`, `confirm_staged`, the render
path); the current `discord.py` docs for intents (message content is a privileged
intent), reactions, and running the client inside an existing asyncio loop.

**Build:** (1) optional import of `discord.py` behind `--discord` / `discord.md`, with a
clear notice when it isn't installed; (2) a `Bridge` that posts what the renderer shows
(paragraph chunks under 2000 characters, spoiler banners as `|| ||`, the map in a code
block) and never GM-view output; (3) inbound: channel filter, player map, speaker
resolution, ignored-user notice; (4) the queue: numbered display, typed lines join it,
empty Enter or `:send`, `:q`, `:edit`, `:drop`, `:clear`, reactions, and edits/deletes
on Discord mirrored; (5) auto mode: batching while the GM replies plus the debounce;
(6) `!x` jumps the queue; slash commands always queue with `⚑`; (7) `:discord
queue|auto|off`; reconnect with backoff; token only from the environment; (8)
`engine/tests/CLIENT-CHECKS.md` gains the Discord checks.

**Verify:** unit tests with a fake Discord client (no network): queue ordering, edit,
drop, submit as one prompt; auto batching with the debounce, using an injected clock;
`!x` bypasses the queue; `/overrule` from Discord queues in auto mode; unmapped users
are ignored; a 4,500-character reply posts as three chunks; a spoiler banner posts
inside `|| ||`; `--gm-view` output never reaches the fake channel. Then one live check
in a private test server.

**Guards:** the token never appears in a file, log or error message; the bridge adds
no permissions (Discord text is a player prompt); if the bridge fails, the terminal
table keeps running.

## Phase 10 — Verification sweep and dry-run readiness (README Phase 3)

1. **Anti-pattern grep** over `engine/` and `.claude/` for everything in 0.8; all empty.
2. **Full test run** (`python -m unittest discover engine/tests`) green on a clean
   checkout with CRLF and with LF working trees (toggle `core.autocrlf` in a temp clone).
3. **Spec parity:** for every command heading in 06 (0.4 list), `python engine/gm.py
   <command> --help` exists and its flags match the heading; record misses in
   `engine/tests/PARITY.md` and either build or amend 06 (never leave the two apart).
4. **Timing:** every command on the POC < 200 ms (06:49); hook < 100 ms.
5. **Secrets leak check:** run the POC opening through `table.py` and diff the console
   transcript against the GM view; the console must contain no `[SCENE]`, `[GM
   BRIEF]`, `(GM)`, file path, DC, or beat name (02:178-228).
6. **Dry run** per `README.md` Phase 3: two pregens + one new PC via `/character`,
   a tense scene at the inn placed by name, the inn fight with a wall and the stairs,
   `travel` to the mill, one `/overrule`, one `/spoilers`, `/end-session`. Note every
   stall or drift in `docs/build/DRY-RUN-NOTES.md`; tighten skills, not
   tools, unless a tool is wrong.
7. Tick the README phases; update `README.md` build-phase checkboxes at the repo level.

---

## Phase 1 — completion notes (2026-10-04)

Built and verified (83 tests). Extras beyond the contract that later phases may use:
`GM_CAMPAIGN` env var (same effect as `--campaign`), `Doc.front_quoted`, `Doc.bom`,
`Table.find`, `Table.extras` (cells beyond the header, preserved on edit),
`journal.log_turn/current_turn/entries`, `gametime.parse_clock/parse_window/diff/
fmt_delta`. `Batch` is lazy: entering costs nothing; the entry is created on the first
write. Writes under `.gm/` are never journaled; writes outside the campaign root raise.
`gm.py` has a minimal `log` command already. Known, deliberately unfixed: indented table
rows lose their indent on edit; `section()` is first-wins on prefix (prefer exact
heading text when two share a prefix); exotic unicode line separators are normalized.

## Phase 2 — completion notes (2026-10-05)

Built and verified (184 tests). Commands: `roll`, `atk/save/check/contest` (in
`roll.py`), `hp/dmg/cond/move-npc/move-party/time/undo` (`mutations.py`),
`item/coin/res/attitude` (`inventory.py`), `rule/retcon/overrule-undo` (`rules.py`).
Libraries: `lib/dice.py` (`Roller`, `Result.body/label`), `lib/resolve.py` (the only
outcome rules, incl. `attack_mode`, ties-go-to-PC, table-rule keys), `lib/creatures.py`
(creature numbers; raises `SrdNotBuilt` for SRD stat blocks until Phase 4),
`lib/errors.py`. Decisions the spec left open:
- Flags for "this DC/target belongs to a PC": `save … --by <pc>`, `check … --vs <pc>`.
- `dmg` applies resistance/immunity/vulnerability (frontmatter lists, see 04); temp HP
  is `hp: {current, max, temp}` and `9/11 (+5 temp)` in combat rows.
- The tool rolls all damage; one log delta per `atk` (HP change folded in).
- `gm.py --seed N do "…"` shares one seeded roller across the batch.
- Locations must be `slug[/area]` naming a non-world-tier file.
- Split group members are single creatures (size `M` until Phase 4 reads stat-block size).
- **For Phase 4:** `combat end` must write HP/temp/conditions from the Combatants rows
  back to PC/NPC frontmatter (added to Phase 4's build list).

## Phase 3 — completion notes (2026-10-05)

Built and verified (205 tests). `engine/brief.py` (`brief`, `--long`, `--hook`),
`engine/juice.py` + `lib/wacky.py` (Wacky Juice), `campaign.settings()` /
`settings_doc()` (campaign.md → current.md → defaults, for the advancement and juice
keys), check/save/contest margins in `roll.py`, `.claude/settings.json`. Decisions the
spec left open:
- `.gm/brief-hash` holds `hash`, `prompts` (since the last full brief) and `turn` (the
  turn of the last full brief, shown in the heartbeat). `.gm/juice` holds
  `prompts-since` (blank = never fired), `pending`, `pending-name`.
- The brief's Party line shows `XP n/next` only for PCs that carry an `xp:` key (Phase 6
  adds it); `Watch:` drops file paths; `Next clock:` is the earliest Clocks bullet at or
  after now, its trailing `(…)` dropped.
- Juice eligibility: in combat, non-party Combatants rows that can act; otherwise Stage
  rows / On stage bullets that aren't PCs (an On stage bullet with no file, like "The
  wolves", is eligible). Prompts starting with `/` or `!` neither fire nor count toward
  the cooldown.
- The hook catches every exception and prints `[GM BRIEF] unavailable: <type>: <msg>`.
  It reads stdin only when it isn't a TTY; tests must patch `sys.stdin`.
- Real-session check (headless `claude -p` in `dnd-adventure/`, POC `in-session: true`):
  both SessionStart and UserPromptSubmit briefs were injected. **The permission
  allowlist is ignored until the workspace is trusted** (open Claude Code interactively
  in `dnd-adventure/` once and accept the trust dialog); re-check `gm.py roll 1d20` runs
  without a prompt after that.

## Phase 4 — completion notes (2026-10-05)

Built and verified (228 tests). `lib/geo.py`, `lib/srd.py`, `engine/fetch_srd.py`
(data in `data/srd/`: Monsters, Spells, Conditions + LICENSE.md, committed so play never
needs the network), `scene.py` (`scene enter`, `onstage`), `tempo.py` (`tempo`, `pos`,
`intent`, and the shared `set_section`/`set_tempo` helpers), `combat.py`, `srd.py`
(the command). `lib/creatures.py` now reads SRD numbers; `hp` on an SRD-statted NPC
with no `hp:` line starts from the stat block's average and writes it. Decisions the
spec left open:
- The 5e-bits files live under `src/2014/en/` (not `src/2014/`); found by listing.
- Distances switch from ft to mi at 1,000 ft (06 said "under a mile", but its own
  example and this plan's check print the mill at 0.8 mi); 06 updated.
- Route time through a shared place ignores the walk across it (inn → square → mill
  road); Nearby says `no route` when no route chain exists.
- Exits from a site's own Routes get a bearing from the area's Layout centre to the
  matching exit row; parent-frame routes get the site→place bearing and `adjacent`.
- Beats are numbered by their order among WHEN/CLOCK lines in the scenario file.
- `scene enter --write` also takes `--summary` and `--scene`; it keeps existing Clocks
  and adds scenario CLOCK lines not yet passed. `onstage` also takes `--remove`.
- `tempo tense` re-run keeps rows' pos/adj/intent. NPC side = `foe` when
  `attitude-to-party` is hostile, else `neutral`.
- `combat start --add "srd:<name> [xN] [@x,y,z | @feature [N|S|E|W] | @near <creature>]"`;
  xN > 1 makes one `group r5` row named `<Name>s ×N`. A failed placement leaves the row
  `?` and says so instead of aborting. With no Layout the block has no Bounds/Terrain.
- `combat end` drops round-based (`Nr`) conditions, keeps the rest; XP counts foes at
  0 HP, `--count <name>` (routed, captured, talked down) and `--count-fled`.
- **space.py bug fixed:** pathfinding let a creature without a fly/climb speed walk
  through the air above the floor (the 2026-10-04 fixture's `move Kael --to Brute
  --stop 10` ended at z 5). Now grounded movers only enter raised cells that terrain
  supports (stairs, a landing). That one fixture output changed; every other is
  byte-identical.
- `space.py map --player-view` (Phase 5's filter) is already in; Phase 5 only needs the
  table client to use it. `gm.py space …` adds `--state` for the active campaign.

## Phase 5 — completion notes (2026-10-05)

Built and verified (241 tests + the live checks in `engine/tests/CLIENT-CHECKS.md`).
`engine/table.py`; `space.py map --player-view` came with Phase 4. Needs
`pip install claude-agent-sdk` (0.2.163 used); everything else stays stdlib-only and
`table.py` imports the SDK lazily. Findings that changed the design:
- **Windows:** the SDK refuses npm's `claude.CMD`; `find_cli()` uses the `claude.exe`
  it wraps (`CLAUDE_CLI_PATH` overrides).
- **Deny-by-default needs a PreToolUse hook.** Read-only shell commands (`whoami`) are
  auto-approved and never reach `can_use_tool`. The client's hook (`decide()`) is the
  real gate; `can_use_tool` is a backstop. Accepted: single `gm.py`/`space.py` commands
  (Bash or PowerShell) with no unquoted `; & | < >`/newline and no `$(`/`${`/backticks,
  optionally after `cd <game folder> &&` or with an absolute path to `engine/`;
  Read/Glob/Grep inside dnd-adventure/; Skill.
- **Auto-memory** was on for SDK sessions; the client sets
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
- `/gm` is auto-sent only when `.claude/skills/gm/` exists (Phase 9).
- **For Phase 9 (`/gm` skill):** the GM must call tools exactly as
  `python engine/gm.py <command>` (it tried `python gm.py …` first), never mention a
  denial to the players, and never invent a roll when a tool fails (the first run did,
  before the denial message named the allowed form).

## Phase 6 — completion notes (2026-10-05)

Built and verified (258 tests). `lib/chargen.py` (derivation + check/card text),
`lib/xp.py`, `engine/pc.py`, `engine/xp.py`; `fetch_srd.py --only …` pulled Classes,
Subclasses, Levels, Features, Races, Subraces, Traits, Equipment, Backgrounds,
Proficiencies, Skills into `data/srd/` (3.0 MB total). PC templates gained `xp:`.
Decisions the spec left open:
- **Editing an existing PC infers its build from the file** (no hidden build data):
  proficient skills and expertise from the skill totals, equipment from the
  Inventory's `Equipped:` line, cantrips/spells from the Spells table. Kael's POC sheet
  re-derives exactly (AC 18, HP 30, skills, mace +4, DC 13).
- Updates keep hand-written rows the tools don't derive (spell attack rows, custom
  resources, prose); spell DC/attack numbers are refreshed wherever the file states
  them (Spells line, spell rows in Attacks, Stats prose), as are save/skill totals in
  the Stats prose. Narrative text (e.g. "cleric 3") is left alone.
- Draft fields: `scores` = final (player-stated) or `base-scores` = before racial
  bonuses; lists accept `a, b` or `a; b`; `--set str=15` sets one score.
- `hp-method: roll` rolls missing hit dice publicly in `pc draft` (logged); `--hp-rolls`
  / `--hp-roll` take reported rolls. A CON increase at level-up is retroactive (PHB).
- Level-up is one level per flow and needs `level-pending` above the current level.
  Choices: `asi=dex+2` / `asi="str+1 con+1"`, `feat=…` (custom), `subclass=`,
  `expertise=`, `fighting-style=`, `cantrips=+x`, `spells=+a,-b`; other choose-features
  are free text keyed by the feature name. Multiclassing stays custom.
- Resources derived: spell slots, rage, channel divinity, action surge + second wind,
  ki, sorcery points, bardic inspiration, lay on hands, wild shape.
- XP: an absent PC named in `--to` gets `xp-absent` of a share; `from-combat` marks
  `.gm/last-combat.json` awarded (not journaled, so `undo` of that award does not
  re-open it). Under `advancement: xp`, totals below the level's threshold are raised
  to it first (04 → switching modes).

## Phase 7 — completion notes (2026-10-05)

Built and verified (281 tests). New command modules: `clock`, `travel`, `rest`, `lint`
(+ `lib/lint.py`), `session` (`start`, `archive`), `stub`, `where`, `world`, `trace`,
`odds`, `spoil`. Every command < 125 ms on loop-play. Decisions the spec left open:
- **Transit state:** an NPC on the road has `location: "@<route id>"` (the leg it is on)
  and `transit: "to <dest> · depart Day N HH:MM · eta Day N HH:MM · from <loc> · via
  <routes>"`; `where`/`trace` read it (percent of the way). Same-site moves are
  instant; a Movements target that isn't a location file is skipped with a `[LINT]`
  line (loop-open has such lines: "→ in transit", "→ (dead …)").
- `time +X` now runs `clock advance`; `time -X` stays a plain correction.
- `clock` counts down `Nm`/`Nh` conditions on PC/NPC files (`cond` itself still takes
  only `r`/`m`). Fired CLOCK lines stay in `## Clocks`; the brief only shows future ones.
- `travel` adds in-site legs at both ends when the parent route names an exit
  (`inn.door`): cellar → trapdoor → common room → front door → … `locked` refuses
  unless `--unlocked`; `DC N to notice` is a note. Encounter rolls are secret, one per
  4 h (2 h with `--night`). `passes:` = placed features within 100 ft of the path.
  Arrival light: `--light`, else `dim` with `--night`, else bright.
- **Lint severities:** errors = unparseable frontmatter, broken references (missing
  files, unknown route ends, a Layout that exists but lacks the exit row, On stage/Watch
  files missing); everything else is a warning, including an exit on a site with no
  Layout yet and in-site route ends written as prose ("back lane"). The Description
  compass check works per clause. Unsatisfiable Known-not-placed constraints are not
  checked yet (needs Phase 8 suggestions).
- Lint layer 2 runs after every successful `do` (touched files only); layer 3 in
  `scene enter --write`, `combat end`, `session archive` (refuses on errors without
  `--force`).
- History files: `## Summary`, `## Changes (public deltas)`, `## Behind the screen (GM)`,
  `## Table rules ended`, `## Turn log` (raw; `trace` reads it). Commit uses the repo
  root found by `git rev-parse` from the campaign folder.
- `world place` needs `--at` until Phase 8 (suggestions); negative coordinates as
  `--at=-10,0`. Places rows have no notes column, so `placed: …` goes in `effect`.
  Times convert at 24 mi/day × 0.8 and 3 mi/h × 0.8 (route check: 8 h travel days).
- `slugify` drops apostrophes (`Shackleton's Folly` → `shackletons-folly`, matching the
  generated files).
- `odds` takes `--adv/--dis` as well as a bare `adv` before any `--flag`.
- **Found in content (not tool bugs):** loop-open has Movements lines outside the
  schedule format (dolorous-pike, isidore-brahe, ptolemy, ursula-shackleton) and route
  exits on sites without a Layout; loop-play's world has `widows-ridge` and
  `castle-lark` footprints overlapping. Fix in Phase 11 / content review.

## Phase 9 — completion notes (2026-10-05)

Built and verified (283 tests + live runs through `table.py` with
`claude-sonnet-5-5` on scratch POC copies). Eleven skills in `.claude/skills/`
(`gm`, `character`, `level-up`, `scene`, `travel`, `combat`, `map`, `overrule`,
`spoilers`, `end-session`, `new-campaign`); `character`, `overrule`, `spoilers`,
`end-session`, `new-campaign` are `disable-model-invocation: true`. New tool support:
`gm.py scaffold <slug> --area "<name>" [--activate]` (what `/new-campaign` runs; Phase
11's `campaign new` builds on it) and `retcon … --session NN` (appends the Erratum line
to a past session's history, 04). `/end-session` passes the summary inline
(`session archive --summary "…"`): the table client forbids Write.

Live checks: all eleven appear as slash commands in an SDK session; `/gm` ran session
start → roster → opening scene with no permission prompt and no `[SCENE]`/`[GM BRIEF]`
on screen; a reported d20 went through `check … --d20 14`; a purchase moved coin;
`/spoilers` answered between the markers with Established labels and was recorded in
`sessions/spoilers.md`; `/end-session` archived (history file, log reset, in-session off);
`/map` pasted the `--player-view` render without the secret trapdoor.

Fixed from the live runs:
- **Gate:** escaped quotes inside a `do` string (`do "attitude mara wary \"why\"; log \"…\""`,
  the cheat sheet's own form) were denied; `command_ok` now honours `\"`/`\` inside double
  quotes and `_strip_root` no longer rewrites backslashes.
- `/gm` now says: use Glob to find files (it tried `ls`); paste tool lines **verbatim**,
  never a check against a DC the players can't know (it pasted a retyped
  `Insight 17 vs DC 12` for Mara's lie); no process talk ("while I settle the coins");
  files are canon for physical facts (it invented a bolted door where the files put a
  floor trapdoor); don't name NPCs the characters haven't learned.
- Promoting a rule to `rules/house-rules.md` is a between-sessions edit, not a table step.

For Phase 10 (dry run): watch for invented physical details and retyped roll lines;
the skills now forbid both, but only a longer run shows whether that holds.

## Phase 11 — completion notes (2026-10-05)

Built and verified (294 tests + a live `/campaign-new` run). `lib/encounter.py` (DMG
thresholds and multipliers as data, ENCOUNTER parser, item power, fitting),
`encounter.py` (`encounter budget|build|threat`, `danger`), `loot.py` (`loot roll`, `shop`,
restock), `loop.py` (`loop start|reset|status`), `campaign_cmd.py` (`campaign
new|fill|status|ledger`), skills `campaign-new`, `campaign-generate` (fork),
`campaign-scenario` (fork), `campaign-fill`, `campaign-status`, `rules/mechanics/time-loop.md`.
Decisions the spec left open:
- `build` picks the count whose adjusted XP is closest to the word's threshold at
  start-level (+ item power) × PCs present (ties → more monsters); party < 3 / ≥ 6 shift
  the multiplier a step. Item power rounds to half-steps, halves up.
- `threat` skips non-SRD rosters with a note (loop-play's glacier uses a **yeti**, not
  in SRD 5.1). The generators hand-wrote some `threat:` values that differ from the
  tool's (castle-lark 2,000 vs 1,600): run `encounter threat <place>` on authored places.
- `loop start` sets the clock and beds, then commits (`git add -A` from the repo root)
  and records the sha. `reset` also refills hit dice and resources (a new morning);
  files created after the baseline stay. `clock advance` restocks `daily`/`weekly`
  merchants at day boundaries and triggers `reset --by time` at `loop-end`.
- Selling pays half; a price-less row uses the DMG rarity band (`RARITY_PRICE`).
- `--via` values carry no leading slash (Git Bash rewrites `/x` into a path).
- `journal.Batch` remembers its campaign root (a command that switches campaigns,
  `campaign new` → `scaffold`, pruned the wrong journal before).
- **Live:** `/campaign-new` on a toy seed: the parent transcript contained no secret
  markers (138 fork messages excluded); the generated campaign linted clean. Open: the
  generator computed danger readings by hand because `danger` needs PCs — add an
  authoring form (`danger <place> --party 2xL1`) and point the skill at it.

## Restructure (2026-10-05)

`tools/` → `engine/`, `planning/` → `docs/design/`, `planning/.implementation/` →
`docs/build/`, campaigns → `campaigns/<name>/`, `.campaign` → `campaigns/.active`.
**Each campaign folder is its own git repository** (ignored by the engine repo);
`session archive` and `loop` commit there (they already used the nearest repo).
`lib/campaign.py` owns resolution (`CAMPAIGNS`, `CAMPAIGN_FILE`); `table.py` resolves the
same way; `scaffold`/`campaign new` create `campaigns/<slug>/` and `git init` it with the
engine repo's local identity. Tests run on frozen copies in `engine/tests/fixtures/`
(`poc`, `loop-play`), so playing a campaign never moves them. The PC template moved to
`engine/templates/pc.md`. `campaigns/dryrun` is a copy of the POC for Phase 10.
Line references in this plan predate the move; search for the quoted heading.

## Phase 12 — completion notes (2026-10-06)

- `engine/split.py`: form / cut / status / sense / task / join. `current.md` stays the
  active group's scene; a cut swaps the body and `SCENE_KEYS` (time, party-location,
  scene, light) and leaves campaign-wide frontmatter in place. Parked scenes live in
  `state/split/<group>.md`; deletions go through the journal hooks, so `undo` restores
  a join.
- `lib/campaign.py`: `split_info()`, `scene_pcs()` (the active group's PCs; used by
  tempo actors → `combat start`, `scene enter` notices, the Sight line, `move-party`)
  and settings `split-exchanges`, `split-combat-rounds`, `split-sense-ft`,
  `split-max-ahead`.
- `clock.advance`: world events on the earliest group clock, active PCs' conditions on
  their own, tasks finished, the ahead warning.
- Added during the build (now in 02/04/06): combat rounds are charged to the group's
  clock (combat never moved time before), `Play on` when the others are far ahead,
  and `split-max-ahead`. The exchange counter lives in `.gm/split-slice`, out of the
  brief hash.
- Sensing uses route distance; the design's "within sight range" clause is left to
  `split sense <group> on` (no reliable straight-line distance across frames).
- Verified by `engine/tests/test_split.py` (10 tests) and a hand run on a copy of
  dryrun (split, travel, 7-round fight with the other group 4,375 ft away, task, join,
  undo of the join).

## Phase 13 — completion notes (2026-10-07)

- New modules: `engine/conditions_ext.py` (`conc`, `deathsave`, `stabilize`, `exhaust`,
  plus the hooks `after_hp` / `after_cond` / `after_save` that `mutations` and `roll`
  call), `engine/supplies.py` (`light`, `eat`, ammunition, the clock's light countdown
  and dawn food check), `engine/lib/light.py` (source data, best carried source,
  effective light by radius). `campaign boundaries` lives in `campaign_cmd.py`; the
  four settings are in `campaign.SETTINGS` (`exhaustion: 2024` is read as a string).
- `lib/md.py`: a map value may be an inline list (`concentration: {spell: bless, until:
  Day 1 18:31, on: [Kael, Kira]}`, as 04 shows it) and `Doc.del_front(key)` removes a
  key that only appears while it means something. 04/06 parsing contract updated.
- Where state lives: files keep `concentration` / `death-saves` / `exhaustion` / `lit` /
  `fed`; in combat the Combatants row mirrors them (`conc bless 8r`, `dying ✓1 ✗2`,
  `exh 2`). `combat start` seeds the mirrors, `combat end` strips them before writing
  conditions back. A combatant without a file (an `srd:` row) keeps its targets and the
  owed save in `notes` (`conc→Kira`, `conc-save 12`).
- Decisions where the spec was silent:
  - Durations: in combat `1m` (or less) becomes `10r`, longer stays minutes/hours; out
    of combat `Nr` becomes minutes. With no duration given, the SRD spell's
    "Concentration, up to …" is used; none found → until ended. Effects are conditions
    named by the spell's slug (`hold-person`), because condition names are one word.
  - Round-based concentration ends at `combat end` (its targets' `Nr` conditions
    already did, per the Phase 4 rule).
  - Only `hp -N` / `dmg` / `atk` owe a CON save; `hp =N` downwards doesn't (only `=0`
    ends it, as 0 HP). The save is matched by ability `con`, the creature and the exact
    DC owed; an unmatched CON save changes nothing.
  - Massive damage also applies when damage drops a PC to 0 with at least the HP max
    left over (SRD); 06 now says so. `atk` crits count as two failures at 0 HP.
  - `deathsave` with no d20 is rolled by the tool only under `death-save-rolls: secret`
    or `dice-mode: gm-rolls-all`; otherwise it asks for the player's d20. A `death-saves
    dc N` table rule sets the success number. Dead PCs are skipped by `combat next`.
  - `stabilize --spell` (spare the dying) added; `--kit` spends a `healer's kit uses`
    Resources row of `--by` or of the first scene PC who has one.
  - Light: a hooded lantern unless the inventory has a `bullseye lantern`. Without
    positions (no combat/Stage, or `?`), a carried source lights the whole group
    brightly; with positions, its bright/dim radius from the carrier. Lights burn only
    on the clock (combat rounds don't move it, as before).
  - Counted inventory entries understand `quiver (20 arrows)`, `torches (4)`,
    `2 flasks of oil`, `5 days rations`; a container keeps `(0 arrows)`, a counted item
    at 0 is removed. `item Kira +3 arrows` / `-3 arrows` was added so the `combat end`
    offer is runnable as printed. Ammunition spends only the inventory (a matching
    `## Resources` row, like the POC Kira's `arrows`, is left alone).
  - `loose` still writes `Ammo spent:` (no inventory change) so `combat end` can name who
    fired. The line sits under the `## Combat` heading after the `Turn:` line.
  - Food: `eat` sets `fed:` when the PC eats; with no water it asks for the CON save at
    once. A PC without `fed:` isn't tracked until their first `eat`/long rest. At each
    dawn a PC behind gets one `Supplies:` line; each day past 3 + CON adds a level;
    `Water:` asks the save only when their waterskin is empty or missing. `--bought`
    is the price for each PC. `services` (a location tag) is new; the POC has none, so
    a default (`loose`) long rest in the POC now eats a ration.
  - Exhaustion 4 (2014) caps current HP at the halved maximum when it is reached; a
    long rest removes one level when the PC ate (or `supplies: off`, or in town under
    `loose`) and heals to the (possibly halved) maximum. Exhaustion also applies to
    `contest` rolls (ability checks).
  - Boundaries: 04 said campaign.md only, 06 said the POC uses current.md; followed 06
    (like every setting) and fixed 04. `campaign boundaries --none` records "asked,
    none"; with no flags it prints them. The session log gets only a `(GM)` count.
  - `!x` is logged as `x-card`, comes first in the hook output, and the brief/heartbeat
    follows as usual (the full brief's `Table:` line is part of the hash).
- Existing tests updated for spec'd output changes: `test_mutations` (the 0-HP note
  became the death-save write; `hp -99` from 11 now also reports massive-damage death)
  and `test_brief.test_shapes` (the `Table: boundaries not asked yet` line).
- Verified by `engine/tests/test_phase13.py` (36 tests: every Verify bullet, undo of
  every new command, `supplies: off` / `track-light: off`, LF and CRLF files).

## Phase 14 — completion notes (2026-10-07)

- New modules: `engine/explore.py` (travel activities, navigation and getting lost,
  foraging, watchers, forced march, `order`), `engine/lib/social.py` (the 02 DC table,
  flair steps, tastes, tiers as data) and `engine/social.py` (`check --ask` through
  roll.py, `state/social.md`, `social status|drop|wall`, the brief's `Social:` line, the
  intro's `[TELL THE TABLE]`), `engine/chase.py` (+ `engine/templates/tables/chase-urban.md`
  and `chase-wild.md`, original text), `engine/hazard.py` (`trap`, `hazard
  fall|breath|env`, the clock's hourly environment saves, breath → choking → 0 HP, the
  underwater attack rules), `engine/hiding.py` (`hide`, `seek`, the scene/combat
  compare, the attack reveal). Morale lives in `combat.py`; travel.py was split into
  `route()` (nothing moved) and `travel()`. The seven settings are in `campaign.SETTINGS`.
- **Defaults and the bookkeeping preference (c01465e):** foraging is food, so it follows
  `supplies` (off by default): nothing is counted or added, the plan says so. Nothing new
  counts per hour or per item by default: the hourly environment saves only run while
  `hazard env` sets an extreme environment, forced-march saves only print under
  `travel-detail: activities` (default `summary`). `getting-lost`, `social-dcs`,
  `creativity`, `social-wall`, `morale`, `chases` keep the spec's gameplay defaults.
- **Spec fixes (docs updated):**
  - Forced march: 06 said "DC 9+1/h from hour 9"; 02 and the PHB say DC 10 + 1 per hour
    past 8, so hour 9 is DC 11. 06 fixed.
  - Getting lost: 04 said only `trail`/`trackless`, 06 "never road/street/path". Now:
    every leg off the roads (trail, trackless, marsh, scree, `--overland`), never road,
    street, path or lane; 04 and 06 fixed. It applies only under `travel-detail:
    activities` (summary asks for nothing, as before).
  - XP: 06's `combat end` said fled foes count only with `--count-fled`; Phase 14 says
    fled and surrendered count as defeated. Marked ones (`+fled`/`+surrendered`) now
    count; `--count-fled` still counts every standing foe. 06 fixed.
  - Verify's chase bullet couldn't happen with the fixture CONs (3 + CON free Dashes,
    turns alternate); the test gives Veskar CON 8 (2 free) against one pursuer, and the
    plan's Verify text says so.
  - 06 had no way for the tool to know a pitch played to an NPC's `moved-by`: `--appeal
    <taste>` (+1 when it's a taste of theirs) and `--grates` (−1) added; `nothing` is −1
    on any flair pitch. Under `social-dcs: gm` the start is `--dc N`. With `--ask` the
    number after the skill is the player's total (a plain `check` keeps its DC).
  - The 04 `Morale:` line is keyed by the unit's singular name (`Morale: thug (half
    HP)`), so a group row splitting into members doesn't fire again.
  - Lost has to live somewhere: `party-location: "@lost"` (PCs too) plus `lost: to … ·
    at (x,y,0) world · bearing … (meant …) · terrain … · since …`; travel from there is
    straight-line cross-country in that frame. 04 documents it; lint accepts it.
  - TRAP lines: the area may stand after the id (`TRAP pit (cellar)`, as 04 shows) or
    before the colon like other Hidden lines; both parse. Breath is the one-word
    condition `holding-breath` (conditions are one word); the output says `holding
    breath 2m` as Verify asks.
  - `campaign new --set` accepts the table settings (so `/campaign-new` can record
    `social-wall=off`); before, only the campaign keys were accepted.
- Decisions where the spec was silent:
  - `--plan` writes nothing to the campaign; the activities go to `.gm/travel-plan.json`
    (scratch) so the resolving call needn't repeat them. Unnamed PCs keep watch.
  - Wrong bearing: d6 1–2 60° left, 3–4 60° right, 5 120° left, 6 120° right (never the
    intended one); 1d6 hours at trackless pace from where the first off-road leg starts
    (road legs before it are walked and timed; encounter rolls cover those routes).
    Navigation DCs: coast 5, sea 10, unset terrain 10 (DMG list otherwise).
  - Social: pitch tags are remembered per NPC (a `—` goal row holds pitches tried with
    no goal or while the wall is off), so "the same trick twice scores 0" holds without
    the wall. The DC call and the roll call log the `(GM)` sum once. Stage cues and
    tiers are `(GM)` log lines; the check line itself is public.
  - Morale units are a group row plus the members split off it (by singular name) or
    one creature; side triggers (leader down — `leader` in row notes — and half the side
    down) ask every standing unit once. Surrendered foes go On stage as `prisoner`;
    `fled`/`surrendered` aren't written back to files.
  - Chases: order is quarry first, then pursuers as named (no initiative); `chase next`
    Dashes by default (`--no-dash`, `--lose N`); `chase dash` is the extra (bonus-action)
    Dash. Only a `los` complication is applied by the tool; the rest are printed for the
    GM. Sight for the escape test: bright 120 ft urban / 300 ft wild, dim half, dark the
    pursuers' best darkvision. `chase end` moves the clock by the rounds (6 s, rounded up
    to the minute) even when not split; combat start and travel refuse during a chase.
  - Traps resolve `ABIL save DC N or …`, `+N to hit, …`, `fall N ft`, `NdM type` and
    conditions; anything else prints for the GM (lint warns). The victim defaults to the
    marching order's front, else the first PC. A PC's save is asked for and nothing
    changes until the total comes; an NPC disarmer's check is rolled.
  - Hidden: a Stage row has no conditions column, so out of combat `hidden N` sits in the
    creature's file (an srd-only Stage row can't hide). `scene enter`/`combat start`
    report who spots whom; they don't remove `hidden` (the GM acts on it). `seek` names
    who stays hidden only in a `(GM)` line. Group hide: success when at least half beat
    the watchers' best passive (strictly).
  - `gm.py` now parses with `parse_known_args`; a command that sets `take_extra` (check,
    trap) receives positionals given after options (`check … --ask major 22`, `trap
    trigger pit --who Kael 8`); every other command still rejects strays.
  - `geo.load`'s cache key includes the file's size and content hash: an mtime-only key
    missed rewrites within one clock tick (an intermittent `test_bestiary` failure).
- Gaps left: faction renown in the social DC (Phase 15); chase complications other than
  `los` aren't applied mechanically; a PC quarry's escape is closed by the GM (`chase end
  escaped`); `seek` doesn't check range; the plain-view warning only knows map terrain
  rows marked cover/obscured; `thin-air` is recorded only; out of combat, choking is a
  minute (the clock has no rounds); the heat save's water exemption is checked only
  while supplies are tracked; while `@lost` there is no scene packet (no place file).
- Existing tests updated: `test_intro` expectations unchanged (the TELL line sits after
  the `[INTRO …]` line, so `[WHY …]` stays last).
- Verified by `engine/tests/test_phase14.py` (43 tests: every Verify bullet and Guard,
  undo of every new mutating command, supplies-off foraging, lint, LF and CRLF trap
  lines, `campaign new --set social-wall=off`). Suite: 420 tests.

## Phase 15 — completion notes (2026-10-07)

- Items (all built): [x] (1) settings `inspiration`, `downtime`, `weather`, `encumbrance`,
  `renown`, `lingering-injuries` (+ `upkeep`, below) in `campaign.SETTINGS`; [x] (2)
  `engine/inspiration.py`: `inspire`, `--insp` on `atk`/`save`/`check` (social checks
  too); [x] (3) `engine/ready.py`: `ready … | fire | drop`, `--spell`, the `combat next`
  reminders and the lapse; [x] (4) `lib/magic.py` (tags, bonuses, SRD tags) +
  `engine/magic.py` (`attune`, `unattune`, `charge`, `identify`, the clock's recharge),
  `rest short --attune / --identify`, `srd item`, `pc card <pc>` for a written PC,
  `data/srd/5e-SRD-Magic-Items.json` via `fetch_srd.py --only Magic-Items` (the same 5e-bits
  source as the other SRD files; LICENSE.md regenerated); [x] (5) `engine/downtime.py`;
  [x] (6)+(10) `engine/allies.py`: `companion add|drop|list`, `hire`, companions in
  `combat start`/`next`/`end`, wages on the clock, hireling morale, `mount`/`dismount`,
  the prone falls; [x] (7) `engine/weather.py`; [x] (8) `lib/encumbrance.py` (weights,
  thresholds) wired into `turnstate.speed_of` (turn, move, chase), `travel`, `roll.py`, the
  party line and `pc card`; [x] (9) `engine/renown.py` + `state/factions.md`, the shift in
  `brief` and in `social.check` (the gap Phase 14 left); [x] (11) `engine/injury.py` + the
  `consider:` line in `conditions_ext.after_hp`; [x] (12) skills `/gm` (an "Optional
  subsystems" section + cheat sheet), `/combat` (readied actions, companions and
  hirelings, mounts, inspiration/wind/load), `/level-up` (magic items and attunement in
  `pc card`), `/campaign-new` (the new settings), `/travel` (the encumbered pace, weather).
- **Defaults and the bookkeeping preference (c01465e):** a new setting **`upkeep: off |
  on` (default off)** gates every coin charge over time: lifestyle costs, crafting
  materials and training fees in `downtime`, and hireling wages on the clock. Off, the
  line says what it would cost and nothing is taken; the Verify bullet's "spends 10 gp of
  lifestyle" holds under `upkeep: on` (the test sets it; the Verify text says so).
  `encumbrance`, `weather`, `renown` and `lingering-injuries` already defaulted off in 04
  and stay off; weather snuffs torches and sets `environment:` only while on. Kept the
  spec's gameplay defaults: `inspiration: advantage`, `downtime: light`, the attunement
  limit, companions in combat, mounts. Magic-item recharge has no setting (it only touches
  items tagged `recharge`).
- **Spec fixes (docs updated):**
  - Key clash: 04's scene key `weather:` is the setting's own key, and a campaign without
    campaign.md (the POC) keeps its settings in current.md, so the rolled text would read
    as the setting. The rolled weather is `weather-now:` (04, 06 fixed).
  - Destroy roll: 06 had the clock make "the destroy roll at 0"; the SRD rolls the d20
    when the last charge is spent, so `charge` does it then (02, 06 fixed).
  - Hireling morale: 02/06 say loyalty feeds morale, the Phase 14 Guard says morale never
    fires for the party side. Hirelings are the one party-side check: WIS save DC 20 −
    loyalty (loyalty 10 → DC 10, the foes' number); PCs and companions never check (02,
    06 and the Phase 14 Guard text fixed).
  - `pc card` only read drafts; "pc card shows load" and "/level-up: magic items in the
    card" need a written PC, so `pc card <pc>` without a draft prints the file's card.
  - "Bracketed numbers feed `pc` derivation": they are applied live (lib/creatures.py: AC,
    saves, the named weapon's attack/damage; the brief's AC; `combat start` seeds the row)
    and the file's `ac:` stays the base, so equipping or unattuning never needs a
    re-derive and can't be double-counted (04 says so).
  - `attune` without `--during-rest` refuses and names the `rest short --attune …` that
    does it (06 said only "it takes a short rest"). Attunement is checked before the rest
    is applied. 06 had no syntax for identify-by-rest or the SRD tags: `rest short
    --identify`, `srd item`.
- Decisions where the spec was silent:
  - `--insp` is spent after every refusal check (ammunition, reach), right before the
    roll; under `reroll` the given d20 is the reroll (`undo` the first one). Inspiration
    with disadvantage cancels as usual (and is still spent).
  - Readied text sits in the `conditions` cell (commas → `;`), a held spell as `· held
    <spell>` with `conc <spell> 2r` (long enough to reach the owner's next turn). `ready`
    and `ctrl` are combat-only mirrors (`strip_mirrors`); `mounted on`/`ridden by` are not
    (a rider stays mounted after the fight).
  - Magic items: the tags are the first parenthesis holding a known tag; bonuses count
    only on the `- Equipped:` line; an attack/damage bonus counts for the Attacks row the
    item names, else for every attack; `overrides` win. Recharge times: dawn, dusk,
    midnight, noon. `identify` keeps the item's own tags, else adds the SRD's.
  - Downtime: one row per `activity subject`; a finished craft goes into the pack and its
    row is removed; training adds a Features line; `full` complications are `(GM)` lines.
    Each call advances the clock (`--no-clock` for parallel PCs). Under `upkeep: on` a
    purse that can't cover the cost is refused up front (`inventory.purse`/`pay`, change
    made in silver and copper).
  - Companions keep the SRD AC; their position starts `?` like everyone's; HP goes back to
    the Companions row at `combat end`. A `mount` companion of a mounted PC gets `ridden
    by`; an in-combat `mount` moves the mount's row and init right after the rider.
  - Weather is rolled once, for the last dawn crossed (not per day of a long skip); the
    roll detail is a `(GM)` log line; climates have a base °F (06 lists them); outdoors =
    not in a site of type building/dungeon/cave/… or tagged `indoors`/`underground`; the
    Perception effects are notes on Perception checks (sight vs hearing can't be told).
  - Encumbrance: aliases map common pack names (silk rope, hooded lantern, flask of oil,
    rations) to SRD rows; an unknown entry weighs 0 and is listed on the card; `50 ft` is
    a length, not a count. Travel scales only `--by foot`.
  - Renown: `who` is `party` or the PC's first name; `notes` keeps the last reason; the
    per-pc brief lists each PC whose standing shifts the attitude. The `no, and` hint
    still lowers the NPC's own (unshifted) attitude.
  - Injuries: `| roll | result | effect | cure |`, die = highest roll, `--roll N` for a
    physical die; the result is appended to Features with `(injury)`.
- Gaps left: forced movement of a mount isn't detected (the GM asks the DEX save); rider
  and mount positions aren't synced (`pos` both); summons only via `companion add` (no
  duration); one `weather-now` for the whole party while split; Large/Tiny carrying
  capacity multipliers aren't applied; vehicles beyond the existing `travel --by` (cart /
  boat HP and AC rows) aren't modelled; research/recuperate outcomes are the GM's; no
  lint check for `## Companions`, `## Downtime` or `state/factions.md` rows.
- Existing tests: none changed (the defaults keep every earlier output).
- Verified by `engine/tests/test_phase15.py` (37 tests: every Verify bullet, undo of every
  new mutating command, both Guards — the same command script with every subsystem
  switched off by hand prints and writes exactly what the defaults do, and with renown,
  injuries and basic encumbrance on but unused prints the same; no injury or downtime
  table ships with the engine — plus an LF PC file). Suite: 457 tests.
