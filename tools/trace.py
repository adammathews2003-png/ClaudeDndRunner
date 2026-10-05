"""`gm.py trace <name|location> [--from "Day 1 18:00"] [--to "Day 2 06:00"]` — a
reconstructed timeline (planning/06 → Spoiler support; 02 → Spoilers: Established /
Likely; plan.md Phase 7 item 7).

Merges logged moves (including `(GM)` lines) from `sessions/history/*` (their
`## Turn log`) and `session-current.md`, timed by the `time A→B` deltas in the log,
with the `## Movements` schedule for the stretches the logs don't cover:

    [TRACE] Veskar · Day 1 18:00 → Day 2 06:00
      Day 1 18:00–00:00  crossroads-inn/upstairs (room 3)   scheduled
      Day 2 00:00        → old-mill by inn-door, mill-rd     logged (GM) turn 22

Each row's source (`logged` / `scheduled`) maps onto the GM's Established / Likely.
A location argument lists everyone whose logged moves or schedule touch it.
"""
import re

from lib import campaign, gametime, md
from lib.errors import ToolError
import clock

_TIME = re.compile(r"\btime (Day -?\d+ \d\d:\d\d)→(Day -?\d+ \d\d:\d\d)")
_DAYT = re.compile(r"Day -?\d+ \d\d:\d\d")


class TraceError(ToolError):
    pass


def _log_files():
    root = campaign.root() / "sessions"
    out = []
    hist = root / "history"
    for p in sorted(hist.glob("session-*.md")) if hist.is_dir() else []:
        doc = md.load(p)
        span = doc.section("Turn log")
        lines = doc.body[span[0] + 1:span[1]] if span else []
        out.append((p.stem, lines))
    cur = campaign.session_log_path()
    if cur.exists():
        out.append(("current", md.load(cur).body))
    return out


def events():
    """[(time, who-text line, gm?, turn, file)] for every move line in the logs."""
    out = []
    now = None
    for name, lines in _log_files():
        turn = None
        for line in lines:
            m = re.match(r"^\[turn (\d+)\]", line)
            if m:
                turn = int(m.group(1))
                continue
            if not line.startswith("  - "):
                continue
            text = line[4:]
            gm = text.startswith("(GM) ")
            if gm:
                text = text[5:]
            t = _TIME.search(text)
            if t:
                now = gametime.parse(t.group(2))
                continue
            if not re.match(r"^(move-npc|move-party|travel|stub npc|scene enter)\b", text):
                continue
            when = now
            stamps = _DAYT.findall(text)
            if text.startswith("move-npc") and stamps:
                when = gametime.parse(stamps[0])
            out.append((when, text, gm, turn, name))
    return out


def _schedule_rows(doc, start, end):
    rows = []
    sched = clock.movements(doc)
    if not sched:
        return rows
    for day in range(start[0] - 1, end[0] + 1):
        for i, (minute, target, note) in enumerate(sched):
            nxt = sched[(i + 1) % len(sched)][0]
            t0 = (day, minute)
            t1 = (day if nxt > minute else day + 1, nxt)
            if gametime.diff(t1, start) >= 0 or gametime.diff(end, t0) > 0:
                continue
            rows.append((t0, t1, target, note))
    return rows


def _fmt_span(t0, t1):
    return f"{gametime.fmt(t0)}–{gametime.fmt_clock(t1[1])}"


def trace(name, frm=None, to=None):
    state = campaign.load_state()
    now = gametime.parse(state.front.get("in-game-datetime"))
    end = gametime.parse(to) if to else now
    start = gametime.parse(frm) if frm else gametime.normalize(end[0], end[1] - 24 * 60)
    evs = [e for e in events() if e[0] is not None and gametime.diff(start, e[0]) >= 0
           and gametime.diff(e[0], end) >= 0]
    loc_file = campaign.path("locations", name.split("/")[0])
    try:
        m = campaign.resolve(name, state)
    except campaign.CampaignError:
        m = None
    lines = [f"[TRACE] {name} · {gametime.fmt(start)} → {gametime.fmt(end)}"]
    rows = []
    if m is not None and m.doc is not None and not loc_file.exists():
        first = str(m.doc.front.get("name")).split()[0].lower()
        mine = [e for e in evs if first in e[1].lower()]
        for when, text, gm, turn, f in mine:
            what = re.sub(r"^move-(?:npc|party)\s+", "", text)
            what = re.sub(rf"^{re.escape(str(m.doc.front.get('name')))}\s*|^{re.escape(first)}\w*\s*", "", what,
                          flags=re.I)
            rows.append((when, f"{gametime.fmt(when):<19} {what:<46} logged{' (GM)' if gm else ''}"
                               + (f" turn {turn}" if turn else "") + (f" [{f}]" if f != "current" else "")))
        if not m.is_pc:
            for t0, t1, target, note in _schedule_rows(m.doc, start, end):
                covered = any(gametime.diff(t0, e[0]) >= 0 and gametime.diff(e[0], t1) > 0 for e in mine)
                if not covered:
                    rows.append((t0, f"{_fmt_span(t0, t1):<19} {target + (' ' + note if note else ''):<46} scheduled"))
    elif loc_file.exists():
        site = name.split("/")[0]
        for when, text, gm, turn, f in evs:
            if site in text:
                rows.append((when, f"{gametime.fmt(when):<19} {text:<56} logged{' (GM)' if gm else ''}"
                                   + (f" turn {turn}" if turn else "")))
        for d in campaign.npcs():
            who = str(d.front.get("name")).split()[0]
            for t0, t1, target, note in _schedule_rows(d, start, end):
                if target.split("/")[0] == site:
                    rows.append((t0, f"{_fmt_span(t0, t1):<19} {who} at {target:<40} scheduled"))
    else:
        raise TraceError(f"trace: no creature or location named {name!r}")
    rows.sort(key=lambda r: (r[0][0], r[0][1]))
    lines += ["  " + r[1].rstrip() for r in rows] or ["  (nothing logged or scheduled in the window)"]
    return lines


def cmd_trace(ctx):
    a = ctx.args
    lines = trace(" ".join(a.name), a.from_, a.to)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("trace", parents=[g], help="trace <name|location> [--from …] [--to …]")
    p.add_argument("name", nargs="+")
    p.add_argument("--from", dest="from_")
    p.add_argument("--to")
    p.set_defaults(func=cmd_trace)
