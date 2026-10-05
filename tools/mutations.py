"""State mutations: `hp dmg cond move-npc move-party time undo` (planning/06 →
mutations table L137-151, group rows L153-154, turn blocks L156-168, undo L219-222;
planning/04 → PC file L352-424, NPC file L312-350, state current.md + Stage + Combat
block L459-538; plan.md Phase 2 item 5). Inventory-side mutations (`item coin res
attitude`) live in inventory.py.

Python API for later phases (combat, rest, pc):
    hp(name, op, n), dmg(name, amount, dtype=None, log=True), cond(name, change,
    duration=None), move_npc(name, where), move_party(where), advance_time(spec),
    validate_location(where)
Each returns `(line, data)`: the bracket line and a dict for `--json`. Each writes
through lib/md.py (atomic, journaled) and logs its delta via `journal.log_delta`
(`(GM)` for off-screen NPC moves). HP arithmetic lives in lib/resolve.py.

Where HP/conditions live: the Combatants row when the creature has one (matched by
name or by `ref` to its file, lib/creatures.py), else the PC/NPC frontmatter
(`hp: {current, max, temp}`, `conditions: [...]`). A group row (`Thugs ×3`,
`7/11 ea`) is split before it is hurt: one member gets its own row (`Thug 1`), as
06 L153-154 / 02 → Groups say; the group row stays first, members follow in order.
"""
import re
from pathlib import Path

from lib import campaign, creatures, gametime, journal, md, resolve
from lib.creatures import GROUP, fmt_hp_cell, norm_name, parse_hp_cell
from lib.errors import ToolError


class MutationError(ToolError):
    pass


def creature(name, state=None):
    """Resolve a creature for a mutation (NotFound → MutationError)."""
    try:
        return creatures.get(name, state)
    except campaign.NotFound as e:
        raise MutationError(str(e)) from None


def allow_negative(p):
    """Let a subparser take `-6`, `-1d4`, `-5m` as positionals (argparse would read
    them as options)."""
    p._negative_number_matcher = re.compile(r"^-(\d|d\d)")
    return p


# ---------- hit points ----------

def _split_group(table, i):
    """Split one member off group row i; the group row stays first and members
    follow it in number order. Returns (member index, 'Thugs ×3')."""
    row = dict(table.rows[i])
    base, count = GROUP.match(norm_name(row["name"])).groups()
    count = int(count)
    singular = base[:-1] if base.endswith("s") and not base.endswith("ss") else base
    pat = re.compile(rf"^{re.escape(singular)} (\d+)$", re.I)
    used = [int(m.group(1)) for r in table.rows for m in [pat.match(norm_name(r.get("name")))] if m]
    n = max(used, default=0) + 1
    cur, mx, temp, _ = parse_hp_cell(row.get("hp", ""))
    # A group's size cell is its footprint (`group r5`), not a member's size. Members are
    # one creature each; Medium until Phase 4 can read the size from the stat block.
    size = row.get("size", "")
    one = "M" if size.lower().startswith("group") else size
    member = dict(row, name=f"{singular} {n}", hp=fmt_hp_cell(cur, mx, temp), size=one)
    if count - 1 >= 2:
        table.set(i, "name", f"{base} ×{count - 1}")
    else:
        table.set(i, "name", f"{singular} {n + 1}")
        table.set(i, "hp", fmt_hp_cell(cur, mx, temp))
        table.set(i, "size", one)
    at = i + 1
    while at < len(table.rows) and pat.match(norm_name(table.rows[at].get("name"))):
        at += 1
    table.insert(at, member)
    return at, f"{base} ×{count}"


