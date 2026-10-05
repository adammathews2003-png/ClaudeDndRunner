"""`gm.py world init | show | add | lead | place | reveal` — the world map (docs/design/06 →
`gm.py world`; 04 → The world file; 02 → The open world; plan.md Phase 7 item 6).
Suggestions (`place` without `--at`) and `import` are Phase 8.

    world init <area-slug> [--size 0.5]                 # world.md with the area at (0,0,0)
    world show [--player-view]
    world add "the market town" --near thornbury --within 3d [--beyond 1d] [--dir E]
              [--on "a navigable river"] --source player:kael --note "…"   # → Known, not placed
    world lead thornbury --heading E --as "the east road" [--to "the coast"] --source scenario
    world place market-town --at 38,-12 [--size 1] [--force]               # → Places
    world reveal <id>                                                    # strip `secret`

Constraints (04): `within <dist|time> of <id>`, `beyond <dist|time> from <id>`,
`<compass> of <id>`, `on <feature>` (kept, unchecked until the feature is placed),
`near (x,y) ±<dist>`. Times convert at 24 mi/day × 0.8 (road sinuosity), hours at
3 mi/h × 0.8; compass = within ±45° of the bearing. `place` refuses a spot that breaks
a constraint or overlaps a placed footprint (`--force` exists for /overrule only), copies
the constraints into the row as `placed: …`, and turns a frontier lead whose "said to
lead to" names the place into a world route.
"""
import math
import re

from lib import campaign, geo, journal, md
from lib.errors import ToolError

COMPASS_DEG = {"E": 0, "NE": 45, "N": 90, "NW": 135, "W": 180, "SW": 225, "S": 270, "SE": 315}
PLACES_COLS = ["id", "glyph", "feature", "at", "from", "to", "effect", "ref", "source"]
ROUTE_COLS = ["id", "from", "to", "via", "kind", "access", "time", "notes"]
WORLD = """---
name: The World
tier: world
type: realm
parent:
tags: []
---

# The World

## Description
What's generally known. Everything past the starting area is unexplored, which means
unknown, not empty.

## Frame
origin (0,0,0) = {name}'s origin (the starting area) · +x east · +y north · +z up · mi

## Places
| id | glyph | feature | at | from | to | effect | ref | source |
|----|-------|---------|----|------|----|--------|-----|--------|
| {slug} | {glyph} | {name} | (0,0,0) | ({lo},{lo},0) | ({hi},{hi},0) | starting area | {slug} | scenario |

## Known, not placed
| id | feature | constraints | source | notes |
|----|---------|-------------|--------|-------|

## Frontier
| id | from | heading | known as | said to lead to | source | notes |
|----|------|---------|----------|-----------------|--------|-------|

## Routes
(world-tier routes between placed places; same format as an area's Routes, in mi)

## Notes / current state
"""


class WorldError(ToolError):
    pass


def _path():
    return campaign.root() / "locations" / "world.md"


def _doc():
    p = _path()
    if not p.exists():
        raise WorldError("no locations/world.md (gm.py world init <starting-area>)")
    return md.load(p)


def dist_mi(text):
    """'3d' → 57.6 · '2h' → 4.8 · '10 mi' → 10 · '500 ft' → 0.095."""
    t = text.strip().lower()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(d|days?|h|hours?|mi|miles?|ft|feet)", t)
    if not m:
        raise WorldError(f"can't read distance {text!r} (3d, 2h, 10 mi, 500 ft)")
    n, u = float(m.group(1)), m.group(2)[0] if not m.group(2).startswith("mi") else "mi"
    if u == "d":
        return n * 24 * 0.8
    if u == "h":
        return n * 3 * 0.8
    if u == "f":
        return n / geo.FT_PER_MI
    return n


