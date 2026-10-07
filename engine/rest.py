"""`gm.py rest short|long [Kael …] [--hd Kael=2] [--interrupted]` (docs/design/06 → `gm.py
rest`; rules/rests-and-recovery.md; plan.md Phase 7 item 3).

- **long:** full HP (temp HP gone), half the PC's total hit dice back (min 1),
  `## Resources` rows that recover `long` or `short` reset to max, 8 h on the clock.
- **short:** spend hit dice (`--hd Kael=2`: rolled publicly, each die + CON, min 0),
  `short` resources reset, 1 h on the clock.
- `--interrupted`: the rest gives nothing (the GM's call); only logged, no time passes
  beyond what the GM advances.
- Phase 13: a long rest first eats (supplies.eat: a ration and a day of water each;
  `supplies: loose` only away from a `services` site, `off` never), then removes one
  level of exhaustion from each PC who ate (or always with `supplies: off`, or in town
  under `loose`); HP fill to the maximum (halved at exhaustion 4+, 2014 table), and a
  dying or stable PC wakes.
Default: every present PC. Uses the PC files and the clock (clock advance).
"""
import re

from lib import campaign, gametime, md, resolve
from lib.chargen import mod
from lib.errors import ToolError
from lib import journal
import clock


class RestError(ToolError):
    pass


def _targets(names):
    if names:
        out = []
        for n in names:
            m = campaign.resolve(n)
            if not m.is_pc or not m.path:
                raise RestError(f"rest: {n!r} is not a PC")
            out.append(md.load(m.path))
        return out
    return [d for d in campaign.pcs() if d.front.get("present") is not False]


def _reset_resources(doc, kinds):
    t = doc.table("Resources")
    names = []
    for i, r in enumerate(t.rows if t else []):
        if r.get("recovers", "").strip().lower() in kinds and str(r.get("current")) != str(r.get("max")):
            t.set(i, "current", r.get("max", ""))
            names.append(r.get("resource", ""))
    return names


def _hd(text):
    out = {}
    for item in text or []:
        k, sep, v = item.partition("=")
        if not sep or not v.strip().isdigit():
            raise RestError(f"--hd wants Name=N, got {item!r}")
        out[k.strip().lower()] = int(v)
    return out


def rest(kind, names=(), hd=(), interrupted=False, roller=None):
    if campaign.load_state().table("Combatants") is not None:
        raise RestError("rest: combat is running")
    docs = _targets(names)
    if not docs:
        raise RestError("rest: nobody present")
    lines = []
    if interrupted:
        who = ", ".join(str(d.front.get("name")).split()[0] for d in docs)
        journal.log_delta(f"rest {kind} interrupted ({who}) — no benefit")
        return [f"[rest {kind} interrupted · {who} · no benefit]"], {}
    spend = _hd(hd)
    if kind == "long":
        import supplies
        eaters = [str(d.front.get("name")) for d in docs if supplies.counts_here(d)]
        if eaters:
            lines += supplies.eat(eaters, quiet_off=True)
        docs = [md.load(d.path) for d in docs]
        today = gametime.parse(campaign.load_state().front.get("in-game-datetime"))[0]
        mode = str(campaign.settings().get("supplies", "loose")).lower()
        lines += _recover_exhaustion(docs, today, mode, supplies)
        docs = [md.load(d.path) for d in docs]
    for d in docs:
        name = str(d.front.get("name")).split()[0]
        hp = dict(d.front.get("hp") or {})
        hdice = dict(d.front.get("hit-dice") or {})
        level = int(d.front.get("level") or 1)
        left = int(hdice.get("left", level))
        cur, mx = int(hp.get("current", 0)), int(hp.get("max", 0))
        bits = []
        if kind == "long":
            back = max(1, level // 2)
            new_left = min(level, left + back)
            hp.pop("temp", None)
            top = resolve.exhaustion_hp_max(mx, int(d.front.get("exhaustion") or 0),
                                            campaign.settings().get("exhaustion", "2014"))
            hp["current"] = top
            hdice["left"] = new_left
            bits.append(f"HP {cur}→{top}/{top}")
            bits.append(f"hit dice {left}→{new_left}/{level}")
            reset = _reset_resources(d, ("long", "short"))
        else:
            n = spend.get(name.lower()) or spend.get(str(d.front.get("name")).lower()) or 0
            if n > left:
                raise RestError(f"rest: {name} has {left} hit dice left (asked for {n})")
            die = int(str(hdice.get("die", "d8")).lstrip("d"))
            con = mod((d.front.get("scores") or {}).get("con", 10))
            heal = 0
            for _ in range(n):
                r = roller.die(die)
                got = max(0, r + con)
                heal += got
                lines.append(f"[{name} hit die: d{die} {r} {'+' if con >= 0 else ''}{con} = {got}]")
            new = min(mx, cur + heal)
            hp["current"] = new
            hdice["left"] = left - n
            if n:
                bits.append(f"HP {cur}→{new}/{mx}")
                bits.append(f"hit dice {left}→{left - n}/{level}")
            reset = _reset_resources(d, ("short",))
        d.set_front("hp", hp)
        d.set_front("hit-dice", hdice)
        d.save()
        if int(hp.get("current") or 0) > 0:
            import conditions_ext
            woke = conditions_ext.clear_dying(md.load(d.path), "rested")
            lines += woke
        if reset:
            bits.append("reset: " + ", ".join(reset))
        line = f"rest {kind} · {name}" + (" · " + " · ".join(bits) if bits else " · nothing to recover")
        journal.log_delta(line)
        lines.append(f"[{line}]")
    clk, data = clock.advance("+8h" if kind == "long" else "+1h")
    return lines + clk, data


def _recover_exhaustion(docs, today, mode, supplies):
    """A long rest with food and water removes one level of exhaustion."""
    import conditions_ext
    out = []
    for d in docs:
        if not int(d.front.get("exhaustion") or 0):
            continue
        ate = mode == "off" or not supplies.counts_here(d) or supplies.ate_today(d, today)
        if ate:
            out += conditions_ext.exhaust(str(d.front.get("name")), "-1", "long rest")
        else:
            out.append(f"[{str(d.front.get('name')).split()[0]}: no food, so the long rest removes no exhaustion]")
    return out


def cmd_rest(ctx):
    a = ctx.args
    lines, data = rest(a.kind, a.names, a.hd, a.interrupted, ctx.roller)
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("rest", parents=[g], help="rest short|long [PCs] [--hd Kael=2]")
    p.add_argument("kind", choices=["short", "long"])
    p.add_argument("names", nargs="*")
    p.add_argument("--hd", action="append", default=[], help="short rest: Kael=2 hit dice to spend")
    p.add_argument("--interrupted", action="store_true")
    p.set_defaults(func=cmd_rest)
