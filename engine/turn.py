"""`gm.py turn [use action|bonus|object|dash]` and `gm.py move <who> --to … | --path …
[--dash] [--stop N] [--climbs]` (docs/design/06 → `gm.py turn` / `move`; lib/turnstate.py).

`turn` prints what the creature who's up still has (action, bonus action, movement, object
interaction); `turn use …` spends one (Dash, Dodge, Disengage, Help, a spell → `action`;
`dash` spends the action and adds speed to the movement left).

`move` is the real move: it finds the path (space.py), saves the new position to the
Combatants/Stage row, and in combat writes the Moves log and charges the feet to the
mover's turn when they're up (refusing a move longer than what's left unless `--dash`).
It reports opportunity attacks the path provokes. `space move` stays a preview.
"""
from lib import campaign, journal, turnstate
from lib.creatures import norm_name
from lib.errors import ToolError
import space
import tempo


class TurnError(ToolError):
    pass


def _budget(state):
    d = turnstate.read(state)
    if d is None:
        raise TurnError("turn: not in combat (no Turn line under ## Combat)")
    return d


def use(what):
    state = campaign.load_state()
    d = _budget(state)
    what = what.lower()
    if what in ("action", "bonus", "object"):
        if d[what] == "no":
            raise TurnError(f"turn use {what}: {d['name']} already spent it")
        d[what] = "no"
    elif what == "dash":
        if d["action"] == "no":
            raise TurnError(f"turn use dash: {d['name']}'s action is spent")
        d["action"] = "no"
        d["left"] += d["speed"]
    else:
        raise TurnError("turn use action | bonus | object | dash")
    turnstate.write(state, d)
    state.save()
    return [turnstate.left_line(d)]


def after_attack(attacker, bonus=False):
    """Spend the attacker's action (or bonus action) when they're up; the left line, or None."""
    state = campaign.load_state()
    d = turnstate.read(state)
    if d is None or not turnstate.is_up(d, attacker):
        return None
    note = None
    if bonus:
        if d["bonus"] == "no":
            note = f"[note: {d['name']}'s bonus action was already spent]"
        d["bonus"] = "no"
    elif d["action"] in ("yes", "attack"):
        d["made"] = d.get("made", 0) + 1
        per = d.get("per")
        d["action"] = "no" if per is not None and d["made"] >= per else "attack"
    else:
        note = f"[note: {d['name']}'s action was already spent (a bonus-action attack? atk … --bonus)]"
    turnstate.write(state, d)
    state.save()
    return [x for x in (note, turnstate.left_line(d)) if x]


def move(who, to=None, path=None, stop=None, climbs=False, dash=False):
    state = campaign.load_state()
    c, table, i = tempo._row(state, who)
    name = norm_name(table.rows[i]["name"])
    st = space.State(str(campaign.state_path()))
    try:
        mover, _, end, spent, provoked, warnings = space.plan_move(st, name, path, to, stop, climbs)
    except SystemExit as e:
        raise TurnError(f"move {name}: {e.code}") from None
    except space.SpaceError as e:
        raise TurnError(f"move {name}: {e}") from None
    d = turnstate.read(state)
    up = turnstate.is_up(d, mover.name)
    if up:
        if dash:
            if d["action"] == "no":
                raise TurnError(f"move {mover.name} --dash: the action is already spent")
            d["action"] = "no"
            d["left"] += d["speed"]
        if spent > d["left"] + 1e-9:
            raise TurnError(f"move {mover.name}: {spent:g} ft needed, {d['left']:g} ft left — "
                            "stop short, or --dash (uses the action)")
        d["left"] -= spent
        turnstate.write(state, d)
    start = tempo.fmt_point(mover.pos)
    dest = tempo.fmt_point(end)
    table.set(i, "pos", dest)
    if d is not None:   # combat: the round's Moves log (summarized into the session log at round end)
        state.append_line("Moves log", f"- {mover.name} {start} → {dest} ({spent:g} ft)")
    else:
        journal.log_delta(f"move {mover.name} {start} → {dest} ({spent:g} ft)", gm=True)
    state.save()
    lines = [f"[move {mover.name} {start} → {dest} · {spent:g} ft" + (" · dashed" if up and dash else "") + "]"]
    if provoked:
        lines.append("[opportunity attacks from: " + ", ".join(provoked) + " — each may use its reaction]")
    lines += [f"[warning: {w}]" for w in warnings]
    if up:
        lines.append(turnstate.left_line(d))
    return lines


def cmd_turn(ctx):
    a = ctx.args
    if a.action == "use":
        if not a.what:
            raise TurnError("turn use action | bonus | object | dash")
        lines = use(a.what)
    else:
        lines = [turnstate.left_line(_budget(campaign.load_state()))]
    for line in lines:
        ctx.emit(line)


def cmd_move(ctx):
    a = ctx.args
    if not a.to and not a.path:
        raise TurnError("move <who> --to <creature | @feature | x,y,z> | --path x,y,z …")
    for line in move(a.who, a.to, a.path, a.stop, a.climbs, a.dash):
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("turn", parents=[g], help="what the creature who's up has left; turn use action|bonus|object|dash")
    p.add_argument("action", nargs="?", choices=["use"])
    p.add_argument("what", nargs="?")
    p.set_defaults(func=cmd_turn)
    p = sub.add_parser("move", parents=[g], help="move a creature (saves the position; charges their turn)")
    p.add_argument("who")
    p.add_argument("--to")
    p.add_argument("--path", nargs="+")
    p.add_argument("--stop", type=float)
    p.add_argument("--climbs", action="store_true")
    p.add_argument("--dash", action="store_true", help="spend the action to add speed")
    p.set_defaults(func=cmd_move)
