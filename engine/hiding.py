"""Hiding as a stored state (docs/design/02 → Table mechanics → Phase 14 → Hiding as a
state; 04 → Scene state added (`hidden 17`); 06 → Table mechanics → Phase 14; plan.md
Phase 14 item 7).

    hide Kira <total>                       Kira hides at that Stealth total
    hide Kael,Kira <t1>,<t2> --group        a group moving quietly: hidden if half succeed
    seek Veskar [<total>]                   an active Perception check against the hidden

A hidden creature carries `hidden <total>` in its conditions: on its Combatants row in a
fight, else in its file's frontmatter (a Stage row without a file can't hold it). It
stays hidden until it attacks (roll.attack gives the advantage and then drops it), is
found by `seek`, or the GM drops it (`cond Kira -hidden`). Everyone who looks later is
compared against the **stored** total with their passive Perception (at least the total
= spotted): `hide` itself, `scene enter` (who is here now) and `combat start` (the
fight's other side) print who spots whom, so stealth is never re-rolled. An NPC's total
is rolled by the tool when none is given; a player's is asked for. In bright light with
no cover or obscurement on the map near it, `hide` adds `Kira is in plain view?` (the GM
decides). A group succeeds when at least half beat the watchers' best passive.

Python API: `hidden_total(conds)`, `scene_lines(npc_docs, pc_docs)` (scene.py),
`combat_lines(rows)` (combat.py), `drop_hidden(name)` (roll.py).
"""
import re

from lib import campaign, creatures, dice, journal, md
from lib.errors import ToolError
import conditions_ext
import mutations

_HIDDEN = re.compile(r"^hidden\s+(\d+)$", re.I)


class HidingError(ToolError):
    pass


def hidden_total(conds):
    for c in conds or []:
        m = _HIDDEN.match(str(c).strip())
        if m:
            return int(m.group(1))
    return None


def _short(c):
    return c.name.split()[0] if c.is_pc or c.doc is not None else c.name


def _conds(c):
    return conditions_ext._conds(c)


def watchers(c, state=None):
    """The creatures who could see `c`: in a fight, the other side's standing rows; else
    the NPCs on stage for a PC, the scene's PCs for an NPC."""
    state = state or campaign.load_state()
    t = state.table("Combatants")
    out = []
    if t is not None and c.combat_index >= 0:
        me = (t.rows[c.combat_index].get("side") or "").strip().lower()
        for r in t.rows:
            if (r.get("side") or "").strip().lower() == me or r.get("hp", "").startswith("0/"):
                continue
            try:
                out.append(creatures.get(creatures.norm_name(r.get("name")), state))
            except (ToolError, campaign.CampaignError):
                continue
        return out
    if c.is_pc:
        for m in campaign.stage_matches(state):
            if m.is_pc:
                continue
            try:
                out.append(creatures.get(m.name, state))
            except (ToolError, campaign.CampaignError):
                continue
    else:
        for d in campaign.scene_pcs():
            out.append(creatures.get(str(d.front.get("name")), state))
    return out


def _passive(c):
    try:
        return c.passive("perception")
    except ToolError:
        return None


def _compare(total, seen_by):
    """(spotted bits, unseen bits) against the stored total."""
    spotted, unseen = [], []
    for w in seen_by:
        p = _passive(w)
        if p is None:
            continue
        (spotted if p >= total else unseen).append(f"{_short(w)} (passive {p})")
    return spotted, unseen


def _plain_view(c, state):
    if str(state.front.get("light") or "bright").lower() != "bright":
        return None
    pos = c.pos
    t = state.table("Terrain")
    if pos is not None and t is not None:
        for r in t.rows:
            if not re.search(r"cover|obscur", r.get("effect", ""), re.I):
                continue
            try:
                a, b = md.parse_point(r.get("from", "")), md.parse_point(r.get("to", "") or r.get("from", ""))
            except ValueError:
                continue
            lo = [min(p, q) - 5 for p, q in zip(a, b)]
            hi = [max(p, q) + 5 for p, q in zip(a, b)]
            if all(l <= v <= h for v, l, h in zip(pos, lo, hi)):
                return None
    return f"[{_short(c)} is in plain view? bright light, no cover or obscurement known — the GM decides]"