def parse_constraint(c):
    c = c.strip()
    m = re.fullmatch(r"within\s+(.+?)\s+of\s+([\w-]+)", c, re.I)
    if m:
        return ("within", dist_mi(m.group(1)), m.group(2))
    m = re.fullmatch(r"beyond\s+(.+?)\s+from\s+([\w-]+)", c, re.I)
    if m:
        return ("beyond", dist_mi(m.group(1)), m.group(2))
    m = re.fullmatch(r"(N|NE|E|SE|S|SW|W|NW)\s+of\s+([\w-]+)", c, re.I)
    if m:
        return ("dir", m.group(1).upper(), m.group(2))
    m = re.fullmatch(r"on\s+(.+)", c, re.I)
    if m:
        return ("on", m.group(1).strip(), None)
    m = re.fullmatch(r"near\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)\s*±\s*(.+)", c, re.I)
    if m:
        return ("near", (float(m.group(1)), float(m.group(2))), dist_mi(m.group(3)))
    return None


def check(constraints, point, size, frame):
    """[problem] for a candidate centre `point` (x, y) in mi."""
    problems = []
    half = size / 2
    box = ((point[0] - half, point[1] - half), (point[0] + half, point[1] + half))
    for raw in constraints:
        c = parse_constraint(raw)
        if c is None:
            continue
        kind, a, ref = c
        if kind == "near":
            if math.dist(point, a) > ref:
                problems.append(f"{raw}: {math.dist(point, a):.1f} mi away")
            continue
        if kind == "on":
            continue
        p = frame.place(ref)
        if p is None or not p.placed:
            problems.append(f"{raw}: {ref} isn't placed")
            continue
        (lo, hi) = p.box()
        gx = max(0, lo[0] - box[1][0], box[0][0] - hi[0])
        gy = max(0, lo[1] - box[1][1], box[0][1] - hi[1])
        d = math.hypot(gx, gy)
        if kind == "within" and d > a:
            problems.append(f"{raw}: {d:.1f} mi straight line (> {a:.1f})")
        elif kind == "beyond" and d < a:
            problems.append(f"{raw}: {d:.1f} mi straight line (< {a:.1f})")
        elif kind == "dir":
            c0 = p.center()
            ang = math.degrees(math.atan2(point[1] - c0[1], point[0] - c0[0])) % 360
            off = min(abs(ang - COMPASS_DEG[a]), 360 - abs(ang - COMPASS_DEG[a]))
            if off > 45:
                problems.append(f"{raw}: the spot is {geo.bearing(c0, point)} of {ref}")
    for p in frame.places:
        if not p.placed:
            continue
        (lo, hi) = p.box()
        if box[0][0] < hi[0] and lo[0] < box[1][0] and box[0][1] < hi[1] and lo[1] < box[1][1]:
            problems.append(f"overlaps {p.id}")
    return problems


def _table(doc, heading, cols):
    t = doc.table(heading)
    if t is not None:
        return t
    span = doc.section(heading)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("-" * (len(c) + 2) for c in cols) + "|"]
    if span is None:
        doc.append_line(heading, lines[0])
        doc.append_line(heading, lines[1])
    else:
        # replace a prose placeholder like "(none yet …)" with the table
        body = [i for i in range(span[0] + 1, span[1]) if doc.body[i].strip()]
        if body and doc.body[body[0]].strip().startswith("("):
            doc.body[body[0]:body[0] + 1] = lines
        else:
            doc.body[span[0] + 1:span[0] + 1] = lines
    return doc.table(heading)


# ---------- commands ----------

def init(area, size=0.5):
    if _path().exists():
        raise WorldError("world init: locations/world.md already exists")
    ap = campaign.path("locations", area)
    name = md.load(ap).front.get("name") if ap.exists() else area.replace("-", " ").title()
    h = size / 2
    md.new(_path(), WORLD.format(name=name, slug=area, glyph=str(name)[:1].upper(), lo=f"{-h:g}", hi=f"{h:g}")).save()
    if ap.exists():
        adoc = md.load(ap)
        if not adoc.front.get("parent"):
            adoc.set_front("parent", "world")
            adoc.save()
    journal.log_delta(f"world init {area}")
    return f"[world init: locations/world.md · {area} at (0,0,0)]"


def show(player_view=False):
    doc = _doc()
    frame = geo.load("world")
    out = ["[WORLD] placed: " + (" · ".join(
        f"{p.feature} {('(%g,%g)' % p.center()[:2]) if p.placed else '(?)'}"
        for p in frame.places if not (player_view and p.secret)) or "—")]
    t = doc.table("Known")
    for r in (t.rows if t else []):
        out.append(f"  known: {r.get('feature')} — {r.get('constraints') or 'no constraints'}"
                   + (f" · {r.get('notes')}" if r.get("notes") else "") + f" [{r.get('source')}]")
    t = doc.table("Frontier")
    for r in (t.rows if t else []):
        out.append(f"  frontier: {r.get('known as')} ({r.get('heading')} from {r.get('from')}) → "
                   f"{r.get('said to lead to') or '(unknown)'} [{r.get('source')}]")
    return out


