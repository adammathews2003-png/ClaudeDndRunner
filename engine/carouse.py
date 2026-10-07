"""`gm.py carouse <pc,pc> [--table carousing]` and `gm.py carouse --reroll <pc>` — a night
of carousing on a d100 table (docs/design/02 → Table mechanics → Phase 16 → Carousing; 06 →
Phase 16 — table extras; 04 → Random tables; plan.md Phase 16 item 6).

Only while `carousing: on` (default on since 2026-10-07). It is offered in the fiction, once
per tavern: after the party orders drinks in a tavern at night, `carouse --offer` says whether
this site has had the offer yet and records it (`offered:` in state/carousing.md); after that
it stays an unspoken option the players may take up any night. Everything is behind the screen: the output is
for the GM (never pasted) and every delta, the coin and items included, is a `(GM)` log
line until the morning reveal. For each PC:
1. the night's cost (`cost:` in the table's frontmatter, default `1d6x10gp`); a PC who
   can't pay spends what they have and owes the rest (a clock: the debt comes due in 7 days);
2. one roll on the table (lib/tables.py). A row whose tags touch one of the campaign's
   content `lines:` is re-rolled at once; one touching a `veils:` entry stays and is marked
   `(veil: off screen)`;
3. the row's effect codes are applied: `coin ±<dice>[xN] [denom]` (a loss beyond the
   purse becomes a debt), `item +"…"`, `item -"…"`, `item -random` (one whole entry from
   the pack), `clock +3d "…"` (a `## Clocks` bullet in current.md), `no-rest` (printed),
   `twice` (two more rolls, each applied, never landing on a `twice` row again; the GM
   combines the stories). Anything else is printed for the GM to file with ordinary commands.
No scenario-breaking nights (02 → Carousing): a row tagged `disruptive` prints a fit check;
the GM re-rolls any row that can't happen here or would put the scenario's goals out of reach.
The night is recorded in `state/carousing.md` (one row per PC: roll, result, what was
applied) so `--reroll <pc>` can take the row back (reversing what the tool applied, never
the cost) and roll again, logged GM-only. The clock is not moved: the GM adds `clock
advance to 07:00` to the same batch, then narrates the morning reveal.
"""
import re

from lib import campaign, dice, gametime, journal, md, tables
from lib.errors import ToolError
import inventory
import mutations

STATE = "state/carousing.md"
STATE_TEXT = """# Carousing
<!-- GM-only. The latest night per PC, written by gm.py carouse and read by
     `carouse --reroll` (02 → Table mechanics → Phase 16 → Carousing). `applied` is what the
     tool did, so a re-roll can take it back; the night's cost is never refunded. -->

| pc | night | roll | result | applied |
|----|-------|------|--------|---------|
"""
_AMOUNT = re.compile(r"^([+-])\s*(\d*d\d+|\d+)\s*(?:[x×]\s*(\d+))?\s*(pp|gp|ep|sp|cp)?$", re.I)
RATE = {"pp": 1000, "gp": 100, "ep": 50, "sp": 10, "cp": 1}
DEBT_DAYS = 7


class CarouseError(ToolError):
    pass


def enabled():
    return str(campaign.settings().get("carousing", "off")).strip().lower() == "on"


def _pc(name):
    c = mutations.creature(name)
    if not c.is_pc or c.doc is None:
        raise CarouseError(f"carouse: {c.name} is not a PC")
    return c


def _first(c):
    return c.name.split()[0]


def boundaries():
    front = campaign.boundaries_front()
    get = lambda k: [str(x) for x in (front.get(k) or []) if str(x).strip()]  # noqa: E731
    return get("lines"), get("veils")


# ---------- coin ----------

def _amount(text, roller):
    """'-2d6x10' -> (-1, 70, 'gp', '2d6×10: (3,4)×10 = 70 gp'): the amount in that coin."""
    m = _AMOUNT.match(text.strip())
    if not m:
        raise CarouseError(f"carouse: can't read the amount {text!r} (want e.g. -2d6x10 or +5 sp)")
    sign = -1 if m.group(1) == "-" else 1
    mult = int(m.group(3) or 1)
    denom = (m.group(4) or "gp").lower()
    if "d" in m.group(2).lower():
        res = roller.roll(m.group(2))
        n = res.total * mult
        faces = ",".join(str(r) for part in [res.parts] for p in part if "rolls" in p for r in p["rolls"])
        x = f"×{mult}" if mult > 1 else ""
        shown = f"{m.group(2)}{x}: ({faces}){x} = {n} {denom}"
    else:
        n = int(m.group(2)) * mult
        shown = f"{n} {denom}"
    return sign, n, denom, shown


