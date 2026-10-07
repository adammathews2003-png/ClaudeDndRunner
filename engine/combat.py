"""`combat start | next | end` (docs/design/06 → `gm.py combat`; 04 → Combat block; 02 →
Combat mode, Spatial model; rules/combat-basics.md; plan.md Phase 4 item 4).

`start [--init Kael=15 …] [--add "srd:thug x3 @25,15,0" …] [--surprised Tobin …]`
promotes the Stage table (or the On stage list + present PCs) to the `## Combat` block:
Map/Bounds and Terrain copied from the party sub-area's `## Layout`, initiative rolled
for NPCs (d20 + DEX; PCs report theirs with `--init`, or the tool rolls under
`dice-mode: gm-rolls-all`), HP/AC seeded from PC/NPC files or SRD stat blocks, ties →
PCs. `--add` places SRD monsters (`@x,y,z`, `@feature [N|S|E|W]`, `@near <creature>`);
`--surprised` adds `surprised 1r`; `--opener Kael` (house rule: Opening strike) adds
`struck-first 1r` to whoever already made the opening attack before initiative. When a
surprised or struck-first creature comes up, a note says what that turn allows. Prints
the order and the player-view map.

`next` advances `up:` (dead NPC rows, and anyone `fled` or `surrendered`, are skipped).
On wrap it starts the next round, moves the Moves log into the session log and ticks
`Nr` condition durations (expiry reported). Prints who's up, where, and who is within
their reach. Phase 14 (`morale: on`): the first time a foe unit (a group row and its
split members, or one creature) has a creature below half its HP, its side's `leader`
falls, or half the side is down, it prints `Morale (half HP): Thugs — WIS save DC 10 …`
once per unit and trigger (kept on the Combat block's `Morale:` line). Constructs,
oozes and undead (unless their notes say `morale`) and `morale: fearless` never check;
the party side never does.

`end [--count <name> …] [--count-fled]` writes HP / temp HP / conditions from the
Combatants rows back to PC/NPC frontmatter (round-based conditions end with the fight),
marks NPCs at 0 HP `status: dead`, restores `(not in combat)`, sets tempo calm, ends
`combat`-scoped table rules, and (unless `xp-tracking: off`) writes
`.gm/last-combat.json` and prints the un-applied `[XP available: …]` line: base XP of
foes at 0 HP or marked `fled` / `surrendered` (they count as defeated, Phase 14), plus
any named with `--count` (routed, captured, talked down) or all standing foes with
`--count-fled`. Surrendered foes join On stage as prisoners. `start` refuses while a
chase runs and prints the stored Stealth totals of hidden rows against the other side
(hiding.py). `--frame` / `reframe` are Phase 8.
"""
import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path

from lib import campaign, creatures, dice, geo, journal, resolve, srd, turnstate
from lib.creatures import GROUP, fmt_hp_cell, norm_name, parse_hp_cell
from lib.errors import ToolError
import conditions_ext
import rules
import space
import tempo

COLS = ["init", "name", "glyph", "side", "pos", "size", "ref", "HP", "AC", "conditions", "notes"]
_HEAD = re.compile(r"^Combat\s*[—-]\s*round\s*(\d+)\s*·\s*up:\s*(.+)$", re.I)
_DUR = re.compile(r"^(.+?)\s+(\d+)r$", re.I)   # `poisoned 3r`, `conc bless 8r`


class CombatError(ToolError):
    pass


# ---------- helpers ----------

def _table_lines(rows):
    return (["| " + " | ".join(COLS) + " |", "|" + "|".join("-" * (len(c) + 2) for c in COLS) + "|"]
            + ["| " + " | ".join(str(r.get(c.lower(), "")) for c in COLS) + " |" for r in rows])


def _heading_index(doc):
    for i, lvl, text in doc.headings():
        if lvl == 2 and text.lower().startswith("combat"):
            return i, text
    raise CombatError("current.md has no ## Combat section")


