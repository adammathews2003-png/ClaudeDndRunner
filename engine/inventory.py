"""Inventory-side mutations: `item coin res attitude` (docs/design/06 → mutations table
L137-151, turn blocks L156-168; docs/design/04 → PC file `## Inventory`, `## Resources`
L352-424; NPC file `## History with the party` L312-350; plan.md Phase 2 item 5).

Python API: item(name, sign, text, reason=""), coin(name, change),
res(name, sign, resource, n=1), attitude(name, value, reason="") — each returns
`(line, data)`, writes through lib/md.py and logs its delta.

`item -thing` finds the entry in the `## Inventory` bullets (exact or plural match,
then a leading word, then a substring; a tie between entries is an error listing
them). A count is decremented instead of removing the entry: leading (`2 daggers` →
`1 dagger`) or in parentheses (`quiver (20 arrows)` → `quiver (19 arrows)`) — only
for an exact/plural match; a looser match removes the whole entry.
`item + thing` appends to the `Pack:` bullet. `item Kira +3 arrows` / `-3 arrows` adds
to or takes from a counted entry (`quiver (17 arrows)` → `(20 arrows)`; Phase 13); with
no counted entry, `+3 arrows` is appended to the pack.

Counted supplies (Phase 13, 04 → Ammunition and supplies): `counted(doc, noun)` finds the
entry holding a count of `noun` — `quiver (20 arrows)`, `torches (4)`, `2 flasks of oil`,
`rations (5 days)`, `5 days rations` — and `adjust_count(doc, noun, delta)` rewrites it
(a container keeps its `(0 arrows)`; a counted item at 0 is gone). Callers save.
"""
import re

from lib import campaign, journal
from lib.errors import ToolError
from mutations import creature, emit

ATTITUDES = ("hostile", "wary", "neutral", "friendly", "ally")


class InventoryError(ToolError):
    pass


# ---------- people ----------

def attitude(name, value, reason=""):
    value = value.strip().lower()
    if value not in ATTITUDES:
        raise InventoryError(f"attitude: one of {' | '.join(ATTITUDES)}")
    c = creature(name)
    if c.is_pc or c.doc is None:
        raise InventoryError(f"attitude: {c.name} is not an NPC with a file")
    doc = c.doc
    old = str(doc.front.get("attitude-to-party") or "")
    doc.set_front("attitude-to-party", value)
    when = str(campaign.load_state().front.get("in-game-datetime") or "")
    line = f"- {when}: {old}→{value}" + (f" — {reason}" if reason else "")
    span = doc.section("History with the party")
    replaced = False
    if span is not None:
        for j in range(span[0] + 1, span[1]):
            if re.fullmatch(r"\s*\((none yet|none)\)\s*", doc.body[j]):
                doc.body[j] = line
                replaced = True
                break
    if not replaced:
        doc.append_line("## History with the party", line)
    doc.save()
    body = f"attitude {c.name} {old}→{value}" + (f" ({reason})" if reason else "")
    journal.log_delta(body)
    return f"[{body}]", {"name": c.name, "from": old, "to": value}


# ---------- items ----------

def _inventory(c):
    span = c.doc.section("Inventory") if c.doc is not None else None
    if span is None:
        raise InventoryError(f"{c.name} has no ## Inventory")
    return c.doc, span


def _split_top(text):
    """Split on commas outside parentheses."""
    out, buf, depth = [], [], 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [x.strip() for x in out if x.strip()]


def _split_entries(line):
    """A bullet/continuation line -> (prefix, [entries], trailing_comma)."""
    m = re.match(r"^(\s*-\s+[^:]+:\s*|\s*-\s+|\s*)(.*)$", line)
    prefix, rest = m.group(1), m.group(2).rstrip()
    trailing = rest.endswith(",")
    return prefix, _split_top(rest.rstrip(",")), trailing


def _sing_first(text):
    """Singularize the first word if it ends in a single s: `flasks of oil` →
    `flask of oil`; otherwise unchanged."""
    first, sep, rest = text.partition(" ")
    if len(first) > 2 and first.endswith("s") and not first.endswith("ss"):
        first = first[:-1]
    return first + sep + rest


