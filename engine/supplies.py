"""Light sources, ammunition, food and water (docs/design/02 → Table mechanics → Light,
Supplies; 04 → PC file, Added by Phases 13–15, Scene state; 06 → Table mechanics →
Phase 13; plan.md Phase 13 items 4–5).

    light Kael torch|lantern|candle|cantrip|daylight|out   light a carried source (spends it)
    eat [Kael …] [--bought "3 sp"]                         a day's food and water each

Settings (04 → Table settings): `track-light: on|off` (off: `lit: [torch]`, nothing
counted or spent), `ammo: all|special|off` (house rule: ordinary arrows and bolts are
tacitly endless):
- special (default): only an Attacks row whose notes say `special ammo <thing>` spends
  one per shot from the inventory (refusing at 0), counted in the Combat block's
  `Ammo spent:` line so `combat end` offers half back; plain `ammo <thing>` is ignored.
- all: every `ammo <thing>` row is spent that way. off: nothing is.
`supplies: strict|loose|off` (food and water):
- strict: `rest long` eats for every PC; the clock checks food at each dawn.
- loose: food and water count only away from a site tagged `services` (rests and dawn
  checks there are skipped).
- off: nothing is counted.
Hunger: 3 + CON modifier days (at least 1) without food, then one level of exhaustion
per day. `fed:` is the last day the PC ate (04); a PC without `fed:` isn't tracked yet.

Python API for roll/combat/clock/rest/brief: `spend_ammo(c, atk)`, `ammo_lines(state)`,
`tick_light(minutes, docs, old)`, `dawn_check(old, new, docs)`, `eat(...)`, `ate_today(doc)`.
"""
import re

from lib import campaign, gametime, journal, light as lightdata, md
from lib.errors import ToolError
import inventory
import mutations

_AMMO = re.compile(r"\b(special\s+)?ammo\s+([a-z][\w-]*)", re.I)
_SPENT = "Ammo spent:"
WATER = ("full", "half", "empty")


class SuppliesError(ToolError):
    pass


def _mode(key):
    return str(campaign.settings().get(key, campaign.SETTINGS[key])).strip().lower()


def _first(name):
    return str(name or "?").split()[0]


def _doc_for(name):
    c = mutations.creature(name)
    if c.doc is None:
        raise SuppliesError(f"{c.name} has no file to carry things in")
    return c


# ---------- light ----------

def _has_spell(doc, spell):
    t = doc.table("Spells")
    return any(r.get("spell", "").strip().lower() == spell for r in (t.rows if t else []))


def light(name, source):
    source = source.strip().lower()
    c = _doc_for(name)
    doc = c.doc
    who = _first(c.name)
    lit = [str(x) for x in (doc.front.get("lit") or [])]
    if source == "out":
        if not lit:
            raise SuppliesError(f"{who} carries no lit source")
        gone = lit.pop()
        if lit:
            doc.set_front("lit", lit)
        else:
            doc.del_front("lit")
        doc.save()
        body = f"light {who} out: {gone}"
        journal.log_delta(body)
        return [f"[{body}]"]
    key = {"cantrip": "light", "light": "light", "torch": "torch", "candle": "candle",
           "lantern": "lantern", "daylight": "daylight"}.get(source)
    if key is None:
        raise SuppliesError("light: torch | lantern | candle | cantrip | daylight | out")
    track = _mode("track-light") != "off"
    spent = ""
    if key == "lantern" and inventory.counted(doc, "bullseye lantern"):
        key = "bullseye-lantern"
    if track:
        if key in ("torch", "candle"):
            n, new, _, _ = inventory.adjust_count(doc, key, -1, who, strict=False)
            spent = f" · {key}es {n}→{new}" if key == "torch" else f" · {key}s {n}→{new}"
        elif key in ("lantern", "bullseye-lantern"):
            if not inventory.counted(doc, "lantern"):
                raise SuppliesError(f"{who} has no lantern")
            n, new, _, _ = inventory.adjust_count(doc, "flask of oil", -1, who, strict=False)
            spent = f" · oil {n}→{new} flasks"
        else:
            if not _has_spell(doc, key):
                raise SuppliesError(f"{who} doesn't have the {key} spell (## Spells)")
    b, dim, minutes, label = lightdata.SOURCES[key]
    lit.append(lightdata.fmt_entry(key, minutes if track else None))
    doc.set_front("lit", lit)
    doc.save()
    body = (f"light {who} {label} · bright {b} ft, dim {b + dim} ft"
            + (f" · {gametime.fmt_delta(minutes)}" if track else " · not counted") + spent)
    journal.log_delta(body)
    return [f"[{body}]"]


