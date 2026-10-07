"""Dice and resolution commands: `roll`, `atk`, `save`, `check`, `contest`
(docs/design/06 → roll L96-109, atk/save/check/contest L111-134, turn blocks L156-168;
docs/design/02 → Dice L167-176; rules/house-rules.md L7-10, L24-32; rules/combat-basics.md
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
    [Kael DEX save: d20 12+0=12 vs DC 14 — FAIL by 2]
    [Mara insight: d20 9+2=11 vs DC 12 — FAIL by 1]
    [Kira stealth d20 15+7=22 vs Mara perception d20 8+3=11 — Kira wins by 11]
The margin (`by N`, 06 → Margin) is |total − DC| or |A − B|; a tie shows `by 0`.
`--secret` prefixes `SECRET` and logs the delta as `(GM)`.

Phase 16 (02 → Dice → Pre-rolls): `--d20 14,6` reports two dice; with one die and
advantage or disadvantage (asked for, or from exhaustion, a load, inspiration …) the
second die is rolled here, in the open (`d20 (14, tool 9)→14`). `--rolled-as <skill>` on
`check`/`save`/`contest` reads a reported total as that skill's: its bonus comes off and
the checked skill's goes on (`Kira investigation (reported as perception total 17): d20
12+3=15 …`). With `crit-die: on` every crit of `atk` rolls the crit die (crit.py;
`--crit-die N` types in a physical die).

Phase 14: `check PC skill --vs <npc> --ask none|free|minor|major …` is a social check
(social.py: the DC from the NPC's attitude, leverage, flair, the wall; the number after
the skill is then the player's total). `atk` from a creature with `hidden N` has
advantage and gives it away (hiding.py); under `environment: underwater` the weapon
rules apply (hazard.underwater_attack: disadvantage, or a miss past normal range).
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


def _dice(d20):
    """--d20 as given: None, an int, or a tuple of one or two ints."""
    if d20 is None:
        return None
    return tuple(d20) if isinstance(d20, (tuple, list)) else (d20,)


def _rolled_as(c, rolled_as):
    """(label, bonus) of the skill / ability / `<ability> save` a pre-roll was reported
    as (02 → Dice → Pre-rolls), or None."""
    if not rolled_as:
        return None
    key = creatures.skill_key(rolled_as)
    save = re.fullmatch(r"(\w+)-save", key)
    if save and save.group(1) in creatures.ABILITIES:
        ab = creatures.ABILITIES[save.group(1)]
        return f"{ab.upper()} save", c.save_bonus(ab)
    if key not in creatures.ABILITIES and key not in creatures.SKILLS:
        raise RollError(f"--rolled-as: unknown skill {rolled_as!r}")
    return key, c.skill_bonus(key)


def _d20(roller, c, bonus, mode, d20, total, state, rules, label="", reported_as=None):
    """The d20 for one side: reported for a PC (--d20/--total), else rolled by the GM
    (NPCs always; PCs only under gm-rolls-all). A reported die under adv/dis gets its
    second die rolled (dice.reported_pair); `reported_as` = (label, bonus) converts a
    total reported for another skill (the result's `.asked` names it)."""
    if d20 is not None or total is not None:
        if not c.is_pc:
            raise RollError(f"--d20/--total are for the PC side; {c.name} is an NPC (the GM rolls)")
        asked = ""
        if reported_as is not None:
            skill, old = reported_as
            if d20 is None:
                asked = f"reported as {skill} total {total}"
                die = total - old
                if 1 <= die <= 20:      # the die the player saw
                    d20, total = (die,), None
                else:
                    total = die + bonus
            else:
                asked = f"reported as {skill}"
        if d20 is not None:
            try:
                r = dice.reported_pair(bonus, _dice(d20), mode, roller)
            except dice.DiceError as e:
                raise RollError(str(e)) from None
        else:
            r = dice.reported(bonus, total=total)
        r.asked = asked
        return r
    if reported_as is not None:
        raise RollError("--rolled-as goes with the player's --total (or --d20)")
    if c.is_pc and resolve.dice_mode(state.front, rules) != "gm-rolls-all":
        raise RollError(f"{c.name}{label} rolls their own d20: pass --d20 N or --total N "
                        "(or set dice-mode: gm-rolls-all)")
    return roller.d20(bonus, mode)


def _exhaustion(c, kind, mode):
    """(mode, bonus change, note) after the creature's exhaustion (02 → Table mechanics →
    Exhaustion): 2014 disadvantage on checks (1+) / attacks and saves (3+); 2024 −2 per
    level. The note is printed even when the player reports the d20."""
    level = c.exhaustion()
    if not level:
        return mode, 0, ""
    ruleset = campaign.settings().get("exhaustion", "2014")
    dis, penalty, note = resolve.exhaustion_d20(level, kind, ruleset)
    new = resolve.with_disadvantage(mode, dis)
    if dis and mode == "adv":
        note += ", adv and dis cancel"
    return new, penalty, note


def _situational(c, kind, mode, ability=None, atk=None, dist=None, insp=False):
    """Phase 15 sources of advantage/disadvantage after exhaustion: a heavy load
    (`encumbrance: variant`), strong wind on a ranged attack (`weather: on`, outdoors),
    and spent inspiration (`--insp`, last, so nothing is spent when an earlier check
    refuses). -> (mode, [notes])."""
    notes = []
    from lib import encumbrance
    try:
        doc = c.doc
    except Exception:  # noqa: BLE001 — a row with no file
        doc = None
    dis = []
    enc = encumbrance.disadvantage(doc, kind, ability)
    if enc:
        dis.append(enc)
    if kind == "attack" and atk is not None:
        import weather
        wind = weather.ranged_note(atk, dist)
        if wind:
            dis.append(wind)
    for note in dis:
        cancel = mode == "adv"
        mode = resolve.with_disadvantage(mode, True)
        notes.append(note + (", adv and dis cancel" if cancel else ""))
    if insp:
        import inspiration
        mode, note = inspiration.spend(c, mode)
        notes.append(note)
    return mode, notes


def _outcome(outcome, note, margin=None):
    """`SUCCESS by 6 (note)`: the margin is how far the total landed from the DC or the
    other side (02 → Player plans, outcome tiers); None leaves it out (total cover)."""
    by = f" by {abs(margin)}" if margin is not None else ""
    return f"{outcome}{by} ({note})" if note else f"{outcome}{by}"


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
           apply=True, seed=None, roller=None, insp=False, crit_face=None):
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
    dist = None
    far, normal = _reach(a, atk)
    if a.pos is not None and t.pos is not None:
        dist = _distance(a, t)
        if dist > far:
            line = f"[{head}: out of reach ({dist:g} ft)]"
            return [line], {"out_of_reach": True, "distance": dist}
        long_range = normal is not None and dist > normal
    import hazard
    import hiding
    uw_dis, uw_miss, uw_note = hazard.underwater_attack(a, atk, dist, far, normal)   # Phase 14
    if uw_miss:
        body = f"{head}: {uw_miss} — MISS"
        journal.log_delta(f"atk {body}")
        return [f"[{body}]"], {"attacker": a.name, "target": t.name, "outcome": "MISS", "note": uw_miss}
    hidden = hiding.hidden_total(mutations._conds_from_cell(a.combat_row.get("conditions")) if a.combat_row
                                 else [str(x) for x in (a.front.get("conditions") or [])])
    mode, extra, mode_notes = resolve.attack_mode(mode, long_range=long_range,
                                                  flanked=_flanked(state, a, t), rules=rules)
    if hidden is not None or uw_dis:   # an unseen attacker has advantage; underwater weapons may not
        cancelled = any("cancel" in x for x in mode_notes)
        adv, dis = mode == "adv" or hidden is not None, mode == "dis" or bool(uw_dis)
        mode = None if cancelled or (adv and dis) else ("adv" if adv else "dis" if dis else None)
        if hidden is not None:
            mode_notes.append(f"hidden ({hidden}): advantage")
        if uw_note:
            mode_notes.append(uw_note)
        if adv and dis and not cancelled:
            mode_notes.append("adv and dis cancel")
    elif uw_note:
        mode_notes.append(uw_note)
    mode, exh_bonus, exh_note = _exhaustion(a, "attack", mode)
    if exh_note:
        mode_notes = mode_notes + [exh_note]
    import supplies
    ammo_line = supplies.spend_ammo(a, atk)   # refuses before the roll when out of ammunition
    mode, more = _situational(a, "attack", mode, atk=atk, dist=dist, insp=insp)
    mode_notes = mode_notes + more
    roll = _d20(roller, a, atk["hit"] + extra + exh_bonus, mode, d20, total, state, rules)
    outcome, note = resolve.attack(roll, ac, attacker_is_pc=a.is_pc, target_is_pc=t.is_pc,
                                   cover=cover, rules=rules)
    note = ", ".join(x for x in mode_notes + [roll.note, note] if x)
    eff = resolve.effective_ac(ac, cover)
    ac_txt = f"AC {eff if eff is not None else ac}"
    body = f"{head}: {roll.text} vs {ac_txt} — {_outcome(outcome, note)}"
    data = {"attacker": a.name, "target": t.name, "attack": atk["name"], "roll": roll.as_dict(),
            "ac": eff, "outcome": outcome, "note": note}
    extra_lines = [ammo_line] if ammo_line else []
    if hidden is not None:
        gone = hiding.drop_hidden(a.name)
        if gone:
            extra_lines.append(gone)
    if outcome not in ("HIT", "CRIT"):
        journal.log_delta(f"atk {body}")
        return [f"[{body}]"] + extra_lines, data
    import crit
    plan = None
    if outcome == "CRIT" and crit.enabled():   # Phase 16: the crit die replaces the crit
        plan = crit.plan(t, roller, crit_face)
        body += f" · {plan.label()}"
        data["crit_die"] = {"die": plan.die, "roll": plan.n, "result": plan.row.result,
                            "effect": plan.row.effect, "damage": plan.damage,
                            "effects": [c for c, _ in plan.effects], "notes": plan.notes}
        if plan.notes:
            body += f" ({'; '.join(plan.notes)})"
        if plan.kill:
            return _crit_kill(t, body, data, plan, rules, apply, extra_lines)
        amount, dtext = crit.damage(roller, atk["damage"], plan.damage, rules)
    elif outcome == "CRIT":
        amount, dtext = resolve.crit_damage(roller, atk["damage"], rules)
    else:
        res = roller.roll(atk["damage"])
        amount, dtext = res.total, res.body
    dtype = atk["dtype"]
    body += f" · {amount}" + (f" {dtype}" if dtype else "")
    data.update({"damage": amount, "damage_type": dtype, "damage_roll": dtext})
    crit_word = (f" crit die {plan.damage}" if plan else " crit") if outcome == "CRIT" else ""
    roll_note = f" [{atk['damage']}{crit_word}: {dtext}]"
    if not apply:
        journal.log_delta(f"atk {body}{roll_note} · not applied")
        return [f"[{body} · not applied]"] + extra_lines, data
    _, hp_data = mutations.dmg(t.name, amount, dtype, rules=rules, log=False, crit=outcome == "CRIT")
    if hp_data.get("resist_note"):
        body += f" → {hp_data['applied']} ({hp_data['resist_note']})"
    body += f" · {hp_data['tail']}"
    data["hp"] = hp_data
    journal.log_delta(f"atk {body}{roll_note}")
    after = []
    if plan is not None:
        after = crit.spend_lr(t, plan)
        if hp_data.get("hp", 1) > 0 or not plan.effects:
            after += crit.effects(t, plan)
        else:
            after.append(f"[crit die: {t.name} is down, so {', '.join(c for c, _ in plan.effects)} doesn't apply]")
    return [f"[{body}]"] + extra_lines + hp_data.get("after", []) + after, data


