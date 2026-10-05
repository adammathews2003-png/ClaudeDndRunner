"""Custom monsters ("bestiary") — homebrew stat blocks the tools treat exactly like SRD
monsters (docs/design/04 → Bestiary file; 07 → Custom monsters).

Where they live, searched in this order by `lib/srd.monster()`:
1. `campaigns/<active>/bestiary/<slug>.md` — monsters that belong to one campaign,
2. `bestiary/<slug>.md` at the repo root — shared, reusable homebrew,
3. the SRD 5.1 data.

A bestiary file is markdown: frontmatter with the numbers (`size`, `type`, `ac`, `hp`,
`hp-dice`, `speed`, `scores`, `prof`, `saves` and `skills` as bonus dicts, `senses`,
`passive-perception`, damage/condition lists, `cr`, `xp`, `based-on`) and body sections
`## Traits` (`- **Name.** text`), `## Attacks` (the PC/NPC table: name | hit | damage |
range | notes), `## Actions` (Multiattack and non-attack actions as bullets), `## Reactions`,
`## Description`, `## Backstory`. `CustomMonster` turns it into the same shape as an SRD
record, so `combat`, `atk`, `encounter`, `danger` and `srd monster` need no changes.
"""
import re
from pathlib import Path

from . import campaign, md

SHARED = campaign.BASE / "bestiary"
SIZES = {"T": "Tiny", "S": "Small", "M": "Medium", "L": "Large", "H": "Huge", "G": "Gargantuan"}
ABBR = ("str", "dex", "con", "int", "wis", "cha")
FULL = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def key(text):
    t = str(text or "").lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def folders():
    out = []
    try:
        out.append(campaign.root() / "bestiary")
    except campaign.CampaignError:
        pass
    out.append(SHARED)
    return out


def all_files():
    seen, out = set(), []
    for d in folders():
        for p in sorted(d.glob("*.md")) if d.is_dir() else []:
            if p.stem not in seen:
                seen.add(p.stem)
                out.append(p)
    return out


def find(name):
    """The bestiary file for `name` (slug or `name:`, exact then unique prefix), or None."""
    want = key(re.sub(r"^(srd|monster):\s*", "", str(name), flags=re.I))
    if not want:
        return None
    files = all_files()
    for p in files:
        if p.stem == want:
            return p
    for p in files:
        if key(md.load(p).front.get("name")) == want:
            return p
    pre = [p for p in files if p.stem.startswith(want)]
    return pre[0] if len(pre) == 1 else None


def _bullets(doc, heading):
    """[(name, text)] from `- **Name.** text` bullets (continuation lines joined)."""
    span = doc.section(heading)
    if span is None:
        return []
    out = []
    for line in doc.body[span[0] + 1:span[1]]:
        m = re.match(r"^\s*-\s+\*\*(.+?)\.?\*\*\.?\s*(.*)$", line)
        if m:
            out.append([m.group(1).strip().rstrip("."), m.group(2).strip()])
        elif out and line.strip() and not line.lstrip().startswith(("<!--", "|", "#")):
            out[-1][1] += " " + line.strip()
    return [tuple(x) for x in out]


def _speed(text):
    out = {}
    for part in str(text or "30 ft").split(","):
        m = re.match(r"^\s*(walk|climb|swim|fly|burrow)?\s*(\d+)\s*ft", part.strip(), re.I)
        if m:
            out[(m.group(1) or "walk").lower()] = f"{m.group(2)} ft."
    return out or {"walk": "30 ft."}


