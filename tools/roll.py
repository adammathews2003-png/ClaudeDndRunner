"""Dice and resolution commands: `roll`, `atk`, `save`, `check`, `contest`
(planning/06 → roll L96-109, atk/save/check/contest L111-134, turn blocks L156-168;
planning/02 → Dice L167-176; rules/house-rules.md L7-10, L24-32; rules/combat-basics.md
L20-27; plan.md Phase 2 items 3-4).

Rolling is lib/dice.py; every outcome (hit/miss/crit, save, tie→PC, cover) is
lib/resolve.py; this module only gathers numbers, formats lines and logs deltas.

PC side: `--d20 N` (the tool adds the bonus) or `--total N` (02 L170-174). Without
either the tool rolls for a PC only when `dice-mode: gm-rolls-all` (current.md or an
active `dice-mode` table rule). NPC numbers come from a custom stat block until
Phase 4 builds `srd` (lib/creatures.py raises "srd not built yet" otherwise).

`atk` on a hit rolls damage (crit per the `crit-damage` rule) and applies it through
mutations.dmg(log=False) unless `--no-apply`; the HP change is folded into the atk
delta, so one attack is one log line. When both creatures have positions (Combatants
or Stage rows) the reach/range is checked with space.py's geometry first; out of
reach stops with `out of reach (N ft)`. Long range, flanking (a table rule) and the
asked-for adv/dis are combined by resolve.attack_mode(); its notes are printed even
when the player reported the d20.

Lines:
    [Veskar → Kael: d20 13+5=18 vs AC 18 — MISS (tie→PC)]
    [Veskar → Kael: d20 19+5=24 vs AC 18 — HIT · 7 slashing · Kael 30→23/30]
    [Kael DEX save: d20 12+0=12 vs DC 14 — FAIL]
    [Mara insight: d20 9+2=11 vs DC 12 — FAIL]
    [Kira stealth d20 15+7=22 vs Mara perception d20 8+3=11 — Kira wins]
`--secret` prefixes `SECRET` and logs the delta as `(GM)`.
"""
import re

from lib import campaign, creatures, dice, journal, resolve
from lib.errors import ToolError
import mutations


class RollError(ToolError):
    pass


def _mode(args):
    words = [w.lower() for w in (getattr(args, "mode", None) or [])]
    bad = [w for w in words if w not in ("adv", "dis")]
    if bad:
        raise RollError(f"unexpected {' '.join(bad)!r} (adv | dis)")
    if "adv" in words and "dis" in words:
        return None
    return words[0] if words else None


def _d20(roller, c, bonus, mode, d20, total, state, rules, label=""):
    """The d20 for one side: reported for a PC (--d20/--total), else rolled by the GM
    (NPCs always; PCs only under gm-rolls-all)."""
    if d20 is not None or total is not None:
        if not c.is_pc:
            raise RollError(f"--d20/--total are for the PC side; {c.name} is an NPC (the GM rolls)")
        return dice.reported(bonus, d20=d20, total=total)
    if c.is_pc and resolve.dice_mode(state.front, rules) != "gm-rolls-all":
        raise RollError(f"{c.name}{label} rolls their own d20: pass --d20 N or --total N "
                        "(or set dice-mode: gm-rolls-all)")
    return roller.d20(bonus, mode)


def _outcome(outcome, note):
    return f"{outcome} ({note})" if note else outcome


def _log(body, secret):
    journal.log_delta(("roll SECRET " if secret else "") + body, gm=secret)


def _wrap(body, secret):
    return f"[SECRET {body}]" if secret else f"[{body}]"


# ---------- roll ----------

def cmd_roll(ctx):
    expr = " ".join(ctx.args.expr)
    r = ctx.roller
    secret = ctx.args.secret
    if expr.lower().startswith("table:"):
        slug = expr.split(":", 1)[1].strip()
        res = r.roll_table(campaign.path("tables", slug), slug, secret=secret)
    else:
        res = r.roll(expr, secret=secret)
    ctx.emit(res.text)
    ctx.result = res.as_dict()
    if secret:
        journal.log_delta(f"roll SECRET {res.label}: {res.body}", gm=True)


