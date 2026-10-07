"""Travel as play: activities, navigation and getting lost, foraging, watchers, forced
marches, and the marching order (docs/design/02 → Table mechanics → Phase 14 → Travel
as play; 04 → Scene state added (`marching-order:`, Navigation); 06 → Table mechanics
→ Phase 14; plan.md Phase 14 item 2).

    travel <to> --plan [--activities Kira=navigate,Kael=watch,Grusk=forage]   (travel.py)
    travel <to> --nav <total> [--forage Grusk=<total>] [--hours 10]           (travel.py)
    order front=Kael middle=Kira back=Grusk | order | order clear

travel.py finds the route; this module works out what the journey asks for. Under
`travel-detail: activities` each PC does one thing: navigate, forage, track, map or
watch (anyone not named watches). A leg can be lost on only when its route `kind` is
off the roads (trail, trackless, marsh, scree, and `--overland`): the navigator's
Survival total against the terrain DC (grassland/coast 5; arctic, desert, hills, sea
10; forest, jungle, swamp, mountains 15; no `terrain:` → 10). A miss with
`getting-lost: on` sends the party 1d6 hours on a wrong bearing (d6: 1–2 60° left,
3–4 60° right, 5 120° left, 6 120° right of the intended one) from where that leg
starts, measured in the top (world) frame: they end there, `party-location: "@lost"`,
with a `lost:` line saying where, and travel from there is straight-line
cross-country to the place they name (the navigator checks again). Road legs before
the first trackless one are walked as normal; nothing is ever moved along a route the
party didn't take.

Foraging is food, so it follows `supplies`: off (the default) → nothing is counted or
added. Otherwise Survival DC 10 / 15 / 20 (abundant / limited / scarce; `forage:` on the
route or the area, default limited); success adds 1d6 + WIS mod rations and fills the
waterskin. Only watchers' passive Perception counts against ambushes (fast pace −5);
the marching order names who meets trouble first. More than 8 hours on the march
(`--hours`, default the trip's length) asks for a CON save each hour from hour 9 (DC
11, +1 per further hour; a failure is `exhaust +1`): the tool asks, the players roll.

Python API for travel.py: `lostable(route)`, `nav_dc(terrain)`, `plan_lines(r, …)`,
`journey(r, …)`, `order_line(state)`, `lost_info(state)`, `world_point(frame, p)`.
"""
import json
import math
import re

from lib import campaign, creatures, geo, journal, md
from lib.errors import ToolError
import inventory

ACTIVITIES = ("navigate", "forage", "track", "map", "watch")
SAFE_KINDS = ("road", "street", "path", "lane", "door", "trapdoor", "stairs", "gate", "ladder")
NAV_DC = {"grassland": 5, "coast": 5, "arctic": 10, "desert": 10, "hills": 10, "sea": 10,
          "forest": 15, "jungle": 15, "swamp": 15, "mountains": 15}
TERRAINS = tuple(NAV_DC)
FORAGE_DC = {"abundant": 10, "limited": 15, "scarce": 20}
DEFAULT_NAV_DC = 10
WRONG = {1: 60, 2: 60, 3: -60, 4: -60, 5: 120, 6: -120}   # degrees counter-clockwise (left)
ROWS = ("front", "middle", "back")
_LOST = re.compile(r"^to (\S+) · at \(([^)]*)\) (\S+) · bearing (\S+) \(meant (\S+)\) · "
                   r"terrain (\S+) · since (.+)$")


class ExploreError(ToolError):
    pass


def setting(key):
    return str(campaign.settings().get(key, campaign.SETTINGS[key])).strip().lower()


def _first(name):
    return str(name or "?").split()[0]


# ---------- terrain ----------

def lostable(kind):
    return (kind or "").lower() not in SAFE_KINDS


def nav_dc(terrain):
    return NAV_DC.get((terrain or "").lower(), DEFAULT_NAV_DC)


def _front_tag(frame, key):
    v = str(frame.doc.front.get(key) or "").strip().lower() if frame is not None else ""
    return v


def leg_terrain(frame, route, dest_site=None):
    """(terrain, forage) of a leg: the route's own, else the frame's (area), else the
    destination's, else ''."""
    t, f = (route.terrain, route.forage) if route is not None else ("", "")
    for src in (frame, _safe_load(dest_site)):
        t = t or _front_tag(src, "terrain")
        f = f or _front_tag(src, "forage")
    return t, f or "limited"


