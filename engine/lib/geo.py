"""World geometry: frames, placement, bearings, distances, route times, route finding
(docs/design/04 → Location files L25-64, area/world files, Deriving travel time, terrain
keywords; 06 → `scene enter` Exits/Nearby, `travel`; 02 → Spatial model, Telling players
distances; plan.md Phase 4 item 1).

Directions and distances are never authored, only derived here. The only compass
words in the tools live in `bearing()`.

- `load(slug)` → `Frame` of a location file: `tier`, `unit` (ft | mi), `origin_text`,
  `places` (Places rows), `routes` (Routes rows), `parent`, and for sites `layouts`
  (one `Layout` per `### <area>` block: bounds + terrain rows).
- `to_parent(frame, point)` / `from_parent(frame, point)`: `parent = at + local` with
  ft↔mi only when the units differ.
- `bearing`, `edge_distance`, `distance_text`, `band`.
- `route_minutes(frame, route, pace, by)`, `round_minutes`, `fmt_minutes`.
- `find_route(src_location, dst)` → `Plan` (routes, minutes, frame), chaining through the
  site → area → world frames; raises `NoRoute`.
- `nearby(frame, place_id)`, `exits(site_slug, area)`.
"""
import heapq
import math
import re

from . import campaign, md
from .errors import ToolError

FT_PER_MI = 5280
MI_FROM_FT = 1000         # distance_text switches to miles from here (06 → scene enter)
FT_PER_MIN = 300          # normal pace, ft frames (PHB: 300 ft/min)
MI_PER_MIN = 3 / 60       # normal pace, mi frames (3 mi/h)
PACE = {"normal": 1.0, "fast": 0.75, "slow": 1.5}
KIND_FACTOR = {
    "road": 1, "street": 1, "door": 1, "path": 1, "lane": 1, "trapdoor": 1, "stairs": 1,
    "gate": 1, "ladder": 1, "trail": 1.5, "trackless": 2, "marsh": 2, "scree": 2,
}
ROADLIKE = ("road", "street")
BANDS = ((5, "adjacent"), (30, "close"), (60, "nearby"), (120, "far"))
_BOUNDS = re.compile(r"x\s*(-?\d+(?:\.\d+)?)\s*(?:–|-|\.\.)\s*(-?\d+(?:\.\d+)?).*?"
                     r"y\s*(-?\d+(?:\.\d+)?)\s*(?:–|-|\.\.)\s*(-?\d+(?:\.\d+)?)"
                     r"(?:.*?z\s*(-?\d+(?:\.\d+)?)\s*(?:–|-|\.\.)\s*(-?\d+(?:\.\d+)?))?")
_TIME = re.compile(r"^\s*(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m(?:in)?)?\b", re.I)


class GeoError(ToolError):
    pass


class NoRoute(GeoError):
    pass


def _point(text):
    text = (text or "").strip()
    if not text or text in ("—", "-", "?"):
        return None
    try:
        return md.parse_point(text)
    except ValueError:
        return None


def _secret(*texts):
    return any(re.search(r"\bsecret\b", t or "", re.I) for t in texts)


class Place:
    """A Places row (area/world frames) or a Layout row (site frames)."""

    def __init__(self, row):
        self.id = row.get("id", "").strip()
        self.glyph = row.get("glyph", "").strip()
        self.feature = row.get("feature", "").strip() or self.id
        self.a = _point(row.get("from"))
        self.b = _point(row.get("to")) or self.a
        self.at = _point(row.get("at")) or self.a          # blank at = from (04)
        self.effect = row.get("effect", "").strip()
        ref = row.get("ref", "").strip()
        self.ref = "" if ref in ("—", "-") else ref
        self.source = row.get("source", "").strip()
        self.secret = _secret(self.effect)

    @property
    def placed(self):
        return self.a is not None

    def box(self):
        lo = tuple(min(p, q) for p, q in zip(self.a, self.b))
        hi = tuple(max(p, q) for p, q in zip(self.a, self.b))
        return lo, hi

    def center(self):
        lo, hi = self.box()
        return tuple((p + q) / 2 for p, q in zip(lo, hi))


