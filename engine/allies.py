"""Allied creatures and mounts: familiars, animal companions, summons, hirelings
(docs/design/02 → Table mechanics → Phase 15 → Allied creatures, Rare situations; 04 → PC
file `## Companions`, Scene state added (`ctrl Kira`); 06 → Table mechanics → Phase 15;
plan.md Phase 15 items 6 and 10).

    companion add Kira Ash srd:owl --acts own|with [--hp 1/1] [--note "familiar"]
    companion drop Kira Ash | companion list
    hire "Bren" --wage "2 gp/day" [--by Kira|party] [--loyalty 10] [--statblock guard]
    mount Kael Horse [--independent] | dismount Kael

- `companion add` writes a `## Companions` row (`| name | ref | hp | acts | notes |`;
  `acts`: `own init` | `with me` | `mount`). `combat start` adds the companions of the PCs
  in the fight as `party` rows with `ctrl <PC>` (own init: rolled like a monster, or
  `--init Ash=N`; with me / mount: the controller's initiative, placed right after them).
  `combat next` names the controller (`up: Ash (Kira's)`); `combat end` writes the HP back
  to the Companions row.
- `hire` makes (or updates) an NPC file with `hired-by:`, `wage:` and `loyalty:` (0–20,
  default 10). Hirelings join a fight on the party's side. Wages are charged each dawn
  only under `upkeep: on` (default off: bookkeeping); under it a PC employer pays from
  their coin and a party hire prints what is due. A hireling's morale check (combat.py)
  is a WIS save against DC 20 − loyalty (loyalty 10 → DC 10, the foes' number).
- `mount Kael Horse` links rider and mount (`mounted on Horse` / `ridden by Kael`). A
  controlled mount (the default; `--independent` for one that acts on its own) takes the
  rider's initiative right after them, and `combat next` reminds that it may only Dash,
  Disengage or Dodge. Knocking the rider prone asks for the DC 10 DEX save; knocking the
  mount prone drops the rider (after_cond). Out of combat the mount is one of the rider's
  Companions (`acts: mount`), so the next `combat start` seats them again.

Python API for combat/clock/conditions_ext: `combat_rows(...)`, `order(...)`,
`write_back(row)`, `turn_note(row)`, `controller(row)`, `after_cond(name, cname)`,
`wage_lines(old, new)`.
"""
import re

from lib import campaign, creatures, gametime, journal, md, srd
from lib.creatures import fmt_hp_cell, norm_name, parse_hp_cell
from lib.errors import ToolError
import mutations

COLS = ["name", "ref", "hp", "acts", "notes"]
ACTS = {"own": "own init", "own init": "own init", "with": "with me", "with me": "with me", "mount": "mount"}
_CTRL = re.compile(r"^ctrl\s+(\S+)", re.I)
_MOUNTED = re.compile(r"^mounted on\s+(.+)$", re.I)
_RIDDEN = re.compile(r"^ridden by\s+(.+)$", re.I)


class AlliesError(ToolError):
    pass


def _conds(cell):
    return mutations._conds_from_cell(cell)


def _pc(name):
    c = mutations.creature(name)
    if not c.is_pc or c.doc is None:
        raise AlliesError(f"{c.name} is not a PC")
    return c, md.load(c.doc.path), c.name.split()[0]


def companions(doc):
    t = doc.table("Companions") if doc is not None else None
    return [r for r in (t.rows if t else []) if r.get("name", "").strip()]


def _set_rows(doc, rows):
    lines = ["| " + " | ".join(COLS) + " |", "|" + "|".join("-" * (len(c) + 2) for c in COLS) + "|"]
    lines += ["| " + " | ".join(str(r.get(c, "")) for c in COLS) + " |" for r in rows]
    span = doc.section("Companions")
    if span is None:
        at = doc.section("Inventory")
        block = ["## Companions"] + lines + [""]
        if at is not None:
            doc.body[at[0]:at[0]] = block
        else:
            if doc.body and doc.body[-1].strip():
                doc.body.append("")
            doc.body += block[:-1]
        return
    t = doc.table("Companions")
    if t is not None:
        doc.body[t.start:t.start + 2 + len(t.rows)] = lines
    else:
        doc.body[span[0] + 1:span[0] + 1] = lines


def _monster(ref):
    if ref.lower().startswith("srd:"):
        try:
            return srd.monster(ref[4:])
        except srd.SrdError:
            return None
    return None


