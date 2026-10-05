"""`gm.py loot roll <table>` and `gm.py shop <merchant> [--buy <item> | --sell <item>]
[--pc <PC>] [--price "25 gp"] [--restock]` (docs/design/06 → loot/shop; 07 → Items, loot and
merchants; 04 → Loot and stock; plan.md Phase 11 item 8).

`loot roll` rolls a `tables/loot-*.md` table, rolls any coin dice in the result
(`2d6×10 gp`) and prints `item … +` / `coin … +` **suggestions**; it never changes an
inventory by itself.

`shop` reads a merchant NPC's `## Stock` table (`| item | price | stock | restock |
random |`). `--buy`/`--sell` move coin and items through the `coin`/`item` mutations
(selling pays half); a row without a price uses the DMG rarity band of the `(rarity)`
in its name. `--restock` re-rolls the rows whose `random` column names a stock table
(`clock advance` restocks `daily`/`weekly` merchants on day boundaries; `loop reset`
restocks `loop` merchants). `restock_all(kinds)` is the Python API for those.
"""
import re

from lib import campaign, dice, journal, md
from lib.errors import ToolError
import inventory

# DMG magic item value bands (gp); a single price per band, the band's midpoint-ish
RARITY_PRICE = {"common": 75, "uncommon": 300, "rare": 2750, "very rare": 27500, "legendary": 75000}
_COIN = re.compile(r"(\d+)\s*(cp|sp|ep|gp|pp)\b", re.I)
_RARITY = re.compile(r"\((common|uncommon|rare|very rare|legendary)\)", re.I)


class LootError(ToolError):
    pass


def _roll_coin_dice(text, roller):
    """'2d6×10 gp' → ('70 gp' substituted, [(70, 'gp')])."""
    found = []

    def sub(m):
        res = roller.roll(m.group(1))
        total = res.total * (int(m.group(2)) if m.group(2) else 1)
        found.append((total, m.group(3).lower()))
        return f"{total} {m.group(3)}"
    out = re.sub(r"(\d+d\d+)\s*(?:[×x]\s*(\d+))?\s*(cp|sp|ep|gp|pp)\b", sub, text, flags=re.I)
    return out, found


def loot_roll(table, roller):
    slug = table if table.startswith(("loot-", "stock-")) else f"loot-{table}"
    path = campaign.path("tables", slug)
    res = roller.roll_table(path, slug)
    raw = res.body.split("→", 1)[1].strip()
    text, coins = _roll_coin_dice(raw, roller)
    lines = [f"[LOOT {slug}: {res.body.split('→')[0].strip()} → {text}]"]
    sugg = [f"coin <PC> +{n}{d}" for n, d in coins]
    for part in re.split(r"\s+and\s+(?![^(]*\))", raw):   # "and" outside parentheses only
        part = part.strip().strip(",;")
        if not part or re.match(r"^\d+d\d+", part):        # a rolled coin amount
            continue
        sugg.append(f'item <PC> + "{part}"')
    if sugg:
        lines.append("[suggest (not applied): " + " · ".join(sugg) + "]")
    journal.log_delta(f"loot roll {slug}: {text}", gm=True)
    return lines


# ---------- merchants ----------

def merchant_doc(name):
    m = campaign.resolve(name)
    if m.doc is None or m.is_pc:
        raise LootError(f"shop: {name!r} is not an NPC with a file")
    doc = m.doc
    if doc.table("Stock") is None:
        raise LootError(f"shop: {m.name} has no ## Stock table")
    return doc


def price_gp(row):
    """Price in gp (float) from the row, else the rarity band; None if neither."""
    m = _COIN.search(row.get("price", ""))
    if m:
        n, d = int(m.group(1)), m.group(2).lower()
        return n * {"cp": 0.01, "sp": 0.1, "ep": 0.5, "gp": 1, "pp": 10}[d]
    r = _RARITY.search(row.get("item", ""))
    if r:
        return RARITY_PRICE[r.group(1).lower()]
    return None


def _coin_text(gp):
    """A coin change in the cheapest whole denomination: 25 → '25gp', 0.5 → '5sp'."""
    if gp >= 1 and float(gp).is_integer():
        return f"{int(gp)}gp"
    sp = gp * 10
    if float(round(sp, 6)).is_integer():
        return f"{int(round(sp))}sp"
    return f"{int(round(gp * 100))}cp"