def _status(doc):
    i, text = _heading_index(doc)
    m = _HEAD.match(text)
    if not m:
        return None
    return int(m.group(1)), m.group(2).strip()


def _write_block(doc, round_no, up, block_lines):
    i, _ = _heading_index(doc)
    doc.body[i] = f"## Combat — round {round_no} · up: {up}"
    tempo.set_section(doc, doc.body[i][3:], block_lines)


def _parse_init(texts):
    out = {}
    for t in texts or []:
        name, sep, val = t.partition("=")
        if not sep or not re.fullmatch(r"-?\d+", val.strip()):
            raise CombatError(f"--init wants Name=N, got {t!r}")
        out[name.strip().lower()] = int(val)
    return out


def _lookup(table, name):
    key = name.lower()
    for k, v in table.items():
        if key == k or key.startswith(k) or k.startswith(key.split()[0]):
            return v
    return None


def _party_layout(state):
    loc = str(state.front.get("party-location") or "")
    site, _, area = loc.partition("/")
    if not site:
        return None, None, None
    try:
        frame = geo.load(site)
    except geo.GeoError:
        return site, area, None
    return site, area, frame.layouts.get(area) if area else None


def _add_specs(texts):
    """[(srd name, count, pos spec or None)] from `--add "srd:thug x3 @25,15,0"`."""
    out = []
    for t in texts or []:
        m = re.match(r"^\s*srd:\s*(.+?)(?:\s+[x×](\d+))?(?:\s+@(.+))?\s*$", t, re.I)
        if not m:
            raise CombatError(f"--add wants \"srd:<monster> [xN] [@where]\", got {t!r}")
        out.append((m.group(1).strip(), int(m.group(2) or 1), (m.group(3) or "").strip() or None))
    return out


def _conds(cell):
    cell = (cell or "").strip()
    return [] if cell in ("", "—", "-") else [c.strip() for c in cell.split(",") if c.strip()]


# ---------- start ----------

