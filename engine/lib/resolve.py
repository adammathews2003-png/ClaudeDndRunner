"""Outcome rules: the ONLY place they live (docs/design/06 → atk/save/check/contest
L111-134, esp. L123-127; table-rule keys L194-204, precedence L207-208; rules/
house-rules.md → Ties go to the player L24-32; rules/combat-basics.md → Attacks and
Cover L20-27; plan.md Phase 2 item 2).

Every outcome function returns `(outcome, note)`; `note` names what decided it
(`nat 20`, `nat 1`, `tie→PC`, `half cover +2`, the table rule id) so the GM can
narrate it. Rolls arrive as `dice.D20` objects (`natural`, `total`); this module never
rolls a d20 itself.

Table rules: rows of `<campaign>/state/table-rules.md` (docs/design/04 L540-557) whose
`status` is `active`; only the v1 keys of 06 L194-204 are read (others stay free text,
06 L205-206). When two active rows set the same key the newer (higher R-number) wins.
Precedence: table rules > house rules > RAW (06 L207-208).

House-rule ties (house-rules L24-32), with `ties=pc` (default):
- PC roll = DC / AC → PC succeeds / hits.
- contest tie → PC wins (attacker or defender).
- NPC roll = PC's AC / save DC / passive score → the PC's side wins.
- initiative tie PC vs NPC → PC first.
- PC vs PC → no house rule (re-roll or players decide).
With `ties=raw`: meets-it-beats-it, and a contest tie leaves things as they were.
"""
import re

from . import campaign, md
from .errors import ToolError

V1_KEYS = ("crit-range", "crit-damage", "ties", "flanking", "death-saves", "potion",
           "dice-mode", "encounters")
V1_VALUES = {
    "crit-range": r"1[89]|20",
    "crit-damage": r"double|max\+roll",
    "ties": r"pc|raw",
    "flanking": r"off|adv|\+2",
    "death-saves": r"on|off|dc \d+",
    "potion": r"action|bonus",
    "dice-mode": r"players-roll-d20s|gm-rolls-all",
    "encounters": r"on|off",
}
COVER = {"none": 0, "half": 2, "three-quarters": 5, "3/4": 5, "total": None}
TIE = "tie→PC"


class ResolveError(ToolError):
    pass


# ---------- table rules ----------

def table_rules_path():
    return campaign.root() / "state" / "table-rules.md"


def _rid(row):
    m = re.match(r"R(\d+)", row.get("id", ""), re.I)
    return int(m.group(1)) if m else 0


def active_keys(rows=None):
    """{key: {"value": str, "id": "R3", "rule": text, "scope": str}} for active rows
    with a v1 key; newest wins per key. `rows` defaults to state/table-rules.md."""
    if rows is None:
        p = table_rules_path()
        if not p.exists():
            return {}
        table = md.load(p).table("Table rules")
        rows = table.rows if table else []
    out = {}
    for row in sorted(rows, key=_rid):
        if row.get("status", "").strip().lower() != "active":
            continue
        key, sep, value = row.get("key", "").partition("=")
        key, value = key.strip().lower(), value.strip().lower()
        if not sep or key not in V1_KEYS:
            continue
        out[key] = {"value": value, "id": row.get("id", ""), "rule": row.get("rule", ""),
                    "scope": row.get("scope", "")}
    return out


def valid_value(key, value):
    """True when `key=value` is a v1 key with a value 06 L194-204 allows."""
    pat = V1_VALUES.get(key)
    return bool(pat and re.fullmatch(pat, value.strip().lower()))


def _rule(rules, key):
    if rules is None:
        rules = active_keys()
    return rules.get(key)


def ties_to_pc(rules=None):
    r = _rule(rules, "ties")
    return not (r and r["value"] == "raw")


def crit_threshold(rules=None):
    """(N, rule id or None): a natural roll >= N crits (06 L196)."""
    r = _rule(rules, "crit-range")
    if r and re.fullmatch(r"\d+", r["value"]):
        return int(r["value"]), r["id"]
    return 20, None