def _score(entry, want):
    """(score, kind): 3 exact/plural, 2 leading word, 1 substring; kind 'paren' when
    the match is a parenthesized count."""
    e = entry.lower()
    bare = re.sub(r"^\d+\s+", "", e)
    w = _sing_first(want)
    if _sing_first(bare) == w or e == want:
        return 3, "whole"
    pm = re.search(r"\((\d+)\s+([^)]+)\)", e)
    if pm and _sing_first(pm.group(2).strip()) == w:
        return 3, "paren"
    if _sing_first(bare).startswith(w + " "):
        return 2, "whole"
    if want in e:
        return 1, "whole"
    return 0, ""


def _decrement(entry, kind):
    """The entry after taking one away, or None when it is gone."""
    if kind == "paren":
        pm = re.search(r"\((\d+)(\s+)([^)]+)\)", entry)
        n = int(pm.group(1)) - 1
        noun = _sing_first(pm.group(3)) if n == 1 else pm.group(3)
        inner = f"({n}{pm.group(2)}{noun})"
        return entry[:pm.start()] + inner + entry[pm.end():]
    m = re.match(r"^(\d+)\s+(.*)$", entry)
    if m and int(m.group(1)) > 1:
        n = int(m.group(1)) - 1
        noun = _sing_first(m.group(2)) if n == 1 else m.group(2)
        return f"{n} {noun}"
    return None


def _sing_word(w):
    lw = w.lower()
    if lw.endswith(("ches", "shes", "xes", "sses")):
        return w[:-2]
    if lw.endswith("ies") and len(lw) > 4:
        return w[:-3] + "y"
    if lw.endswith("s") and not lw.endswith("ss") and len(lw) > 2:
        return w[:-1]
    return w


def _sing_text(text):
    return " ".join(_sing_word(w) for w in re.findall(r"[a-z'-]+", text.lower()))


def _has_noun(text, stem):
    return re.search(rf"(^|\s){re.escape(stem)}(\s|$)", _sing_text(text)) is not None


def counted(doc, noun):
    """[(line j, entry k, entry text, count, kind)] for inventory entries holding a count
    of `noun`. kind: 'paren-noun' (`quiver (20 arrows)`: the container stays at 0),
    'paren' (`torches (4)`, `rations (5 days)`), 'lead' (`2 flasks of oil`), 'one'."""
    span = doc.section("Inventory")
    if span is None:
        return []
    stem = _sing_text(noun)
    out = []
    for j in range(span[0] + 1, span[1]):
        line = doc.body[j]
        if not line.strip() or re.match(r"^\s*-\s+Coin:", line):
            continue
        _, entries, _ = _split_entries(line)
        for k, e in enumerate(entries):
            paren = re.search(r"\((\d+)(?:\s+([^)]*))?\)", e)
            base = re.sub(r"\([^)]*\)", " ", e).strip()
            lead = re.match(r"^(\d+)\s+(.*)$", base)
            if paren and paren.group(2) and _has_noun(paren.group(2), stem):
                out.append((j, k, e, int(paren.group(1)), "paren-noun"))
            elif _has_noun(lead.group(2) if lead else base, stem):
                if paren:
                    out.append((j, k, e, int(paren.group(1)), "paren"))
                elif lead:
                    out.append((j, k, e, int(lead.group(1)), "lead"))
                else:
                    out.append((j, k, e, 1, "one"))
    return out


def adjust_count(doc, noun, delta, owner="", strict=True):
    """Change the count of `noun` by `delta`. -> (before, after, entry before, entry
    after or None). Raises when there is none (or not enough). Doesn't save."""
    hits = counted(doc, noun)
    if delta < 0:
        hits = [h for h in hits if h[3] > 0]
    if not hits:
        raise InventoryError(f"{owner or 'they'} {'has' if owner else 'have'} no {noun}")
    if len(hits) > 1 and strict:
        raise InventoryError(f"{noun!r} is ambiguous: " + "; ".join(h[2] for h in hits))
    j, k, e, n, kind = hits[0]
    new = n + delta
    if new < 0:
        raise InventoryError(f"{owner or 'they'} {'has' if owner else 'have'} only {n} {noun}")
    if kind in ("paren-noun", "paren"):
        m = re.search(r"\((\d+)", e)
        after = e[:m.start(1)] + str(new) + e[m.end(1):]
        if new == 0 and kind == "paren":
            after = None
    elif kind == "lead":
        m = re.match(r"^(\d+)(\s+)(.*)$", e)
        rest = m.group(3)
        after = None if new == 0 else f"{new}{m.group(2)}{_sing_first(rest) if new == 1 else rest}"
    else:
        after = None if new == 0 else (e if new == 1 else f"{new} {e}")
    prefix, entries, trailing = _split_entries(doc.body[j])
    if after is None:
        del entries[k]
    else:
        entries[k] = after
    doc.body[j] = (prefix + ", ".join(entries) + ("," if trailing and entries else "")).rstrip()
    return n, new, e, after


