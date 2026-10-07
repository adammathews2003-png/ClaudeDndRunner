"""`gm.py brief [--long] [--hook]` — the GM's state digest, injected by hooks so a normal
turn needs no file reads (docs/design/06 → `gm.py brief` + hooks; 01 → Session lifecycle;
05 #8; plan.md Phase 3).

The brief (≤ 20 lines) is built from `state/current.md` and the files it names: the
On stage NPC files, the PC files, `state/table-rules.md`, the session log. `--long`
adds the scene Summary, the last 5 turns of the session log and the spoiler record.

`--hook` is what `.claude/settings.json` runs. It reads the hook's stdin JSON
(`hook_event_name`, `source`, `prompt`) and prints nothing unless current.md has
`in-session: true`:
- SessionStart (any source): the long brief; the change-tracking state is cleared so
  the next prompt gets a full brief.
- UserPromptSubmit: the full brief when it changed since the last injection (hash of
  every line but `Log:`, kept in `<campaign>/.gm/brief-hash`), on every 15th prompt,
  or when the prompt starts with `!brief`; otherwise a one-line heartbeat. Then the
  Wacky Juice roll (lib/wacky.py) may append a `Juice:` line.
The hook never fails the prompt: any error prints `[GM BRIEF] unavailable: <reason>`
and exits 0.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

from lib import campaign, creatures, gametime, journal, md, resolve, sight, wacky

FORCE_EVERY = 15
XP_NEXT = (0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000, 85000, 100000,
           120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000)
_TEMPO = re.compile(r"^Tempo:\s*([a-z]+)", re.I)
_COMBAT = re.compile(r"^Combat\s*[—-]\s*(.+)$")
_CLOCK = re.compile(r"^\s*-\s*(Day\s+-?\d+\s+\d{1,2}:\d{2})\s*:?\s*(.*)$", re.I)
_PATH = re.compile(r"(?:load\s+)?\b[\w./-]+\.md\b,?\s*")
_TURN = re.compile(r"^\[turn (\d+)\]")


# ---------- pieces ----------

def _short(name):
    return str(name).split()[0] if str(name).strip() else str(name)


def _bullets(state, heading):
    span = state.section(heading)
    if span is None:
        return []
    return [state.body[i].strip()[1:].strip() for i in range(span[0] + 1, span[1])
            if state.body[i].strip().startswith("-")]


def tempo(state):
    for _, _, text in state.headings():
        if _COMBAT.match(text):
            return "combat"
    for _, _, text in state.headings():
        m = _TEMPO.match(text)
        if m:
            return m.group(1).lower()
    return "calm"


def combat_status(state):
    for _, _, text in state.headings():
        m = _COMBAT.match(text)
        if m:
            return m.group(1).strip()
    return None


def _now(state):
    try:
        return gametime.parse(state.front.get("in-game-datetime"))
    except gametime.TimeError:
        return None


def header(state):
    camp = state.front.get("campaign") or campaign.root().name
    now = _now(state)
    when = f"{gametime.fmt(now)} ({gametime.period(now)})" if now else str(state.front.get("in-game-datetime") or "?")
    site = str(state.front.get("party-location") or "?").split("/")[0]
    scene = state.front.get("scene")
    where = f"{site} — {scene}" if scene else site
    return f"[GM BRIEF] {camp} · {when} · {where} · tempo: {tempo(state)}"


def _goal_from_bullet(state, m):
    if m.line is None:
        return None
    text = state.body[m.line]
    g = re.search(r"goal:\s*(.+)$", text, re.I)
    return g.group(1).strip() if g else None


def on_stage(state):
    parts = []
    for m in campaign.stage_matches(state):
        if m.is_pc:
            continue
        front = m.doc.front if m.doc is not None else {}
        bit = m.name
        att = front.get("attitude-to-party")
        if att:
            bit += f" ({att})"
        goal = (m.row or {}).get("intent", "").strip() if m.row else ""
        goal = goal if goal and goal not in ("—", "-") else (_goal_from_bullet(state, m) or front.get("default-goal"))
        if goal:
            bit += f" goal: {goal}"
        parts.append(bit)
    return "On stage: " + (" · ".join(parts) if parts else "—")


def order(state):
    table = state.table("Combatants")
    if table is None:
        table = state.table("Stage")
    if table is None:
        return None
    bits = []
    for row in table.rows:
        name = creatures.norm_name(row.get("name", ""))
        init = (row.get("init") or "").strip()
        if name:
            bits.append(f"{name} {init}".strip())
    return "Order: " + " · ".join(bits) if bits else None


def _combat_row(state, pc_doc):
    table = state.table("Combatants")
    if table is None:
        return None
    slug = Path(pc_doc.path).stem
    full = str(pc_doc.front.get("name") or slug)
    for row in table.rows:
        ref = (row.get("ref") or "").strip()
        name = creatures.norm_name(row.get("name", ""))
        if ref == f"pcs/{slug}" or name.lower() in (full.lower(), _short(full).lower()):
            return row
    return None


def _pc_numbers(state, doc):
    """(cur, max, temp, ac, [conditions]) — the Combatants row wins during combat."""
    hp = doc.front.get("hp") if isinstance(doc.front.get("hp"), dict) else {}
    cur, mx, temp = hp.get("current"), hp.get("max"), hp.get("temp") or 0
    ac = doc.front.get("ac")
    conds = [str(c) for c in (doc.front.get("conditions") or []) if str(c).strip()]
    row = _combat_row(state, doc)
    if row is not None:
        parsed = creatures.parse_hp_cell(row.get("hp", ""))
        if parsed:
            cur, mx, temp = parsed[0], parsed[1], parsed[2]
        ac = row.get("ac") or ac
        cell = (row.get("conditions") or "").strip()
        conds = [c.strip() for c in cell.split(",") if c.strip() and cell not in ("—", "-")]
    return cur, mx, temp, ac, conds


def party(state, settings):
    bits = []
    tracking = str(settings.get("xp-tracking", "on")).lower() == "on"
    for doc in campaign.pcs():
        name = _short(doc.front.get("name") or "?")
        if campaign.player_of(doc):
            name += f" ({campaign.player_of(doc)})"
        if doc.front.get("present") is False:
            bits.append(f"{name} (autopilot)")
            continue
        cur, mx, temp, ac, conds = _pc_numbers(state, doc)
        bit = f"{name} {cur}/{mx}" + (f" (+{temp} temp)" if temp else "") + f" AC{ac}"
        if conds:
            bit += " [" + ", ".join(conds) + "]"
        xp = doc.front.get("xp")
        if tracking and isinstance(xp, int):
            level = doc.front.get("level") if isinstance(doc.front.get("level"), int) else 1
            nxt = XP_NEXT[level] if 1 <= level < len(XP_NEXT) else None
            bit += f" XP {xp:,}" + (f"/{nxt:,}" if nxt else "")
        bits.append(bit)
    return "Party: " + (" · ".join(bits) if bits else "—")


def sight_line(state):
    """`Sight (dark): …` for each present PC when the scene isn't brightly lit, so the GM
    knows who sees what without asking (lib/sight.py; senses come from the PC file)."""
    light = str(state.front.get("light") or "bright").lower()
    if light == "bright":
        return None
    bits = [sight.describe(d, light, _short(d.front.get("name") or "?"))
            for d in campaign.scene_pcs()]
    return f"Sight ({light}): " + (" · ".join(bits) if bits else "—")


def _rule_rows():
    p = resolve.table_rules_path()
    if not p.exists():
        return []
    table = md.load(p).table("Table rules")
    return [r for r in (table.rows if table else []) if r.get("status", "").strip().lower() == "active"]


def rules_line(rows):
    bits = []
    for r in rows:
        what = (r.get("key") or "").strip() or (r.get("rule") or "").strip()
        if len(what) > 30:
            what = what[:29].rstrip() + "…"
        bits.append(f"{r.get('id')} {what} ({r.get('scope')})")
    return "Rules: " + (" · ".join(bits) if bits else "—")


def watch_line(state):
    watch = [_PATH.sub("", b).replace("→  ", "→ ").strip() for b in _bullets(state, "Watch for")]
    watch = [re.sub(r"\s{2,}", " ", re.sub(r"\s*\(\s*\)", "", w)) for w in watch]
    nxt = next_clock(state)
    return "Watch: " + (" · ".join(watch) if watch else "—") + "   Next clock: " + nxt


def next_clock(state):
    now = _now(state)
    best = None
    for b in _bullets(state, "Clocks"):
        m = _CLOCK.match("- " + b)
        if not m:
            continue
        try:
            t = gametime.parse(m.group(1))
        except gametime.TimeError:
            continue
        if now is not None and gametime.diff(now, t) < 0:
            continue
        if best is None or gametime.diff(best[0], t) < 0:
            label = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(2)).strip()
            if len(label) > 40:
                label = label[:40].rsplit(" ", 1)[0] + "…"
            best = (t, label)
    if best is None:
        return "—"
    t, label = best
    left = f" in {gametime.fmt_delta(gametime.diff(now, t))}" if now is not None else ""
    return f"{gametime.fmt(t)} ({label}){left}"


def log_line():
    doc = journal._load_log()
    n, is_open = journal.current_turn(doc)
    if is_open:
        idx = max(i for i, line in enumerate(doc.body) if _TURN.match(line))
        deltas = 0
        for line in doc.body[idx + 1:]:
            if not line.startswith("  - "):
                break
            deltas += 1
        return f"Log: turn {n} open ({deltas} delta{'s' if deltas != 1 else ''})"
    return f"Log: turn {n - 1} closed" if n > 1 else "Log: no turns yet"


# ---------- the brief ----------

def build(state=None):
    """The brief's lines (no `Juice:` line; that's the hook's)."""
    state = state or campaign.load_state()
    settings = campaign.settings(state)
    rows = _rule_rows()
    lines = [header(state), on_stage(state)]
    o = order(state)
    if o:
        lines.append(o)
    lines.append(party(state, settings))
    sl = sight_line(state)
    if sl:
        lines.append(sl)
    lines += [rules_line(rows), watch_line(state),
              "Combat: " + (combat_status(state) or "—")]
    import split
    split_line, slice_line = split.brief_lines(state)
    if split_line:
        lines += [split_line, slice_line]
    lines.append(log_line())
    return lines


