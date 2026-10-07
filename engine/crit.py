"""The critical hit die (docs/design/02 → Table mechanics → Phase 16 → Critical hit die;
06 → Phase 16 — table extras; 04 → Table settings `crit-die`, `crit-die-pcs`; plan.md
Phase 16 item 7). Not a command: roll.attack() calls it on every crit while `crit-die: on`.

The die is the campaign's `tables/crit-die.md` (else the engine's starter copy), `| roll
| result | effect |`, one row per face, so its size is the number of rows. The codes:
- damage: `dice x2` (RAW: the `crit-damage` table rule still applies), `dice x3`,
  `max+dice` (the dice's maximum plus a roll). A row with no damage code and no `kill`
  deals `dice x2`, so the crit die is never worse than RAW.
- `prone`, `stunned 1t` (until the end of the target's next turn: `1r` when it still acts
  this round, `2r` when it already has), `disarm` (the weapon drops in the target's space:
  a `dropped …` note on its Combatants row and a public log line), `bleed 1d4` (the
  condition `bleeding 1d4`; `combat next` rolls it at the start of each of its turns,
  healing or `cond X -bleeding` after a DC 10 Medicine check ends it), `kill` (HP to 0;
  a PC follows `crit-die-pcs`: `dying` = 0 HP and dying, `dead` = dead).
- anything else is printed for the GM to narrate.
An effect that can't apply (a disarm against a bite, prone on the prone) is dropped and
the row falls back to `dice x2`, saying so. A target with Legendary Resistance left
spends one to turn `kill` into `dice x3` (a tracked `legendary resistance` Resources row
is spent; otherwise the line says to mark it).
"""
import re

from lib import campaign, creatures, dice, journal, resolve, tables
from lib.errors import ToolError

DAMAGE = ("dice x2", "dice x3", "max+dice")
NATURAL = ("bite", "claw", "slam", "tail", "gore", "hoof", "hooves", "tentacle", "sting", "talon",
           "beak", "fist", "unarmed", "tusk", "horn", "touch", "ray", "spit", "breath", "pseudopod",
           "constrict", "ram", "wing", "fang", "stomp")


class CritError(ToolError):
    pass


def enabled():
    return str(campaign.settings().get("crit-die", "off")).strip().lower() == "on"


def pcs_rule():
    v = str(campaign.settings().get("crit-die-pcs", "dying")).strip().lower()
    return "dead" if v == "dead" else "dying"


def _conds(t):
    if t.combat_row:
        cell = t.combat_row.get("conditions") or ""
        return [c.strip().split()[0].lower() for c in cell.split(",") if c.strip() and c.strip() not in ("—", "-")]
    return [str(x).split()[0].lower() for x in (t.front.get("conditions") or [])]


def weapon_of(t):
    """The weapon `t` would drop, or None (no attacks, or a natural attack)."""
    try:
        atk = t.attack(None)
    except (ToolError, campaign.CampaignError):
        return None
    name = atk.get("name", "").strip()
    words = set(re.findall(r"[a-z]+", name.lower()))
    if not name or any(w in words or w.rstrip("s") in NATURAL for w in words for _ in [0] if w in NATURAL) \
            or "natural" in atk.get("notes", "").lower():
        return None
    return name


def legendary(t):
    """(has Legendary Resistance, uses left or None when not tracked)."""
    text = ""
    if t.doc is not None:
        text = t.doc.text().lower()
    try:
        mon = t.monster
    except ToolError:
        mon = None
    if mon is not None:
        text += " ".join(str(s.get("name", "")) for s in mon.rec.get("special_abilities") or []).lower()
    if "legendary resistance" not in text:
        return False, None
    table = t.doc.table("Resources") if t.doc is not None else None
    for r in table.rows if table is not None else []:
        if r.get("resource", "").strip().lower().startswith("legendary resistance"):
            try:
                return True, int(r.get("current", "0"))
            except ValueError:
                return True, None
    return True, None


class Plan:
    def __init__(self, die, n, row):
        self.die, self.n, self.row = die, n, row
        self.damage = None        # one of DAMAGE, or None with kill
        self.effects = []         # [(code, arg)]
        self.other = []           # codes for the GM
        self.notes = []
        self.lr_used = False      # Legendary Resistance turned a kill into dice x3
        self.lr_left = None       # its tracked uses (None: not tracked)

    @property
    def kill(self):
        return any(c == "kill" for c, _ in self.effects)

    def label(self):
        return f"CRIT DIE d{self.die} → {self.n} {self.row.effect or self.row.result}".rstrip()


def plan(t, roller, face=None):
    """Roll the die and decide what applies to target `t` (a creatures.Creature)."""
    try:
        table = tables.load("crit-die")
    except tables.TableError as e:
        raise CritError(f"crit-die: {e}") from None
    n, row = table.roll(roller, face)
    p = Plan(table.die, n, row)
    conds = _conds(t)
    dropped = []
    for code in tables.codes(row.effect):
        c = " ".join(code.lower().split())
        if c in DAMAGE:
            p.damage = c
        elif c == "kill":
            has, left = legendary(t)
            if has and (left is None or left > 0):
                p.damage = "dice x3"
                p.lr_used, p.lr_left = True, left
                p.notes.append("Legendary Resistance: kill → dice x3")
            else:
                p.effects.append(("kill", None))
        elif c == "prone":
            if "prone" in conds:
                dropped.append("already prone")
            else:
                p.effects.append(("prone", None))
        elif re.fullmatch(r"stunned(\s+\d+t)?", c):
            if "stunned" in conds:
                dropped.append("already stunned")
            else:
                p.effects.append(("stunned", None))
        elif c == "disarm":
            w = weapon_of(t)
            if w is None:
                dropped.append(f"{t.name} has no weapon to drop")
            else:
                p.effects.append(("disarm", w))
        elif re.fullmatch(r"bleed\s+\d*d\d+", c):
            p.effects.append(("bleed", c.split()[1]))
        else:
            p.other.append(code)
    if dropped:
        p.notes.append("; ".join(dropped) + ": dice x2 instead")
        p.damage = p.damage or "dice x2"
    if p.damage is None and not p.kill:
        p.damage = "dice x2"
    return p


