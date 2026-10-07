"""The Discord bridge for the table client (docs/design/06 → Table client → Discord
bridge; 04 → `<campaign>/discord.md`; plan.md Phase 17).

    python engine/table.py --campaign poc --discord queue|auto

Remote players type in one Discord channel and read the narration there; the person
running `table.py` stays the host. Everything here except `DiscordPyIO` is pure and
stdlib-only: the config reader, speaker resolution, the queue / auto batch (`Bridge`),
the post formatter (`Posts`) and the reconnect loop. Discord I/O sits behind a tiny
interface (`run()`, `post(text)`, `react(message_id, emoji)`, `close()`, `ready`), so the
tests drive the bridge with a fake. `DiscordPyIO` is the only code that imports
`discord` (the optional `discord.py` package), and only when the bridge starts.

Guards: the bot token comes from the `DND_DISCORD_TOKEN` environment variable, else the
git-ignored `.local/discord-token` file the host keeps by hand (`take_token()` removes the
variable from the environment so the GM's session never inherits it, and the project
settings deny the GM reads of `.local/`); the engine never writes it anywhere, and `redact()` scrubs it from any error text the
client prints or logs. Discord text reaches the GM as an ordinary player prompt (the
same PreToolUse gate). Only what the public renderer shows is posted (never GM-view
output, never client notices except `[the table is open]` / `[the table is closed]`).
Any failure here leaves the terminal table running.
"""
import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

TOKEN_ENV = "DND_DISCORD_TOKEN"
TOKEN_FILE = Path(__file__).resolve().parents[1] / ".local" / "discord-token"   # git-ignored
MODES = ("off", "queue", "auto")
LIMIT = 2000                       # Discord's message length limit
DEBOUNCE = 4.0
SENT, DROPPED, EDITED = "✅", "🗑️", "✏️"
FLAG = "⚑"
OPEN_POST, CLOSED_POST = "[the table is open]", "[the table is closed]"
XCARD = re.compile(r"^\s*!x(?![\w-])", re.I)        # brief.py's X-card test
_SPEAKER = re.compile(r"^\s*([A-Z][\w'’-]*)\s*:\s*(.+)$", re.S)  # table._SPEAKER
NO_PLAYER = {"", "-", "—", "(pregen)", "pregen", "none", "(none)"}   # campaign.NO_PLAYER
BACKOFF = (2, 4, 8, 16, 30, 60)


class BridgeFatal(Exception):
    """A connection error retrying can't fix (bad token, missing intent)."""


# ---------- token ----------

def take_token(env=None, path=None):
    """The bot token from DND_DISCORD_TOKEN (removed from the environment so child
    processes, the GM's Claude Code session, never see it), else the first line of the
    git-ignored `.local/discord-token` that isn't blank or a `#` comment. '' when neither."""
    env = os.environ if env is None else env
    token = (env.pop(TOKEN_ENV, "") or "").strip()
    if token:
        return token
    p = TOKEN_FILE if path is None else Path(path)
    try:
        lines = p.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return ""
    return next((x.strip() for x in lines if x.strip() and not x.strip().startswith("#")), "")


def redact(text, token):
    """`text` with the token scrubbed (for anything printed or logged)."""
    text = str(text)
    if token:
        text = text.replace(token, "[token]")
    return text


# ---------- discord.md ----------

@dataclass
class Config:
    mode: str = "off"
    channel: int = 0
    debounce: float = DEBOUNCE
    users: dict = field(default_factory=dict)   # discord username or id (lower) → player
    problems: list = field(default_factory=list)


def _front_and_body(text):
    lines = text.splitlines()
    front, body = {}, lines
    if lines and lines[0].strip() == "---":
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if close is not None:
            for line in lines[1:close]:
                key, sep, val = line.partition(":")
                if sep and re.fullmatch(r"[A-Za-z0-9_.-]+", key.strip()):
                    front[key.strip().lower()] = re.sub(r"\s+#.*$", "", val).strip().strip("\"'")
            body = lines[close + 1:]
    return front, body


def _table(body, first_col):
    """Rows of the first `| <first_col> | … |` table as lists of cells."""
    rows, header = [], None
    for line in body:
        s = line.strip()
        if not s.startswith("|"):
            if header is not None and rows:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            if cells and cells[0].lower() == first_col:
                header = cells
            continue
        if all(re.fullmatch(r":?-+:?", c or "-") for c in cells):
            continue
        rows.append(cells)
    return rows


