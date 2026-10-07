"""What a creature can see in the scene's light, from its `senses:` frontmatter
(`[darkvision 60]`, `[blindsight 10, darkvision 120]`; set by chargen from race traits).

SRD 5.1 → Vision and Light: dim light is lightly obscured (disadvantage on Perception
checks that rely on sight); darkness is heavily obscured (effectively blinded).
Darkvision: within range, dim counts as bright and darkness as dim (shades of grey).
Blindsight and truesight perceive within range regardless of light.

Carried sources (Phase 13, lib/light.py): `scene_light(doc, ambient, state)` is the
light a PC actually has: the ambient `light:` or the best source carried by the active
group, by radius from the carrier's `pos` in combat or a Stage.
"""
import re

_SENSE = re.compile(r"^\s*([a-z' ]+?)\s+(\d+)", re.I)


def senses(doc):
    """{'darkvision': 60, …} from a PC/NPC doc's `senses:` list."""
    out = {}
    for s in doc.front.get("senses") or []:
        m = _SENSE.match(str(s))
        if m:
            out[m.group(1).strip().lower()] = int(m.group(2))
    return out


def effective(doc, light):
    """(effective light within range, range in ft or None, sense name or None).
    `light` is the scene's bright|dim|dark."""
    light = str(light or "bright").lower()
    ss = senses(doc)
    for name in ("truesight", "blindsight"):
        if name in ss and light != "bright":
            return "bright", ss[name], name
    dv = ss.get("darkvision")
    if dv and light == "dim":
        return "bright", dv, "darkvision"
    if dv and light == "dark":
        return "dim", dv, "darkvision"
    return light, None, None


def describe(doc, light, name):
    """One brief fragment: how `name` sees in this light."""
    eff, rng, sense = effective(doc, light)
    if sense == "darkvision" and eff == "dim":
        return f"{name} sees to {rng} ft (darkvision: grey, no colour; sight Perception at disadv.)"
    if sense:
        return f"{name} sees normally to {rng} ft ({sense})"
    if eff == "dim":
        return f"{name} dim (sight Perception at disadv.)"
    if eff == "dark":
        return f"{name} blind without a light"
    return f"{name} sees normally"


def _row_for(state, doc):
    """The Combatants (else Stage) row of a PC/NPC file, or None."""
    from pathlib import Path
    if state is None:
        return None
    table = state.table("Combatants") or state.table("Stage")
    if table is None:
        return None
    slug = Path(doc.path).stem
    full = str(doc.front.get("name") or slug).lower()
    for row in table.rows:
        ref = (row.get("ref") or "").strip().lower()
        name = re.sub(r"\s*\(PC\)", "", row.get("name", ""), flags=re.I).strip().lower()
        if ref.endswith("/" + slug) or name in (full, full.split()[0]):
            return row
    return None


def distance_fn(state):
    """f(carrier_doc, doc) -> feet between their rows' positions, or None."""
    def dist(a, b):
        if a is b or a.path == b.path:
            return 0
        ra, rb = _row_for(state, a), _row_for(state, b)
        if ra is None or rb is None or "?" in (ra.get("pos") or "?") or "?" in (rb.get("pos") or "?"):
            return None
        try:
            import space
            return space.dist_between(space.Combatant(ra).cells(), space.Combatant(rb).cells())
        except Exception:  # noqa: BLE001 — an unreadable position lights like no position
            return None
    return dist


def scene_light(doc, ambient, state=None, docs=None):
    """The effective light for `doc`: ambient, or the best carried source of the group."""
    from . import campaign, light
    group = campaign.scene_pcs() if docs is None else docs
    return light.level_for(doc, ambient, group, distance_fn(state))