def companion_add(owner, name, ref, acts="own", hp=None, note=""):
    c, doc, who = _pc(owner)
    acts_txt = ACTS.get(acts.strip().lower())
    if acts_txt is None:
        raise AlliesError("--acts: own | with | mount")
    rows = companions(doc)
    if any(r["name"].lower() == name.lower() for r in rows):
        raise AlliesError(f"{who} already has a companion named {name}")
    ref = ref.strip()
    mon = _monster(ref)
    if ref.lower().startswith("srd:") and mon is None:
        raise AlliesError(f"no SRD creature {ref[4:]!r}")
    if hp is None:
        if mon is None:
            raise AlliesError("--hp cur/max is needed when the ref isn't srd:<creature>")
        hp = f"{mon.hp}/{mon.hp}"
    if parse_hp_cell(hp) is None:
        raise AlliesError(f"--hp wants cur/max, got {hp!r}")
    rows.append({"name": name, "ref": ref, "hp": hp, "acts": acts_txt, "notes": note.replace("|", "/")})
    _set_rows(doc, rows)
    doc.save()
    body = f"companion {who} + {name} ({ref}, {acts_txt})"
    journal.log_delta(body)
    return [f"[{body}]"]


def companion_drop(owner, name):
    c, doc, who = _pc(owner)
    rows = companions(doc)
    keep = [r for r in rows if r["name"].lower() != name.lower()]
    if len(keep) == len(rows):
        raise AlliesError(f"{who} has no companion named {name}")
    _set_rows(doc, keep)
    doc.save()
    body = f"companion {who} - {name}"
    journal.log_delta(body)
    return [f"[{body}]"]


def companion_list():
    out = []
    for d in campaign.pcs():
        for r in companions(d):
            out.append(f"{str(d.front.get('name')).split()[0]}: {r['name']} ({r['ref']}, {r['hp']}, {r['acts']})"
                       + (f" — {r['notes']}" if r.get("notes") else ""))
    for d in campaign.npcs():
        if d.front.get("hired-by"):
            out.append(f"hireling: {d.front.get('name')} (by {d.front.get('hired-by')}, {d.front.get('wage') or 'no wage'}, "
                       f"loyalty {d.front.get('loyalty', '?')})")
    return ["[companions] " + (" · ".join(out) if out else "none")]


# ---------- combat ----------

def combat_rows(rows, roller, inits, used):
    """combat start: rows for the companions of the PCs in `rows` (not already there).
    -> ([rows], [(name, init, False)], {companion: controller})."""
    import tempo
    have = {norm_name(r["name"]).lower() for r in rows}
    out, entries, follow = [], [], {}
    for r in list(rows):
        ref = r.get("ref", "")
        if not ref.startswith("pcs/"):
            continue
        p = campaign.root() / (ref + ".md")
        if not p.exists():
            continue
        doc = md.load(p)
        ctl = norm_name(r["name"]).split()[0]
        for comp in companions(doc):
            name = comp["name"].strip()
            if name.lower() in have:
                continue
            mon = _monster(comp.get("ref", ""))
            cell = parse_hp_cell(comp.get("hp", ""))
            hp = fmt_hp_cell(cell[0], cell[1], cell[2]) if cell else (fmt_hp_cell(mon.hp, mon.hp) if mon else "?")
            ac = mon.ac if mon else "?"
            acts = comp.get("acts", "own init").strip().lower()
            given = next((v for k, v in inits.items() if k == name.lower()), None)
            if acts in ("with me", "mount"):
                init = r["init"]
                follow[name] = norm_name(r["name"])
            else:
                init = given if given is not None else roller.d20(mon.mod("dex") if mon else 0).total
            conds = [f"ctrl {ctl}"]
            if acts == "mount" and any(_MOUNTED.match(x) and _MOUNTED.match(x).group(1).lower() == name.lower()
                                       for x in _conds(r.get("conditions"))):
                conds.append(f"ridden by {ctl}")
            glyph = tempo.unique_glyph(name, used)
            used.add(glyph)
            out.append({"init": init, "name": name, "glyph": glyph, "side": "party", "pos": "?",
                        "size": mon.size if mon else "M", "ref": comp.get("ref", ""), "hp": hp, "ac": ac,
                        "conditions": ", ".join(conds), "notes": comp.get("notes", "")})
            entries.append((name, init, False))
            have.add(name.lower())
    return out, entries, follow


def order(ordered, follow):
    """Move each `with me`/mount companion to right after its controller."""
    if not follow:
        return ordered
    rest = [r for r in ordered if norm_name(r["name"]) not in follow]
    for name, ctl in follow.items():
        row = next(r for r in ordered if norm_name(r["name"]) == name)
        at = next((i for i, r in enumerate(rest) if norm_name(r["name"]) == ctl), len(rest) - 1)
        while at + 1 < len(rest) and norm_name(rest[at + 1]["name"]) in follow:
            at += 1
        rest.insert(at + 1, row)
    return rest


