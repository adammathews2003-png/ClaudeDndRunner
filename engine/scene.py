"""`scene enter <location> [--area A] [--light dim|dark] [--write] [--summary "…"] [--scene "…"]`
and `onstage <npc> [--goal "…"] [--note "…"] [--remove]` (docs/design/06 → `gm.py scene
enter`; 02 → Session start, Spatial model; plan.md Phase 4 item 2).

`scene enter` prints the GM's packet for a place: header, description, Exits and Nearby
(derived by lib/geo.py — no direction or distance is typed anywhere), who is present
and who is elsewhere in the site, passive Perception against `## Hidden` (light: dim
−5 unless darkvision; dark: darkvision only, as dim; ties → PC), the scenario beats
whose text mentions the place or the people here (a text filter: whether a beat fires
is the GM's call), and the Layout status. The packet is GM-only; never pasted.

`--write` makes it the current scene: moves the party (move-party), sets light/scene,
rebuilds On stage (from NPC frontmatter), Watch for (the matching beats) and Clocks
(scenario CLOCK lines not yet passed are added; existing ones kept), resets tempo to
calm and ends `scene`-scoped table rules. Refused during combat.
"""
import re
from pathlib import Path

from lib import campaign, gametime, geo, journal, md, sight
from lib.errors import ToolError
import mutations
import rules
import tempo

_HIDDEN = re.compile(r"^\s*-\s*DC\s*(\d+)\s*(?:\(([\w-]+)\))?\s*:\s*(.+)$", re.I)
_MOVE = re.compile(r"^\s*-\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*→\s*(\S+)\s*(.*)$")
_STOP = {"the", "old", "of", "and", "a", "an", "at", "in", "on", "s"}


class SceneError(ToolError):
    pass


def _split(location, area=None):
    site, _, a = location.strip().partition("/")
    return site, (area or a or None)


def _bullets(doc, heading):
    span = doc.section(heading)
    if span is None:
        return []
    return [doc.body[i] for i in range(span[0] + 1, span[1]) if doc.body[i].strip().startswith("-")]


def _paragraphs(doc, heading):
    span = doc.section(heading)
    if span is None:
        return ""
    return " ".join(doc.body[i].strip() for i in range(span[0] + 1, span[1])
                    if doc.body[i].strip() and not doc.body[i].strip().startswith("<!--"))


def _first(name):
    words = str(name).split()
    return name if not words or words[0].lower() in ("the", "a", "an") else words[0]


# ---------- packet pieces ----------

def exits_line(site, area):
    bits = []
    for e in geo.exits(site, area):
        extra = []
        access = e["access"]
        if access and access.lower() != "obvious":
            extra.append(access)
        if e["adjacent"]:
            extra.append("adjacent")
        if e["bearing"]:
            extra.append(e["bearing"])
        name = e["to"] if e["label"] == e["to"] else f"{e['label']} → {e['to']}"
        bits.append(name + (f" ({', '.join(extra)})" if extra else ""))
    return "Exits: " + (" · ".join(bits) if bits else "—")


def nearby_line(frame):
    """Nearby places in the parent frame of `frame` (a site or area)."""
    par, row = geo.parent_of(frame)
    if par is None or row is None:
        return "Nearby: —"
    bits = []
    for p, brg, dist, mins, plan in geo.nearby(par, row.id):
        t = f"{mins} min" if mins is not None and mins < 60 else (geo.fmt_minutes(mins) if mins else None)
        via = ""
        if plan is not None and len(plan.routes) > 1:
            via = f" (via {', '.join(r.id for r in plan.routes)})"
        if dist is None:
            bits.append(f"{p.feature} (unplaced)" + (f", {t}" if t else ""))
        else:
            where = f"{dist} {brg}" if dist != "adjacent" else f"adjacent {brg}"
            bits.append(f"{p.feature} {where}, " + (t + via if t else "no route"))
    return "Nearby: " + (" · ".join(bits) if bits else "—")


def _at(loc, site, area):
    loc = (loc or "").strip().lower()
    if area:
        return loc == f"{site}/{area}".lower() or (loc == site.lower())
    return loc.split("/")[0] == site.lower()


