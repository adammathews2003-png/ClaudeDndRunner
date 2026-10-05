# Implementation plan — Claude GM tools, client and skills

How to use this file: pick the next unticked phase in `README.md`, open a fresh session,
and give it only that phase (plus Phase 0, which every phase assumes). Each phase lists
what to read, what to build, the contracts later phases depend on, how to verify, and the
guards. Build by copying what the planning docs specify, cited by file and line; where a
phase has to decide something the docs leave open, the decision is written here so every
session makes the same one.

Conventions used throughout:
- Paths are relative to `dnd-adventure/` unless they start with `~` or the repo root is
  named. The git repo root is one level up (`ProjectX/`), branch `main`.
- `04:68-130` means `planning/04-file-formats.md` lines 68–130 as of commit `0bbce3d`.
- Run tools as `python tools/gm.py …` from `dnd-adventure/` (Python 3.11.9 is installed;
  both `python` and `py` resolve to it).
- Every phase ends with its tests passing and a commit. Commit messages end with the
  attribution line the session is given.

---

## Phase 0 — Documentation discovery (consolidated; read before any phase)

### 0.1 Sources that govern the build
| Doc | What it owns | Read when |
|---|---|---|
| `planning/06-tools-spec.md` (773 lines) | every command's syntax, output, reads/writes; lib layout L60-81; build order L740-755; prohibitions | every tools phase |
| `planning/04-file-formats.md` (608 lines) | every file's frontmatter, sections, table header rows; terrain/route/constraint vocabularies; travel-time math; tool-owned files L600-608 | Phases 1, 4, 6, 7 |
| `planning/02-gm-agent-design.md` (548 lines) | skills table L8-20; session start L33-50; intake L52-108; level-up L110-140; dice L167-176; behind the screen L178-228; overrule L230-305; spoilers L307-372; spatial L397-486; open world L488-529; timeliness L538-548 | Phases 2, 5, 6, 9 |
| `planning/01-architecture.md` (187 lines) | directory layout + `.campaign` L10-34; turn loop L55-79; scene tempo L84-104; world geometry L106-148; session lifecycle L150-160; secrets L162-187 | Phases 3, 4, 9 |
| `planning/05-hard-problems.md` | rules tools must enforce: #1 files win L6-15, #2 real RNG L17-22, #4 journal/undo + git L35-41, #5 lint L43-52, #6 stubs L54-60, #7 time L62-70, #8 compaction hook L72-77, #14 permissions L118-125 | Phases 1, 2, 7 |
| `rules/house-rules.md` | ties-go-to-PC L24-32; HP max-or-roll L13-21; dice L7-10; overrules L35-38 | Phases 2, 6 |
| `rules/combat-basics.md` | grid model L29-42 (walls at L38-41); movement L43-51; areas L52-85 | Phase 4 |
| `tools/space.py` (542 lines) | the one built tool; its parsing is what `md.py` must replace | Phases 1, 4, 5 |
| `poc/` | the fixture campaign (copied for tests); see 0.5 | all |

### 0.2 Hard constraints (from 06, verbatim or near)
- Python 3 **stdlib only**, no install step (06:44-46). No PyYAML (06:759). The game
  tools never import the Agent SDK; only `table.py` does (06:76, 06:648).
- One entry point `python tools/gm.py <command>`; `space.py` stays standalone and is also
  reachable as `gm.py space …` (06:27-29).
- `do "a; b; c"` runs left to right; a failure stops the batch, earlier steps stay
  applied and are listed (06:30-32). Writes are atomic: temp file + rename (06:33-34).
- Every mutation auto-logs a delta line into the open turn block (06:35-36, 06:156-168).
- Output is short bracket lines; `--json` only on request (06:37-43). `--seed N` makes
  any command deterministic; RNG is `random.SystemRandom` otherwise (06:44-45).