def _crit_kill(t, body, data, plan, rules, apply, extra_lines):
    """The crit die's `kill` (no damage roll): HP to 0; a PC per `crit-die-pcs`."""
    import crit
    if not apply:
        journal.log_delta(f"atk {body} · not applied")
        return [f"[{body} · not applied]"] + extra_lines, data
    tail, after, hp_data = crit.kill(t, rules)
    body += f" · slain · {tail}"
    data["hp"] = hp_data
    journal.log_delta(f"atk {body}")
    return [f"[{body}]"] + extra_lines + after, data


def cmd_atk(ctx):
    a = ctx.args
    lines, data = attack(a.attacker, a.target, with_=a.with_, mode=_mode(a), cover=a.cover,
                         d20=a.d20, total=a.total, apply=not a.no_apply, roller=ctx.roller, insp=a.insp,
                         crit_face=a.crit_die)
    if not data.get("out_of_reach"):
        import turn
        lines += turn.after_attack(data.get("attacker", a.attacker), bonus=a.bonus) or []
    for line in lines:
        ctx.emit(line)
    ctx.result = data


# ---------- save / check ----------

def saving_throw(name, ability, dc, *, mode=None, d20=None, total=None, by=None, cover=None,
                 secret=False, seed=None, roller=None, insp=False, rolled_as=None):
    state = campaign.load_state()
    rules = resolve.active_keys()
    c = creatures.get(name, state)
    ab = creatures.ABILITIES.get(ability.lower())
    if not ab:
        raise RollError(f"save: unknown ability {ability!r} (str dex con int wis cha)")
    dc_from_pc = creatures.get(by, state).is_pc if by else False
    mode, exh_bonus, exh_note = _exhaustion(c, "save", mode)
    bonus = c.save_bonus(ab) + exh_bonus
    mode, more = _situational(c, "save", mode, ability=ab, insp=insp)
    roll = _d20(roller or dice.Roller(seed), c, bonus, mode, d20, total, state, rules,
                reported_as=_rolled_as(c, rolled_as))
    outcome, note = resolve.save(roll, dc, saver_is_pc=c.is_pc, dc_from_pc=dc_from_pc,
                                 cover=cover, ability=ab, rules=rules)
    note = ", ".join(x for x in [exh_note] + more + [roll.note, note] if x)
    shown = resolve.save_total(roll, cover, ab)
    rtext = roll.text if shown == roll.total else f"{roll.text} → {shown}"
    margin = None if note.endswith("total cover") else shown - dc
    asked = f" ({roll.asked})" if getattr(roll, "asked", "") else ""
    body = f"{c.name} {ab.upper()} save{asked}: {rtext} vs DC {dc} — {_outcome(outcome, note, margin)}"
    _log(body, secret)
    import conditions_ext
    after = conditions_ext.after_save(c.name, ab, dc, outcome)
    return _wrap(body, secret), {"name": c.name, "ability": ab, "dc": dc, "roll": roll.as_dict(),
                                 "outcome": outcome, "note": note,
                                 "margin": None if margin is None else abs(margin), "after": after}


