"""Concentration, dying and exhaustion: state the table forgets (docs/design/02 → Table
mechanics → Phase 13; 04 → PC file, Added by Phases 13–15, and Scene state; 06 → Table
mechanics → Phase 13; plan.md Phase 13 items 2, 3, 6).

    conc Kael bless [--on Kael,Kira] [1m|10r|1h]   start concentrating (ends any other)
    conc Kael end ["failed save"]                  end it; strips the targets' effect
    deathsave Kael [<d20>]                         one death save (the player's d20)
    stabilize Kael [--by Kira [<d20>]] [--kit] [--spell]
    exhaust Kael +1|-1|=N ["forced march"]

Where the state lives. A creature with a file keeps it in frontmatter, written only
while it means something: `concentration: {spell, until, on, save}` (`until` = game
time, `Nr`, or empty; `save` = the CON save DC owed after damage), `death-saves: {ok,
fail}` (PCs at 0 HP), `exhaustion: N`. In combat the Combatants row's `conditions`
mirrors them (`conc bless 8r`, `dying ✓1 ✗2`, `exh 2`); a row without a file (an
`srd:` monster) keeps only the mirror, plus `conc→Kael+Kira` / `conc-save 12` in its
`notes`. Concentration targets get the spell as a condition (`bless 10r` / `bless 1m`)
with the same duration, so the usual round and clock ticks expire both together;
`combat next`, `clock` and `combat end` call back here to clear the caster's record.
`stable` carries the 1d4 hours until the PC wakes (`stable 3h`); the clock wakes them.

Python API for mutations/roll/combat/clock/rest/brief: `after_hp(...)`,
`after_cond(name, cname)`, `after_save(name, ability, dc, outcome)`, `record(c)`,
`end_conc(name, why)`, `expire_concs(...)`, `mirrors(front, ...)`, `strip_mirrors(conds)`,
`clear_dying(doc)`, `tags(front, conds)`.
"""
import math
import re

from lib import campaign, creatures, gametime, journal, resolve
from lib.errors import ToolError
import mutations

INCAPACITATING = ("incapacitated", "paralyzed", "petrified", "stunned", "unconscious")
_MIRROR = re.compile(r"^(conc|dying|exh)\b", re.I)
_DUR = re.compile(r"^(\d+)\s*([rmh])$", re.I)
_NOTE_ON = re.compile(r"conc→([^;·]*)")
_NOTE_SAVE = re.compile(r"conc-save (\d+)")


class TableMechError(ToolError):
    pass


def creature(name, state=None):
    return mutations.creature(name, state)


def _short(c):
    """How a creature is named in records and lines: a PC's first name, else the row/file name."""
    return c.name.split()[0] if c.is_pc else c.name


def _setting(key):
    return str(campaign.settings().get(key, campaign.SETTINGS[key])).strip().lower()


# ---------- conditions on a row or a file ----------

def _conds(c):
    if c.combat_index >= 0:
        return mutations._conds_from_cell(c.combat_table().rows[c.combat_index].get("conditions"))
    if c.doc is None:
        return []
    return [str(x) for x in (c.doc.front.get("conditions") or []) if str(x).strip()]


def _write_conds(c, conds):
    """Write the creature's conditions where they live (row or file) and save."""
    if c.combat_index >= 0:
        c.combat_table().set(c.combat_index, "conditions", ", ".join(conds) if conds else "—")
        c.state.save()
    elif c.doc is not None:
        c.doc.set_front("conditions", conds)
        c.doc.save()


