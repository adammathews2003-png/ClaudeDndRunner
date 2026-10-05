"""Spatial helper for combat: distances, movement, areas of effect, ASCII map.

Implements the model in rules/combat-basics.md (Positions & distance, Areas of effect).
Reads the `## Combat` block of a campaign's state/current.md when --state is given.

  python tools/space.py dist  Kael Veskar            --state poc/state/current.md
  python tools/space.py dist  10,5,0 20,30,10
  python tools/space.py move  Kael --to Veskar --state ...        (pathfinds; stops adjacent)
  python tools/space.py move  Kael --to @landing --state ...      (@id = a terrain feature)
  python tools/space.py move  Kael --path 15,10,0 5,25,0 5,30,10 --state ...   (explicit route)
  python tools/space.py cone  Kael --toward @door --length 15 --state ...
  python tools/space.py sphere 22.5,12.5,0 --radius 20 --state ...
  python tools/space.py emanation Kael --radius 15 --state ...
  python tools/space.py line  Kael --toward 40,5,0 --length 60 --state ...
  python tools/space.py map   --state ... [--from Kael]
"""
import argparse
import math
import re
import sys

CELL = 5
SIZE_CELLS = {"T": 1, "S": 1, "M": 1, "L": 2, "H": 3, "G": 4}
EPS = 1e-9


# ---------- state parsing ----------

def parse_point(text):
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]
    if len(nums) == 2:
        nums.append(0.0)
    if len(nums) != 3:
        raise ValueError(f"not a point: {text!r}")
    return tuple(nums)


def table_rows(lines, start):
    """Rows of the first markdown table at/after `start`, as dicts keyed by header."""
    i = start
    while i < len(lines) and not lines[i].lstrip().startswith("|"):
        if lines[i].startswith("#"):
            return []
        i += 1
    if i >= len(lines):
        return []
    header = [h.strip().lower() for h in lines[i].strip().strip("|").split("|")]
    rows = []
    for line in lines[i + 2:]:
        if not line.lstrip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(dict(zip(header, cells)))
    return rows


class Combatant:
    def __init__(self, row):
        self.name = re.sub(r"\s*\(PC\)", "", row["name"]).strip()
        self.glyph = (row.get("glyph") or self.name[0]).strip()[:1].upper()
        self.side = row.get("side", "").strip().lower()
        self.pos = parse_point(row["pos"])
        size = (row.get("size") or "M").strip()
        group = re.match(r"group\s*r?(\d+)", size, re.I)
        self.group_r = int(group.group(1)) if group else 0
        self.cells_per_side = 1 if group else SIZE_CELLS.get(size[:1].upper(), 1)
        reach = re.search(r"reach\s*(\d+)", row.get("notes", ""), re.I)
        self.reach = int(reach.group(1)) if reach else 5
        self.climbs = bool(re.search(r"climb speed", row.get("notes", ""), re.I))
        self.flies = bool(re.search(r"fly(ing)? speed|flying", row.get("notes", ""), re.I))
        self.down = row.get("hp", "").startswith("0/")

    def cells(self):
        x0, y0, z0 = self.pos
        if self.group_r:  # a swarm/group fills a cube of radius r around pos
            r = self.group_r
            rng = range(-r, r + 1, CELL)
            return [(x0 + dx, y0 + dy, z0) for dx in rng for dy in rng]
        n = self.cells_per_side
        return [(x0 + i * CELL, y0 + j * CELL, z0 + k * CELL)
                for i in range(n) for j in range(n) for k in range(n)]


class Terrain:
    def __init__(self, row):
        self.id = row.get("id", "")
        self.glyph = (row.get("glyph") or self.id[:1]).strip()[:1].lower() or "?"
        self.a = parse_point(row["from"])
        self.b = parse_point(row.get("to") or row["from"])
        self.effect = row.get("effect", "")
        low = self.effect.lower()
        self.difficult = "difficult" in low
        self.walkway = bool(re.search(r"stairs|ramp", low))
        # a wall blocks movement and sight; a door/gate/exit row is a gap in it
        # unless closed or locked (the gap is a wall until it's opened)
        self.door = bool(re.search(r"\bdoor\b|\bgate\b|exit →|exit ->", low))
        shut = bool(re.search(r"\bclosed\b|\blocked\b|\bbarred\b", low))
        self.wall = bool(re.search(r"\bwall\b", low)) or (self.door and shut)
        # passable but harmful (damage dice, or the word hazard): pathfinding avoids it
        self.hazard = bool(re.search(r"\d+d\d+|\bhazard\b", low)) and not self.wall

    def cells(self):
        lo = [min(p, q) for p, q in zip(self.a, self.b)]
        hi = [max(p, q) for p, q in zip(self.a, self.b)]
        return [(x, y, z)
                for x in frange(lo[0], hi[0]) for y in frange(lo[1], hi[1])
                for z in frange(lo[2], hi[2])]


