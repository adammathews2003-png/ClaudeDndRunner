"""`gm.py where [<name>] [--from <place>]` (docs/design/06 → `gm.py where`; plan.md Phase 7
item 6). From frontmatter only — the cheap answer to "check the record".

- no name: the party's location and who is there;
- a PC/NPC: where they are (on the road: which route, how far along, due when) and
  what their schedule says now;
- a place (location slug or Places id): the relational view from `--from` (default:
  the party's site) — bearing, straight-line distance, route time — plus who is there
  and who is scheduled there:

    [WHERE] old-mill (site, in thornbury) · from crossroads-inn
      bearing N · straight line 0.8 mi · by route 15 min (inn-door, mill-rd)
      here: (nobody)   scheduled: Veskar 00:00–04:00
"""
import re

from lib import campaign, gametime, geo
from lib.errors import ToolError
import clock


class WhereError(ToolError):
    pass


def _who_at(site):
    out = []
    for d in campaign.pcs() + campaign.npcs():
        loc = str(d.front.get("location") or "")
        if loc.split("/")[0] == site and str(d.front.get("status") or "").lower() != "dead":
            out.append(str(d.front.get("name")).split()[0] + (f" ({loc.split('/', 1)[1]})" if "/" in loc else ""))
    return out


def _scheduled(site):
    out = []
    for d in campaign.npcs():
        span = d.section("Movements")
        for i in range(span[0] + 1, span[1]) if span else []:
            m = re.match(r"^\s*-\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*→\s*(\S+)", d.body[i])
            if m and m.group(3).split("/")[0] == site:
                out.append(f"{str(d.front.get('name')).split()[0]} {m.group(1)}–{m.group(2)}")
    return out


def _now():
    try:
        return gametime.parse(campaign.load_state().front.get("in-game-datetime"))
    except gametime.TimeError:
        return None


def where_creature(m):
    d = m.doc
    name = str(d.front.get("name"))
    loc = str(d.front.get("location") or "?")
    now = _now()
    info = clock.transit_info(d.front, now)
    if info:
        pct = int(round(info.get("fraction", 0) * 100))
        line = (f"[WHERE] {name} · on {loc[1:]} (→ {info['to']}, about {pct}% of the way; "
                f"left {gametime.fmt_clock(info['depart'][1])}, due {gametime.fmt_clock(info['eta'][1])})")
    else:
        line = f"[WHERE] {name} · {loc}"
    lines = [line]
    if not m.is_pc and now is not None:
        sched = None
        for minute, target, note in clock.movements(d):
            sched = sched or (minute, target, note)
            if minute <= now[1]:
                sched = (minute, target, note)
        if sched:
            lines.append(f"  schedule now: → {sched[1]} since {gametime.fmt_clock(sched[0])}"
                         + (f" {sched[2]}" if sched[2] else ""))
    return lines


def where_place(target, frm):
    site = target
    if not campaign.path("locations", site).exists():
        here = frm.split("/")[0]
        for frame, _ in geo.chain(here):
            p = frame.place(target)
            if p is not None:
                site = p.ref or p.id
                break
    tier, parent = "place", None
    try:
        f = geo.load(site)
        tier, parent = f.tier, f.parent
    except geo.GeoError:
        pass
    src = frm.split("/")[0]
    head = f"[WHERE] {site} ({tier}" + (f", in {parent}" if parent else "") + f") · from {src}"
    lines = [head]
    up = geo.chain(src)
    down = {fr.slug: n for fr, n in geo.chain(site)}
    for fr in [x for x, _ in up]:
        node_dst = fr.place(target) or fr.place_for_ref(site)
        node_src = next((n for x, n in up if x.slug == fr.slug), None)
        if node_dst is None and fr.slug in down:
            node_dst = fr.place(down[fr.slug])
        if node_dst is None or node_src is None:
            continue
        a = fr.place(node_src)
        bits = []
        if a is not None and a.placed and node_dst.placed:
            bits.append(f"bearing {geo.bearing(a.center(), node_dst.center())}")
            bits.append(f"straight line {geo.distance_text(geo.edge_distance(a, node_dst), fr.unit)}")
        try:
            plan = geo._dijkstra(fr, node_src, node_dst.id)
            bits.append(f"by route {geo.fmt_minutes(plan.rounded)} ({', '.join(r.id for r in plan.routes)})")
        except geo.GeoError:
            bits.append("no route")
        lines.append("  " + " · ".join(bits))
        break
    here = _who_at(site)
    sched = _scheduled(site)
    lines.append(f"  here: {', '.join(here) if here else '(nobody)'}   "
                 f"scheduled: {', '.join(sched) if sched else '—'}")
    return lines


def cmd_where(ctx):
    a = ctx.args
    state = campaign.load_state()
    party = str(state.front.get("party-location") or "")
    if not a.name:
        site = party.split("/")[0]
        lines = [f"[WHERE] the party · {party}", f"  here: {', '.join(_who_at(site)) or '(nobody)'}"]
    else:
        name = " ".join(a.name)
        try:
            m = campaign.resolve(name, state)
        except campaign.CampaignError:
            m = None
        if m is not None and m.doc is not None and m.kind in ("pc", "npc", "onstage", "stage"):
            lines = where_creature(m)
        else:
            lines = where_place(name, a.from_ or party)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("where", parents=[g], help="where [<name|place>] [--from <place>]")
    p.add_argument("name", nargs="*")
    p.add_argument("--from", dest="from_")
    p.set_defaults(func=cmd_where)