def _edit_conds(name, drop=(), add=(), mirror_only=False):
    """Fresh-load `name`, drop conditions whose first word is in `drop` (lower-case), add
    `add`. `mirror_only` touches only a Combatants row (out of combat: nothing).
    Returns the names actually dropped."""
    state = campaign.load_state()
    try:
        c = creature(name, state)
    except mutations.MutationError:
        return []
    if mirror_only and c.combat_index < 0:
        return []
    conds = _conds(c)
    adding = {a.split()[0].lower() for a in add}
    gone = [x for x in conds if x.split()[0].lower() in drop and x.split()[0].lower() not in adding]
    kept = [x for x in conds if x.split()[0].lower() not in drop or x.split()[0].lower() in adding]
    for a in add:   # a condition already there is replaced in place
        first = a.split()[0].lower()
        at = next((i for i, x in enumerate(kept) if x.split()[0].lower() == first), None)
        if at is None:
            kept.append(a)
        else:
            kept[at] = a
    if kept != conds:
        _write_conds(c, kept)
    return [x.split()[0] for x in gone]


def is_mirror(cond):
    return bool(_MIRROR.match(str(cond).strip()))


def strip_mirrors(conds):
    """Conditions without the combat-only mirrors (combat end writes the rest back)."""
    return [x for x in conds if not is_mirror(x)]


# ---------- concentration ----------

def _dur_text(minutes):
    return f"{minutes // 60}h" if minutes >= 60 and minutes % 60 == 0 else f"{minutes}m"


def srd_duration(spell):
    """'1m' / '10m' / '1h' from the SRD spell's `Concentration, up to …`, else None."""
    try:
        from lib import srd
        rec = srd.find("Spells", spell.replace("-", " "))
    except Exception:  # noqa: BLE001 — no data or no such spell: the GM gives one
        return None
    m = re.search(r"(\d+)\s*(minute|hour|round)", str(rec.get("duration", "")), re.I)
    if not m:
        return None
    return m.group(1) + {"minute": "m", "hour": "h", "round": "r"}[m.group(2).lower()]


def record(c):
    """{spell, until, on, save} for a concentrating creature, else None."""
    if c.doc is not None:
        r = c.doc.front.get("concentration")
        if isinstance(r, dict) and r.get("spell"):
            on = r.get("on") or []
            return {"spell": str(r["spell"]), "until": str(r.get("until") or ""),
                    "on": [str(x) for x in (on if isinstance(on, list) else [on])],
                    "save": r.get("save") if isinstance(r.get("save"), int) else None}
        return None
    if c.combat_index < 0:
        return None
    row = c.combat_table().rows[c.combat_index]
    mirror = next((x for x in mutations._conds_from_cell(row.get("conditions"))
                   if x.split()[0].lower() == "conc"), None)
    if mirror is None:
        return None
    parts = mirror.split()
    notes = row.get("notes", "") or ""
    on = _NOTE_ON.search(notes)
    save = _NOTE_SAVE.search(notes)
    rounds = parts[2] if len(parts) > 2 and parts[2].endswith("r") else ""
    return {"spell": parts[1] if len(parts) > 1 else "?", "until": rounds,
            "on": [x for x in (on.group(1).strip().split("+") if on else []) if x],
            "save": int(save.group(1)) if save else None}


def _write_record(name, rec):
    """Write (or clear, rec=None) the record where it lives; fresh load, saves."""
    state = campaign.load_state()
    c = creature(name, state)
    if c.doc is not None:
        if rec is None:
            c.doc.del_front("concentration")
        else:
            out = {"spell": rec["spell"], "until": rec["until"], "on": rec["on"]}
            if rec.get("save"):
                out["save"] = rec["save"]
            c.doc.set_front("concentration", out)
        c.doc.save()
        return
    if c.combat_index < 0:
        return
    t = c.combat_table()
    notes = t.rows[c.combat_index].get("notes", "") or ""
    bits = [b.strip() for b in notes.split(";") if b.strip() and not b.strip().startswith("conc")]
    if rec is not None:
        if rec["on"]:
            bits.append("conc→" + "+".join(rec["on"]))
        if rec.get("save"):
            bits.append(f"conc-save {rec['save']}")
    t.set(c.combat_index, "notes", "; ".join(bits))
    state.save()