def start(inits=(), adds=(), surprised=(), frame=None, roller=None, openers=()):
    if frame:
        raise CombatError("combat start --frame: not built yet (Phase 8)")
    state = campaign.load_state()
    if tempo.in_combat(state):
        raise CombatError("combat is already running (combat next / combat end)")
    if state.section("Chase") is not None:
        raise CombatError("combat start: a chase is running (chase end first; a caught quarry is a fight)")
    roller = roller or dice.Roller()
    rules_ = resolve.active_keys()
    gm_rolls = resolve.dice_mode(state.front, rules_) == "gm-rolls-all"
    init_given = _parse_init(inits)
    stage = state.table("Stage")
    rows, entries, used, missing = [], [], set(), []
    if stage is not None:
        source = [dict(r) for r in stage.rows]
    else:
        source = []
        for a in tempo.actors(state):
            source.append({"name": a.name, "ref": a.ref, "pos": "?", "size": a.size(),
                           "side": a.side(), "glyph": ""})
    for r in source:
        name = norm_name(r.get("name"))
        is_pc = "(pc)" in r.get("name", "").lower() or r.get("ref", "").startswith("pcs/")
        ref = r.get("ref", "")
        c = None
        try:
            c = creatures.get(name, state) if not ref.startswith("srd:") else None
        except campaign.CampaignError:
            c = None
        mon = None
        if ref.startswith("srd:"):
            mon = srd.monster(ref[4:])
        elif c is not None:
            mon = c.monster
        dex = c.mod("dex") if c is not None else (mon.mod("dex") if mon else 0)
        if is_pc:
            given = _lookup(init_given, name)
            if given is None:
                if gm_rolls:
                    given = roller.d20(dex).total
                else:
                    missing.append(name)
                    continue
            init = given
        else:
            given = _lookup(init_given, name)
            init = given if given is not None else roller.d20(dex).total
        hp, ac, conds, notes = _numbers(c, mon, name)
        if any(name.lower().startswith(s.lower()) for s in surprised):
            conds = conds + ["surprised 1r"]
        if any(name.lower().startswith(o.lower()) for o in openers):
            conds = conds + ["struck-first 1r"]
        glyph = (r.get("glyph") or "").strip() or tempo.unique_glyph(name, used)
        used.add(glyph)
        rows.append({"init": init, "name": f"{name} (PC)" if is_pc else name, "glyph": glyph,
                     "side": r.get("side") or ("party" if is_pc else "neutral"), "pos": r.get("pos") or "?",
                     "size": r.get("size") or "M", "ref": ref, "hp": hp, "ac": ac,
                     "conditions": ", ".join(conds) or "—", "notes": notes})
        entries.append((name, init, is_pc))
    if missing:
        raise CombatError("players roll initiative: pass --init " + " ".join(f"{n}=N" for n in missing)
                          + " (or set dice-mode: gm-rolls-all)")
    import allies   # Phase 15: the PCs' companions join on the party's side (`ctrl <PC>`)
    comp_rows, comp_entries, follow = allies.combat_rows(rows, roller, init_given, used)
    rows += comp_rows
    entries += comp_entries
    pending_pos = []
    for name, n, where in _add_specs(adds):
        mon = srd.monster(name)
        disp = mon.name if n == 1 else f"{mon.name}s ×{n}"
        init = roller.d20(mon.mod("dex")).total
        glyph = tempo.unique_glyph(mon.name, used)
        used.add(glyph)
        rows.append({"init": init, "name": disp, "glyph": glyph, "side": "foe", "pos": "?",
                     "size": "group r5" if n > 1 else mon.size, "ref": f"srd:{mon.index}",
                     "hp": fmt_hp_cell(mon.hp, mon.hp, each=n > 1), "ac": mon.ac,
                     "conditions": "surprised 1r" if any(disp.lower().startswith(s.lower()) for s in surprised) else "—",
                     "notes": f"reach {mon.reach()}" if mon.reach() > 5 else ""})
        entries.append((disp, init, False))
        if where:
            pending_pos.append((disp, where))
    if not rows:
        raise CombatError("combat start: nobody on stage")
    by_name = {norm_name(r["name"]): r for r in rows}
    ordered = [by_name[n] for n, _, _ in resolve.initiative_order(entries, rules_)]
    ordered = allies.order(ordered, follow)
    site, area, lay = _party_layout(state)
    block = []
    if lay is not None:
        block.append(f"Map: {site} / {area} (frame: site {site}; layout: locations/{site}.md)")
        block.append(lay.bounds_line)
        block += ["", "### Terrain", "| id | glyph | feature | from | to | effect |",
                  "|----|-------|---------|------|----|--------|"]
        for t in lay.rows:
            block.append("| " + " | ".join(t.get(k, "") for k in ("id", "glyph", "feature", "from", "to", "effect")) + " |")
    else:
        block.append(f"Map: {site or '?'} / {area or '?'} (no Layout yet: positions are unbounded)")
    block += ["", "### Combatants"] + _table_lines(ordered)
    block += ["", "### Moves log (this round; cleared at round end, summarized into the session log)"]
    first = norm_name(ordered[0]["name"])
    _write_block(state, 1, first, block)
    tempo.set_tempo(state, "combat", [])
    budget = turnstate.reset(state, first)
    state.save()
    order = " · ".join(f"{norm_name(r['name'])} {r['init']}" for r in ordered)
    journal.log_delta(f"combat start · {order}")
    lines = [f"[combat start · round 1 · order: {order}]"]
    note = _turn_note(ordered[0])
    lines.append(note or turnstate.turn_start_line(budget))
    for disp, where in pending_pos:
        spec = where if re.match(r"^(near\s|\(?\s*-?\d)", where, re.I) else "@" + where
        try:
            lines.append(tempo.place(disp, spec)[0])
        except tempo.TempoError as e:
            lines.append(f"[{e}]")
    st = space.State(str(campaign.state_path()))
    if st.unplaced:
        lines.append("[unplaced: " + ", ".join(st.unplaced) + " — gm.py pos <name> @<feature>]")
    if lay is None:
        lines.append(f"[no Layout for {site}/{area}: write one (02 → first fight writes the Layout)]")
    import hiding
    lines += hiding.combat_lines(ordered)   # stored Stealth totals vs the other side (Phase 14)
    lines += map_lines(player_view=True)
    return lines, {"order": [(norm_name(r["name"]), r["init"]) for r in ordered]}


