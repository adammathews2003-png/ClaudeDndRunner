"""`gm.py xp award <N | from-combat> [--to Kira,Kael | --present] --reason "…"`,
`xp show [<pc>]`, `xp set <pc> <N> --reason "…"` (docs/design/06 → `gm.py xp`; 04 →
Advancement; 02 → Level-up flow; plan.md Phase 6 item 5).

Settings come from campaign.md, else current.md (`advancement: milestone | xp`,
`xp-tracking: on | off`, `xp-absent: full | half | none`). With tracking off every
command refuses. `award` splits evenly among the recipients (present PCs by default,
or `--to`); an absent PC named in `--to` gets `xp-absent` of a share; remainders are
dropped (DMG). Crossing a threshold sets `level-pending` (highest level reached) under
`advancement: xp`, and is only noted under milestone. `from-combat` reads
`.gm/last-combat.json` (combat end) and refuses a second award of the same fight.
Every change is one journaled delta with the reason, so `undo` reverses it.
"""
import json
import re

from lib import campaign, journal, md, xp
from lib.chargen import as_list
from lib.errors import ToolError


class XpError(ToolError):
    pass


def _settings():
    s = campaign.settings()
    if str(s.get("xp-tracking", "on")).lower() == "off":
        raise XpError("xp: tracking is off for this campaign (xp-tracking: off)")
    return s


def _pcs(names):
    out = []
    for n in names:
        m = campaign.resolve(n)
        if not m.is_pc or not m.path:
            raise XpError(f"{n!r} is not a PC")
        out.append(md.load(m.path))
    return out


def _short(doc):
    return str(doc.front.get("name") or "?").split()[0]


def _gain(doc, amount, s):
    """Add XP to one PC file; returns the output fragment."""
    level = int(doc.front.get("level") or 1)
    old = xp.current(doc.front)
    if str(s.get("advancement", "milestone")).lower() == "xp":
        old = max(old, xp.start_xp(level))   # 04: switching to xp raises totals to the level's threshold
    new = old + amount
    doc.set_front("xp", new)
    reached = xp.level_for(new)
    frag = f"{_short(doc)} {old:,}→{new:,}"
    if reached > level:
        if str(s.get("advancement", "milestone")).lower() == "xp":
            pend = doc.front.get("level-pending")
            top = max(reached, pend if isinstance(pend, int) else 0)
            doc.set_front("level-pending", top)
            frag += f" ★ L{reached} at {xp.THRESHOLDS[reached]:,}: level-up pending"
        else:
            frag += f" ★ past the L{reached} threshold (milestone: no level-up)"
    doc.save()
    return frag


def award(amount_text, to=None, reason="", present_only=True):
    s = _settings()
    if not reason:
        raise XpError("xp award: give a --reason")
    combat = None
    if amount_text == "from-combat":
        p = campaign.root() / ".gm" / "last-combat.json"
        if not p.exists():
            raise XpError("xp award from-combat: no combat tally (combat end writes one)")
        combat = json.loads(p.read_text(encoding="utf-8"))
        if combat.get("awarded"):
            raise XpError("xp award from-combat: that fight was already awarded")
        amount = int(combat.get("total") or 0)
    else:
        if not re.fullmatch(r"\d+", str(amount_text)):
            raise XpError(f"xp award: want a number or from-combat, got {amount_text!r}")
        amount = int(amount_text)
    if to:
        docs = _pcs(as_list(to))
    else:
        docs = [d for d in campaign.pcs() if d.front.get("present") is not False]
    if not docs:
        raise XpError("xp award: nobody to award (no present PCs)")
    present = [d for d in docs if d.front.get("present") is not False]
    share = amount // max(1, len(present) or len(docs))
    absent_rule = str(s.get("xp-absent", "full")).lower()
    frags = []
    for d in docs:
        if d.front.get("present") is False:
            part = share if absent_rule == "full" else (share // 2 if absent_rule == "half" else 0)
        else:
            part = share
        frags.append(_gain(d, part, s) + ("" if part == share else f" (absent: {part:,})"))
    if combat is not None:
        combat["awarded"] = True
        (campaign.root() / ".gm" / "last-combat.json").write_text(json.dumps(combat, indent=1), encoding="utf-8")
    line = f"XP +{share:,} each → " + " · ".join(frags)
    journal.log_delta(f"{line} — {reason}")
    return f"[{line}]", {"amount": amount, "each": share}


def show(name=None):
    s = _settings()
    docs = _pcs([name]) if name else campaign.pcs()
    out = []
    for d in docs:
        level = int(d.front.get("level") or 1)
        cur = xp.current(d.front)
        nxt, need = xp.next_threshold(level)
        tail = f"L{nxt} at {need:,}" if nxt else "max level"
        if nxt and cur >= need:
            tail += (" — level-up pending" if str(s.get("advancement")).lower() == "xp"
                     else " (milestone: levels come from the story)")
        out.append(f"{_short(d)}: L{level} · {cur:,} XP · {tail}")
    return [f"[{x}]" for x in out], {}


def set_xp(name, value, reason=""):
    s = _settings()
    if not reason:
        raise XpError("xp set: give a --reason")
    d = _pcs([name])[0]
    old = xp.current(d.front)
    frag = _gain(d, int(value) - old, s)
    journal.log_delta(f"xp set {frag} — {reason}")
    return f"[xp set {frag}]", {}


def cmd_xp(ctx):
    a = ctx.args
    if a.action == "award":
        if not a.args:
            raise XpError("xp award <N | from-combat>")
        line, data = award(a.args[0], a.to, a.reason or "", present_only=a.present)
        lines = [line]
    elif a.action == "show":
        lines, data = show(a.args[0] if a.args else None)
    else:
        if len(a.args) != 2 or not a.args[1].isdigit():
            raise XpError("xp set <pc> <N> --reason \"…\"")
        line, data = set_xp(a.args[0], a.args[1], a.reason or "")
        lines = [line]
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("xp", parents=[g], help="xp award | show | set (unless xp-tracking: off)")
    p.add_argument("action", choices=["award", "show", "set"])
    p.add_argument("args", nargs="*")
    p.add_argument("--to", help="Kira,Kael (default: present PCs)")
    p.add_argument("--present", action="store_true", help="present PCs (the default)")
    p.add_argument("--reason")
    p.set_defaults(func=cmd_xp)
