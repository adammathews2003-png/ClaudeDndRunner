"""Consistency sweep (docs/design/06 → `gm.py lint`; 05 #5, #6; plan.md Phase 7 item 4).

`run(files=None, fix_safe=False)` -> [Finding]. `files` = campaign-relative paths for the
touched-files check (layer 2: only file-local checks for those files); None = the full
sweep (layer 3). Errors are broken references and unparseable files; everything
unfinished-on-purpose is a warning and never blocks.
"""
import math
import re
from pathlib import Path

from . import campaign, geo, md

TIERS = ("site", "area", "world")
PARENT_TIERS = {"site": ("area", "world"), "area": ("area", "world"), "world": ()}
REQUIRED = {
    "pcs": ("name", "race", "class", "level", "hp", "ac", "scores"),
    "npcs": ("name", "location", "status"),
    "locations": ("name", "tier"),
}
_COMPASS = {"north": "N", "south": "S", "east": "E", "west": "W", "northeast": "NE",
            "northwest": "NW", "southeast": "SE", "southwest": "SW"}
_SPATIAL = re.compile(r"^(within|beyond)\s+\S+.*\b(of|from)\s+[\w-]+$|^(N|NE|E|SE|S|SW|W|NW)\s+of\s+[\w-]+$|"
                      r"^on\s+.+$|^near\s*\(", re.I)


class Finding:
    def __init__(self, level, path, msg):
        self.level, self.path, self.msg = level, path, msg

    def line(self):
        return f"{self.level}: {self.path}: {self.msg}"

    def __repr__(self):
        return f"<{self.line()}>"


class _Out(list):
    def err(self, path, msg):
        self.append(Finding("error", path, msg))

    def warn(self, path, msg):
        self.append(Finding("warning", path, msg))


def _rel(p):
    try:
        return Path(p).resolve().relative_to(campaign.root()).as_posix()
    except ValueError:
        return str(p)


# ---------- file-local ----------

def check_parse(out, path):
    rel = _rel(path)
    try:
        raw = md.read_text(path)[0]
    except (OSError, UnicodeDecodeError) as e:
        out.err(rel, f"unreadable: {e}")
        return None
    lines = raw.splitlines()
    if lines and lines[0].strip() == "---":
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if close is None:
            out.err(rel, "frontmatter has no closing ---")
            return None
        for i in range(1, close):
            line = lines[i]
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if md._parse_front_line(line) is None:
                out.err(rel, f"frontmatter line {i + 1} outside the parsing contract: {line.strip()[:60]}")
    return md.load(path)


def check_required(out, doc, kind):
    for k in REQUIRED.get(kind, ()):
        if doc.front.get(k) in (None, "", {}, []):
            out.warn(_rel(doc.path), f"missing `{k}`")


def _areas(site):
    try:
        return geo.area_slugs(site)
    except geo.GeoError:
        return []


def check_location_value(out, doc, fix_safe=False):
    rel = _rel(doc.path)
    loc = str(doc.front.get("location") or "").strip()
    if not loc:
        return
    if loc == "@lost":   # off course in the wilds (Phase 14; state/current.md `lost:`)
        return
    if loc.startswith("@"):
        rid = loc[1:]
        if not any(r.id == rid for f in _all_frames() for r in f.routes):
            out.warn(rel, f"location @{rid}: no route with that id (in transit on a missing route)")
        return
    site, _, area = loc.partition("/")
    if not campaign.path("locations", site).exists():
        out.err(rel, f"location {loc!r}: no locations/{site}.md")
        return
    if area and area not in _areas(site):
        if fix_safe:
            sdoc = md.load(campaign.path("locations", site))
            sdoc.append_line("Areas", f"- **{area}** — <!-- added by lint, check me -->")
            sdoc.save()
            out.warn(rel, f"location {loc!r}: added `{area}` to {site}'s ## Areas (check it)")
        else:
            out.warn(rel, f"location {loc!r}: `{area}` is not in {site}'s ## Areas")