def _apply_hp(name, op, n, *, verb="hp", dtype=None, rules=None, log=True):
    """Shared by hp/dmg/atk. Returns (line, data); data["tail"] is the `Kael 9→2/11`
    part atk appends to its own line."""
    if n < 0:
        raise MutationError(f"{verb}: amounts are never negative (got {n})")
    state = campaign.load_state()
    c = creature(name, state)
    if n == 0 and op in ("-", "+", "temp"):
        line = f"[{verb} {c.name} no change]"
        return line, {"name": c.name, "noop": True, "tail": f"{c.name} no change"}
    rules = resolve.active_keys() if rules is None else rules
    split_note = ""
    table, i = (c.combat_table(), c.combat_index)
    if i >= 0:
        cell = parse_hp_cell(table.rows[i].get("hp", ""))
        if cell is None:
            raise MutationError(f"{c.name}: can't read HP {table.rows[i].get('hp')!r}")
        if cell[3] and GROUP.match(norm_name(table.rows[i]["name"])) and op != "temp":
            i, group = _split_group(table, i)
            split_note = f"split from {group}"
            cell = parse_hp_cell(table.rows[i]["hp"])
        cur, mx, temp, each = cell
        who = norm_name(table.rows[i]["name"])
    else:
        doc = c.doc
        if doc is None or not isinstance(doc.front.get("hp"), dict):
            if doc is not None and not c.is_pc and c.monster is not None:
                # an SRD-statted NPC starts at the stat block's average; written on save
                doc.front["hp"] = {"current": c.monster.hp, "max": c.monster.hp}
            else:
                raise MutationError(f"{c.name}: no hp in frontmatter or Combatants row")
        h = doc.front["hp"]
        cur, mx, temp, each = int(h.get("current") or 0), int(h.get("max") or 0), int(h.get("temp") or 0), False
        who = c.name
    note_dmg = ""
    n_applied = n
    if op == "-" and dtype:
        resist, immune, vuln = c.damage_traits()
        n_applied, note_dmg = resolve.adjust_damage(n, dtype, resist=resist, immune=immune, vuln=vuln)
    try:
        new, new_temp, note = resolve.apply_hp(cur, mx, temp, op, n_applied, is_pc=c.is_pc, rules=rules)
    except resolve.ResolveError as e:
        raise MutationError(str(e)) from None
    if i >= 0:
        table.set(i, "hp", fmt_hp_cell(new, mx, new_temp, each))
        state.save()
    else:
        h = dict(doc.front["hp"])
        h["current"] = new
        if new_temp:
            h["temp"] = new_temp
        else:
            h.pop("temp", None)
        doc.set_front("hp", h)
        doc.save()
    tail = f"{who} {cur}→{new}/{mx}"
    if temp != new_temp:
        tail += f" · temp {temp}→{new_temp}"
    notes = " · ".join(x for x in (note, split_note) if x)
    if notes:
        tail += f" ({notes})"
    if verb == "dmg":
        head = f"dmg {who} {n}" + (f" {dtype}" if dtype else "")
        if note_dmg:
            head += f" → {n_applied} ({note_dmg})"
        body = f"{head} · {tail}"
    else:
        body = f"hp {tail}"
    if log:
        journal.log_delta(body)
    data = {"name": who, "hp": new, "max": mx, "temp": new_temp, "was": cur,
            "applied": n_applied, "note": notes, "resist_note": note_dmg, "tail": tail}
    return f"[{body}]", data


def hp(name, op, n, rules=None):
    """op: '-' | '+' | '=' | 'temp'."""
    return _apply_hp(name, op, n, rules=rules)


def dmg(name, amount, dtype=None, rules=None, log=True):
    """`log=False` lets atk fold the HP change into its own delta line."""
    return _apply_hp(name, "-", amount, verb="dmg", dtype=dtype or "", rules=rules, log=log)


def parse_hp_args(tokens):
    """['-6'] | ['+4'] | ['=11'] | ['+temp', '5'] | ['+temp5'] -> (op, n)."""
    text = " ".join(tokens).strip().lower()
    m = re.fullmatch(r"\+?\s*temp\s*\+?(\d+)", text)
    if m:
        return "temp", int(m.group(1))
    m = re.fullmatch(r"([+\-=])\s*(\d+)", text)
    if not m:
        raise MutationError(f"hp: want -N, +N, =N or +temp N, got {text!r}")
    return m.group(1), int(m.group(2))


# ---------- conditions ----------

_DUR = re.compile(r"^\d+[rm]$", re.I)


def _conds_from_cell(cell):
    cell = (cell or "").strip()
    if cell in ("", "—", "-"):
        return []
    return [c.strip() for c in cell.split(",") if c.strip()]


def cond(name, change, duration=None):
    """change '+prone' / '-prone'; duration '3r' (rounds) or '10m' (minutes)."""
    m = re.fullmatch(r"([+-])\s*([A-Za-z][\w-]*)", change.strip())
    if not m:
        raise MutationError(f"cond: want +name or -name, got {change!r}")
    sign, cname = m.group(1), m.group(2).lower()
    if duration and not _DUR.match(duration):
        raise MutationError(f"cond: duration is Nr (rounds) or Nm (minutes), got {duration!r}")
    if duration and sign == "-":
        raise MutationError("cond: a duration only goes with +condition")
    state = campaign.load_state()
    c = creature(name, state)
    table, i = c.combat_table(), c.combat_index
    if i >= 0:
        conds = _conds_from_cell(table.rows[i].get("conditions"))
    else:
        if c.doc is None:
            raise MutationError(f"{c.name}: no Combatants row or file for conditions")
        conds = [str(x) for x in (c.doc.front.get("conditions") or [])]
    before = list(conds)
    rest = [x for x in conds if x.split()[0].lower() != cname]
    if sign == "+":
        rest.append(cname + (f" {duration.lower()}" if duration else ""))
    elif len(rest) == len(conds):
        raise MutationError(f"{c.name} is not {cname}")
    if i >= 0:
        table.set(i, "conditions", ", ".join(rest) if rest else "—")
        state.save()
    else:
        c.doc.set_front("conditions", rest)
        c.doc.save()
    shown = ", ".join(rest) if rest else "none"
    body = f"cond {c.name} {sign}{cname}" + (f" {duration.lower()}" if duration else "") + f" · now {shown}"
    journal.log_delta(body)
    return f"[{body}]", {"name": c.name, "before": before, "conditions": rest}


