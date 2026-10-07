"""Creature numbers for atk/save/check/contest and the mutations (docs/design/06 L120-121,
L137-154; docs/design/04 → PC file L352-424, NPC file L312-350 incl. custom stat blocks
L349-350, Combat block L507-538; plan.md Phase 2 items 4-5).

`get(name)` resolves a creature (06 L55-58) and wraps it: its file Doc (PC/NPC), its
Combatants row (when in combat) or Stage row (positions only). Numbers come from:
- a PC file (Attacks table, `scores`/`prof`/`saves`/`skills`, `ac`, `hp`), or
- an NPC file whose `statblock:` is `custom…` (same frontmatter + `## Attacks`), or
- the SRD stat block (lib/srd.py) named by `ref: srd:<monster>` or an NPC file's
  `statblock: <monster>` (Phase 4), or
- the Combatants row (`HP`, `AC`) for hit points and armour class.
An NPC file's own `## Attacks` table wins over the SRD actions (`srd --write` fills it).
SrdNotBuilt is raised only when the SRD data isn't downloaded (engine/fetch_srd.py);
numbers are never invented here.
"""
import re
from pathlib import Path

from . import campaign, md, srd
from .errors import ToolError

ABILITIES = {"str": "str", "strength": "str", "dex": "dex", "dexterity": "dex",
             "con": "con", "constitution": "con", "int": "int", "intelligence": "int",
             "wis": "wis", "wisdom": "wis", "cha": "cha", "charisma": "cha"}
SKILLS = {
    "acrobatics": "dex", "animal-handling": "wis", "arcana": "int", "athletics": "str",
    "deception": "cha", "history": "int", "insight": "wis", "intimidation": "cha",
    "investigation": "int", "medicine": "wis", "nature": "int", "perception": "wis",
    "performance": "cha", "persuasion": "cha", "religion": "int",
    "sleight-of-hand": "dex", "stealth": "dex", "survival": "wis",
}
GROUP = re.compile(r"^(.*?)\s*[×x]\s*(\d+)$")
_HP = re.compile(r"^\s*(\d+)\s*/\s*(\d+)(\s*ea)?(?:\s*\(\+(\d+) temp\))?\s*$", re.I)


class SrdNotBuilt(ToolError):
    pass


class CreatureError(ToolError):
    pass


def norm_name(text):
    return re.sub(r"\s*\(PC\)", "", text or "", flags=re.I).strip()


def parse_hp_cell(cell):
    """'9/11' | '7/11 ea' | '9/11 (+5 temp)' -> (cur, max, temp, each) or None."""
    m = _HP.match(cell or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(4) or 0), bool(m.group(3))


def fmt_hp_cell(cur, mx, temp=0, each=False):
    return f"{cur}/{mx}" + (" ea" if each else "") + (f" (+{temp} temp)" if temp else "")


def skill_key(text):
    return re.sub(r"[\s_]+", "-", text.strip().lower())