def people(site, area, now):
    """(present npc docs, elsewhere-in-site npc docs, present pc docs)."""
    here, elsewhere = [], []
    for doc in campaign.npcs():
        if str(doc.front.get("status") or "").lower() == "dead":
            continue
        loc = str(doc.front.get("location") or "")
        if _at(loc, site, area):
            here.append(doc)
        elif loc.split("/")[0].lower() == site.lower():
            elsewhere.append(doc)
    return here, elsewhere, campaign.scene_pcs()


def movement_now(doc, now):
    """The `## Movements` line covering `now` (Day, minute), or None."""
    if now is None:
        return None
    for line in _bullets(doc, "Movements"):
        m = _MOVE.match(line)
        if not m:
            continue
        a, b = gametime.parse_clock(m.group(1)), gametime.parse_clock(m.group(2))
        t = now[1]
        inside = (a <= t < b) if a < b else (t >= a or t < b)
        if inside:
            return line.strip()[1:].strip()
    return None


def present_line(here, pcs):
    bits = [f"{_first(d.front.get('name'))} (npc, {d.front.get('attitude-to-party') or '?'})" for d in here]
    if pcs:
        bits.append(", ".join(tempo.short_pc(d) for d in pcs) + " (party)")
    return "Present: " + (" · ".join(bits) if bits else "—")


def elsewhere_line(docs, now):
    bits = []
    for d in docs:
        loc = str(d.front.get("location") or "")
        where = loc.split("/", 1)[1] if "/" in loc else loc
        mv = movement_now(d, now)
        bits.append(f"{_first(d.front.get('name'))} ({where}" + (f" — Movements: {mv}" if mv else "") + ")")
    return "Not on stage but here: " + (" · ".join(bits) if bits else "—")


def hidden_entries(frame, area):
    out = []
    for line in _bullets(frame.doc, "Hidden"):
        m = _HIDDEN.match(line)
        if not m:
            continue
        scope = m.group(2)
        if scope and scope != area:
            continue
        out.append((int(m.group(1)), m.group(3).strip()))
    return out


def notices_line(frame, area, pcs, light):
    entries = hidden_entries(frame, area)
    if not entries:
        return "Passive notices: — (nothing hidden here)"
    bits = []
    for d in pcs:
        pp = d.front.get("passive-perception")
        if not isinstance(pp, int):
            continue
        seen_in = sight.effective(d, light)[0]
        name = tempo.short_pc(d)
        if seen_in == "dark":
            bits.append(f"{name} (dark, no darkvision) → nothing")
            continue
        eff = pp - 5 if seen_in == "dim" else pp
        tag = f"PP {pp}" + (f"→{eff} {light}" if eff != pp else "")
        seen = [f"DC {dc} {text}" for dc, text in entries if eff >= dc]  # ties → PC
        bits.append(f"{name} ({tag}) → " + ("; ".join(seen) if seen else "nothing"))
    return "Passive notices: " + (" · ".join(bits) if bits else "—")


def _keywords(frame, area):
    words = {frame.slug.lower(), frame.slug.replace("-", " ").lower()}
    if area:
        words |= {area.lower(), area.replace("-", " ").lower()}
    for w in re.findall(r"[a-z]+", frame.name.lower()):
        if w not in _STOP and len(w) >= 3:
            words.add(w)
    return words


def beats(frame, area, names):
    """[(scenario slug, n, kind, text, matched words)] for beat lines that mention the
    place or the people (text filter only)."""
    out = []
    keys = _keywords(frame, area)
    folder = campaign.root() / "scenarios"
    for p in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        doc = md.load(p)
        n = 0
        for line in _bullets(doc, "Beats"):
            m = re.match(r"^\s*-\s*(WHEN|CLOCK)\b(.*)$", line)
            if not m:
                continue
            n += 1
            low = line.lower()
            hit = [k for k in sorted(keys) if re.search(rf"\b{re.escape(k)}\b", low)]
            hit += [nm for nm in names if re.search(rf"\b{re.escape(nm.lower())}\b", low)]
            if hit:
                out.append((p.stem, n, m.group(1), m.group(2).strip(), hit))
    return out


def triggers_line(found):
    multi = len({f[0] for f in found}) > 1
    bits = [(f"{s} " if multi else "") + f"beat {n} ({', '.join(dict.fromkeys(h))})" for s, n, _, _, h in found]
    return "Triggers mentioning this place/these NPCs: " + (" · ".join(bits) if bits else "—")


