"""Magic items: attunement, charges, identification (docs/design/02 → Table mechanics →
Phase 15 → Magic items; 04 → PC file, Added by Phases 13–15; 06 → Table mechanics →
Phase 15; plan.md Phase 15 item 4). The tags and bonuses are parsed by lib/magic.py.

    attune Kira "cloak of protection" --during-rest     (or rest short --attune Kira="…")
    unattune Kira "cloak of protection"
    charge Kira "wand of magic missiles" -1 | +2 | =7
    identify Kira "smoky glass ring" [--spell]          (or rest short --identify Kira="…")
    srd item "wand of magic missiles"                   the SRD text and the tags it implies

- Attuning takes a short rest: without `--during-rest` the command refuses and names the
  rest that does it. It refuses an item without the `attune` tag, a fourth item (three at
  most) and one already attuned. `attuned:` holds the item names.
- `charge` spends or restores charges (`charges 5/7`); spending the last one of an item
  with `destroy on 1` rolls the d20 at once (on a 1 the item is gone, and unattuned).
- At each recharge time crossed (`recharge 1d6+1 dawn`) the clock rolls the dice for
  every PC's and NPC's item below its maximum (`dawn_lines`).
- `identify` swaps `unidentified: smoky glass ring (GM: ring of mind shielding)` for the
  true name, with the tags the SRD gives it (rarity, attune, charges, bonuses).
- Bonuses of equipped (and attuned) items feed the numbers live (lib/creatures.py: AC,
  saves, the named weapon's attack and damage); the file's `ac:` stays the base. `pc card
  <pc>` lists the items, `attuned n/3` and the effective numbers.
"""
import re

from lib import campaign, dice, gametime, journal, md
from lib import magic as data
from lib.errors import ToolError
import mutations


class MagicError(ToolError):
    pass


def _pc(name):
    c = mutations.creature(name)
    if c.doc is None:
        raise MagicError(f"{c.name} has no file")
    return c, md.load(c.doc.path), c.name.split()[0] if c.is_pc else c.name


def _find(doc, item):
    try:
        return data.find(doc, item)
    except LookupError as e:
        raise MagicError(str(e)) from None


def _rewrite(doc, it, text):
    """Replace one inventory entry (`it`) by `text` (None removes it)."""
    import inventory
    prefix, entries, trailing = inventory._split_entries(doc.body[it.line])
    if text is None:
        del entries[it.index]
    else:
        entries[it.index] = text
    doc.body[it.line] = (prefix + ", ".join(entries) + ("," if trailing and entries else "")).rstrip()


def attune(name, item, during_rest=False, dry=False):
    c, doc, who = _pc(name)
    it = _find(doc, item)
    if not during_rest:
        raise MagicError(f"attuning takes a short rest: gm.py rest short {who} --attune {who}=\"{it.name}\" "
                         f"(or --during-rest when the rest is being taken anyway)")
    if it.unidentified:
        raise MagicError(f"{it.label()} isn't identified yet (gm.py identify {who} \"{it.name}\")")
    if not it.attune:
        raise MagicError(f"{it.name} doesn't need attunement (no `attune` tag)")
    have = data.attuned(doc)
    if it.name.lower() in {a.lower() for a in have}:
        raise MagicError(f"{who} is already attuned to {it.name}")
    if len(have) >= data.MAX_ATTUNED:
        raise MagicError(f"{who} is attuned to {data.MAX_ATTUNED} items already ({', '.join(have)}): "
                         f"unattune one first")
    if dry:
        return []
    doc.set_front("attuned", have + [it.name])
    doc.save()
    body = f"attune {who} {it.name} ({len(have) + 1}/{data.MAX_ATTUNED})"
    journal.log_delta(body)
    eq = "" if it.equipped else " · not on the Equipped line, so its bonuses don't count yet"
    return [f"[{body}{eq}]"]


def unattune(name, item):
    c, doc, who = _pc(name)
    have = data.attuned(doc)
    want = item.strip().lower()
    hit = [a for a in have if a.lower() == want] or [a for a in have if want in a.lower()]
    if len(hit) != 1:
        raise MagicError(f"{who} isn't attuned to {item!r}" if not hit else f"{item!r} is ambiguous: {', '.join(hit)}")
    left = [a for a in have if a != hit[0]]
    if left:
        doc.set_front("attuned", left)
    else:
        doc.del_front("attuned")
    doc.save()
    body = f"unattune {who} {hit[0]} ({len(left)}/{data.MAX_ATTUNED})"
    journal.log_delta(body)
    return [f"[{body}]"]


def _destroy(doc, it, who):
    _rewrite(doc, it, None)
    have = data.attuned(doc)
    if it.name.lower() in {a.lower() for a in have}:
        left = [a for a in have if a.lower() != it.name.lower()]
        if left:
            doc.set_front("attuned", left)
        else:
            doc.del_front("attuned")