def controller(row):
    for c in _conds(row.get("conditions")):
        m = _CTRL.match(c)
        if m:
            return m.group(1)
    return None


def turn_note(row):
    """combat next: what a controlled mount may do, or None."""
    conds = _conds(row.get("conditions"))
    rider = next((_RIDDEN.match(c).group(1) for c in conds if _RIDDEN.match(c)), None)
    if rider and controller(row):
        return (f"[{norm_name(row['name'])} ({rider}'s mount): only Dash, Disengage or Dodge; it moves "
                f"with {rider} on {rider}'s initiative]")
    return None


def write_back(row):
    """combat end: a controlled companion's HP back to its owner's Companions row."""
    ctl = controller(row)
    if not ctl:
        return
    try:
        c = mutations.creature(ctl)
    except mutations.MutationError:
        return
    if c.doc is None:
        return
    doc = md.load(c.doc.path)
    rows = companions(doc)
    name = norm_name(row["name"]).lower()
    hit = next((r for r in rows if r["name"].lower() == name), None)
    cell = parse_hp_cell(row.get("hp", ""))
    if hit is None or cell is None:
        return
    new = f"{cell[0]}/{cell[1]}"
    if hit.get("hp") != new:
        hit["hp"] = new
        _set_rows(doc, rows)
        doc.save()


def after_cond(name, cname):
    """mutations.cond (+prone): a mounted rider's DEX save, a fallen mount's rider."""
    if cname != "prone":
        return []
    try:
        c = mutations.creature(name)
    except mutations.MutationError:
        return []
    conds = _conds(c.combat_row.get("conditions")) if c.combat_row else \
        [str(x) for x in (c.front.get("conditions") or [])]
    who = c.name.split()[0] if c.is_pc else c.name
    for x in conds:
        m = _MOUNTED.match(x)
        if m:
            return [f"[{who} is knocked prone while mounted: DC 10 DEX save or fall off {m.group(1)}, prone "
                    f"within 5 ft (gm.py save {who} dex 10; on a fail gm.py dismount {who})]"]
        m = _RIDDEN.match(x)
        if m:
            return [f"[{c.name} falls: {m.group(1)} is dismounted and lands prone within 5 ft unless they use "
                    f"their reaction to land on their feet (gm.py dismount {m.group(1)})]"]
    return []


# ---------- mounts ----------

def _edit(c, drop_re, add=None):
    state = campaign.load_state()
    c = mutations.creature(c.name, state)
    if c.combat_index >= 0:
        conds = [x for x in _conds(c.combat_row.get("conditions")) if not drop_re.match(x)]
        if add:
            conds.append(add)
        c.combat_table().set(c.combat_index, "conditions", ", ".join(conds) if conds else "—")
        state.save()
    elif c.doc is not None:
        doc = md.load(c.doc.path)
        conds = [str(x) for x in (doc.front.get("conditions") or []) if not drop_re.match(str(x))]
        if add:
            conds.append(add)
        doc.set_front("conditions", conds)
        doc.save()


def mount(rider, steed, independent=False):
    state = campaign.load_state()
    r = mutations.creature(rider, state)
    rname = r.name.split()[0] if r.is_pc else r.name
    if state.table("Combatants") is not None:
        m = mutations.creature(steed, state)
        if m.combat_index < 0 or r.combat_index < 0:
            raise AlliesError("mount: both rider and mount need Combatants rows (add the mount first)")
        mname = m.name
        _edit(r, _MOUNTED, f"mounted on {mname}")
        _edit(m, _RIDDEN, f"ridden by {rname}")
        extra = ""
        if not independent:
            state = campaign.load_state()
            t = state.table("Combatants")
            ri = next(i for i, x in enumerate(t.rows) if norm_name(x["name"]).lower() == r.name.lower())
            mi = next(i for i, x in enumerate(t.rows) if norm_name(x["name"]).lower() == mname.lower())
            row = dict(t.rows[mi])
            row["init"] = t.rows[ri]["init"]
            conds = [x for x in _conds(row.get("conditions")) if not _CTRL.match(x)] + [f"ctrl {rname}"]
            row["conditions"] = ", ".join(conds)
            t.remove(mi)
            ri = next(i for i, x in enumerate(t.rows) if norm_name(x["name"]).lower() == r.name.lower())
            t.insert(ri + 1, row)
            state.save()
            extra = f" · controlled: acts on {rname}'s initiative (Dash, Disengage or Dodge)"
        body = f"mount {rname} on {mname}"
        journal.log_delta(body)
        return [f"[{body}{extra}]"]
    if not r.is_pc or r.doc is None:
        raise AlliesError("mount: out of combat the rider is a PC whose mount is one of their Companions")
    doc = md.load(r.doc.path)
    rows = companions(doc)
    hit = next((x for x in rows if x["name"].lower() == steed.lower()), None)
    if hit is None:
        raise AlliesError(f"{rname} has no companion {steed!r} (gm.py companion add {rname} {steed} srd:riding-horse)")
    hit["acts"] = "own init" if independent else "mount"
    _set_rows(doc, rows)
    doc.save()
    _edit(r, _MOUNTED, f"mounted on {hit['name']}")
    body = f"mount {rname} on {hit['name']}"
    journal.log_delta(body)
    return [f"[{body}]"]


