"""Lingering injuries (docs/design/02 → Table mechanics → Phase 15 → Rare situations; 06 →
Table mechanics → Phase 15; plan.md Phase 15 item 11).

    injury Kael [--roll N]

`lingering-injuries: off | on` (default off). While on, `hp`/`dmg`/`atk` append
`[consider: gm.py injury Kael]` when a PC takes a critical hit or drops to 0 HP
(conditions_ext.after_hp); whether it happens is the GM's call. `injury` rolls on the
campaign's own `tables/injuries.md` — the engine ships no injury table (non-SRD rules
text is campaign-supplied) — with columns `| roll | result | effect | cure |` (`effect`
and `cure` optional; the die is the highest roll). The result goes into the PC's
`## Features & abilities` as `- **Injury: <result>** (injury) — <effect> · cure: <cure>`
and is logged publicly. `--roll N` takes a die the table rolled itself.
"""
from lib import campaign, dice, journal, md
from lib.errors import ToolError
import mutations


class InjuryError(ToolError):
    pass


def table_path():
    return campaign.root() / "tables" / "injuries.md"


def _rows():
    p = table_path()
    if not p.exists():
        raise InjuryError("injury: the campaign has no tables/injuries.md (campaign-supplied: "
                          "| roll | result | effect | cure |)")
    doc = md.load(p)
    t = None
    for i, line in enumerate(doc.body):
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and "roll" in cells and "result" in cells:
            t = md.Table(doc, i)
            break
    if t is None or not t.rows:
        raise InjuryError("tables/injuries.md has no | roll | result | rows")
    out = []
    for r in t.rows:
        lo, hi = dice._range(r.get("roll", ""), "injuries")
        out.append((lo, hi, r))
    return out


def injury(name, roll=None, roller=None):
    if str(campaign.settings().get("lingering-injuries", "off")).strip().lower() != "on":
        raise InjuryError("lingering-injuries: off (campaign setting)")
    c = mutations.creature(name)
    if not c.is_pc or c.doc is None:
        raise InjuryError(f"injury: {c.name} is not a PC")
    rows = _rows()
    sides = max(hi for _, hi, _ in rows)
    n = roll if roll is not None else (roller or dice.Roller()).die(sides)
    if not 1 <= n <= sides:
        raise InjuryError(f"injury: the roll is 1–{sides}")
    hit = next((r for lo, hi, r in rows if lo <= n <= hi), None)
    if hit is None:
        raise InjuryError(f"tables/injuries.md: no row covers {n}")
    who = c.name.split()[0]
    result = hit.get("result", "").strip()
    effect, cure = hit.get("effect", "").strip(), hit.get("cure", "").strip()
    line = f"- **Injury: {result}** (injury)" + (f" — {effect}" if effect else "") + (f" · cure: {cure}" if cure else "")
    doc = md.load(c.doc.path)
    doc.append_line("Features & abilities", line)
    doc.save()
    body = f"injury {who}: d{sides} {n} → {result}" + (f" ({effect})" if effect else "")
    journal.log_delta(body)
    return [f"[{body}" + (f" · cure: {cure}" if cure else "") + "]"]


def cmd_injury(ctx):
    lines = injury(ctx.args.target, ctx.args.roll, ctx.roller)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("injury", parents=[g], help="injury PC: roll the campaign's lingering-injury table")
    p.add_argument("target")
    p.add_argument("--roll", type=int, help="a die the table rolled itself")
    p.set_defaults(func=cmd_injury)