class Route:
    def __init__(self, row):
        self.id = row.get("id", "").strip()
        self.frm = row.get("from", "").strip()
        self.to = row.get("to", "").strip()
        self.via = [tuple(float(n) for n in m) + ((0.0,) if len(m) == 2 else ())
                    for m in (re.findall(r"-?\d+(?:\.\d+)?", p) for p in
                              re.findall(r"\(([^)]*)\)", row.get("via", "")))]
        self.kind = row.get("kind", "").strip().lower()
        self.access = row.get("access", "").strip()
        self.time = row.get("time", "").strip()
        self.notes = row.get("notes", "").strip()
        self.secret = _secret(self.access)

    def ends(self):
        return _base(self.frm), _base(self.to)


def _base(ref):
    """`inn.door` → `inn`."""
    return ref.split(".", 1)[0].strip()


class Layout:
    """One `### <area>` block of a site's ## Layout."""

    def __init__(self, area, bounds_line, rows):
        self.area = area
        self.bounds_line = bounds_line
        self.rows = rows
        self.terrain = [Place(r) for r in rows]
        m = _BOUNDS.search(bounds_line or "")
        if m:
            x0, x1, y0, y1 = (float(g) for g in m.groups()[:4])
            z0 = float(m.group(5)) if m.group(5) is not None else 0.0
            z1 = float(m.group(6)) if m.group(6) is not None else 0.0
            self.bounds = ((x0, y0, z0), (x1, y1, z1))
        else:
            self.bounds = None

    def center(self):
        if not self.bounds:
            return None
        return tuple((p + q) / 2 for p, q in zip(*self.bounds))

    def row(self, row_id):
        return next((t for t in self.terrain if t.id == row_id), None)

    def exit_to(self, target):
        """The Layout row whose effect says `exit → <target>` (first word match)."""
        for t in self.terrain:
            m = re.match(r"\s*exit\s*(?:→|->)\s*([\w-]+)", t.effect, re.I)
            if m and m.group(1).lower() == target.lower():
                return t
        return None


class Frame:
    def __init__(self, slug, doc):
        self.slug = slug
        self.doc = doc
        self.tier = str(doc.front.get("tier") or "site").lower()
        self.type = str(doc.front.get("type") or "")
        self.name = str(doc.front.get("name") or slug)
        self.unit = "mi" if self.tier == "world" else "ft"
        self.parent = str(doc.front.get("parent") or "").strip() or None
        t = doc.table("Places")
        self.places = [Place(r) for r in t.rows] if t else []
        t = doc.table("Routes")
        self.routes = [Route(r) for r in t.rows] if t else []
        self.origin_text = ""
        span = doc.section("Frame")
        if span:
            for i in range(span[0] + 1, span[1]):
                if doc.body[i].strip().startswith("origin"):
                    self.origin_text = doc.body[i].strip()
                    break
        self.layouts = self._layouts()
        if not self.origin_text and self.layouts:
            first = next(iter(self.layouts.values()))
            m = re.search(r"origin\s*\(0,0,0\)\s*=\s*([^·]+)", first.bounds_line or "")
            self.origin_text = f"origin (0,0,0) = {m.group(1).strip()}" if m else ""

    def _layouts(self):
        doc = self.doc
        span = doc.section("Layout")
        if span is None:
            return {}
        out = {}
        heads = [(i, lvl, text) for i, lvl, text in doc.headings() if span[0] < i < span[1] and lvl == 3]
        for n, (i, _, text) in enumerate(heads):
            end = heads[n + 1][0] if n + 1 < len(heads) else span[1]
            bounds_line, rows = "", []
            j = i + 1
            while j < end:
                line = doc.body[j]
                if line.strip().lower().startswith("bounds:"):
                    bounds_line = line.strip()
                if line.lstrip().startswith("|") and j + 1 < end and re.match(r"^\s*\|?\s*:?-", doc.body[j + 1]):
                    rows = md.Table(doc, j).rows
                    break
                j += 1
            area = text.strip().split()[0]
            out[area] = Layout(area, bounds_line, rows)
        return out

    def place(self, pid):
        return next((p for p in self.places if p.id == pid), None)

    def place_for_ref(self, slug):
        return next((p for p in self.places if p.ref == slug), None)

    def layout_row(self, row_id):
        for lay in self.layouts.values():
            r = lay.row(row_id)
            if r is not None:
                return lay, r
        return None, None


_frames = {}


