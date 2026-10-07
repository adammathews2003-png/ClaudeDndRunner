"""What a creature can see in the scene's light, from its `senses:` frontmatter
(`[darkvision 60]`, `[blindsight 10, darkvision 120]`; set by chargen from race traits).

SRD 5.1 → Vision and Light: dim light is lightly obscured (disadvantage on Perception
checks that rely on sight); darkness is heavily obscured (effectively blinded).
Darkvision: within range, dim counts as bright and darkness as dim (shades of grey).
Blindsight and truesight perceive within range regardless of light.
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
