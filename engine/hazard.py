"""Traps and environmental hazards (docs/design/02 → Table mechanics → Phase 14 → Traps
and hazards; 04 → Scene state added (`TRAP` lines, `environment:`); 06 → Table mechanics
→ Phase 14; plan.md Phase 14 item 6).

    trap trigger <id> [--who Kael] [<save total>]   resolve the trap's effect on a creature
    trap disarm <id> --who Kira <total>             against its disarm DC; a miss by 5+ sets it off
    trap status                                     the site's traps (GM-only lines)
    hazard fall <who> <ft>                          1d6 per 10 ft (max 20d6), lands prone
    hazard breath <who>                             holding breath 1 + CON min (≥ 30 s), then choking
    hazard env extreme-cold|extreme-heat|underwater|thin-air|none

A trap is a `## Hidden` line of a location:
`- DC 15: TRAP pit (cellar) · trigger: … · disarm: DC 12 thieves' tools · effect: DEX save DC
13 or fall 20 ft · state: armed` (the scope may also stand as `DC 15 (cellar):`). The DC is
the passive Perception to notice it (scene enter compares it, as for any Hidden line).
`effect:` clauses (`;` or ` and ` between them): `<ABIL> save DC N or <consequence>`
(`(half on a success)` for damage), or a bare consequence; a consequence is `fall N ft`,
`NdM <type>` damage, or a condition (`poisoned 1h`, `restrained`); `+N to hit, NdM <type>`
is an attack roll against AC. The tool keeps `state:` (armed | triggered | disarmed |
spent) on the line and rolls everything but a player's d20: a PC's save without a total
is asked for and nothing changes until it comes. `(GM …)` notes on the line and the
disarm details never reach a public log line; `trap status` prints `(GM)` lines.

Hazards follow the SRD: falling 1d6 bludgeoning per 10 ft (at most 20d6) and prone;
holding breath 1 + CON modifier minutes (at least 30 s), then CON modifier rounds of
choking (at least 1), then 0 HP and dying (the clock and `combat next` run the
`holding-breath` and `choking` conditions down and call `expiry_lines`). `environment:`
in current.md: extreme cold and heat ask a CON save each hour from `environment-since`
for every PC not exempt (cold: cold-weather gear or cold resistance; heat: fire
resistance, heat adaptation, or water while supplies are tracked); cold DC 10, heat 5 (+1
each hour after the first). `underwater`: roll.attack applies the attack rules (`underwater_attack`) and
fire damage is resisted (mutations).

Python API: `env()`, `env_lines(old, new, docs)` (clock), `expiry_lines(pairs)` (clock,
combat), `underwater_attack(c, atk, dist, far, normal)` (roll), `traps(frame)`,
`parse_trap(line)` (lint, scene).
"""
import re

from lib import campaign, creatures, dice, gametime, geo, journal, md
from lib.errors import ToolError
import mutations

_TRAP = re.compile(r"^\s*-\s*DC\s*(\d+)\s*(?:\(([\w-]+)\))?\s*:\s*TRAP\s+([\w-]+)\s*(?:\(([\w-]+)\))?\s*(.*)$",
                   re.I)
_GM = re.compile(r"\s*\(GM\b[^)]*\)", re.I)
_SAVE = re.compile(r"^(str|dex|con|int|wis|cha)\w*\s+save\s+DC\s*(\d+)\s+or\s+(.+)$", re.I)
_ATTACK = re.compile(r"^\+(\d+)\s+to hit,?\s+(.+)$", re.I)
_FALL = re.compile(r"^fall\s+(\d+)\s*ft\.?$", re.I)
_DMG = re.compile(r"^(\d*d\d+(?:\s*[+-]\s*\d+)?)\s+([a-z]+)$", re.I)
_COND = re.compile(r"^([a-z][\w-]*)(?:\s+(\d+[rmh]))?$", re.I)
STATES = ("armed", "triggered", "disarmed", "spent")
ENVS = ("none", "extreme-cold", "extreme-heat", "underwater", "thin-air")
MELEE_OK = ("dagger", "javelin", "shortsword", "spear", "trident")
RANGED_OK = ("crossbow", "net", "javelin", "spear", "trident", "dart")


class HazardError(ToolError):
    pass


def _short(c):
    return c.name.split()[0] if c.is_pc else c.name


def strip_gm(text):
    """A trap's text without `(GM …)` notes (what may reach players)."""
    return _GM.sub("", text or "").strip()


# ---------- traps ----------

