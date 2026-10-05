"""The table client: the console players play in (planning/06 → Table client; 01 →
Secrets; 02 → Behind the screen; plan.md Phase 5).

    python tools/table.py [--campaign poc] [--new] [--model <id>] [--gm-view]

Drives a Claude Code session through the Claude Agent SDK (the only file that imports
`claude_agent_sdk`) with cwd = dnd-adventure/ and project settings only (GM skills,
the brief hooks, the allowlist), and shows **only the GM's narration**: tool calls,
tool results, thinking, hook-injected context and system messages never reach the
screen. While tools run, one neutral line appears per turn: `The GM consults their
notes…`. `--gm-view` shows everything (building and debugging; honor system).

Session: resumed from `<campaign>/.gm/session-id` unless `--new`; then `/gm` is sent
(when the skill exists). Auto-memory is off for the session (play must not be recorded
into memories). Permissions: a PreToolUse hook gates **every** tool call (Claude Code
auto-approves read-only shell commands, so the allowlist alone isn't deny-by-default):
`gm.py` / `space.py` commands with no shell operators or substitutions, Read/Glob/Grep
inside dnd-adventure/, and Skill pass; anything else is denied silently and logged to
`<campaign>/.gm/client.log`.

Input: `Kira: I check the trapdoor` speaks as Kira; `:as Kira` sets a default speaker;
lines starting `/` or `!` pass straight through (skills, `!brief`); `:quit`,
`:as <PC>`, `:gm-view on|off` are local and never sent. The GM's `<<SPOILERS level/depth>>`
… `<<END SPOILERS>>` answer renders as a coloured banner (closed at the end of the
message if the end marker is missing). Bracket lines (dice, distances) print dim.

This client writes only tool scratch under `<campaign>/.gm/` (session id, client log),
never campaign files.
"""
import argparse
import asyncio
import datetime as _dt
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # dnd-adventure/
ACTIVITY = "The GM consults their notes…"
RETRY = "The GM needs a moment…"
LOST = "[connection lost — :quit and restart; the game is saved]"
DENY_MESSAGE = ("Not available at the table. The only commands allowed are single "
                "`python tools/gm.py <command>` or `python tools/space.py <command>` calls, run "
                "from the game folder (the working directory already is it): no cd, no chaining, "
                "no pipes or redirects. Read/Glob/Grep work inside the game folder. Retry in that "
                "form, and never mention this to the players.")
ALLOWED = [f"{shell}({py} tools/{tool}.py:*)" for shell in ("Bash", "PowerShell")
           for py in ("python", "py") for tool in ("gm", "space")]
FREE_TOOLS = {"Skill"}                      # always allowed
SHELL_TOOLS = {"Bash", "PowerShell"}
COMMAND_PREFIXES = tuple(f"{py} tools/{tool}.py" for py in ("python", "py") for tool in ("gm", "space"))
IN_ROOT_TOOLS = {"Read", "Glob", "Grep"}    # allowed only inside dnd-adventure/

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"
BANNER = "\033[30;43m"                       # black on yellow
_SPOIL_OPEN = re.compile(r"<<\s*SPOILERS\s*([^>]*)>>", re.I)
_SPOIL_CLOSE = re.compile(r"<<\s*END\s+SPOILERS\s*>>", re.I)
_SPEAKER = re.compile(r"^\s*([A-Z][\w'’-]*)\s*:\s*(.+)$")


# ---------- pure helpers (unit-tested without the SDK) ----------

def campaign_dir(name):
    """The campaign folder: `--campaign`, else dnd-adventure/.campaign."""
    if not name:
        f = ROOT / ".campaign"
        name = f.read_text(encoding="utf-8").strip() if f.exists() else "poc"
    p = Path(name)
    return (p if p.is_absolute() else ROOT / p).resolve()


class InputState:
    """Turns a typed line into ('send', text) | ('local', cmd, arg) | ('skip',)."""

    def __init__(self):
        self.speaker = None

    def handle(self, line):
        text = line.strip()
        if not text:
            return ("skip",)
        if text.startswith(":"):
            cmd, _, arg = text[1:].partition(" ")
            cmd = cmd.lower()
            if cmd == "as":
                self.speaker = arg.strip() or None
            return ("local", cmd, arg.strip())
        if text.startswith(("/", "!")):
            return ("send", text)
        if _SPEAKER.match(text):
            return ("send", text)
        if self.speaker:
            return ("send", f"{self.speaker}: {text}")
        return ("send", text)   # table talk