def _list(v):
    if v in (None, ""):
        return []
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def to_record(doc):
    """An SRD-shaped record dict from a bestiary Doc."""
    f = doc.front
    scores = f.get("scores") if isinstance(f.get("scores"), dict) else {}
    profs = []
    for ab, v in (f.get("saves") or {}).items() if isinstance(f.get("saves"), dict) else []:
        profs.append({"value": int(v), "proficiency": {"index": f"saving-throw-{ab.lower()[:3]}"}})
    for sk, v in (f.get("skills") or {}).items() if isinstance(f.get("skills"), dict) else []:
        profs.append({"value": int(v), "proficiency": {"index": f"skill-{key(sk)}"}})
    senses = {}
    for s in _list(f.get("senses")):
        m = re.match(r"^\s*([a-z]+)\s+(\d+)", s, re.I)
        if m:
            senses[m.group(1).lower()] = f"{m.group(2)} ft."
    if isinstance(f.get("passive-perception"), int):
        senses["passive_perception"] = f["passive-perception"]
    size = str(f.get("size") or "M").strip()
    actions = [{"name": n, "desc": d} for n, d in _bullets(doc, "Actions")]
    t = doc.table("Attacks")
    for r in (t.rows if t else []):
        dmg = []
        for part in re.split(r"\s+\+\s+", r.get("damage", "")):
            m = re.match(r"^\s*(\d*d\d+(?:\s*[+-]\s*\d+)?|\d+)\s*([a-z]*)", part.strip(), re.I)
            if m:
                dmg.append({"damage_dice": m.group(1).replace(" ", ""), "damage_type": {"name": m.group(2).title()}})
        hit = re.match(r"^\s*([+-]?\d+)", r.get("hit", ""))
        actions.append({"name": r.get("name", "").title(), "desc": r.get("notes", ""),
                        "attack_bonus": int(hit.group(1)) if hit else None, "damage": dmg,
                        "_range": r.get("range", "")})
    rec = {
        "index": Path(doc.path).stem, "name": str(f.get("name") or Path(doc.path).stem),
        "size": SIZES.get(size[:1].upper(), size), "type": str(f.get("type") or "monstrosity"),
        "subtype": f.get("subtype") or "", "armor_class": [{"value": int(f.get("ac") or 10),
                                                            "type": str(f.get("ac-note") or "natural")}],
        "hit_points": int(f.get("hp") or 1), "hit_points_roll": str(f.get("hp-dice") or ""),
        "speed": _speed(f.get("speed")), "proficiencies": profs,
        "damage_resistances": _list(f.get("resistances")), "damage_immunities": _list(f.get("immunities")),
        "damage_vulnerabilities": _list(f.get("vulnerabilities")),
        "condition_immunities": [{"name": c} for c in _list(f.get("condition-immunities"))],
        "senses": senses, "challenge_rating": f.get("cr"), "proficiency_bonus": int(f.get("prof") or 2),
        "xp": int(f.get("xp") or 0),
        "special_abilities": [{"name": n, "desc": d} for n, d in _bullets(doc, "Traits")],
        "actions": actions, "reactions": [{"name": n, "desc": d} for n, d in _bullets(doc, "Reactions")],
    }
    for ab, full in zip(ABBR, FULL):
        rec[full] = int(scores.get(ab, 10))
    return rec


def load(name):
    """A CustomMonster for `name`, or None when no bestiary file matches."""
    p = find(name)
    if p is None:
        return None
    from .srd import Monster

    class CustomMonster(Monster):
        """An SRD-shaped Monster whose attacks come straight from the file's table."""

        def __init__(self, doc):
            super().__init__(to_record(doc))
            self.doc = doc
            self.path = doc.path
            self.custom = True
            self.based_on = doc.front.get("based-on")

        def attacks(self):
            out = []
            for a in self.rec["actions"]:
                if a.get("attack_bonus") is None:
                    continue
                dmg = " + ".join(f"{d['damage_dice']} {d['damage_type']['name'].lower()}".strip()
                                 for d in a.get("damage", []))
                hit = a["attack_bonus"]
                out.append({"name": a["name"].lower(), "hit": f"+{hit}" if hit >= 0 else str(hit),
                            "damage": dmg, "range": a.get("_range", ""), "notes": a.get("desc", "")})
            return out

        def reach(self):
            best = 5
            for a in self.attacks():
                if a["range"].isdigit():
                    best = max(best, int(a["range"]))
            return best

        def block(self):
            lines = Monster.block(self)
            rel = Path(self.path).resolve()
            try:
                rel = rel.relative_to(campaign.BASE)
            except ValueError:
                pass
            lines[0] = lines[0].replace("[SRD ", "[CUSTOM ", 1)
            lines.append(f"Custom: {Path(rel).as_posix()}" + (f" · based on {self.based_on}" if self.based_on else ""))
            return lines

    return CustomMonster(md.load(p))