def check_state(out, doc):
    rel = _rel(doc.path)
    root = campaign.root()
    for m in campaign.onstage(doc):
        line = doc.body[m.line]
        ref = re.search(r"\((\S+?\.md)\)", line)
        if ref and not (root / ref.group(1)).exists():
            out.err(rel, f"On stage {m.name}: {ref.group(1)} is missing")
    span = doc.section("Watch for")
    for i in range(span[0] + 1, span[1]) if span else []:
        line = doc.body[i]
        m = re.search(r"(scenarios/[\w-]+\.md)(?:\s+beat\s+(\d+))?", line)
        if not m:
            continue
        p = root / m.group(1)
        if not p.exists():
            out.err(rel, f"Watch for: {m.group(1)} is missing")
        elif m.group(2):
            n = _beat_count(md.load(p))
            if int(m.group(2)) > n:
                out.warn(rel, f"Watch for: beat {m.group(2)} — {m.group(1)} has {n} beats")
    loc = str(doc.front.get("party-location") or "")
    if loc == "@lost":
        if not doc.front.get("lost"):
            out.err(rel, "party-location @lost without a `lost:` line (where are they?)")
    elif loc:
        site, _, area = loc.partition("/")
        if not campaign.path("locations", site).exists():
            out.err(rel, f"party-location {loc!r}: no locations/{site}.md")
    check_combat(out, doc)


def _beat_count(doc):
    span = doc.section("Beats")
    if span is None:
        return 0
    return sum(1 for i in range(span[0] + 1, span[1]) if re.match(r"^\s*-\s*(WHEN|CLOCK)\b", doc.body[i]))


def check_combat(out, doc):
    t = doc.table("Combatants")
    if t is None:
        return
    rel = _rel(doc.path)
    bounds = None
    for line in doc.body:
        if line.lower().lstrip().startswith("bounds:"):
            m = re.search(r"x\s*(-?\d+)\s*(?:–|-|\.\.)\s*(-?\d+).*?y\s*(-?\d+)\s*(?:–|-|\.\.)\s*(-?\d+)", line)
            if m:
                bounds = tuple(int(g) for g in m.groups())
            break
    cells = {}
    names = []
    for r in t.rows:
        name = re.sub(r"\s*\(PC\)", "", r.get("name", ""), flags=re.I).strip()
        names.append(name.lower())
        pos = r.get("pos", "").strip()
        if pos and pos != "?":
            try:
                p = md.parse_point(pos)
            except ValueError:
                out.warn(rel, f"combat: {name} has an unreadable pos {pos!r}")
                p = None
            if p and bounds and not (bounds[0] <= p[0] <= bounds[1] and bounds[2] <= p[1] <= bounds[3]):
                out.warn(rel, f"combat: {name} at {pos} is out of bounds")
            if p and "group" not in r.get("size", "").lower():
                if p in cells:
                    out.warn(rel, f"combat: {name} and {cells[p]} share the cell {pos}")
                cells[p] = name
        hp = re.match(r"^\s*(\d+)\s*/\s*(\d+)", r.get("hp", ""))
        if hp and int(hp.group(1)) > int(hp.group(2)):
            out.warn(rel, f"combat: {name} HP {r.get('hp')} is above max")
    for _, lvl, text in doc.headings():
        m = re.search(r"up:\s*(.+)$", text)
        if m and text.lower().startswith("combat"):
            up = m.group(1).strip().lower()
            if not any(n == up or n.startswith(up) for n in names):
                out.warn(rel, f"combat: up: {m.group(1).strip()} is not a combatant")


# ---------- geography ----------

_frame_cache = {}