def _numbers(c, mon, name):
    """(HP cell, AC, conditions, notes) for a PC/NPC/SRD creature."""
    notes = ""
    if c is not None and c.doc is not None and isinstance(c.front.get("hp"), dict):
        h = c.front["hp"]
        hp = fmt_hp_cell(int(h.get("current") or 0), int(h.get("max") or 0), int(h.get("temp") or 0))
    elif mon is not None:
        hp = fmt_hp_cell(mon.hp, mon.hp)
    else:
        raise CombatError(f"{name}: no hp in the file and no SRD stat block")
    try:
        ac = c.ac() if c is not None else mon.ac
    except creatures.CreatureError:
        ac = mon.ac if mon else "?"
    conds = [str(x) for x in (c.front.get("conditions") or [])] if c is not None and c.doc is not None else []
    if c is not None and c.doc is not None:   # Phase 13 mirrors: conc, dying, exh
        conds = conditions_ext.strip_mirrors(conds) + conditions_ext.mirrors(c.front)
    if mon is not None and mon.reach() > 5:
        notes = f"reach {mon.reach()}"
    return hp, ac, conds, notes


def map_lines(player_view=False, origin=None):
    st = space.State(str(campaign.state_path()))
    if not st.combatants and not st.terrain:
        return []
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            space.render(st, origin, player_view=player_view)
    except SystemExit:
        return []
    return out.getvalue().splitlines()


# ---------- next ----------

def _alive(row):
    """Still takes turns: not dead (a PC), not at 0 HP (an NPC), not fled or surrendered."""
    words = [c.split()[0].lower() for c in _conds(row.get("conditions"))]
    if "fled" in words or "surrendered" in words:
        return False
    is_pc = "(pc)" in row.get("name", "").lower() or row.get("ref", "").startswith("pcs/")
    if is_pc:
        return "dead" not in words
    return not row.get("hp", "").startswith("0/")


# ---------- morale (Phase 14; 02 → Table mechanics → Morale) ----------

MORALE_EXEMPT = ("construct", "ooze", "undead")
_MORALE = "Morale:"


def _unit_of(name):
    """(key, save name) of a foe row: `Thugs ×3` and its split members `Thug 1` are one
    unit, saved as `Thugs` while the group row stands."""
    g = GROUP.match(name)
    base = g.group(1) if g else re.sub(r"\s+\d+$", "", name)
    key = base.lower()
    key = key[:-1] if key.endswith("s") and not key.endswith("ss") else key
    return key, base


def _morale_exempt(row):
    notes = (row.get("notes") or "").lower()
    if re.search(r"morale:\s*fearless", notes):
        return True
    ref = (row.get("ref") or "").strip()
    try:
        c = creatures.get(norm_name(row.get("name")))
        if str(c.front.get("morale") or "").strip().lower() == "fearless":
            return True
        mon = srd.monster(ref[4:]) if ref.startswith("srd:") else c.monster
    except (ToolError, campaign.CampaignError):
        mon = None
    kind = str((mon.rec.get("type") if mon is not None else "") or "").lower()
    return kind in MORALE_EXEMPT and "morale" not in notes