# ---------- range ----------

def _reach(c, atk):
    """(max ft, normal ft or None) for the attack: a melee row ('5', '' or 'reach 10')
    uses the creature's reach (notes `reach N`, default 5); 'N/M' is normal/long;
    a bare N > 10 is a single range."""
    rng = atk["range"].lower()
    row = c.combat_row or c.stage_row or {}
    m = re.search(r"reach\s*(\d+)", row.get("notes", "") + " " + rng)
    reach = max(5, int(m.group(1))) if m else 5
    nm = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", rng)
    if nm:
        return max(int(nm.group(2)), reach), int(nm.group(1))
    single = re.fullmatch(r"\s*(\d+)\s*(ft)?\s*", rng)
    if single and int(single.group(1)) > 10:
        return int(single.group(1)), None
    if single:
        return max(int(single.group(1)), reach), None
    return reach, None


def _distance(a, b):
    """Feet between two creatures with positions, via space.py's geometry."""
    import space
    ra = a.combat_row or a.stage_row
    rb = b.combat_row or b.stage_row
    return space.dist_between(space.Combatant(ra).cells(), space.Combatant(rb).cells())


def _flanked(state, a, t):
    """An ally of the attacker on the opposite side of the target (06 L199): the cell
    mirrored through the target from the attacker, both adjacent."""
    if a.pos is None or t.pos is None or resolve.flanking()[0] is None:
        return False
    table = state.table("Combatants") or state.table("Stage")
    if table is None:
        return False
    if max(abs(p - q) for p, q in zip(a.pos, t.pos)) > 5:
        return False
    mirror = tuple(2 * q - p for p, q in zip(a.pos, t.pos))
    for row in table.rows:
        name = creatures.norm_name(row.get("name"))
        if name.lower() in (a.name.lower(), t.name.lower()):
            continue
        if row.get("side", "").strip().lower() != a.side or row.get("hp", "").startswith("0/"):
            continue
        try:
            from lib import md
            if md.parse_point(row.get("pos", "")) == mirror:
                return True
        except ValueError:
            continue
    return False


# ---------- atk ----------

def attack(attacker, target, *, with_=None, mode=None, cover=None, d20=None, total=None,
           apply=True, seed=None, roller=None):
    """Python API: resolve one attack. Returns (lines, data). One delta per attack:
    the HP change is folded into the atk line (mutations.dmg(log=False))."""
    state = campaign.load_state()
    rules = resolve.active_keys()
    roller = roller or dice.Roller(seed)
    a = creatures.get(attacker, state)
    t = creatures.get(target, state)
    atk = a.attack(with_)
    ac = t.ac()
    head = f"{a.name} → {t.name}"
    long_range = False
    if a.pos is not None and t.pos is not None:
        dist = _distance(a, t)
        far, normal = _reach(a, atk)
        if dist > far:
            line = f"[{head}: out of reach ({dist:g} ft)]"
            return [line], {"out_of_reach": True, "distance": dist}
        long_range = normal is not None and dist > normal
    mode, extra, mode_notes = resolve.attack_mode(mode, long_range=long_range,
                                                  flanked=_flanked(state, a, t), rules=rules)
    roll = _d20(roller, a, atk["hit"] + extra, mode, d20, total, state, rules)
    outcome, note = resolve.attack(roll, ac, attacker_is_pc=a.is_pc, target_is_pc=t.is_pc,
                                   cover=cover, rules=rules)
    note = ", ".join(x for x in mode_notes + [note] if x)
    eff = resolve.effective_ac(ac, cover)
    ac_txt = f"AC {eff if eff is not None else ac}"
    body = f"{head}: {roll.text} vs {ac_txt} — {_outcome(outcome, note)}"
    data = {"attacker": a.name, "target": t.name, "attack": atk["name"], "roll": roll.as_dict(),
            "ac": eff, "outcome": outcome, "note": note}
    if outcome not in ("HIT", "CRIT"):
        journal.log_delta(f"atk {body}")
        return [f"[{body}]"], data
    if outcome == "CRIT":
        amount, dtext = resolve.crit_damage(roller, atk["damage"], rules)
    else:
        res = roller.roll(atk["damage"])
        amount, dtext = res.total, res.body
    dtype = atk["dtype"]
    body += f" · {amount}" + (f" {dtype}" if dtype else "")
    data.update({"damage": amount, "damage_type": dtype, "damage_roll": dtext})
    crit = " crit" if outcome == "CRIT" else ""
    roll_note = f" [{atk['damage']}{crit}: {dtext}]"
    if not apply:
        journal.log_delta(f"atk {body}{roll_note} · not applied")
        return [f"[{body} · not applied]"], data
    _, hp_data = mutations.dmg(t.name, amount, dtype, rules=rules, log=False)
    if hp_data.get("resist_note"):
        body += f" → {hp_data['applied']} ({hp_data['resist_note']})"
    body += f" · {hp_data['tail']}"
    data["hp"] = hp_data
    journal.log_delta(f"atk {body}{roll_note}")
    return [f"[{body}]"], data