def _all_frames():
    key = str(campaign.root())
    if key not in _frame_cache:
        frames = []
        for p in sorted((campaign.root() / "locations").glob("*.md")):
            if p.name.startswith("_"):
                continue
            try:
                frames.append(geo.load(p.stem))
            except Exception:  # noqa: BLE001 — parse errors are reported separately
                continue
        _frame_cache[key] = frames
    return _frame_cache[key]


def check_location_file(out, doc):
    rel = _rel(doc.path)
    slug = Path(doc.path).stem
    tier = str(doc.front.get("tier") or "").lower()
    if tier not in TIERS:
        out.err(rel, f"tier {tier or '(none)'!r} is not site | area | world")
        return
    try:
        frame = geo.load(slug)
    except geo.GeoError as e:
        out.err(rel, str(e))
        return
    parent = frame.parent
    if parent:
        if not campaign.path("locations", parent).exists():
            out.err(rel, f"parent {parent!r}: no locations/{parent}.md")
        else:
            pt = str(md.load(campaign.path("locations", parent)).front.get("tier") or "").lower()
            if pt not in PARENT_TIERS[tier]:
                out.err(rel, f"parent {parent} is tier {pt or '?'}; a {tier} sits in {' or '.join(PARENT_TIERS[tier])}")
            par, row = geo.parent_of(frame)
            if par is not None and row is None:
                out.warn(rel, f"not placed: no ## Places row with ref {slug} in {parent}")
            elif row is not None and not row.placed:
                out.warn(rel, f"unplaced: {parent}'s row `{row.id}` has no coordinates")
            elif row is not None and tier == "site" and par.unit == "ft":
                lo, hi = row.box()
                for lay in frame.layouts.values():
                    if lay.bounds:
                        (x0, y0, _), (x1, y1, _) = lay.bounds
                        if x1 - x0 > hi[0] - lo[0] + 5 or y1 - y0 > hi[1] - lo[1] + 5:
                            out.warn(rel, f"Layout {lay.area} ({x1 - x0:g}×{y1 - y0:g} ft) doesn't fit the "
                                          f"footprint in {parent} ({hi[0] - lo[0]:g}×{hi[1] - lo[1]:g} ft)")
    elif tier != "world":
        out.warn(rel, "no parent: not on the world map")
    for p in frame.places:
        if p.ref and not campaign.path("locations", p.ref).exists():
            out.err(rel, f"Places `{p.id}`: ref {p.ref} has no file")
        if not p.placed:
            out.warn(rel, f"Places `{p.id}` has no coordinates")
    placed = [p for p in frame.places if p.placed and p.ref]
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            (alo, ahi), (blo, bhi) = a.box(), b.box()
            stacked = not (alo[2] < bhi[2] and blo[2] < ahi[2]) and (ahi[2] != alo[2] or bhi[2] != blo[2])
            if alo[0] < bhi[0] and blo[0] < ahi[0] and alo[1] < bhi[1] and blo[1] < ahi[1] and not stacked:
                out.warn(rel, f"Places `{a.id}` and `{b.id}` overlap")
    areas = set(geo._area_slugs(doc)) if tier == "site" else set()
    for r in frame.routes:
        for end in (r.frm, r.to):
            base, _, ex = end.partition(".")
            base = base.strip()
            if tier == "site":
                if base not in areas and frame.layout_row(base)[1] is None:
                    out.warn(rel, f"route `{r.id}`: end {end!r} is not an area or Layout row")
                continue
            pl = frame.place(base)
            if pl is None:
                out.err(rel, f"route `{r.id}`: end {end!r} is not a Places id")
            elif ex and pl.ref:
                try:
                    child = geo.load(pl.ref)
                except geo.GeoError:
                    continue
                if child.layout_row(ex.strip())[1] is None:
                    if child.layouts:
                        out.err(rel, f"route `{r.id}`: {pl.ref}'s Layout has no row `{ex}`")
                    else:
                        out.warn(rel, f"route `{r.id}`: exit `{ex}` waits for {pl.ref}'s first Layout")
        over = geo.parse_time(r.time)
        if over is not None and tier != "site":
            length = geo.route_length(frame, r)
            if length:
                per = geo.MI_PER_MIN if frame.unit == "mi" else geo.FT_PER_MIN
                derived = length / per * geo.KIND_FACTOR.get(r.kind, 1)
                if derived >= 1 and (over > 2 * derived or over < derived / 2):
                    out.warn(rel, f"route `{r.id}`: time {r.time!r} vs derived {derived:.0f} min (>2× off)")
    check_compass_prose(out, doc, frame)
    check_traps(out, doc)
    check_terrain(out, doc, frame)