# ---------- places ----------

_SLUG = re.compile(r"^[a-z0-9-]+(/[a-z0-9-]+)?$")


def _areas(doc):
    span = doc.section("Areas")
    if span is None:
        return []
    out = []
    for line in doc.body[span[0] + 1:span[1]]:
        m = re.match(r"^\s*-\s+\*\*([^*]+)\*\*", line)
        if m:
            out.append(m.group(1).strip().lower())
    return out


def validate_location(where):
    """`site` or `site/area` (04 L289-293): slugs only; the first part must be a
    locations/ file whose `tier:` is set and is not `world`; an area must be listed in
    that file's ## Areas. Returns the normalized text."""
    where = where.strip().lower()
    if not _SLUG.match(where):
        raise MutationError(f"not a location: {where!r} (want site or site/area, slugs a-z 0-9 -)")
    site, _, area = where.partition("/")
    folder = campaign.root() / "locations"
    p = folder / f"{site}.md"
    if not p.exists():
        known = sorted(x.stem for x in folder.glob("*.md") if not x.name.startswith("_"))
        raise MutationError(f"no location {site!r} (known: {', '.join(known)})")
    doc = md.load(p)
    tier = str(doc.front.get("tier") or "").strip().lower()
    if not tier or tier == "world":
        raise MutationError(f"{site} is {'the world' if tier == 'world' else 'not a place'} "
                            "(tier: site or area wanted)")
    if area:
        areas = _areas(doc)
        if area not in areas:
            raise MutationError(f"{site} has no area {area!r} in ## Areas "
                                f"({', '.join(areas) or 'none listed'})")
    return where


def _at(loc, party):
    loc, party = (loc or "").lower(), (party or "").lower()
    return loc == party or ("/" not in party and loc.split("/")[0] == party)


def _same_file(a, b):
    return bool(a and b) and Path(a).resolve() == Path(b).resolve()


def _drop_from_stage(state, c):
    """Remove the NPC's On stage bullet, a stale `(Name is …)` note bullet about it,
    and its Stage row. True if anything went."""
    dropped = False
    first = c.name.split()[0].lower()
    span = state.section("On stage")
    if span is not None:
        bullets = {b.line for b in campaign.onstage(state)
                   if b.name.lower() == c.name.lower()
                   or _same_file(b.path, c.doc.path if c.doc else None)}
        for j in range(span[1] - 1, span[0], -1):
            stale = re.match(r"^\s*-\s+\(([^\s,)]+)", state.body[j])
            if j in bullets or (stale and stale.group(1).lower() == first):
                del state.body[j]
                dropped = True
    st = state.table("Stage")
    if st is not None and c.stage_index >= 0:
        st.remove(c.stage_index)
        dropped = True
    return dropped


def move_npc(name, where):
    target = validate_location(where)
    state = campaign.load_state()
    c = creature(name, state)
    if c.is_pc or c.doc is None:
        raise MutationError(f"move-npc: {c.name} is not an NPC with a file (use move-party for PCs)")
    if c.combat_index >= 0:
        raise MutationError(f"{c.name} is in combat — end combat or remove the row first")
    old = str(c.doc.front.get("location") or "")
    party = str(state.front.get("party-location") or "")
    on_stage = c.stage_row is not None or any(b.name.lower() == c.name.lower()
                                              for b in campaign.onstage(state))
    c.doc.set_front("location", target)
    c.doc.save()
    flag = ""
    if not _at(target, party):
        if _drop_from_stage(state, c):
            state.save()
        if on_stage:
            flag = " · left the scene"
    off_screen = not on_stage and not _at(target, party)
    body = f"move-npc {c.name} {old}→{target}{flag}"
    journal.log_delta(body, gm=off_screen)
    return f"[{body}]", {"name": c.name, "from": old, "to": target, "left": bool(flag),
                         "gm": off_screen}