def frange(lo, hi):
    v = lo
    while v <= hi + EPS:
        yield v
        v += CELL


class State:
    def __init__(self, path):
        self.combatants, self.terrain, self.bounds, self.active = [], [], None, None
        if not path:
            return
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        for i, line in enumerate(lines):
            low = line.lower()
            if low.startswith("## combat"):
                m = re.search(r"up:\s*(.+)$", line)
                self.active = m.group(1).strip() if m else None
            elif "bounds:" in low:
                m = re.search(r"x\s*(-?\d+)\s*(?:–|-|\.\.)\s*(-?\d+).*?y\s*(-?\d+)\s*(?:–|-|\.\.)\s*(-?\d+)", line)
                if m:
                    self.bounds = tuple(int(g) for g in m.groups())
            elif low.startswith("### terrain"):
                self.terrain = [Terrain(r) for r in table_rows(lines, i + 1)]
            elif low.startswith("### combatants"):
                self.combatants = [Combatant(r) for r in table_rows(lines, i + 1)]

    def find(self, name):
        name = name.lower()
        hits = [c for c in self.combatants if c.name.lower().startswith(name)]
        if len(hits) != 1:
            sys.exit(f"'{name}': {'no' if not hits else 'ambiguous'} combatant match")
        return hits[0]

    def feature(self, name):
        name = name.lstrip("@").lower()
        hits = [t for t in self.terrain if t.id.lower().startswith(name)]
        if len(hits) != 1:
            sys.exit(f"'@{name}': {'no' if not hits else 'ambiguous'} terrain feature match")
        return hits[0]

    def point_or_name(self, text):
        """A point, a combatant name, or @feature (its first cell). Returns (point, combatant)."""
        if re.match(r"^\s*-?\d", text):
            return parse_point(text), None
        if text.startswith("@"):
            return self.feature(text).a, None
        c = self.find(text)
        return c.pos, c

    def difficult_cells(self):
        return {c for t in self.terrain if t.difficult for c in t.cells()}

    def walkway_cells(self):
        return {c for t in self.terrain if t.walkway for c in t.cells()}

    def hazard_cells(self):
        return {c: t for t in self.terrain if t.hazard for c in t.cells()}

    def wall_cells(self):
        walls = {c for t in self.terrain if t.wall for c in t.cells()}
        gaps = {c for t in self.terrain if t.door and not t.wall for c in t.cells()}
        return walls - gaps

    def in_bounds(self, p):
        if not self.bounds:
            return True
        x0, x1, y0, y1 = self.bounds
        return x0 - EPS <= p[0] <= x1 + EPS and y0 - EPS <= p[1] <= y1 + EPS

    def z_range(self):
        zs = [p[2] for c in self.combatants for p in c.cells()]
        zs += [p[2] for t in self.terrain for p in t.cells()]
        return (min(zs), max(zs)) if zs else (0, 0)

    def visible(self, src, dst, walls=None):
        """Line of sight: no wall cell strictly between src and dst (cell-stepped)."""
        walls = self.wall_cells() if walls is None else walls
        if not walls:
            return True
        return not any(c in walls for c in steps(src, dst)[:-1])


# ---------- geometry ----------

def cheb(a, b):
    return max(abs(p - q) for p, q in zip(a, b))


def dist_between(a_cells, b_cells):
    return min(cheb(a, b) for a in a_cells for b in b_cells)


def steps(a, b):
    """Cell-by-cell path a→b, moving every axis that still differs (diagonals first)."""
    cur, out = list(a), []
    while tuple(cur) != tuple(b):
        for k in range(3):
            if abs(cur[k] - b[k]) > EPS:
                cur[k] += CELL if b[k] > cur[k] else -CELL
        out.append(tuple(cur))
    return out


def unit(v):
    n = math.sqrt(sum(c * c for c in v))
    if n < EPS:
        sys.exit("aim point is the caster's own cell")
    return tuple(c / n for c in v)


def apex_for(center, u):
    """Point where the aim ray leaves the caster's cell: face midpoint or corner."""
    k = (CELL / 2) / max(abs(c) for c in u)
    return tuple(c + k * d for c, d in zip(center, u))


