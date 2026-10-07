"""Readied actions (docs/design/02 → Table mechanics → Phase 15; 04 → Scene state added
(Combatants `ready: …`); 06 → Table mechanics → Phase 15; plan.md Phase 15 item 3).

    ready Kira "shoot whoever opens the door" [--spell hold-person]
    ready Kira fire        the trigger happened: the action goes off (her reaction)
    ready Kira drop        she lets it go

Combat only. `ready` writes `ready: <trigger and action>` into the combatant's
`conditions` (commas become `;`, the cell is comma-separated) and spends nothing until it
fires. A readied spell (`--spell`) is cast now: the slot is spent when readied (the line
says so) and the caster concentrates on it (conditions_ext.conc_start) until it is
released; `drop` or the lapse ends that concentration, `fire` keeps it only for a spell
that needs concentration anyway. `combat next` prints `[Readied: Kira — …]` before every
other combatant's turn and clears an unfired ready at the start of its owner's turn
(`lapsed`). `combat end` drops it with the other combat-only mirrors.

Python API for combat.py: `reminders(table, up_index)` -> lines, `lapse(name)` -> lines.
"""
import re

from lib import campaign, journal
from lib.creatures import norm_name
from lib.errors import ToolError
import mutations

_READY = re.compile(r"^ready:\s*(.*?)(?:\s*·\s*held\s+(\S+))?\s*$", re.I)


class ReadyError(ToolError):
    pass


def _conds(cell):
    return mutations._conds_from_cell(cell)


def parse(conds):
    """(text, held spell or None) of a `ready: …` condition, or None."""
    for c in conds:
        m = _READY.match(c)
        if m:
            return m.group(1).strip(), (m.group(2) or None)
    return None


def _row(name):
    state = campaign.load_state()
    if state.table("Combatants") is None:
        raise ReadyError("ready: only in combat (gm.py combat start)")
    c = mutations.creature(name, state)
    if c.combat_index < 0:
        raise ReadyError(f"ready: {c.name} has no Combatants row")
    return state, c


def _write(state, c, conds):
    c.combat_table().set(c.combat_index, "conditions", ", ".join(conds) if conds else "—")
    state.save()


def _short(c):
    return c.name.split()[0] if c.is_pc else c.name


def ready(name, text, spell=None):
    state, c = _row(name)
    conds = _conds(c.combat_row.get("conditions"))
    if parse(conds):
        raise ReadyError(f"{_short(c)} already has a readied action (ready {_short(c)} drop first)")
    text = re.sub(r"\s+", " ", text.replace(",", ";").replace("|", "/")).strip()
    if not text:
        raise ReadyError('ready: say the trigger and the action ("shoot whoever opens the door")')
    held = re.sub(r"\s+", "-", spell.strip().lower()) if spell else None
    _write(state, c, conds + [f"ready: {text}" + (f" · held {held}" if held else "")])
    body = f"ready {_short(c)}: {text}" + (f" (holding {held})" if held else "")
    journal.log_delta(body)
    lines = [f"[{body}]"]
    if held:
        import conditions_ext
        lines += conditions_ext.conc_start(c.name, held, duration="2r")
        lines.append(f"[the spell's slot is spent now (gm.py res {_short(c)} -\"spell slot N\"); "
                     "it is lost if the trigger doesn't come before their next turn]")
    return lines


def _clear(name, why):
    state, c = _row(name)
    conds = _conds(c.combat_row.get("conditions"))
    got = parse(conds)
    if got is None:
        raise ReadyError(f"{_short(c)} has no readied action")
    _write(state, c, [x for x in conds if not _READY.match(x)])
    return c, got


def fire(name):
    c, (text, held) = _clear(name, "fire")
    body = f"ready {_short(c)} fires: {text}"
    journal.log_delta(body)
    lines = [f"[{body} · uses {_short(c)}'s reaction]"]
    if held:
        import conditions_ext
        if conditions_ext.srd_duration(held) is None:   # not a concentration spell: released
            try:
                lines += conditions_ext.end_conc(c.name, "readied spell released")
            except ToolError:
                pass
        else:   # a concentration spell runs its own duration from now (targets: gm.py conc … --on)
            lines += conditions_ext.conc_start(c.name, held)
    return lines


def drop(name, why="dropped"):
    c, (text, held) = _clear(name, why)
    body = f"ready {_short(c)} {why}: {text}"
    journal.log_delta(body)
    lines = [f"[{body}]"]
    if held:
        import conditions_ext
        try:
            lines += conditions_ext.end_conc(c.name, f"readied spell {why}")
        except ToolError:
            pass
    return lines


def lapse(name):
    """combat next: the owner's turn starts with an unfired ready — it lapses."""
    try:
        state, c = _row(name)
    except (ReadyError, mutations.MutationError):
        return []
    if parse(_conds(c.combat_row.get("conditions"))) is None:
        return []
    return drop(name, "lapsed (unused)")


def reminders(table, up_index):
    """combat next: `[Readied: Kira — …]` for every other combatant holding one."""
    out = []
    for i, r in enumerate(table.rows):
        if i == up_index:
            continue
        got = parse(_conds(r.get("conditions")))
        if got:
            name = norm_name(r.get("name"))
            out.append(f"[Readied: {name.split()[0] if '(pc)' in r.get('name', '').lower() else name} — {got[0]}]")
    return out


def cmd_ready(ctx):
    a = ctx.args
    what = " ".join(a.what).strip()
    if what.lower() == "fire":
        lines = fire(a.target)
    elif what.lower() == "drop":
        lines = drop(a.target)
    else:
        lines = ready(a.target, what, a.spell)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("ready", parents=[g], help='ready NAME "trigger → action" | fire | drop')
    p.add_argument("target")
    p.add_argument("what", nargs="+")
    p.add_argument("--spell", help="a readied spell: cast now, held with concentration")
    p.set_defaults(func=cmd_ready)