def _store(c, total):
    conditions_ext._edit_conds(c.name, drop=("hidden",), add=[f"hidden {total}"])


def _total_for(c, total, roller):
    if total is not None:
        return total, ""
    if c.is_pc:
        from lib import resolve
        if resolve.dice_mode(campaign.load_state().front) != "gm-rolls-all":
            raise HidingError(f"{_short(c)} rolls their own Stealth: hide {_short(c)} <total>")
    r = (roller or dice.Roller()).d20(c.skill_bonus("stealth"))
    return r.total, f" (Stealth {r.text})"


def hide(names, totals=(), group=False, roller=None):
    state = campaign.load_state()
    cs = [mutations.creature(n, state) for n in names]
    for c in cs:
        if c.combat_index < 0 and c.doc is None:
            raise HidingError(f"{c.name}: no Combatants row or file to hold `hidden`")
    totals = list(totals) + [None] * (len(cs) - len(totals))
    got = [_total_for(c, t, roller) for c, t in zip(cs, totals)]
    lines = []
    if group and len(cs) > 1:
        seen_by = watchers(cs[0], state)
        best = max((p for p in (_passive(w) for w in seen_by) if p is not None), default=None)
        ok = [t for t, _ in got if best is None or t > best]
        success = len(ok) * 2 >= len(cs)
        who = ", ".join(f"{_short(c)} {t}{r}" for c, (t, r) in zip(cs, got))
        verdict = "hidden" if success else "spotted"
        body = (f"hide group {who} · {len(ok)} of {len(cs)} beat the best passive "
                + (f"{best}" if best is not None else "(nobody watching)") + f" → {verdict}")
        if success:
            for c, (t, _) in zip(cs, got):
                _store(c, t)
        journal.log_delta(body)
        lines.append(f"[{body}]")
        for c in cs:
            pv = _plain_view(c, state)
            if pv and success:
                lines.append(pv)
        return lines
    for c, (t, r) in zip(cs, got):
        _store(c, t)
        spotted, unseen = _compare(t, watchers(c, campaign.load_state()))
        tail = (" · spotted by " + ", ".join(spotted)) if spotted else ""
        tail += (" · unseen by " + ", ".join(unseen)) if unseen else ""
        body = f"hide {_short(c)} {t}{r}{tail}"
        journal.log_delta(body)
        lines.append(f"[{body}]")
        pv = _plain_view(c, state)
        if pv:
            lines.append(pv)
    return lines


def seek(name, total=None, roller=None):
    state = campaign.load_state()
    c = mutations.creature(name, state)
    note = ""
    if total is None:
        if c.is_pc:
            from lib import resolve
            if resolve.dice_mode(state.front) != "gm-rolls-all":
                raise HidingError(f"{_short(c)} rolls their own Perception: seek {_short(c)} <total>")
        r = (roller or dice.Roller()).d20(c.skill_bonus("perception"))
        total, note = r.total, f" (Perception {r.text})"
    found, missed = [], []
    for h in _hidden_others(c, state):
        n = hidden_total(_conds(h))
        if total >= n:
            conditions_ext._edit_conds(h.name, drop=("hidden",))
            found.append(f"{_short(h)} (hidden {n})")
        else:
            missed.append(_short(h))
    body = f"seek {_short(c)} {total}{note}: " + (("spots " + ", ".join(found)) if found else "spots no one")
    journal.log_delta(body)
    if missed:   # who stays hidden is the GM's to know
        journal.log_delta(f"seek {_short(c)} {total}: still hidden {', '.join(missed)}", gm=True)
    return [f"[{body}]"] + ([f"(GM) still hidden: {', '.join(missed)}"] if missed else [])