def load_config(camp):
    """`<campaign>/discord.md` as a Config, or None when the file is missing. CRLF or
    LF. Bad values are listed in `problems` (never fatal)."""
    p = Path(camp) / "discord.md"
    if not p.exists():
        return None
    front, body = _front_and_body(p.read_text(encoding="utf-8-sig"))
    cfg = Config()
    mode = (front.get("discord") or "off").lower()
    if mode in MODES:
        cfg.mode = mode
    else:
        cfg.problems.append(f"discord: {mode!r} isn't off, queue or auto")
    chan = front.get("channel") or ""
    if re.fullmatch(r"\d{5,25}", chan):
        cfg.channel = int(chan)
    elif chan:
        cfg.problems.append(f"channel: {chan!r} isn't a channel id")
    deb = front.get("debounce") or ""
    if deb:
        try:
            cfg.debounce = max(0.0, float(deb))
        except ValueError:
            cfg.problems.append(f"debounce: {deb!r} isn't a number of seconds")
    for cells in _table(body, "discord user"):
        if len(cells) >= 2 and cells[0] and cells[1]:
            cfg.users[cells[0].lstrip("@").lower()] = cells[1]
    return cfg


def player_pcs(camp):
    """{player (lower): [PC first names]} for PCs not marked `present: false`."""
    out = {}
    folder = Path(camp) / "pcs"
    if not folder.is_dir():
        return out
    for p in sorted(folder.glob("*.md")):
        if p.name.startswith("_"):
            continue
        try:
            front, _ = _front_and_body(p.read_text(encoding="utf-8-sig"))
        except OSError:
            continue
        player = (front.get("player") or "").strip()
        name = (front.get("name") or "").strip()
        if not name or player.lower() in NO_PLAYER or front.get("present", "").lower() == "false":
            continue
        out.setdefault(player.lower(), []).append(name.split()[0])
    return out


def speaker_line(text, player, pcs):
    """A Discord line as the GM gets it: `Kira: …` stays; an unprefixed line from a
    player with exactly one PC speaks for that PC; anything else is table talk,
    labelled with the player so the GM knows who asked."""
    if _SPEAKER.match(text):
        return text
    mine = pcs.get((player or "").lower(), [])
    if len(mine) == 1:
        return f"{mine[0]}: {text}"
    return f"({player}, table talk) {text}"


# ---------- output: what goes to the channel ----------

def chunks(text, limit=LIMIT):
    """`text` cut into pieces of at most `limit` characters, at a newline, else a
    space, else anywhere."""
    out = []
    text = text.strip("\n")
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit + 1)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        out.append(text[:cut].rstrip())
        text = text[cut:].lstrip("\n ")
    if text.strip():
        out.append(text)
    return out


class Posts:
    """Turns the public renderer's events into Discord posts: a paragraph posts when it
    ends (a blank line or the end of the message); a fenced block (the player-view map)
    posts as a code block when it closes; a spoiler answer posts as its header line and
    the text inside `|| ||`. Every post is under the 2000-character limit."""

    def __init__(self, limit=LIMIT):
        self.limit = limit
        self.para = []
        self.code = None        # lines inside a fence
        self.spoiler = None     # (header, lines) inside a spoiler banner

    def event(self, kind, arg=None):
        out = []
        if kind == "line":
            if self.spoiler is not None:
                self.spoiler[1].append(arg)
            elif self.code is not None:
                self.code.append(arg)
            elif arg.strip():
                self.para.append(arg)
            else:
                out += self._para()
        elif kind == "fence":
            if self.spoiler is not None:
                pass                           # a fence inside a spoiler: text only
            elif self.code is None:
                out += self._para()
                self.code = []
            else:
                out += self._code()
        elif kind == "spoiler":
            out += self._para() + self._code()
            self.spoiler = (arg or "", [])
        elif kind == "endspoiler":
            out += self._spoiler()
        elif kind == "end":
            out += self._para() + self._code() + self._spoiler()
        return out

    def _para(self):
        text, self.para = "\n".join(self.para), []
        return chunks(text, self.limit) if text.strip() else []

    def _code(self):
        if self.code is None:
            return []
        lines, self.code = self.code, None
        body = "\n".join(lines).replace("```", "'''")
        if not body.strip():
            return []
        return [f"```\n{c}\n```" for c in chunks(body, self.limit - 8)]

    def _spoiler(self):
        if self.spoiler is None:
            return []
        header, lines = self.spoiler
        self.spoiler = None
        head = f"── SPOILERS · {header} ──" if header else "── SPOILERS ──"
        body = "\n".join(lines).strip().replace("||", "| |")
        if not body:
            return [head]
        parts = [f"||{c}||" for c in chunks(body, self.limit - 4)]
        if len(head) + 1 + len(parts[0]) <= self.limit:
            return [head + "\n" + parts[0]] + parts[1:]
        return [head] + parts


