"""Character derivation from the SRD 5.1 data (docs/design/06 → Character tools; 02 →
Character intake loop, Level-up flow; 04 → PC file; rules/house-rules.md → HP max or
roll; plan.md Phase 6).

A **draft** is a dict of what the player said (never invented): name, player, race,
class, subclass, level, background, scores (final) or base-scores (before racial
bonuses), ability-bonuses (half-elf picks), skills (chosen class skills),
race-skills (half-elf picks), expertise, fighting-style, cantrips, spells,
hp-method, hp-rolls, equipment, overrides, look, personality, goal, autopilot, …

`derive(draft)` returns a `Sheet`: every computable number (scores, mods, prof, HP,
AC, speed, senses, saves, skill totals, passives, attacks, spell slots/DC/attack,
resources, features) plus the check lists `pending`, `missing`, `defaults`,
`conflicts`, `custom`, and `warnings`. The model never adds up HP or slots; this does.
Checks are warnings, never blocks: player-stated values win (02).
"""
import json
import re
from pathlib import Path

from .errors import ToolError

DATA = Path(__file__).resolve().parents[2] / "data" / "srd"
ABBR = ("str", "dex", "con", "int", "wis", "cha")
FULL = {"str": "Strength", "dex": "Dexterity", "con": "Constitution", "int": "Intelligence",
        "wis": "Wisdom", "cha": "Charisma"}
SUBCLASS_LEVEL = {"cleric": 1, "sorcerer": 1, "warlock": 1, "druid": 2, "wizard": 2}
STANDARD_ARRAY = (15, 14, 13, 12, 10, 8)
POINT_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
# class priority for auto-assigning the standard array (02: "auto-assigned by class")
PRIORITY = {
    "barbarian": "str con dex wis cha int", "bard": "cha dex con wis int str",
    "cleric": "wis con str dex cha int", "druid": "wis con dex int cha str",
    "fighter": "str con dex wis cha int", "monk": "dex wis con str int cha",
    "paladin": "str cha con wis dex int", "ranger": "dex wis con str int cha",
    "rogue": "dex con int wis cha str", "sorcerer": "cha con dex wis int str",
    "warlock": "cha con dex wis int str", "wizard": "int con dex wis cha str",
}
PREPARED = {"cleric": 1, "druid": 1, "wizard": 1, "paladin": 0.5}   # mod + level × factor
# per-level resources from Levels.class_specific (name, key, recovers)
CLASS_RESOURCES = {
    "barbarian": [("rage", "rage_count", "long")],
    "cleric": [("channel divinity", "channel_divinity_charges", "short")],
    "fighter": [("action surge", "action_surges", "short")],
    "monk": [("ki", "ki_points", "short")],
    "sorcerer": [("sorcery points", "sorcery_points", "long")],
}
SUBCLASS_PROFS = {"life": ["heavy-armor"]}
# subclass-choice placeholders in the class tables: not features a player uses
PLACEHOLDERS = {"primal path", "bard college", "divine domain", "druid circle", "martial archetype",
                "monastic tradition", "sacred oath", "ranger archetype", "roguish archetype",
                "sorcerous origin", "otherworldly patron", "arcane tradition", "domain spells",
                "divine domain feature", "oath spells", "circle spells", "expanded spell list",
                "bonus proficiency", "bonus proficiencies"}
_cache = {}


class ChargenError(ToolError):
    pass


# ---------- data ----------

def _load(thing):
    if thing not in _cache:
        p = DATA / f"5e-SRD-{thing}.json"
        if not p.exists():
            raise ChargenError(f"SRD data missing: {p.name} — run `python engine/fetch_srd.py --only "
                               "Classes Subclasses Levels Features Races Subraces Traits Equipment "
                               "Backgrounds Spells Proficiencies Skills`")
        _cache[thing] = json.loads(p.read_text(encoding="utf-8"))
    return _cache[thing]


def key(text):
    t = str(text or "").lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _by_index(thing):
    k = "idx:" + thing
    if k not in _cache:
        _cache[k] = {r["index"]: r for r in _load(thing)}
    return _cache[k]