def tick_light(minutes, docs, old):
    """Clock: count every lit source down. -> lines (`Light out: …`, `Light low: …`)."""
    out = []
    for doc in docs:
        items = lightdata.entries(doc.front)
        if not items or all(m is None for _, m in items):
            continue
        who = _first(doc.front.get("name"))
        kept = []
        for src, left in items:
            if left is None:
                kept.append(lightdata.fmt_entry(src, None))
                continue
            label = lightdata.SOURCES[src][3]
            now_left = left - minutes
            if now_left <= 0:
                when = gametime.normalize(old[0], old[1] + left)
                out.append(f"Light out: {who}'s {label} ({gametime.fmt(when)})")
                journal.log_delta(f"light {who} {label} burned out {gametime.fmt(when)}")
                continue
            if now_left <= 10 < left:
                out.append(f"Light low: {who}'s {label} ({now_left}m left)")
            kept.append(lightdata.fmt_entry(src, now_left))
        if kept:
            doc.set_front("lit", kept)
        else:
            doc.del_front("lit")
        doc.save()
    return out


# ---------- ammunition ----------

def ammo_of(atk):
    """The ammunition an attack spends under the `ammo` setting, or None."""
    m = _AMMO.search(atk.get("notes", "") or "")
    mode = _mode("ammo")
    if m is None or mode == "off" or (mode != "all" and not m.group(1)):
        return None
    return m.group(2).lower()


def _spent_line(state):
    """(index, {(name, thing): n}) of the Combat block's `Ammo spent:` line."""
    span = state.section("Combat")
    if span is None:
        return None, {}
    for j in range(span[0] + 1, span[1]):
        if state.body[j].startswith(_SPENT):
            counts = {}
            for part in state.body[j][len(_SPENT):].split("·"):
                bits = part.split()
                if len(bits) >= 3 and bits[-1].isdigit():
                    counts[(" ".join(bits[:-2]), bits[-2])] = int(bits[-1])
            return j, counts
    return None, {}


def _record_shot(name, thing):
    state = campaign.load_state()
    if state.table("Combatants") is None:
        return
    j, counts = _spent_line(state)
    counts[(name, thing)] = counts.get((name, thing), 0) + 1
    line = _SPENT + " " + " · ".join(f"{n} {t} {k}" for (n, t), k in counts.items())
    if j is None:
        span = state.section("Combat")
        j = span[0] + 1
        if j < len(state.body) and state.body[j].startswith("Turn:"):
            j += 1
        state.body.insert(j, line)
    else:
        state.body[j] = line
    state.save()


def spend_ammo(c, atk):
    """roll.attack: a shot with tracked ammunition (`ammo_of`) spends one (refusing at 0)
    and is counted in the Combat block. -> a line or None."""
    thing = ammo_of(atk)
    if thing is None:
        return None
    who = _first(c.name)
    line = None
    if c.doc is not None and c.doc.section("Inventory") is not None:
        doc = md.load(c.doc.path)
        if not [h for h in inventory.counted(doc, thing) if h[3] > 0]:
            raise SuppliesError(f"{who} has no {thing}")
        n, new, before, after = inventory.adjust_count(doc, thing, -1, who, strict=False)
        doc.save()
        line = f"[ammo {who} {thing} {n}→{new}]"
        journal.log_delta(f"ammo {who} {thing} {n}→{new}")
    _record_shot(who, thing)
    return line


def ammo_lines(state):
    """combat end: what the shooters spent and what a search recovers."""
    _, counts = _spent_line(state)
    if not counts or _mode("ammo") == "off":
        return []
    out = []
    for (n, thing), k in counts.items():
        back = k // 2
        out.append(f"[Ammo: {n} spent {k} {thing}; after a search, "
                   + (f"{back} can be recovered (gm.py item {n} +{back} {thing})]" if back
                      else "none can be recovered]"))
    return out


# ---------- food and water ----------

def _site_has_services(loc):
    site = str(loc or "").split("/")[0].lstrip("@")
    if not site:
        return False
    p = campaign.root() / "locations" / f"{site}.md"
    if not p.exists():
        return False
    tags = md.load(p).front.get("tags") or []
    return "services" in [str(t).strip().lower() for t in (tags if isinstance(tags, list) else [tags])]


def counts_here(doc):
    """Does food and water count for this PC now? strict: always; loose: away from a
    `services` site; off: never."""
    mode = _mode("supplies")
    if mode == "off":
        return False
    return mode == "strict" or not _site_has_services(doc.front.get("location"))


def _water(doc):
    """(entry index tuple, state) of the first waterskin, or None."""
    span = doc.section("Inventory")
    if span is None:
        return None
    for j in range(span[0] + 1, span[1]):
        _, entries, _ = inventory._split_entries(doc.body[j])
        for k, e in enumerate(entries):
            if re.search(r"\bwaterskins?\b", e, re.I):
                m = re.search(r"\((full|half|empty)\)", e, re.I)
                return j, k, e, (m.group(1).lower() if m else "full")
    return None


def _drink(doc):
    """Spend a day of water: full → half → empty. -> text or None (no water)."""
    w = _water(doc)
    if w is None or w[3] == "empty":
        return None
    j, k, e, st = w
    new = WATER[WATER.index(st) + 1]
    after = re.sub(r"\((full|half|empty)\)", f"({new})", e, flags=re.I) if "(" in e else f"{e} ({new})"
    prefix, entries, trailing = inventory._split_entries(doc.body[j])
    entries[k] = after
    doc.body[j] = (prefix + ", ".join(entries) + ("," if trailing and entries else "")).rstrip()
    return f"waterskin {st}→{new}"