def _morale_line(state):
    """(index, {"unit (trigger)"}) of the Combat block's `Morale:` line."""
    span = state.section("Combat")
    if span is None:
        return None, set()
    for j in range(span[0] + 1, span[1]):
        if state.body[j].startswith(_MORALE):
            return j, {x.strip() for x in state.body[j][len(_MORALE):].split("·") if x.strip()}
    return None, set()


def morale_check(state=None):
    """combat next: a morale check for each foe unit the first time a trigger happens
    (a creature below half its HP, its leader down, half the side down). -> lines."""
    if str(campaign.settings().get("morale", "on")).strip().lower() == "off":
        return []
    state = state or campaign.load_state()
    table = state.table("Combatants")
    if table is None:
        return []
    units, order = {}, []
    side_n = side_down = 0
    leader_down = False
    for r in table.rows:
        if r.get("side", "").strip().lower() != "foe":
            continue
        name = norm_name(r.get("name"))
        g = GROUP.match(name)
        n = int(g.group(2)) if g else 1
        cell = parse_hp_cell(r.get("hp", ""))
        words = [c.split()[0].lower() for c in _conds(r.get("conditions"))]
        down = (cell is not None and cell[0] == 0) or any(w in words for w in ("fled", "surrendered", "dead"))
        below = cell is not None and 0 < cell[0] < cell[1] / 2
        side_n += n
        side_down += n if down else 0
        if down and "leader" in (r.get("notes") or "").lower():
            leader_down = True
        key, base = _unit_of(name)
        u = units.get(key)
        if u is None:
            u = units[key] = {"name": base, "save": None, "group": False, "standing": 0, "below": False,
                              "exempt": True}
            order.append(key)
        if g and not down:          # a standing group row saves for the unit
            u["save"], u["group"] = base, True
        elif not down and u["save"] is None:
            u["save"] = name        # else the first standing member
        if not down:
            u["standing"] += n
            u["below"] = u["below"] or below
            u["exempt"] = u["exempt"] and _morale_exempt(r)
    j, fired = _morale_line(state)
    new = []
    for key in order:
        u = units[key]
        if not u["standing"] or u["exempt"]:
            continue
        why = []
        if u["below"]:
            why.append("half HP")
        if leader_down:
            why.append("leader down")
        if side_n and side_down * 2 >= side_n:
            why.append("half the side down")
        for w in why:
            tag = f"{key} ({w})"   # keyed by the unit, so a group splitting up doesn't re-fire
            if tag in fired:
                continue
            fired.add(tag)
            new.append((u, w, tag))
    import allies   # Phase 15: hirelings check too, against DC 20 − loyalty
    hired = allies.hireling_morale(table, fired)
    if not new and not hired:
        return []
    line = _MORALE + " " + " · ".join(sorted(fired))
    if j is None:
        span = state.section("Combat")
        j = span[0] + 1
        while j < len(state.body) and state.body[j].startswith(("Turn:", "Ammo spent:")):
            j += 1
        state.body.insert(j, line)
    else:
        state.body[j] = line
    state.save()
    out = []
    for u, w, tag in new:
        journal.log_delta(f"morale {tag}: WIS save DC 10", gm=True)
        out.append(f"[Morale ({w}): {u['name']} — WIS save DC 10 (gm.py save {u['save']} wis 10); "
                   f"fail → flee or surrender (gm.py cond {u['save']} +fled | +surrendered)]")
    return out + hired