def dismount(rider):
    state = campaign.load_state()
    r = mutations.creature(rider, state)
    rname = r.name.split()[0] if r.is_pc else r.name
    conds = _conds(r.combat_row.get("conditions")) if r.combat_row else [str(x) for x in (r.front.get("conditions") or [])]
    steed = next((_MOUNTED.match(x).group(1) for x in conds if _MOUNTED.match(x)), None)
    if steed is None:
        raise AlliesError(f"{rname} isn't mounted")
    _edit(r, _MOUNTED)
    try:
        m = mutations.creature(steed, campaign.load_state())
        if m.combat_index >= 0:
            _edit(m, _RIDDEN)
    except mutations.MutationError:
        pass
    if r.combat_index < 0 and r.doc is not None:
        doc = md.load(r.doc.path)
        rows = companions(doc)
        hit = next((x for x in rows if x["name"].lower() == steed.lower()), None)
        if hit is not None and hit.get("acts") == "mount":
            hit["acts"] = "with me"
            _set_rows(doc, rows)
            doc.save()
    body = f"dismount {rname} from {steed}"
    journal.log_delta(body)
    return [f"[{body}]"]


# ---------- hirelings ----------

def hire(name, wage, by="party", loyalty=10, statblock=None):
    if inventory_cost(wage) is None:
        raise AlliesError(f"--wage wants e.g. \"2 gp/day\", got {wage!r}")
    if not 0 <= loyalty <= 20:
        raise AlliesError("--loyalty: 0–20")
    who = "party"
    if by and by.lower() != "party":
        c = mutations.creature(by)
        if not c.is_pc:
            raise AlliesError(f"--by: {c.name} is not a PC")
        who = c.name.split()[0]
    slug = campaign.slugify(name)
    p = campaign.path("npcs", slug)
    made = False
    if not p.exists():
        import stub
        stub.stub("npc", name, note="hireling")
        made = True
    doc = md.load(p)
    doc.set_front("hired-by", who)
    doc.set_front("wage", wage if "/" in wage else f"{wage}/day")
    doc.set_front("loyalty", loyalty)
    doc.set_front("attitude-to-party", doc.front.get("attitude-to-party") or "friendly")
    if statblock:
        doc.set_front("statblock", statblock)
    doc.save()
    body = f"hire {doc.front.get('name')} · {doc.front['wage']} · by {who} · loyalty {loyalty}"
    journal.log_delta(body)
    up = str(campaign.settings().get("upkeep", "off")).lower() == "on"
    return [f"[{body}" + ("" if up else " · wages not charged (upkeep: off)") + "]"]


def hireling_morale(table, fired):
    """combat.morale_check: a hireling below half HP, or half the party side down, checks
    once per trigger: WIS save DC 20 − loyalty. Adds its tags to `fired`. -> lines."""
    side_n = side_down = 0
    hires = []
    for r in table.rows:
        if r.get("side", "").strip().lower() != "party":
            continue
        cell = parse_hp_cell(r.get("hp", ""))
        words = [c.split()[0].lower() for c in _conds(r.get("conditions"))]
        down = (cell is not None and cell[0] == 0) or any(w in words for w in ("fled", "surrendered", "dead"))
        side_n += 1
        side_down += 1 if down else 0
        ref = r.get("ref", "").strip()
        if ref.startswith("npcs/") and not down:
            p = campaign.root() / (ref if ref.endswith(".md") else ref + ".md")
            front = md.load(p).front if p.exists() else {}
            if front.get("hired-by"):
                hires.append((norm_name(r["name"]), cell, front))
    out = []
    for name, cell, front in hires:
        why = []
        if cell is not None and 0 < cell[0] < cell[1] / 2:
            why.append("half HP")
        if side_n and side_down * 2 >= side_n:
            why.append("half the side down")
        try:
            loyalty = max(0, min(20, int(front.get("loyalty", 10))))
        except (TypeError, ValueError):
            loyalty = 10
        for w in why:
            tag = f"{name.lower()} ({w})"
            if tag in fired:
                continue
            fired.add(tag)
            dc = 20 - loyalty
            journal.log_delta(f"morale {tag}: WIS save DC {dc} (loyalty {loyalty})", gm=True)
            out.append(f"[Morale ({w}): {name} (hireling, loyalty {loyalty}) — WIS save DC {dc} "
                       f"(gm.py save {name} wis {dc}); fail → flees or refuses (gm.py cond {name} +fled)]")
    return out