def ability_check(name, skill, dc, *, mode=None, d20=None, total=None, vs=None, secret=False,
                  seed=None, roller=None, insp=False, rolled_as=None):
    state = campaign.load_state()
    rules = resolve.active_keys()
    c = creatures.get(name, state)
    vs_pc = creatures.get(vs, state).is_pc if vs else False
    mode, exh_bonus, exh_note = _exhaustion(c, "check", mode)
    bonus = c.skill_bonus(skill) + exh_bonus
    key = creatures.skill_key(skill)
    mode, more = _situational(c, "check", mode, ability=creatures.ABILITIES.get(key) or creatures.SKILLS.get(key),
                              insp=insp)
    if key == "perception":
        import weather
        more = more + [x for x in [weather.perception_note()] if x]
    roll = _d20(roller or dice.Roller(seed), c, bonus, mode, d20, total, state, rules,
                reported_as=_rolled_as(c, rolled_as))
    outcome, note = resolve.check(roll, dc, checker_is_pc=c.is_pc, vs_pc=vs_pc, rules=rules)
    note = ", ".join(x for x in [exh_note] + more + [roll.note, note] if x)
    margin = roll.total - dc
    asked = f" ({roll.asked})" if getattr(roll, "asked", "") else ""
    body = (f"{c.name} {creatures.skill_key(skill)}{asked}: {roll.text} vs DC {dc} — "
            f"{_outcome(outcome, note, margin)}")
    _log(body, secret)
    return _wrap(body, secret), {"name": c.name, "skill": creatures.skill_key(skill), "dc": dc,
                                 "roll": roll.as_dict(), "outcome": outcome, "note": note,
                                 "margin": abs(margin)}