def conc_start(caster, spell, on=(), duration=None):
    lines = []
    state = campaign.load_state()
    c = creature(caster, state)
    if record(c) is not None:
        lines += end_conc(c.name, "a new concentration spell")
        state = campaign.load_state()
        c = creature(caster, state)
    spell = campaign.slugify(spell)
    if not spell:
        raise TableMechError("conc: name the spell")
    duration = duration or srd_duration(spell)
    in_combat = state.table("Combatants") is not None
    rounds = minutes = None
    if duration:
        m = _DUR.match(duration.strip())
        if not m:
            raise TableMechError(f"conc: duration is Nr, Nm or Nh, got {duration!r}")
        n, unit = int(m.group(1)), m.group(2).lower()
        mins = n * 60 if unit == "h" else n
        if in_combat and (unit == "r" or mins <= 1):
            rounds = n if unit == "r" else mins * 10       # 1 minute = 10 rounds
        elif unit == "r":
            minutes = max(1, math.ceil(n / 10))
        else:
            minutes = mins
    if rounds:
        until, dur = f"{rounds}r", f"{rounds}r"
    elif minutes:
        now = gametime.parse(state.front.get("in-game-datetime"))
        until, dur = gametime.fmt(gametime.normalize(now[0], now[1] + minutes)), _dur_text(minutes)
    else:
        until, dur = "", None
    names = []
    for t in on:
        tc = creature(t, campaign.load_state())
        _edit_conds(tc.name, add=[spell + (f" {dur}" if dur else "")])
        names.append(_short(tc))
    _write_record(c.name, {"spell": spell, "until": until, "on": names, "save": None})
    if in_combat:
        _edit_conds(c.name, drop=("conc",), add=[f"conc {spell}" + (f" {rounds}r" if rounds else "")],
                    mirror_only=True)
    body = (f"conc {_short(c)} {spell}" + (f" · {dur}" if dur else " · until ended")
            + (f" · on {', '.join(names)}" if names else ""))
    journal.log_delta(body)
    return lines + [f"[{body}]"]


def end_conc(name, why=""):
    """End `name`'s concentration: strip the effect from every target, clear the record
    and the mirror. Raises when not concentrating."""
    state = campaign.load_state()
    c = creature(name, state)
    rec = record(c)
    if rec is None:
        raise TableMechError(f"{c.name} is not concentrating")
    who = _short(c)
    lost = []
    for t in rec["on"]:
        if _edit_conds(t, drop=(rec["spell"].lower(),)):
            lost.append(t)
    _write_record(c.name, None)
    _edit_conds(c.name, drop=("conc",), mirror_only=True)
    body = (f"conc {who} ends {rec['spell']}" + (f" ({why})" if why else "")
            + (f" · {', '.join(lost)} lose {rec['spell']}" if lost else ""))
    journal.log_delta(body)
    return [f"[{body}]"]


def conc_tag(front, now=None, rounds_text=None):
    """`conc bless 8r` / `conc bless 40m` / `conc bless` for the party line, or None."""
    r = front.get("concentration") if front else None
    if not isinstance(r, dict) or not r.get("spell"):
        return None
    if rounds_text and re.fullmatch(r"\d+r", rounds_text.split()[-1]):
        return rounds_text   # the combat mirror counts the rounds down
    until = str(r.get("until") or "")
    left = ""
    if until.endswith("r"):
        left = " " + until
    elif until and now is not None:
        try:
            left = " " + gametime.fmt_delta(max(0, gametime.diff(now, gametime.parse(until))))
        except gametime.TimeError:
            left = ""
    return f"conc {r['spell']}{left}"


def expire_concs(new, docs):
    """Clock: end every concentration in `docs` whose game-time `until` is at or before
    `new`. Returns the lines."""
    out = []
    for doc in docs:
        r = doc.front.get("concentration")
        if not isinstance(r, dict) or not r.get("until") or str(r["until"]).endswith("r"):
            continue
        try:
            until = gametime.parse(r["until"])
        except gametime.TimeError:
            continue
        if gametime.diff(until, new) >= 0:
            out += end_conc(str(doc.front.get("name")), "duration ended")
    return out