def cone_cells(center, toward, length):
    u = unit(tuple(t - c for t, c in zip(toward, center)))
    apex = apex_for(center, u)
    out = []
    for c in grid_around(center, length):
        v = tuple(p - q for p, q in zip(c, apex))
        f = sum(p * q for p, q in zip(v, u))
        s = math.sqrt(max(0.0, sum(p * p for p in v) - f * f))
        if 0 < f <= length + EPS and s <= f / 2 + EPS:
            out.append(c)
    return out


def line_cells(center, toward, length):
    u = unit(tuple(t - c for t, c in zip(toward, center)))
    apex = apex_for(center, u)
    out = []
    for c in grid_around(center, length):
        v = tuple(p - q for p, q in zip(c, apex))
        f = sum(p * q for p, q in zip(v, u))
        s = math.sqrt(max(0.0, sum(p * p for p in v) - f * f))
        if 0 < f <= length + EPS and s <= CELL / 2 + EPS:
            out.append(c)
    return out


def sphere_cells(origin, r, height=None):
    if any(abs((o / CELL) % 1 - 0.5) > EPS for o in origin[:2]):
        print("note: sphere origins should be grid intersections (x.5 coordinates)")
    out = []
    for c in grid_around(origin, r + CELL):
        dx, dy, dz = (abs(p - q) for p, q in zip(c, origin))
        z_ok = (0 <= c[2] - origin[2] < height) if height else dz < r
        if dx < r and dy < r and z_ok:
            out.append(c)
    return out


def grid_around(center, reach):
    n = int(math.ceil(reach / CELL)) + 1
    base = tuple(round(c / CELL) * CELL for c in center)
    rng = range(-n, n + 1)
    return [(base[0] + i * CELL, base[1] + j * CELL, base[2] + k * CELL)
            for i in rng for j in rng for k in rng]


# ---------- commands ----------

def fmt(p):
    return "(" + ",".join(f"{v:g}" for v in p) + ")"


def report_hits(state, cells, exclude=None, plane_z=None):
    cellset = set(cells)
    hit = [c for c in state.combatants
           if c is not exclude and any(x in cellset for x in c.cells())]
    if plane_z is not None:
        flat = sum(1 for c in cells if abs(c[2] - plane_z) < EPS)
        print(f"{flat} cells at z={plane_z:g} ({len(cells)} in 3D)")
    else:
        print(f"{len(cells)} cells")
    if state.combatants:
        print("in area: " + (", ".join(f"{c.name} {fmt(c.pos)}" for c in hit) or "nobody"))
    return cellset


def cmd_dist(st, a, b):
    pa, ca = st.point_or_name(a)
    pb, cb = st.point_or_name(b)
    d = dist_between(ca.cells() if ca else [pa], cb.cells() if cb else [pb])
    dz = pb[2] - pa[2]
    print(f"{d:g} ft" + (f"  (height diff {dz:+g} ft)" if dz else ""))


def step_cost(st, mover, cur, nxt, climbs, difficult, walkway, warnings=None):
    """Movement cost of one cell step, or None if the step is impossible."""
    dz = nxt[2] - cur[2]
    on_walkway = cur in walkway or nxt in walkway
    climbing = dz > EPS and not (on_walkway or climbs or mover.flies)
    if dz < -EPS and not (on_walkway or mover.flies):
        if warnings is None:   # pathfinding never jumps or falls on its own
            return None
        warnings.append(f"drops {-dz:g} ft at {fmt(nxt)} without stairs: jump/fall?")
    return CELL * (2 if (nxt in difficult or climbing) else 1)


def find_path(st, mover, goals, climbs):
    """Dijkstra over cells from the mover to the cheapest reachable goal cell."""
    import heapq
    difficult, walkway, walls = st.difficult_cells(), st.walkway_cells(), st.wall_cells()
    hazards = st.hazard_cells()     # steep penalty, not a block: the only way may be through
    blocked = set(walls)
    for c in st.combatants:         # can't pass through enemies; allies are passable
        if c is not mover and not c.down and c.side and c.side != mover.side:
            blocked |= set(c.cells())
    occupied = {p for c in st.combatants if c is not mover for p in c.cells()}
    goals = {g for g in goals if g not in blocked and g not in occupied}
    if not goals:
        sys.exit("no free cell to end on at that target")
    zlo, zhi = st.z_range()
    start = mover.pos
    best, prev, heap = {start: 0}, {}, [(0, start)]
    while heap:
        cost, cur = heapq.heappop(heap)
        if cur in goals:
            path = [cur]
            while path[-1] != start:
                path.append(prev[path[-1]])
            return path[::-1][1:], cost
        if cost > best.get(cur, float("inf")):
            continue
        for dx in (-CELL, 0, CELL):
            for dy in (-CELL, 0, CELL):
                for dz in (-CELL, 0, CELL):
                    nxt = (cur[0] + dx, cur[1] + dy, cur[2] + dz)
                    if nxt == cur or nxt in blocked or not st.in_bounds(nxt):
                        continue
                    if not (zlo - EPS <= nxt[2] <= zhi + EPS):
                        continue
                    c = step_cost(st, mover, cur, nxt, climbs, difficult, walkway)
                    if c is None:
                        continue
                    if nxt in hazards:
                        c += 1000
                    if cost + c < best.get(nxt, float("inf")):
                        best[nxt], prev[nxt] = cost + c, cur
                        heapq.heappush(heap, (cost + c, nxt))
    sys.exit("no path (walls, enemies or height in the way)")