def load(slug):
    """The Frame of `locations/<slug>.md` (cached per campaign root and file mtime)."""
    p = campaign.path("locations", slug)
    if not p.exists():
        raise GeoError(f"no location file locations/{slug}.md")
    key = (str(p), p.stat().st_mtime_ns)
    if key not in _frames:
        _frames[key] = Frame(slug, md.load(p))
    return _frames[key]


def parent_of(frame):
    """(parent Frame, this frame's Place row in it) or (None, None)."""
    if not frame.parent:
        return None, None
    try:
        par = load(frame.parent)
    except GeoError:
        return None, None
    return par, par.place_for_ref(frame.slug)


# ---------- placement ----------

def _conv(child_unit, parent_unit):
    if child_unit == parent_unit:
        return 1.0
    return 1 / FT_PER_MI if child_unit == "ft" else FT_PER_MI


def to_parent(frame, point):
    """A point in `frame` → its parent's frame (`at + local`)."""
    par, row = parent_of(frame)
    if par is None or row is None or row.at is None:
        raise GeoError(f"{frame.slug} is not placed in a parent frame")
    k = _conv(frame.unit, par.unit)
    return tuple(a + p * k for a, p in zip(row.at, point))


def from_parent(frame, point):
    """A point in the parent's frame → `frame` (`(p - at)` converted)."""
    par, row = parent_of(frame)
    if par is None or row is None or row.at is None:
        raise GeoError(f"{frame.slug} is not placed in a parent frame")
    k = _conv(frame.unit, par.unit)
    return tuple((p - a) / k for a, p in zip(row.at, point))


# ---------- bearings and distances ----------

def bearing(a, b):
    """8-point compass word from point a to point b (north = +y)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return "here"
    words = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")
    return words[round(math.degrees(math.atan2(dy, dx)) / 45) % 8]


def _gap(lo1, hi1, lo2, hi2):
    return max(0.0, lo2 - hi1, lo1 - hi2)


def edge_distance(pa, pb):
    """Footprint-to-footprint distance (x/y, Euclidean) between two placed Places, in
    their frame's unit."""
    (alo, ahi), (blo, bhi) = pa.box(), pb.box()
    gx = _gap(alo[0], ahi[0], blo[0], bhi[0])
    gy = _gap(alo[1], ahi[1], blo[1], bhi[1])
    return math.hypot(gx, gy)


def to_ft(value, unit):
    return value * FT_PER_MI if unit == "mi" else value


def distance_text(value, unit="ft"):
    """`adjacent` (≤ 5 ft), `135 ft` under 1,000 ft (to 5 ft), else `0.8 mi` (to 0.1)."""
    ft = to_ft(value, unit)
    if ft <= 5:
        return "adjacent"
    if ft < MI_FROM_FT:
        return f"{int(5 * math.ceil(ft / 5 - 1e-9))} ft"
    return f"{ft / FT_PER_MI:.1f} mi"


def band(ft):
    """Player-facing band (02 → Telling players distances)."""
    for limit, word in BANDS:
        if ft <= limit:
            return word
    return "distant"


# ---------- route time ----------

def parse_time(text):
    """`45m — switchbacks` / `1h30m` / `2d` → minutes, or None."""
    if not text or not text.strip() or text.strip() in ("—", "-"):
        return None
    m = _TIME.match(text)
    if not m or not any(m.groups()):
        return None
    d, h, mi = (int(g) if g else 0 for g in m.groups())
    return d * 1440 + h * 60 + mi


def round_minutes(x):
    """Round up to a whole minute (minimum 1); over an hour, up to 5 minutes."""
    if x is None:
        return None
    n = max(1, math.ceil(x - 1e-9))
    if n > 60:
        n = 5 * math.ceil(n / 5)
    return n


def fmt_minutes(n):
    if n is None:
        return "?"
    d, rem = divmod(n, 1440)
    h, m = divmod(rem, 60)
    out = []
    if d:
        out.append(f"{d}d")
    if h:
        out.append(f"{h}h")
    if m or not out:
        out.append(f"{m} min" if not (d or h) else f"{m}m")
    return " ".join(out)