def find(thing, text):
    """Record by index or name, else a unique prefix; None when not SRD."""
    want = key(text)
    if not want:
        return None
    idx = _by_index(thing)
    if want in idx:
        return idx[want]
    for r in idx.values():
        if key(r["name"]) == want:
            return r
    pre = [r for i, r in idx.items() if i.startswith(want)]
    return pre[0] if len(pre) == 1 else None


def level_rows(cls, level, subclass=None):
    """(class level row, subclass level row or None)."""
    base = sub = None
    for r in _load("Levels"):
        if r.get("level") != level:
            continue
        if r.get("subclass"):
            if subclass and r["subclass"]["index"] == subclass:
                sub = r
        elif r.get("class", {}).get("index") == cls:
            base = r
    return base, sub


def skill_name(idx):
    return idx.replace("skill-", "").replace("-", " ")


SKILL_ABILITY = {
    "acrobatics": "dex", "animal-handling": "wis", "arcana": "int", "athletics": "str",
    "deception": "cha", "history": "int", "insight": "wis", "intimidation": "cha",
    "investigation": "int", "medicine": "wis", "nature": "int", "perception": "wis",
    "performance": "cha", "persuasion": "cha", "religion": "int", "sleight-of-hand": "dex",
    "stealth": "dex", "survival": "wis",
}


def mod(score):
    return (int(score) - 10) // 2


def sign(n):
    return f"+{n}" if n >= 0 else str(n)


def _opts(choice):
    """Option indices of an SRD choice block (flattening nested choices)."""
    out = []
    for o in (choice or {}).get("from", {}).get("options", []):
        if o.get("option_type") == "reference":
            out.append(o["item"]["index"])
        elif o.get("option_type") == "choice":
            out += _opts(o["choice"])
        elif o.get("option_type") == "ability_bonus":
            out.append(o["ability_score"]["index"])
    return out


def as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [s.strip() for s in re.split(r"[;,]", str(v)) if s.strip()]


# ---------- equipment ----------

_QTY = re.compile(r"^\s*(\d+)\s*(?:x\s*)?(.+)$", re.I)


def parse_item(text):
    """'4 javelins' → (4, 'javelins'); 'shortbow + quiver (20 arrows)' kept whole."""
    m = _QTY.match(text.strip())
    if m:
        return int(m.group(1)), m.group(2).strip()
    return 1, text.strip()


def equipment_record(name):
    """SRD equipment for a free-text item name, or None."""
    idx = _by_index("Equipment")
    k = key(name)
    cands = [k, k.rstrip("s"), re.sub(r"es$", "", k), k + "-armor", k.rstrip("s") + "-armor"]
    for c in cands:
        if c in idx:
            return idx[c]
    for r in idx.values():
        if key(r["name"]) in cands:
            return r
    # a leading SRD name inside longer text: "shield bearing Chauntea's sheaf" → shield
    words = k.split("-")
    for n in range(min(4, len(words)), 0, -1):
        head = "-".join(words[:n])
        for c in (head, head.rstrip("s"), head + "-armor"):
            if c in idx and not c.startswith("barding"):
                return idx[c]
    return None


# ---------- the sheet ----------

class Sheet:
    def __init__(self):
        self.fields = {}       # derived values written to the PC file
        self.derived = []      # DERIVED lines (text)
        self.pending = []
        self.missing = []
        self.defaults = []
        self.conflicts = []
        self.custom = []
        self.warnings = []
        self.attacks = []      # Attacks rows
        self.resources = []    # Resources rows
        self.spells = []       # Spells rows
        self.features = []     # feature names (class/subclass/race)
        self.inventory = []    # (name, qty, record or None)


