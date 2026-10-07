"""Inspiration (docs/design/02 → Table mechanics → Phase 15; 04 → PC file, Added by Phases
13–15; 06 → Table mechanics → Phase 15; plan.md Phase 15 item 2).

    inspire Kira ["the toast to the dead"]     award it (one at a time per PC)
    atk|save|check … --insp                    spend it on this d20

`inspiration: advantage | reroll | off` (default advantage). The award writes
`inspiration: true` on the PC (the key is only there while she has it) and a public log
line with the reason; a second award while she has it is refused. `--insp` spends it:
- advantage (2014): the roll has advantage (cancelled by disadvantage as usual).
- reroll (2024): the d20 given (or rolled) is the reroll, and it stands. After a roll the
  player wants back: `undo`, then the same command with the new d20 and `--insp`.
Without inspiration (or with the setting off) `--insp` is an error and nothing is spent.
The brief's party line shows `★` while a PC holds it.

Python API for roll.py: `spend(c, mode)` -> (mode, note); `holds(front)`.
"""
from lib import campaign, journal
from lib.errors import ToolError
import mutations


class InspirationError(ToolError):
    pass


def setting():
    return str(campaign.settings().get("inspiration", campaign.SETTINGS["inspiration"])).strip().lower()


def holds(front):
    return front.get("inspiration") is True


def inspire(name, reason=""):
    if setting() == "off":
        raise InspirationError("inspiration: off (campaign setting) — nothing to award")
    c = mutations.creature(name)
    if not c.is_pc or c.doc is None:
        raise InspirationError(f"inspire: {c.name} is not a PC")
    who = c.name.split()[0]
    if holds(c.doc.front):
        raise InspirationError(f"{who} already has inspiration (one at a time; spend it first)")
    c.doc.set_front("inspiration", True)
    c.doc.save()
    body = f"inspire {who}" + (f" — {reason}" if reason else "")
    journal.log_delta(body)
    return [f"[{body} · ★ ({setting()})]"]


def spend(c, mode):
    """Spend `c`'s inspiration on a d20 (roll.py's `--insp`). -> (mode, note). Raises when
    there is none to spend."""
    how = setting()
    if how == "off":
        raise InspirationError("--insp: inspiration: off (campaign setting)")
    if not c.is_pc or c.doc is None:
        raise InspirationError(f"--insp: {c.name} is not a PC")
    who = c.name.split()[0]
    if not holds(c.doc.front):
        raise InspirationError(f"--insp: {who} has no inspiration (gm.py inspire {who} \"why\")")
    from lib import md
    doc = md.load(c.doc.path)
    doc.del_front("inspiration")
    doc.save()
    c.doc.front.pop("inspiration", None)
    journal.log_delta(f"inspiration {who} spent ({how})")
    if how == "reroll":
        return mode, "inspiration: reroll (this roll stands)"
    if mode == "dis":
        return None, "inspiration: advantage, adv and dis cancel"
    return "adv", "inspiration: advantage"


def cmd_inspire(ctx):
    lines = inspire(ctx.args.target, ctx.args.reason or "")
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("inspire", parents=[g], help='inspire PC ["why"]: award inspiration')
    p.add_argument("target")
    p.add_argument("reason", nargs="?")
    p.set_defaults(func=cmd_inspire)