def banner(header, width=72, color=True):
    label = f"── SPOILERS · {header} " if header else "── SPOILERS "
    line = label + "─" * max(4, width - len(label))
    return f"{BANNER}{line}{RESET}" if color else line


def end_banner(width=72, color=True):
    line = "── END SPOILERS " + "─" * max(4, width - 16)
    return f"{BANNER}{line}{RESET}" if color else line


class Renderer:
    """Line-buffered narration printer: dims bracket lines, draws spoiler banners,
    prints the activity line once per turn."""

    def __init__(self, out=None, color=True, width=72):
        self.out = out or sys.stdout
        self.color = color
        self.width = width
        self.buf = ""
        self.in_spoiler = False
        self.activity_shown = False

    def _w(self, s):
        self.out.write(s + "\n")
        self.out.flush()

    def start_turn(self):
        self.activity_shown = False

    def activity(self):
        if not self.activity_shown:
            self.flush()
            self._w(f"{DIM}{ACTIVITY}{RESET}" if self.color else ACTIVITY)
            self.activity_shown = True

    def text(self, chunk):
        self.buf += chunk
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self._line(line)

    def _line(self, line):
        while True:
            m = _SPOIL_OPEN.search(line) if not self.in_spoiler else _SPOIL_CLOSE.search(line)
            if not m:
                break
            before, after = line[:m.start()], line[m.end():]
            if before.strip():
                self._plain(before)
            if not self.in_spoiler:
                header = re.sub(r"\s*/\s*", " · ", m.group(1).strip())
                self._w(banner(header, self.width, self.color))
                self.in_spoiler = True
            else:
                self._w(end_banner(self.width, self.color))
                self.in_spoiler = False
            line = after
            if not line.strip():
                return
        self._plain(line)

    def _plain(self, line):
        if self.color and line.lstrip().startswith("["):
            self._w(f"{DIM}{line}{RESET}")
        else:
            self._w(line)

    def flush(self):
        if self.buf:
            line, self.buf = self.buf, ""
            self._line(line)

    def end_message(self):
        self.flush()
        if self.in_spoiler:  # unbalanced markers: close at the end of the message
            self._w(end_banner(self.width, self.color))
            self.in_spoiler = False

    def notice(self, text):
        self.flush()
        self._w(f"{DIM}{text}{RESET}" if self.color else text)


def find_cli():
    """A native claude executable for the SDK, or None (let the SDK look). The SDK
    refuses Windows .cmd shims (cmd.exe argument injection), so for npm's `claude.cmd`
    use the `claude.exe` it wraps. `CLAUDE_CLI_PATH` overrides."""
    import shutil
    env = os.environ.get("CLAUDE_CLI_PATH")
    if env:
        return env
    found = shutil.which("claude")
    if not found:
        return None
    p = Path(found)
    if p.suffix.lower() in (".cmd", ".bat"):
        exe = p.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        return str(exe) if exe.exists() else None
    return str(p)


def inside_root(path_text, root=ROOT):
    if not path_text:
        return True   # Glob/Grep default to cwd
    p = Path(path_text)
    p = p if p.is_absolute() else root / p
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _strip_root(cmd, root=ROOT):
    """Drop a leading `cd <root> &&` / `cd <root>;` (exactly the game folder) and turn an
    absolute `<root>/tools/x.py` into `tools/x.py`."""
    r = str(root.resolve()).replace("\\", "/").rstrip("/")
    c = cmd   # backslashes stay as they are: `\"` escapes must survive for the quote scan
    m = re.match(r'^\s*(?:cd|Set-Location)\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*(?:&&|;)\s*(.*)$', c, re.I | re.S)
    if m:
        target = (m.group(1) or m.group(2) or m.group(3) or "").replace("\\", "/").rstrip("/")
        if target.lower() != r.lower():
            return None
        c = m.group(4)
    # an absolute path to the script (either slash style) → tools/x.py
    m = re.match(r'^(\s*\S+\s+)["\']?([^\s"\']+?)[\\/]tools[\\/]((?:gm|space)\.py)["\']?(?=\s|$)', c, re.I)
    if m and m.group(2).replace("\\", "/").rstrip("/").lower() == r.lower():
        c = m.group(1) + "tools/" + m.group(3) + c[m.end():]
    return c