def cmd_save(ctx):
    a = ctx.args
    line, data = saving_throw(a.target, a.ability, a.dc, mode=_mode(a), d20=a.d20, total=a.total,
                              by=a.by, cover=a.cover, secret=a.secret, roller=ctx.roller, insp=a.insp,
                              rolled_as=a.rolled_as)
    ctx.emit(line)
    for extra in data.get("after", []):
        ctx.emit(extra)
    ctx.result = data


def _check_args(a):
    """Split `check`'s positionals: the first number is the DC (the player's total for a
    social check, `--ask`), adv/dis words are the mode."""
    words = [w for w in [a.dc] + list(a.mode or []) + list(getattr(a, "extra", None) or []) if w is not None]
    nums = [w for w in words if re.fullmatch(r"-?\d+", w)]
    a.mode = [w for w in words if w not in nums]
    if len(nums) > 1:
        raise RollError(f"check: unexpected {' '.join(nums[1:])!r}")
    return int(nums[0]) if nums else None


def cmd_check(ctx):
    a = ctx.args
    number = _check_args(a)
    social = a.ask is not None or a.core
    if social:   # 02 → Social stakes: the DC comes from the NPC's attitude and the ask
        if not a.vs:
            raise RollError("check --ask: name the NPC with --vs <npc>")
        if number is not None and (a.d20 is not None or a.total is not None):
            raise RollError("check --ask: give the player's total once (<total>, --total or --d20)")
        import social as social_mod
        lines, data = social_mod.check(
            a.target, a.skill, a.vs, a.ask or "none", leverage=a.leverage, flair=a.flair, pitch=a.pitch,
            appeal=a.appeal, grates=a.grates, why=a.why, goal=a.goal, core=a.core, dc=a.dc_base,
            d20=a.d20, total=a.total if number is None else number, mode=_mode(a), roller=ctx.roller,
            insp=a.insp, rolled_as=a.rolled_as)
        for line in lines:
            ctx.emit(line)
        ctx.result = data
        return
    if number is None:
        raise RollError("check NAME SKILL DC: the DC is missing (or --ask … --vs <npc> for a social check)")
    line, data = ability_check(a.target, a.skill, number, mode=_mode(a), d20=a.d20, total=a.total,
                               vs=a.vs, secret=a.secret, roller=ctx.roller, insp=a.insp,
                               rolled_as=a.rolled_as)
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
            d20b=None, totalb=None, secret=False, seed=None, roller=None, rolled_as=None):
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
    given_a = a_given != (None, None)
    mode, a_exh, a_note = _exhaustion(a, "check", mode)
    a_roll = _d20(roller, a, a.skill_bonus(a_skill) + a_exh, mode, *a_given, state, rules,
                  reported_as=_rolled_as(a, rolled_as) if given_a else None)
    a_note = ", ".join(x for x in (getattr(a_roll, "asked", ""), a_note, a_roll.note) if x)
    a_txt = f"{a.name} {creatures.skill_key(a_skill)} {a_roll.text}" + (f" ({a_note})" if a_note else "")
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
            by = f" by {abs(a_roll.total - p)}"
            verdict = f"{who} wins{by}" + (f" ({note})" if note else "") if who else f"TIE ({note})"
            parts.append(f"{c.name} {p} — {verdict}")
            results.append({"name": c.name, "passive": p, "winner": who or "TIE", "note": note,
                            "margin": abs(a_roll.total - p)})
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
    b_as = rolled_as if (not given_a and b_given != (None, None)) else None   # --rolled-as follows --d20/--total
    b_mode, b_exh, b_note = _exhaustion(b, "check", None)
    b_roll = _d20(roller, b, b.skill_bonus(b_skill) + b_exh, b_mode, *b_given, state, rules,
                  reported_as=_rolled_as(b, b_as))
    b_note = ", ".join(x for x in (getattr(b_roll, "asked", ""), b_note, b_roll.note) if x)
    win, note = resolve.contest(a_roll.total, b_roll.total, a_is_pc=a.is_pc, b_is_pc=b.is_pc,
                                rules=rules)
    b_txt = f"{b.name} {creatures.skill_key(b_skill)} {b_roll.text}" + (f" ({b_note})" if b_note else "")
    if win == "TIE":
        verdict = f"TIE ({note})"
    else:
        by = f" by {abs(a_roll.total - b_roll.total)}"
        verdict = f"{a.name if win == 'A' else b.name} wins{by}" + (f" ({note})" if note else "")
    body = f"{a_txt} vs {b_txt} — {verdict}"
    _log(body, secret)
    return _wrap(body, secret), {"a": a.name, "b": b.name, "a_roll": a_roll.as_dict(),
                                 "b_roll": b_roll.as_dict(), "winner": win, "note": note,
                                 "margin": abs(a_roll.total - b_roll.total)}


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
                         roller=ctx.roller, rolled_as=a.rolled_as)
    ctx.emit(line)
    ctx.result = data