def item(name, sign, text, reason="", count=None):
    text = text.strip()
    if not text:
        raise InventoryError("item: name the item")
    c = creature(name)
    doc, (start, end) = _inventory(c)
    if count is not None:   # `item Kira +3 arrows`: a counted entry, else a new pack entry
        hits = counted(doc, text)
        if hits or sign == "-":
            n, new, before, after = adjust_count(doc, text, count if sign == "+" else -count, c.name)
            doc.save()
            body = f"item {c.name} {sign}{count} {text} · {before} → {after or 'gone'}" + (f" ({reason})" if reason else "")
            journal.log_delta(body)
            return f"[{body}]", {"name": c.name, "sign": sign, "item": text, "from": n, "to": new}
        text = f"{count} {text}"
    if sign == "+":
        pack = None
        for j in range(start + 1, end):
            if re.match(r"^\s*-\s+Pack:", doc.body[j]):
                pack = j
        if pack is None:
            doc.append_line("## Inventory", f"- Pack: {text}")
        else:
            last = pack
            while last + 1 < end and doc.body[last + 1].startswith((" ", "\t")) and doc.body[last + 1].strip():
                last += 1
            doc.body[last] = doc.body[last].rstrip().rstrip(",") + f", {text}"
    else:
        want = text.lower()
        hits = []
        for j in range(start + 1, end):
            if not doc.body[j].strip() or re.match(r"^\s*-\s+Coin:", doc.body[j]):
                continue
            _, entries, _ = _split_entries(doc.body[j])
            for k, e in enumerate(entries):
                score, kind = _score(e, want)
                if score:
                    hits.append((score, j, k, kind, e))
        if not hits:
            raise InventoryError(f"{c.name} has no {text!r} in ## Inventory")
        best = max(h[0] for h in hits)
        top = [h for h in hits if h[0] == best]
        if len(top) > 1:
            raise InventoryError(f"item {text!r} is ambiguous: " + "; ".join(h[4] for h in top))
        score, j, k, kind, _ = top[0]
        prefix, entries, trailing = _split_entries(doc.body[j])
        # only an exact/plural match counts down (`2 daggers`); a looser match such
        # as `-silk` on `50 ft silk rope` takes the whole entry
        left = _decrement(entries[k], kind) if score == 3 else None
        if left is None:
            del entries[k]
        else:
            entries[k] = left
        new = prefix + ", ".join(entries) + ("," if trailing and entries else "")
        doc.body[j] = new.rstrip()
    doc.save()
    from lib import magic   # an unidentified item's `(GM: true name)` stays out of public lines (Phase 15)
    body = f"item {c.name} {sign}{magic.public(text)}" + (f" ({reason})" if reason else "")
    journal.log_delta(body)
    if magic.has_gm(text):
        journal.log_delta(f"item {c.name} {sign}{text}", gm=True)
    return f"[{body}]", {"name": c.name, "sign": sign, "item": text}


def parse_item_args(tokens):
    """['-dagger', 'taken by guard'] | ['+', 'brass key'] -> (sign, text, reason)."""
    if not tokens:
        raise InventoryError("item: want +name or -name")
    first = tokens[0]
    if first in ("+", "-"):
        if len(tokens) < 2:
            raise InventoryError("item: name the item")
        return first, tokens[1], " ".join(tokens[2:])
    if re.fullmatch(r"[+-]\d+", first) and len(tokens) >= 2:   # `+3 arrows`: a count
        return first[0], tokens[1], " ".join(tokens[2:]), int(first[1:])
    if first[:1] in "+-":
        return first[0], first[1:], " ".join(tokens[1:])
    raise InventoryError(f"item: want +name or -name, got {first!r}")