def dice_mode(state_front, rules=None):
    """`players-roll-d20s` | `gm-rolls-all`: a `dice-mode` table rule overrides
    current.md (06 L202)."""
    r = _rule(rules, "dice-mode")
    if r:
        return r["value"]
    return str(state_front.get("dice-mode") or "players-roll-d20s").strip().lower()


def flanking(rules=None):
    """(effect, rule id): effect None | 'adv' | '+2' (06 L199). Off unless a rule
    turns it on (RAW 5e has no flanking)."""
    r = _rule(rules, "flanking")
    if r and r["value"] in ("adv", "+2"):
        return r["value"], r["id"]
    return None, None


def cover_bonus(cover):
    """AC / DEX-save bonus for cover (combat-basics L26-27). None = total cover."""
    key = (cover or "none").strip().lower()
    if key not in COVER:
        raise ResolveError(f"unknown cover {cover!r} (half | three-quarters | total)")
    return COVER[key]


def _tie_ok(a_is_pc, b_is_pc, rules):
    """The tie goes to the PC side: exactly one side is a PC and ties=pc."""
    return a_is_pc != b_is_pc and ties_to_pc(rules)


def _join(*notes):
    return ", ".join(n for n in notes if n)


# ---------- outcomes ----------

def attack(roll, ac, *, attacker_is_pc, target_is_pc, cover=None, rules=None):
    """-> (outcome, note); outcome HIT | MISS | CRIT | NO TARGET. Natural 1 misses,
    natural >= crit-range crits (combat-basics L22-23, 06 L196); a reported total has
    no natural. Cover adds to AC (combat-basics L26-27). Ties per house-rules."""
    if rules is None:
        rules = active_keys()
    bonus = cover_bonus(cover)
    if bonus is None:
        return "NO TARGET", "total cover"
    cover_note = f"{cover} cover +{bonus}" if bonus else ""
    eff = ac + bonus
    crit_at, rid = crit_threshold(rules)
    nat = roll.natural
    if nat is not None and nat >= crit_at:
        why = f"nat {nat}" + (f", crit-range {crit_at} ({rid})" if rid and nat < 20 else "")
        return "CRIT", _join(why, cover_note)
    if nat == 1:
        return "MISS", _join("nat 1", cover_note)
    if roll.total > eff:
        return "HIT", cover_note
    if roll.total < eff:
        return "MISS", cover_note
    if _tie_ok(attacker_is_pc, target_is_pc, rules):
        return ("HIT" if attacker_is_pc else "MISS"), _join(TIE, cover_note)
    return "HIT", cover_note  # RAW: meets it, beats it


def effective_ac(ac, cover=None):
    bonus = cover_bonus(cover)
    return None if bonus is None else ac + bonus


def attack_mode(mode=None, *, long_range=False, flanked=False, rules=None):
    """Combine the attack's adv/dis sources: the asked-for `mode`, long range
    (disadvantage, combat-basics L22-25 / RAW) and a `flanking` table rule (06 L199).
    Advantage and disadvantage cancel. -> (mode, bonus, notes); the notes are always
    given (even when a player reports the d20) so the GM knows what applied."""
    if rules is None:
        rules = active_keys()
    adv, dis, bonus, notes = mode == "adv", mode == "dis", 0, []
    if long_range:
        dis = True
        notes.append("long range: disadvantage")
    if flanked:
        effect, rid = flanking(rules)
        if effect == "adv":
            adv = True
        elif effect == "+2":
            bonus = 2
        if effect:
            notes.append(f"flanking {effect} ({rid})")
    if adv and dis:
        if mode or len(notes) > 1:
            notes.append("adv and dis cancel")
        return None, bonus, notes
    return ("adv" if adv else "dis" if dis else None), bonus, notes


def save(roll, dc, *, saver_is_pc, dc_from_pc=False, cover=None, ability=None, rules=None):
    """-> (SAVE | FAIL, note). `dc_from_pc`: the DC is a PC's (spell save DC), so an
    NPC meeting it exactly fails (house-rules L30-31). Cover adds to DEX saves only."""
    if rules is None:
        rules = active_keys()
    dex = (ability or "").lower() == "dex"
    bonus = cover_bonus(cover) if (cover and dex) else 0  # cover only helps DEX saves
    if bonus is None:
        return "SAVE", "total cover"
    cover_note = ""
    total = roll.total
    if bonus:
        total += bonus
        cover_note = f"{cover} cover +{bonus}"
    if total > dc:
        return "SAVE", cover_note
    if total < dc:
        return "FAIL", cover_note
    if _tie_ok(saver_is_pc, dc_from_pc, rules):
        return ("SAVE" if saver_is_pc else "FAIL"), _join(TIE, cover_note)
    return "SAVE", cover_note