# ---------- registration ----------

def d20_arg(text):
    """`14` or `14,6` (two dice for advantage/disadvantage, Phase 16)."""
    parts = [x for x in re.split(r"[,\s]+", str(text).strip()) if x]
    if not 1 <= len(parts) <= 2 or not all(re.fullmatch(r"\d+", x) for x in parts):
        raise ValueError(text)
    return tuple(int(x) for x in parts)


d20_arg.__name__ = "d20"   # argparse's message: invalid d20 value


def _pc_side(p, insp=False, rolled_as=False):
    x = p.add_mutually_exclusive_group()
    x.add_argument("--d20", type=d20_arg, help="the player's natural d20, or two (14,6) for adv/dis")
    x.add_argument("--total", type=int, help="the player's total")
    if insp:
        p.add_argument("--insp", action="store_true", help="spend inspiration on this d20 (Phase 15)")
    if rolled_as:
        p.add_argument("--rolled-as", dest="rolled_as",
                       help="the skill the player rolled for (a pre-roll; its bonus comes off)")


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
    p.add_argument("--bonus", action="store_true", help="a bonus-action attack (off-hand, etc.)")
    p.add_argument("--crit-die", dest="crit_die", type=int, help="the crit die's face, from a physical die")
    _pc_side(p, insp=True)
    p.set_defaults(func=cmd_atk)

    p = sub.add_parser("save", parents=[g], help="save NAME ABILITY DC [adv|dis]")
    p.add_argument("target"); p.add_argument("ability"); p.add_argument("dc", type=int)
    p.add_argument("mode", nargs="*")
    p.add_argument("--by", help="whose DC it is (a PC's: an NPC tie fails, house rule)")
    p.add_argument("--cover", choices=["half", "three-quarters", "total"])
    p.add_argument("--secret", action="store_true")
    _pc_side(p, insp=True, rolled_as=True)
    p.set_defaults(func=cmd_save)

    p = sub.add_parser("check", parents=[g], help="check NAME SKILL DC [adv|dis] [--secret] | "
                       "check PC SKILL --vs NPC --ask SIZE [… <total>]")
    p.add_argument("target"); p.add_argument("skill"); p.add_argument("dc", nargs="?")
    p.add_argument("mode", nargs="*")
    p.add_argument("--vs", help="the DC is this PC's score (passive/AC): an NPC tie fails; "
                                "with --ask: the NPC being asked")
    p.add_argument("--secret", action="store_true")
    # social stakes (Phase 14; social.py)
    p.add_argument("--ask", choices=["none", "free", "minor", "major"], help="the size of the ask")
    p.add_argument("--leverage", type=int, default=0, help="-5..5: the pitch's reason for this NPC")
    p.add_argument("--flair", type=int, default=0, help="0-3 (GM-only score)")
    p.add_argument("--pitch", help="a short tag for the pitch (a repeat scores 0)")
    p.add_argument("--appeal", help="the kind of pitch: audacity honesty flattery humour piety coin")
    p.add_argument("--grates", action="store_true", help="the pitch grates on this NPC (flair −1)")
    p.add_argument("--why", help="the argument made (a new one is a different approach)")
    p.add_argument("--goal", help="the goal it serves (counted toward the wall)")
    p.add_argument("--core", action="store_true", help="the ask would break the core scenario")
    p.add_argument("--dc", dest="dc_base", type=int, help="the starting DC (social-dcs: gm)")
    _pc_side(p, insp=True, rolled_as=True)
    p.set_defaults(func=cmd_check, take_extra=True)

    p = sub.add_parser("contest", parents=[g], help="contest A SKILL B SKILL | contest A SKILL passive")
    p.add_argument("a_name"); p.add_argument("a_skill")
    p.add_argument("rest", nargs="*", help="B SKILL | passive [sense]; adv | dis")
    p.add_argument("--mode", dest="mode", action="append", choices=["adv", "dis"],
                   help="alias for a bare adv/dis")
    p.add_argument("--secret", action="store_true")
    _pc_side(p, rolled_as=True)
    p.add_argument("--d20b", type=d20_arg, help="PC vs PC: the second PC's natural d20 (or two)")
    p.add_argument("--totalb", type=int, help="PC vs PC: the second PC's total")
    p.set_defaults(func=cmd_contest)