# ---------- coin ----------

def coin(name, change):
    m = re.fullmatch(r"([+-])\s*(\d+)\s*(pp|gp|ep|sp|cp)", change.strip().lower())
    if not m:
        raise InventoryError(f"coin: want e.g. -5gp or +12sp, got {change!r}")
    sign, n, denom = m.group(1), int(m.group(2)), m.group(3)
    c = creature(name)
    doc, (start, end) = _inventory(c)
    line_i = next((j for j in range(start + 1, end) if re.match(r"^\s*-\s+Coin:", doc.body[j])), None)
    if line_i is None:
        line_i = next((j for j in range(start + 1, end)
                       if re.search(r"\b\d+\s*(pp|gp|ep|sp|cp)\b", doc.body[j])), None)
    delta = n if sign == "+" else -n
    old = 0
    if line_i is None:
        if delta < 0:
            raise InventoryError(f"{c.name} has no {denom}")
        doc.append_line("## Inventory", f"- Coin: {n} {denom}")
    else:
        line = doc.body[line_i]
        cm = re.search(rf"\b(\d+)\s*{denom}\b", line)
        if cm:
            old = int(cm.group(1))
            if old + delta < 0:
                raise InventoryError(f"{c.name} has {old} {denom}, can't pay {n} {denom}")
            doc.body[line_i] = line[:cm.start(1)] + str(old + delta) + line[cm.end(1):]
        else:
            if delta < 0:
                raise InventoryError(f"{c.name} has no {denom}")
            cl = re.match(r"^(\s*-\s+Coin:\s*)(.*)$", line)
            if cl:
                doc.body[line_i] = (f"{cl.group(1)}{n} {denom}, {cl.group(2)}" if cl.group(2)
                                    else f"{cl.group(1)}{n} {denom}")
            else:
                doc.body[line_i] = line.rstrip() + f", {n} {denom}"
    doc.save()
    body = f"coin {c.name} {old}→{old + delta} {denom}"
    journal.log_delta(body)
    return f"[{body}]", {"name": c.name, "denom": denom, "from": old, "to": old + delta}


