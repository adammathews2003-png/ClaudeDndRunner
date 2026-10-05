"""`gm.py monster new <name> --from <base> [--shared] | list | show <name>` — custom
monsters (docs/design/04 → Bestiary file; 07 → Custom monsters; lib/bestiary.py).

`new` copies a base stat block (an SRD monster, or another custom one) into an editable
markdown file, pre-filled with every number, trait and attack, so a custom creature is
"a similar monster, renamed and re-themed": rename the attacks, add a damage rider or a
trait, change resistances, set `cr`/`xp`, and write a Description and a Backstory. It goes
to `campaigns/<active>/bestiary/<slug>.md` (the campaign's own), or with `--shared` to
`bestiary/<slug>.md` (reusable by every campaign). Once the file exists, every tool finds
the creature by name: `combat start --add "srd:frost yeti"`, `ENCOUNTER … frost yeti ×1`,
`statblock: frost yeti`, `srd monster frost yeti`, `encounter threat`.
"""
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


def new(name, base_name, shared=False):
    slug = campaign.slugify(name)
    if not slug:
        raise MonsterError("monster new: give a name")
    folder = bestiary.SHARED if shared else campaign.root() / "bestiary"
    p = folder / f"{slug}.md"
    if p.exists():
        raise MonsterError(f"monster new: {p} already exists")
    existing = bestiary.find(name)
    if existing is not None and not shared:
        pass  # a campaign file may shadow a shared one on purpose
    try:
        base = srd.monster(base_name)
    except srd.SrdError as e:
        raise MonsterError(f"monster new --from: {e}") from None
    folder.mkdir(parents=True, exist_ok=True)
    if shared:   # engine content, versioned by the engine repo: not a campaign's undo journal
        p.write_text(render(name, base), encoding="utf-8")
    else:
        md.new(p, render(name, base)).save()
    where = "bestiary/" if shared else f"campaigns/{campaign.root().name}/bestiary/"
    return f"[monster new: {where}{slug}.md · from {base.name} · CR {_fmt_cr(base.cr)} · edit it, then `srd monster {name}`]"


def list_lines():
    out = []
    for p in bestiary.all_files():
        f = md.load(p).front
        scope = "shared" if Path(p).resolve().parent == bestiary.SHARED.resolve() else "campaign"
        out.append(f"[{f.get('name')} · CR {f.get('cr')} ({f.get('xp')} XP) · {scope} · based on {f.get('based-on') or '—'}]")
    return out or ["[no custom monsters]"]


def cmd_monster(ctx):
    a = ctx.args
    if a.action == "new":
        if not a.name or not a.from_:
            raise MonsterError('monster new "<name>" --from "<srd or custom monster>" [--shared]')
        lines = [new(" ".join(a.name), a.from_, a.shared)]
    elif a.action == "list":
        lines = list_lines()
    else:
        if not a.name:
            raise MonsterError("monster show <name>")
        lines = srd.monster(" ".join(a.name)).block()
    for line in lines:
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("monster", parents=[g], help="custom monsters: new --from <base> [--shared] | list | show")
    p.add_argument("action", choices=["new", "list", "show"])
    p.add_argument("name", nargs="*")
    p.add_argument("--from", dest="from_")
    p.add_argument("--shared", action="store_true", help="bestiary/ (all campaigns) instead of the campaign's")
    p.set_defaults(func=cmd_monster)