def next_turn(roller=None):
    state = campaign.load_state()
    table = state.table("Combatants")
    if table is None:
        raise CombatError("combat next: not in combat")
    status = _status(state)
    if status is None:
        raise CombatError("combat next: can't read the ## Combat heading")
    round_no, up = status
    names = [norm_name(r["name"]) for r in table.rows]
    idx = next((i for i, n in enumerate(names) if n.lower() == up.lower()), None)
    if idx is None:
        idx = next((i for i, n in enumerate(names) if n.lower().startswith(up.lower())), -1)
    lines, wrapped = [], False
    n = len(table.rows)
    j = idx
    for _ in range(n):
        j += 1
        if j >= n:
            j, wrapped = 0, True
        if _alive(table.rows[j]):
            break
    else:
        raise CombatError("combat next: nobody left standing")
    ended_conc, ended_other = [], []
    if wrapped:
        round_no += 1
        lines += _end_of_round(state, round_no - 1, ended_conc, ended_other)
        table = state.table("Combatants")
    new_up = norm_name(table.rows[j]["name"])
    import allies
    import ready
    ctl = allies.controller(table.rows[j])
    reminders = ready.reminders(table, j)   # Phase 15: readied actions before every other turn
    i, _ = _heading_index(state)
    state.body[i] = f"## Combat — round {round_no} · up: {new_up}"
    budget = turnstate.reset(state, new_up)
    state.save()
    journal.log_delta(f"combat round {round_no} · up: {new_up}", gm=True)
    for caster in ended_conc:   # a round-based concentration ran out with its targets' effect
        try:
            lines += conditions_ext.end_conc(caster, "duration ended")
        except ToolError:
            pass
    import hazard   # held breath → choking → 0 HP (Phase 14)
    lines += hazard.expiry_lines(ended_other)
    lines.insert(0, f"[round {round_no} · up: {new_up}" + (f" ({ctl}'s)" if ctl else "") + "]")
    note = _turn_note(table.rows[j])
    lines.insert(1, note or turnstate.turn_start_line(budget))
    mount_note = allies.turn_note(table.rows[j])
    if mount_note:
        lines.insert(2, mount_note)
    lines += ready.lapse(new_up) + reminders
    import crit   # the crit die's bleed: 1d4 at the start of each of its turns (Phase 16)
    lines += crit.bleed_line(new_up, roller or dice.Roller())
    dying = conditions_ext.dying_prompt(new_up)
    if dying:
        lines.insert(2, dying)
    lines += morale_check()
    lines.append(_reach_line(new_up))
    return lines, {"round": round_no, "up": new_up}


def _end_of_round(state, finished, ended_conc=None, ended_other=None):
    """Move the Moves log into the session log and tick `Nr` durations. A `conc <spell>
    Nr` mirror that runs out puts its creature in `ended_conc` (next_turn ends the
    record after saving)."""
    out = []
    span = state.section("Moves log")
    if span is not None:
        moves = [state.body[k] for k in range(span[0] + 1, span[1]) if state.body[k].strip().startswith("-")]
        for mv in moves:
            journal.log_delta("move " + mv.strip()[1:].strip())
        tail = [""] if span[1] < len(state.body) else []
        state.body[span[0] + 1:span[1]] = tail
    table = state.table("Combatants")
    for i, r in enumerate(table.rows):
        conds, kept, ended = _conds(r.get("conditions")), [], []
        for cnd in conds:
            m = _DUR.match(cnd)
            if not m:
                kept.append(cnd)
                continue
            left = int(m.group(2)) - 1
            if left <= 0:
                ended.append(m.group(1))
            else:
                kept.append(f"{m.group(1)} {left}r")
        if conds != kept:
            table.set(i, "conditions", ", ".join(kept) or "—")
        for e in ended:
            out.append(f"[{norm_name(r['name'])}: {e} ended]")
            journal.log_delta(f"cond {norm_name(r['name'])} -{e} (expired)")
            if ended_other is not None:
                ended_other.append((norm_name(r["name"]), e.split()[0]))
            if e.lower().startswith("conc ") and ended_conc is not None:
                ended_conc.append(norm_name(r["name"]))
                notes = [b.strip() for b in (r.get("notes") or "").split(";")
                         if b.strip() and not b.strip().startswith("conc")]
                table.set(i, "notes", "; ".join(notes))   # a file-less caster's record
    return out