- Every command < 200 ms (06:49).
- `.campaign` holds the active campaign folder name; `--campaign <dir>` overrides
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
| tool-owned | 04:600-608 | `.campaign`; `<campaign>/.gm/{journal/, brief-hash, drafts/, session-id, client.log}`; `tables/<slug>.md` `\| roll \| result \|` |

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
- Exists: `planning/`, `rules/` (4 sheets), `poc/` (locations ×5, npcs ×3, pcs ×3 incl.
  `_template.md`, scenario ×1, `sessions/{session-current.md, spoilers.md, history/}`,
  `state/{current.md, table-rules.md}`), `tools/space.py`, `README.md`.
- Does **not** exist yet: `tools/lib/`, `tools/gm.py`, `tools/table.py`, `tools/tests/`,
  `data/`, `.claude/` (no settings.json, no skills), `.campaign`, any `.gm/`.
- Repo root `.gitignore` already ignores `__pycache__/`, `*.pyc`, `.gm/`.
- `poc/state/current.md` has `in-session: false`, `Tempo: calm`, `## Combat` =
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

**Permissions** (https://code.claude.com/docs/en/permissions.md): `Bash(python tools/gm.py:*)`
and `Bash(python tools/gm.py *)` are equivalent prefix rules; project file is
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
5. `tools/space.py` has no `secret` handling yet (04:303 requires it for
   `--player-view`). Phase 4/5 adds it; note it in the docstring until then.

### 0.8 Anti-patterns (grep for these at every verification step)
- `import yaml`, `import requests`, any non-stdlib import in `tools/` except
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
the test harness with a fixture copy of `poc/`, and the spec nits from 0.7.

**Read first:** 06:25-58 (principles), 06:60-92 (layout + md.py contract), 06:156-168
(turn blocks), 06:219-222 (journal), 06:754-755 (tests), 04:7-21, 04:600-608,
05:6-15, 05:35-41, 05:62-70; `tools/space.py` L29-55 (`parse_point`, `table_rows`: the
behaviour `md.py` must reproduce) and L117-136 (`State.__init__`).

**Build:**
1. `tools/lib/__init__.py` (empty) and `tools/lib/md.py` with this contract:
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
2. `tools/lib/campaign.py`: `root()` (reads `dnd-adventure/.campaign`, honours
   `--campaign`), `path(kind, slug)` for `pcs/npcs/locations/scenarios/tables`,
   `pcs()`, `npcs()`, `locations()` (loaded `Doc`s), `resolve(name, state=None)`
   implementing the lookup order 06:55-58 and raising `Ambiguous(candidates)`,
   `slugify(name)`, `who_is_at(site_or_area)` by grepping `location:` (04:307-308).
3. `tools/lib/journal.py`: `Batch` context manager that snapshots before-images of every
   file a command opens for writing into `<campaign>/.gm/journal/<NNNN>/` with a
   `manifest.json` (`files`, `command line`, `turn`, `overrule: bool`), keeps the last
   50, and exposes `touched` (for lint layer 2, 06:431-434). `undo()` restores the
   latest batch and appends `undo turn N step M` to the log (06:221-222). A
   `log_delta(text, gm=False)` writer that opens `[turn N]` on the first delta after a
   `log` and appends `  - ` lines (06:156-168; `(GM)` prefix when `gm=True`).
4. `tools/lib/gametime.py`: `parse("Day 1 19:30") -> (day:int, minute:int)`,
   `fmt(day, minute)`, `add(t, "+4h30m" | "+1d" | "to 06:00" | "to dawn")`, named times
   from 06:377-378, `period(t)` (dawn/morning/…/night for the brief line), and a
   `between(t, start, end)` helper for `## Movements` windows that may wrap midnight.
5. `tools/gm.py`: argparse with subcommands registered by the modules that exist
   (`space` forwards to `space.py`), global `--campaign`, `--seed`, `--json`; `do
   "<cmd>; <cmd>"` splits on `;`, runs each through the same dispatcher inside one
   `Batch`, stops on the first failure and prints which step failed and which earlier
   steps applied (06:30-32). Unknown commands print the usage line. Nothing else yet.
6. `tools/tests/`: `conftest.py`-free `unittest` layout (stdlib). `fixture.py` copies
   `poc/` to a temp dir per test and points `.campaign` at it. Tests for every md.py
   method against real POC files (round-trip a file unchanged byte-for-byte after
   `load`→`save`; `set_front` on a key with a comment keeps the comment; table edits
   keep widths; CRLF and LF inputs both round-trip), gametime arithmetic including
   midnight wrap, campaign resolution (`Kael`, `kael`, `ka` ok; `k` ambiguous), journal
   snapshot/undo, `do` stop-on-failure.
7. Write `dnd-adventure/.campaign` containing `poc`.
8. Apply the doc edits in 0.7 items 1–4.

**Verify:** `python -m unittest discover tools/tests` green; `python tools/gm.py do
"nonexistent"` reports the failing step; `grep -rn "import yaml\|requests" tools/`
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
"random\." tools/ | grep -v dice.py` is empty.

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
   (only when a Stage/Combat table exists), `Party:`, `Rules:`, `Watch:` + `Next
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
         "Bash(python tools/gm.py:*)",
         "Bash(python tools/space.py:*)",
         "Bash(py tools/gm.py:*)",
         "Bash(py tools/space.py:*)"
       ]
     },
     "hooks": {
       "UserPromptSubmit": [
         { "hooks": [ { "type": "command", "command": "python tools/gm.py brief --hook", "timeout": 10 } ] }
       ],
       "SessionStart": [
         { "matcher": "startup|resume|compact|clear",
           "hooks": [ { "type": "command", "command": "python tools/gm.py brief --hook --long", "timeout": 30 } ] }
       ]
     }
   }
   ```
   Working directory for hooks is the project dir Claude Code was started in; the plan
   assumes sessions start in `dnd-adventure/`. If the repo root is used instead, prefix
   `command` with `cd dnd-adventure &&` (check `cwd` from the stdin JSON at build time).

**Verify:** `python tools/gm.py brief` on the POC prints ≤ 20 lines matching the
06:227-234 shapes; piping `{"hook_event_name":"UserPromptSubmit","prompt":"hi"}` to
`brief --hook` prints nothing while `in-session: false`, the full brief once it's
`true`, and the heartbeat on the second identical call; a `SessionStart` JSON with
`"source":"compact"` prints the long form; a 200-ms timer around the hook. Then start a
real Claude Code session in `dnd-adventure/`, set `in-session: true`, and confirm the
brief appears as a system reminder (hooks debug log) and that `python tools/gm.py roll
1d20` runs without a permission prompt.

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
L29-51; `tools/space.py` whole file (it already does walls, doors, hazards, `--to`
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
   back, sets `status: dead`, restores `(not in combat)`, ends `combat` rules. `--frame`
   and `reframe` are Phase 8; reject with "not built yet".
5. `srd monster|spell|condition <name> [--write <npc file>]` (06:347-355) and a one-off
   `tools/fetch_srd.py` (stdlib `urllib`) that lists the 5e-bits repo directory first,
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

**Goal:** `tools/table.py`, the console players play in, and `space.py map
--player-view`.

**Read first:** 06:632-713 in full; 02:178-228 (what narration may never contain,
what the client hides); 01:162-187; 0.6 Agent SDK facts; the five build-time checks
at 06:707-713.

**Build:**
1. `space.py map --player-view [--from X]`: drop hidden combatants and `secret` terrain
   (06:324-327); everything else identical. `/map` skill uses only this form.
2. `tools/table.py` (the only file allowed to import `claude_agent_sdk`): CLI
   `[--campaign poc] [--new] [--model <id>] [--gm-view]` (06:645). Session: resume
   from `<campaign>/.gm/session-id` or start new, then auto-send `/gm` (06:648-656).
   Options: `cwd=dnd-adventure/`, `setting_sources=["project"]`, `allowed_tools=
   ["Bash(python tools/gm.py:*)", "Bash(python tools/space.py:*)", "Read"]`,
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

**Verify (the five checks at 06:707-713, each recorded in `tools/tests/CLIENT-CHECKS.md`):**
message types stream as expected; project hooks fire inside the SDK session, including
`SessionStart` after a forced compaction; plugins/memory absent; a disallowed tool is
denied silently and logged; `/gm` and `/overrule` arrive as skills. Plus: a run through
the POC opening scene shows only narration on screen, and `gm-view` shows the brief.
If a check fails because the SDK can't do it, fall back to the headless CLI (0.6) and
record why.

**Guards:** `grep -rn "claude_agent_sdk" tools/` returns only `table.py`; nothing in
`table.py` writes campaign files; GM-level text never reaches the console (02:178-228).

---

## Phase 6 — Character tools (2a.5b)

**Goal:** `gm.py pc draft|check|card|write|edit|level-pending|levelup|roster` and the
SRD class/race/equipment data behind them.

**Read first:** 06:559-630; 02:33-50 (session start), 02:52-108 (intake loop), 02:110-140
(level-up); 04:352-424 (PC file, derived fields, `overrides`); `rules/house-rules.md`
L13-21 (HP max-or-roll, `hp-method`); `poc/pcs/_template.md` and `kael-ashford.md`.

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

**Verify:** `pc draft grask --set race="half-orc" class=barbarian level=3
subclass=berserker --equip "greataxe; 4 javelins; explorer's pack"` then `pc check`
matches the DERIVED line at 06:581-582 (speed 30, prof +2, darkvision 60, d12, saves
STR/CON); `pc write` produces a file that `md.load` round-trips and that has all 26
frontmatter keys in template order; `pc level-pending kael --to 4` + `levelup --plan`
lists an ASI choice; `--apply` with `hp-method: max` raises Kael's max HP by 8 + CON
and adds a Journal line; `overrides: {ac: 17}` survives `edit`.

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
   -m "session NN"` from the repo root.
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
`character`) so only `/name` invokes them; `allowed-tools: Bash(python tools/gm.py:*)
Bash(python tools/space.py:*) Read`. Bodies:
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
- `/new-campaign`: copy templates from 04, `world init <area>`, write `.campaign`.

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

