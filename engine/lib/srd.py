"""SRD 5.1 lookups from `data/srd/` (docs/design/06 → `gm.py srd`; plan.md Phase 4 item 5).

The data is downloaded once by `engine/fetch_srd.py` (5e-bits `5e-database`, CC-BY-4.0
SRD content; see data/srd/LICENSE.md). Nothing here touches the network, and monster
numbers always come from this data, never from model memory.

`monster(name)` returns a `Monster` with the numbers lib/creatures.py needs (scores,
proficiency, save and skill bonuses, AC, HP, passive Perception, attacks as Attacks-table
rows, damage traits, size, xp) and `block()` lines for `gm.py srd monster`.
"""
import json
import re
from pathlib import Path

from .errors import ToolError

DATA = Path(__file__).resolve().parents[2] / "data" / "srd"
ABBR = ("str", "dex", "con", "int", "wis", "cha")
FULL = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
SIZE = {"tiny": "T", "small": "S", "medium": "M", "large": "L", "huge": "H", "gargantuan": "G"}

_cache = {}


class SrdError(ToolError):
    pass


class SrdMissing(SrdError):
    """The data file isn't downloaded."""


def _load(thing):
    if thing not in _cache:
        p = DATA / f"5e-SRD-{thing}.json"
        if not p.exists():
            raise SrdMissing(f"SRD data missing: {p.name} — run `python engine/fetch_srd.py` once")
        _cache[thing] = json.loads(p.read_text(encoding="utf-8"))
    return _cache[thing]


def available():
    return (DATA / "5e-SRD-Monsters.json").exists()


def _key(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def find(thing, name):
    """The record whose index/name matches exactly, else a unique prefix."""
    want = _key(re.sub(r"^srd:\s*", "", str(name), flags=re.I))
    if not want:
        raise SrdError(f"srd {thing.lower()}: no name given")
    rows = _load(thing)
    exact = [r for r in rows if r["index"] == want or _key(r["name"]) == want]
    if exact:
        return exact[0]
    pre = [r for r in rows if r["index"].startswith(want)]
    if len(pre) == 1:
        return pre[0]
    if pre:
        names = ", ".join(r["name"] for r in pre[:8]) + (" …" if len(pre) > 8 else "")
        raise SrdError(f"srd: {name!r} is ambiguous: {names}")
    raise SrdError(f"srd: no {thing.lower().rstrip('s')} named {name!r}")


def _mod(score):
    return (int(score) - 10) // 2


def _sign(n):
    return f"+{n}" if n >= 0 else str(n)


class Monster:
    def __init__(self, rec):
        self.rec = rec
        self.name = rec["name"]
        self.index = rec["index"]
        self.scores = {a: int(rec[f]) for a, f in zip(ABBR, FULL)}
        self.prof = int(rec.get("proficiency_bonus") or 2)
        self.saves, self.skills = {}, {}
        for p in rec.get("proficiencies", []):
            idx = p["proficiency"]["index"]
            if idx.startswith("saving-throw-"):
                self.saves[idx.rsplit("-", 1)[1]] = int(p["value"])
            elif idx.startswith("skill-"):
                self.skills[idx[len("skill-"):]] = int(p["value"])
        ac = rec.get("armor_class") or [{"value": 10}]
        self.ac = int(ac[0]["value"])
        self.ac_note = ac[0].get("type", "")
        self.hp = int(rec["hit_points"])
        self.hp_roll = rec.get("hit_points_roll") or rec.get("hit_dice", "")
        self.size = SIZE.get(str(rec.get("size", "medium")).lower(), "M")
        self.speed = rec.get("speed") or {}
        self.senses = rec.get("senses") or {}
        self.xp = int(rec.get("xp") or 0)
        self.cr = rec.get("challenge_rating")
        self.resist = [str(x) for x in rec.get("damage_resistances") or []]
        self.immune = [str(x) for x in rec.get("damage_immunities") or []]
        self.vuln = [str(x) for x in rec.get("damage_vulnerabilities") or []]

    # -- numbers (lib/creatures.py) --
    def mod(self, ab):
        return _mod(self.scores[ab])

    def save_bonus(self, ab):
        return self.saves.get(ab, self.mod(ab))

    def passive_perception(self):
        v = self.senses.get("passive_perception")
        return int(v) if v is not None else 10 + self.skills.get("perception", self.mod("wis"))

    def darkvision(self):
        return bool(self.senses.get("darkvision"))

    def attacks(self):
        """Attacks-table rows: {name, hit, damage, range, notes} for every action with an
        attack bonus (damage `1d6+3 slashing`; extra damage parts joined with ' + ')."""
        out = []
        for a in self.rec.get("actions", []):
            if a.get("attack_bonus") is None:
                continue
            parts = []
            for d in a.get("damage", []):
                if "damage_dice" in d:
                    parts.append(f"{d['damage_dice']} {d.get('damage_type', {}).get('name', '').lower()}".strip())
                elif d.get("from"):  # a choice (versatile): take the first option
                    opt = d["from"].get("options", [{}])[0]
                    if "damage_dice" in opt:
                        parts.append(f"{opt['damage_dice']} {opt.get('damage_type', {}).get('name', '').lower()}".strip())
            desc = a.get("desc", "")
            rng = re.search(r"range (\d+)/(\d+) ft", desc)
            reach = re.search(r"reach (\d+) ft", desc)
            if rng:
                where = f"{rng.group(1)}/{rng.group(2)}"
            elif reach:
                where = reach.group(1)
            else:
                where = ""
            out.append({"name": a["name"].lower(), "hit": _sign(int(a["attack_bonus"])),
                        "damage": " + ".join(parts), "range": where, "notes": ""})
        return out

    def reach(self):
        """Longest melee reach in ft (5 when none says)."""
        best = 5
        for a in self.rec.get("actions", []):
            m = re.search(r"reach (\d+) ft", a.get("desc", ""))
            if m:
                best = max(best, int(m.group(1)))
        return best

    # -- display --
    def block(self):
        r = self.rec
        sub = f" ({r['subtype']})" if r.get("subtype") else ""
        cr = self.cr
        cr_txt = {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, f"{cr:g}" if isinstance(cr, (int, float)) else str(cr))
        speed = ", ".join(f"{k} {v}".replace("walk ", "").replace(" ft.", " ft") for k, v in self.speed.items()
                          if k != "hover")
        lines = [f"[SRD {self.name}] {r.get('size')} {r.get('type')}{sub} · CR {cr_txt} ({self.xp:,} XP) · "
                 f"AC {self.ac}" + (f" ({self.ac_note})" if self.ac_note and self.ac_note != "dex" else "") +
                 f" · HP {self.hp} ({self.hp_roll}) · speed {speed or '—'}"]
        mods = " ".join(f"{a.upper()} {_sign(self.mod(a))}" for a in ABBR)
        bits = [mods]
        if self.saves:
            bits.append("saves " + " ".join(f"{a.upper()} {_sign(v)}" for a, v in self.saves.items()))
        if self.skills:
            bits.append("skills " + " ".join(f"{k} {_sign(v)}" for k, v in self.skills.items()))
        senses = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in self.senses.items())
        if senses:
            bits.append("senses " + senses)
        lines.append(" · ".join(bits))
        traits = []
        if self.resist:
            traits.append("resist " + ", ".join(self.resist))
        if self.immune:
            traits.append("immune " + ", ".join(self.immune))
        if self.vuln:
            traits.append("vulnerable " + ", ".join(self.vuln))
        ci = [c.get("name", "") for c in r.get("condition_immunities") or []]
        if ci:
            traits.append("condition immune " + ", ".join(ci))
        if traits:
            lines.append("Defenses: " + " · ".join(traits))
        specials = [s["name"] for s in r.get("special_abilities", [])]
        if specials:
            lines.append("Traits: " + " · ".join(specials))
        acts = []
        attacks = {a["name"]: a for a in self.attacks()}
        for a in r.get("actions", []):
            row = attacks.get(a["name"].lower())
            if row:
                rng = f", range {row['range']}" if "/" in row["range"] else (
                    f", reach {row['range']}" if row["range"] and row["range"] != "5" else "")
                acts.append(f"{a['name']} {row['hit']}, {row['damage'] or 'no damage'}{rng}")
            elif a.get("dc"):
                dc = a["dc"]
                acts.append(f"{a['name']} (DC {dc.get('dc_value')} {dc.get('dc_type', {}).get('name', '')} save)")
            else:
                acts.append(a["name"])
        if acts:
            lines.append("Actions: " + " · ".join(acts))
        for key, label in (("legendary_actions", "Legendary"), ("reactions", "Reactions")):
            names = [x["name"] for x in r.get(key) or []]
            if names:
                lines.append(f"{label}: " + " · ".join(names))
        return lines