def long_extra(state):
    out = []
    span = state.section("Summary")
    if span:
        text = " ".join(state.body[i].strip() for i in range(span[0] + 1, span[1]) if state.body[i].strip())
        if text:
            out.append("Summary: " + text)
    doc = journal._load_log()
    turns = [i for i, line in enumerate(doc.body) if _TURN.match(line)]
    if turns:
        start = turns[-5] if len(turns) >= 5 else turns[0]
        recent = [line for line in doc.body[start:] if line.strip()]
        out.append("Recent log:")
        out += recent[-40:]
    else:
        out.append("Recent log: (no turns yet)")
    sp = campaign.root() / "sessions" / "spoilers.md"
    rows = []
    if sp.exists():
        t = md.load(sp).table("Spoilers")
        rows = t.rows if t else []
    if rows:
        latest = " · ".join(f"{r.get('question')} → {r.get('revealed')}" for r in rows[-3:])
        out.append(f"Spoilers: {len(rows)} · latest: {latest}")
    else:
        out.append("Spoilers: none")
    return out


def heartbeat(state, since_turn):
    bits = [f"[GM BRIEF] unchanged since turn {since_turn}"]
    now = _now(state)
    bits.append(gametime.fmt(now) if now else str(state.front.get("in-game-datetime") or "?"))
    bits.append(tempo(state))
    for doc in campaign.pcs():
        if doc.front.get("present") is False:
            continue
        cur, mx, temp, _, conds = _pc_numbers(state, doc)
        hurt = isinstance(cur, int) and isinstance(mx, int) and cur < mx
        if hurt or conds:
            b = _short(doc.front.get("name") or "?")
            if hurt:
                b += f" {cur}/{mx}"
            if conds:
                b += " " + ", ".join(c.split()[0] for c in conds)
            bits.append(b)
    status = combat_status(state)
    if status and "up:" in status:
        bits.append("up: " + status.split("up:", 1)[1].strip())
    ids = [r.get("id") for r in _rule_rows()]
    if ids:
        bits.append(" ".join(ids))
    import split
    sb = split.heartbeat_bit(state)
    if sb:
        bits.append(sb)
    return " · ".join(bits)