def cmd_atk(ctx):
    a = ctx.args
    lines, data = attack(a.attacker, a.target, with_=a.with_, mode=_mode(a), cover=a.cover,
                         d20=a.d20, total=a.total, apply=not a.no_apply, roller=ctx.roller)
    for line in lines:
        ctx.emit(line)
    ctx.result = data


# ---------- save / check ----------

def saving_throw(name, ability, dc, *, mode=None, d20=None, total=None, by=None, cover=None,
                 secret=False, seed=None, roller=None):
    state = campaign.load_state()
    rules = resolve.active_keys()
    c = creatures.get(name, state)
    ab = creatures.ABILITIES.get(ability.lower())
    if not ab:
        raise RollError(f"save: unknown ability {ability!r} (str dex con int wis cha)")
    dc_from_pc = creatures.get(by, state).is_pc if by else False
    bonus = c.save_bonus(ab)
    roll = _d20(roller or dice.Roller(seed), c, bonus, mode, d20, total, state, rules)
    outcome, note = resolve.save(roll, dc, saver_is_pc=c.is_pc, dc_from_pc=dc_from_pc,
                                 cover=cover, ability=ab, rules=rules)
    shown = resolve.save_total(roll, cover, ab)
    rtext = roll.text if shown == roll.total else f"{roll.text} → {shown}"
    body = f"{c.name} {ab.upper()} save: {rtext} vs DC {dc} — {_outcome(outcome, note)}"
    _log(body, secret)
    return _wrap(body, secret), {"name": c.name, "ability": ab, "dc": dc, "roll": roll.as_dict(),
                                 "outcome": outcome, "note": note}


def ability_check(name, skill, dc, *, mode=None, d20=None, total=None, vs=None, secret=False,
                  seed=None, roller=None):
    state = campaign.load_state()
    rules = resolve.active_keys()
    c = creatures.get(name, state)
    vs_pc = creatures.get(vs, state).is_pc if vs else False
    bonus = c.skill_bonus(skill)
    roll = _d20(roller or dice.Roller(seed), c, bonus, mode, d20, total, state, rules)
    outcome, note = resolve.check(roll, dc, checker_is_pc=c.is_pc, vs_pc=vs_pc, rules=rules)
    body = f"{c.name} {creatures.skill_key(skill)}: {roll.text} vs DC {dc} — {_outcome(outcome, note)}"
    _log(body, secret)
    return _wrap(body, secret), {"name": c.name, "skill": creatures.skill_key(skill), "dc": dc,
                                 "roll": roll.as_dict(), "outcome": outcome, "note": note}


def cmd_save(ctx):
    a = ctx.args
    line, data = saving_throw(a.target, a.ability, a.dc, mode=_mode(a), d20=a.d20, total=a.total,
                              by=a.by, cover=a.cover, secret=a.secret, roller=ctx.roller)
    ctx.emit(line)
    ctx.result = data