def check_traps(out, doc):
    """`TRAP` lines under `## Hidden` (Phase 14; 04 → Scene state added) parse: an id, an
    `effect:` the tool can resolve, a known `state:`, a `disarm:` with a DC."""
    import hazard
    rel = _rel(doc.path)
    span = doc.section("Hidden")
    for i in range(span[0] + 1, span[1]) if span else []:
        line = doc.body[i]
        if not re.search(r"\bTRAP\b", line):
            continue
        t = hazard.parse_trap(line)
        if t is None:
            out.err(rel, f"Hidden: a TRAP line doesn't parse (want `- DC N: TRAP <id> (area) · trigger: … · "
                         f"disarm: DC N … · effect: … · state: armed`): {line.strip()[:60]}")
            continue
        if t.state not in hazard.STATES:
            out.err(rel, f"TRAP {t.id}: state {t.state!r} is not {' | '.join(hazard.STATES)}")
        if not t.get("effect"):
            out.err(rel, f"TRAP {t.id}: no `effect:`")
        else:
            for cl in hazard._clauses(t.get("effect")):
                if not hazard.clause_ok(cl):
                    out.warn(rel, f"TRAP {t.id}: effect `{cl}` isn't one the tool resolves (the GM narrates it)")
        if t.get("disarm") and t.disarm_dc() is None:
            out.warn(rel, f"TRAP {t.id}: `disarm:` has no DC")
        if t.area and doc.front.get("tier") == "site" and t.area not in set(geo._area_slugs(doc)):
            out.warn(rel, f"TRAP {t.id}: area `{t.area}` is not in ## Areas")


def check_terrain(out, doc, frame):
    """`terrain:` / `forage:` on the file and its routes take the 04 values (Phase 14)."""
    import explore
    rel = _rel(doc.path)
    checks = [("file", str(doc.front.get("terrain") or ""), str(doc.front.get("forage") or ""))]
    checks += [(f"route `{r.id}`", r.terrain, r.forage) for r in frame.routes]
    for where, terrain, forage in checks:
        terrain, forage = terrain.strip().lower(), forage.strip().lower()
        if terrain and terrain not in explore.TERRAINS:
            out.warn(rel, f"{where}: terrain {terrain!r} is not {' | '.join(explore.TERRAINS)}")
        if forage and forage not in explore.FORAGE_DC:
            out.warn(rel, f"{where}: forage {forage!r} is not abundant | limited | scarce")


def check_compass_prose(out, doc, frame):
    """`<placed feature> … to the <compass>` in a Description against the geometry."""
    par, me = geo.parent_of(frame)
    if par is None or me is None or not me.placed:
        return
    span = doc.section("Description")
    text = " ".join(doc.body[i] for i in range(span[0] + 1, span[1])) if span else ""
    for sent in re.split(r"[.;:,]\s*", text):   # one clause at a time
        m = re.search(r"\bto the (north|south|east|west|northeast|northwest|southeast|southwest)\b", sent, re.I)
        if not m:
            continue
        for p in par.places:
            if p.id == me.id or not p.placed:
                continue
            words = [w for w in re.findall(r"[a-z]+", p.feature.lower()) if len(w) > 3]
            if p.id in sent.lower() or any(w in sent.lower() for w in words):
                want = _COMPASS[m.group(1).lower()]
                # "X to the east" in this place's description: X lies that way from here
                got = geo.bearing(me.center(), p.center())
                if want not in got and got not in want:
                    out.warn(_rel(doc.path), f"Description says {p.feature} … to the {m.group(1)}; "
                                             f"the geometry says {got}")