def digest(lines):
    keep = [line for line in lines if not line.startswith(("Log:", "Slice:"))]  # change every prompt
    return hashlib.sha256("\n".join(keep).encode("utf-8")).hexdigest()[:16]


# ---------- hook state ----------

def _hash_path():
    return campaign.root() / ".gm" / "brief-hash"


def _load_hash():
    p = _hash_path()
    out = {"hash": None, "prompts": 0, "turn": None}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "hash":
            out["hash"] = value or None
        elif key in ("prompts", "turn") and value.isdigit():
            out[key] = int(value)
    return out


def _save_hash(st):
    p = _hash_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(p, f"hash: {st['hash'] or ''}\nprompts: {st['prompts']}\nturn: {st['turn'] or ''}\n")


def _clear_hash():
    p = _hash_path()
    if p.exists():
        p.unlink()


def _read_stdin():
    stream = sys.stdin
    if stream is None:
        return {}
    try:
        if stream.isatty():
            return {}
    except (AttributeError, ValueError):
        pass
    try:
        raw = stream.read()
    except (OSError, ValueError):
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def hook(ctx, long):
    """The hook body. Returns the lines to print (maybe none)."""
    data = _read_stdin()
    event = data.get("hook_event_name") or ("SessionStart" if long else "UserPromptSubmit")
    state = campaign.load_state()
    if state.front.get("in-session") is not True:
        return []
    if event == "SessionStart":
        _clear_hash()
        return build(state) + long_extra(state)
    prompt = str(data.get("prompt") or "")
    import split
    split.count_prompt(prompt)
    lines = build(state)
    h = digest(lines)
    st = _load_hash()
    forced = st["hash"] is None or st["prompts"] + 1 >= FORCE_EVERY or prompt.lstrip().startswith("!brief")
    if forced or h != st["hash"]:
        out = list(lines)
        st = {"hash": h, "prompts": 0, "turn": journal.current_turn()[0]}
    else:
        out = [heartbeat(state, st["turn"] if st["turn"] is not None else "?")]
        st["prompts"] += 1
    _save_hash(st)
    juice = wacky.hook_roll(prompt, ctx.roller, state)
    if juice:
        out.append(juice)
    return out


def cmd_brief(ctx):
    a = ctx.args
    if a.hook:
        try:
            lines = hook(ctx, a.long)
        except Exception as e:  # the hook must never block or fail the prompt
            lines = [f"[GM BRIEF] unavailable: {type(e).__name__}: {e}"]
        for line in lines:
            ctx.emit(line)
        ctx.result = {"lines": lines}
        return
    state = campaign.load_state()
    lines = build(state) + (long_extra(state) if a.long else [])
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("brief", parents=[g], help="state digest (--long at session start; --hook for hooks)")
    p.add_argument("--long", action="store_true", help="add summary, recent log, spoilers")
    p.add_argument("--hook", action="store_true", help="hook mode: reads stdin JSON, hash/heartbeat, juice roll")
    p.set_defaults(func=cmd_brief)
