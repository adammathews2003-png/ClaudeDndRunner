# Table client — live build-time checks (docs/design/06 → Table client; plan.md Phase 5)

Run 2026-10-05 against a scratch copy of `poc/` with `in-session: true`, Claude Code
2.1.289, `claude-agent-sdk` 0.2.163 (Python 3.11, Windows 11), model
`claude-haiku-4-5-20251001`. Scripts: one-off, in the session scratchpad (not kept);
re-run them by hand if the SDK or Claude Code changes.

## 0. Launching the CLI on Windows — needed a fix
The SDK refuses npm's `claude.CMD` shim (cmd.exe argument injection). `table.find_cli()`
points `cli_path` at the `claude.exe` the shim wraps
(`%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe`);
`CLAUDE_CLI_PATH` overrides.

## 1. Message types and streaming — PASS
With `include_partial_messages=True` a turn yields `StreamEvent`s
(`message_start`, `content_block_start`, `content_block_delta` (`text_delta`),
`content_block_stop`, `message_delta`, `message_stop`), then the full
`AssistantMessage`(s), `UserMessage` (tool results), `SystemMessage`s (`init`, `status`,
hook events), a `RateLimitEvent`, and `ResultMessage` (carries `session_id`). The client
prints text deltas line by line and nothing else; a `tool_use` content block start
triggers the one activity line.

## 2. Project hooks in SDK sessions — PASS
`SessionStart` (startup and resume) and `UserPromptSubmit` fired from
`.claude/settings.json`; the model quoted the `[GM BRIEF]` header line. Sending
`/compact` as a prompt compacted (`compact_boundary`, trigger manual) and fired
`SessionStart:compact`, which re-injected the long brief (the model quoted its
`Summary:` line afterwards).

## 3. User-level plugins and memory — PASS (after a fix)
`setting_sources=["project"]`: no MCP servers, no user plugins (only Claude Code's
builtin `cc-plugin-*`), no claude-mem; the model saw no memory index. But the `init`
message still listed an **auto-memory path** for `dnd-adventure/`, so play could have
written memories. Fix: the client sets `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` for its
session; `init` then reports no memory path. (Design sessions are unaffected.)

## 4. Deny-by-default with a log — PASS (after a fix)
First run: `whoami` via Bash **ran** — Claude Code auto-approves read-only shell
commands, so they never reach `can_use_tool`. Fix: a PreToolUse hook in the client
(`table.decide()`) gates every tool call: single `python engine/gm.py|space.py …`
commands (no unquoted `; & | < >`, newline, `$(`, `${` or backticks; a leading `cd` into
exactly the game folder and absolute paths to `engine/` are accepted), Read/Glob/Grep
inside `dnd-adventure/`, and Skill. Re-run: `whoami` (Bash and PowerShell),
`python engine/gm.py … ; whoami` and a `Write` were denied and each logged to
`<campaign>/.gm/client.log`; `python engine/gm.py --seed 3 roll 1d20` ran without a
prompt (`[1d20: 8]`). `can_use_tool` stays as a backstop for anything that would prompt.
Note: the GM *mentioned* the denials in its reply. The `/gm` skill (Phase 9) must tell it
to retry in the allowed form silently; the denial message already says so.

## 5. Slash commands as prompts — PASS
A temporary project skill (`.claude/skills/zz-ping`, removed afterwards) answered when
sent as `/zz-ping`; `/compact` worked the same way. `/gm`, `/overrule`, `/spoilers` will
arrive the same way once Phase 9 writes them.

## End-to-end (POC opening, no `/gm` skill yet)
`printf 'Kira: …\n:quit\n' | python engine/table.py --campaign <copy> --new`: the screen
showed the banner line, one `The GM consults their notes…`, the GM's narration with the
public roll line it pasted (`d20 8+5=13 vs DC 12 — SUCCESS by 1`), and `[saved]`. No
command lines, tool output, thinking or brief. The GM's first, wrong command
(`python gm.py …`) was denied and logged; it retried correctly. `--gm-view` on the
resumed session showed the `SessionStart:resume` and `UserPromptSubmit` briefs, the
tool calls and their results.
