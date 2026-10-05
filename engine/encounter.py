"""`gm.py encounter budget|build|threat` and `gm.py danger` (docs/design/06 → Campaign
authoring, encounters and mechanics; 07 → Difficulty scaled to the table, The danger
stone; plan.md Phase 11 items 1–2).

    encounter budget [--present Kira,Kael] [--power +1]
    encounter build "<encounter name>" [--present …] [--power N]   → `--add` arguments for combat start
    encounter threat <place>                                         → writes `threat: {xp, fixed}`
    danger <place> | --bearing N [--present …]                       → green | yellow | red

The difficulty word is pinned to the campaign's `start-level` (07): a template's
absolute budget is the word's threshold at start-level for 4 PCs; `build` keeps the
per-PC pressure and changes the monster *count* for the PCs present (and item power),
never for level. `fixed` encounters keep their roster. Danger: green ≤ the party's
medium total · yellow ≤ deadly · red above deadly, or `fixed` above the party's
unshifted level.
"""
import math
import re

from lib import campaign, encounter as enc, geo, md
from lib.errors import ToolError


class EncounterCmdError(ToolError):
    pass


def campaign_param(key, default=None):
    p = campaign.campaign_doc_path()
    front = md.load(p).front if p.exists() else campaign.load_state().front
    v = front.get(key)
    return default if v in (None, "") else v


def start_level():
    v = campaign_param("start-level", None)
    if isinstance(v, int):
        return v
    levels = [int(d.front.get("level") or 1) for d in campaign.pcs()]
    return min(levels) if levels else 1


def present_pcs(names=None):
    if names:
        out = []
        for n in [x.strip() for x in names.split(",") if x.strip()]:
            m = campaign.resolve(n)
            if not m.is_pc or not m.path:
                raise EncounterCmdError(f"{n!r} is not a PC")
            out.append(md.load(m.path))
        return out
    return [d for d in campaign.pcs() if d.front.get("present") is not False]


def _power(docs, override):
    if override is not None:
        return float(override), "override"
    return enc.item_power(docs)


def budget(present=None, power=None):
    docs = present_pcs(present)
    if not docs:
        raise EncounterCmdError("encounter budget: no PCs present")
    levels = [int(d.front.get("level") or 1) for d in docs]
    pw, desc = _power(docs, power)
    th = enc.party_thresholds(levels, pw)
    lv = ", ".join(f"L{lv}" for lv in levels)
    line = (f"[BUDGET] {len(docs)} PCs ({lv}) · " + " · ".join(f"{w} {th[w]:,}" for w in enc.WORDS)
            + f" · power {pw:+g} ({desc})")
    return line, {"thresholds": th, "power": pw, "size": len(docs)}


def find_line(name):
    """The ENCOUNTER line named `name` in locations/, scenarios/ or tables/."""
    root = campaign.root()
    hits = []
    for kind in ("locations", "scenarios", "tables"):
        for p in sorted((root / kind).glob("*.md")) if (root / kind).is_dir() else []:
            for line in p.read_text(encoding="utf-8").splitlines():
                ln = enc.parse_line(line, f"{kind}/{p.name}")
                if ln and ln.name.lower() == name.lower():
                    hits.append(ln)
    if not hits:
        raise EncounterCmdError(f"encounter: no ENCOUNTER line named {name!r}")
    return hits[0]


def build(name, present=None, power=None):
    line = find_line(name)
    docs = present_pcs(present)
    if not docs:
        raise EncounterCmdError("encounter build: no PCs present")
    pw, desc = _power(docs, power)
    n, roster, adj, target = enc.fit(line, start_level(), len(docs), pw)
    adds = " ".join(f'--add "srd:{nm}' + (f' x{c}"' if c > 1 else '"') for nm, c in roster)
    out = []
    if line.fixed:
        avg = sum(int(d.front.get("level") or 1) for d in docs) / len(docs)
        head = (f"[BUILD \"{line.name}\" fixed L{line.level} {line.word} · roster: "
                + ", ".join(f"{nm} ×{c}" for nm, c in roster) + f" · adj {adj:,}]")
        out.append(head)
        if line.level and line.level > math.floor(avg):
            out.append(f"[fixed L{line.level} {line.word} — above the party]")
    else:
        out.append(f"[BUILD \"{line.name}\" {line.word} · {len(docs)} PCs · start L{start_level()} · power {pw:+g} "
                   f"· target {int(target):,} → " + ", ".join(f"{nm} ×{c}" for nm, c in roster)
                   + f" (adj {adj:,})]")
    out.append(f"[combat start … {adds}]")
    return out, {"roster": roster, "adjusted": adj, "fixed": line.fixed}


def threat_of(doc):
    """(xp, fixed) of the hardest ENCOUNTER line in a location file, at nominal party."""
    best = (0, False)
    sl = start_level()
    threat_of.skipped = []
    for text in doc.body:
        ln = enc.parse_line(text)
        if ln is None:
            continue
        try:
            _, _, adj, _ = enc.fit(ln, sl, enc.NOMINAL_PARTY, 0.0)
        except enc.EncounterError as e:
            threat_of.skipped.append(f"{ln.name}: {e}")
            continue
        if adj > best[0]:
            best = (adj, ln.fixed)
    return best