def _safe_load(slug):
    if not slug:
        return None
    try:
        return geo.load(slug)
    except geo.GeoError:
        return None


# ---------- world-frame points ----------

def world_point(frame, point):
    """(top frame, point in it): `point` in `frame` carried up the parent chain."""
    seen = set()
    while frame.parent and frame.slug not in seen:
        seen.add(frame.slug)
        par, row = geo.parent_of(frame)
        if par is None or row is None or row.at is None:
            break
        point = geo.to_parent(frame, point)
        frame = par
    return frame, point


def node_point(frame, node):
    g = geo._geom(frame, node)
    if g is None:
        return None
    if g[0] == "point":
        return g[1]
    return tuple((a + b) / 2 for a, b in zip(g[1], g[2]))


def site_point(site):
    """(top frame, point) of a site's footprint centre, via its Places row upward."""
    frame = geo.load(site)
    par, row = geo.parent_of(frame)
    if par is None or row is None or not row.placed:
        raise ExploreError(f"{site} isn't placed on a map (no coordinates to travel toward)")
    return world_point(par, row.center())


def _fmt_pt(p):
    return ",".join(f"{v:.2f}".rstrip("0").rstrip(".") for v in p)


def _bearing_word(deg):
    words = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")
    return words[round(deg / 45) % 8]


# ---------- the lost state ----------

def lost_info(state=None):
    """{to, at, frame, bearing, meant, terrain, since} while the party is lost, else None."""
    state = state or campaign.load_state()
    if str(state.front.get("party-location") or "") != "@lost":
        return None
    m = _LOST.match(str(state.front.get("lost") or ""))
    if not m:
        raise ExploreError("party-location is @lost but the `lost:` line is unreadable")
    pt = tuple(float(x) for x in m.group(2).split(","))
    return {"to": m.group(1), "at": pt + (0.0,) * (3 - len(pt)), "frame": m.group(3),
            "bearing": m.group(4), "meant": m.group(5), "terrain": m.group(6), "since": m.group(7)}


def set_lost(to, frame_slug, point, bearing, meant, terrain, when):
    state = campaign.load_state()
    old = str(state.front.get("party-location") or "")
    names = []
    for doc in campaign.scene_pcs(include_absent=True):
        doc.set_front("location", "@lost")
        doc.save()
        names.append(_first(doc.front.get("name")))
    state.set_front("party-location", "@lost")
    state.set_front("lost", f"to {to} · at ({_fmt_pt(point)}) {frame_slug} · bearing {bearing} "
                            f"(meant {meant}) · terrain {terrain or '?'} · since {when}")
    state.save()
    journal.log_delta(f"move-party {old}→@lost ({', '.join(names)}): off course, bearing {bearing} "
                      f"instead of {meant}, at ({_fmt_pt(point)}) {frame_slug}", gm=True)


def clear_lost(state):
    state.del_front("lost")


# ---------- activities ----------

def parse_assign(text, what="--activities"):
    """`Kira=navigate,Kael=watch` → {pc first name: value} (PCs of the active group)."""
    out = {}
    for part in [p for p in (text or "").split(",") if p.strip()]:
        name, sep, val = part.partition("=")
        if not sep:
            raise ExploreError(f"{what} wants Name=value, got {part!r}")
        doc = _pc(name.strip())
        out[_first(doc.front.get("name"))] = val.strip().lower()
    return out


def _pc(name):
    want = name.strip().lower()
    for d in campaign.scene_pcs(include_absent=True):
        full = str(d.front.get("name") or "").lower()
        if want in (full, full.split()[0] if full else "") or full.startswith(want):
            return d
    raise ExploreError(f"{name}: not a PC in this scene")


def _plan_path():
    return campaign.root() / ".gm" / "travel-plan.json"


def save_plan(to, acts):
    p = _plan_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"to": to, "activities": acts}), encoding="utf-8")


def stored_plan(to):
    p = _plan_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data.get("activities", {}) if data.get("to") == to else {}