def charge(name, item, change, roller=None):
    c, doc, who = _pc(name)
    it = _find(doc, item)
    if it.charges is None:
        raise MagicError(f"{it.name} has no charges (tag it `charges N/M`)")
    m = re.fullmatch(r"\s*([+=-])\s*(\d+)\s*", change)
    if not m:
        raise MagicError(f"charge: want -N, +N or =N, got {change!r}")
    cur, mx = it.charges
    n = int(m.group(2))
    new = {"-": cur - n, "+": min(mx, cur + n), "=": n}[m.group(1)]
    if new < 0:
        raise MagicError(f"{it.name} has {cur} charge{'s' if cur != 1 else ''} left, can't spend {n}")
    if new > mx:
        raise MagicError(f"{it.name} holds at most {mx}")
    _rewrite(doc, it, it.with_charges(new))
    lines = []
    body = f"charge {who} {it.name} {cur}→{new}/{mx}"
    if new == 0 and cur > 0 and it.destroy:
        r = (roller or dice.Roller()).die(20)
        if r == 1:
            _destroy(doc, it, who)
            body += f" · last charge: d20 {r} — destroyed"
        else:
            body += f" · last charge: d20 {r} — it holds"
    doc.save()
    journal.log_delta(body)
    lines.append(f"[{body}]")
    return lines


def identify(name, item, how="", dry=False):
    c, doc, who = _pc(name)
    it = _find(doc, item)
    if not it.unidentified:
        raise MagicError(f"{it.name} is already identified")
    if dry:
        return []
    true = it.gm or it.name
    tags = data.srd_tags(true)
    rest = re.sub(r"^unidentified\s*:\s*", "", data.public(it.text), flags=re.I).strip()
    own = rest[len(it.name):].strip() if rest.lower().startswith(it.name.lower()) else ""
    text = true + (f" ({tags})" if tags and not own else "") + (f" {own}" if own else "")
    _rewrite(doc, it, text)
    doc.save()
    body = f"identify {who} {it.name} → {true}" + (f" ({how})" if how else "")
    journal.log_delta(body)
    return [f"[{body}" + (f" · {tags}" if tags else "") + "]"]


def _recharge_owners():
    return campaign.pcs() + campaign.npcs()


def dawn_lines(old, new, roller=None):
    """Clock: each item's `recharge <dice> <time>` at each such time crossed in (old,
    new], for items below their maximum. -> lines."""
    out = []
    roller = roller or dice.Roller()
    for d in _recharge_owners():
        doc = md.load(d.path)
        changed = False
        who = str(doc.front.get("name") or "?").split()[0]
        for it in data.items(doc):
            if it.charges is None or it.recharge is None:
                continue
            expr, when = it.recharge
            at = gametime.NAMED.get(when)
            times = [day for day in range(old[0], new[0] + 1)
                     if gametime.diff(old, (day, at)) > 0 and gametime.diff((day, at), new) >= 0]
            cur, mx = it.charges
            for _ in times:
                if cur >= mx:
                    break
                try:
                    res = roller.roll(expr)
                except dice.DiceError:
                    out.append(f"  Recharge: {who}'s {it.name}: can't read {expr!r}")
                    break
                new_cur = min(mx, cur + res.total)
                journal.log_delta(f"recharge {who} {it.name} {cur}→{new_cur}/{mx} ({expr}: {res.body})")
                out.append(f"  Recharge ({when}): {who}'s {it.name} {cur}→{new_cur}/{mx} ({expr}: {res.body})")
                cur = new_cur
            if cur != it.charges[0]:
                _rewrite(doc, it, it.with_charges(cur))
                changed = True
        if changed:
            doc.save()
    return out


def card_lines(doc):
    """`pc card <pc>`: the magic items, attunement and their bonuses."""
    its = data.items(doc)
    have = data.attuned(doc)
    if not its and not have:
        return []
    bits = []
    for it in its:
        tags = []
        if it.attune:
            tags.append("attuned" if data.is_attuned(doc, it) else "not attuned")
        if it.charges:
            tags.append(f"charges {it.charges[0]}/{it.charges[1]}")
        if it.bonus and not it.unidentified:
            tags += [f"{k} {v:+d}" for k, v in it.bonus.items()]
        if not it.equipped and it.bonus:
            tags.append("not equipped")
        bits.append(it.label() + (f" ({', '.join(tags)})" if tags else ""))
    return [f"Magic items: {'; '.join(bits) or '—'} · attuned {len(have)}/{data.MAX_ATTUNED}"]


# ---------- CLI ----------

def _out(ctx, lines):
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def cmd_attune(ctx):
    _out(ctx, attune(ctx.args.target, ctx.args.item, ctx.args.during_rest))


def cmd_unattune(ctx):
    _out(ctx, unattune(ctx.args.target, ctx.args.item))


def cmd_charge(ctx):
    _out(ctx, charge(ctx.args.target, ctx.args.item, ctx.args.change, ctx.roller))


def cmd_identify(ctx):
    _out(ctx, identify(ctx.args.target, ctx.args.item, "identify spell" if ctx.args.spell else ""))


def register(sub, g):
    p = sub.add_parser("attune", parents=[g], help='attune PC "item" --during-rest (a short rest)')
    p.add_argument("target"); p.add_argument("item")
    p.add_argument("--during-rest", action="store_true", help="the short rest is being taken anyway")
    p.set_defaults(func=cmd_attune)

    p = sub.add_parser("unattune", parents=[g], help='unattune PC "item"')
    p.add_argument("target"); p.add_argument("item")
    p.set_defaults(func=cmd_unattune)

    p = mutations.allow_negative(sub.add_parser("charge", parents=[g], help='charge PC "item" -1|+2|=7'))
    p.add_argument("target"); p.add_argument("item"); p.add_argument("change")
    p.set_defaults(func=cmd_charge)

    p = sub.add_parser("identify", parents=[g], help='identify PC "item" [--spell]')
    p.add_argument("target"); p.add_argument("item")
    p.add_argument("--spell", action="store_true", help="by the identify spell (else a short rest with it)")
    p.set_defaults(func=cmd_identify)