def _find(table, item):
    want = item.lower().strip()
    rows = table.rows
    for i, r in enumerate(rows):
        if r.get("item", "").lower() == want:
            return i
    hits = [i for i, r in enumerate(rows) if r.get("item", "").lower().startswith(want)] or \
           [i for i, r in enumerate(rows) if want in r.get("item", "").lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise LootError(f"shop: no {item!r} in stock")
    raise LootError(f"shop: {item!r} is ambiguous: " + ", ".join(rows[i]["item"] for i in hits))


def restock(doc, roller, kinds=None):
    """Re-roll the random rows (optionally only those whose `restock` is in `kinds`)."""
    t = doc.table("Stock")
    n = 0
    for i, r in enumerate(t.rows):
        if not r.get("random", "").strip():
            continue
        if kinds and r.get("restock", "").strip().lower() not in kinds:
            continue
        slug = r["random"].strip()
        res = roller.roll_table(campaign.path("tables", slug), slug)
        text = res.body.split("→", 1)[1].strip()
        m = re.match(r"^(.*?),\s*(\d+\s*(?:cp|sp|ep|gp|pp))\b", text, re.I)
        item, price = (m.group(1).strip(), m.group(2)) if m else (re.split(r";", text)[0].strip(), "—")
        t.set(i, "item", item.replace("|", "/"))
        t.set(i, "price", price)
        t.set(i, "stock", "1")
        n += 1
    if n:
        doc.save()
    return n


def restock_all(kinds, roller=None):
    """Restock every merchant whose random rows recover by one of `kinds` (daily |
    weekly | loop). Returns the merchants' first names."""
    roller = roller or dice.Roller()
    out = []
    for doc in campaign.npcs():
        if doc.table("Stock") is None:
            continue
        if restock(doc, roller, kinds):
            out.append(str(doc.front.get("name")).split()[0])
    return out


def shop(merchant, buy=None, sell=None, pc=None, price=None, do_restock=False, roller=None):
    doc = merchant_doc(merchant)
    who = str(doc.front.get("name")).split()[0]
    lines = []
    if do_restock:
        n = restock(doc, roller or dice.Roller())
        journal.log_delta(f"shop {who} restocked ({n} random rows)", gm=True)
        doc = merchant_doc(merchant)
        lines.append(f"[shop {who}: restocked {n} rows]")
    t = doc.table("Stock")
    if buy or sell:
        if not pc:
            raise LootError("shop: say who with --pc <PC>")
        if buy:
            i = _find(t, buy)
            row = t.rows[i]
            if row.get("random") and row.get("item", "").startswith("("):
                raise LootError(f"shop: that row isn't stocked yet (shop {merchant} --restock)")
            stock = row.get("stock", "").strip()
            if stock.isdigit() and int(stock) <= 0:
                raise LootError(f"shop: {row['item']} is sold out")
            gp = price_gp({"price": price or row.get("price", ""), "item": row.get("item", "")})
            if gp is None:
                raise LootError(f"shop: {row['item']} has no price and no rarity — give --price")
            lines.append(inventory.coin(pc, "-" + _coin_text(gp))[0])
            lines.append(inventory.item(pc, "+", row["item"], f"bought from {who}")[0])
            doc = merchant_doc(merchant)
            t = doc.table("Stock")
            if stock.isdigit():
                t.set(i, "stock", str(int(stock) - 1))
                doc.save()
            journal.log_delta(f"shop {who}: {pc} bought {row['item']} ({_coin_text(gp)})")
        else:
            row = None
            try:
                row = t.rows[_find(t, sell)]
            except LootError:
                pass
            gp = price_gp({"price": price or (row or {}).get("price", ""), "item": (row or {}).get("item", sell)})
            if gp is None:
                raise LootError(f"shop: what is {sell!r} worth? give --price \"N gp\" (it sells for half)")
            half = gp / 2
            lines.append(inventory.item(pc, "-", sell, f"sold to {who}")[0])
            lines.append(inventory.coin(pc, "+" + _coin_text(half))[0])
            journal.log_delta(f"shop {who}: {pc} sold {sell} ({_coin_text(half)})")
        return lines
    rows = []
    for r in t.rows:
        if r.get("random") and r.get("item", "").startswith("("):
            rows.append(f"{r['item']} (unrolled — --restock)")
            continue
        stock = r.get("stock", "").strip()
        if stock == "0":
            continue
        p = r.get("price", "").strip()
        if p in ("", "—", "-"):
            gp = price_gp(r)
            p = f"~{_coin_text(gp)}" if gp else "ask"
        rows.append(f"{r['item']} — {p}" + (f" ×{stock}" if stock.isdigit() and int(stock) > 1 else ""))
    lines.append(f"[SHOP {who}] " + " · ".join(rows))
    return lines


def cmd_loot(ctx):
    for line in loot_roll(ctx.args.table, ctx.roller):
        ctx.emit(line)


def cmd_shop(ctx):
    a = ctx.args
    for line in shop(" ".join(a.merchant), a.buy, a.sell, a.pc, a.price, a.restock, ctx.roller):
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("loot", parents=[g], help="loot roll <table> (suggests, never applies)")
    p.add_argument("action", choices=["roll"])
    p.add_argument("table")
    p.set_defaults(func=cmd_loot)
    p = sub.add_parser("shop", parents=[g], help="shop <merchant> [--buy x|--sell x] --pc PC [--restock]")
    p.add_argument("merchant", nargs="+")
    p.add_argument("--buy")
    p.add_argument("--sell")
    p.add_argument("--pc")
    p.add_argument("--price")
    p.add_argument("--restock", action="store_true")
    p.set_defaults(func=cmd_shop)
