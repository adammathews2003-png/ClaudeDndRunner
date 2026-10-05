"""`gm.py travel <to> [--pace fast|normal|slow] [--by foot|cart|horse|boat] [--night]
[--overland] [--unlocked] [--light bright|dim|dark]` (docs/design/06 → `gm.py travel`; 04 →
Deriving travel time; 02 → The open world; plan.md Phase 7 item 2).

Finds a route from the party's location to `<to>` (a location `site[/area]`, or a place
id in an enclosing frame that has a file): the `## Routes` rows chained through site,
area and world frames (lib/geo.py). No route = error — nobody teleports; `--overland`
allows a straight-line trip at trackless pace and logs it. Inside a site with a
`## Routes` table, the in-site route is checked: `locked` rows refuse unless
`--unlocked` (the party opened it), `DC N to notice` rows are flagged.

Then: encounter rolls (secret; the route's `tables/encounters-<route id>.md`, else the
destination area's `tables/encounters-<area>.md`; one roll per 4 h, per 2 h with
`--night`; skipped while the table rule `encounters=off` is active), a `passes:` line
(placed features within 100 ft of the path), `clock advance`, and `scene enter <to>
--write` (which moves the party). Output = the travel line plus all the packets.
"""
import math
import re

from lib import campaign, dice, geo, journal, resolve
from lib.errors import ToolError
import clock
import scene
import tempo

PASS_FT = 100


class TravelError(ToolError):
    pass


def _dest(to):
    """(site, area or None, location text)."""
    to = to.strip().lower()
    site, _, area = to.partition("/")
    if campaign.path("locations", site).exists():
        return site, area or None, to
    state = campaign.load_state()
    here = str(state.front.get("party-location") or "").split("/")[0]
    for frame, _ in geo.chain(here):
        p = frame.place(site)
        if p is not None:
            if not p.ref:
                raise TravelError(f"travel: {p.feature} has no location file yet "
                                  f"(gm.py stub location \"{p.feature}\" --in {frame.slug})")
            return p.ref, area or None, p.ref + (f"/{area}" if area else "")
    raise TravelError(f"travel: no place {to!r}")


def _in_site(frame, src_area, dst_area, unlocked):
    """(minutes, [route ids], notes) through a site's own Routes."""
    if not frame.routes:
        return 0, [], ["no in-site Routes: unchecked move"]
    graph = {}
    for r in frame.routes:
        a, b = r.ends()
        graph.setdefault(a, []).append((b, r))
        graph.setdefault(b, []).append((a, r))
    best, prev, todo = {src_area: 0}, {}, [src_area]
    while todo:
        cur = min(todo, key=lambda n: best[n])
        todo.remove(cur)
        for nxt, r in graph.get(cur, []):
            c = best[cur] + (geo.parse_time(r.time) or 1)
            if c < best.get(nxt, math.inf):
                best[nxt], prev[nxt] = c, (cur, r)
                todo.append(nxt)
    if dst_area not in best:
        raise TravelError(f"travel: no route inside {frame.slug} from {src_area} to {dst_area}")
    routes, cur = [], dst_area
    while cur != src_area:
        cur, r = prev[cur]
        routes.append(r)
    routes.reverse()
    notes = []
    for r in routes:
        acc = r.access.lower()
        if "secret" in acc:
            notes.append(f"{r.id}: secret (the party must have found it)")
        if re.search(r"\blocked\b", acc) and not unlocked:
            raise TravelError(f"travel: {r.id} is locked ({r.access}) — open it first, then --unlocked")
        if re.search(r"\bbarred\b", acc) and not unlocked:
            notes.append(f"{r.id}: {r.access}")
        m = re.search(r"dc\s*(\d+)\s*to notice", acc)
        if m:
            notes.append(f"{r.id}: hidden (DC {m.group(1)} to notice — only if the party knows it)")
    return best[dst_area], [r.id for r in routes], notes