def layout_line(frame, area):
    if frame.tier != "site":
        return f"Layout: — ({frame.tier} tier)"
    if area and area in frame.layouts:
        lay = frame.layouts[area]
        return f"Layout: {area} ({len(lay.terrain)} features) — `gm.py space map` to draw"
    have = ", ".join(frame.layouts) or "none"
    return f"Layout: none for {area or frame.slug} yet (laid out: {have}); write one at the first tense scene"


# ---------- commands ----------

def enter(location, area=None, light=None, write=False, summary=None, scene_name=None):
    site, area = _split(location, area)
    frame = geo.load(site)
    if frame.tier == "world":
        raise SceneError(f"scene enter: {site} is the world map; enter a place in it")
    if area and frame.tier == "site" and area not in geo.area_slugs(site) and area not in frame.layouts:
        raise SceneError(f"scene enter: {site} has no area {area!r} ({', '.join(geo.area_slugs(site)) or 'none'})")
    state = campaign.load_state()
    now = None
    try:
        now = gametime.parse(state.front.get("in-game-datetime"))
    except gametime.TimeError:
        pass
    light = light or "bright"
    loc = f"{site}/{area}" if area else site
    par, _ = geo.parent_of(frame)
    head = (f"[SCENE] {loc} ({frame.tier} · {frame.type or '?'}" + (f", in {par.slug}" if par else "")
            + f") · light: {light}")
    here, elsewhere, pcs = people(site, area, now)
    names = [_first(d.front.get("name")) for d in here + elsewhere]
    found = beats(frame, area, names)
    lines = [head, "Description: " + (_paragraphs(frame.doc, "Description") or "—"),
             exits_line(site, area) if frame.tier == "site" else "Exits: (area: see its Routes)",
             nearby_line(frame), present_line(here, pcs), elsewhere_line(elsewhere, now),
             notices_line(frame, area, pcs, light), triggers_line(found), layout_line(frame, area)]
    data = {"location": loc, "present": [str(d.front.get("name")) for d in here]}
    if write:
        lines += write_scene(loc, light, here, found, summary, scene_name)
    return lines, data


def place_name(loc):
    """'The Old Mill — main floor' for `old-mill/main-floor` (the site file's name)."""
    site, _, area = loc.partition("/")
    try:
        name = geo.load(site).name or site
    except geo.GeoError:
        name = site.replace("-", " ")
    return f"{name} — {area.replace('-', ' ')}" if area else name


def write_scene(loc, light, here, found, summary, scene_name):
    state = campaign.load_state()
    if tempo.in_combat(state):
        raise SceneError("scene enter --write: combat is running (combat end first)")
    moved = str(state.front.get("party-location") or "") != loc
    out = [mutations.move_party(loc)[0]]
    state = campaign.load_state()
    state.set_front("light", light)
    if scene_name:
        state.set_front("scene", scene_name)
    elif moved:   # a new place: never keep the last place's scene name
        state.set_front("scene", place_name(loc))
    if summary:
        tempo.set_section(state, "Summary", [summary])
    bullets = []
    for d in here:
        rel = Path(d.path).relative_to(campaign.root()).as_posix()
        goal = d.front.get("default-goal")
        bullets.append(f"- **{_first(d.front.get('name'))}** ({rel})" + (f" — goal: {goal}" if goal else ""))
    tempo.set_section(state, "On stage", bullets or ["(nobody)"])
    watch = []
    for slug, n, kind, text, _ in found:
        if kind == "WHEN":
            watch.append(f"- {text} → scenarios/{slug}.md beat {n}")
    tempo.set_section(state, "Watch for", watch or ["(nothing here)"])
    clocks = [b for b in _bullets(state, "Clocks")]
    have = set()
    for b in clocks:
        k = _clock_key(b)
        if k[0] < 10 ** 9:
            have.add(gametime.fmt(k))
    now = gametime.parse(state.front.get("in-game-datetime"))
    folder = campaign.root() / "scenarios"
    for p in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        for line in _bullets(md.load(p), "Beats"):
            m = re.match(r"^\s*-\s*CLOCK\s+(Day\s+-?\d+\s+\d{1,2}:\d{2})\s*:\s*(.+)$", line)
            if not m:
                continue
            t = gametime.parse(m.group(1))
            key = gametime.fmt(t)
            if gametime.diff(now, t) >= 0 and key not in have:
                text = m.group(2).strip()
                short = re.split(r"(?<=[.;:])\s", text)[0].rstrip(".;:")
                clocks.append(f"- {key}: {short} (scenario clock)")
                have.add(key)
    clocks.sort(key=lambda b: _clock_key(b))
    tempo.set_section(state, "Clocks", clocks or ["(none)"])
    tempo.set_tempo(state, "calm", [])
    state.save()
    out += rules.end_scope("scene")
    journal.log_delta(f"scene enter {loc}", gm=False)
    from lib import lint
    out += lint.summary(lint.run())
    out.append(f"[scene written: {loc} · {len(bullets)} on stage · {len(watch)} watch · {len(clocks)} clocks]")
    return out


