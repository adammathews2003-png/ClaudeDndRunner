"""Carried light sources (docs/design/02 → Table mechanics → Light; 06 → Phase 13 → Light;
SRD 5.1 → Adventuring Gear, Spells).

`light:` on the scene is the AMBIENT light and is never overwritten by a carried source.
A creature carrying a lit source has `lit: [torch 40m]` (minutes left; no time when
`track-light: off`). The effective light for a PC is the brighter of the ambient light
and the best source carried by anyone in the active group; in combat or a Stage, a
source lights only what is within its radius of the carrier's `pos`.
"""
import re

# key: (bright ft, dim ft beyond it, minutes per use, label)
SOURCES = {
    "torch": (20, 20, 60, "torch"),
    "lantern": (30, 30, 360, "lantern"),                  # hooded; 6 h per flask of oil
    "bullseye-lantern": (60, 60, 360, "bullseye lantern"),  # a 60 ft cone
    "candle": (5, 5, 60, "candle"),
    "light": (20, 20, 60, "light"),                       # the cantrip
    "daylight": (60, 60, 60, "daylight"),
}
RANK = {"dark": 0, "dim": 1, "bright": 2}
_ENTRY = re.compile(r"^\s*([a-z-]+)(?:\s+(\d+)m)?\s*$", re.I)


def entries(front):
    """[(source, minutes left or None)] from a creature's `lit:`."""
    out = []
    for item in (front.get("lit") or []) if front else []:
        m = _ENTRY.match(str(item))
        if m and m.group(1).lower() in SOURCES:
            out.append((m.group(1).lower(), int(m.group(2)) if m.group(2) else None))
    return out


def fmt_entry(source, minutes):
    return source if minutes is None else f"{source} {minutes}m"


def brighter(a, b):
    return a if RANK.get(a, 2) >= RANK.get(b, 2) else b


def carried(docs):
    """[{owner, doc, source, left, bright, dim}] for every lit source in `docs`."""
    out = []
    for d in docs:
        owner = str(d.front.get("name") or "?").split()[0]
        for src, left in entries(d.front):
            b, dm, _, _ = SOURCES[src]
            out.append({"owner": owner, "doc": d, "source": src, "left": left, "bright": b, "dim": dm})
    return out


def best(docs):
    """The brightest carried source (bright radius, then dim, then time left), or None."""
    srcs = carried(docs)
    if not srcs:
        return None
    return max(srcs, key=lambda s: (s["bright"], s["dim"], s["left"] or 0))


def describe(src):
    """`Kael's torch 40m: bright 20 ft, dim 40 ft` for the Sight line."""
    label = SOURCES[src["source"]][3]
    left = f" {src['left']}m" if src["left"] is not None else ""
    return f"{src['owner']}'s {label}{left}: bright {src['bright']} ft, dim {src['bright'] + src['dim']} ft"


def lit_by(src, dist):
    """The light a source gives at `dist` feet (None = no positions: assume in its bright radius)."""
    if dist is None or dist <= src["bright"]:
        return "bright"
    if dist <= src["bright"] + src["dim"]:
        return "dim"
    return "dark"


def level_for(doc, ambient, docs, distance=None):
    """Effective light for `doc`: the ambient light or the best source carried by the
    group (`docs`), whichever is brighter. `distance(carrier_doc, doc)` gives feet
    between the two in combat/Stage, or None when either has no position."""
    level = str(ambient or "bright").lower()
    for s in carried(docs):
        dist = distance(s["doc"], doc) if distance else None
        level = brighter(level, lit_by(s, dist))
    return level
