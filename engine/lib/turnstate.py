"""What the creature who's up has left this turn (docs/design/06 → `gm.py turn`; rules/
combat-basics.md → On your turn).

The budget is one line right under the `## Combat` heading:

    Turn: Kael · action yes · attacks 0/2 · bonus yes · object yes · move 30/30

`action` is `yes` (unused), `attack` (an Attack action under way) or `no`; `attacks` is
attacks made / attacks per Attack action (a PC's Extra Attack from `## Features &
abilities`; a stat block's Multiattack count, the larger option when it offers two; 1 with
no Multiattack; `?` when the count can't be read); `bonus` and
`object` are `yes`/`no`; `move` is feet left / speed (Dash adds speed to both). `combat start`/`next` reset it for whoever is up; `atk` (the action,
or the bonus action with `--bonus`), `move` and `turn use …` spend it. Nothing here ends a
turn: only `combat next` does, when the player says they're done.
"""
import re

from . import creatures

_LINE = re.compile(r"^Turn:\s*(?P<name>[^·]+?)\s*·\s*action (?P<action>\w+)\s*·"
                   r"(?:\s*attacks (?P<made>\d+)/(?P<per>\d+|\?)\s*·)?\s*bonus (?P<bonus>\w+)\s*·"
                   r"\s*object (?P<object>\w+)\s*·\s*move (?P<left>-?\d+(?:\.\d+)?)/(?P<speed>\d+(?:\.\d+)?)\s*$")


def speed_of(c):
    """Walking speed in feet: the PC/NPC file's `speed`, else the stat block's walk, else 30."""
    try:
        v = c.front.get("speed")
    except Exception:  # noqa: BLE001 — a row with no file
        v = None
    m = re.match(r"^\s*(\d+)", str(v or ""))
    if m:
        return int(m.group(1))
    mon = getattr(c, "monster", None)
    if mon is not None:
        m = re.match(r"^\s*(\d+)", str((mon.speed or {}).get("walk", "")))
        if m:
            return int(m.group(1))
    return 30


_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def multiattack(rec):
    """Attacks in a stat block's Multiattack (1 without one; None when unreadable)."""
    for a in (rec or {}).get("actions", []):
        if str(a.get("name", "")).lower() == "multiattack":
            counts = [_WORDS[m.group(1).lower()] for m in
                      re.finditer(r"makes (one|two|three|four|five|six)\b[^.]*?attacks?", a.get("desc", ""), re.I)]
            return max(counts) if counts else None
    return 1


def attacks_per_action(c):
    """Attacks per Attack action: a PC's Extra Attack (2)/(3), else an NPC's Multiattack."""
    if not getattr(c, "is_pc", False):
        mon = getattr(c, "monster", None)
        return multiattack(mon.rec) if mon is not None else None
    try:
        text = c.doc.text() if c.doc is not None else ""
    except Exception:  # noqa: BLE001
        text = ""
    best = 1
    for m in re.finditer(r"extra attack(?:\s*\((\d)\))?", text, re.I):
        best = max(best, 1 + int(m.group(1) or 1))
    return best


def _heading(doc):
    for i, lvl, text in doc.headings():
        if lvl == 2 and text.lower().startswith("combat"):
            return i
    return None


def read(doc):
    """The budget dict, or None (not in combat / no Turn line)."""
    i = _heading(doc)
    if i is None or i + 1 >= len(doc.body):
        return None
    m = _LINE.match(doc.body[i + 1].strip())
    if not m:
        return None
    d = m.groupdict()
    d["name"] = d["name"].strip()
    d["left"], d["speed"] = float(d["left"]), float(d["speed"])
    d["made"] = int(d["made"] or 0)
    d["per"] = None if d["per"] in (None, "?") else int(d["per"])
    return d


def write(doc, d):
    i = _heading(doc)
    per = "?" if d.get("per") is None else d["per"]
    line = (f"Turn: {d['name']} · action {d['action']} · attacks {d.get('made', 0)}/{per} · bonus {d['bonus']} · "
            f"object {d['object']} · move {d['left']:g}/{d['speed']:g}")
    if i + 1 < len(doc.body) and doc.body[i + 1].startswith("Turn:"):
        doc.body[i + 1] = line
    else:
        doc.body.insert(i + 1, line)


def reset(doc, name):
    """A fresh budget for `name` (combat start / next). Returns it."""
    try:
        c = creatures.get(name, doc)
        sp, per = speed_of(c), attacks_per_action(c)
    except Exception:  # noqa: BLE001 — an unresolvable row still gets a default turn
        sp, per = 30, None
    d = {"name": name, "action": "yes", "made": 0, "per": per, "bonus": "yes", "object": "yes",
         "left": float(sp), "speed": float(sp)}
    write(doc, d)
    return d


def is_up(d, name):
    return d is not None and d["name"].lower() == str(name).lower()


def left_text(d):
    bits = []
    if d["action"] == "yes":
        bits.append("action")
    elif d["action"] == "attack":
        if d.get("per") is None:
            bits.append("the rest of the Attack action (Multiattack per the stat block)")
        else:
            n = d["per"] - d["made"]
            bits.append(f"{n} more attack{'s' if n != 1 else ''} this action")
    if d["bonus"] == "yes":
        bits.append("bonus action")
    if d["left"] > 0:
        bits.append(f"{d['left']:g} ft of movement")
    if d["object"] == "yes":
        bits.append("object interaction")
    return bits


def left_line(d):
    bits = left_text(d)
    if not bits:
        return f"[{d['name']} has used everything this turn — combat next]"
    return f"[{d['name']} still has: {' · '.join(bits)} — ask if they're done before combat next]"


def turn_start_line(d):
    return (f"[{d['name']}'s turn: action · bonus action · {d['speed']:g} ft of movement · object "
            "interaction · reaction (once per round)]")