def add(name, near=None, within=None, beyond=None, direction=None, on=None, source="generated", note="",
        rid=None):
    doc = _doc()
    rid = rid or campaign.slugify(name)
    cons = []
    if within:
        cons.append(f"within {within} of {near}")
    if beyond:
        cons.append(f"beyond {beyond} from {near}")
    if direction:
        cons.append(f"{direction.upper()} of {near}")
    if on:
        cons.append(f"on {on}")
    if (within or beyond or direction) and not near:
        raise WorldError("world add: --within/--beyond/--dir need --near <id>")
    for c in cons:
        if parse_constraint(c) is None:
            raise WorldError(f"world add: can't read constraint {c!r}")
    frame = geo.load("world")
    if frame.place(rid):
        raise WorldError(f"world add: {rid} is already placed")
    t = _table(doc, "Known, not placed", ["id", "feature", "constraints", "source", "notes"])
    if t.find("id", rid) >= 0:
        raise WorldError(f"world add: {rid} is already known (edit its row, or place it)")
    t.append({"id": rid, "feature": name, "constraints": "; ".join(cons) or "—", "source": source,
              "notes": note or ""})
    doc.save()
    journal.log_delta(f"world add {name} ({'; '.join(cons) or 'no constraints'}) [{source}]")
    return f"[world add: {rid} → Known, not placed · {'; '.join(cons) or 'no constraints'}]"


def lead(frm, heading, known_as, to="", source="generated", note=""):
    doc = _doc()
    frame = geo.load("world")
    if frame.place(frm) is None:
        raise WorldError(f"world lead: {frm} is not placed")
    t = _table(doc, "Frontier", ["id", "from", "heading", "known as", "said to lead to", "source", "notes"])
    rid = campaign.slugify(known_as)
    if t.find("id", rid) >= 0:
        raise WorldError(f"world lead: {rid} already exists")
    row = {"id": rid, "from": frm, "heading": heading.upper(), "known as": known_as,
           "said to lead to": to or "(unknown)", "source": source}
    if "notes" in t.keys:
        row["notes"] = note
    t.append(row)
    doc.save()
    journal.log_delta(f"world lead {known_as} ({heading.upper()} from {frm}) [{source}]")
    return f"[world lead: {rid} · {heading.upper()} from {frm}]"


def place(rid, at, size=1.0, force=False):
    doc = _doc()
    frame = geo.load("world")
    t = doc.table("Known")
    i = t.find("id", rid) if t else -1
    if i < 0:
        raise WorldError(f"world place: {rid} is not in Known, not placed (world add it first)")
    if not at:
        raise WorldError("world place: give --at x,y (suggestions are Phase 8)")
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", at)]
    if len(nums) < 2:
        raise WorldError(f"world place: --at wants x,y, got {at!r}")
    point = (nums[0], nums[1])
    row = t.rows[i]
    cons = [c.strip() for c in row.get("constraints", "").split(";") if c.strip() and c.strip() not in ("—", "-")]
    problems = check(cons, point, size, frame)
    if problems and not force:
        raise WorldError("world place: refused — " + "; ".join(problems))
    h = size / 2
    effect = "; ".join(x for x in (row.get("notes", ""), f"placed: {', '.join(cons)}" if cons else "") if x)
    places = _table(doc, "Places", PLACES_COLS)
    places.append({"id": rid, "glyph": row.get("feature", rid)[:1].upper(), "feature": row.get("feature", rid),
                   "at": f"({point[0]:g},{point[1]:g},0)", "from": f"({point[0] - h:g},{point[1] - h:g},0)",
                   "to": f"({point[0] + h:g},{point[1] + h:g},0)", "effect": effect, "ref": "—",
                   "source": row.get("source", "generated")})
    t = doc.table("Known")
    t.remove(t.find("id", rid))
    out = [f"[world place: {rid} at ({point[0]:g},{point[1]:g}) · {size:g} mi"
           + (f" · FORCED past: {'; '.join(problems)}" if problems else "") + "]"]
    fr = doc.table("Frontier")
    feature = row.get("feature", "").lower()
    for j in range(len(fr.rows) - 1, -1, -1) if fr else []:
        f = fr.rows[j]
        to = f.get("said to lead to", "").lower()
        if to and (to == rid or to == feature or campaign.slugify(to) == rid):
            routes = _table(doc, "Routes", ROUTE_COLS)
            routes.append({"id": f["id"], "from": f["from"], "to": rid, "via": "", "kind": "road",
                           "access": "obvious", "time": "", "notes": f.get("known as", "")})
            fr = doc.table("Frontier")
            fr.remove(j)
            out.append(f"[world route: {f['id']} {f['from']} → {rid} (was a frontier lead)]")
    doc.save()
    journal.log_delta(f"world place {rid} at ({point[0]:g},{point[1]:g})" + (" FORCED" if problems else ""))
    return out