def check_movements(out, doc):
    span = doc.section("Movements")
    if span is None:
        return
    targets = []
    for i in range(span[0] + 1, span[1]):
        m = re.match(r"^\s*-\s*\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}\s*→\s*(\S+)", doc.body[i])
        if m:
            targets.append(m.group(1))
    for a, b in zip(targets, targets[1:] + targets[:1]):
        sa, sb = a.split("/")[0], b.split("/")[0]
        if sa == sb or len(targets) < 2:
            continue
        if not campaign.path("locations", sb).exists():
            out.err(_rel(doc.path), f"Movements → {b}: no locations/{sb}.md")
            continue
        try:
            geo.find_route(a, sb)
        except geo.GeoError:
            out.warn(_rel(doc.path), f"Movements {a} → {b}: no route")


def check_world(out):
    p = campaign.root() / "locations" / "world.md"
    if not p.exists():
        out.err("locations/world.md", "missing (every campaign has a world file: gm.py world init)")
        return
    doc = md.load(p)
    placed = {r.id for r in geo.load("world").places}
    known = set(placed)
    t = doc.table("Known")
    rows = t.rows if t else []
    known |= {r.get("id", "") for r in rows}
    for r in rows:
        for c in [c.strip() for c in re.split(r";", r.get("constraints", "")) if c.strip() and c.strip() not in ("—", "-")]:
            if not _SPATIAL.match(c):
                out.warn("locations/world.md", f"Known `{r.get('id')}`: {c!r} is not a spatial constraint "
                                               "(move it to notes, or it stays unchecked)")
                continue
            m = re.search(r"\b(?:of|from)\s+([\w-]+)$", c)
            if m and m.group(1) not in known:
                out.warn("locations/world.md", f"Known `{r.get('id')}`: constraint names unknown id {m.group(1)!r}")
    t = doc.table("Frontier")
    for r in (t.rows if t else []):
        if r.get("from") and r["from"] not in placed:
            out.warn("locations/world.md", f"Frontier `{r.get('id')}`: from {r['from']!r} is not placed")
    for f in _all_frames():
        for pl in f.places:
            m = re.search(r"placed:\s*within\s+(\d+)\s*d\s+of\s+([\w-]+)", pl.effect + " " + _notes(f, pl.id))
            if m:
                try:
                    plan = geo._dijkstra(f, m.group(2), pl.id)
                except geo.GeoError:
                    continue
                if plan.minutes and plan.minutes > int(m.group(1)) * 8 * 60:
                    out.warn(_rel(f.doc.path), f"`{pl.id}` was placed within {m.group(1)}d of {m.group(2)}; "
                                               f"the route takes {geo.fmt_minutes(plan.rounded)} (8 h travel days)")


def _notes(frame, pid):
    t = frame.doc.table("Places")
    for r in (t.rows if t else []):
        if r.get("id") == pid:
            return r.get("notes", "")
    return ""


def check_loop(out):
    """Time-loop campaigns need a baseline once the loop runs; `## Memory across loops`
    outside such a campaign is a leftover (07 → Time loop)."""
    p = campaign.campaign_doc_path()
    front = md.load(p).front if p.exists() else {}
    mech = front.get("mechanics") or []
    looping = "time-loop" in (mech if isinstance(mech, list) else [mech])
    if looping:
        st = campaign.load_state().front
        n = st.get("loop")
        sha = str(st.get("loop-baseline") or "")
        if isinstance(n, int) and n >= 1 and (not sha or sha == "pending"):
            out.err("state/current.md", f"loop {n} is running without a loop-baseline (gm.py loop start)")
        elif not isinstance(n, int) or n < 1:
            out.warn("state/current.md", "time loop not started yet (gm.py loop start at the loop day's first moment)")
    else:
        for d in campaign.npcs():
            if d.section("Memory across loops") is not None:
                out.warn(_rel(d.path), "`## Memory across loops` in a campaign without the time-loop mechanic")