def save_total(roll, cover=None, ability=None):
    """The save total shown in the line, cover included for DEX saves."""
    if not cover or (ability or "").lower() != "dex":
        return roll.total
    bonus = cover_bonus(cover)
    return roll.total + bonus if bonus else roll.total


def check(roll, dc, *, checker_is_pc, vs_pc=False, rules=None):
    """-> (SUCCESS | FAIL, note). `vs_pc`: the DC is a PC's passive score/AC, so an
    NPC meeting it exactly fails (house-rules L30-31)."""
    if rules is None:
        rules = active_keys()
    if roll.total > dc:
        return "SUCCESS", ""
    if roll.total < dc:
        return "FAIL", ""
    if _tie_ok(checker_is_pc, vs_pc, rules):
        return ("SUCCESS" if checker_is_pc else "FAIL"), TIE
    return "SUCCESS", ""


def contest(a_total, b_total, *, a_is_pc, b_is_pc, rules=None):
    """-> ('A' | 'B' | 'TIE', note). A tie goes to the PC side (house-rules L28-29);
    PC vs PC or NPC vs NPC (or ties=raw): nothing changes (RAW)."""
    if rules is None:
        rules = active_keys()
    if a_total > b_total:
        return "A", ""
    if b_total > a_total:
        return "B", ""
    if _tie_ok(a_is_pc, b_is_pc, rules):
        return ("A" if a_is_pc else "B"), TIE
    if a_is_pc and b_is_pc:
        return "TIE", "PC vs PC: re-roll or players decide"
    return "TIE", "no change (RAW)"


def initiative_order(entries, rules=None):
    """Sort [(name, init, is_pc)] highest first; a PC beats an NPC on a tie
    (house-rules L32). Stable otherwise."""
    pc_first = ties_to_pc(rules if rules is not None else active_keys())
    return sorted(entries, key=lambda e: (-e[1], 0 if (pc_first and e[2]) else 1))


# ---------- damage and hit points ----------

def crit_damage(roller, expr, rules=None):
    """Roll damage for a critical hit: `crit-damage=double` (default, dice doubled,
    combat-basics L23) or `max+roll` (06 L197). -> (total, text)."""
    r = _rule(rules, "crit-damage")
    if r and r["value"] == "max+roll":
        from . import dice
        res = roller.roll(expr)
        mx = dice.dice_max(expr)
        total = res.total + mx
        return total, f"{res.body} +{mx} max ({r['id']}) = {total}"
    res = roller.roll(expr + " crit")
    return res.total, res.body


def adjust_damage(amount, dtype=None, *, resist=(), immune=(), vuln=()):
    """Apply resistance (half, round down), immunity (0), vulnerability (double) from
    the stat block for damage type `dtype`. -> (amount, note)."""
    if not dtype:
        return amount, ""
    d = dtype.strip().lower()
    low = lambda xs: {str(x).strip().lower() for x in (xs or [])}  # noqa: E731
    if d in low(immune):
        return 0, "immune"
    if d in low(resist):
        return amount // 2, "resistant"
    if d in low(vuln):
        return amount * 2, "vulnerable"
    return amount, ""