class Trap:
    def __init__(self, frame, index, m):
        self.frame = frame
        self.index = index
        self.notice = int(m.group(1))
        self.area = m.group(2) or m.group(4) or None
        self.id = m.group(3).lower()
        self.fields = {}
        for part in m.group(5).split("·"):
            k, sep, v = part.partition(":")
            if sep and k.strip():
                self.fields[k.strip().lower()] = v.strip()
        self.state = (self.fields.get("state") or "armed").lower()

    def get(self, key):
        return self.fields.get(key, "")

    def disarm_dc(self):
        m = re.search(r"DC\s*(\d+)", self.get("disarm"), re.I)
        return int(m.group(1)) if m else None


def parse_trap(line):
    """(notice DC, id, area, fields) of a TRAP line, else None."""
    m = _TRAP.match(line)
    if not m:
        return None
    t = Trap(None, -1, m)
    return t


def traps(frame):
    out = []
    span = frame.doc.section("Hidden")
    for i in range(span[0] + 1, span[1]) if span else []:
        m = _TRAP.match(frame.doc.body[i])
        if m:
            out.append(Trap(frame, i, m))
    return out


def _site():
    loc = str(campaign.load_state().front.get("party-location") or "")
    return loc.split("/")[0]


def find(trap_id):
    """The trap `trap_id` at the party's site, else anywhere in locations/."""
    want = trap_id.strip().lower()
    site = _site()
    order = [site] if site and not site.startswith("@") else []
    order += sorted(p.stem for p in (campaign.root() / "locations").glob("*.md") if p.stem != site)
    for slug in order:
        try:
            frame = geo.load(slug)
        except geo.GeoError:
            continue
        for t in traps(frame):
            if t.id == want:
                return t
    raise HazardError(f"trap: no TRAP {trap_id!r} under a ## Hidden (gm.py trap status)")


def _set_state(t, new):
    doc = md.load(t.frame.doc.path)
    line = doc.body[t.index]
    if re.search(r"·\s*state:\s*\w+", line):
        line = re.sub(r"(·\s*state:\s*)\w+", rf"\g<1>{new}", line)
    else:
        line = line.rstrip() + f" · state: {new}"
    doc.body[t.index] = line
    doc.save()


def _victim(who):
    if who:
        return creatures.get(who)
    o = campaign.load_state().front.get("marching-order")
    if isinstance(o, dict) and o.get("front"):
        first = o["front"][0] if isinstance(o["front"], list) else o["front"]
        return creatures.get(str(first))
    pcs = campaign.scene_pcs()
    if not pcs:
        raise HazardError("trap: --who <creature>")
    return creatures.get(str(pcs[0].front.get("name")))


def _clauses(effect):
    return [c.strip() for c in re.split(r";|\s+and\s+", strip_gm(effect)) if c.strip()]


def trigger(trap_id, who=None, total=None, d20=None, roller=None, t=None):
    rng = roller or dice.Roller()
    t = t or find(trap_id)
    if t.state != "armed":
        raise HazardError(f"trap {t.id} is {t.state}, not armed")
    c = _victim(who)
    name = _short(c)
    clauses = _clauses(t.get("effect"))
    if not clauses:
        raise HazardError(f"trap {t.id}: no `effect:` on its line")
    saves = [cl for cl in clauses if _SAVE.match(cl)]
    if saves and c.is_pc and total is None and d20 is None:
        from lib import resolve
        if resolve.dice_mode(campaign.load_state().front) != "gm-rolls-all":
            m = _SAVE.match(saves[0])
            return [f"[trap {t.id} springs on {name}: {m.group(1).upper()} save DC {m.group(2)} — ask for the d20 "
                    f"(gm.py trap trigger {t.id} --who {name} <total>)]"]
    lines = [f"[trap {t.id} triggered · {name}]"]
    journal.log_delta(f"trap {t.id} triggered ({name})")
    journal.log_delta(f"trap {t.id} ({t.frame.slug}): {strip_gm(t.get('effect'))}", gm=True)
    for cl in clauses:
        lines += _apply(cl, c.name, total, d20, rng)
    _set_state(t, "triggered")
    return lines