def derive(draft):
    s = Sheet()
    ov = draft.get("overrides") or {}
    lvl = _int(draft.get("level"))
    if not lvl:
        s.missing.append("level")
        lvl = 1
    s.fields["level"] = lvl
    prof = 2 + (lvl - 1) // 4
    s.fields["prof"] = prof

    # race / subrace
    race_txt = str(draft.get("race") or "").strip()
    race = sub = None
    if not race_txt:
        s.missing.append("race")
    else:
        sub = find("Subraces", race_txt)
        if sub is not None:
            race = _by_index("Races")[sub["race"]["index"]]
        else:
            race = find("Races", race_txt)
            if race is None:
                s.custom.append(f"race {race_txt!r} (not SRD): traits come from the player's summary")
            elif race.get("subraces"):
                names = ", ".join(x["name"] for x in race["subraces"])
                s.missing.append(f"subrace for {race['name']} ({names})")

    # class / subclass
    cls_txt = str(draft.get("class") or "").strip()
    cls = find("Classes", cls_txt) if cls_txt else None
    if not cls_txt:
        s.missing.append("class")
    elif cls is None:
        s.custom.append(f"class {cls_txt!r} (not SRD): the tools carry it, they don't derive it")
    ci = cls["index"] if cls else None
    sub_txt = str(draft.get("subclass") or "").strip()
    subcls = None
    if cls:
        need_at = SUBCLASS_LEVEL.get(ci, 3)
        if sub_txt:
            subcls = next((x for x in _load("Subclasses") if x["class"]["index"] == ci and
                           (key(sub_txt) in (x["index"], key(x["name"])) or key(x["name"]) in key(sub_txt)
                            or x["index"] in key(sub_txt))), None)
            if subcls is None:
                s.custom.append(f"subclass {sub_txt!r} (not SRD): summarize its features at this level")
            if lvl < need_at:
                s.warnings.append(f"subclass given before level {need_at} ({cls['name']} chooses it then)")
        elif lvl >= need_at:
            opts = [x["name"] for x in _load("Subclasses") if x["class"]["index"] == ci]
            s.missing.append(f"subclass ({cls['name']} chooses at level {need_at}; SRD: "
                             f"{', '.join(opts)}; any other is custom)")
    si = subcls["index"] if subcls else None

    # scores
    racial = {}
    if race:
        for b in race.get("ability_bonuses", []):
            racial[b["ability_score"]["index"]] = racial.get(b["ability_score"]["index"], 0) + b["bonus"]
    if sub:
        for b in sub.get("ability_bonuses", []):
            racial[b["ability_score"]["index"]] = racial.get(b["ability_score"]["index"], 0) + b["bonus"]
    if race and race.get("ability_bonus_options"):
        n = race["ability_bonus_options"]["choose"]
        picks = [p.lower()[:3] for p in as_list(draft.get("ability-bonuses"))]
        if len(picks) != n:
            s.missing.append(f"{race['name']}: +1 to {n} abilities of your choice (not CHA)")
        for p in picks[:n]:
            racial[p] = racial.get(p, 0) + 1
    scores = None
    base = draft.get("base-scores")
    if isinstance(draft.get("scores"), dict) and draft["scores"]:
        scores = {a: int(draft["scores"].get(a, 10)) for a in ABBR}
        base_guess = {a: scores[a] - racial.get(a, 0) for a in ABBR}
        _check_scores(s, base_guess, stated_final=True)
    elif isinstance(base, dict) and base:
        b = {a: int(base.get(a, 10)) for a in ABBR}
        _check_scores(s, b, stated_final=False)
        scores = {a: b[a] + racial.get(a, 0) for a in ABBR}
    else:
        order = PRIORITY.get(ci, "str dex con int wis cha").split()
        arr = dict(zip(order, STANDARD_ARRAY))
        fin = {a: arr[a] + racial.get(a, 0) for a in ABBR}
        shown = " ".join(f"{a.upper()} {arr[a]}" for a in order)
        bumped = ", ".join(f"{a.upper()} {fin[a]}" for a in order if racial.get(a))
        s.missing.append("ability scores (offer: standard array → " + shown + " before racial bonuses"
                         + (f", so {bumped}" if bumped else "") + " · point buy · roll 4d6 drop lowest)")
    for asi in as_list(draft.get("asi")):
        if scores is None:
            break
        for part in re.split(r"\s+", asi.replace(",", " ")):
            m = re.match(r"^(str|dex|con|int|wis|cha)\s*\+\s*(\d)$", part.strip().lower())
            if m:
                scores[m.group(1)] = min(20, scores[m.group(1)] + int(m.group(2)))
    if scores:
        s.fields["scores"] = scores
    mods = {a: mod(scores[a]) for a in ABBR} if scores else None

    # proficiencies
    profs = set()
    if cls:
        profs |= {p["index"] for p in cls.get("proficiencies", [])}
    if si:
        profs |= set(SUBCLASS_PROFS.get(si, []))
    traits = []
    if race:
        traits += [t["index"] for t in race.get("traits", [])]
        profs |= {p["index"] for p in race.get("starting_proficiencies", [])}
    if sub:
        traits += [t["index"] for t in sub.get("racial_traits", [])]
        profs |= {p["index"] for p in sub.get("starting_proficiencies", [])}
    T = _by_index("Traits")
    for t in traits:
        rec = T.get(t)
        if rec:
            profs |= {p["index"] for p in rec.get("proficiencies", [])}
    bg_txt = str(draft.get("background") or "").strip()
    bg = find("Backgrounds", bg_txt) if bg_txt else None
    if bg:
        profs |= {p["index"] for p in bg.get("starting_proficiencies", [])}
    elif bg_txt:
        s.custom.append(f"background {bg_txt!r} (not SRD): its skills/equipment come from the player")
    else:
        s.defaults.append("background: none given → skills/equipment from background skipped (OK?)")

    # class skills
    chosen = [key(x) for x in as_list(draft.get("skills"))]
    known_profs = [key(x) for x in as_list(draft.get("skill-profs"))]   # inferred from a PC file
    profs |= {f"skill-{x}" for x in known_profs}
    if cls and cls.get("proficiency_choices"):
        pc = next((c for c in cls["proficiency_choices"] if any(o.startswith("skill-") for o in _opts(c))),
                  None)
        if pc:
            n = pc["choose"]
            opts = [o for o in _opts(pc) if o.startswith("skill-")]
            names = [skill_name(o).title() for o in opts]
            good = [c for c in chosen if f"skill-{c}" in opts]
            have = set(good) | {x for x in known_profs if f"skill-{x}" in opts}
            if len(have) < n:
                s.missing.append(f"{n} {cls['name'].lower()} skills from: {', '.join(names)}"
                                 + (f" (have {len(have)})" if have else ""))
            for c in chosen:
                if f"skill-{c}" not in opts:
                    s.warnings.append(f"{skill_name(c)} is not a {cls['name']} skill choice (kept)")
            profs |= {f"skill-{c}" for c in good}
            profs |= {f"skill-{c}" for c in chosen}
    if "skill-versatility" in traits:
        picks = [key(x) for x in as_list(draft.get("race-skills"))]
        if len(picks) < 2:
            s.missing.append("half-elf Skill Versatility: 2 skills of your choice")
        profs |= {f"skill-{p}" for p in picks}
    expertise = [key(x) for x in as_list(draft.get("expertise"))]

    # features (class + subclass, levels 1..lvl)
    F = _by_index("Features")
    feats, choices = [], []
    if cls:
        for L in range(1, lvl + 1):
            b, sb = level_rows(ci, L, si)
            for row in (b, sb):
                for f in (row or {}).get("features", []):
                    rec = F.get(f["index"], {})
                    if "ability-score-improvement" in f["index"]:
                        choices.append(("asi", L, f["name"]))
                        continue
                    if f["name"].lower() not in PLACEHOLDERS and not f["name"].lower().endswith(" feature"):
                        feats.append(f["name"])
                    fs = rec.get("feature_specific") or {}
                    if "expertise_options" in fs:
                        choices.append(("expertise", L, f["name"]))
                    if "subfeature_options" in fs and "fighting-style" in f["index"]:
                        choices.append(("fighting-style", L, f["name"]))
    s.features = feats
    need_exp = 2 * sum(1 for c in choices if c[0] == "expertise")
    if need_exp and len(expertise) < need_exp and not draft.get("_file"):
        s.missing.append(f"expertise: {need_exp} proficient skills (have {len(expertise)})")
    if any(c[0] == "fighting-style" for c in choices) and not draft.get("fighting-style"):
        s.missing.append("fighting style (Archery, Defense, Dueling, Great Weapon Fighting, Protection, "
                         "Two-Weapon Fighting)")
    n_asi = sum(1 for c in choices if c[0] == "asi")
    if n_asi and len(as_list(draft.get("asi"))) < n_asi and not draft.get("_file"):
        s.missing.append(f"{n_asi} ability score improvement(s) or feat(s) from levels "
                         + ", ".join(str(c[1]) for c in choices if c[0] == "asi"))

    # saves / skills totals
    saves = [st["index"] for st in (cls or {}).get("saving_throws", [])]
    s.fields["saves"] = saves
    if mods:
        skills = {}
        for sk, ab in SKILL_ABILITY.items():
            if f"skill-{sk}" in profs:
                skills[sk] = mods[ab] + prof * (2 if sk in expertise else 1)
        for e in expertise:
            if f"skill-{e}" not in profs:
                s.warnings.append(f"expertise in {skill_name(e)} without proficiency")
        s.fields["skills"] = skills
        perc = skills.get("perception", mods["wis"])
        inv = skills.get("investigation", mods["int"])
        s.fields["passive-perception"] = 10 + perc
        s.fields["passive-investigation"] = 10 + inv

    # speed, senses, size
    speed = int(race.get("speed", 30)) if race else 30
    senses = ["darkvision 60"] if "darkvision" in traits else []
    s.fields["senses"] = senses
    s.fields["speed"] = speed

    # equipment → AC, attacks
    items = []
    for raw in as_list(draft.get("equipment")):
        q, name = parse_item(raw)
        rec = equipment_record(name)
        items.append((name, q, rec))
    s.inventory = items
    if not items:
        s.defaults.append("equipment: none given → offer the class (and background) starting equipment")
    armor = [r for _, _, r in items if r and r.get("armor_category") and r["armor_category"] != "Shield"]
    shield = any(r and r.get("armor_category") == "Shield" for _, _, r in items)
    for r in armor + ([{"armor_category": "Shield", "name": "Shield"}] if shield else []):
        cat = r["armor_category"].lower()
        need = "shields" if cat == "shield" else f"{cat}-armor"
        if need not in profs:
            s.warnings.append(f"not proficient with {r['name']} ({r['armor_category']} armor)")
    if mods:
        ac, ac_note = _ac(ci, si, mods, armor, shield, draft)
        s.fields["ac"] = ac
        heavy = next((r for r in armor if r["armor_category"] == "Heavy"), None)
        if heavy and scores["str"] < (heavy.get("str_minimum") or 0) and not (race and race["index"] == "dwarf"):
            s.fields["speed"] = speed - 10
            s.warnings.append(f"{heavy['name']} needs STR {heavy['str_minimum']}: speed −10")
        s.ac_note = ac_note
        for name, q, r in items:
            if r and r.get("equipment_category", {}).get("index") == "weapon":
                s.attacks.append(_attack(r, mods, prof, profs, draft, s))
    else:
        s.pending.append("HP, AC, attack bonuses, save totals: need ability scores")

    # hit points
    die = int(cls["hit_die"]) if cls else None
    method = str(draft.get("hp-method") or "").strip().lower()
    if die:
        s.fields["hit-dice"] = {"die": f"d{die}", "left": lvl}
        if method not in ("max", "roll"):
            s.missing.append("hp-method: max or roll (asked once; stored, reused at every level-up)")
            if lvl > 1:
                s.pending.append(f"HP for levels 2–{lvl}: by hp-method (level 1 = {die})")
        if mods:
            per = 1 if (si == "draconic" or (sub and sub["index"] == "hill-dwarf")) else 0
            hp = die + mods["con"] + per
            ok = True
            rolls = [int(x) for x in as_list(draft.get("hp-rolls")) if str(x).isdigit()]
            for i in range(2, lvl + 1):
                if method == "max":
                    hp += max(1, die + mods["con"]) + per
                elif method == "roll" and len(rolls) >= i - 1:
                    hp += max(1, rolls[i - 2] + mods["con"]) + per
                else:
                    ok = False
            if method == "roll" and len(rolls) < lvl - 1:
                s.pending.append(f"HP rolls for levels 2–{lvl} (rolled publicly by `pc draft`)")
            if ok:
                s.fields["hp"] = {"current": hp, "max": hp}

    # spellcasting
    _spells(s, draft, cls, ci, si, lvl, mods, prof, sub)

    # resources
    if cls:
        b, _ = level_rows(ci, lvl)
        cs = (b or {}).get("class_specific") or {}
        for name, k, rec in CLASS_RESOURCES.get(ci, []):
            if cs.get(k):
                s.resources.append({"resource": name, "current": cs[k], "max": cs[k], "recovers": rec})
        if ci == "fighter":
            s.resources.append({"resource": "second wind", "current": 1, "max": 1, "recovers": "short"})
        if ci == "bard" and mods:
            n = max(1, mods["cha"])
            s.resources.append({"resource": f"bardic inspiration d{cs.get('bardic_inspiration_die', 6)}",
                                "current": n, "max": n, "recovers": "short" if lvl >= 5 else "long"})
        if ci == "paladin":
            s.resources.append({"resource": "lay on hands", "current": 5 * lvl, "max": 5 * lvl, "recovers": "long"})
        if ci == "druid" and lvl >= 2:
            s.resources.append({"resource": "wild shape", "current": 2, "max": 2, "recovers": "short"})
        if ci == "rogue":
            sa = cs.get("sneak_attack") or {}
            s.derived_extra = f"sneak attack {sa.get('dice_count', 1)}d{sa.get('dice_value', 6)}"

    # race traits for the DERIVED line
    s.race_traits = [T[t]["name"] for t in traits if t in T and t not in ("darkvision",)]
    s.racial = racial

    # overrides win
    for k, v in ov.items():
        s.fields[k] = v
    # required identity
    if not str(draft.get("name") or "").strip():
        s.missing.append("name")
    s.cls, s.subcls, s.race, s.sub, s.bg = cls, subcls, race, sub, bg
    s.profs = profs
    s.mods = mods
    return s


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _check_scores(s, base, stated_final):
    vals = sorted(base.values(), reverse=True)
    if tuple(vals) == STANDARD_ARRAY:
        return
    if all(8 <= v <= 15 for v in vals):
        cost = sum(POINT_COST[v] for v in vals)
        if cost <= 27:
            return
        s.warnings.append(f"point buy costs {cost} (> 27)")
        return
    if any(v < 3 or v > 18 for v in vals):
        s.warnings.append("scores outside 3–18 before racial bonuses (rolled?)")


