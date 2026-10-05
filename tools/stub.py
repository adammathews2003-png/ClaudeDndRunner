"""`gm.py stub npc|location|place <name> [--location site[/area]] [--in <area>] [--at x,y,z]
[--note "…"] [--type building]` (planning/06 → `gm.py stub`; 05 #6; plan.md Phase 7
item 6). Improvised canon → a valid file (or Places row) in one call.

- `npc`: `npcs/<slug>.md` from the 04 template (`location` = `--location`, else the
  party's), body sections present and empty except the note.
- `location`: `locations/<slug>.md` (a site; `--in` = its parent area, default the
  party's area) plus its `## Places` row in the parent (`--at` = the footprint's
  `from`; without it the coordinates stay `?` and lint warns).
- `place`: only the Places row, `ref —` (a smithy that needs no file yet).
Refuses when the slug exists. Everything is logged.
"""
import re

from lib import campaign, geo, journal, md
from lib.errors import ToolError
import mutations


class StubError(ToolError):
    pass


def _parent_area(in_area):
    if in_area:
        return in_area
    loc = str(campaign.load_state().front.get("party-location") or "").split("/")[0]
    if not loc:
        raise StubError("stub: no --in and no party-location")
    try:
        par = geo.load(loc)
    except geo.GeoError as e:
        raise StubError(str(e)) from None
    return par.slug if par.tier == "area" else (par.parent or loc)


def _point(text):
    if not text:
        return None
    nums = re.findall(r"-?\d+(?:\.\d+)?", text)
    if len(nums) not in (2, 3):
        raise StubError(f"--at wants x,y or x,y,z, got {text!r}")
    return "(" + ",".join(nums + (["0"] if len(nums) == 2 else [])) + ")"


def _places_row(area, pid, feature, at, ref, note):
    p = campaign.path("locations", area)
    if not p.exists():
        raise StubError(f"stub: no locations/{area}.md")
    doc = md.load(p)
    t = doc.table("Places")
    if t is not None and t.find("id", pid) >= 0:
        raise StubError(f"stub: {area} already has a Places row `{pid}`")
    row = {"id": pid, "glyph": feature[:1].upper(), "feature": feature, "at": at or "",
           "from": at or "?", "to": at or "", "effect": note or "not yet detailed", "ref": ref,
           "source": "generated"}
    if t is None:
        cols = ["id", "glyph", "feature", "at", "from", "to", "effect", "ref", "source"]
        doc.append_line("Places", "| " + " | ".join(cols) + " |")
        doc.append_line("Places", "|" + "|".join("-" * (len(c) + 2) for c in cols) + "|")
        doc.append_line("Places", "| " + " | ".join(row[c] for c in cols) + " |")
    else:
        t.append(row)
    doc.save()


NPC = """---
name: {name}
location: {location}
role:
faction:
attitude-to-party: neutral
statblock: commoner
default-goal:
status: alive
---

# {name}

## Description
{note}

## Personality & motivation

## Knowledge & secrets

## History with the party

## Movements
<!-- `- HH:MM–HH:MM → site[/area] (note)` lines first; prose after. -->
"""

SITE = """---
name: {name}
tier: site
type: {type}
parent: {parent}
tags: []
---

# {name}

## Description
{note}

## Areas

## Items & features

## Hidden

## Notes / current state
(stub — flesh out if it recurs)
"""


def stub(kind, name, location=None, in_area=None, at=None, note=None, type_="building"):
    slug = campaign.slugify(name)
    if not slug:
        raise StubError("stub: give a name")
    if kind == "npc":
        p = campaign.path("npcs", slug)
        if p.exists():
            raise StubError(f"stub: {p} already exists")
        loc = location or str(campaign.load_state().front.get("party-location") or "")
        loc = mutations.validate_location(loc)
        md.new(p, NPC.format(name=name, location=loc, note=note or "(stub)")).save()
        journal.log_delta(f"stub npc {name} @ {loc}")
        return f"[stub npc {name} → npcs/{slug}.md @ {loc}]", {"path": str(p)}
    area = _parent_area(in_area)
    pt = _point(at)
    if kind == "location":
        p = campaign.path("locations", slug)
        if p.exists():
            raise StubError(f"stub: {p} already exists")
        _places_row(area, slug, name, pt, slug, note)
        md.new(p, SITE.format(name=name, type=type_, parent=area, note=note or "(stub)")).save()
        journal.log_delta(f"stub location {name} in {area}" + (f" at {pt}" if pt else " (unplaced)"))
        warn = "" if pt else " · no --at: coordinates `?` (lint warns until placed)"
        return f"[stub location {name} → locations/{slug}.md · Places row in {area}{warn}]", {"path": str(p)}
    _places_row(area, slug, name, pt, "—", note)
    journal.log_delta(f"stub place {name} in {area}" + (f" at {pt}" if pt else " (unplaced)"))
    return f"[stub place {name} → Places row `{slug}` in {area}" + ("" if pt else " (unplaced)") + "]", {}


def cmd_stub(ctx):
    a = ctx.args
    line, data = stub(a.kind, " ".join(a.name), a.location, a.in_, a.at, a.note, a.type)
    ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("stub", parents=[g], help="stub npc|location|place <name>")
    p.add_argument("kind", choices=["npc", "location", "place"])
    p.add_argument("name", nargs="+")
    p.add_argument("--location")
    p.add_argument("--in", dest="in_")
    p.add_argument("--at")
    p.add_argument("--note")
    p.add_argument("--type", default="building")
    p.set_defaults(func=cmd_stub)