def _apply(clause, name, total, d20, rng):
    m = _SAVE.match(clause)
    if m:
        import roll
        half = bool(re.search(r"\(half on a success\)", clause, re.I))
        rest = re.sub(r"\s*\(half on a success\)", "", m.group(3), flags=re.I).strip()
        line, data = roll.saving_throw(name, m.group(1), int(m.group(2)), d20=d20, total=total, roller=rng)
        out = [line]
        if data["outcome"] == "SUCCESS":
            if half and _DMG.match(rest):
                out += _consequence(rest, name, rng, half=True)
            return out
        return out + _consequence(rest, name, rng)
    m = _ATTACK.match(clause)
    if m:
        c = creatures.get(name)
        r = rng.d20(int(m.group(1)))
        ac = c.ac()
        from lib import resolve
        outcome, note = resolve.attack(r, ac, attacker_is_pc=False, target_is_pc=c.is_pc)
        hit = outcome in ("HIT", "CRIT")
        line = f"[trap → {_short(c)}: {r.text} vs AC {ac} — {outcome}" + (f" ({note})" if note else "") + "]"
        return [line] + (_consequence(m.group(2).strip(), name, rng) if hit else [])
    return _consequence(clause, name, rng)


def clause_ok(clause):
    """Can the tool resolve this effect clause? (lint)"""
    m = _SAVE.match(clause)
    if m:
        clause = re.sub(r"\s*\(half on a success\)", "", m.group(3), flags=re.I).strip()
    m = _ATTACK.match(clause)
    if m:
        clause = m.group(2).strip()
    return bool(_FALL.match(clause) or _DMG.match(clause) or _COND.match(clause))


def _consequence(text, name, rng, half=False):
    m = _FALL.match(text)
    if m:
        return fall(name, int(m.group(1)), rng)
    m = _DMG.match(text)
    if m:
        res = rng.roll(m.group(1).replace(" ", ""))
        amount = res.total // 2 if half else res.total
        line, data = mutations.dmg(name, amount, m.group(2).lower())
        return [f"[{res.body}" + (" → half" if half else "") + "]", line] + data.get("after", [])
    m = _COND.match(text)
    if m:
        line, data = mutations.cond(name, "+" + m.group(1).lower(), m.group(2))
        return [line] + data.get("after", [])
    return [f"[trap effect for the GM to narrate: {text}]"]


def disarm(trap_id, who, total, roller=None):
    t = find(trap_id)
    if t.state != "armed":
        raise HazardError(f"trap {t.id} is {t.state}, not armed")
    dc = t.disarm_dc()
    if dc is None:
        raise HazardError(f"trap {t.id}: no `disarm: DC N` on its line")
    c = creatures.get(who)
    name = _short(c)
    if total is None:
        if c.is_pc:
            return [f"[trap {t.id}: {name} tries to disarm it — ask for the check total "
                    f"(gm.py trap disarm {t.id} --who {name} <total>)]"]
        bonus = 0
        tool = t.get("disarm").lower()
        skill = "sleight-of-hand" if "thieves" in tool or "sleight" in tool else "investigation"
        r = (roller or dice.Roller()).d20(c.skill_bonus(skill) + bonus)
        total = r.total
    if total >= dc:
        _set_state(t, "disarmed")
        body = f"trap {t.id}: {name} {total} vs DC {dc} — disarmed"
        journal.log_delta(body)
        return [f"[{body}]"]
    if dc - total >= 5:
        body = f"trap {t.id}: {name} {total} vs DC {dc} — missed by {dc - total}: it goes off"
        journal.log_delta(body)
        return [f"[{body}]"] + trigger(t.id, name, roller=roller, t=t)
    body = f"trap {t.id}: {name} {total} vs DC {dc} — not disarmed (still armed; try again)"
    journal.log_delta(body)
    return [f"[{body}]"]


def status():
    site = _site()
    out = []
    try:
        frame = geo.load(site)
        ts = traps(frame)
    except geo.GeoError:
        ts = []
    if not ts:
        return [f"(GM) traps at {site or '?'}: none"]
    out.append(f"(GM) traps at {site}:")
    for t in ts:
        bits = [f"notice DC {t.notice}"] + [f"{k}: {v}" for k, v in t.fields.items() if k != "state"]
        out.append(f"(GM)   {t.id}" + (f" ({t.area})" if t.area else "") + f" · {t.state} · " + " · ".join(bits))
    return out


# ---------- hazards ----------