def command_ok(cmd):
    """A single gm.py/space.py invocation: allowed prefix, no command substitution
    (`$(`, backticks, `${`) anywhere, and no unquoted control operator or redirect
    (`;` `&` `|` `<` `>` newline). Quoted text (`do "a; b"`) is fine. A leading
    `cd <game folder> &&` and an absolute path to tools/ are accepted."""
    cmd = _strip_root((cmd or "").strip())
    if cmd is None:
        return False
    cmd = cmd.strip()
    norm = cmd
    if not any(norm == p or norm.startswith(p + " ") for p in COMMAND_PREFIXES):
        return False
    if "$(" in cmd or "`" in cmd or "${" in cmd:
        return False
    quote = None
    skip = False
    for i, ch in enumerate(cmd):
        if skip:
            skip = False
            continue
        if quote:
            # `\"` and `\\` inside double quotes are escapes (do "log \"a; b\"")
            if quote == '"' and ch == "\\" and i + 1 < len(cmd) and cmd[i + 1] in '"\\':
                skip = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in ";&|<>\n\r":
            return False
    return quote is None


def decide(tool, args, root=ROOT):
    """(allow?, reason) for a tool call (the PreToolUse gate and the permission
    callback share it)."""
    if tool in FREE_TOOLS:
        return True, ""
    if tool in SHELL_TOOLS:
        cmd = args.get("command", "")
        if command_ok(cmd):
            return True, ""
        return False, f"{tool} command not allowed at the table"
    if tool in IN_ROOT_TOOLS:
        target = args.get("file_path") or args.get("path") or ""
        if inside_root(target, root):
            return True, ""
        return False, f"{tool} outside the game folder: {target}"
    return False, f"{tool} not allowed at the table"


def log_denial(camp, tool, args, reason):
    p = camp / ".gm" / "client.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    summary = args.get("command") or args.get("file_path") or args.get("path") or str(args)[:200]
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} DENIED {tool}: {summary} — {reason}\n")


# ---------- the client ----------