def _ac(ci, si, mods, armor, shield, draft):
    if armor:
        a = armor[0]
        ac_ = a["armor_class"]
        dex = mods["dex"] if ac_.get("dex_bonus") else 0
        if ac_.get("max_bonus") is not None:
            dex = min(dex, ac_["max_bonus"])
        ac = ac_["base"] + dex
        note = a["name"]
        if str(draft.get("fighting-style") or "").lower().startswith("def"):
            ac += 1
            note += " + Defense"
    elif ci == "barbarian":
        ac, note = 10 + mods["dex"] + mods["con"], "unarmored defense"
    elif ci == "monk":
        ac, note = 10 + mods["dex"] + mods["wis"], "unarmored defense"
    elif si == "draconic":
        ac, note = 13 + mods["dex"], "draconic resilience"
    else:
        ac, note = 10 + mods["dex"], "unarmored"
    if shield:
        ac += 2
        note += " + shield"
    return ac, note


def _attack(r, mods, prof, profs, draft, s):
    props = [p["index"] for p in r.get("properties", [])]
    ranged = r.get("weapon_range") == "Ranged"
    ab = "dex" if ranged else "str"
    if "finesse" in props:
        ab = "dex" if mods["dex"] >= mods["str"] else "str"
    plural = key(r["name"]) + "s"
    proficient = (f"{r['weapon_category'].lower()}-weapons" in profs or plural in profs
                  or r["index"] in profs)
    if not proficient:
        s.warnings.append(f"not proficient with {r['name']}")
    hit = mods[ab] + (prof if proficient else 0)
    fs = str(draft.get("fighting-style") or "").lower()
    if ranged and fs.startswith("arch"):
        hit += 2
    dmg = r.get("damage") or {}
    dice = dmg.get("damage_dice", "1")
    bonus = mods[ab]
    dtype = (dmg.get("damage_type") or {}).get("name", "").lower()
    if ranged:
        rng = f"{r['range']['normal']}/{r['range'].get('long', r['range']['normal'])}"
    elif "thrown" in props and r.get("throw_range"):
        rng = f"{r['throw_range']['normal']}/{r['throw_range']['long']}"
    else:
        rng = "10" if "reach" in props else "5"
    notes = [p for p in props if p not in ("monk", "simple", "martial")]
    if "versatile" in props and r.get("two_handed_damage"):
        notes = [p if p != "versatile" else f"versatile ({r['two_handed_damage']['damage_dice']})" for p in notes]
    return {"name": r["name"].lower(), "hit": sign(hit),
            "damage": f"{dice}{('+' + str(bonus)) if bonus > 0 else (str(bonus) if bonus < 0 else '')} {dtype}".strip(),
            "range": rng, "notes": ", ".join(notes)}