class Creature:
    def __init__(self, match, state):
        self.match = match
        self.state = state
        self.name = match.name
        self.kind = match.kind
        self.file_ref = _file_ref(match)
        self.combat_index = self._find(state.table("Combatants"))
        self.stage_index = self._find(state.table("Stage"))
        self.combat_row = state.table("Combatants").rows[self.combat_index] if self.combat_index >= 0 else None
        self.stage_row = state.table("Stage").rows[self.stage_index] if self.stage_index >= 0 else None
        row = self.combat_row or self.stage_row
        if row is not None:
            self.name = norm_name(row.get("name"))  # in the scene, the row's name is shown
        self._doc = None
        self._doc_loaded = False
        self._monster = False  # not looked up yet

    def _find(self, table):
        """Index of this creature's row: same display name, or a `ref` pointing at
        the file the name resolved to (`Kael Ashford` → ref pcs/kael-ashford). -1."""
        if table is None:
            return -1
        for i, row in enumerate(table.rows):
            if norm_name(row.get("name")).lower() == self.name.lower():
                return i
        if self.file_ref:
            for i, row in enumerate(table.rows):
                ref = row.get("ref", "").strip().lower()
                if ref.endswith(".md"):
                    ref = ref[:-3]
                if ref and ref == self.file_ref:
                    return i
        return -1

    def combat_table(self):
        """The Combatants Table of `self.state` (edits go to the same Doc)."""
        return self.state.table("Combatants")

    # -- identity --
    @property
    def ref(self):
        row = self.combat_row or self.stage_row
        return (row or {}).get("ref", "").strip()

    @property
    def doc(self):
        """The PC/NPC file, or None (an srd:-only combat row, a group)."""
        if not self._doc_loaded:
            self._doc_loaded = True
            ref = self.ref
            if ref and not ref.lower().startswith("srd:"):
                p = campaign.root() / (ref if ref.endswith(".md") else ref + ".md")
                if p.exists():
                    self._doc = md.load(p)
            if self._doc is None and not ref.lower().startswith("srd:"):
                try:
                    self._doc = self.match.doc
                except campaign.CampaignError:
                    self._doc = None
        return self._doc

    @property
    def is_pc(self):
        row = self.combat_row or self.stage_row
        if row and ("(pc)" in row.get("name", "").lower() or self.ref.lower().startswith("pcs/")):
            return True
        if self.match.is_pc:
            return True
        d = self.doc
        return bool(d) and Path(d.path).parent.name == "pcs"

    @property
    def front(self):
        return self.doc.front if self.doc else {}

    @property
    def pos(self):
        row = self.combat_row or self.stage_row
        if row and row.get("pos"):
            try:
                return md.parse_point(row["pos"])
            except ValueError:
                return None
        return None

    @property
    def side(self):
        row = self.combat_row or self.stage_row
        if row and row.get("side"):
            return row["side"].strip().lower()
        return "party" if self.is_pc else "npc"

    # -- numbers --
    def srd_name(self):
        """The SRD monster this creature's numbers come from, or None (PC, custom block)."""
        if self.ref.lower().startswith("srd:"):
            return self.ref.split(":", 1)[1].strip()
        if self.is_pc or self.doc is None:
            return None
        sb = str(self.front.get("statblock") or "").strip()
        if not sb or sb.lower().startswith("custom"):
            return None
        return sb

    @property
    def monster(self):
        """The lib/srd Monster, or None. Raises SrdNotBuilt when the data is missing."""
        if self._monster is False:
            name = self.srd_name()
            if name is None:
                self._monster = None
            else:
                try:
                    self._monster = srd.monster(name)
                except srd.SrdMissing as e:
                    raise SrdNotBuilt(f"{self.name}: {e}") from None
                except srd.SrdError as e:
                    raise CreatureError(f"{self.name}: {e}") from None
        return self._monster

    def _srd_only(self):
        """True when numbers come from the SRD block (no own scores in the file)."""
        return self.monster is not None and "scores" not in self.front

    def require_numbers(self):
        """PCs, custom-statblock NPCs and SRD creatures have numbers."""
        if self.is_pc and self.doc is not None:
            return
        if self.monster is not None:
            return
        if self.doc is None:
            raise CreatureError(f"{self.name}: no PC/NPC file to read numbers from")
        sb = str(self.front.get("statblock") or "").strip()
        if sb.lower().startswith("custom"):
            return
        raise CreatureError(f"{self.name}: no statblock in {Path(self.doc.path).name}")

    def _need(self, key):
        self.require_numbers()
        if key not in self.front or self.front[key] in (None, ""):
            raise CreatureError(f"{self.name}: no `{key}` in {Path(self.doc.path).name}")
        return self.front[key]

    def mod(self, ability):
        ab = ABILITIES.get(ability.lower())
        if not ab:
            raise CreatureError(f"unknown ability {ability!r}")
        self.require_numbers()
        if self._srd_only():
            return self.monster.mod(ab)
        scores = self._need("scores")
        if not isinstance(scores, dict) or ab not in scores:
            raise CreatureError(f"{self.name}: no {ab} score")
        return (int(scores[ab]) - 10) // 2

    def prof(self):
        self.require_numbers()
        if self._srd_only():
            return self.monster.prof
        return int(self._need("prof"))

    def save_bonus(self, ability):
        ab = ABILITIES.get(ability.lower())
        if not ab:
            raise CreatureError(f"unknown ability {ability!r} (str dex con int wis cha)")
        self.require_numbers()
        if self._srd_only():
            return self.monster.save_bonus(ab)
        saves = [str(s).lower() for s in (self.front.get("saves") or [])]
        return self.mod(ab) + (self.prof() if ab in saves else 0) + self._magic("saves")

    def _magic(self, key, attack=None):
        """An equipped (and attuned) magic item's bonus (lib/magic.py, Phase 15); 0 for a
        creature without a file or with the value in `overrides`."""
        if self.doc is None or key in (self.front.get("overrides") or {}):
            return 0
        from . import magic
        return magic.bonus(self.doc, key, attack)

    def skill_bonus(self, skill):
        """Skill total from `skills`, else its ability mod; a bare ability is an
        ability check."""
        key = skill_key(skill)
        if key in ABILITIES:
            return self.mod(key)
        if key not in SKILLS:
            raise CreatureError(f"unknown skill {skill!r}")
        self.require_numbers()
        if self._srd_only():
            return self.monster.skills.get(key, self.mod(SKILLS[key]))
        skills = self.front.get("skills") or {}
        if isinstance(skills, dict):
            for k, v in skills.items():
                if skill_key(k) == key:
                    return int(v)
        return self.mod(SKILLS[key])

    def passive(self, skill):
        key = skill_key(skill)
        self.require_numbers()
        v = self.front.get(f"passive-{key}")
        if isinstance(v, int):
            return v
        if key == "perception" and self._srd_only():
            return self.monster.passive_perception()
        return 10 + self.skill_bonus(key)

    def ac(self):
        if self.combat_row and self.combat_row.get("ac", "").strip().isdigit():
            return int(self.combat_row["ac"])
        self.require_numbers()
        if self.monster is not None and "ac" not in self.front:
            return self.monster.ac
        return int(self._need("ac")) + self._magic("ac")

    def max_hp(self):
        """Max HP from the file's `hp`, else the SRD average."""
        hp = self.front.get("hp")
        if isinstance(hp, dict) and hp.get("max") is not None:
            return int(hp["max"])
        self.require_numbers()
        if self.monster is not None:
            return self.monster.hp
        raise CreatureError(f"{self.name}: no `hp` in {Path(self.doc.path).name}")

    def exhaustion(self):
        """Exhaustion level 0–6: the file's `exhaustion:`, else a Combatants row's `exh N`."""
        v = self.front.get("exhaustion")
        if isinstance(v, int):
            return max(0, min(6, v))
        row = self.combat_row or {}
        m = re.search(r"(?:^|,)\s*exh\s+(\d)", row.get("conditions", "") or "")
        return int(m.group(1)) if m else 0

    def size(self):
        """T/S/M/L/H/G from the file's `size`, the SRD block, else M."""
        s = str(self.front.get("size") or "").strip()[:1].upper()
        if s in ("T", "S", "M", "L", "H", "G"):
            return s
        try:
            if self.monster is not None:
                return self.monster.size
        except (SrdNotBuilt, CreatureError):
            pass
        return "M"

    def damage_traits(self):
        """(resist, immune, vuln) lists from the file, else the SRD block's."""
        try:
            m = self.monster
        except (SrdNotBuilt, CreatureError):
            m = None
        own = any(k in self.front for k in ("resistances", "immunities", "vulnerabilities"))
        if m is not None and not own:
            return list(m.resist), list(m.immune), list(m.vuln)
        if self.doc is None:
            return [], [], []
        f = self.front
        as_list = lambda v: v if isinstance(v, list) else ([v] if v else [])  # noqa: E731
        return (as_list(f.get("resistances")), as_list(f.get("immunities")),
                as_list(f.get("vulnerabilities")))

    def attack(self, name=None):
        """The Attacks-table row to use: `name` by prefix, else the first row with a
        to-hit bonus. -> dict(name, hit, damage, dtype, range, notes)."""
        self.require_numbers()
        table = self.doc.table("Attacks") if self.doc is not None else None
        if table is not None and table.rows:
            rows = table.rows
        elif self.monster is not None:
            rows = self.monster.attacks()
        else:
            raise CreatureError(f"{self.name}: no ## Attacks table")
        if name:
            want = name.strip().lower()
            hits = [r for r in rows if r.get("name", "").lower() == want] or \
                   [r for r in rows if r.get("name", "").lower().startswith(want)]
            if not hits:
                raise CreatureError(f"{self.name} has no attack {name!r} "
                                    f"({', '.join(r.get('name', '') for r in rows)})")
            if len(hits) > 1:
                raise CreatureError(f"attack {name!r} is ambiguous: "
                                    f"{', '.join(r['name'] for r in hits)}")
            row = hits[0]
        else:
            row = next((r for r in rows if re.fullmatch(r"[+-]\d+", r.get("hit", "").strip())), None)
            if row is None:
                raise CreatureError(f"{self.name}: no attack with a to-hit bonus")
        hit = row.get("hit", "").strip()
        if not re.fullmatch(r"[+-]\d+", hit):
            raise CreatureError(f"{row.get('name')}: '{hit}' is not an attack roll "
                                "(a save-based attack: use `save`)")
        m = re.match(r"^\s*((?:\d*d\d+|\d+)(?:\s*[+-]\s*(?:\d*d\d+|\d+))*)\s*(.*)$",
                     row.get("damage", ""), re.I)
        if not m:
            raise CreatureError(f"{row.get('name')}: can't read damage {row.get('damage')!r}")
        damage = m.group(1).replace(" ", "")
        plus_hit, plus_dmg = self._magic("attack", row.get("name", "")), self._magic("damage", row.get("name", ""))
        if plus_dmg:   # a magic weapon's bonus (Phase 15)
            damage += f"{plus_dmg:+d}"
        return {"name": row.get("name", ""), "hit": int(hit) + plus_hit, "damage": damage,
                "dtype": (m.group(2) or "").strip(), "range": row.get("range", "").strip(),
                "notes": row.get("notes", "")}


def _file_ref(match):
    """`pcs/kael-ashford` for a match that resolved to a file, else None."""
    p = match.path
    if not p:
        return None
    try:
        rel = Path(p).resolve().relative_to(campaign.root())
    except ValueError:
        return None
    return rel.with_suffix("").as_posix().lower()


def get(name, state=None):
    state = state or campaign.load_state()
    return Creature(campaign.resolve(name, state), state)