def threat(place):
    p = campaign.path("locations", place)
    if not p.exists():
        raise EncounterCmdError(f"encounter threat: no locations/{place}.md")
    doc = md.load(p)
    xp, fixed = threat_of(doc)
    skipped = list(getattr(threat_of, "skipped", []))
    if skipped and xp == 0:
        raise EncounterCmdError("encounter threat: no line could be priced — " + "; ".join(skipped))
    doc.set_front("threat", {"xp": xp, "fixed": fixed})
    doc.save()
    line = f"[threat {place}: xp {xp:,}" + (" · fixed" if fixed else "") + "]"
    if skipped:
        line += " [skipped (not SRD): " + "; ".join(skipped) + "]"
    return line, {"xp": xp, "fixed": fixed}


def _fixed_level(doc):
    lvl = None
    best = -1
    sl = start_level()
    for text in doc.body:
        ln = enc.parse_line(text)
        if ln is None:
            continue
        try:
            _, _, adj, _ = enc.fit(ln, sl, enc.NOMINAL_PARTY, 0.0)
        except enc.EncounterError:
            continue
        if adj > best:
            best, lvl = adj, (ln.level if ln.fixed else None)
    return lvl


def colour(place, docs, power):
    p = campaign.path("locations", place)
    doc = md.load(p)
    t = doc.front.get("threat") if isinstance(doc.front.get("threat"), dict) else None
    if t is None:
        xp, fixed = threat_of(doc)
    else:
        xp, fixed = int(t.get("xp") or 0), bool(t.get("fixed"))
    if xp <= 0:
        return None, xp
    levels = [int(d.front.get("level") or 1) for d in docs]
    th = enc.party_thresholds(levels, power)
    if fixed:
        lvl = _fixed_level(doc)
        if lvl and lvl > math.floor(sum(levels) / len(levels)):
            return "red", xp
    if xp <= th["medium"]:
        return "green", xp
    if xp <= th["deadly"]:
        return "yellow", xp
    return "red", xp


def danger(place=None, bearing=None, present=None, power=None):
    docs = present_pcs(present)
    if not docs:
        raise EncounterCmdError("danger: no PCs present")
    pw, _ = _power(docs, power)
    if place:
        c, xp = colour(place, docs, pw)
        if c is None:
            return [f"[DANGER {place}: no encounters authored here]"], {}
        return [f"[DANGER {place}: {c}]"], {"colour": c}
    want = bearing.upper()
    here = str(campaign.load_state().front.get("party-location") or "").split("/")[0]
    rows = []
    seen = set()
    for frame, node in geo.chain(here):
        me = frame.place(node)
        if me is None or not me.placed:
            continue
        for pl in frame.places:
            if not pl.placed or not pl.ref or pl.id == node or pl.ref in seen:
                continue
            if geo.bearing(me.center(), pl.center()) != want:
                continue
            if not campaign.path("locations", pl.ref).exists():
                continue
            c, xp = colour(pl.ref, docs, pw)
            if c is None:
                continue
            seen.add(pl.ref)
            d = geo.edge_distance(me, pl)
            rows.append((geo.to_ft(d, frame.unit), f"{pl.feature} {c} ({geo.distance_text(d, frame.unit)})"))
    rows.sort()
    return [f"[DANGER {want}] " + (" · ".join(r for _, r in rows) if rows else "nothing authored that way")], {}


def cmd_encounter(ctx):
    a = ctx.args
    if a.action == "budget":
        lines = [budget(a.present, a.power)[0]]
    elif a.action == "build":
        if not a.name:
            raise EncounterCmdError('encounter build "<encounter name>"')
        lines, _ = build(" ".join(a.name), a.present, a.power)
    else:
        if not a.name:
            raise EncounterCmdError("encounter threat <place>")
        lines = [threat(a.name[0])[0]]
    for line in lines:
        ctx.emit(line)


def cmd_danger(ctx):
    a = ctx.args
    if not a.place and not a.bearing:
        raise EncounterCmdError("danger <place> | --bearing N|NE|…")
    lines, _ = danger(a.place, a.bearing, a.present, a.power)
    for line in lines:
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("encounter", parents=[g], help="encounter budget | build \"name\" | threat <place>")
    p.add_argument("action", choices=["budget", "build", "threat"])
    p.add_argument("name", nargs="*")
    p.add_argument("--present", help="Kira,Kael (default: present PCs)")
    p.add_argument("--power", type=float, help="item power override (virtual levels)")
    p.set_defaults(func=cmd_encounter)
    p = sub.add_parser("danger", parents=[g], help="danger <place> | --bearing N")
    p.add_argument("place", nargs="?")
    p.add_argument("--bearing", choices=["N", "NE", "E", "SE", "S", "SW", "W", "NW", "n", "ne", "e", "se", "s", "sw", "w", "nw"])
    p.add_argument("--present")
    p.add_argument("--power", type=float)
    p.set_defaults(func=cmd_danger)
