# Claude GM — D&D 5e adventure run by Claude Code

State lives in markdown; Claude Code plays Game Master via skills; every number and
every write goes through the engine (`engine/gm.py`).

## Layout

| folder | what |
|---|---|
| `engine/` | the tools: `gm.py` (every command), `table.py` (the players' console), `space.py`, `lib/`, `templates/`, `tests/` (+ frozen `tests/fixtures/`) |
| `.claude/` | project settings (hooks, permission allowlist) and the GM + authoring skills |
| `campaigns/` | one folder **and git repository** per campaign (`poc`, `loop-play`, `loop-open`, `dryrun`, …); `campaigns/.active` names the default |
| `rules/` | condensed rule sheets the GM reads; `rules/mechanics/` for optional campaign mechanics |
| `data/srd/` | SRD 5.1 data (CC-BY-4.0, see its LICENSE.md) |
| `engine/templates/tables/` | random tables; `carousing.md` collects three community tables with credit to their authors (see its Credits; ask and yours comes out) |
| `docs/design/` | the design (01–07) · `docs/build/` the build plan, status and notes |

## Running

- Play: `python engine/table.py --campaign <name>` (narration only; `/gm` starts the session).
- GM's eye / prep: plain `claude` in this folder; `python engine/gm.py --campaign <name> <command>`.
- Tests: `python -m unittest discover -s engine/tests`.
- Needs Python 3.10+; `pip install claude-agent-sdk` for `table.py` only. Trust this folder
  in Claude Code once (open `claude` here and accept) so the allowlist applies.

## Player commands

When the table opens, the console prints the short list below (and posts it to Discord
when the bridge is on). Type `/commands` (or `/help`) at the console or on Discord for
the detailed version. Neither reaches the GM or costs a turn.

| type | what it does |
|---|---|
| `Kira: I check the trapdoor` | act or speak as your character; add `rolled 16` to roll ahead |
| no name | table talk to the GM: questions, "what do I see?" |
| `Kira: I climb (OOC: how long is our rope?)` | an out-of-character aside with an action: the GM narrates first, then answers in `(…)` at the bottom |
| `(OOC: can we break at 9?)` · `OOC: …` · `/ooc …` · `[ooc …]` · `((…))` | a whole line out of character: answered in `(…)`, the story doesn't move |
| `/table-talk …` (`/tt …`) | chat with the other players; the GM never sees it |
| `/overrule …` | retcon something, or add a table rule (honor system) |
| `/spoilers …` | ask about the secrets behind the screen, or a "what if" |
| `!x` | X-card: the GM rewinds and steers away, no questions |
| `/character …` · `/level-up` · `/map` | make or change a character · level up · show the map |
| `/end-session` | wrap up and save |
| `/execute-queue` | Discord: send everything waiting in the queue to the GM; add it to a line (`I open the door /execute-queue`) to queue that line and send it all |
| `/queue on\|off` | Discord: turn the queue on or off (or ask the GM: "OOC: turn the queue off") |
| `/commands` | the detailed list |

Host console only: `:as Kira` (default speaker), `:q` / `:send` (or an empty Enter) /
`:edit n text` / `:drop n` / `:clear` (the queue), `:discord queue|auto|off`,
`:gm-view on|off`, `:quit`.

## Discord setup

Remote players can join through one Discord channel: they type there and read the
narration there, while the person running `table.py` stays the host. One-time setup:

1. **Install the library** into the Python that runs the table:
   `pip install discord.py` (2.x). Without it the table runs normally, console only.
2. **Create the bot.** Go to <https://discord.com/developers/applications> →
   **New Application** → name it → **Bot** in the sidebar. Click **Reset Token** and copy
   the token (you see it once). On the same page, under *Privileged Gateway Intents*,
   turn on **Message Content Intent** and save. Without it the bot can't read messages.
3. **Invite it to your server.** **OAuth2 → URL Generator**: tick the `bot` scope, then
   the permissions **View Channels**, **Send Messages**, **Read Message History** and
   **Add Reactions**. Open the generated URL, pick your server, authorize. (You need
   Manage Server on that server.)
4. **Get the channel id.** In Discord: **User Settings → Advanced → Developer Mode** on.
   Right-click the channel the game will use → **Copy Channel ID**. If the channel is
   private, add the bot to it (channel settings → Permissions).
5. **Store the token** (never in a campaign file, never committed). Either paste it as
   the only line of `.local/discord-token` in this folder (git-ignored; create the
   folder), or set it in the shell that starts the table:
   PowerShell `$env:DND_DISCORD_TOKEN = "…"`, bash `export DND_DISCORD_TOKEN=…`
   (the variable wins). The client removes it from the environment so the GM's
   session never sees it.
6. **Write `campaigns/<name>/discord.md`** with the channel and who's who:
   ```markdown
   ---
   discord: queue          # off | queue | auto
   channel: 123456789012345678
   debounce: 4             # auto mode: seconds of quiet before a batch is sent
   ---
   | discord user | player |
   |--------------|--------|
   | sam_the_bard | Sam    |
   ```
   `discord user` is the Discord **username** (not the display name; right-click a
   member → Copy User ID also works). `player` matches the `player:` on that person's
   PC sheet, so a player with one PC can type without the name prefix. A row added
   while the table runs counts from that person's next message.
7. **Start the table:** `python engine/table.py --campaign <name>` (uses `discord:` from
   the file) or `--discord queue|auto` for one run. The terminal says
   `[discord: connected — queue mode]` and the channel gets `[the table is open]` and
   the command list.

**Queue vs auto.** In **queue** mode Discord lines wait in a numbered queue; the bot
posts what's waiting, and the host (an empty Enter or `:send`) or any player
(`/execute-queue`) sends it as one turn. In **auto** mode lines go to the GM in batches:
those posted while the GM is replying go when it finishes, otherwise after `debounce`
seconds of quiet. Switch any time: `/queue on|off` on Discord, `:discord queue|auto` at
the console, or just ask the GM ("OOC: turn the queue off"). The host's own typed lines
never queue; they go straight to the GM and are echoed to the channel. `!x` always
skips the queue. Reactions on Discord: ✅ sent, 🗑️ dropped, ✏️ edited by the host.

**Troubleshooting.** `login failed` → the token is wrong or was reset (step 2/5).
`turn on the bot's Message Content intent` → step 2. `can't see the channel` → wrong
id, or the bot lacks access to a private channel (step 4). `ignoring @name (not on the
map)` → add their username to `discord.md` (step 6). Errors are logged, token scrubbed,
to `campaigns/<name>/.gm/client.log`. More detail: `docs/design/06-tools-spec.md` →
Discord bridge.

## Build phases

Status and notes: `docs/build/README.md`. Done: design, POC content, tools (Phases 1–7),
GM skills (9), campaign authoring + mechanics (11). Left: Phase 10, the verification
sweep and dry run (in `campaigns/dryrun`), and Phase 8 (deferred spatial features).

## Open decisions

1. **Edition:** assuming 2014 5e rules unless told otherwise.
2. ~~Secrets~~ **Decided:** honor system for files (the driver doesn't open them); play
   runs through `engine/table.py`, which shows only narration (docs/design/01 → Secrets).
3. ~~Dice~~ **Decided:** players roll their own d20s and report them; the GM rolls the rest via `gm.py`.
4. **Table size:** how many players/PCs will the real campaign have?
5. ~~Git~~ **Decided (2026-10-05):** `dnd-adventure/` is the engine repo (branch `main`),
   published at https://github.com/adammathews2003-png/ClaudeDndRunner. Each campaign
   under `campaigns/` is its own git repository: `gm.py session archive` and the time
   loop commit there, never in the engine repo (docs/design/05, item 4).
6. ~~Tools~~ **Decided:** stdlib frontmatter parser; hybrid brief injection; lint at
   write time, per batch on touched files, and fully at scene/session boundaries.
   Secrets in tool output: hidden by the table client (`docs/design/06-tools-spec.md`).
7. ~~Advancement~~ **Decided (2026-10-05): per campaign.** `advancement: milestone`
   (default; GM announces levels, `gm.py pc level-pending`) or `advancement: xp` (PHB
   thresholds flag level-ups automatically). **XP is tracked by default in both modes**
   (`xp-tracking: on`; `gm.py xp award`, combat XP offered at `combat end`) so the total
   is available for other thresholds or a later switch; `xp-tracking: off` disables it.
   Absent PCs' share is a campaign setting (`xp-absent`).
   HP per level **decided: max or roll**, chosen once per character (`hp-method`),
   revisited only if the player asks (house rule).
8. ~~Map model~~ **Decided (2026-10-04):** nested coordinate frames: world (mi) → area (ft)
   → site (5-ft cells), north-up, offset-only, same-unit nesting to any depth. Each
   route is stored once in the parent frame; sites may carry their own routes. The GM
   addresses places and creatures by name (`@bar`, `--to Veskar`) and the tools do the
   geometry. Directions, distances and travel times are derived by tools, never hand-written
   (docs/design/01 → World geometry, 04 → Location files). Every campaign has a world file
   from creation: known places are placed or constrained, and the rest is open frontier
   filled in by generation, player choice or imports (docs/design/02 → The open world).