def goal_cells(st, mover, target, stop):
    """Cells that count as 'arrived' for a --to target."""
    if re.match(r"^\s*-?\d", target):
        return [parse_point(target)]
    if target.startswith("@"):
        t = st.feature(target)
        if not (t.wall or t.difficult):   # passable feature: end on it
            return t.cells()
        around = {(x + dx, y + dy, z)
                  for (x, y, z) in t.cells() for dx in (-CELL, 0, CELL) for dy in (-CELL, 0, CELL)}
        return [c for c in around if c not in set(t.cells())]
    c = st.find(target)
    reach = stop or 5
    return [g for g in grid_around(c.pos, reach + max(c.cells_per_side, 1) * CELL)
            if 0 < dist_between([g], c.cells()) <= reach]


def cmd_move(st, who, path, to, stop, speed, climbs):
    mover = st.find(who)
    speed = speed or 30
    climbs = climbs or mover.climbs
    difficult, walkway, walls = st.difficult_cells(), st.walkway_cells(), st.wall_cells()
    enemies = [c for c in st.combatants
               if c is not mover and not c.down and c.side and c.side != mover.side]
    if to:
        cells, _ = find_path(st, mover, goal_cells(st, mover, to, stop), climbs)
        waypoints = [c for i, c in enumerate(cells)   # keep only direction changes
                     if i == len(cells) - 1 or i == 0 or
                     tuple(a - b for a, b in zip(cells[i + 1], c)) !=
                     tuple(a - b for a, b in zip(c, cells[i - 1]))]
        print("path: " + " -> ".join(fmt(p) for p in waypoints))
    else:
        cells = []
        cur = mover.pos
        for wp in [parse_point(p) for p in path]:
            cells += steps(cur, wp)
            cur = wp
    cur, spent, provoked, warnings = mover.pos, 0, [], []
    hazards = st.hazard_cells()
    for nxt in cells:
        if nxt in walls:
            sys.exit(f"blocked: {fmt(nxt)} is a wall")
        if nxt in hazards:
            warnings.append(f"enters {hazards[nxt].id} at {fmt(nxt)}: {hazards[nxt].effect}")
        spent += step_cost(st, mover, cur, nxt, climbs, difficult, walkway, warnings)
        for e in enemies:
            was = dist_between([cur], e.cells()) <= e.reach
            now = dist_between([nxt], e.cells()) <= e.reach
            if was and not now and e.name not in provoked:
                provoked.append(e.name)
        cur = nxt
    ok = "OK" if spent <= speed else f"OVER by {spent - speed:g} (dash doubles speed)"
    print(f"{mover.name}: {fmt(mover.pos)} -> {fmt(cur)}  cost {spent:g} / {speed:g} ft  {ok}")
    print("opportunity attacks from: " + (", ".join(provoked) or "none"))
    for w in warnings:
        print("warning: " + w)


def behind_walls(st, origin, cells):
    """Drop cells the origin can't see (walls block areas of effect) and the walls themselves."""
    walls = st.wall_cells()
    if not walls:
        return cells, 0
    base = tuple(round(c / CELL) * CELL for c in origin)
    kept = [c for c in cells if c not in walls and st.visible(base, c, walls)]
    return kept, len(cells) - len(kept)