def damage(roller, expr, how, rules):
    """(total, text) for a damage code."""
    if how == "dice x3":
        res = roller.roll(dice.multiply(expr, 3))
        return res.total, f"{res.label}: {res.body}"
    if how == "max+dice":
        res = roller.roll(expr)
        mx = dice.dice_max(expr)
        total = res.total + mx
        return total, f"{res.body} +{mx} max = {total}"
    return resolve.crit_damage(roller, expr, rules)


def spend_lr(t, p):
    """The Legendary Resistance line (spends a tracked use)."""
    if not p.lr_used:
        return []
    if p.lr_left is not None:
        import inventory
        line, _ = inventory.res(t.name, "-", "legendary resistance")
        return [f"[LR: {t.name} spends a Legendary Resistance: kill → dice x3] {line}"]
    journal.log_delta(f"crit die: {t.name} spends a Legendary Resistance (kill → dice x3)")
    return [f"[LR: {t.name} spends a Legendary Resistance: kill → dice x3 — mark it spent]"]


def kill(t, rules):
    """Apply `kill` -> (tail, after lines, data)."""
    import conditions_ext
    import mutations
    rule = pcs_rule()
    if t.is_pc:
        state = campaign.load_state()
        c = creatures.get(t.name, state)
        hp_now = None
        if c.combat_row:
            m = re.match(r"\s*(\d+)", c.combat_row.get("hp", ""))
            hp_now = int(m.group(1)) if m else None
        elif isinstance(c.front.get("hp"), dict):
            hp_now = int(c.front["hp"].get("current") or 0)
        if hp_now == 0 and rule == "dying":   # already down: a crit at 0 HP (two failures)
            _, data = mutations.dmg(t.name, 1, rules=rules, log=False, crit=True)
            return data["tail"], data.get("after", []), data
        _, data = mutations._apply_hp(t.name, "=", 0, rules=rules, log=False)
        after = data.get("after", [])
        if rule == "dead":
            after = conditions_ext._die(t.name, "crit die: slain (crit-die-pcs: dead)")
        return data["tail"], after, data
    _, data = mutations._apply_hp(t.name, "=", 0, rules=rules, log=False)
    return data["tail"], data.get("after", []), data


def _stun_rounds(t):
    """1r when the target still acts this round, 2r when its turn has passed."""
    state = campaign.load_state()
    table = state.table("Combatants")
    if table is None:
        return "1r"
    import combat
    st = combat._status(state)
    if not st:
        return "1r"
    names = [creatures.norm_name(r["name"]).lower() for r in table.rows]
    up = st[1].lower()
    up_i = next((i for i, n in enumerate(names) if n == up or n.startswith(up)), None)
    me = next((i for i, n in enumerate(names) if n == t.name.lower() or n.startswith(t.name.lower())), None)
    if up_i is None or me is None:
        return "1r"
    return "2r" if me <= up_i else "1r"


def effects(t, p):
    """Apply the plan's conditions and disarm after the damage -> lines."""
    import mutations
    out = []
    for code, arg in p.effects:
        if code == "kill":
            continue
        if code == "prone":
            line, data = mutations.cond(t.name, "+prone")
            out += [line] + data.get("after", [])
        elif code == "stunned":
            line, data = mutations.cond(t.name, "+stunned", _stun_rounds(t))
            out += [line] + data.get("after", [])
        elif code == "bleed":
            line, data = mutations.cond(t.name, "+bleeding", detail=arg)
            out.append(line)
        elif code == "disarm":
            out.append(disarm(t.name, arg))
    for code in p.other:
        out.append(f"[crit die: {code} — narrate and file it]")
    return out


def disarm(name, weapon):
    state = campaign.load_state()
    c = creatures.get(name, state)
    where = ""
    table = state.table("Combatants")
    if c.combat_row is not None and table is not None:
        pos = c.combat_row.get("pos", "").strip()
        where = f" at {pos}" if pos and pos != "?" else ""
        notes = [x.strip() for x in (c.combat_row.get("notes") or "").split(";") if x.strip()]
        notes.append(f"dropped {weapon}{where}")
        table.set(c.combat_index, "notes", "; ".join(notes))
        state.save()
    body = f"crit die: {c.name} drops {weapon}{where} (disarm)"
    journal.log_delta(body)
    return f"[{body}]"


def bleed_line(name, roller):
    """`combat next`: a bleeding creature's start-of-turn damage -> [lines]."""
    import mutations
    state = campaign.load_state()
    c = creatures.get(name, state)
    cell = (c.combat_row or {}).get("conditions", "") if c.combat_row else \
        ", ".join(str(x) for x in (c.front.get("conditions") or []))
    m = re.search(r"\bbleeding\s+(\d*d\d+)", cell or "", re.I)
    if not m and not re.search(r"\bbleeding\b", cell or "", re.I):
        return []
    expr = m.group(1) if m else "1d4"
    res = roller.roll(expr)
    line, data = mutations.dmg(c.name, res.total, log=False)
    body = f"{c.name} bleeds: {expr} {res.body} · {data['tail']}"
    journal.log_delta(body)
    return [f"[{body} (ends when healed, or DC 10 Medicine: cond {c.name.split()[0]} -bleeding)]"] + data.get("after", [])
