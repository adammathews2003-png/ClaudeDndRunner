"""`gm.py odds atk|save|check|contest …` — exact probabilities, never simulation
(planning/06 → Spoiler support; 02 → Spoilers "Guess" claims; plan.md Phase 7 item 7).

Same arguments as the resolving commands; every d20 outcome (1–20, or the 400 pairs
for adv/dis) goes through lib/resolve.py, so table rules and ties-go-to-PC apply
exactly as in play. Damage is an exact distribution (dice convolution; crits double
the dice, or max+roll under that table rule).

    odds atk Kira Veskar [--with dagger] [adv|dis] [--cover half] [--sneak 2d6]
      → [ODDS Kira → Veskar: hit 60% (crit 5%) · dmg avg 12.5 · drops him (22 HP) in 1 hit 0% · in 2 hits 41%]
    odds check Mara insight 12 [adv|dis] [--vs Kira] → [ODDS Mara insight ≥12: 55%]
    odds save Kael dex 14 [adv|dis] [--by Veskar]    → [ODDS Kael DEX save vs DC 14: 50%]
    odds contest Kira stealth Mara perception          → [ODDS Kira wins 68% (ties→PC)]
"""
import re
from collections import defaultdict

from lib import campaign, creatures, dice, resolve
from lib.errors import ToolError


class OddsError(ToolError):
    pass


def d20_dist(mode=None):
    """{natural: probability}."""
    if mode == "adv":
        return {k: (2 * k - 1) / 400 for k in range(1, 21)}
    if mode == "dis":
        return {k: (41 - 2 * k) / 400 for k in range(1, 21)}
    return {k: 1 / 20 for k in range(1, 21)}


def _roll(nat, bonus):
    return dice.D20(nat, [nat], bonus, nat + bonus, "")


def dice_dist(expr, double=False, max_extra=False):
    """Exact distribution of a dice expression like '1d6+3' / '2d6' ({total: p})."""
    dist = {0: 1.0}
    for sign, n, m, flat in re.findall(r"([+-]?)\s*(?:(\d*)d(\d+)|(\d+))", expr.replace(" ", "")):
        s = -1 if sign == "-" else 1
        if m:
            count = int(n or 1) * (2 if double else 1)
            sides = int(m)
            if max_extra:
                dist = {k + s * int(n or 1) * sides: p for k, p in dist.items()}
                count = int(n or 1)
            for _ in range(count):
                new = defaultdict(float)
                for k, p in dist.items():
                    for face in range(1, sides + 1):
                        new[k + s * face] += p / sides
                dist = dict(new)
        elif flat:
            dist = {k + s * int(flat): p for k, p in dist.items()}
    return {max(0, k): p for k, p in dist.items()}


def _convolve(a, b):
    out = defaultdict(float)
    for k1, p1 in a.items():
        for k2, p2 in b.items():
            out[k1 + k2] += p1 * p2
    return dict(out)


def _mode(words):
    words = [w.lower() for w in words or []]
    if "adv" in words and "dis" in words:
        return None
    return "adv" if "adv" in words else ("dis" if "dis" in words else None)


def pct(p):
    v = round(p * 100)
    return "<1%" if 0 < p < 0.005 else (">99%" if p < 1 and v >= 100 else f"{v}%")


def atk(a_name, t_name, with_=None, mode=None, cover=None, sneak=None):
    state = campaign.load_state()
    rules = resolve.active_keys()
    a = creatures.get(a_name, state)
    t = creatures.get(t_name, state)
    att = a.attack(with_)
    ac = t.ac()
    p_hit = p_crit = 0.0
    for nat, p in d20_dist(mode).items():
        out, _ = resolve.attack(_roll(nat, att["hit"]), ac, attacker_is_pc=a.is_pc, target_is_pc=t.is_pc,
                                cover=cover, rules=rules)
        if out == "CRIT":
            p_crit += p
        elif out == "HIT":
            p_hit += p
    expr = att["damage"] + (f"+{sneak}" if sneak else "")
    crit_rule = (rules.get("crit-damage") or {}).get("value", "double")
    normal = dice_dist(expr)
    crit = dice_dist(expr, double=crit_rule == "double", max_extra=crit_rule != "double")
    per = defaultdict(float)
    per[0] += 1 - p_hit - p_crit
    for k, p in normal.items():
        per[k] += p_hit * p
    for k, p in crit.items():
        per[k] += p_crit * p
    avg = sum(k * p for k, p in normal.items())
    hp = None
    if t.combat_row is not None:
        cell = creatures.parse_hp_cell(t.combat_row.get("hp", ""))
        hp = cell[0] if cell else None
    if hp is None:
        h = t.front.get("hp") if isinstance(t.front.get("hp"), dict) else None
        hp = int(h["current"]) if h else (t.monster.hp if t.monster is not None else None)
    bits = [f"hit {pct(p_hit + p_crit)} (crit {pct(p_crit)})", f"dmg avg {avg:.1f}"]
    if hp:
        one = sum(p for k, p in per.items() if k >= hp)
        two = sum(p for k, p in _convolve(per, per).items() if k >= hp)
        who = "them" if t.is_pc else "it" if t.ref.startswith("srd:") else "them"
        bits.append(f"drops {who} ({hp} HP) in 1 hit {pct(one)} · in 2 hits {pct(two)}")
    line = f"[ODDS {a.name} → {t.name} ({att['name']}): " + " · ".join(bits) + "]"
    return line, {"hit": p_hit + p_crit, "crit": p_crit, "avg": avg}