def cmd_area(st, kind, args):
    if kind == "sphere":
        origin, _ = st.point_or_name(args.origin)
        cells = sphere_cells(origin, args.radius, args.height)
        cells, cut = behind_walls(st, origin, cells)
        report_hits(st, cells, plane_z=origin[2])
    elif kind == "emanation":
        src = st.find(args.source)
        cells = sorted({c for base in src.cells()
                        for c in grid_around(base, args.radius)
                        if dist_between([c], src.cells()) <= args.radius})
        cells, cut = behind_walls(st, src.pos, cells)
        report_hits(st, cells, exclude=src, plane_z=src.pos[2])
    else:
        center, caster = st.point_or_name(args.source)
        toward, _ = st.point_or_name(args.toward)
        fn = cone_cells if kind == "cone" else line_cells
        cells = fn(center, toward, args.length)
        cells, cut = behind_walls(st, center, cells)
        report_hits(st, cells, exclude=caster, plane_z=center[2])
    if cut:
        print(f"({cut} cells behind walls left out)")
    if args.show:
        render(st, highlight=set(cells))


def render(st, origin_name=None, highlight=None):
    highlight = highlight or set()
    pts = [p for c in st.combatants for p in c.cells()]
    pts += [p for t in st.terrain for p in t.cells()] + list(highlight)
    if st.bounds:
        x0, x1, y0, y1 = st.bounds
    elif pts:
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    else:
        sys.exit("nothing to draw")
    grid = {}
    # walls draw first so doors and gaps show through; higher terrain draws over lower
    for t in sorted(st.terrain, key=lambda t: 0 if t.wall else 1):
        for c in sorted(t.cells(), key=lambda p: p[2]):
            grid[(c[0], c[1])] = t.glyph
    for (x, y, _z) in highlight:
        grid[(x, y)] = "*"
    for c in st.combatants:
        for (x, y, _z) in c.cells():
            grid[(x, y)] = c.glyph.lower() if c.down else c.glyph
    xs = list(frange(x0, x1))
    # x labels every 20 ft (4 cells = 8 chars, room for 3-digit labels)
    print("     " + "".join(f"{int(x):<8}" for x in xs if int(x - x0) % 20 == 0))
    for y in reversed(list(frange(y0, y1))):
        row = "".join(f"{grid.get((x, y), '.'):<2}" for x in xs)
        print(f"{int(y):>4} {row}")
    print("     (north = +y up the page; 1 cell = 5 ft; lowercase combatant = down)")
    ref = st.find(origin_name) if origin_name else None
    for c in st.combatants:
        extra = f"  z={c.pos[2]:g}" if c.pos[2] else ""
        d = f"  {dist_between(ref.cells(), c.cells()):g} ft from {ref.name}" if ref and c is not ref else ""
        glyph = c.glyph.lower() if c.down else c.glyph
        print(f"  {glyph} {c.name:<14} {fmt(c.pos)}{extra}{d}")
    for t in st.terrain:
        z = {p[2] for p in t.cells()}
        zs = f"  z={min(z):g}" + (f"-{max(z):g}" if len(z) > 1 else "") if max(z) else ""
        print(f"  {t.glyph} {t.id:<14} {t.effect}{zs}")
    if highlight:
        print("  * area of effect")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", help="campaign state/current.md")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("dist"); p.add_argument("a"); p.add_argument("b")
    p = sub.add_parser("move"); p.add_argument("who")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--to", help="creature (stops adjacent), @feature, or point; pathfinds")
    g.add_argument("--path", nargs="+", help="explicit waypoints x,y,z ...")
    p.add_argument("--stop", type=float, help="with --to <creature>: stop at this reach (ft)")
    p.add_argument("--speed", type=float); p.add_argument("--climbs", action="store_true")
    for kind in ("cone", "line"):
        p = sub.add_parser(kind); p.add_argument("source")
        p.add_argument("--toward", required=True)
        p.add_argument("--length", type=float, required=True)
        p.add_argument("--show", action="store_true")
    p = sub.add_parser("sphere"); p.add_argument("origin")
    p.add_argument("--radius", type=float, required=True)
    p.add_argument("--height", type=float, help="cylinder height (omit for sphere)")
    p.add_argument("--show", action="store_true")
    p = sub.add_parser("emanation"); p.add_argument("source")
    p.add_argument("--radius", type=float, required=True)
    p.add_argument("--show", action="store_true")
    p = sub.add_parser("map"); p.add_argument("--from", dest="origin")

    # allow --state anywhere on the line
    argv = sys.argv[1:]
    if "--state" in argv:
        i = argv.index("--state")
        argv = argv[i:i + 2] + argv[:i] + argv[i + 2:]
    args = ap.parse_args(argv)
    st = State(args.state)

    if args.cmd == "dist":
        cmd_dist(st, args.a, args.b)
    elif args.cmd == "move":
        cmd_move(st, args.who, args.path, args.to, args.stop, args.speed, args.climbs)
    elif args.cmd == "map":
        render(st, args.origin)
    else:
        cmd_area(st, args.cmd, args)


if __name__ == "__main__":
    main()