def parse_cost(text):
    """`2 gp`, `1 sp`, `2 gp/day`, `0` -> copper pieces (None when unreadable)."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(pp|gp|ep|sp|cp)?\b", str(text or "").lower())
    if not m:
        return None
    rate = {"pp": 1000, "gp": 100, "ep": 50, "sp": 10, "cp": 1}[m.group(2) or "gp"]
    return int(round(float(m.group(1)) * rate))


def fmt_cost(cp):
    if cp % 100 == 0:
        return f"{cp // 100} gp"
    if cp % 10 == 0:
        return f"{cp // 10} sp"
    return f"{cp} cp"


def purse(doc):
    """Copper's worth of the coin in a file's `## Inventory` (the `Coin:` line, else the
    first line naming coins)."""
    span = doc.section("Inventory") if doc is not None else None
    if span is None:
        return 0
    lines = [doc.body[j] for j in range(span[0] + 1, span[1])]
    line = next((x for x in lines if re.match(r"^\s*-\s+Coin:", x)), None) or \
        next((x for x in lines if re.search(r"\b\d+\s*(pp|gp|ep|sp|cp)\b", x)), "")
    return sum(parse_cost(f"{n} {d}") for n, d in re.findall(r"\b(\d+)\s*(pp|gp|ep|sp|cp)\b", line.lower()))


def pay(name, cp):
    """Take `cp` copper's worth from a PC's coin (Phase 15: lifestyle, materials, wages):
    in one denomination when the purse has it, else whole gold with the change back in
    silver and copper. -> [lines]; raises InventoryError when they can't pay."""
    if cp <= 0:
        return []
    exact = fmt_cost(cp).replace(" ", "")
    try:
        return [coin(name, "-" + exact)[0]]
    except InventoryError:
        pass
    gold = -(-cp // 100)
    lines = [coin(name, f"-{gold}gp")[0]]
    change = gold * 100 - cp
    if change // 10:
        lines.append(coin(name, f"+{change // 10}sp")[0])
    if change % 10:
        lines.append(coin(name, f"+{change % 10}cp")[0])
    return lines


# ---------- resources ----------

def res(name, sign, resource, n=1):
    """sign '-' spend / '+' restore (clamped to max) / '=' set."""
    c = creature(name)
    if c.doc is None:
        raise InventoryError(f"{c.name} has no file")
    table = c.doc.table("Resources")
    if table is None or not table.rows:
        raise InventoryError(f"{c.name} has no ## Resources table")
    want = resource.strip().lower()
    names = [r.get("resource", "").lower() for r in table.rows]
    idx = [i for i, x in enumerate(names) if x == want] or [i for i, x in enumerate(names) if x.startswith(want)]
    if not idx:
        raise InventoryError(f"{c.name} has no resource {resource!r} ({', '.join(names)})")
    if len(idx) > 1:
        raise InventoryError(f"resource {resource!r} is ambiguous: {', '.join(names[i] for i in idx)}")
    i = idx[0]
    row = table.rows[i]
    try:
        cur = int(row.get("current", "0"))
    except ValueError:
        raise InventoryError(f"{row['resource']}: current {row.get('current')!r} is not a number") from None
    mx = int(row["max"]) if row.get("max", "").strip().isdigit() else None
    if sign == "-":
        new = cur - n
        if new < 0:
            raise InventoryError(f"{c.name} has {cur} {row['resource']} left, can't spend {n}")
    elif sign == "+":
        new = cur + n if mx is None else min(mx, cur + n)
    elif sign == "=":
        new = n
    else:
        raise InventoryError(f"res: bad sign {sign!r}")
    table.set(i, "current", new)
    c.doc.save()
    body = f"res {c.name} {row['resource']} {cur}→{new}" + (f"/{mx}" if mx is not None else "")
    journal.log_delta(body)
    return f"[{body}]", {"name": c.name, "resource": row["resource"], "from": cur, "to": new, "max": mx}


def parse_res_args(tokens):
    """['-spell slot 1'] | ['-', 'arrows', '3'] | ['+arrows', '2'] -> (sign, name, n)."""
    if not tokens:
        raise InventoryError("res: want -name, +name or =name [N]")
    if tokens[0] in ("+", "-", "="):
        sign, rest = tokens[0], tokens[1:]
    elif tokens[0][:1] in "+-=":
        sign, rest = tokens[0][0], [tokens[0][1:]] + tokens[1:]
    else:
        raise InventoryError(f"res: want -name, +name or =name, got {tokens[0]!r}")
    n = 1
    if len(rest) > 1 and re.fullmatch(r"\d+", rest[-1]):
        n = int(rest[-1])
        rest = rest[:-1]
    name = " ".join(rest).strip()
    if not name:
        raise InventoryError("res: name the resource")
    return sign, name, n


# ---------- CLI ----------

def cmd_attitude(ctx):
    emit(ctx, attitude(ctx.args.target, ctx.args.value, ctx.args.reason or ""))


def cmd_item(ctx):
    parsed = parse_item_args(ctx.args.change)
    emit(ctx, item(ctx.args.target, *parsed))


def cmd_coin(ctx):
    emit(ctx, coin(ctx.args.target, "".join(ctx.args.change)))


def cmd_res(ctx):
    sign, name, n = parse_res_args(ctx.args.change)
    emit(ctx, res(ctx.args.target, sign, name, n))


def register(sub, g):
    R = "..."  # noqa: N806  (argparse.REMAINDER: `-dagger` must not parse as an option)
    p = sub.add_parser("attitude", parents=[g], help='attitude NAME VALUE "reason"')
    p.add_argument("target"); p.add_argument("value"); p.add_argument("reason", nargs="?")
    p.set_defaults(func=cmd_attitude)

    p = sub.add_parser("item", parents=[g], help='item NAME -thing "reason" | + "thing" | +3 arrows')
    p.add_argument("target"); p.add_argument("change", nargs=R)
    p.set_defaults(func=cmd_item)

    p = sub.add_parser("coin", parents=[g], help="coin NAME -5gp")
    p.add_argument("target"); p.add_argument("change", nargs=R)
    p.set_defaults(func=cmd_coin)

    p = sub.add_parser("res", parents=[g], help='res NAME -"spell slot 1" [N]')
    p.add_argument("target"); p.add_argument("change", nargs=R)
    p.set_defaults(func=cmd_res)