def _exit_area(frame, route, site_slug):
    """The sub-area of `site_slug` holding the Layout exit a parent-frame route names
    (`inn.door` → the `door` row's ### block), or None."""
    node = frame.place_for_ref(site_slug)
    if node is None:
        return None
    for end in (route.frm, route.to):
        base, _, ex = end.partition(".")
        if base.strip() == node.id and ex:
            try:
                lay, row = geo.load(site_slug).layout_row(ex.strip())
            except geo.GeoError:
                return None
            return lay.area if lay is not None else None
    return None


def _overland(src_site, dst_site, pace, by):
    up = geo.chain(src_site)
    down = {f.slug: n for f, n in geo.chain(dst_site)}
    for frame, node in up:
        if frame.slug in down:
            a, b = frame.place(node), frame.place(down[frame.slug])
            if a is None or b is None or not (a.placed and b.placed):
                break
            d = geo.edge_distance(a, b)
            per = geo.MI_PER_MIN if frame.unit == "mi" else geo.FT_PER_MIN
            mins = d / per * geo.KIND_FACTOR["trackless"] * geo.PACE.get(pace, 1) * geo.conveyance_factor("trackless", by)
            return frame, mins, [(a.center(), b.center())]
    raise TravelError(f"travel --overland: {src_site} and {dst_site} aren't both placed in a shared frame")


def _path_points(frame, routes):
    segs = []
    for r in routes:
        ga, gb = geo._geom(frame, r.frm), geo._geom(frame, r.to)
        if ga is None or gb is None:
            continue
        if r.via:
            pts = [geo._clamp(ga, r.via[0])] + list(r.via) + [geo._clamp(gb, r.via[-1])]
        else:
            pts = list(geo._closest_pair(ga, gb))
        segs += list(zip(pts, pts[1:]))
    return segs


def _seg_box_dist(p, q, lo, hi, step):
    n = max(1, int(math.dist(p[:2], q[:2]) / step))
    best = math.inf
    for i in range(n + 1):
        t = i / n
        x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
        dx = max(lo[0] - x, 0, x - hi[0])
        dy = max(lo[1] - y, 0, y - hi[1])
        best = min(best, math.hypot(dx, dy))
    return best


def passes(frame, segs, skip):
    limit = PASS_FT if frame.unit == "ft" else PASS_FT / geo.FT_PER_MI
    step = 25 if frame.unit == "ft" else 25 / geo.FT_PER_MI
    out = []
    for pl in frame.places:
        if pl.id in skip or not pl.placed or pl.secret:
            continue
        lo, hi = pl.box()
        if any(_seg_box_dist(p, q, lo, hi, step) <= limit for p, q in segs):
            out.append(pl.feature)
    return out


def encounters(route_ids, dest_site, minutes, night, roller):
    if resolve.active_keys().get("encounters", {}).get("value") == "off":
        return ["  Encounters: off (table rule)"]
    tables = campaign.root() / "tables"
    slug = None
    for rid in route_ids:
        if (tables / f"encounters-{rid}.md").exists():
            slug = f"encounters-{rid}"
            break
    if slug is None:
        try:
            parent = geo.load(dest_site).parent
        except geo.GeoError:
            parent = None
        if parent and (tables / f"encounters-{parent}.md").exists():
            slug = f"encounters-{parent}"
    if slug is None:
        return []
    n = max(1, math.ceil(minutes / (120 if night else 240)))
    out = []
    for _ in range(n):
        res = roller.roll_table(tables / f"{slug}.md", slug, secret=True)
        out.append("  Encounter " + res.text)
        journal.log_delta(f"roll SECRET {res.label}: {res.body}", gm=True)
    return out


