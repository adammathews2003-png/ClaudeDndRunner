"""Carried weight and encumbrance (docs/design/02 → Table mechanics → Phase 15 →
Encumbrance; 04 → PC file, Added by Phases 13–15 (Weight); 06 → Table mechanics → Phase 15).

Weights come from the SRD equipment data (lib/chargen.equipment_record; a bundle such as
`Arrow` weighs its `weight` per `quantity`), a custom entry may say `(5 lb)`, and coins
weigh a pound per 50. Entries are the `## Inventory` text the other tools already read:
`2 daggers`, `quiver (20 arrows)`, `torches (4)`, `5 days rations`, `shortbow + quiver
(20 arrows)`. An entry the data doesn't know weighs nothing and is listed as unknown.

`encumbrance: off | basic | variant` (default off):
- basic: over STR × 15 lb (the carrying capacity) the speed drops to 5 ft.
- variant: over STR × 5 lb, −10 ft speed (`[enc]`); over STR × 10 lb, −20 ft and
  disadvantage on attack rolls and on STR, DEX and CON checks and saves (`[heavy]`).
"""
import re

from . import campaign

COINS_PER_LB = 50
ALIASES = {
    "silk rope": "rope-silk-50-feet", "rope": "rope-hempen-50-feet", "hempen rope": "rope-hempen-50-feet",
    "hooded lantern": "lantern-hooded", "lantern": "lantern-hooded", "bullseye lantern": "lantern-bullseye",
    "flask of oil": "oil-flask", "oil": "oil-flask", "ration": "rations-1-day", "rations": "rations-1-day",
    "day rations": "rations-1-day", "days rations": "rations-1-day",
}
_LB = re.compile(r"\((\d+(?:\.\d+)?)\s*lbs?\)", re.I)


def mode():
    return str(campaign.settings().get("encumbrance", "off")).strip().lower()


def _record(name):
    from . import chargen
    key = re.sub(r"\s+", " ", re.sub(r"^\d+\s*ft\s+", "", name.strip().lower()))
    key = re.sub(r"\s*\(.*$", "", key).strip()
    sing = " ".join(w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 3 else w for w in key.split())
    for k in (key, sing):
        if k in ALIASES:
            return chargen._by_index("Equipment").get(ALIASES[k])
    try:
        return chargen.equipment_record(key)
    except Exception:  # noqa: BLE001 — no SRD data: nothing is weighed
        return None


def _each(name):
    """Pounds for one of `name`, or None when unknown."""
    rec = _record(name)
    if rec is None or rec.get("weight") is None:
        return None
    return float(rec["weight"]) / float(rec.get("quantity") or 1)


def entry_weight(text):
    """(pounds, [unknown names]) for one inventory entry."""
    from . import magic
    text = magic.public(text).strip()
    text = re.sub(r"^unidentified\s*:\s*", "", text, flags=re.I)
    parts = [p.strip() for p in re.split(r"\s\+\s", text) if p.strip()]
    total, unknown = 0.0, []
    for part in parts:
        lead = re.match(r"^(\d+)\s+(?!ft\b)(.*)$", part)
        n = int(lead.group(1)) if lead else 1
        body = lead.group(2) if lead else part
        lb = _LB.search(body)
        if lb:
            total += n * float(lb.group(1))
            continue
        paren = re.search(r"\((\d+)(?:\s+([^)]*))?\)", body)
        base = re.sub(r"\([^)]*\)", " ", body).strip()
        base = re.sub(r"^(\d+)\s+days?\s+", "", base) if re.match(r"^\d+\s+days?\s", base) else base
        if paren and paren.group(2) and not re.fullmatch(r"days?", paren.group(2).strip(), re.I):
            # a container with a count of something inside: `quiver (20 arrows)`
            w = _each(base)
            inner = _each(paren.group(2))
            if w is None:
                unknown.append(base)
            else:
                total += n * w
            if inner is None:
                unknown.append(paren.group(2).strip())
            else:
                total += n * int(paren.group(1)) * inner
            continue
        if paren:            # `torches (4)`, `rations (5 days)`
            n *= int(paren.group(1))
        w = _each(base)
        if w is None:
            unknown.append(base)
        else:
            total += n * w
    return total, unknown


def coin_weight(line):
    coins = sum(int(n) for n in re.findall(r"\b(\d+)\s*(?:pp|gp|ep|sp|cp)\b", line, re.I))
    return coins / COINS_PER_LB


def load(doc):
    """(pounds carried, [unknown entries]) from the `## Inventory` section."""
    import inventory
    span = doc.section("Inventory") if doc is not None else None
    if span is None:
        return 0.0, []
    total, unknown = 0.0, []
    for j in range(span[0] + 1, span[1]):
        line = doc.body[j]
        if not line.strip() or line.strip().startswith("<!--"):
            continue
        if re.match(r"^\s*-\s+Coin:", line):
            total += coin_weight(line)
            continue
        _, entries, _ = inventory._split_entries(line)
        for e in entries:
            if re.fullmatch(r"\d+\s*(pp|gp|ep|sp|cp)", e.strip(), re.I):
                total += coin_weight(e)
                continue
            w, unk = entry_weight(e)
            total += w
            unknown += unk
    return round(total, 1), unknown


def strength(doc):
    scores = doc.front.get("scores") if doc is not None else None
    try:
        return int((scores or {}).get("str", 10))
    except (TypeError, ValueError):
        return 10


def status(doc, how=None):
    """{load, cap, level 0|1|2, tag, speed (delta or None), set_speed (or None), dis}
    under `how` (default the table's `encumbrance` setting); level 0 when off."""
    how = how or mode()
    lb, unknown = load(doc)
    s = strength(doc)
    out = {"load": lb, "cap": s * 15, "unknown": unknown, "level": 0, "tag": "", "delta": 0,
           "set_speed": None, "dis": False, "mode": how}
    if how == "basic" and lb > s * 15:
        out.update(level=2, tag="[heavy]", set_speed=5)
    elif how == "variant":
        if lb > s * 10:
            out.update(level=2, tag="[heavy]", delta=-20, dis=True)
        elif lb > s * 5:
            out.update(level=1, tag="[enc]", delta=-10)
    return out


def speed(base, doc):
    """Walking speed after the load (unchanged with `encumbrance: off`)."""
    if doc is None or mode() == "off":
        return base
    st = status(doc)
    if st["set_speed"] is not None:
        return min(base, st["set_speed"])
    return max(0, base + st["delta"])


def disadvantage(doc, kind, ability=None):
    """variant heavy load: disadvantage on attack rolls, and on STR/DEX/CON checks and
    saves. -> note or ''."""
    if doc is None or mode() != "variant":
        return ""
    st = status(doc)
    if not st["dis"]:
        return ""
    if kind == "attack" or (ability or "") in ("str", "dex", "con"):
        return f"heavily encumbered ({st['load']:g} lb): disadvantage"
    return ""