**Read first:** `planning/07-campaign-authoring.md` in full; 06 → Campaign authoring,
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

## Phase 10 — Verification sweep and dry-run readiness (README Phase 3)

1. **Anti-pattern grep** over `tools/` and `.claude/` for everything in 0.8; all empty.
2. **Full test run** (`python -m unittest discover tools/tests`) green on a clean
   checkout with CRLF and with LF working trees (toggle `core.autocrlf` in a temp clone).
3. **Spec parity:** for every command heading in 06 (0.4 list), `python tools/gm.py
   <command> --help` exists and its flags match the heading; record misses in
   `tools/tests/PARITY.md` and either build or amend 06 (never leave the two apart).
4. **Timing:** every command on the POC < 200 ms (06:49); hook < 100 ms.
5. **Secrets leak check:** run the POC opening through `table.py` and diff the console
   transcript against the GM view; the console must contain no `[SCENE]`, `[GM
   BRIEF]`, `(GM)`, file path, DC, or beat name (02:178-228).
6. **Dry run** per `README.md` Phase 3: two pregens + one new PC via `/character`,
   a tense scene at the inn placed by name, the inn fight with a wall and the stairs,
   `travel` to the mill, one `/overrule`, one `/spoilers`, `/end-session`. Note every
   stall or drift in `planning/.implementation/DRY-RUN-NOTES.md`; tighten skills, not
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
