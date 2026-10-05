"""`gm.py clock advance <+20m|+2h|+1d|to 06:00|to dawn>` (planning/06 → `gm.py clock
advance`; 05 #7; 02 → The open world, "Travel is visible"; plan.md Phase 7 item 1).

Advances `in-game-datetime` and reports everything it crossed:

    [TIME] Day 1 19:40 → Day 2 00:10 (+4h30m)
      Movements: Veskar left crossroads-inn/upstairs 00:00 by back-lane, mill-rd → old-mill, due 00:16  [off-stage — in transit]
      Conditions expired: Kira poisoned
      Clocks: none fired · next: Day 3 04:00 Red Ledger cart (in 1d 3h50m)

- `## Movements` lines (`- HH:MM–HH:MM → site[/area] (note)`) are daily departures.
  Off-stage NPCs are moved: nobody teleports — the route is found (lib/geo.py) and
  the NPC is `location: "@<route id>"` with a `transit:` line until arrival, when
  `location:` flips to the destination. No route → an instant move plus a `[LINT]`
  warning. In-site moves (same site) are instant. On-stage NPCs are only listed as
  intents for the GM to narrate or override.
- Conditions with minute/hour durations (`poisoned 10m`, `blessed 1h`) count down on
  PC/NPC files; expiries are reported.
- Scenario `- CLOCK Day N HH:MM:` lines and `## Clocks` bullets that fall inside the
  window fire: printed in full and logged as `(GM)` lines. Whether a beat happens is
  the GM's call.
Python API: `advance(spec)` -> (lines, data); `transit_info(front, now)`.
"""
import re
from pathlib import Path

from lib import campaign, gametime, geo, journal, md
from lib.errors import ToolError

_MOVE = re.compile(r"^\s*-\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*→\s*(\S+)\s*(.*)$")
_CLOCK = re.compile(r"^\s*-\s*(?:CLOCK\s+)?(Day\s+-?\d+\s+\d{1,2}:\d{2})\s*:\s*(.+)$", re.I)
_TRANSIT = re.compile(r"^to (\S+) · depart (Day -?\d+ \d\d:\d\d) · eta (Day -?\d+ \d\d:\d\d) · "
                      r"from (\S+) · via (.*)$")
_DUR = re.compile(r"^(\S+)\s+(\d+)([mh])$", re.I)


class ClockError(ToolError):
    pass


def movements(doc):
    """[(depart minute, target, note)] from an NPC's `## Movements` section."""
    span = doc.section("Movements")
    if span is None:
        return []
    out = []
    for i in range(span[0] + 1, span[1]):
        m = _MOVE.match(doc.body[i])
        if m:
            out.append((gametime.parse_clock(m.group(1)), m.group(3).strip(), m.group(4).strip()))
    return out


def transit_info(front, now=None):
    """{to, depart, eta, from, via, fraction} for an NPC on the road, else None."""
    m = _TRANSIT.match(str(front.get("transit") or ""))
    if not m:
        return None
    dep, eta = gametime.parse(m.group(2)), gametime.parse(m.group(3))
    info = {"to": m.group(1), "depart": dep, "eta": eta, "from": m.group(4),
            "via": [v.strip() for v in m.group(5).split(",") if v.strip()]}
    if now is not None:
        total = max(1, gametime.diff(dep, eta))
        info["fraction"] = max(0.0, min(1.0, gametime.diff(dep, now) / total))
    return info


def on_stage_names(state):
    names = {m.name.lower() for m in campaign.stage_matches(state)}
    t = state.table("Combatants")
    for r in (t.rows if t else []):
        names.add(re.sub(r"\s*\(PC\)", "", r.get("name", ""), flags=re.I).strip().lower())
    return names


def _first(name):
    return str(name or "").split()[0]


def _leg_at(plan, depart, when):
    """The route id the traveller is on at `when` (by cumulative leg time)."""
    elapsed = gametime.diff(depart, when)
    acc = 0.0
    for r in plan.routes:
        m = geo.route_minutes(plan.frame, r) or 0
        acc += m
        if elapsed < acc:
            return r.id
    return plan.routes[-1].id if plan.routes else "?"