def _turn_note(row):
    """What a surprised / struck-first creature may do on this turn, or None."""
    conds = [c.split()[0].lower() for c in _conds(row.get("conditions"))]
    name = norm_name(row["name"])
    if "surprised" in conds:
        return f"[{name} is surprised: no move and no action this turn; no reactions until it ends]"
    if "struck-first" in conds:
        return f"[{name} struck first: their action is spent; move and bonus action as normal]"
    return None


def _reach_line(name):
    st = space.State(str(campaign.state_path()))
    me = next((c for c in st.combatants if c.name.lower() == name.lower()), None)
    if me is None:
        return f"[{name}: no position — gm.py pos {name} @…]"
    bits = []
    for c in st.combatants:
        if c is me:
            continue
        d = space.dist_between(me.cells(), c.cells())
        tag = " in reach" if d <= me.reach and c.side != me.side else ""
        bits.append((d, f"{c.name} {d:g} ft{tag}"))
    bits.sort()
    return f"[{me.name} at {space.fmt(me.pos)} · " + (" · ".join(b for _, b in bits) or "alone") + "]"


# ---------- end ----------

def end(count=(), count_fled=False):
    state = campaign.load_state()
    table = state.table("Combatants")
    if table is None:
        raise CombatError("combat end: not in combat")
    lines = []
    foes, prisoners = [], []
    import split
    sp = split.load()
    played = split.rounds_played(sp, state) if sp else 0
    for r in table.rows:
        name = norm_name(r["name"])
        ref = r.get("ref", "").strip()
        cell = parse_hp_cell(r.get("hp", ""))
        all_conds = _conds(r.get("conditions"))
        words = [c.split()[0].lower() for c in all_conds]
        gone = "surrendered" if "surrendered" in words else ("fled" if "fled" in words else None)
        conds = conditions_ext.strip_mirrors([c for c in all_conds if not _DUR.match(c)
                                              and c.split()[0].lower() not in ("fled", "surrendered")])
        if ref and not ref.startswith("srd:"):
            p = campaign.root() / (ref if ref.endswith(".md") else ref + ".md")
            if p.exists() and cell is not None:
                from lib import md
                doc = md.load(p)
                cur, mx, temp, _ = cell
                h = {"current": cur, "max": mx}
                if temp:
                    h["temp"] = temp
                doc.set_front("hp", h)
                doc.set_front("conditions", conds)
                is_pc = p.parent.name == "pcs"
                if not is_pc and cur == 0:
                    doc.set_front("status", "dead")
                    lines.append(f"[{name}: status dead]")
                doc.save()
        import allies
        allies.write_back(r)   # a companion's HP back to its owner's Companions row (Phase 15)
        if r.get("side", "").strip().lower() == "foe":
            foes.append((name, ref, cell, gone))
            if gone == "surrendered":
                prisoners.append((name, ref))
            elif gone == "fled" and ref and not ref.startswith("srd:"):
                lines.append(f"[{name} fled: gm.py move-npc {name.split()[0]} <where> when you know]")
    span = state.section("Moves log")   # the unfinished round's moves still reach the session log
    if span is not None:
        for k in range(span[0] + 1, span[1]):
            if state.body[k].strip().startswith("-"):
                journal.log_delta("move " + state.body[k].strip()[1:].strip())
    import supplies
    ammo = supplies.ammo_lines(state)
    i, _ = _heading_index(state)
    state.body[i] = "## Combat"
    tempo.set_section(state, "Combat", ["(not in combat)"])
    tempo.set_tempo(state, "calm", [])
    state.save()
    lines += rules.end_scope("combat")
    lines += conditions_ext.end_round_concs()
    lines += ammo
    lines += _prisoners(prisoners)
    journal.log_delta("combat end")
    if sp:
        lines += split.charge_combat(played)
        sp = split.load()
        sp["slice-round"] = 0
        split._save(sp)
    from lib import lint
    lines += lint.summary(lint.run())
    data = {}
    if str(campaign.settings(state).get("xp-tracking", "on")).lower() != "off":
        xp_line, data = _xp(foes, count, count_fled)
        lines.append(xp_line)
    lines.insert(0, "[combat end]")
    return lines, data