# ---------- input: the queue and the auto batch ----------

@dataclass
class Entry:
    n: int
    who: str            # "host" or the Discord username
    text: str           # what was typed (shown, editable)
    prompt: str         # what the GM gets
    msg_id: int = None  # the Discord message, for reactions / edits / deletes
    flagged: bool = False
    edited: bool = False
    own: bool = False   # a slash or `!` line: sent as a prompt of its own

    def show(self):
        tag = f" {FLAG}" if self.flagged else ""
        text = self.text if self.flagged else self.prompt
        return f"[Q{self.n} {self.who}{tag}] {text}" + (" (edited)" if self.edited else "")


@dataclass
class Incoming:
    """One Discord message, as the adapter hands it over."""
    id: int
    author: str
    text: str
    channel_id: int
    author_id: int = 0
    bot: bool = False
    dm: bool = False


class Bridge:
    """Queue/auto logic, output posting and Discord feedback, with injected I/O.

    `notice(text)` prints on the host's terminal; `wake()` tells the table's loop to look
    again (a line arrived, a batch may be due); `interpret(text)` turns a host line into
    its prompt (table.InputState: `:as`, unknown slash commands); `pcs()` gives
    {player: [PC]} for speaker resolution; `clock()` is monotonic seconds; `users()`
    re-reads the player map from discord.md (a row added mid-session counts at once)."""

    def __init__(self, cfg, io=None, notice=print, wake=None, interpret=None, pcs=None,
                 clock=time.monotonic, token="", log=None, users=None):
        self.cfg = cfg
        self.mode = cfg.mode if cfg.mode in MODES else "off"
        self.io = io
        self.notice = notice
        self.wake = wake or (lambda: None)
        self.interpret = interpret or (lambda t: t)
        self.pcs = pcs or (lambda: {})
        self.clock = clock
        self.token = token
        self.log = log or (lambda text: None)
        self.users = users
        self.entries = []
        self.urgent = []            # (prompt, msg_id): X-cards, sent before anything else
        self.ignored = set()
        self.posts = Posts()
        self.outbox = []            # ("post", text) | ("react", msg_id, emoji)
        self.last_at = None         # when the last unflagged line joined (auto debounce)
        self.force = False          # auto: send the batch as soon as the GM is free
        self.busy = False           # the GM is replying
        self.closed = False
        self.dead = False           # a fatal connection error: off until the table restarts
        self._next = 1
        self._out_event = None
        self._down = False

    # -- helpers --
    @property
    def on(self):
        return self.mode in ("queue", "auto")

    def _say(self, text):
        self.notice(redact(text, self.token))

    def _queue_out(self, *item):
        if self.closed:
            return
        self.outbox.append(item)
        if self._out_event is not None:
            self._out_event.set()

    def _add(self, who, text, prompt, msg_id=None, flagged=False, own=False):
        if not self.entries:
            self._next = 1
        e = Entry(self._next, who, text, prompt, msg_id, flagged, own=own)
        self._next += 1
        self.entries.append(e)
        if not flagged:
            self.last_at = self.clock()
            if self.busy:
                self.force = True       # collected during the reply: goes when it ends
        return e

    def _find(self, n=None, msg_id=None):
        for e in self.entries:
            if (n is not None and e.n == n) or (msg_id is not None and e.msg_id == msg_id):
                return e
        return None

    def _resolve_discord(self, text, player):
        if text.startswith("/"):
            # a slash command waits for the host (⚑) only in queue mode; auto sends it
            return self.interpret(text), self.mode != "auto", True
        if text.startswith("!"):
            return text, False, True
        return speaker_line(text, player, self.pcs()), False, False

    # -- inbound from Discord --
    def on_message(self, m):
        """A Discord message. Returns the Entry it made (or None)."""
        try:
            return self._on_message(m)
        except Exception as e:  # noqa: BLE001 — the terminal table keeps running
            self.log(f"discord message error: {type(e).__name__}: {redact(e, self.token)}")
            return None

    def _player(self, m):
        return self.cfg.users.get((m.author or "").lower()) or self.cfg.users.get(str(m.author_id))

    def _on_message(self, m):
        if not self.on or m.bot or m.dm or m.channel_id != self.cfg.channel:
            return None
        player = self._player(m)
        if not player and self.users is not None:
            fresh = self.users()        # discord.md may have gained a row since the start
            if fresh:
                self.cfg.users = fresh
                player = self._player(m)
                if player and m.author in self.ignored:
                    self.ignored.discard(m.author)
                    self._say(f"[discord: @{m.author} joins as {player}]")
        if not player:
            if m.author not in self.ignored:
                self.ignored.add(m.author)
                self._say(f"[discord: ignoring @{m.author} (not on the map)]")
            return None
        text = (m.text or "").strip()
        if not text or text.startswith(":"):
            return None                 # empty, or a client command: never from Discord
        if XCARD.match(text):
            self.urgent.append(("!x", m.id))
            self._say("[discord: X-card — sent at once]")
            self.wake()
            return None
        prompt, flagged, own = self._resolve_discord(text, player)
        e = self._add(m.author, text, prompt, m.id, flagged, own)
        self._say(e.show())
        self.wake()
        return e

    def on_edit(self, msg_id, text):
        e = self._find(msg_id=msg_id)
        if e is None or e.who == "host":
            return None
        player = self.cfg.users.get(e.who.lower(), e.who)
        text = (text or "").strip()
        if not text:
            return self.on_delete(msg_id)
        e.text = text
        e.prompt, e.flagged, e.own = self._resolve_discord(text, player)
        e.edited = True
        self._say(e.show())
        return e

    def on_delete(self, msg_id):
        e = self._find(msg_id=msg_id)
        if e is None:
            return None
        self.entries.remove(e)
        self._say(f"[Q{e.n} {e.who}] deleted on Discord — dropped")
        return e

    # -- the host --
    def host_line(self, text, prompt=None):
        """A line the host typed (the prompt already through InputState)."""
        prompt = prompt if prompt is not None else self.interpret(text)
        own = text.startswith(("/", "!"))
        e = self._add("host", text, prompt, own=own)
        if self.mode == "auto":
            self.force = True           # the host's Enter sends the batch
        else:
            self._say(e.show())
        self.wake()
        return e

    def listing(self):
        if not self.entries:
            return ["[queue empty]"]
        return [e.show() for e in self.entries]

    def edit(self, n, text):
        e = self._find(n=n)
        if e is None:
            return f"[no Q{n}]"
        text = text.strip()
        if not text:
            return "[:edit <n> <new text>]"
        e.text = text
        if e.who == "host":
            e.prompt, e.own = self.interpret(text), text.startswith(("/", "!"))
        else:
            e.prompt, e.flagged, e.own = self._resolve_discord(text, self.cfg.users.get(e.who.lower(), e.who))
            if e.msg_id is not None:
                self._queue_out("react", e.msg_id, EDITED)
        return e.show()

    def drop(self, n):
        e = self._find(n=n)
        if e is None:
            return f"[no Q{n}]"
        self.entries.remove(e)
        if e.msg_id is not None:
            self._queue_out("react", e.msg_id, DROPPED)
        return f"[dropped Q{n}]"

    def clear(self):
        k = len(self.entries)
        for e in self.entries:
            if e.msg_id is not None:
                self._queue_out("react", e.msg_id, DROPPED)
        self.entries = []
        self.force = False
        return f"[queue cleared — {k} dropped]"

    def set_mode(self, mode):
        mode = (mode or "").strip().lower()
        if mode not in MODES:
            return "[:discord queue|auto|off]"
        if self.dead and mode != "off":
            return "[discord: the connection failed — fix it and restart the table]"
        was = self.mode
        self.mode = mode
        if mode != "off" and was == "off":
            self._queue_out("post", OPEN_POST)
        elif mode == "off" and was != "off":
            self._queue_out("post", CLOSED_POST)
            self.posts = Posts()
        if mode == "auto":
            for e in self.entries:
                e.flagged = False       # auto holds nothing back, slash commands included
            self.last_at = self.clock() if self.entries else None
        self.wake()
        extra = f" — {len(self.entries)} queued (:q, :send)" if self.entries else ""
        return f"[discord: {mode}]{extra}"

    # -- submitting --
    def take_urgent(self):
        out = []
        for prompt, msg_id in self.urgent:
            out.append(prompt)
            if msg_id is not None:
                self._queue_out("react", msg_id, SENT)
        self.urgent = []
        return out

    def take(self, everything=True):
        """The queued lines as prompts, in arrival order: consecutive ordinary lines
        join into one prompt (one turn with several actors); a slash or `!` line is a
        prompt of its own. `everything=False` (auto mode's batch) leaves ⚑ lines for the
        host. Reacts ✅ to each Discord message sent."""
        pick = [e for e in self.entries if everything or not e.flagged]
        self.entries = [e for e in self.entries if e not in pick]
        self.force = False
        self.last_at = None
        prompts, group = [], []
        for e in pick:
            if e.own:
                if group:
                    prompts.append("\n".join(group))
                    group = []
                prompts.append(e.prompt)
            else:
                group.append(e.prompt)
            if e.msg_id is not None:
                self._queue_out("react", e.msg_id, SENT)
        if group:
            prompts.append("\n".join(group))
        return prompts

    def due(self):
        """Auto mode: the batch should go now (the GM is idle)."""
        if self.mode != "auto" or self.busy or not any(not e.flagged for e in self.entries):
            return False
        if self.force:
            return True
        return self.last_at is not None and self.clock() - self.last_at >= self.cfg.debounce

    def wait_time(self):
        """Seconds until the auto batch is due, or None (nothing pending)."""
        if self.mode != "auto" or self.busy or self.last_at is None:
            return None
        if not any(not e.flagged for e in self.entries):
            return None
        return max(0.0, self.cfg.debounce - (self.clock() - self.last_at))

    # -- output --
    def feed(self, kind, arg=None):
        """An event from the public renderer (table.Renderer.tee)."""
        if not self.on:
            return
        try:
            for text in self.posts.event(kind, arg):
                self._queue_out("post", text)
        except Exception as e:  # noqa: BLE001
            self.log(f"discord format error: {type(e).__name__}: {redact(e, self.token)}")

    def post(self, text):
        if self.on:
            for c in chunks(text):
                self._queue_out("post", c)

    async def flush_out(self):
        """Send what's waiting (when connected). Errors are logged, never raised."""
        if self.io is None or not getattr(self.io, "ready", False):
            return
        while self.outbox and getattr(self.io, "ready", False):
            item = self.outbox.pop(0)
            try:
                if item[0] == "post":
                    await self.io.post(item[1])
                else:
                    await self.io.react(item[1], item[2])
            except Exception as e:  # noqa: BLE001
                self.log(f"discord send error: {type(e).__name__}: {redact(e, self.token)}")

    async def sender(self):
        """Background task: posts and reactions go out in order as they are queued."""
        self._out_event = asyncio.Event()
        self._out_event.set()
        while not self.closed:
            await self._out_event.wait()
            self._out_event.clear()
            await self.flush_out()

    # -- connection --
    def ready(self):
        if self._down:
            self._say("[discord: reconnected]")
        else:
            self._say(f"[discord: connected — {self.mode} mode]")
        self._down = False
        if self._out_event is not None:
            self._out_event.set()

    def disconnected(self):
        if not self._down and not self.closed:
            self._down = True
            self._say("[discord: disconnected — retrying]")

    async def connect_loop(self, sleep=asyncio.sleep, backoff=BACKOFF):
        """Run the I/O, reconnecting with backoff when a connection attempt fails.
        `BridgeFatal` (bad token, missing intent) stops the bridge with one notice; the
        terminal table carries on either way."""
        tries = 0
        while not self.closed:
            try:
                await self.io.run()
                if self.closed:
                    return
                tries = 0
            except asyncio.CancelledError:
                raise
            except BridgeFatal as e:
                self._say(f"[discord: {redact(e, self.token)} — the table carries on without Discord]")
                self.mode = "off"
                self.dead = True
                self.outbox.clear()
                return
            except Exception as e:  # noqa: BLE001
                self.log(f"discord connection error: {type(e).__name__}: {redact(e, self.token)}")
            if self.closed:
                return
            self.disconnected()
            await sleep(backoff[min(tries, len(backoff) - 1)])
            tries += 1

    async def close(self):
        """Post `[the table is closed]`, send what's left, disconnect."""
        if self.closed:
            return
        if self.on:
            self.posts = Posts()
            self._queue_out("post", CLOSED_POST)
        try:
            await asyncio.wait_for(self.flush_out(), 10)
        except Exception:  # noqa: BLE001
            pass
        self.closed = True
        if self._out_event is not None:
            self._out_event.set()
        if self.io is not None:
            try:
                await self.io.close()
            except Exception as e:  # noqa: BLE001
                self.log(f"discord close error: {type(e).__name__}: {redact(e, self.token)}")