def cmd_check(ctx):
    a = ctx.args
    line, data = ability_check(a.target, a.skill, a.dc, mode=_mode(a), d20=a.d20, total=a.total,
                               vs=a.vs, secret=a.secret, roller=ctx.roller)
    ctx.emit(line)
    ctx.result = data


# ---------- contest ----------

def _opponents(state, a):
    """Who a passive contest is against: in combat the Combatants of the other kind
    (PC/NPC); else, for a PC, the NPCs on stage (Stage rows, On stage bullets), and for
    an NPC, the present PCs."""
    if state.table("Combatants") is not None:
        names = [creatures.norm_name(r.get("name")) for r in state.table("Combatants").rows]
    elif a.is_pc:
        names = [m.name for m in campaign.stage_matches(state)]
    else:
        names = [str(d.front.get("name")) for d in campaign.pcs() if d.front.get("present") is not False]
    out = []
    for n in names:
        c = creatures.get(n, state)
        if c.is_pc != a.is_pc:
            out.append(c)
    return out


def contest(a_name, a_skill, b_name=None, b_skill=None, *, mode=None, d20=None, total=None,
            d20b=None, totalb=None, secret=False, seed=None, roller=None):
    """`contest A skill B skill`, or `contest A skill passive [sense]` against every
    opponent's passive score (default perception). `--d20/--total` belong to the PC
    side (06 L118); PC vs PC takes `--d20b/--totalb` for B."""
    state = campaign.load_state()
    rules = resolve.active_keys()
    roller = roller or dice.Roller(seed)
    a = creatures.get(a_name, state)
    passive = b_name is None or b_name.lower() == "passive"
    b = None if passive else creatures.get(b_name, state)
    if not passive and b_skill is None:
        raise RollError("contest: name the second skill (contest A skill B skill)")
    a_given = (d20, total) if (a.is_pc or passive or not b.is_pc) else (None, None)
    a_roll = _d20(roller, a, a.skill_bonus(a_skill), mode, *a_given, state, rules)
    a_txt = f"{a.name} {creatures.skill_key(a_skill)} {a_roll.text}"
    if passive:
        sense = creatures.skill_key(b_skill or "perception")
        parts, results = [], []
        for c in _opponents(state, a):
            try:
                p = c.passive(sense)
            except creatures.SrdNotBuilt:
                parts.append(f"{c.name} — no numbers (srd not built yet)")
                results.append({"name": c.name, "passive": None, "winner": None, "note": "srd"})
                continue
            win, note = resolve.contest(a_roll.total, p, a_is_pc=a.is_pc, b_is_pc=c.is_pc, rules=rules)
            who = {"A": a.name, "B": c.name}.get(win)
            verdict = f"{who} wins" + (f" ({note})" if note else "") if who else f"TIE ({note})"
            parts.append(f"{c.name} {p} — {verdict}")
            results.append({"name": c.name, "passive": p, "winner": who or "TIE", "note": note})
        if not parts:
            raise RollError("contest passive: nobody on stage to contest")
        if all(r["passive"] is None for r in results):
            raise RollError("contest passive: no opponent has numbers yet (srd not built yet, Phase 4)")
        body = f"{a_txt} vs passive {sense}: " + " · ".join(parts)
        _log(body, secret)
        return _wrap(body, secret), {"a": a.name, "roll": a_roll.as_dict(), "vs": results}
    if b.is_pc:
        b_given = (d20b, totalb) if a.is_pc else (d20, total)
    else:
        b_given = (None, None)
    b_roll = _d20(roller, b, b.skill_bonus(b_skill), None, *b_given, state, rules)
    win, note = resolve.contest(a_roll.total, b_roll.total, a_is_pc=a.is_pc, b_is_pc=b.is_pc,
                                rules=rules)
    b_txt = f"{b.name} {creatures.skill_key(b_skill)} {b_roll.text}"
    if win == "TIE":
        verdict = f"TIE ({note})"
    else:
        verdict = f"{a.name if win == 'A' else b.name} wins" + (f" ({note})" if note else "")
    body = f"{a_txt} vs {b_txt} — {verdict}"
    _log(body, secret)
    return _wrap(body, secret), {"a": a.name, "b": b.name, "a_roll": a_roll.as_dict(),
                                 "b_roll": b_roll.as_dict(), "winner": win, "note": note}