def travel(to, pace="normal", by="foot", night=False, overland=False, unlocked=False, light=None, roller=None):
    state = campaign.load_state()
    if tempo.in_combat(state):
        raise TravelError("travel: combat is running (combat end first)")
    here = str(state.front.get("party-location") or "")
    src_site, _, src_area = here.partition("/")
    site, area, loc = _dest(to)
    roller = roller or dice.Roller()
    lines, notes, route_ids, segs, frame = [], [], [], [], None
    if site == src_site:
        if not area or area == src_area:
            raise TravelError(f"travel: the party is already at {here}")
        sframe = geo.load(site)
        mins, route_ids, notes = _in_site(sframe, src_area or "", area, unlocked)
        minutes = mins
        how = ", ".join(route_ids) or "unchecked"
    elif overland:
        frame, raw, segs = _overland(src_site, site, pace, by)
        minutes = geo.round_minutes(raw)
        how = "overland (trackless)"
        notes.append("cross-country: no road")
    else:
        try:
            plan = geo.find_route(here, site, pace, by)
        except geo.NoRoute as e:
            raise TravelError(f"travel: {e} (no teleporting; --overland for cross-country)") from None
        if plan.minutes is None:
            raise TravelError("travel: a leg of the route has no coordinates or time (lint will say which)")
        minutes = geo.round_minutes(plan.minutes) if plan.routes else 1
        route_ids = [r.id for r in plan.routes]
        frame = plan.frame
        segs = _path_points(frame, plan.routes)
        # in-site legs: from the party's area to the exit the route leaves by, and from
        # the exit it arrives by to the destination area (e.g. cellar → trapdoor → door)
        if plan.routes:
            out_area = _exit_area(frame, plan.routes[0], src_site)
            if out_area and src_area and out_area != src_area:
                m, ids, nts = _in_site(geo.load(src_site), src_area, out_area, unlocked)
                minutes += m
                route_ids = ids + route_ids
                notes += nts
            in_area = _exit_area(frame, plan.routes[-1], site)
            if in_area and area and in_area != area:
                m, ids, nts = _in_site(geo.load(site), in_area, area, unlocked)
                minutes += m
                route_ids = route_ids + ids
                notes += nts
        how = ", ".join(route_ids)
    head = f"[TRAVEL] {here} → {loc} · {geo.fmt_minutes(minutes)} ({how}) · {pace} pace" + \
           (f" by {by}" if by != "foot" else " on foot") + (" · at night" if night else "")
    lines.append(head)
    for n in notes:
        lines.append(f"  note: {n}")
    if frame is not None and segs:
        skip = set()
        for f, node in geo.chain(src_site) + geo.chain(site):
            if f.slug == frame.slug:
                skip.add(node)
        got = passes(frame, segs, skip)
        lines.append("  passes: " + (", ".join(got) if got else "open country"))
    if site != src_site:
        lines += encounters(route_ids, site, minutes, night, roller)
    journal.log_delta(f"travel {here} → {loc} ({geo.fmt_minutes(minutes)}, {how})")
    clk, _ = clock.advance(f"+{max(0, minutes)}m") if minutes else ([], {})
    lines += clk
    packet, _ = scene.enter(loc, None, light or ("dim" if night else None), write=True)
    lines += packet
    return lines, {"to": loc, "minutes": minutes, "routes": route_ids}


def cmd_travel(ctx):
    a = ctx.args
    lines, data = travel(a.to, a.pace, a.by, a.night, a.overland, a.unlocked, a.light, ctx.roller)
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("travel", parents=[g], help="travel <to>: route, time, encounters, clock, scene")
    p.add_argument("to")
    p.add_argument("--pace", choices=["fast", "normal", "slow"], default="normal")
    p.add_argument("--by", choices=["foot", "cart", "wagon", "horse", "boat"], default="foot")
    p.add_argument("--night", action="store_true")
    p.add_argument("--overland", action="store_true", help="straight line at trackless pace")
    p.add_argument("--unlocked", action="store_true", help="the party has opened a locked way")
    p.add_argument("--light", choices=["bright", "dim", "dark"])
    p.set_defaults(func=cmd_travel)