def _coin_deltas(lines):
    """`[coin Kira 35→15 gp]` lines -> ['coin -20gp']."""
    out = []
    for line in lines:
        m = re.search(r"(\d+)→(\d+) (pp|gp|ep|sp|cp)\]$", line)
        if m:
            d = int(m.group(2)) - int(m.group(1))
            if d:
                out.append(f"coin {d:+d}{m.group(3)}")
    return out


def _clock(c, delta, text, applied):
    state = campaign.load_state()
    now = gametime.parse(state.front.get("in-game-datetime"))
    due = gametime.add(now, delta if delta.startswith("+") else "+" + delta)
    bullet = f"- {gametime.fmt(due)}: {text} (carousing: {_first(c)})"
    span = state.section("Clocks")
    if span is not None:
        for i in range(span[0] + 1, span[1]):
            if state.body[i].strip() == "(none)":
                del state.body[i]
                break
    state.append_line("Clocks", bullet)
    span = state.section("Clocks")   # keep the bullets in time order
    import scene
    idx = [i for i in range(span[0] + 1, span[1]) if state.body[i].lstrip().startswith("- ")]
    ordered = sorted((state.body[i] for i in idx), key=scene._clock_key)
    for i, line in zip(idx, ordered):
        state.body[i] = line
    state.save()
    journal.log_delta(f"clock added: {bullet[2:]}")
    applied.append(f'clock "{bullet[2:]}"')
    return f"[clock {bullet[2:]}]"


def _pay(c, sign, n, denom, why, applied):
    """Pay (or receive) coin; a loss beyond the purse becomes a debt clock. -> lines."""
    if sign > 0:
        line, _ = inventory.coin(c.name, f"+{n}{denom}")
        applied += _coin_deltas([line])
        return [line]
    want = n * RATE[denom]
    have = inventory.purse(md.load(c.doc.path))
    paid = min(want, have)
    lines = inventory.pay(c.name, paid) if paid else []
    applied += _coin_deltas(lines)
    if paid < want:
        owed = inventory.fmt_cost(want - paid)
        lines.append(_clock(c, f"+{DEBT_DAYS}d", f"{_first(c)} owes {owed} ({why}); the debt comes due", applied))
        lines.append(f"[carouse {_first(c)}: couldn't pay {inventory.fmt_cost(want)} ({why}), owes {owed}]")
    return lines


# ---------- items ----------

def _pack_entries(doc):
    """[(line index, entry)] of the `- Pack:` line and its continuations."""
    span = doc.section("Inventory")
    out, in_pack = [], False
    for j in range(span[0] + 1, span[1]) if span else []:
        line = doc.body[j]
        if re.match(r"^\s*-\s+Pack:", line):
            in_pack = True
        elif re.match(r"^\s*-\s+", line) or not line.strip():
            in_pack = False
        elif not line.startswith((" ", "\t")):
            in_pack = False
        if in_pack:
            _, entries, _ = inventory._split_entries(line)
            out += [(j, e) for e in entries]
    return out


def _take_random(c, roller, applied):
    doc = md.load(c.doc.path)
    entries = _pack_entries(doc)
    if not entries:
        return [f"[carouse {_first(c)}: item -random, but the pack is empty]"]
    j, entry = entries[roller.die(len(entries)) - 1]
    prefix, items, trailing = inventory._split_entries(doc.body[j])
    items.remove(entry)
    doc.body[j] = (prefix + ", ".join(items) + ("," if trailing and items else "")).rstrip()
    doc.save()
    body = f"item {c.name} -{entry} (carousing)"
    journal.log_delta(body)
    applied.append(f'item -"{entry}"')
    return [f"[{body}]"]


def _item(c, sign, text, applied):
    line, _ = inventory.item(c.name, sign, text, "carousing")
    applied.append(f'item {sign}"{text}"')
    return [line]


# ---------- the night ----------

def _codes(c, row, roller, applied):
    """Apply a row's effect codes -> (lines, [codes for the GM], no_rest)."""
    lines, other, no_rest = [], [], False
    for code in tables.codes(row.effect):
        low = code.lower()
        m = re.match(r'^item\s*([+-])\s*"(.+)"$', code, re.I) or re.match(r"^item\s*([+-])\s*(\S.*)$", code, re.I)
        if low.startswith("coin"):
            sign, n, denom, shown = _amount(code[4:], roller)
            lines.append(f"[carouse {_first(c)}: coin {'+' if sign > 0 else '-'}{shown}]")
            lines += _pay(c, sign, n, denom, "carousing", applied)
        elif re.fullmatch(r"item\s*-\s*random", low):
            lines += _take_random(c, roller, applied)
        elif m:
            lines += _item(c, m.group(1), m.group(2).strip().strip('"'), applied)
        elif low.startswith("clock"):
            cm = re.match(r'^clock\s+(\+?\s*(?:\d+\s*[dhm]\s*)+)\s+"?(.+?)"?$', code, re.I)
            if not cm:
                raise CarouseError(f"carouse: can't read {code!r} (want clock +3d \"…\")")
            lines.append(_clock(c, cm.group(1).replace(" ", ""), cm.group(2), applied))
        elif low in ("no-rest", "no rest"):
            no_rest = True
        elif low == "twice":
            pass
        else:
            other.append(code)
    return lines, other, no_rest