def _geom(frame, ref):
    """('point', p) | ('box', lo, hi) | None for a route end in `frame`."""
    base, _, exit_id = ref.partition(".")
    base = base.strip()
    pl = frame.place(base)
    if pl is not None and pl.placed:
        if exit_id and pl.ref:
            try:
                child = load(pl.ref)
            except GeoError:
                child = None
            if child is not None:
                _, row = child.layout_row(exit_id.strip())
                if row is not None and row.a is not None:
                    k = _conv(child.unit, frame.unit)
                    return ("point", tuple(a + p * k for a, p in zip(pl.at, row.a)))
        lo, hi = pl.box()
        return ("box", lo, hi)
    # site frames: a Layout exit row or a laid-out sub-area
    lay, row = frame.layout_row(base)
    if row is not None and row.a is not None:
        return ("point", row.a)
    lay = frame.layouts.get(base)
    if lay is not None and lay.bounds:
        return ("box", lay.bounds[0], lay.bounds[1])
    return None


def _clamp(g, p):
    if g[0] == "point":
        return g[1]
    lo, hi = g[1], g[2]
    return tuple(min(max(v, a), b) for v, a, b in zip(p, lo, hi))


def _closest_pair(ga, gb):
    if ga[0] == "point":
        return ga[1], _clamp(gb, ga[1])
    if gb[0] == "point":
        return _clamp(ga, gb[1]), gb[1]
    pa, pb = [], []
    for k in range(3):
        alo, ahi, blo, bhi = ga[1][k], ga[2][k], gb[1][k], gb[2][k]
        if ahi < blo:
            pa.append(ahi), pb.append(blo)
        elif bhi < alo:
            pa.append(alo), pb.append(bhi)
        else:
            mid = (max(alo, blo) + min(ahi, bhi)) / 2
            pa.append(mid), pb.append(mid)
    return tuple(pa), tuple(pb)


def route_length(frame, route):
    """Path length (frame units) from → via → to, or None without coordinates."""
    ga, gb = _geom(frame, route.frm), _geom(frame, route.to)
    if ga is None or gb is None:
        return None
    if route.via:
        pts = [_clamp(ga, route.via[0])] + list(route.via) + [_clamp(gb, route.via[-1])]
    else:
        pts = list(_closest_pair(ga, gb))
    return sum(math.dist(p, q) for p, q in zip(pts, pts[1:]))


def conveyance_factor(kind, by="foot"):
    by = (by or "foot").lower()
    if by in ("cart", "wagon"):
        return 1 if kind in ROADLIKE else 2
    if by == "horse":
        return 0.5 if kind in ROADLIKE else 1
    if by == "boat":
        return 0.5 if kind == "river" else 1
    return 1


def route_minutes(frame, route, pace="normal", by="foot"):
    """Unrounded minutes for one route, or None when it can't be derived. A `time`
    override wins (pace and conveyance still apply)."""
    over = parse_time(route.time)
    factor = PACE.get(pace, 1.0) * conveyance_factor(route.kind, by)
    if over is not None:
        return over * factor
    length = route_length(frame, route)
    if length is None:
        return None
    per_min = MI_PER_MIN if frame.unit == "mi" else FT_PER_MIN
    return length / per_min * factor * KIND_FACTOR.get(route.kind, 1)


class Plan:
    def __init__(self, frame, routes, minutes):
        self.frame = frame
        self.routes = routes
        self.minutes = minutes   # unrounded; None if any leg is unknown

    @property
    def rounded(self):
        return round_minutes(self.minutes)


def _dijkstra(frame, src, dst, pace="normal", by="foot", include_secret=False):
    graph = {}
    for r in frame.routes:
        if r.secret and not include_secret:
            continue
        a, b = r.ends()
        graph.setdefault(a, []).append((b, r))
        graph.setdefault(b, []).append((a, r))
    best = {src: 0.0}
    unknown = {src: False}
    prev = {}
    heap = [(0.0, 0, src)]
    n = 0
    while heap:
        cost, _, cur = heapq.heappop(heap)
        if cur == dst:
            routes = []
            while cur != src:
                cur, r = prev[cur]
                routes.append(r)
            return Plan(frame, routes[::-1], None if unknown[dst] else cost)
        if cost > best.get(cur, math.inf):
            continue
        for nxt, r in graph.get(cur, []):
            m = route_minutes(frame, r, pace, by)
            c = cost + (m if m is not None else 0.0)
            if c < best.get(nxt, math.inf):
                best[nxt], prev[nxt] = c, (cur, r)
                unknown[nxt] = unknown[cur] or m is None
                n += 1
                heapq.heappush(heap, (c, n, nxt))
    raise NoRoute(f"no route from {src} to {dst} in {frame.slug}")