def check_encounters(out, doc):
    """Every ENCOUNTER roster entry must be an SRD or custom-bestiary monster (07 → Custom monsters)."""
    from . import encounter as enc
    for line in doc.body:
        ln = enc.parse_line(line)
        if ln is None:
            continue
        for e in ln.entries:
            try:
                e.monster_xp()
            except enc.EncounterError:
                out.warn(_rel(doc.path), f"ENCOUNTER \"{ln.name}\": {e.name!r} is not an SRD or custom-bestiary monster "
                                         "(gm.py monster new \"<name>\" --from \"<similar SRD monster>\")")


def check_bestiary(out, doc):
    for k in ("name", "ac", "hp", "scores", "xp"):
        if doc.front.get(k) in (None, "", {}):
            out.err(_rel(doc.path), f"custom-bestiary: missing `{k}`")
    if doc.table("Attacks") is None and doc.section("Actions") is None:
        out.warn(_rel(doc.path), "custom-bestiary: no ## Attacks table or ## Actions")


def check_party_together(out):
    locs = {}
    for d in campaign.pcs():
        if d.front.get("present") is False:
            continue
        locs.setdefault(str(d.front.get("location") or ""), []).append(str(d.front.get("name")).split()[0])
    if len(locs) > 1:
        out.warn("pcs/", "the PCs are not all in one place: " + " · ".join(f"{', '.join(v)} @ {k}" for k, v in locs.items()))


# ---------- driver ----------

def _kind(rel):
    head = rel.split("/")[0]
    return head if head in ("pcs", "npcs", "locations", "scenarios", "state", "sessions", "tables",
                            "custom-bestiary") else ""


def check_file(out, path, fix_safe=False):
    rel = _rel(path)
    doc = check_parse(out, path)
    if doc is None:
        return
    kind = _kind(rel)
    if Path(path).name.startswith("_"):
        return
    check_required(out, doc, kind)
    if kind in ("pcs", "npcs"):
        check_location_value(out, doc, fix_safe)
    if kind == "npcs":
        check_movements(out, doc)
    if kind == "locations":
        check_location_file(out, doc)
    if kind in ("locations", "scenarios", "tables"):
        check_encounters(out, doc)
    if kind == "custom-bestiary":
        check_bestiary(out, doc)
    if rel == "state/current.md":
        check_state(out, doc)


def run(files=None, fix_safe=False):
    _frame_cache.clear()
    out = _Out()
    root = campaign.root()
    if files is not None:
        for rel in files:
            p = root / rel
            if p.exists() and p.suffix == ".md" and not rel.startswith("sessions/"):
                check_file(out, p, fix_safe)
        return out
    for kind in ("locations", "npcs", "pcs", "scenarios", "tables", "custom-bestiary"):
        for p in sorted((root / kind).glob("*.md")) if (root / kind).is_dir() else []:
            check_file(out, p, fix_safe)
    if campaign.state_path().exists():
        check_file(out, campaign.state_path(), fix_safe)
    check_world(out)
    check_party_together(out)
    check_loop(out)
    return out


def summary(found, limit=5):
    """Short report lines for the boundary sweeps (layer 3)."""
    errs = [f for f in found if f.level == "error"]
    warns = [f for f in found if f.level == "warning"]
    lines = [f"[LINT] full sweep: {len(errs)} error{'s' if len(errs) != 1 else ''} · "
             f"{len(warns)} warning{'s' if len(warns) != 1 else ''}" + (" (gm.py lint for the list)" if found else "")]
    lines += [f"[LINT] {f.line()}" for f in errs[:limit]]
    return lines