def _prisoners(prisoners):
    """Surrendered foes join On stage as prisoners (02 → Morale)."""
    if not prisoners:
        return []
    state = campaign.load_state()
    out = []
    for name, ref in prisoners:
        path = ""
        if ref and not ref.startswith("srd:"):
            rel = ref if ref.endswith(".md") else ref + ".md"
            if (campaign.root() / rel).exists():
                path = f" ({rel})"
        bullet = f"- **{name}**{path} — prisoner (surrendered)"
        span = state.section("On stage")
        if span is not None and any(state.body[k].strip() == "(nobody)" for k in range(span[0] + 1, span[1])):
            k = next(k for k in range(span[0] + 1, span[1]) if state.body[k].strip() == "(nobody)")
            state.body[k] = bullet
        else:
            state.append_line("On stage", bullet)
        journal.log_delta(f"onstage {name} (prisoner)")
        out.append(f"[{name} surrendered: on stage as a prisoner]")
    state.save()
    return out


def _xp_each(ref, name):
    try:
        if ref.startswith("srd:"):
            return srd.monster(ref[4:]).xp
        c = creatures.get(name)
        if isinstance(c.front.get("xp"), int):
            return c.front["xp"]
        return c.monster.xp if c.monster is not None else 0
    except (ToolError, campaign.CampaignError):
        return 0


def _xp(foes, count, count_fled):
    counted, parts, total = [], [], 0
    for name, ref, cell, gone in foes:
        g = GROUP.match(name)
        n = int(g.group(2)) if g else 1
        down = cell is not None and cell[0] == 0
        named = any(name.lower().startswith(c.lower()) for c in count)
        if down or gone or named or count_fled:   # fled / surrendered count as defeated (Phase 14)
            each = _xp_each(ref, name)
            total += each * n
            how = "defeated" if down else (gone or ("counted" if named else "fled"))
            parts.append(f"{name} {how}")
            counted.append({"name": name, "ref": ref, "n": n, "xp each": each, "outcome": how})
        else:
            parts.append(f"{name} standing")
    present = [d for d in campaign.pcs() if d.front.get("present") is not False]
    each = total // len(present) if present else 0
    data = {"foes": counted, "total": total, "present": [str(d.front.get("name")) for d in present],
            "each": each}
    p = campaign.root() / ".gm" / "last-combat.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    line = (f"[XP available: {total:,} ({', '.join(parts) or 'no foes'}) → {each:,} each for "
            f"{len(present)} present · award with: xp award from-combat]")
    return line, data


# ---------- commands ----------

def cmd_combat(ctx):
    a = ctx.args
    if a.action == "start":
        lines, data = start(a.init, a.add, a.surprised, a.frame, ctx.roller, a.opener)
    elif a.action == "next":
        lines, data = next_turn(ctx.roller)
    elif a.action == "end":
        lines, data = end(a.count, a.count_fled)
    else:
        raise CombatError("combat reframe: not built yet (Phase 8)")
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("combat", parents=[g], help="combat start | next | end")
    p.add_argument("action", choices=["start", "next", "end", "reframe"])
    p.add_argument("target", nargs="?", help="reframe target (Phase 8)")
    p.add_argument("--init", action="append", default=[], help="Kael=15 (players roll)")
    p.add_argument("--add", action="append", default=[], help='"srd:thug x3 @25,15,0"')
    p.add_argument("--surprised", action="append", default=[])
    p.add_argument("--opener", action="append", default=[],
                   help="who made the opening strike before initiative (house rule)")
    p.add_argument("--frame", help="Phase 8")
    p.add_argument("--count", action="append", default=[], help="end: count this foe's XP (routed, captured…)")
    p.add_argument("--count-fled", action="store_true", help="end: count every standing foe")
    p.set_defaults(func=cmd_combat)