def reveal(rid):
    hits = []
    for p in sorted((campaign.root() / "locations").glob("*.md")):
        doc = md.load(p)
        changed = False
        for heading, col in (("Places", "effect"), ("Routes", "access"), ("Layout", "effect")):
            for t in _tables(doc, heading):
                k = t.find("id", rid)
                if k >= 0 and re.search(r"\bsecret\b", t.rows[k].get(col, ""), re.I):
                    v = re.sub(r"\s*[;,]?\s*\bsecret\b\s*[;,]?", "; ", t.rows[k][col], flags=re.I)
                    v = re.sub(r"(;\s*)+", "; ", v).strip("; ").strip() or "—"
                    t.set(k, col, v)
                    changed = True
                    hits.append(f"{p.stem}:{rid}")
        if changed:
            doc.save()
    if not hits:
        raise WorldError(f"world reveal: no secret row `{rid}`")
    journal.log_delta(f"world reveal {rid} ({', '.join(hits)})")
    return f"[world reveal: {', '.join(hits)}]"


def _tables(doc, heading):
    """Every table in a section, including ### sub-blocks (Layout)."""
    span = doc.section(heading)
    if span is None:
        return []
    out = []
    i = span[0] + 1
    while i < span[1]:
        if doc.body[i].lstrip().startswith("|") and i + 1 < span[1] and re.match(r"^\s*\|?\s*:?-", doc.body[i + 1]):
            t = md.Table(doc, i)
            out.append(t)
            i += 2 + len(t.rows)
            continue
        i += 1
    return out


def cmd_world(ctx):
    a = ctx.args
    if a.action == "init":
        lines = [init(a.target, a.size or 0.5)]
    elif a.action == "show":
        lines = show(a.player_view)
    elif a.action == "add":
        lines = [add(a.target, a.near, a.within, a.beyond, a.dir, a.on, a.source or "generated", a.note or "")]
    elif a.action == "lead":
        if not a.heading or not a.as_:
            raise WorldError("world lead <from> --heading E --as \"the east road\"")
        lines = [lead(a.target, a.heading, a.as_, a.to or "", a.source or "generated", a.note or "")]
    elif a.action == "place":
        lines = place(a.target, a.at, a.size or 1.0, a.force)
    elif a.action == "reveal":
        lines = [reveal(a.target)]
    else:
        raise WorldError("world import: not built yet (Phase 8)")
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("world", parents=[g], help="world init|show|add|lead|place|reveal")
    p.add_argument("action", choices=["init", "show", "add", "lead", "place", "reveal", "import"])
    p.add_argument("target", nargs="?", default="")
    p.add_argument("--near")
    p.add_argument("--within")
    p.add_argument("--beyond")
    p.add_argument("--dir")
    p.add_argument("--on")
    p.add_argument("--source")
    p.add_argument("--note")
    p.add_argument("--heading")
    p.add_argument("--as", dest="as_")
    p.add_argument("--to")
    p.add_argument("--at")
    p.add_argument("--size", type=float)
    p.add_argument("--force", action="store_true", help="/overrule only")
    p.add_argument("--player-view", action="store_true")
    p.set_defaults(func=cmd_world)