class Table:
    def __init__(self, args):
        self.args = args
        self.camp = campaign_dir(args.campaign)
        self.gm_view = args.gm_view
        self.render = Renderer(color=sys.stdout.isatty() or bool(os.environ.get("FORCE_COLOR")))
        self.client = None
        self.session_id = None

    # -- session id --
    def _sid_path(self):
        return self.camp / ".gm" / "session-id"

    def saved_session(self):
        p = self._sid_path()
        return p.read_text(encoding="utf-8").strip() if p.exists() and not self.args.new else None

    def save_session(self, sid):
        if sid and sid != self.session_id:
            self.session_id = sid
            p = self._sid_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(sid + "\n", encoding="utf-8")

    # -- SDK --
    def options(self, resume):
        from claude_agent_sdk import ClaudeAgentOptions
        from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

        async def can_use_tool(tool, args, ctx):
            ok, reason = decide(tool, args or {})
            if ok:
                return PermissionResultAllow()
            log_denial(self.camp, tool, args or {}, reason)
            return PermissionResultDeny(message=DENY_MESSAGE)

        from claude_agent_sdk import HookMatcher

        async def gate(data, tool_use_id, ctx):
            tool = data.get("tool_name", "")
            args = data.get("tool_input") or {}
            ok, reason = decide(tool, args)
            if ok:
                return {}  # the normal permission flow (the allowlist) decides
            log_denial(self.camp, tool, args, reason)
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                           "permissionDecision": "deny",
                                           "permissionDecisionReason": DENY_MESSAGE}}

        env = {"GM_CAMPAIGN": str(self.camp), "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
        return ClaudeAgentOptions(
            cwd=str(ROOT),
            setting_sources=["project"],
            allowed_tools=list(ALLOWED),
            permission_mode="default",
            can_use_tool=can_use_tool,
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[gate])]},
            include_partial_messages=True,
            include_hook_events=True,   # shown only in --gm-view
            resume=resume,
            model=self.args.model,
            env=env,
            cli_path=find_cli(),
        )

    async def connect(self):
        import warnings
        from claude_agent_sdk import ClaudeSDKClient
        from claude_agent_sdk.types import CanUseToolShadowedWarning
        warnings.filterwarnings("ignore", category=CanUseToolShadowedWarning)
        self.client = ClaudeSDKClient(options=self.options(self.saved_session()))
        await self.client.connect()

    async def send(self, text):
        """Send one prompt and render the reply. Retries once on an SDK error."""
        for attempt in (1, 2):
            try:
                await self._turn(text)
                return True
            except Exception as e:  # noqa: BLE001 — any SDK/API failure
                self._log_error(e)
                if attempt == 1:
                    self.render.notice(RETRY)
                    try:
                        await self.client.disconnect()
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        await self.connect()
                    except Exception as e2:  # noqa: BLE001
                        self._log_error(e2)
                        break
        self.render.notice(LOST)
        return False

    def _log_error(self, e):
        p = self.camp / ".gm" / "client.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{_dt.datetime.now():%Y-%m-%d %H:%M:%S} ERROR {type(e).__name__}: {e}\n")

    async def _turn(self, text):
        from claude_agent_sdk import (AssistantMessage, ResultMessage, StreamEvent,
                                      SystemMessage, UserMessage)
        from claude_agent_sdk.types import TextBlock, ThinkingBlock, ToolResultBlock, ToolUseBlock
        r = self.render
        r.start_turn()
        streamed = False
        await self.client.query(text)
        async for msg in self.client.receive_response():
            if isinstance(msg, StreamEvent):
                if msg.parent_tool_use_id:
                    continue  # subagent activity
                ev = msg.event or {}
                kind = ev.get("type")
                if kind == "content_block_start" and (ev.get("content_block") or {}).get("type") in (
                        "tool_use", "server_tool_use"):
                    if not self.gm_view:
                        r.activity()
                elif kind == "content_block_delta" and (ev.get("delta") or {}).get("type") == "text_delta":
                    streamed = True
                    r.text(ev["delta"].get("text", ""))
                elif kind == "message_stop":
                    r.end_message()
            elif isinstance(msg, AssistantMessage):
                if msg.parent_tool_use_id:
                    continue
                for block in msg.content:
                    if isinstance(block, TextBlock) and not streamed:
                        r.text(block.text + "\n")
                    elif self.gm_view and isinstance(block, ToolUseBlock):
                        r.notice(f"[gm-view] tool {block.name}: {block.input}")
                    elif self.gm_view and isinstance(block, ThinkingBlock):
                        r.notice(f"[gm-view] thinking: {block.thinking[:2000]}")
                r.end_message()
                streamed = False
            elif isinstance(msg, UserMessage):
                if self.gm_view and isinstance(msg.content, list):
                    for block in msg.content:
                        if isinstance(block, ToolResultBlock):
                            r.notice(f"[gm-view] result: {str(block.content)[:3000]}")
            elif isinstance(msg, SystemMessage):
                if self.gm_view:
                    data = msg.data or {}
                    if msg.subtype == "hook_response":
                        r.notice(f"[gm-view] hook {data.get('hook_name')}: {str(data.get('output') or '')[:3000]}")
                    elif msg.subtype != "hook_started":
                        r.notice(f"[gm-view] system {msg.subtype}")
            elif isinstance(msg, ResultMessage):
                self.save_session(msg.session_id)
                if self.gm_view:
                    cost = f" · ${msg.total_cost_usd:.4f}" if msg.total_cost_usd else ""
                    r.notice(f"[gm-view] turns {msg.num_turns}{cost}")
        r.end_message()

    async def run(self):
        print(f"{BOLD}The table is open ({self.camp.name}).{RESET} "
              "Speak as `Name: …`; `:as Name`, `:gm-view on|off`, `:quit`.")
        try:
            await self.connect()
        except Exception as e:  # noqa: BLE001
            self._log_error(e)
            self.render.notice(LOST)
            return 1
        if (ROOT / ".claude" / "skills" / "gm").exists():
            await self.send("/gm")
        else:
            self.render.notice("[the /gm skill isn't built yet — type to talk to the GM]")
        inp = InputState()
        while True:
            try:
                line = await asyncio.to_thread(input, "> ")
            except (EOFError, KeyboardInterrupt):
                break
            act = inp.handle(line)
            if act[0] == "skip":
                continue
            if act[0] == "local":
                cmd, arg = act[1], act[2]
                if cmd == "quit":
                    break
                if cmd == "gm-view":
                    self.gm_view = arg.lower() != "off"
                    self.render.notice(f"[gm-view {'on' if self.gm_view else 'off'}]")
                elif cmd == "as":
                    self.render.notice(f"[speaking as {inp.speaker}]" if inp.speaker else "[speaking as the table]")
                else:
                    self.render.notice(f"[unknown :{cmd} — :quit, :as <PC>, :gm-view on|off]")
                continue
            await self.send(act[1])
        try:
            await self.client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        self.render.notice("[saved]")
        return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if os.name == "nt":
        os.system("")  # enable ANSI colours in the Windows console
    ap = argparse.ArgumentParser(description="The players' console (narration only).")
    ap.add_argument("--campaign", help="campaign folder (default: .campaign)")
    ap.add_argument("--new", action="store_true", help="start a new session instead of resuming")
    ap.add_argument("--model", help="model id for the GM session")
    ap.add_argument("--gm-view", action="store_true", help="show tool calls, results and thinking")
    args = ap.parse_args(argv)
    return asyncio.run(Table(args).run())


if __name__ == "__main__":
    sys.exit(main())