def end_round_concs():
    """Combat end: round-based concentration ends with the fight (its targets' `Nr`
    conditions already did)."""
    out = []
    for doc in campaign.pcs() + campaign.npcs():
        r = doc.front.get("concentration")
        if isinstance(r, dict) and str(r.get("until") or "").endswith("r"):
            out += end_conc(str(doc.front.get("name")), "the fight is over")
    return out


def damage_line(name, taken, new_hp):
    """After damage: the CON save owed (recorded as `save`), or the end at 0 HP."""
    state = campaign.load_state()
    c = creature(name, state)
    rec = record(c)
    if rec is None or taken <= 0:
        return []
    if new_hp == 0:
        return end_conc(c.name, "dropped to 0 HP")
    dc = max(10, taken // 2)
    rec["save"] = dc
    _write_record(c.name, rec)
    first = c.name.split()[0]
    return [f"[concentration: CON save DC {dc} to keep {rec['spell']} (gm.py save {first} con {dc})]"]


def after_save(name, ability, dc, outcome):
    """roll.saving_throw: a CON save that matches the DC owed settles it; a fail ends it."""
    if ability != "con":
        return []
    state = campaign.load_state()
    c = creature(name, state)
    rec = record(c)
    if rec is None or rec.get("save") != dc:
        return []
    if outcome == "FAIL":
        return end_conc(c.name, "failed save")
    rec["save"] = None
    _write_record(c.name, rec)
    return [f"[concentration: {_short(c)} keeps {rec['spell']}]"]


def after_cond(name, cname):
    """mutations.cond: an incapacitating condition ends concentration."""
    if cname not in INCAPACITATING:
        return []
    c = creature(name)
    if record(c) is None:
        return []
    return end_conc(c.name, cname)


# ---------- dying ----------

def _pc_doc(name):
    c = creature(name)
    if not c.is_pc or c.doc is None:
        raise TableMechError(f"{c.name} is not a PC (only PCs make death saves)")
    return c


def dying_state(front):
    ds = front.get("death-saves") if front else None
    if isinstance(ds, dict):
        return int(ds.get("ok") or 0), int(ds.get("fail") or 0)
    return None


def dying_text(ok, fail):
    return f"dying ✓{ok} ✗{fail}"


def _set_dying(name, ok, fail):
    c = _pc_doc(name)
    c.doc.set_front("death-saves", {"ok": ok, "fail": fail})
    c.doc.save()
    _edit_conds(c.name, drop=("dying",), add=[dying_text(ok, fail)], mirror_only=True)


def _die(name, why):
    c = creature(name)
    if c.doc is not None:
        c.doc.del_front("death-saves")
        if not c.is_pc:
            c.doc.set_front("status", "dead")
        c.doc.save()
    if c.doc is not None and c.combat_index >= 0:   # the file's own conditions too
        doc = c.doc
        conds = [str(x) for x in (doc.front.get("conditions") or [])
                 if str(x).split()[0].lower() not in ("unconscious", "stable")]
        doc.set_front("conditions", conds + (["dead"] if "dead" not in conds else []))
        doc.save()
    _edit_conds(c.name, drop=("dying", "unconscious", "stable"), add=["dead"])
    body = f"{_short(c)} is dead ({why})"
    journal.log_delta(body)
    return [f"[{body}]"]


def _start_dying(name):
    c = _pc_doc(name)
    _set_dying(c.name, 0, 0)
    _edit_conds(c.name, drop=("stable",), add=["unconscious"])
    if c.combat_index >= 0:   # the file keeps it too, for after the fight
        doc = creature(c.name).doc
        conds = [str(x) for x in (doc.front.get("conditions") or [])]
        if "unconscious" not in [x.split()[0] for x in conds]:
            doc.set_front("conditions", conds + ["unconscious"])
            doc.save()
    body = f"{_short(c)} is dying: unconscious, death saves ✓0 ✗0"
    journal.log_delta(body)
    return [f"[{body}]"]


def clear_dying(doc, why="healed"):
    """Healing (any HP above 0) ends dying/stable and wakes the PC. `doc` is the PC's
    loaded file; saves it and the combat mirror. Returns the lines."""
    had = dying_state(doc.front) is not None
    conds = [str(x) for x in (doc.front.get("conditions") or [])]
    stable = any(x.split()[0].lower() == "stable" for x in conds)
    if not had and not stable:
        return []
    doc.del_front("death-saves")
    doc.set_front("conditions", [x for x in conds if x.split()[0].lower() not in ("unconscious", "stable")])
    doc.save()
    name = str(doc.front.get("name") or "")
    _edit_conds(name, drop=("dying", "unconscious", "stable"), mirror_only=True)
    body = f"{name.split()[0]} is conscious again ({why})"
    journal.log_delta(body)
    return [f"[{body}]"]


def after_hp(name, *, is_pc, op, cur, new, mx, taken, hp_lost=0, crit=False):
    """mutations._apply_hp, after its write: concentration (CON save / 0 HP) and, for a
    PC, dying (06 → Dying). `taken` = the damage (after resistance; sets the CON save
    DC), `hp_lost` = the part that got past temp HP (death save failures, massive damage)."""
    lines = []
    if op == "-":
        lines += damage_line(name, taken, new)
    elif new == 0 and cur > 0:          # `hp X =0`: no save, but 0 HP still ends it
        lines += damage_line(name, cur, 0)
    if not is_pc:
        return lines
    on, _, _ = resolve.death_saves()
    if not on:
        return lines
    c = creature(name)
    doc = c.doc
    if doc is None:
        return lines
    conds = [x.split()[0].lower() for x in _conds(c)] + \
            [str(x).split()[0].lower() for x in (doc.front.get("conditions") or [])]
    if "dead" in conds:
        return lines
    if cur > 0 and new == 0:
        overflow = (hp_lost - cur) if op == "-" else 0
        if overflow >= mx:
            return lines + _die(c.name, f"massive damage: {overflow} past 0 ≥ HP max {mx}")
        return lines + _start_dying(c.name)
    if cur == 0 and new == 0 and op == "-" and hp_lost > 0:
        if hp_lost >= mx:
            return lines + _die(c.name, f"{hp_lost} damage at 0 HP ≥ HP max {mx}")
        state = dying_state(doc.front)
        if state is None:
            lines += _start_dying(c.name)
            state = (0, 0)
        ok, fail = state
        fail += 2 if crit else 1
        if fail >= 3:
            return lines + _die(c.name, "three death save failures")
        _set_dying(c.name, ok, fail)
        body = (f"{_short(c)}: damage at 0 HP — {'two failures (crit)' if crit else 'a death save failure'}"
                f" · {dying_text(ok, fail)}")
        journal.log_delta(body)
        return lines + [f"[{body}]"]
    if cur == 0 and new > 0:
        lines += clear_dying(creature(c.name).doc)
    return lines


def _stable(name, roller):
    c = _pc_doc(name)
    hours = roller.die(4)
    c.doc.del_front("death-saves")
    c.doc.save()
    _edit_conds(c.name, drop=("dying",), add=[f"stable {hours}h"])
    body = f"{_short(c)} is stable (wakes with 1 HP in {hours}h, 1d4: {hours})"
    journal.log_delta(body)
    return [f"[{body}]"]


def wake(doc):
    """Clock: a PC's `stable Nh` ran out — 1 HP and awake. Edits `doc` (not saved)."""
    hp = dict(doc.front.get("hp") or {})
    if int(hp.get("current") or 0) <= 0:
        hp["current"] = 1
        doc.set_front("hp", hp)
    conds = [str(x) for x in (doc.front.get("conditions") or [])]
    doc.set_front("conditions", [x for x in conds if x.split()[0].lower() != "unconscious"])
    return "wakes with 1 HP"


def deathsave(name, d20=None, roller=None):
    on, dc, rid = resolve.death_saves()
    c = _pc_doc(name)
    if not on:
        raise TableMechError(f"death saves are off ({rid}): nothing to roll")
    ds = dying_state(c.doc.front)
    if ds is None:
        raise TableMechError(f"{c.name} is not dying")
    secret = _setting("death-save-rolls") == "secret"
    first = c.name.split()[0]
    if d20 is None:
        gm_rolls = resolve.dice_mode(campaign.load_state().front) == "gm-rolls-all"
        if not (secret or gm_rolls):
            raise TableMechError(f"{first} rolls their own death save: ask for a d20 (gm.py deathsave {first} <d20>)")
        d20 = roller.die(20)
    elif not 1 <= d20 <= 20:
        raise TableMechError(f"deathsave: a d20 is 1-20, got {d20}")
    ok, fail = ds
    ok, fail, result = resolve.death_save(d20, ok, fail, dc)
    head = f"deathsave {first}: d20 {d20}" + (f" vs {dc}" if dc != 10 else "")
    lines = []
    if result == "up":
        body = f"{head} — natural 20: back up with 1 HP"
        journal.log_delta(body, gm=secret)
        lines.append(f"[SECRET {body}]" if secret else f"[{body}]")
        line, data = mutations.hp(c.name, "=", 1)
        return lines + [line] + data.get("after", [])
    what = "two failures" if d20 == 1 else ("success" if d20 >= dc else "failure")
    if result == "dead":
        body = f"{head} — {what} · ✓{ok} ✗{fail}"
        journal.log_delta(body, gm=secret)
        lines.append(f"[SECRET {body}]" if secret else f"[{body}]")
        return lines + _die(c.name, "three death save failures")
    if result == "stable":
        body = f"{head} — {what} · ✓{ok} ✗{fail}"
        journal.log_delta(body, gm=secret)
        lines.append(f"[SECRET {body}]" if secret else f"[{body}]")
        return lines + _stable(c.name, roller)
    _set_dying(c.name, ok, fail)
    body = f"{head} — {what} · {dying_text(ok, fail)}"
    journal.log_delta(body, gm=secret)
    return [f"[SECRET {body}]" if secret else f"[{body}]"]


def _kit_owner(by):
    """(creature, resource name) of a healer's kit to spend: `by`'s, else the first
    scene PC with uses left."""
    cands = [creature(by)] if by else [creature(str(d.front.get("name"))) for d in campaign.scene_pcs()]
    for c in cands:
        t = c.doc.table("Resources") if c.doc is not None else None
        for r in (t.rows if t else []):
            if r.get("resource", "").strip().lower().startswith("healer's kit") \
                    and str(r.get("current", "")).strip().isdigit() and int(r["current"]) > 0:
                return c, r["resource"]
    raise TableMechError("stabilize --kit: " + (f"{by} has" if by else "nobody here has")
                         + " a healer's kit with uses left (a `healer's kit uses` Resources row)")


def stabilize(name, by=None, d20=None, kit=False, spell=False, roller=None):
    c = _pc_doc(name)
    if dying_state(c.doc.front) is None:
        raise TableMechError(f"{c.name} is not dying")
    lines = []
    if kit:
        owner, res = _kit_owner(by)
        import inventory
        line, _ = inventory.res(owner.name, "-", res, 1)
        lines.append(line)
    elif not spell:
        if not by:
            raise TableMechError("stabilize: --by <who> (Medicine DC 10), --kit or --spell")
        import roll
        line, data = roll.ability_check(by, "medicine", 10, d20=d20, roller=roller)
        lines.append(line)
        if data["outcome"] != "SUCCESS":
            return lines
    return lines + _stable(c.name, roller)


# ---------- exhaustion ----------

def exhaust(name, change, reason=""):
    m = re.fullmatch(r"([+=-])\s*(\d)", change.strip())
    if not m:
        raise TableMechError(f"exhaust: want +N, -N or =N, got {change!r}")
    state = campaign.load_state()
    c = creature(name, state)
    if c.combat_index < 0 and c.doc is None:
        raise TableMechError(f"{c.name}: no file or Combatants row to hold exhaustion")
    old = c.exhaustion()
    n = int(m.group(2))
    new = {"+": old + n, "-": old - n, "=": n}[m.group(1)]
    new = max(0, min(6, new))
    ruleset = _setting("exhaustion")
    if c.doc is not None:
        if new:
            c.doc.set_front("exhaustion", new)
        else:
            c.doc.del_front("exhaustion")
        c.doc.save()
    _edit_conds(c.name, drop=("exh",), add=[f"exh {new}"] if new else [], mirror_only=True)
    lines = []
    if new >= 4 > old and ruleset != "2024":   # the halved maximum caps current HP now
        lines += _cap_hp(name, new, ruleset)
    body = (f"exhaust {_short(c)} {old}→{new}" + (f" ({reason})" if reason else "")
            + f" · {resolve.exhaustion_effects(new, ruleset)}")
    journal.log_delta(body)
    lines.insert(0, f"[{body}]")
    if new >= 6:
        lines += _die(c.name, "exhaustion 6")
    return lines


def _cap_hp(name, level, ruleset):
    """Exhaustion 4 (2014): current HP above the halved maximum drops to it (not damage)."""
    state = campaign.load_state()
    c = creature(name, state)
    if c.combat_index >= 0:
        t = c.combat_table()
        cell = creatures.parse_hp_cell(t.rows[c.combat_index].get("hp", ""))
        if cell is None:
            return []
        cur, mx, temp, each = cell
        cap = resolve.exhaustion_hp_max(mx, level, ruleset)
        if cur <= cap:
            return []
        t.set(c.combat_index, "hp", creatures.fmt_hp_cell(cap, mx, temp, each))
        state.save()
    else:
        h = c.front.get("hp") if c.doc is not None else None
        if not isinstance(h, dict):
            return []
        cur, mx = int(h.get("current") or 0), int(h.get("max") or 0)
        cap = resolve.exhaustion_hp_max(mx, level, ruleset)
        if cur <= cap:
            return []
        c.doc.set_front("hp", dict(h, current=cap))
        c.doc.save()
    body = f"hp {_short(c)} {cur}→{cap}/{cap} (exhaustion {level}: HP max halved)"
    journal.log_delta(body)
    return [f"[{body}]"]


# ---------- brief / combat helpers ----------

def mirrors(front, now=None):
    """The combat mirrors for a creature's file (combat start seeds its row)."""
    out = []
    t = conc_tag(front)
    if t:
        until = str((front.get("concentration") or {}).get("until") or "")
        out.append(f"conc {front['concentration']['spell']}" + (f" {until}" if until.endswith("r") else ""))
    ds = dying_state(front)
    if ds:
        out.append(dying_text(*ds))
    if isinstance(front.get("exhaustion"), int) and front["exhaustion"]:
        out.append(f"exh {front['exhaustion']}")
    return out


def tags(front, conds, now=None):
    """(conditions without mirrors, [tags]) for the brief's party line: `DYING ✓1 ✗2`,
    `[conc bless 8r]`, `[exh 2]` (02 → Table mechanics; 06 → Phase 13)."""
    rest = strip_mirrors(conds)
    mirror_conc = next((x for x in conds if x.split()[0].lower() == "conc"), None)
    out = []
    ds = dying_state(front)
    if ds:
        out.append("DYING ✓%d ✗%d" % ds)
    c = conc_tag(front, now, mirror_conc)
    if c is None and mirror_conc:
        c = mirror_conc
    if c:
        out.append(f"[{c}]")
    exh = front.get("exhaustion") if isinstance(front.get("exhaustion"), int) else None
    if exh is None:
        m = next((x for x in conds if x.split()[0].lower() == "exh"), None)
        exh = int(m.split()[1]) if m and len(m.split()) > 1 and m.split()[1].isdigit() else None
    if exh:
        out.append(f"[exh {exh}]")
    return rest, out


def dying_prompt(row_name):
    """combat next: the line for a dying PC who is up, or None."""
    try:
        c = creature(row_name)
    except mutations.MutationError:
        return None
    if not c.is_pc or c.doc is None:
        return None
    ds = dying_state(c.doc.front)
    if ds is None or not resolve.death_saves()[0]:
        return None
    first = c.name.split()[0]
    head = f"[{first} is dying (✓{ds[0]} ✗{ds[1]}): death save — "
    if _setting("death-save-rolls") == "secret":
        return head + f"roll it hidden (gm.py deathsave {first})]"
    return head + f"ask for a d20 (gm.py deathsave {first} <d20>)]"


# ---------- CLI ----------

def _out(ctx, lines):
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def cmd_conc(ctx):
    a = ctx.args
    rest, on_text = [], a.on or ""
    toks = list(a.rest)
    while toks:
        t = toks.pop(0)
        if t == "--on" and toks:
            on_text = toks.pop(0)
        elif t.startswith("--on="):
            on_text = t[5:]
        else:
            rest.append(t)
    if rest[:1] and rest[0].lower() == "end":
        _out(ctx, end_conc(creature(a.caster).name, " ".join(rest[1:]).strip()))
        return
    if not rest:
        raise TableMechError("conc <caster> <spell> [--on A,B] [1m|10r|1h] | conc <caster> end")
    dur = rest.pop() if len(rest) > 1 and _DUR.match(rest[-1]) else None
    on = [x.strip() for x in on_text.split(",") if x.strip()]
    _out(ctx, conc_start(a.caster, " ".join(rest), on, dur))


def cmd_deathsave(ctx):
    _out(ctx, deathsave(ctx.args.target, ctx.args.d20, ctx.roller))


def cmd_stabilize(ctx):
    a = ctx.args
    by, d20 = None, None
    if a.by:
        by = a.by[0]
        if len(a.by) > 1:
            if not a.by[1].isdigit():
                raise TableMechError("stabilize --by <who> [<d20>]")
            d20 = int(a.by[1])
    _out(ctx, stabilize(a.target, by, d20, a.kit, a.spell, ctx.roller))


def cmd_exhaust(ctx):
    a = ctx.args
    _out(ctx, exhaust(a.target, a.change, " ".join(a.reason).strip()))


def register(sub, g):
    p = sub.add_parser("conc", parents=[g], help="conc CASTER SPELL [--on A,B] [1m|10r|1h] | conc CASTER end [why]")
    p.add_argument("caster"); p.add_argument("rest", nargs="...")
    p.add_argument("--on", help="the spell's targets: A,B")
    p.set_defaults(func=cmd_conc)

    p = sub.add_parser("deathsave", parents=[g], help="deathsave PC [d20] (the player's d20)")
    p.add_argument("target"); p.add_argument("d20", nargs="?", type=int)
    p.set_defaults(func=cmd_deathsave)

    p = sub.add_parser("stabilize", parents=[g], help="stabilize PC [--by WHO [d20]] [--kit] [--spell]")
    p.add_argument("target")
    p.add_argument("--by", nargs="+", help="who tends them: Medicine DC 10 (their d20)")
    p.add_argument("--kit", action="store_true", help="a healer's kit use (no check)")
    p.add_argument("--spell", action="store_true", help="spare the dying or the like (no check)")
    p.set_defaults(func=cmd_stabilize)

    p = mutations.allow_negative(sub.add_parser("exhaust", parents=[g], help='exhaust NAME +1|-1|=N ["why"]'))
    p.add_argument("target"); p.add_argument("change"); p.add_argument("reason", nargs="*")
    p.set_defaults(func=cmd_exhaust)