def _hidden_others(c, state):
    out = []
    t = state.table("Combatants")
    if t is not None and c.combat_index >= 0:
        me = (t.rows[c.combat_index].get("side") or "").strip().lower()
        for r in t.rows:
            if (r.get("side") or "").strip().lower() == me:
                continue
            if hidden_total(mutations._conds_from_cell(r.get("conditions"))) is not None:
                out.append(creatures.get(creatures.norm_name(r.get("name")), state))
        return out
    pool = []
    if c.is_pc:
        pool = [creatures.get(m.name, state) for m in campaign.stage_matches(state) if not m.is_pc]
    else:
        pool = [creatures.get(str(d.front.get("name")), state) for d in campaign.scene_pcs()]
    return [h for h in pool if hidden_total(_conds(h)) is not None]


def drop_hidden(name):
    """roll.attack: an attack gives a hider away. -> line or None."""
    try:
        c = mutations.creature(name)
    except ToolError:
        return None
    n = hidden_total(_conds(c))
    if n is None:
        return None
    conditions_ext._edit_conds(c.name, drop=("hidden",))
    journal.log_delta(f"cond {_short(c)} -hidden (attacked)")
    return f"[{_short(c)} is no longer hidden (attacked)]"


# ---------- scene / combat compare ----------

def scene_lines(npc_docs, pc_docs):
    """scene enter: hidden PCs against the NPCs here, hidden NPCs against the PCs (the
    stored total vs each passive Perception)."""
    out = []
    pairs = [(d, npc_docs) for d in pc_docs] + [(d, pc_docs) for d in npc_docs]
    for d, others in pairs:
        n = hidden_total(d.front.get("conditions"))
        if n is None:
            continue
        seen_by = []
        for o in others:
            try:
                seen_by.append(creatures.get(str(o.front.get("name"))))
            except (ToolError, campaign.CampaignError):
                continue
        spotted, unseen = _compare(n, seen_by)
        name = str(d.front.get("name") or "?").split()[0]
        bits = []
        if spotted:
            bits.append("spotted by " + ", ".join(spotted))
        if unseen:
            bits.append("unseen by " + ", ".join(unseen))
        out.append(f"Hidden: {name} ({n}) — " + ("; ".join(bits) if bits else "nobody here to see"))
    return out


def combat_lines(rows):
    """combat start: each hidden row against the other side's passives."""
    out = []
    for r in rows:
        n = hidden_total(mutations._conds_from_cell(r.get("conditions")))
        if n is None:
            continue
        side = (r.get("side") or "").strip().lower()
        seen_by = []
        for o in rows:
            if (o.get("side") or "").strip().lower() == side:
                continue
            try:
                seen_by.append(creatures.get(creatures.norm_name(o.get("name"))))
            except (ToolError, campaign.CampaignError):
                continue
        spotted, unseen = _compare(n, seen_by)
        name = creatures.norm_name(r.get("name"))
        bits = (["spotted by " + ", ".join(spotted)] if spotted else []) + \
               (["unseen by " + ", ".join(unseen)] if unseen else [])
        out.append(f"[hidden: {name} ({n}) — " + ("; ".join(bits) if bits else "nobody on the other side") + "]")
    return out


# ---------- CLI ----------

def _ints(text, what):
    try:
        return [int(x) for x in text.split(",") if x.strip()]
    except ValueError:
        raise HidingError(f"{what}: totals are numbers (17 or 12,18)") from None


def cmd_hide(ctx):
    a = ctx.args
    names = [x.strip() for x in a.names.split(",") if x.strip()]
    totals = _ints(a.totals, "hide") if a.totals else []
    if len(totals) > len(names):
        raise HidingError("hide: more totals than names")
    lines = hide(names, totals, a.group, ctx.roller)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def cmd_seek(ctx):
    lines = seek(ctx.args.name, ctx.args.total, ctx.roller)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("hide", parents=[g], help="hide NAME[,NAME] [TOTAL[,TOTAL]] [--group]")
    p.add_argument("names"); p.add_argument("totals", nargs="?")
    p.add_argument("--group", action="store_true", help="a group check: hidden if half succeed")
    p.set_defaults(func=cmd_hide)

    p = sub.add_parser("seek", parents=[g], help="seek NAME [TOTAL]: active Perception vs the hidden")
    p.add_argument("name"); p.add_argument("total", nargs="?", type=int)
    p.set_defaults(func=cmd_seek)