def _roll_row(table, roller, lines_, veils, skip=None):
    """(n, row, notes) with rows touching a content line re-rolled."""
    notes = []
    for _ in range(200):
        n, row = table.roll(roller)
        if skip is not None and (skip(row) if callable(skip) else row is skip):
            continue
        hit = next((x for x in lines_ if tables.matches(row.tags, x)), None)
        if hit:
            notes.append(f"re-rolled {n} (line: {hit})")
            continue
        veil = next((x for x in veils if tables.matches(row.tags, x)), None)
        if veil:
            notes.append(f"veil: off screen ({veil})")
        return n, row, notes
    raise CarouseError(f"carouse: every row of tables/{table.name}.md touches a content line")


def _state_doc():
    p = campaign.root() / STATE
    if not p.exists():
        return md.new(p, STATE_TEXT)
    return md.load(p)


def _record(c, night, n, row, applied):
    doc = _state_doc()
    t = doc.table("Carousing")
    clean = lambda s: str(s).replace("|", "/")  # noqa: E731
    vals = {"pc": _first(c), "night": night, "roll": str(n), "result": clean(row.result),
            "applied": clean("; ".join(applied) or "—")}
    for i, r in enumerate(t.rows):
        if r.get("pc", "").lower() == _first(c).lower():
            for k, v in vals.items():
                t.set(i, k, v)
            break
    else:
        t.append(vals)
    doc.save()


def _cost(table, roller):
    text = str(table.front.get("cost") or "1d6x10gp").replace(" ", "")
    return _amount("-" + text.lstrip("+-"), roller)


def _one(c, table, roller, lines_, veils, night):
    out, applied = [], []
    sign, n, denom, shown = _cost(table, roller)
    out.append(f"[carouse {_first(c)}: the night costs {shown}]")
    out += _pay(c, sign, n, denom, "a night of carousing", [])   # the cost (and its debt) is never taken back
    k, row, notes = _roll_row(table, roller, lines_, veils)
    out += _show(c, table, k, row, notes)
    lines, other, no_rest = _codes(c, row, roller, applied)
    out += lines + _for_gm(c, other, no_rest)
    if _twice(row):
        picks = [_roll_row(table, roller, lines_, veils, skip=_twice) for _ in range(2)]
        for k2, r2, n2 in picks:
            out += _show(c, table, k2, r2, n2)
            lines, other, nr = _codes(c, r2, roller, applied)
            out += lines + _for_gm(c, other, nr and not no_rest)
            no_rest = no_rest or nr
        out.append(f"[carouse {_first(c)}: combine the two into one night]")
        k = f"{k}: " + " + ".join(str(x) for x, _, _ in picks)
        row = tables.Row(row.lo, row.hi, " + ".join(r.result for _, r, _ in picks))
    _record(c, night, k, row, applied)
    journal.log_delta(f'[carouse] {_first(c)} {k}: "{row.result}"' + (f" ({'; '.join(notes)})" if notes else ""))
    return out


def _twice(row):
    return any(x.lower() == "twice" for x in tables.codes(row.effect))


def _show(c, table, n, row, notes):
    tag = f" · tags: {', '.join(row.tags)}" if row.tags else ""
    eff = f" · effect: {row.effect}" if row.effect else ""
    note = f" ({'; '.join(notes)})" if notes else ""
    base, _, k = str(n).partition(".")
    die = f"d{table.die} {base}" + (f" · d{len(table.slots(int(base)))} {k}" if k else "")
    out = [f"[carouse {_first(c)}: {die} → {row.result}{eff}{tag}{note}]"]
    if any(t.lower() == "disruptive" for t in row.tags):
        out.append(f"[fit check: can this happen here, and does it leave the scenario's goals reachable? "
                   f"If not, `carouse --reroll {_first(c)}` before the reveal]")
    return out


def _for_gm(c, other, no_rest):
    out = [f"[file for {_first(c)}: {code}]" for code in other]
    if no_rest:
        out.append(f"[{_first(c)}: the night doesn't count as a long rest]")
    return out