def _spells(s, draft, cls, ci, si, lvl, mods, prof, sub):
    cantrips = [key(x) for x in as_list(draft.get("cantrips"))]
    known = [key(x) for x in as_list(draft.get("spells"))]
    SP = _by_index("Spells")
    rows = []
    if sub and sub["index"] == "high-elf":
        if not draft.get("race-cantrip"):
            s.missing.append("high elf cantrip: one wizard cantrip (INT)")
        else:
            rows.append({"spell": str(draft["race-cantrip"]).lower(), "level": 0, "source": "cantrip",
                         "notes": "high elf (INT)"})
    if not cls or not cls.get("spellcasting"):
        s.spells = rows
        return
    b, _ = level_rows(ci, lvl)
    sc = (b or {}).get("spellcasting") or {}
    if not sc:
        s.spells = rows
        return
    ab = cls["spellcasting"]["spellcasting_ability"]["index"]
    if mods:
        s.fields["spell-dc"] = 8 + prof + mods[ab]
        s.fields["spell-attack"] = prof + mods[ab]
    slots = {n: sc.get(f"spell_slots_level_{n}", 0) for n in range(1, 10)}
    top = max([n for n, c in slots.items() if c] or [0])
    for n, c in slots.items():
        if c:
            s.resources.append({"resource": f"spell slot {n}", "current": c, "max": c, "recovers":
                                "short" if ci == "warlock" else "long"})
    s.spell_ability, s.slots = ab, slots
    need_c = sc.get("cantrips_known") or 0
    if need_c and len(cantrips) < need_c:
        s.missing.append(f"{need_c} {cls['name'].lower()} cantrips (have {len(cantrips)})")
    need_k = sc.get("spells_known") or 0
    if ci == "wizard":
        need_k = 6 + 2 * (lvl - 1)
    if need_k and len(known) < need_k:
        what = "spellbook spells" if ci == "wizard" else "spells known"
        s.missing.append(f"{need_k} {what} (have {len(known)}; level ≤ {top})")
    if ci in PREPARED and ci != "wizard" and mods:
        n = max(1, mods[ab] + int(lvl * PREPARED[ci]))
        s.defaults.append(f"prepared spells: up to {n} per long rest from the {cls['name'].lower()} list "
                          "(optional now)")
    for x in cantrips + known:
        r = SP.get(x) or next((v for v in SP.values() if key(v["name"]) == x), None)
        if r is None:
            s.custom.append(f"spell {x!r} (not SRD)")
            rows.append({"spell": x.replace("-", " "), "level": "?", "source": "custom", "notes": ""})
            continue
        if ci not in [c["index"] for c in r.get("classes", [])]:
            s.warnings.append(f"{r['name']} is not on the {cls['name']} list")
        if x in cantrips and r["level"] != 0:
            s.warnings.append(f"{r['name']} is not a cantrip")
        if x in known and r["level"] > top:
            s.warnings.append(f"{r['name']} is level {r['level']}: no slot for it yet")
        src = "cantrip" if r["level"] == 0 else ("known" if ci != "wizard" else "spellbook")
        rows.append({"spell": r["name"].lower(), "level": r["level"], "source": src, "notes": ""})
    for p in _always(si, ci, lvl):
        rows.append({"spell": p, "level": SP.get(key(p), {}).get("level", "?"), "source": "always",
                     "notes": "subclass"})
    s.spells = rows