# ---------- the real Discord connection (needs `pip install discord.py`) ----------

def library_available():
    try:
        import importlib.util
        return importlib.util.find_spec("discord") is not None
    except (ImportError, ValueError):
        return False


class DiscordPyIO:
    """discord.py behind the bridge's I/O interface. Listens to the one channel (never
    DMs), posts with mentions disabled, reacts. `run()` is one connection's lifetime
    (discord.py itself resumes short drops); a bad token or a missing Message Content
    intent raises BridgeFatal."""

    def __init__(self, token, bridge):
        self._token = token
        self.bridge = bridge
        self.client = None
        self.ready = False
        self._channel = None

    async def run(self):
        import logging
        import discord
        logging.getLogger("discord").addHandler(logging.NullHandler())
        logging.getLogger("discord").propagate = False   # nothing from the library on the terminal
        intents = discord.Intents.default()
        intents.message_content = True                   # privileged: enable it in the Developer Portal
        client = discord.Client(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.client = client
        b = self.bridge
        chan = b.cfg.channel

        @client.event
        async def on_ready():
            self._channel = client.get_channel(chan)
            if self._channel is None:
                try:
                    self._channel = await client.fetch_channel(chan)
                except Exception:  # noqa: BLE001
                    b._say("[discord: can't see the channel in discord.md — check the id and the bot's access]")
                    return
            self.ready = True
            b.ready()

        @client.event
        async def on_resumed():
            self.ready = self._channel is not None
            if self.ready:
                b.ready()

        @client.event
        async def on_disconnect():
            self.ready = False
            b.disconnected()

        @client.event
        async def on_message(m):
            if m.author == client.user:
                return
            b.on_message(Incoming(id=m.id, author=m.author.name, author_id=m.author.id, text=m.content,
                                  channel_id=m.channel.id, bot=m.author.bot, dm=m.guild is None))

        @client.event
        async def on_message_edit(before, after):
            if after.channel.id == chan and after.author != client.user:
                b.on_edit(after.id, after.content)

        @client.event
        async def on_raw_message_delete(payload):
            if payload.channel_id == chan:
                b.on_delete(payload.message_id)

        @client.event
        async def on_error(event, *args, **kwargs):
            import sys
            err = sys.exc_info()[1]
            b.log(f"discord event error in {event}: {type(err).__name__}: {redact(err, self._token)}")

        try:
            await client.start(self._token, reconnect=True)
        except discord.LoginFailure:
            raise BridgeFatal("login failed: check the DND_DISCORD_TOKEN environment variable") from None
        except discord.PrivilegedIntentsRequired:
            raise BridgeFatal("turn on the bot's Message Content intent (Developer Portal → Bot)") from None
        finally:
            self.ready = False
            if not client.is_closed():
                try:
                    await client.close()
                except Exception:  # noqa: BLE001
                    pass

    async def post(self, text):
        await self._channel.send(text)

    async def react(self, msg_id, emoji):
        await self._channel.get_partial_message(msg_id).add_reaction(emoji)

    async def close(self):
        self.ready = False
        if self.client is not None and not self.client.is_closed():
            await self.client.close()