def cmd_contest(ctx):
    a = ctx.args
    words = [w.lower() for w in a.rest if w.lower() in ("adv", "dis")]
    rest = [w for w in a.rest if w.lower() not in ("adv", "dis")]
    if len(rest) > 2:
        raise RollError("contest: unexpected " + " ".join(rest[2:]))
    a.mode = (a.mode or []) + words
    b_name = rest[0] if rest else None
    b_skill = rest[1] if len(rest) > 1 else None
    line, data = contest(a.a_name, a.a_skill, b_name, b_skill, mode=_mode(a), d20=a.d20,
                         total=a.total, d20b=a.d20b, totalb=a.totalb, secret=a.secret,
                         roller=ctx.roller)
    ctx.emit(line)
    ctx.result = data


# ---------- registration ----------

def _pc_side(p):
    x = p.add_mutually_exclusive_group()
    x.add_argument("--d20", type=int, help="the player's natural d20 (tool adds the bonus)")
    x.add_argument("--total", type=int, help="the player's total")


def register(sub, g):
    p = mutations.allow_negative(
        sub.add_parser("roll", parents=[g], help="roll 1d20+5 [adv|dis|crit|x3] | table:<slug>"))
    p.add_argument("expr", nargs="+")
    p.add_argument("--secret", action="store_true")
    p.set_defaults(func=cmd_roll)

    p = sub.add_parser("atk", parents=[g], help="atk ATTACKER TARGET [--with W] [adv|dis] [--cover half]")
    p.add_argument("attacker"); p.add_argument("target")
    p.add_argument("mode", nargs="*", help="adv | dis")
    p.add_argument("--with", dest="with_")
    p.add_argument("--cover", choices=["half", "three-quarters", "total"])
    p.add_argument("--no-apply", action="store_true", help="don't apply the damage")
    _pc_side(p)
    p.set_defaults(func=cmd_atk)

    p = sub.add_parser("save", parents=[g], help="save NAME ABILITY DC [adv|dis]")
    p.add_argument("target"); p.add_argument("ability"); p.add_argument("dc", type=int)
    p.add_argument("mode", nargs="*")
    p.add_argument("--by", help="whose DC it is (a PC's: an NPC tie fails, house rule)")
    p.add_argument("--cover", choices=["half", "three-quarters", "total"])
    p.add_argument("--secret", action="store_true")
    _pc_side(p)
    p.set_defaults(func=cmd_save)

    p = sub.add_parser("check", parents=[g], help="check NAME SKILL DC [adv|dis] [--secret]")
    p.add_argument("target"); p.add_argument("skill"); p.add_argument("dc", type=int)
    p.add_argument("mode", nargs="*")
    p.add_argument("--vs", help="the DC is this PC's score (passive/AC): an NPC tie fails")
    p.add_argument("--secret", action="store_true")
    _pc_side(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("contest", parents=[g], help="contest A SKILL B SKILL | contest A SKILL passive")
    p.add_argument("a_name"); p.add_argument("a_skill")
    p.add_argument("rest", nargs="*", help="B SKILL | passive [sense]; adv | dis")
    p.add_argument("--mode", dest="mode", action="append", choices=["adv", "dis"],
                   help="alias for a bare adv/dis")
    p.add_argument("--secret", action="store_true")
    _pc_side(p)
    p.add_argument("--d20b", type=int, help="PC vs PC: the second PC's natural d20")
    p.add_argument("--totalb", type=int, help="PC vs PC: the second PC's total")
    p.set_defaults(func=cmd_contest)