def apply_hp(cur, mx, temp, op, n, *, is_pc=False, rules=None):
    """HP arithmetic for `hp`/`dmg` (06 L141). op: '-' damage (temp HP absorbs first),
    '+' heal, '=' set, 'temp' grant temp HP (no stacking: keep the higher). Clamps to
    0..max (pass the exhaustion-halved max, see exhaustion_hp_max); a `death-saves=off`
    rule drops a PC to 1 instead of 0 (06 L200). What 0 HP means for a PC (dying, death
    save failures, massive damage) is conditions_ext.after_hp's write.
    -> (cur, temp, note)."""
    temp = temp or 0
    note = ""
    if n < 0:
        raise ResolveError(f"hp amounts are never negative (got {n}); use + to heal")
    if op == "temp":
        if n <= temp:
            return cur, temp, f"temp HP don't stack (kept {temp})"
        return cur, n, ""
    # damage at 0 HP is a death save failure: written by conditions_ext.after_hp (Phase 13)
    if op == "-":
        absorbed = min(temp, n)
        temp -= absorbed
        n -= absorbed
        if absorbed:
            note = _join(note, f"temp absorbed {absorbed}")
        new = cur - n
    elif op == "+":
        new = cur + n
    elif op == "=":
        new = n
    else:
        raise ResolveError(f"bad hp op {op!r}")
    new = max(0, min(mx, new))
    if new == 0 and is_pc and cur > 0:
        r = _rule(rules, "death-saves")
        if r and r["value"] == "off":
            new = 1
            note = _join(note, f"death-saves off ({r['id']}): 1 HP")
    return new, temp, note


# ---------- dying (02 → Table mechanics → Dying; 06 → Phase 13) ----------

def death_saves(rules=None):
    """(on, success DC, rule id): the `death-saves` table rule (`on | off | dc N`)."""
    r = _rule(rules, "death-saves")
    if r is None:
        return True, 10, None
    if r["value"] == "off":
        return False, 10, r["id"]
    m = re.fullmatch(r"dc (\d+)", r["value"])
    return True, (int(m.group(1)) if m else 10), r["id"]


def death_save(natural, ok, fail, dc=10):
    """One death save on a natural d20 -> (ok, fail, result) with result 'up' (a 20:
    1 HP), 'stable' (third success), 'dead' (third failure) or '' (still dying). A 1
    is two failures."""
    if natural == 20:
        return ok, fail, "up"
    if natural == 1:
        fail += 2
    elif natural >= dc:
        ok += 1
    else:
        fail += 1
    if fail >= 3:
        return ok, min(fail, 3), "dead"
    if ok >= 3:
        return 3, fail, "stable"
    return ok, fail, ""


# ---------- exhaustion (02 → Table mechanics → Exhaustion) ----------

EXHAUSTION_2014 = {1: "disadvantage on ability checks", 2: "speed halved",
                   3: "disadvantage on attacks and saves", 4: "HP maximum halved",
                   5: "speed 0", 6: "death"}


def exhaustion_effects(level, ruleset="2014"):
    """Short text of what `level` does under the table's ruleset."""
    if not level:
        return "no effect"
    if str(ruleset) == "2024":
        return "death" if level >= 6 else f"−{2 * level} on d20 tests, −{5 * level} ft speed"
    return "; ".join(EXHAUSTION_2014[k] for k in range(1, min(level, 6) + 1))


def exhaustion_d20(level, kind, ruleset="2014"):
    """(disadvantage, penalty, note) for a d20 test of `kind` (check | save | attack):
    2014: level 1+ disadvantage on checks, 3+ on attacks and saves; 2024: −2 per level
    on every d20 test."""
    if not level:
        return False, 0, ""
    if str(ruleset) == "2024":
        return False, -2 * level, f"exhaustion {level}: −{2 * level}"
    if (kind == "check" and level >= 1) or (kind in ("attack", "save") and level >= 3):
        return True, 0, f"exhaustion {level}: disadvantage"
    return False, 0, ""


def with_disadvantage(mode, dis):
    """Add a disadvantage source to an asked-for mode (advantage and disadvantage cancel)."""
    if not dis:
        return mode
    return None if mode == "adv" else "dis"


def exhaustion_speed(speed, level, ruleset="2014"):
    if not level:
        return speed
    if str(ruleset) == "2024":
        return max(0, speed - 5 * level)
    if level >= 5:
        return 0
    return speed // 2 if level >= 2 else speed


def exhaustion_hp_max(mx, level, ruleset="2014"):
    """The HP maximum the arithmetic uses: halved at level 4+ under the 2014 table."""
    return mx // 2 if level and level >= 4 and str(ruleset) != "2024" else mx