def activities(acts):
    """{activity: [PC first names]}; PCs not named keep watch."""
    for who, what in acts.items():
        if what not in ACTIVITIES:
            raise ExploreError(f"{who}={what}: one of {', '.join(ACTIVITIES)}")
    out = {a: [] for a in ACTIVITIES}
    for d in campaign.scene_pcs():
        n = _first(d.front.get("name"))
        out[acts.get(n, "watch")].append(n)
    return out


def _passive(name):
    try:
        return creatures.get(name).passive("perception")
    except ToolError:
        return None


def watch_line(groups, pace):
    bits = []
    for n in groups["watch"]:
        p = _passive(n)
        if p is None:
            bits.append(n)
        elif pace == "fast":
            bits.append(f"{n} (passive {p}; fast pace −5 → {p - 5})")
        else:
            bits.append(f"{n} (passive {p})")
    tail = " · slow pace: the party may move stealthily" if pace == "slow" else ""
    return "Watch: " + (", ".join(bits) if bits else "nobody — only watchers notice an ambush") + tail


def _legs(r):
    """[(route or None, kind, terrain, forage)] of the trip's overland legs."""
    out = []
    if r.get("lost_from"):
        info = r["lost_from"]
        t = info["terrain"] if info["terrain"] != "?" else leg_terrain(None, None, r["site"])[0]
        return [(None, "trackless", t, leg_terrain(None, None, r["site"])[1])]
    if r.get("overland"):
        t, f = leg_terrain(r["frame"], None, r["site"])
        return [(None, "trackless", t, f)]
    for route in r.get("routes", []):
        t, f = leg_terrain(r["frame"], route, r["site"])
        out.append((route, route.kind, t, f))
    return out


def nav_need(r):
    """(DC, terrain, kind, route id) of the hardest lost-able leg, or None (roads only)."""
    worst = None
    for route, kind, terrain, _ in _legs(r):
        if not lostable(kind):
            continue
        dc = nav_dc(terrain)
        if worst is None or dc > worst[0]:
            worst = (dc, terrain, kind, route.id if route is not None else "cross-country")
    return worst


def forage_need(r):
    legs = _legs(r)
    kinds = [f for _, _, _, f in legs] or [leg_terrain(r.get("frame"), None, r["site"])[1]]
    worst = max(kinds, key=lambda f: FORAGE_DC.get(f, 15))
    return FORAGE_DC.get(worst, 15), worst


def forced_lines(hours, prefix="  "):
    if hours <= 8:
        return []
    out = [f"{prefix}Forced march: {hours} h > 8 h — a CON save for each PC at the end of each hour "
           f"from hour 9 (a failure is one level of exhaustion; the players roll)"]
    for h in range(9, hours + 1):
        dc = 10 + (h - 8)
        out.append(f"{prefix}  hour {h}: CON save DC {dc} (gm.py save <PC> con {dc} · fail → "
                   f"gm.py exhaust <PC> +1 \"forced march\")")
    return out


def plan_lines(r, acts, pace, hours):
    """`travel <to> --plan`: what the trip needs, nothing moved (dry run)."""
    detail = setting("travel-detail")
    lines = []
    if detail != "activities":
        lines.append("  travel-detail: summary — one packet, no navigation or foraging "
                     "(set travel-detail: activities for travel as play)")
        lines += order_lines(campaign.load_state())
        lines += forced_lines(hours)
        return lines
    groups = activities(acts)
    need = nav_need(r)
    nav = ", ".join(groups["navigate"]) or "nobody (assign one)"
    if need is None:
        road = ", ".join(rt.id for rt, k, _, _ in _legs(r) if rt is not None) or "the way"
        lines.append(f"  Navigate: on the road ({road}) — no check")
    elif setting("getting-lost") == "off":
        lines.append(f"  Navigate: getting-lost: off — no check ({need[3]}, {need[2]})")
    else:
        lines.append(f"  Navigate: {nav}, Survival DC {need[0]} ({need[1] or 'terrain not set'}, {need[2]})")
    if groups["forage"]:
        if setting("supplies") == "off":
            lines.append(f"  Forage: {', '.join(groups['forage'])} — supplies: off, nothing is counted "
                         f"(narrate what they find)")
        else:
            dc, kind = forage_need(r)
            lines.append(f"  Forage: {', '.join(groups['forage'])}, Survival DC {dc} ({kind})")
    for act in ("track", "map"):
        if groups[act]:
            lines.append(f"  {act.capitalize()}: {', '.join(groups[act])}")
    lines.append("  " + watch_line(groups, pace))
    lines += order_lines(campaign.load_state())
    lines += forced_lines(hours)
    ask = []
    if need is not None and setting("getting-lost") != "off":
        ask.append(f"--nav <{groups['navigate'][0] if groups['navigate'] else 'navigator'}'s Survival total>")
    if groups["forage"] and setting("supplies") != "off":
        ask.append("--forage " + ",".join(f"{n}=<total>" for n in groups["forage"]))
    lines.append(f"  Next: gm.py travel {r['loc']} " + " ".join(ask) if ask else
                 f"  Next: gm.py travel {r['loc']}")
    return lines


