"""`gm.py monster new "<name>" --from "<base>" | list [--all] | show <name>` — custom
monsters (docs/design/04 → Custom-bestiary file; 07 → Custom monsters; lib/bestiary.py).

`new` makes a creature in the active campaign's `custom-bestiary/<slug>.md`:
- `--from "<SRD monster>"` (or one already in this campaign's custom-bestiary) copies the
  stat block into an editable file, pre-filled with every number, trait and attack, so a
  custom creature is "a similar monster, renamed and re-themed": rename the attacks, add a
  damage rider or a trait, change resistances, set `cr`/`xp`, and write a Description and a
  Backstory;
- `--from "<other-campaign>:<monster>"` copies a creature from another campaign's
  custom-bestiary as it is (backstory included), renamed if you give a new name. This is
  the only way creatures cross campaigns: during play each campaign sees only its own.
`list` shows this campaign's creatures; `list --all` every campaign's (to pick one to
copy). Once the file exists, every tool finds the creature by name: `combat start --add
"srd:frost yeti"`, `ENCOUNTER … frost yeti ×1`, `statblock: frost yeti`, `srd monster`.
"""
import re
from pathlib import Path

from lib import bestiary, campaign, md, srd
from lib.errors import ToolError

SIZE_LETTER = {"tiny": "T", "small": "S", "medium": "M", "large": "L", "huge": "H", "gargantuan": "G"}


class MonsterError(ToolError):
    pass


def _fmt_cr(cr):
    return {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, f"{cr:g}" if isinstance(cr, (int, float)) else str(cr))


def render(name, base):
    """Markdown for a new bestiary file copied from Monster `base`."""
    r = base.rec
    senses = [f"{k} {str(v).replace(' ft.', '')}" for k, v in base.senses.items() if k != "passive_perception"]
    speed = ", ".join((f"{v}".replace(" ft.", " ft") if k == "walk" else f"{k} {v}".replace(" ft.", " ft"))
                      for k, v in base.speed.items() if k != "hover")
    origin = "custom" if getattr(base, "custom", False) else "SRD"
    front = {
        "name": name, "kind": "monster", "based-on": f"{base.name} ({origin})",
        "size": SIZE_LETTER.get(str(r.get("size", "medium")).lower(), "M"), "type": r.get("type", "monstrosity"),
        "ac": base.ac, "ac-note": base.ac_note or "natural", "hp": base.hp, "hp-dice": base.hp_roll,
        "speed": speed or "30 ft", "scores": dict(base.scores), "prof": base.prof, "saves": dict(base.saves),
        "skills": dict(base.skills), "senses": senses, "passive-perception": base.passive_perception(),
        "resistances": list(base.resist), "immunities": list(base.immune), "vulnerabilities": list(base.vuln),
        "condition-immunities": [c.get("name", "") for c in r.get("condition_immunities") or []],
        "cr": _fmt_cr(base.cr), "xp": base.xp,
    }
    lines = ["---"]
    for k, v in front.items():
        text = md.fmt_value(v)
        lines.append(f"{k}: {text}" if text != "" else f"{k}:")
    lines += ["---", "", f"# {name}", "", "## Description",
              f"(copied from {base.name}: rewrite what it looks like, sounds like and how it fights)", "",
              "## Traits"]
    lines += [f"- **{s['name']}.** {' '.join(s.get('desc', '').split())}" for s in r.get("special_abilities", [])] \
        or ["(none)"]
    lines += ["", "## Attacks", "| name | hit | damage | range | notes |", "|------|-----|--------|-------|-------|"]
    for a in base.attacks():
        notes = "" if not getattr(base, "custom", False) else a.get("notes", "")
        lines.append(f"| {a['name']} | {a['hit']} | {a['damage']} | {a['range']} | {notes} |")
    attack_names = {a["name"] for a in base.attacks()}
    others = [a for a in r.get("actions", []) if a["name"].lower() not in attack_names]
    lines += ["", "## Actions"]
    lines += [f"- **{a['name']}.** {' '.join(a.get('desc', '').split())}" for a in others] or ["(none)"]
    reactions = r.get("reactions") or []
    lines += ["", "## Reactions"]
    lines += [f"- **{a['name']}.** {' '.join(a.get('desc', '').split())}" for a in reactions] or ["(none)"]
    lines += ["", "## Backstory", "(optional: who this creature is, what it wants, what it fears)", ""]
    return "\n".join(lines)


def new(name, base_name):
    slug = campaign.slugify(name)
    if not slug:
        raise MonsterError("monster new: give a name")
    folder = bestiary.folder()
    p = folder / f"{slug}.md"
    if p.exists():
        raise MonsterError(f"monster new: {p} already exists")
    where = f"campaigns/{campaign.root().name}/{bestiary.FOLDER}/{slug}.md"
    other, sep, mon = base_name.partition(":")
    if sep and other.strip() not in ("srd", "monster"):
        src = bestiary.find_in(other.strip(), mon.strip())
        if src is None:
            raise MonsterError(f"monster new --from: campaign {other.strip()!r} has no custom monster {mon.strip()!r}")
        text = src.read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
        old = md.load(src).front.get("name") or src.stem
        text = re.sub(r"^name: .*$", f"name: {name}", text, count=1, flags=re.M)
        text = re.sub(r"^based-on: (.*)$", lambda m: f"based-on: {old} from campaigns/{other.strip()} ({m.group(1)})",
                      text, count=1, flags=re.M)
        text = re.sub(r"^# .*$", f"# {name}", text, count=1, flags=re.M)
        folder.mkdir(parents=True, exist_ok=True)
        md.new(p, text).save()
        return f"[monster new: {where} · copied from campaigns/{other.strip()}/{bestiary.FOLDER}/{src.name} · edit it to fit]"
    try:
        base = srd.monster(base_name)
    except srd.SrdError as e:
        raise MonsterError(f"monster new --from: {e}") from None
    folder.mkdir(parents=True, exist_ok=True)
    md.new(p, render(name, base)).save()
    return f"[monster new: {where} · from {base.name} · CR {_fmt_cr(base.cr)} · edit it, then `srd monster {name}`]"


def _line(p, scope):
    f = md.load(p).front
    return f"[{f.get('name')} · CR {f.get('cr')} ({f.get('xp')} XP) · {scope} · based on {f.get('based-on') or '—'}]"


def list_lines(all_=False):
    if all_:
        out = [_line(p, c) for c, p in bestiary.all_campaign_files()]
    else:
        out = [_line(p, campaign.root().name) for p in bestiary.files()]
    return out or ["[no custom monsters]"]


def cmd_monster(ctx):
    a = ctx.args
    if a.action == "new":
        if not a.name or not a.from_:
            raise MonsterError('monster new "<name>" --from "<SRD monster | other-campaign:monster>"')
        lines = [new(" ".join(a.name), a.from_)]
    elif a.action == "list":
        lines = list_lines(a.all)
    else:
        if not a.name:
            raise MonsterError("monster show <name>")
        lines = srd.monster(" ".join(a.name)).block()
    for line in lines:
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("monster", parents=[g], help="custom monsters: new --from <base> | list [--all] | show")
    p.add_argument("action", choices=["new", "list", "show"])
    p.add_argument("name", nargs="*")
    p.add_argument("--from", dest="from_", help='an SRD monster, or "<other-campaign>:<monster>" to copy one')
    p.add_argument("--all", action="store_true", help="list: every campaign's custom-bestiary")
    p.set_defaults(func=cmd_monster)