def _crossings(old, new, sched):
    """[(time, target, note)] departures in (old, new], in order."""
    out = []
    for day in range(old[0], new[0] + 1):
        for minute, target, note in sched:
            t = (day, minute)
            if gametime.diff(old, t) > 0 and gametime.diff(t, new) >= 0:
                out.append((t, target, note))
    out.sort(key=lambda x: (x[0][0], x[0][1]))
    return out


def _npc_moves(old, new, state, on_stage):
    lines, lint = [], []
    for doc in campaign.npcs():
        if str(doc.front.get("status") or "").lower() == "dead":
            continue
        name = _first(doc.front.get("name"))
        here_on_stage = name.lower() in on_stage or str(doc.front.get("name", "")).lower() in on_stage
        # 1. arrivals of NPCs already on the road
        info = transit_info(doc.front, new)
        if info and gametime.diff(info["eta"], new) >= 0:
            doc.set_front("location", info["to"])
            doc.set_front("transit", None)
            doc.save()
            lines.append(f"{name} arrived at {info['to']} {gametime.fmt_clock(info['eta'][1])}")
            journal.log_delta(f"move-npc {name} → {info['to']} (arrived {gametime.fmt(info['eta'])})", gm=True)
        elif info:
            continue  # still travelling
        # 2. scheduled departures in the window
        for when, target, note in _crossings(old, new, movements(doc)):
            loc = str(doc.front.get("location") or "")
            if loc.startswith("@"):
                break
            if loc == target or loc.split("/")[0] == target and "/" not in target:
                continue
            if not campaign.path("locations", target.split("/")[0]).exists():
                lint.append(f"[LINT] warning: {name}'s Movements line → {target!r} is not a location "
                            "(schedule lines are `- HH:MM–HH:MM → site[/area] (note)`); skipped")
                continue
            if here_on_stage:
                lines.append(f"{name} intends to leave for {target} at {gametime.fmt_clock(when[1])}"
                             f"{' ' + note if note else ''}  [on stage — narrate or override]")
                break
            same_site = loc.split("/")[0] == target.split("/")[0]
            plan = None
            if not same_site:
                try:
                    plan = geo.find_route(loc, target.split("/")[0])
                except geo.GeoError:
                    plan = None
            if same_site or plan is None or plan.minutes is None:
                doc.set_front("location", target)
                doc.save()
                lines.append(f"{name} moved {loc} → {target} at {gametime.fmt_clock(when[1])}"
                             + ("" if same_site else "  [no route: instant]"))
                journal.log_delta(f"move-npc {name} {loc}→{target} at {gametime.fmt(when)}", gm=True)
                if not same_site:
                    lint.append(f"[LINT] warning: {name}'s Movements → {target} has no route from {loc}")
                continue
            minutes = geo.round_minutes(plan.minutes)
            eta = gametime.normalize(when[0], when[1] + minutes)
            via = ", ".join(r.id for r in plan.routes)
            journal.log_delta(f"move-npc {name} left {loc} {gametime.fmt(when)} by {via} → {target}, "
                              f"due {gametime.fmt(eta)}", gm=True)
            if gametime.diff(eta, new) >= 0:
                doc.set_front("location", target)
                doc.save()
                lines.append(f"{name} left {loc} {gametime.fmt_clock(when[1])} by {via} → {target}, "
                             f"arrived {gametime.fmt_clock(eta[1])}  [off-stage]")
                continue
            leg = _leg_at(plan, when, new)
            doc.set_front("location", f"@{leg}")
            doc.set_front("transit", f"to {target} · depart {gametime.fmt(when)} · eta {gametime.fmt(eta)} · "
                                     f"from {loc} · via {via}")
            doc.save()
            lines.append(f"{name} left {loc} {gametime.fmt_clock(when[1])} by {via} → {target}, "
                         f"due {gametime.fmt_clock(eta[1])}  [off-stage — in transit]")
            break
    return lines, lint