# ---------- the journey ----------

def journey(r, acts, nav, forage, pace, roller):
    """Resolve the activities for a trip (travel.py moves the party). -> {lines, lost:
    None | {...}}. Raises when a navigation total is needed and missing."""
    groups = activities(acts)
    out = {"lines": [], "lost": None, "groups": groups}
    need = nav_need(r)
    if need is not None and setting("getting-lost") != "off":
        if nav is None:
            who = groups["navigate"][0] if groups["navigate"] else "the navigator"
            raise ExploreError(f"travel: {need[3]} is off the road ({need[1] or 'terrain not set'}): "
                               f"--nav <{who}'s Survival total> (DC {need[0]})")
        who = groups["navigate"][0] if groups["navigate"] else "navigator"
        if nav >= need[0]:   # ties → the PC
            out["lines"].append(f"  Navigate: {who} {nav} vs DC {need[0]} — on course")
            journal.log_delta(f"navigate {who} {nav} vs DC {need[0]}: on course")
        else:
            out["lines"].append(f"  Navigate: {who} {nav} vs DC {need[0]} — off course (they don't know yet)")
            journal.log_delta(f"navigate {who} {nav} vs DC {need[0]}: off course", gm=True)
            out["lost"] = _wander(r, need, pace, roller)
    elif need is not None:
        out["lines"].append(f"  Navigate: getting-lost: off ({need[3]})")
    out["lines"] += _forage(r, groups, forage or {}, roller)
    return out


def _wander(r, need, pace, roller):
    """Where a failed navigation takes the party: the lost-able leg's start, then 1d6 h on
    a wrong bearing in the top frame. -> {minutes before, hours, point, frame, …}."""
    before, start = 0.0, None
    if r.get("lost_from"):
        info = r["lost_from"]
        top_slug, start = info["frame"], info["at"]
        top = geo.load(top_slug)
        _, goal = site_point(r["site"])
    else:
        frame = r["frame"]
        if r.get("overland"):
            top, start = site_point(r["src_site"])
        else:
            cur = r["src_node"]
            for route in r["routes"]:
                a, b = route.ends()
                nxt = b if a == cur else a
                if lostable(route.kind):
                    p = node_point(frame, cur)
                    if p is not None:
                        top, start = world_point(frame, p)
                    break
                before += geo.route_minutes(frame, route, pace, r["by"]) or 0
                cur = nxt
            if start is None:
                top, start = site_point(r["src_site"])
        _, goal = site_point(r["site"])
    meant = math.degrees(math.atan2(goal[1] - start[1], goal[0] - start[0]))
    face = roller.die(6)
    wrong = meant + WRONG[face]
    hours = roller.die(6)
    per_h = (3.0 if top.unit == "mi" else 3 * geo.FT_PER_MI) / geo.PACE.get(pace, 1.0) / 2   # trackless halves it
    dist = per_h * hours
    point = (start[0] + dist * math.cos(math.radians(wrong)), start[1] + dist * math.sin(math.radians(wrong)), 0.0)
    journal.log_delta(f"lost: d6 {face} → bearing {_bearing_word(wrong)} (meant {_bearing_word(meant)}), "
                      f"1d6 {hours} h", gm=True)
    return {"before": geo.round_minutes(before) if before else 0, "hours": hours, "frame": top.slug,
            "point": point, "bearing": _bearing_word(wrong), "meant": _bearing_word(meant),
            "terrain": need[1] or "?", "distance": dist, "unit": top.unit}