def monster(name):
    """A custom monster from the active campaign's custom-bestiary (lib/bestiary.py) when
    one matches, else the SRD record."""
    from . import bestiary
    custom = bestiary.load(name)
    if custom is not None:
        return custom
    return Monster(find("Monsters", name))


def spell(name):
    r = find("Spells", name)
    lvl = "cantrip" if r.get("level") == 0 else f"level {r.get('level')}"
    school = r.get("school", {}).get("name", "")
    comps = ", ".join(r.get("components", [])) + (f" ({r['material']})" if r.get("material") else "")
    head = (f"[SRD {r['name']}] {lvl} {school.lower()} · {r.get('casting_time')} · range {r.get('range')} · "
            f"{comps} · {r.get('duration')}" + (" (concentration)" if r.get("concentration") else "")
            + (" · ritual" if r.get("ritual") else ""))
    lines = [head]
    if r.get("dc"):
        lines.append(f"Save: {r['dc'].get('dc_type', {}).get('name', '')} ({r['dc'].get('dc_success', '')} on success)")
    if r.get("attack_type"):
        lines.append(f"Attack: {r['attack_type']} spell attack")
    dmgs = r.get("damage") or []
    for dmg in dmgs if isinstance(dmgs, list) else [dmgs]:
        by = dmg.get("damage_at_slot_level") or dmg.get("damage_at_character_level") or {}
        if by:
            steps = " · ".join(f"{k}: {v}" for k, v in sorted(by.items(), key=lambda kv: int(kv[0])))
            kind = "slot level" if "damage_at_slot_level" in dmg else "character level"
            lines.append(f"Damage ({dmg.get('damage_type', {}).get('name', '').lower()}, by {kind}): {steps}")
    lines += [d for d in r.get("desc", [])]
    if r.get("higher_level"):
        lines.append("Higher levels: " + " ".join(r["higher_level"]))
    return lines


def condition(name):
    r = find("Conditions", name)
    return [f"[SRD {r['name']}]"] + [str(d) for d in r.get("desc", [])]