def chain(slug):
    """[(Frame, node id in that frame)] from the location's parent upward."""
    out = []
    try:
        frame = load(slug)
    except GeoError:
        return out
    seen = set()
    while frame.parent and frame.slug not in seen:
        seen.add(frame.slug)
        par, row = parent_of(frame)
        if par is None or row is None:
            break
        out.append((par, row.id))
        frame = par
    return out


def find_route(src_location, dst, pace="normal", by="foot"):
    """Routes from a location (`site` or `site/area`) to `dst` (a location slug or a
    place id in one of the enclosing frames), in the lowest frame holding both."""
    site = src_location.split("/")[0]
    up = chain(site)
    for frame, node in up:
        target = frame.place(dst) or frame.place_for_ref(dst)
        if target is not None:
            if target.id == node:
                return Plan(frame, [], 0.0)
            return _dijkstra(frame, node, target.id, pace, by)
    down = {f.slug: n for f, n in chain(dst)}
    for frame, node in up:
        if frame.slug in down:
            return _dijkstra(frame, node, down[frame.slug], pace, by)
    raise NoRoute(f"no shared frame between {src_location} and {dst}")


# ---------- scene helpers ----------

def nearby(frame, place_id):
    """[(place, bearing, distance_text, minutes_rounded, plan)] for the other non-secret
    places of `frame`, nearest first; unplaced rows last (bearing/distance None)."""
    me = frame.place(place_id)
    out = []
    for p in frame.places:
        if p.id == place_id or p.secret:
            continue
        try:
            plan = _dijkstra(frame, place_id, p.id)
            mins = plan.rounded
        except NoRoute:
            plan, mins = None, None
        if me is not None and me.placed and p.placed:
            d = edge_distance(me, p)
            out.append((p, bearing(me.center(), p.center()), distance_text(d, frame.unit), mins, plan, d))
        else:
            out.append((p, None, None, mins, plan, math.inf))
    out.sort(key=lambda t: t[5])
    return [t[:5] for t in out]


def exits(site_slug, area=None):
    """[{label, to, access, bearing, adjacent, kind}] ways out of a site (or one of its
    areas): the site's own Routes touching the area (or its ## Areas when it has no
    Routes), plus every route in the parent frame that touches the site. Secret routes
    are left out."""
    site = load(site_slug)
    out = []
    lay = site.layouts.get(area) if area else None
    here = lay.center() if lay else None
    if site.routes:
        for r in site.routes:
            if r.secret:
                continue
            a, b = r.ends()
            if area and area not in (a, b):
                continue
            other = b if (not area or a == area) else a
            brg = None
            if lay is not None and here is not None:
                row = lay.exit_to(other) or lay.row(r.id)
                if row is not None and row.a is not None:
                    brg = bearing(here, row.center())
            out.append({"label": r.id, "to": other, "access": r.access, "bearing": brg,
                        "adjacent": False, "kind": r.kind, "route": r})
    else:
        for other in _area_slugs(site.doc):
            if other != area:
                out.append({"label": other, "to": other, "access": "", "bearing": None,
                            "adjacent": False, "kind": "", "route": None})
    par, row = parent_of(site)
    if par is not None and row is not None:
        for r in par.routes:
            if r.secret:
                continue
            a, b = r.ends()
            if row.id not in (a, b):
                continue
            mine, theirs = (r.frm, r.to) if a == row.id else (r.to, r.frm)
            other = par.place(_base(theirs))
            label = r.id
            if "." in mine:
                _, ex = site.layout_row(mine.split(".", 1)[1])
                if ex is not None:
                    label = ex.feature
            brg, adjacent = None, False
            if other is not None and other.placed and row.placed:
                brg = bearing(row.center(), other.center())
                adjacent = to_ft(edge_distance(row, other), par.unit) <= 5
            out.append({"label": label, "to": other.feature if other else _base(theirs),
                        "access": r.access, "bearing": brg, "adjacent": adjacent,
                        "kind": r.kind, "route": r})
    return out


def _area_slugs(doc):
    span = doc.section("Areas")
    if span is None:
        return []
    out = []
    for i in range(span[0] + 1, span[1]):
        m = re.match(r"^\s*-\s+\*\*([\w-]+)\*\*", doc.body[i])
        if m:
            out.append(m.group(1))
    return out


def area_slugs(site_slug):
    return _area_slugs(load(site_slug).doc)