def inventory_cost(text):
    import inventory
    return inventory.parse_cost(text)


def wage_lines(old, new):
    """Clock (`upkeep: on`): each dawn crossed, every hireling's daily wage."""
    if str(campaign.settings().get("upkeep", "off")).lower() != "on":
        return []
    dawn = gametime.NAMED["dawn"]
    days = sum(1 for d in range(old[0], new[0] + 1)
               if gametime.diff(old, (d, dawn)) > 0 and gametime.diff((d, dawn), new) >= 0)
    if not days:
        return []
    import inventory
    out = []
    for d in campaign.npcs():
        by = str(d.front.get("hired-by") or "").strip()
        if not by or str(d.front.get("status") or "").lower() == "dead":
            continue
        cp = inventory.parse_cost(d.front.get("wage"))
        if not cp:
            continue
        total = cp * days
        name = str(d.front.get("name"))
        if by.lower() == "party":
            out.append(f"  Wages: {name} {inventory.fmt_cost(total)} due ({days} day{'s' if days != 1 else ''}; "
                       f"party hire — gm.py coin <PC> -…)")
            continue
        try:
            paid = inventory.pay(by, total)
            out.append(f"  Wages: {name} {inventory.fmt_cost(total)} paid by {by} "
                       + " ".join(x.strip("[]") for x in paid))
        except (inventory.InventoryError, ToolError) as e:
            out.append(f"  Wages: {name} {inventory.fmt_cost(total)} unpaid — {e} (loyalty suffers)")
    return out


# ---------- CLI ----------

def _out(ctx, lines):
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def cmd_companion(ctx):
    a = ctx.args
    if a.action == "list":
        return _out(ctx, companion_list())
    if a.action == "add":
        if len(a.rest) != 3:
            raise AlliesError("companion add <PC> <name> <srd:creature | npcs/slug>")
        return _out(ctx, companion_add(a.rest[0], a.rest[1], a.rest[2], a.acts, a.hp, a.note or ""))
    if len(a.rest) != 2:
        raise AlliesError("companion drop <PC> <name>")
    _out(ctx, companion_drop(a.rest[0], a.rest[1]))


def cmd_hire(ctx):
    a = ctx.args
    _out(ctx, hire(a.name, a.wage, a.by, a.loyalty, a.statblock))


def cmd_mount(ctx):
    _out(ctx, mount(ctx.args.rider, ctx.args.steed, ctx.args.independent))


def cmd_dismount(ctx):
    _out(ctx, dismount(ctx.args.rider))


def register(sub, g):
    p = sub.add_parser("companion", parents=[g], help="companion add PC NAME REF --acts own|with | drop | list")
    p.add_argument("action", choices=["add", "drop", "list"])
    p.add_argument("rest", nargs="*")
    p.add_argument("--acts", default="own", help="own (its own initiative) | with (right after its owner) | mount")
    p.add_argument("--hp", help="cur/max (default: the SRD creature's)")
    p.add_argument("--note")
    p.set_defaults(func=cmd_companion)

    p = sub.add_parser("hire", parents=[g], help='hire "Bren" --wage "2 gp/day" [--by PC] [--loyalty N]')
    p.add_argument("name")
    p.add_argument("--wage", required=True)
    p.add_argument("--by", default="party")
    p.add_argument("--loyalty", type=int, default=10)
    p.add_argument("--statblock", help="an SRD monster for the hireling's numbers (e.g. guard)")
    p.set_defaults(func=cmd_hire)

    p = sub.add_parser("mount", parents=[g], help="mount RIDER MOUNT [--independent]")
    p.add_argument("rider"); p.add_argument("steed")
    p.add_argument("--independent", action="store_true", help="the mount acts on its own initiative")
    p.set_defaults(func=cmd_mount)

    p = sub.add_parser("dismount", parents=[g], help="dismount RIDER")
    p.add_argument("rider")
    p.set_defaults(func=cmd_dismount)