def _always(si, ci, lvl):
    if not si:
        return []
    sub = _by_index("Subclasses").get(si) or {}
    out = []
    for sp in sub.get("spells", []):
        pre = sp.get("prerequisites") or [{}]
        m = re.search(r"-(\d+)$", pre[0].get("index", ""))
        if m and int(m.group(1)) <= lvl:
            out.append(sp["spell"]["name"].lower())
    return out


# ---------- text for pc check / card ----------

def check_lines(slug, draft, s):
    name = draft.get("name") or slug
    race = str(draft.get("race") or "?")
    cls = str(draft.get("class") or "?")
    subc = f" ({draft['subclass']})" if draft.get("subclass") else ""
    lines = [f"[PC CHECK] {slug} · {race} {cls}{subc} {s.fields.get('level', '?')}" + (f" · {name}" if name != slug else "")]
    d1 = [f"speed {s.fields.get('speed')}", f"prof {sign(s.fields['prof'])}"]
    d1 += s.fields.get("senses") or []
    if s.cls:
        d1.append(f"hit die d{s.cls['hit_die']}")
        d1.append("saves " + ", ".join(x.upper() for x in s.fields.get("saves", [])))
    if "ac" in s.fields:
        d1.append(f"AC {s.fields['ac']} ({getattr(s, 'ac_note', '')})")
    if "hp" in s.fields:
        d1.append(f"HP {s.fields['hp']['max']}")
    out = ["DERIVED   " + " · ".join(d1)]
    if s.features:
        out.append("          " + " · ".join(dict.fromkeys(f.lower() for f in s.features)))
    rr = [f"{r['resource']} {r['max']}/{r['recovers']}" for r in s.resources]
    if getattr(s, "derived_extra", None):
        rr.insert(0, s.derived_extra)
    if rr:
        out.append("          " + " · ".join(rr))
    if s.race and (s.racial or s.race_traits):
        rb = " ".join(f"{sign(v)} {a.upper()}" for a, v in s.racial.items())
        out.append(f"          {(s.sub or s.race)['name'].lower()}: " + " · ".join(x for x in [rb] + [t.lower() for t in s.race_traits] if x))
    if s.mods and s.fields.get("skills"):
        out.append("          skills " + " · ".join(f"{k} {sign(v)}" for k, v in s.fields["skills"].items()))
    if s.attacks:
        out.append("          attacks " + " · ".join(f"{a['name']} {a['hit']} {a['damage']}" for a in s.attacks))
    if "spell-dc" in s.fields:
        out.append(f"          spell save DC {s.fields['spell-dc']} · spell attack {sign(s.fields['spell-attack'])}")
    lines += out

    def block(label, items, numbered=False):
        if not items:
            return [f"{label:<10}—"]
        rows = [f"{i}. {t}" if numbered else t for i, t in enumerate(items, 1)]
        return [f"{label:<10}{rows[0]}"] + [f"          {r}" for r in rows[1:]]

    lines += block("PENDING", s.pending)
    lines += block("MISSING", s.missing, numbered=True)
    lines += block("DEFAULTS", s.defaults)
    lines += block("CONFLICTS", s.conflicts + [f"warning: {w}" for w in s.warnings])
    lines += block("CUSTOM", s.custom)
    return lines


