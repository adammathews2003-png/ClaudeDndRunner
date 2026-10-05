"""`gm.py juice [on | off | <value> | cooldown <n> | waive | status]` — Wacky Juice
table configuration and the GM's waive (docs/design/06 → `gm.py juice`; 02 → Wacky Juice;
04 → Campaign file → Wacky Juice). The roll itself lives in lib/wacky.py and runs from
`brief --hook`.

`on` / `off` / `<value>` (0-100) / `cooldown <n>` write the setting into campaign.md
(current.md when there is none) and log a public `[juice] …` line. `waive` clears the
pending juice with a `(GM) [juice] Name — waived` line. `status` (the default) prints
the settings, the hook state and this session's counts.
"""
from lib import campaign, journal, wacky
from lib.errors import ToolError


class JuiceError(ToolError):
    pass


def _set(key, value):
    doc = campaign.settings_doc()
    old = campaign.settings()[key]
    doc.set_front(key, value)
    doc.save()
    return old


def status():
    on, value, cooldown = wacky.config()
    st = wacky.load()
    counts = wacky.session_counts()
    since = "never fired" if st["prompts-since"] is None else (
        f"{st['prompts-since']} prompt{'s' if st['prompts-since'] != 1 else ''} since last")
    line = (f"[Juice: {'on' if on else 'off'} · {value}% · cooldown {cooldown} · {since} · "
            f"pending: {st['pending-name'] or '—'} · this session: {counts['used']} used, "
            f"{counts['waived']} waived, {counts['unlogged']} unlogged]")
    return line, {"on": on, "value": value, "cooldown": cooldown, **st, "session": counts}


def run(words):
    words = [w.lower() for w in words]
    if not words or words == ["status"]:
        return status()
    head = words[0]
    if head in ("on", "off") and len(words) == 1:
        old = _set("wacky-juice", head)
        journal.log_delta(f"[juice] {old} → {head}" if str(old) != head else f"[juice] {head}")
        return f"[juice {head}]", {"wacky-juice": head}
    if head == "waive" and len(words) == 1:
        name = wacky.waive()
        if name is None:
            return "[juice: nothing pending]", {"waived": None}
        return f"[juice waived: {name}]", {"waived": name}
    if head == "cooldown" and len(words) == 2:
        n = _number(words[1], "cooldown", 0, 1000)
        old = _set("wacky-juice-cooldown", n)
        journal.log_delta(f"[juice] cooldown {old} → {n}")
        return f"[juice cooldown {old} → {n}]", {"wacky-juice-cooldown": n}
    if len(words) == 1:
        n = _number(head, "value", 0, 100)
        old = _set("wacky-juice-value", n)
        journal.log_delta(f"[juice] value {old} → {n}")
        return f"[juice value {old} → {n}]", {"wacky-juice-value": n}
    raise JuiceError("juice: want on | off | <value 0-100> | cooldown <n> | waive | status")


def _number(text, what, lo, hi):
    try:
        n = int(text.rstrip("%"))
    except ValueError:
        raise JuiceError(f"juice: want on | off | <value 0-100> | cooldown <n> | waive | status "
                         f"(got {text!r})") from None
    if not lo <= n <= hi:
        raise JuiceError(f"juice {what}: {n} is outside {lo}-{hi}")
    return n


def cmd_juice(ctx):
    line, data = run(ctx.args.words)
    ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("juice", parents=[g], help="Wacky Juice: on | off | <value> | cooldown <n> | waive | status")
    p.add_argument("words", nargs="*")
    p.set_defaults(func=cmd_juice)