def _tick_conditions(minutes):
    expired = []
    for doc in campaign.pcs() + campaign.npcs():
        conds = [str(c) for c in (doc.front.get("conditions") or []) if str(c).strip()]
        kept, changed = [], False
        for c in conds:
            m = _DUR.match(c)
            if not m:
                kept.append(c)
                continue
            left = int(m.group(2)) * (60 if m.group(3).lower() == "h" else 1) - minutes
            changed = True
            if left <= 0:
                expired.append(f"{_first(doc.front.get('name'))} {m.group(1)}")
            else:
                kept.append(f"{m.group(1)} {left // 60}h" if left % 60 == 0 and left >= 60 else f"{m.group(1)} {left}m")
        if changed:
            doc.set_front("conditions", kept)
            doc.save()
    for e in expired:
        journal.log_delta(f"cond {e} expired")
    return expired


def clock_lines(state):
    """[(time, text, source)] from the scenarios' CLOCK beats and current.md's Clocks."""
    out, seen = [], set()
    folder = campaign.root() / "scenarios"
    for p in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        doc = md.load(p)
        span = doc.section("Beats")
        for i in range(span[0] + 1, span[1]) if span else []:
            line = doc.body[i]
            if not re.match(r"^\s*-\s*CLOCK\b", line):
                continue
            m = _CLOCK.match(line)
            if m:
                t = gametime.parse(m.group(1))
                out.append((t, m.group(2).strip(), p.stem))
                seen.add(gametime.fmt(t))
    span = state.section("Clocks")
    for i in range(span[0] + 1, span[1]) if span else []:
        m = _CLOCK.match(state.body[i])
        if m:
            try:
                t = gametime.parse(m.group(1))
            except gametime.TimeError:
                continue
            if gametime.fmt(t) not in seen:
                out.append((t, m.group(2).strip(), "current"))
    out.sort(key=lambda x: (x[0][0], x[0][1]))
    return out


def advance(spec, *, log_time=True):
    state = campaign.load_state()
    old = gametime.parse(state.front.get("in-game-datetime"))
    spec = spec.strip()
    if spec.startswith("-"):
        raise ClockError("clock advance goes forward; use `time -5m` to correct a mistake")
    new = gametime.add(old, spec)
    minutes = gametime.diff(old, new)
    on_stage = on_stage_names(state)
    state.set_front("in-game-datetime", gametime.fmt(new))
    state.save()
    if log_time:
        journal.log_delta(f"time {gametime.fmt(old)}→{gametime.fmt(new)}")
    lines = [f"[TIME] {gametime.fmt(old)} → {gametime.fmt(new)} (+{gametime.fmt_delta(minutes)})"]
    moves, lint = _npc_moves(old, new, state, on_stage)
    if moves:
        lines.append("  Movements: " + " · ".join(moves))
    expired = _tick_conditions(minutes)
    if expired:
        lines.append("  Conditions expired: " + ", ".join(expired))
    fired, nxt = [], None
    for t, text, src in clock_lines(campaign.load_state()):
        if gametime.diff(old, t) > 0 and gametime.diff(t, new) >= 0:
            fired.append((t, text, src))
        elif gametime.diff(new, t) > 0 and nxt is None:
            nxt = (t, text)
    for t, text, src in fired:
        lines.append(f"  CLOCK {gametime.fmt(t)} ({src}): {text}")
        journal.log_delta(f"clock fired {gametime.fmt(t)}: {text[:120]}", gm=True)
    tail = f"{len(fired)} fired" if fired else "none fired"
    if nxt:
        short = re.split(r"(?<=[.;:])\s", nxt[1])[0].rstrip(".;:")
        short = re.sub(r"\s*\([^)]*\)\s*$", "", short)
        if len(short) > 60:
            short = short[:60].rsplit(" ", 1)[0] + "…"
        tail += f" · next: {gametime.fmt(nxt[0])} {short} (in {gametime.fmt_delta(gametime.diff(new, nxt[0]))})"
    lines.append("  Clocks: " + tail)
    lines += lint
    return lines, {"from": gametime.fmt(old), "to": gametime.fmt(new), "minutes": minutes,
                   "fired": [gametime.fmt(t) for t, _, _ in fired], "expired": expired}


def cmd_clock(ctx):
    lines, data = advance(" ".join(ctx.args.spec))
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("clock", parents=[g], help="clock advance <+20m|+2h|to 06:00|to dawn>")
    p.add_argument("action", choices=["advance"])
    p.add_argument("spec", nargs="+")
    p.set_defaults(func=cmd_clock)