def card_lines(slug, draft, s):
    f = s.fields
    name = draft.get("name") or slug
    head = f"[CARD] {name} — {draft.get('race', '?')} {draft.get('class', '?')}"
    head += f" ({draft['subclass']})" if draft.get("subclass") else ""
    head += f" {f.get('level')}"
    sc = f.get("scores")
    lines = [head]
    if sc:
        lines.append(" | ".join(f"{a.upper()} {sc[a]} ({sign(mod(sc[a]))})" for a in ABBR))
    lines.append(f"HP {f.get('hp', {}).get('max', '?')} · AC {f.get('ac', '?')} · speed {f.get('speed')} · "
                 f"prof {sign(f['prof'])} · passive Perception {f.get('passive-perception', '?')}"
                 + (" · " + ", ".join(f.get("senses")) if f.get("senses") else ""))
    if f.get("skills"):
        lines.append("Skills: " + ", ".join(f"{k} {sign(v)}" for k, v in f["skills"].items()))
    if f.get("saves"):
        lines.append("Saves: " + ", ".join(x.upper() for x in f["saves"]))
    for a in s.attacks:
        lines.append(f"Attack: {a['name']} {a['hit']}, {a['damage']} ({a['range']})" + (f" — {a['notes']}" if a['notes'] else ""))
    if s.features:
        lines.append("Features: " + ", ".join(dict.fromkeys(s.features)))
    if s.spells:
        lines.append("Spells: " + ", ".join(f"{r['spell']} ({r['level']})" for r in s.spells))
    if s.inventory:
        lines.append("Equipment: " + "; ".join((f"{q} " if q > 1 else "") + n for n, q, _ in s.inventory))
    open_ = len(s.missing)
    lines.append(f"{open_} required item(s) still missing — `pc check`" if open_ else "Ready: `pc write` on the player's OK")
    return lines