def carouse(names, table_name="carousing", roller=None):
    if not enabled():
        raise CarouseError("carousing: off (campaign setting `carousing: on` turns it on)")
    roller = roller or dice.Roller()
    pcs = [_pc(x) for x in names]
    if not pcs:
        raise CarouseError("carouse: who's in? (carouse Kira,Kael)")
    try:
        table = tables.load(table_name)
    except tables.TableError as e:
        raise CarouseError(f"carouse: {e}") from None
    lines_, veils = boundaries()
    night = str(campaign.load_state().front.get("in-game-datetime") or "")
    out = ["[CAROUSE — GM only: never paste this; reveal it through the morning]"]
    with journal.gm_only():
        for c in pcs:
            out += _one(c, table, roller, lines_, veils, night)
    out.append("[next: `clock advance to 07:00` in this batch (a long rest unless a row says not), "
               "then narrate each PC waking to the evidence; file the rest (stub npc, attitude, rumor) in the same do]")
    return out


# ---------- re-roll ----------

def _reverse(c, applied):
    out = []
    for code in tables.codes(applied):
        if code in ("—", ""):
            continue
        m = re.match(r"^coin ([+-])(\d+)(pp|gp|ep|sp|cp)$", code)
        if m:
            back = "-" if m.group(1) == "+" else "+"
            out.append(inventory.coin(c.name, f"{back}{m.group(2)}{m.group(3)}")[0])
            continue
        m = re.match(r'^item ([+-])"(.+)"$', code)
        if m:
            back = "-" if m.group(1) == "+" else "+"
            out.append(inventory.item(c.name, back, m.group(2), "carousing re-rolled")[0])
            continue
        m = re.match(r'^clock "(.+)"$', code)
        if m:
            state = campaign.load_state()
            span = state.section("Clocks")
            for i in range(span[0] + 1, span[1]) if span else []:
                if state.body[i].strip() == f"- {m.group(1)}":
                    del state.body[i]
                    break
            state.save()
            journal.log_delta(f"clock removed: {m.group(1)}")
            out.append(f"[clock removed: {m.group(1)}]")
    return out


def reroll(name, table_name="carousing", roller=None):
    if not enabled():
        raise CarouseError("carousing: off (campaign setting `carousing: on` turns it on)")
    roller = roller or dice.Roller()
    c = _pc(name)
    p = campaign.root() / STATE
    t = md.load(p).table("Carousing") if p.exists() else None
    row = next((r for r in (t.rows if t else []) if r.get("pc", "").lower() == _first(c).lower()), None)
    if row is None:
        raise CarouseError(f"carouse --reroll: {_first(c)} hasn't caroused yet")
    try:
        table = tables.load(table_name)
    except tables.TableError as e:
        raise CarouseError(f"carouse: {e}") from None
    lines_, veils = boundaries()
    out = [f"[CAROUSE re-roll — GM only: {_first(c)}'s {row.get('roll')} is taken back]"]
    with journal.gm_only():
        out += _reverse(c, row.get("applied", ""))
        old = table.row_for_label(row.get("roll"))
        k, new, notes = _roll_row(table, roller, lines_, veils, skip=lambda r: r is old or _twice(r))
        out += _show(c, table, k, new, notes)
        applied = []
        lines, other, no_rest = _codes(c, new, roller, applied)
        out += lines + _for_gm(c, other, no_rest)
        _record(c, row.get("night", ""), k, new, applied)
        journal.log_delta(f'[carouse] {_first(c)} re-rolled {row.get("roll")} → {k}: "{new.result}"')
    return out


def offer():
    """`carouse --offer`: first offer at this site (record it), or already offered."""
    if not enabled():
        raise CarouseError("carousing: off (campaign setting `carousing: on` turns it on)")
    site = str(campaign.load_state().front.get("party-location") or "").split("/")[0].lstrip("@")
    if not site:
        raise CarouseError("carouse --offer: the party has no location")
    doc = _state_doc()
    offered = [str(x) for x in (doc.front.get("offered") or [])]
    if site in offered:
        return [f"[carousing: already offered at {site}. Don't raise it again; it's still theirs to take any night]"]
    doc.set_front("offered", offered + [site])
    doc.save()
    journal.log_delta(f"[carouse] offered at {site}", gm=True)
    return [f"[carousing: first time at {site}. Offer it once, in the fiction (a round of dice, a rowdy "
            "table, \"the night's young\"), then let it be]"]


def cmd_carouse(ctx):
    a = ctx.args
    if a.offer:
        lines = offer()
    elif a.reroll:
        lines = reroll(a.reroll, a.table, ctx.roller)
    else:
        names = [x.strip() for x in ",".join(a.pcs).split(",") if x.strip()]
        lines = carouse(names, a.table, ctx.roller)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("carouse", parents=[g], help="carouse Kira,Kael [--table carousing] | carouse --reroll Kira "
                                                    "(GM-only output)")
    p.add_argument("pcs", nargs="*")
    p.add_argument("--table", default="carousing")
    p.add_argument("--reroll", help="take back this PC's last row and roll again (GM-only)")
    p.add_argument("--offer", action="store_true",
                   help="drinks ordered at night in a tavern: first offer here? (records it; once per tavern)")
    p.set_defaults(func=cmd_carouse)