def check(name, skill, dc, mode=None, vs=None):
    state = campaign.load_state()
    rules = resolve.active_keys()
    c = creatures.get(name, state)
    vs_pc = creatures.get(vs, state).is_pc if vs else False
    bonus = c.skill_bonus(skill)
    p = sum(pr for nat, pr in d20_dist(mode).items()
            if resolve.check(_roll(nat, bonus), dc, checker_is_pc=c.is_pc, vs_pc=vs_pc, rules=rules)[0] == "SUCCESS")
    return f"[ODDS {c.name} {creatures.skill_key(skill)} ≥{dc}: {pct(p)}]", {"p": p}


def save(name, ability, dc, mode=None, by=None):
    state = campaign.load_state()
    rules = resolve.active_keys()
    c = creatures.get(name, state)
    ab = creatures.ABILITIES.get(ability.lower())
    if not ab:
        raise OddsError(f"odds save: unknown ability {ability!r}")
    dc_from_pc = creatures.get(by, state).is_pc if by else False
    bonus = c.save_bonus(ab)
    p = sum(pr for nat, pr in d20_dist(mode).items()
            if resolve.save(_roll(nat, bonus), dc, saver_is_pc=c.is_pc, dc_from_pc=dc_from_pc, ability=ab,
                            rules=rules)[0] == "SAVE")
    return f"[ODDS {c.name} {ab.upper()} save vs DC {dc}: {pct(p)}]", {"p": p}


def contest(a_name, a_skill, b_name, b_skill, mode=None):
    state = campaign.load_state()
    rules = resolve.active_keys()
    a, b = creatures.get(a_name, state), creatures.get(b_name, state)
    ba, bb = a.skill_bonus(a_skill), b.skill_bonus(b_skill)
    win = tie = 0.0
    note = ""
    for na, pa in d20_dist(mode).items():
        for nb, pb in d20_dist().items():
            w, n = resolve.contest(na + ba, nb + bb, a_is_pc=a.is_pc, b_is_pc=b.is_pc, rules=rules)
            if w == "A":
                win += pa * pb
            elif w == "TIE":
                tie += pa * pb
            if n and "tie" in n:
                note = " (ties→PC)"
    tail = f" · tie {pct(tie)}" if tie else ""
    return f"[ODDS {a.name} wins {pct(win)}{note}{tail}]", {"p": win, "tie": tie}


def cmd_odds(ctx):
    a = ctx.args
    words = a.rest + (["adv"] if a.adv else []) + (["dis"] if a.dis else [])
    mode = _mode(words)
    rest = [w for w in words if w.lower() not in ("adv", "dis")]
    if a.kind == "atk":
        if len(rest) != 2:
            raise OddsError("odds atk <attacker> <target> [--with x] [adv|dis] [--cover half] [--sneak 2d6]")
        line, data = atk(rest[0], rest[1], a.with_, mode, a.cover, a.sneak)
    elif a.kind == "check":
        if len(rest) != 3 or not rest[2].isdigit():
            raise OddsError("odds check <name> <skill> <DC> [adv|dis] [--vs pc]")
        line, data = check(rest[0], rest[1], int(rest[2]), mode, a.vs)
    elif a.kind == "save":
        if len(rest) != 3 or not rest[2].isdigit():
            raise OddsError("odds save <name> <ability> <DC> [adv|dis] [--by pc]")
        line, data = save(rest[0], rest[1], int(rest[2]), mode, a.by)
    else:
        if len(rest) != 4:
            raise OddsError("odds contest <A> <skill> <B> <skill> [adv|dis]")
        line, data = contest(rest[0], rest[1], rest[2], rest[3], mode)
    ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("odds", parents=[g], help="exact odds: odds atk|save|check|contest …")
    p.add_argument("kind", choices=["atk", "save", "check", "contest"])
    p.add_argument("rest", nargs="+")
    p.add_argument("--with", dest="with_")
    p.add_argument("--cover")
    p.add_argument("--sneak")
    p.add_argument("--vs")
    p.add_argument("--by")
    p.add_argument("--adv", action="store_true", help="advantage (same as a bare `adv` before any --flag)")
    p.add_argument("--dis", action="store_true")
    p.set_defaults(func=cmd_odds)