def _forage(r, groups, totals, roller):
    if not groups["forage"]:
        return []
    if setting("supplies") == "off":
        return [f"  Forage: {', '.join(groups['forage'])} — supplies: off, nothing is counted"]
    dc, kind = forage_need(r)
    out = []
    for n in groups["forage"]:
        total = totals.get(n)
        if total is None:
            out.append(f"  Forage: {n} — no total given (--forage {n}=<Survival total>, DC {dc}); nothing found")
            continue
        if total < dc:
            out.append(f"  Forage: {n} {total} vs DC {dc} ({kind}) — nothing found")
            journal.log_delta(f"forage {n} {total} vs DC {dc}: nothing")
            continue
        doc = _pc(n)
        wis = (int((doc.front.get("scores") or {}).get("wis", 10)) - 10) // 2
        die = roller.die(6)
        lb = max(1, die + wis)
        line, _ = inventory.item(n, "+", "rations", f"foraged, 1d6 {die} + WIS {wis:+d}", count=lb)
        bits = [f"  Forage: {n} {total} vs DC {dc} ({kind}) — {lb} lb of food (1d6 {die} + WIS {wis:+d}) "
                f"as {lb} day{'s' if lb != 1 else ''} of rations", "  " + line]
        import supplies
        fresh = md.load(doc.path)
        w = supplies._water(fresh)
        if w is not None and w[3] != "full":
            j, k, e, st = w
            prefix, entries, trailing = inventory._split_entries(fresh.body[j])
            entries[k] = re.sub(r"\((half|empty)\)", "(full)", e, flags=re.I)
            fresh.body[j] = (prefix + ", ".join(entries) + ("," if trailing and entries else "")).rstrip()
            fresh.save()
            journal.log_delta(f"forage {n}: waterskin {st}→full")
            bits.append(f"  [waterskin {n} {st}→full]")
        out += bits
    return out


# ---------- marching order ----------

def order_lines(state):
    o = state.front.get("marching-order")
    if not isinstance(o, dict) or not any(o.get(k) for k in ROWS):
        return []
    return ["  " + order_text(o)]


def order_text(o):
    bits = []
    for k in ROWS:
        v = o.get(k) or []
        v = v if isinstance(v, list) else [v]
        if v:
            bits.append(f"{k} {', '.join(str(x) for x in v)}")
    return "Marching order: " + " · ".join(bits)


def ambush_line(state):
    o = state.front.get("marching-order")
    if not isinstance(o, dict):
        return None
    front = ", ".join(str(x) for x in (o.get("front") or []))
    back = ", ".join(str(x) for x in (o.get("back") or []))
    if not front and not back:
        return None
    return f"  Ambush: from ahead it meets {front or '(nobody set)'} first; from behind, {back or '(nobody set)'}"


def order(specs):
    state = campaign.load_state()
    if not specs:
        o = state.front.get("marching-order")
        return [f"[{order_text(o)}]" if isinstance(o, dict) else "[marching order: not set]"]
    if specs == ["clear"]:
        state.del_front("marching-order")
        state.save()
        journal.log_delta("order cleared")
        return ["[order cleared]"]
    out = {}
    for s in specs:
        row, sep, names = s.partition("=")
        row = row.strip().lower()
        if not sep or row not in ROWS:
            raise ExploreError(f"order wants front=… middle=… back=…, got {s!r}")
        out[row] = [_name(n) for n in names.split(",") if n.strip()]
    o = {k: out[k] for k in ROWS if k in out}
    state.set_front("marching-order", o)
    state.save()
    body = "order " + order_text(o)[len("Marching order: "):]
    journal.log_delta(body)
    return [f"[{body}]"]


def _name(n):
    try:
        return _first(_pc(n).front.get("name"))
    except ExploreError:
        try:
            c = creatures.get(n)
        except ToolError:
            raise ExploreError(f"order: no one named {n!r}") from None
        except campaign.CampaignError:
            raise ExploreError(f"order: no one named {n!r}") from None
        return c.name.split()[0]


def cmd_order(ctx):
    lines = order(ctx.args.rows)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("order", parents=[g], help="order front=Kael middle=Kira back=Grusk | order | order clear")
    p.add_argument("rows", nargs="*")
    p.set_defaults(func=cmd_order)