def move_party(where):
    target = validate_location(where)
    state = campaign.load_state()
    old = str(state.front.get("party-location") or "")
    names = []
    for doc in campaign.pcs():
        doc.set_front("location", target)
        doc.save()
        names.append(str(doc.front.get("name") or ""))
    state.set_front("party-location", target)
    state.save()
    body = f"move-party {old}→{target} ({', '.join(names)})"
    journal.log_delta(body)
    return f"[{body}]", {"from": old, "to": target, "pcs": names}


# ---------- time ----------

def advance_time(spec):
    """`time +20m` / `time to dawn` / `time -5m` (a correction backwards): a simple
    frontmatter change until `clock` (Phase 7) exists; nothing crossed is reported
    (plan.md Phase 2 item 5)."""
    state = campaign.load_state()
    old = gametime.parse(state.front.get("in-game-datetime"))
    spec = spec.strip()
    if spec.startswith("-"):
        new = gametime.normalize(old[0], old[1] - gametime.parse_delta("+" + spec[1:]))
    else:
        new = gametime.add(old, spec)
    state.set_front("in-game-datetime", gametime.fmt(new))
    state.save()
    body = f"time {gametime.fmt(old)}→{gametime.fmt(new)}"
    journal.log_delta(body)
    return f"[{body}]", {"from": gametime.fmt(old), "to": gametime.fmt(new),
                         "minutes": gametime.diff(old, new)}


# ---------- CLI ----------

def emit(ctx, out):
    line, data = out
    ctx.emit(line)
    ctx.result = data


def cmd_hp(ctx):
    op, n = parse_hp_args(ctx.args.change)
    emit(ctx, hp(ctx.args.target, op, n))


def cmd_dmg(ctx):
    emit(ctx, dmg(ctx.args.target, ctx.args.amount, ctx.args.type))


def cmd_cond(ctx):
    toks = " ".join(ctx.args.change).split()
    if not toks:
        raise MutationError("cond: want +name [Nr|Nm] or -name")
    emit(ctx, cond(ctx.args.target, toks[0], toks[1] if len(toks) > 1 else None))


def cmd_move_npc(ctx):
    emit(ctx, move_npc(ctx.args.target, ctx.args.where))


def cmd_move_party(ctx):
    emit(ctx, move_party(ctx.args.where))


def cmd_time(ctx):
    """`time +20m` runs `clock advance` (Phase 7); `time -5m` stays a plain correction."""
    spec = " ".join(ctx.args.spec).strip()
    if spec.startswith("-"):
        emit(ctx, advance_time(spec))
        return
    import clock
    lines, data = clock.advance(spec)
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def cmd_undo(ctx):
    b = journal.current()
    if b is not None and b.dir is not None:
        raise MutationError("undo must be its own command, not a later step of a do batch")
    manifest = journal.undo()
    files = sorted(manifest.get("files", {}))
    line = (f"[undo turn {manifest.get('turn')} step {manifest.get('step')} · "
            f"{manifest.get('command line', '')} · restored {', '.join(files) or 'nothing'}]")
    ctx.emit(line)
    ctx.result = {"undone": manifest}


def register(sub, g):
    R = "..."  # noqa: N806  (argparse.REMAINDER: `-prone` must not parse as an option)
    p = allow_negative(sub.add_parser("hp", parents=[g], help="hp NAME -N | +N | =N | +temp N"))
    p.add_argument("target"); p.add_argument("change", nargs=R)
    p.set_defaults(func=cmd_hp)

    p = sub.add_parser("dmg", parents=[g], help="dmg NAME N [type]")
    p.add_argument("target"); p.add_argument("amount", type=int); p.add_argument("type", nargs="?")
    p.set_defaults(func=cmd_dmg)

    p = sub.add_parser("cond", parents=[g], help="cond NAME +cond [3r|10m] | -cond")
    p.add_argument("target"); p.add_argument("change", nargs=R)
    p.set_defaults(func=cmd_cond)

    p = sub.add_parser("move-npc", parents=[g], help="move-npc NAME site[/area]")
    p.add_argument("target"); p.add_argument("where")
    p.set_defaults(func=cmd_move_npc)

    p = sub.add_parser("move-party", parents=[g], help="move-party site[/area]")
    p.add_argument("where")
    p.set_defaults(func=cmd_move_party)

    p = allow_negative(sub.add_parser("time", parents=[g], help="time +20m | -5m | to dawn"))
    p.add_argument("spec", nargs="+")
    p.set_defaults(func=cmd_time)

    p = sub.add_parser("undo", parents=[g], help="roll back the last batch")
    p.set_defaults(func=cmd_undo)