def fall(name, ft, roller=None):
    rng = roller or dice.Roller()
    c = creatures.get(name)
    n = min(20, max(0, ft) // 10)
    if n == 0:
        body = f"hazard fall {_short(c)} {ft} ft: no damage (under 10 ft)"
        journal.log_delta(body)
        return [f"[{body}]"]
    res = rng.roll(f"{n}d6")
    line, data = mutations.dmg(c.name, res.total, "bludgeoning")
    out = [f"[hazard fall {_short(c)} {ft} ft: {res.body}]", line] + data.get("after", [])
    fresh = creatures.get(c.name)
    words = [str(x).split()[0].lower() for x in (_conds(fresh))]
    if "prone" not in words and "dead" not in words:
        cl, cdata = mutations.cond(c.name, "+prone")
        out.append(cl)
    return out


def _conds(c):
    if c.combat_index >= 0:
        return mutations._conds_from_cell(c.combat_table().rows[c.combat_index].get("conditions"))
    return [str(x) for x in (c.front.get("conditions") or [])]


def _in_combat(c):
    return c.combat_index >= 0


def breath(name):
    c = creatures.get(name)
    con = c.mod("con")
    minutes = 1 + con
    if _in_combat(c):
        dur = f"{max(5, minutes * 10)}r"
    else:
        dur = f"{max(1, minutes)}m"
    shown = f"{minutes}m" if minutes >= 1 else "30 s"
    line, data = mutations.cond(c.name, "+holding-breath", dur)
    choke = max(1, con)
    return [f"[hazard {_short(c)} holding breath {shown} (1 + CON {con:+d}"
            + (", at least 30 s" if minutes < 1 else "") + f") · then choking {choke}r, then 0 HP and dying]", line]


def expiry_lines(pairs):
    """`holding-breath` ran out → choking for CON mod rounds (min 1); `choking` ran out →
    0 HP. `pairs` = [(name, condition word)]. -> lines."""
    out = []
    for name, word in pairs:
        word = word.lower()
        if word not in ("holding-breath", "choking"):
            continue
        try:
            c = creatures.get(name)
        except (ToolError, campaign.CampaignError):
            continue
        if word == "holding-breath":
            try:
                n = max(1, c.mod("con"))
            except ToolError:
                n = 1
            dur = f"{n}r" if _in_combat(c) else "1m"
            line, _ = mutations.cond(c.name, "+choking", dur)
            out += [f"[{_short(c)} is out of breath: choking {n}r, then 0 HP]", line]
        else:
            line, data = mutations.hp(c.name, "=", 0)
            out += [f"[{_short(c)} has choked: 0 HP]", line] + data.get("after", [])
    return out


def env():
    v = str(campaign.load_state().front.get("environment") or "none").strip().lower()
    return v if v in ENVS else "none"


def set_env(value):
    value = value.strip().lower()
    if value not in ENVS:
        raise HazardError(f"hazard env: {' | '.join(ENVS)}")
    state = campaign.load_state()
    old = str(state.front.get("environment") or "none")
    if value == "none":
        state.del_front("environment")
        state.del_front("environment-since")
    else:
        state.set_front("environment", value)
        state.set_front("environment-since", str(state.front.get("in-game-datetime") or ""))
    state.save()
    body = f"environment {old}→{value}"
    journal.log_delta(body)
    extra = {"extreme-cold": "a CON save DC 10 each hour for anyone not exempt (cold-weather gear, cold resistance)",
             "extreme-heat": "a CON save each hour (DC 5 the first hour, +1 each hour after) without drinkable water; fire resistance "
                             "or heat adaptation exempt",
             "underwater": "melee at disadvantage except dagger, javelin, shortsword, spear, trident; ranged "
                           "misses past normal range, disadvantage within it (crossbows, nets, thrown "
                           "javelins/spears/tridents/darts aside); fire damage resisted",
             "thin-air": "no tool effect (the GM narrates altitude)", "none": ""}[value]
    return [f"[{body}]" + (f" · {extra}" if extra else "")]


def _text(doc):
    return " ".join(doc.body).lower() + " " + " ".join(str(x) for x in (doc.front.get("senses") or [])).lower()


def _exempt(doc, kind):
    res = [str(x).lower() for x in (doc.front.get("resistances") or [])]
    txt = _text(doc)
    if kind == "extreme-cold":
        return "cold" in res or bool(re.search(r"cold[- ]weather|winter (?:gear|clothes)|\bfurs\b|cold adaptation", txt))
    if "fire" in res or "heat adaptation" in txt:
        return True
    import supplies
    if str(campaign.settings().get("supplies", "off")).lower() != "off":
        return supplies.has_water(doc)
    return False


def env_lines(old, new, docs):
    """Clock: the hourly CON saves in extreme cold or heat, per hour boundary crossed
    since `environment-since`."""
    kind = env()
    if kind not in ("extreme-cold", "extreme-heat"):
        return []
    state = campaign.load_state()
    try:
        since = gametime.parse(state.front.get("environment-since"))
    except gametime.TimeError:
        since = old
    h0 = max(0, gametime.diff(since, old)) // 60
    h1 = max(0, gametime.diff(since, new)) // 60
    if h1 <= h0:
        return []
    who = [d for d in docs if d.front.get("present") is not False]
    exempt = [str(d.front.get("name")).split()[0] for d in who if _exempt(d, kind)]
    names = [str(d.front.get("name")).split()[0] for d in who if not _exempt(d, kind)]
    word = "cold" if kind == "extreme-cold" else "heat"
    out = []
    for h in range(h0 + 1, h1 + 1):
        dc = 10 if kind == "extreme-cold" else 4 + h   # heat: DC 5 the first hour, +1 each hour after
        if not names:
            continue
        out.append(f"  Environment ({kind}) hour {h}: CON save DC {dc} — {', '.join(names)} "
                   f"(gm.py save <PC> con {dc} · fail → gm.py exhaust <PC> +1 \"{word}\")")
    if exempt and out:
        out.append(f"  Environment: exempt — {', '.join(exempt)}")
    if word == "heat" and out and str(campaign.settings().get("supplies", "off")).lower() == "off":
        out.append("  Environment: anyone with drinkable water skips the heat save (supplies aren't tracked)")
    return out


def underwater_attack(c, atk, dist, far, normal):
    """(mode change 'dis' | None, auto-miss reason | None, note) for an attack under water."""
    if env() != "underwater":
        return None, None, ""
    name = (atk.get("name") or "").lower()
    rng = (atk.get("range") or "").lower()
    ranged = ("/" in rng or (rng.strip().isdigit() and int(rng) > 10)) and not (dist is not None and dist <= 5)
    if not ranged:
        if any(w in name for w in MELEE_OK):
            return None, None, "underwater (piercing weapon: no penalty)"
        return "dis", None, "underwater melee: disadvantage"
    if dist is not None and normal is not None and dist > normal:
        return None, f"underwater, beyond normal range ({dist:g} ft > {normal} ft)", ""
    if any(w in name for w in RANGED_OK):
        return None, None, "underwater (no penalty for this weapon)"
    return "dis", None, "underwater ranged: disadvantage"


# ---------- CLI ----------

def _out(ctx, lines):
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def cmd_trap(ctx):
    a = ctx.args
    extra = list(getattr(a, "extra", None) or [])   # `--who Kael 8`: the total after the option
    if extra:
        if a.total is not None or len(extra) > 1 or not extra[0].lstrip("-").isdigit():
            raise HazardError(f"trap: unexpected {' '.join(extra)!r}")
        a.total = int(extra[0])
    if a.action == "status":
        _out(ctx, status())
        return
    if not a.trap:
        raise HazardError(f"trap {a.action} <id>")
    if a.action == "trigger":
        _out(ctx, trigger(a.trap, a.who, a.total, a.d20, ctx.roller))
    else:
        if not a.who:
            raise HazardError("trap disarm <id> --who <creature> <total>")
        _out(ctx, disarm(a.trap, a.who, a.total, ctx.roller))


def cmd_hazard(ctx):
    a = ctx.args
    if a.kind == "fall":
        if len(a.args) != 2 or not a.args[1].isdigit():
            raise HazardError("hazard fall <who> <ft>")
        _out(ctx, fall(a.args[0], int(a.args[1]), ctx.roller))
    elif a.kind == "breath":
        if len(a.args) != 1:
            raise HazardError("hazard breath <who>")
        _out(ctx, breath(a.args[0]))
    else:
        if len(a.args) != 1:
            raise HazardError(f"hazard env {' | '.join(ENVS)}")
        _out(ctx, set_env(a.args[0]))


def register(sub, g):
    p = sub.add_parser("trap", parents=[g], help="trap trigger|disarm|status <id> [--who X] [<total>]")
    p.add_argument("action", choices=["trigger", "disarm", "status"])
    p.add_argument("trap", nargs="?")
    p.add_argument("total", nargs="?", type=int, help="the player's save (trigger) or check (disarm) total")
    p.add_argument("--who")
    p.add_argument("--d20", type=int, help="trigger: the player's natural d20 for the save")
    p.set_defaults(func=cmd_trap, take_extra=True)

    p = sub.add_parser("hazard", parents=[g], help="hazard fall <who> <ft> | breath <who> | env <kind>")
    p.add_argument("kind", choices=["fall", "breath", "env"])
    p.add_argument("args", nargs="*")
    p.set_defaults(func=cmd_hazard)