def _clock_key(bullet):
    m = re.match(r"^\s*-\s*(Day\s+-?\d+\s+\d{1,2}:\d{2})", bullet)
    if not m:
        return (10 ** 9, 0)
    try:
        return gametime.parse(m.group(1))
    except gametime.TimeError:
        return (10 ** 9, 0)


def onstage(name, goal=None, note=None, remove=False):
    state = campaign.load_state()
    target = campaign.resolve(name, state)
    if target.is_pc:
        raise SceneError("onstage is for NPCs (PCs are always in the scene)")
    bullets = campaign.onstage(state)
    hit = next((b for b in bullets if b.name.lower() == target.name.lower()
                or (b.path and target.path and Path(b.path).resolve() == Path(target.path).resolve())), None)
    if remove:
        if hit is None:
            raise SceneError(f"{target.name} is not on stage")
        del state.body[hit.line]
        state.save()
        journal.log_delta(f"onstage -{hit.name}", gm=True)
        return f"[onstage {hit.name} removed]", {"name": hit.name, "removed": True}
    doc = target.doc
    short = hit.name if hit else _first(doc.front.get("name") if doc else target.name)
    old = state.body[hit.line] if hit else ""
    old_goal = re.search(r"goal:\s*(.+)$", old)
    old_note = re.match(r"^\s*-\s+\*\*.+?\*\*(?:\s*\([^)]*\))?\s*—\s*(.*?)(?:;?\s*goal:.*)?$", old)
    goal = goal if goal is not None else (old_goal.group(1).strip() if old_goal else
                                           (doc.front.get("default-goal") if doc else None))
    note = note if note is not None else (old_note.group(1).strip() if old_note else "")
    ref = f" ({Path(doc.path).relative_to(campaign.root()).as_posix()})" if doc else ""
    tail = "; ".join(x for x in (note, f"goal: {goal}" if goal else "") if x)
    line = f"- **{short}**{ref}" + (f" — {tail}" if tail else "")
    if hit:
        state.body[hit.line] = line
    else:
        span = state.section("On stage")
        if span is not None:
            for j in range(span[0] + 1, span[1]):
                if state.body[j].strip() in ("(nobody)",):
                    state.body[j] = line
                    break
            else:
                state.append_line("On stage", line)
        else:
            state.append_line("On stage", line)
    state.save()
    journal.log_delta(f"onstage {short}" + (f" · goal: {goal}" if goal else ""), gm=True)
    return f"[onstage {short}" + (f" · {tail}" if tail else "") + "]", {"name": short, "goal": goal, "note": note}


def cmd_scene(ctx):
    a = ctx.args
    lines, data = enter(a.location, a.area, a.light, a.write, a.summary, a.scene)
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def cmd_onstage(ctx):
    a = ctx.args
    line, data = onstage(a.name, a.goal, a.note, a.remove)
    ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("scene", parents=[g], help="scene enter <location> — the GM's scene packet")
    p.add_argument("action", choices=["enter"])
    p.add_argument("location")
    p.add_argument("--area")
    p.add_argument("--light", choices=["bright", "dim", "dark"])
    p.add_argument("--write", action="store_true", help="make it the current scene (rebuild current.md)")
    p.add_argument("--summary", help="with --write: the new Summary")
    p.add_argument("--scene", help="with --write: the scene name")
    p.set_defaults(func=cmd_scene)
    p = sub.add_parser("onstage", parents=[g], help="edit one On stage bullet")
    p.add_argument("name")
    p.add_argument("--goal")
    p.add_argument("--note")
    p.add_argument("--remove", action="store_true")
    p.set_defaults(func=cmd_onstage)