def has_water(doc):
    w = _water(doc)
    return w is not None and w[3] != "empty"


def _con_mod(doc):
    scores = doc.front.get("scores") or {}
    try:
        return (int(scores.get("con", 10)) - 10) // 2
    except (TypeError, ValueError):
        return 0


def food_limit(doc):
    return max(1, 3 + _con_mod(doc))


def _day(text):
    m = re.match(r"^\s*Day\s+(-?\d+)", str(text or ""))
    return int(m.group(1)) if m else None


def eat(names=(), bought=None, quiet_off=False):
    """One day's food and water for each PC: a ration and a day from the waterskin, or
    coin with `bought` ("3 sp", each). Sets `fed:` to today. -> lines."""
    if _mode("supplies") == "off":
        return [] if quiet_off else ["[eat: supplies: off — nothing is counted]"]
    state = campaign.load_state()
    today = gametime.parse(state.front.get("in-game-datetime"))[0]
    if names:
        docs = [_doc_for(n).doc for n in names]
    else:
        docs = [d for d in campaign.scene_pcs() if d.front.get("present") is not False]
    lines = []
    for d in docs:
        doc = md.load(d.path)
        who = _first(doc.front.get("name"))
        bits = []
        if bought:
            m = re.fullmatch(r"\s*(\d+)\s*(pp|gp|ep|sp|cp)\s*", bought.lower())
            if not m:
                raise SuppliesError(f"eat --bought wants e.g. \"3 sp\", got {bought!r}")
            line, _ = inventory.coin(doc.front.get("name"), f"-{m.group(1)}{m.group(2)}")
            lines.append(line)
            doc = md.load(d.path)
            bits.append(f"bought ({m.group(1)} {m.group(2)})")
        else:
            try:
                n, new, _, _ = inventory.adjust_count(doc, "ration", -1, who, strict=False)
            except inventory.InventoryError:
                body = f"eat {who}: no rations — not fed"
                journal.log_delta(body)
                lines.append(f"[{body}]")
                continue
            bits.append(f"rations {n}→{new}")
            drank = _drink(doc)
            if drank:
                bits.append(drank)
            else:
                bits.append("no water")
        doc.set_front("fed", f"Day {today}")
        doc.save()
        body = f"eat {who} · " + " · ".join(bits) + f" · fed Day {today}"
        journal.log_delta(body)
        lines.append(f"[{body}]")
        if "no water" in bits:
            lines.append(f"[{who} has no water today: DC 15 CON save or 1 level of exhaustion; none at all "
                         f"→ the level is automatic (gm.py save {who} con 15 · gm.py exhaust {who} +1)]")
    return lines


def ate_today(doc, day):
    return _day(doc.front.get("fed")) == day


def dawn_check(old, new, docs):
    """Clock: for each dawn crossed in (old, new], PCs who didn't eat the day before.
    Past 3 + CON days the exhaustion is applied; no water asks for the CON save."""
    if _mode("supplies") == "off":
        return []
    dawn = gametime.NAMED["dawn"]
    days = [d for d in range(old[0], new[0] + 1)
            if gametime.diff(old, (d, dawn)) > 0 and gametime.diff((d, dawn), new) >= 0]
    if not days:
        return []
    out = []
    import conditions_ext
    for d in docs:
        doc = md.load(d.path)
        fed = _day(doc.front.get("fed"))
        if fed is None or not counts_here(doc):
            continue
        name = str(doc.front.get("name") or "?")
        who = _first(name)
        limit = food_limit(doc)
        behind = [day - 1 - fed for day in days if day - 1 > fed]
        if not behind:
            continue
        hungry = sum(1 for b in behind if b > limit)
        line = f"Supplies: {who} last ate Day {fed} ({behind[-1]} day{'s' if behind[-1] != 1 else ''}; exhaustion after {limit})"
        if hungry:
            got = conditions_ext.exhaust(name, f"+{hungry}", "hunger")
            line += f" · +{hungry} exhaustion (hunger)"
            out.append("  " + line)
            out += ["  " + x for x in got]
        else:
            out.append("  " + line)
        if not has_water(md.load(d.path)):
            out.append(f"  Water: {who} has none — DC 15 CON save or 1 level of exhaustion; none at all → "
                       f"automatic (gm.py save {who} con 15 · gm.py exhaust {who} +1)")
    return out


# ---------- CLI ----------

def _out(ctx, lines):
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def cmd_light(ctx):
    _out(ctx, light(ctx.args.target, ctx.args.source))


def cmd_eat(ctx):
    _out(ctx, eat(ctx.args.names, ctx.args.bought))


def register(sub, g):
    p = sub.add_parser("light", parents=[g], help="light NAME torch|lantern|candle|cantrip|daylight|out")
    p.add_argument("target"); p.add_argument("source")
    p.set_defaults(func=cmd_light)

    p = sub.add_parser("eat", parents=[g], help='eat [PCs] [--bought "3 sp"]: a day of food and water')
    p.add_argument("names", nargs="*")
    p.add_argument("--bought", help="paid for a meal instead (each)")
    p.set_defaults(func=cmd_eat)
