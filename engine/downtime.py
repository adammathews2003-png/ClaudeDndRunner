"""Downtime between adventures (docs/design/02 → Table mechanics → Phase 15 → Downtime;
04 → PC file `## Downtime`; 06 → Table mechanics → Phase 15; plan.md Phase 15 item 5).

    downtime Kira craft "chain shirt" 10d [--lifestyle modest] [--value "50 gp"] [--no-clock]
    downtime Kael train "thieves' tools" 20d
    downtime Kira research "the Red Ledger" 5d [--goal 10d]
    downtime status

`downtime: off | light | full` (default light). light: craft, train, research, recuperate,
work; full: also any activity with a campaign table `tables/downtime-<activity>.md`
(crime, pit-fight …; campaign-supplied, never shipped), rolled once per call for its
complication. Progress lives in the PC's `## Downtime` table (`| activity | progress |
goal | cost/day | notes |`):
- craft: 5 gp of market value per day toward the item's price (the SRD equipment cost,
  else `--value`); materials are half the price, paid when the work starts. Finished →
  the item goes into the pack and the row is removed.
- train: 250 days at 1 gp a day (a language or tool proficiency); finished → a Features line.
- research, recuperate, work: days counted toward `--goal` (if any); the GM narrates the
  result (work pays a modest lifestyle: no lifestyle cost while working).
Lifestyle per day: wretched 0, squalid 1 sp, poor 2 sp, modest 1 gp, comfortable 2 gp,
wealthy 4 gp, aristocratic 10 gp. **Coin moves only under `upkeep: on`** (the table's
bookkeeping preference; default off): lifestyle, materials and training fees are then
paid from the PC's coin; with it off the line says what it would cost and nothing is
taken. The clock then advances by the days (the whole party; `--no-clock` for all but
the longest when several PCs spend downtime at once), with the usual `[TIME]` packet.
"""
import re

from lib import campaign, chargen, dice, journal, md
from lib.errors import ToolError
import inventory
import mutations

COLS = ["activity", "progress", "goal", "cost/day", "notes"]
LIGHT = ("craft", "train", "research", "recuperate", "work")
LIFESTYLE = {"wretched": 0, "squalid": 10, "poor": 20, "modest": 100, "comfortable": 200,
             "wealthy": 400, "aristocratic": 1000}   # copper per day
CRAFT_PER_DAY = 500      # 5 gp of market value
TRAIN_DAYS, TRAIN_FEE = 250, 100


class DowntimeError(ToolError):
    pass


def setting():
    return str(campaign.settings().get("downtime", campaign.SETTINGS["downtime"])).strip().lower()


def upkeep():
    return str(campaign.settings().get("upkeep", "off")).strip().lower() == "on"


def _days(text):
    m = re.fullmatch(r"\s*(\d+)\s*d?\s*", str(text))
    if not m or int(m.group(1)) < 1:
        raise DowntimeError(f"downtime: days are N or Nd, got {text!r}")
    return int(m.group(1))


def _rows(doc):
    t = doc.table("Downtime")
    return [dict(r) for r in (t.rows if t else []) if r.get("activity", "").strip()]


def _set_rows(doc, rows):
    lines = ["| " + " | ".join(COLS) + " |", "|" + "|".join("-" * (len(c) + 2) for c in COLS) + "|"]
    lines += ["| " + " | ".join(str(r.get(c, "")) for c in COLS) + " |" for r in rows]
    span = doc.section("Downtime")
    if span is None:
        at = doc.section("Background")
        block = ["## Downtime"] + lines + [""]
        if at is not None:
            doc.body[at[0]:at[0]] = block
        else:
            if doc.body and doc.body[-1].strip():
                doc.body.append("")
            doc.body += block[:-1]
        return
    t = doc.table("Downtime")
    if t is not None:
        doc.body[t.start:t.start + 2 + len(t.rows)] = lines
    elif rows:
        doc.body[span[0] + 1:span[0] + 1] = lines


def _cp(text):
    return inventory.parse_cost(text) or 0


def _price(item, value):
    if value:
        cp = inventory.parse_cost(value)
        if not cp:
            raise DowntimeError(f"--value wants e.g. \"50 gp\", got {value!r}")
        return cp
    try:
        rec = chargen.equipment_record(item)
    except Exception:  # noqa: BLE001 — no SRD data
        rec = None
    cost = (rec or {}).get("cost") or {}
    if not cost.get("quantity"):
        raise DowntimeError(f"craft: {item!r} has no SRD price — give it with --value \"N gp\"")
    return inventory.parse_cost(f"{cost['quantity']} {cost.get('unit', 'gp')}")


def _charge(name, cp, what, lines):
    """Pay `cp` for `what` under upkeep: on; else say what it would have cost. (Called
    after the PC file is saved: paying writes the file again.)"""
    if not cp:
        return
    if upkeep():
        lines.append(f"[{what}: {inventory.fmt_cost(cp)}]")
        lines += inventory.pay(name, cp)
    else:
        lines.append(f"[{what} {inventory.fmt_cost(cp)} — not charged (upkeep: off)]")


def downtime(name, activity, subject, days, lifestyle=None, value=None, goal=None, clock=True, roller=None):
    mode = setting()
    if mode == "off":
        raise DowntimeError("downtime: off (campaign setting)")
    activity = activity.strip().lower()
    if activity not in LIGHT:
        table = campaign.root() / "tables" / f"downtime-{activity}.md"
        if mode != "full":
            raise DowntimeError(f"downtime: {' | '.join(LIGHT)} (downtime: full adds campaign tables)")
        if not table.exists():
            raise DowntimeError(f"downtime {activity}: no campaign table tables/downtime-{activity}.md")
    n = _days(days)
    life = None
    if lifestyle:
        life = lifestyle.strip().lower()
        if life not in LIFESTYLE:
            raise DowntimeError(f"--lifestyle: {' | '.join(LIFESTYLE)}")
    c = mutations.creature(name)
    if not c.is_pc or c.doc is None:
        raise DowntimeError(f"downtime: {c.name} is not a PC")
    who = c.name.split()[0]
    doc = md.load(c.doc.path)
    rows = _rows(doc)
    label = f"{activity} {subject}".strip()
    row = next((r for r in rows if r["activity"].lower() == label.lower()), None)
    lines, money = [], []
    fresh = row is None
    if fresh:
        row = {"activity": label, "progress": "0", "goal": "", "cost/day": "", "notes": ""}
        rows.append(row)
    if life:
        row["cost/day"] = f"{inventory.fmt_cost(LIFESTYLE[life])} ({life})" if LIFESTYLE[life] else f"0 ({life})"
    done = False
    if activity == "craft":
        if not subject:
            raise DowntimeError('craft: name the item (downtime Kira craft "chain shirt" 10d)')
        price = _price(subject, value) if fresh or not row["goal"] else _cp(row["goal"])
        row["goal"] = inventory.fmt_cost(price)
        before = _cp(row["progress"])
        after = min(price, before + n * CRAFT_PER_DAY)
        row["progress"] = inventory.fmt_cost(after)
        prog = f"progress {inventory.fmt_cost(before)}→{inventory.fmt_cost(after)} of {row['goal']}"
        if fresh:
            money.append((price // 2, "materials (half the price)"))
        done = after >= price
    elif activity == "train":
        before = int(re.sub(r"\D", "", row["progress"]) or 0)
        after = min(TRAIN_DAYS, before + n)
        row["progress"], row["goal"] = f"{after} days", f"{TRAIN_DAYS} days"
        prog = f"progress {before}→{after}/{TRAIN_DAYS} days"
        money.append(((after - before) * TRAIN_FEE, f"training fees ({after - before} days × 1 gp)"))
        done = after >= TRAIN_DAYS
    else:
        before = int(re.sub(r"\D", "", row["progress"]) or 0)
        after = before + n
        if goal:
            row["goal"] = f"{_days(goal)} days"
        row["progress"] = f"{after} days"
        target = int(re.sub(r"\D", "", row["goal"]) or 0)
        prog = f"progress {before}→{after}" + (f"/{target}" if target else "") + " days"
        done = bool(target) and after >= target
    if life and activity != "work":
        money.append((LIFESTYLE[life] * n, f"lifestyle {life} × {n} days"))
    owed = sum(cp for cp, _ in money)
    if upkeep() and owed > inventory.purse(doc):
        raise DowntimeError(f"{who} can't pay {inventory.fmt_cost(owed)} "
                            f"(has {inventory.fmt_cost(inventory.purse(doc))}): a cheaper --lifestyle, or fewer days")
    finished = ""
    if done:
        rows = [r for r in rows if r is not row]
        if activity == "craft":
            finished = f" · done: {subject} added to the pack"
        elif activity == "train":
            doc.append_line("Features & abilities", f"- **Trained:** {subject} (downtime, {TRAIN_DAYS} days)")
            finished = f" · done: {subject} learned"
        else:
            finished = " · done (the GM tells what came of it)"
    _set_rows(doc, rows)
    doc.save()
    if done and activity == "craft":
        inventory.item(c.name, "+", subject, "crafted")
    body = f"downtime {who} {label} · {n} day{'s' if n != 1 else ''} · {prog}" + finished
    journal.log_delta(body)
    lines.append(f"[{body}]")
    for cp, what in money:
        _charge(c.name, cp, what, lines)
    if mode == "full":
        table = campaign.root() / "tables" / f"downtime-{activity}.md"
        if table.exists():
            res = (roller or dice.Roller()).roll_table(table, f"downtime-{activity}", secret=True)
            journal.log_delta(f"downtime complication {who}: {res.body}", gm=True)
            lines.append(f"(GM) complication: {res.body}")
    if clock:
        import clock as clk
        out, _ = clk.advance(f"+{n}d", roller=roller)
        lines += out
    return lines


def status():
    out = []
    for d in campaign.pcs():
        for r in _rows(d):
            out.append(f"{str(d.front.get('name')).split()[0]}: {r['activity']} {r['progress']}"
                       + (f"/{r['goal']}" if r.get("goal") else "") + (f" · {r['cost/day']}/day" if r.get("cost/day") else ""))
    return ["[downtime] " + (" · ".join(out) if out else "nothing under way") + f" · downtime: {setting()}"]


def cmd_downtime(ctx):
    a = ctx.args
    if a.pc == "status":
        lines = status()
    else:
        if a.activity is None or a.rest is None or not a.rest:
            raise DowntimeError('downtime PC ACTIVITY ["subject"] DAYS (or downtime status)')
        rest = list(a.rest)
        days = rest.pop()
        lines = downtime(a.pc, a.activity, " ".join(rest), days, a.lifestyle, a.value, a.goal,
                         not a.no_clock, ctx.roller)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("downtime", parents=[g], help='downtime PC craft "chain shirt" 10d [--lifestyle modest] | status')
    p.add_argument("pc")
    p.add_argument("activity", nargs="?")
    p.add_argument("rest", nargs="*", help='["subject"] DAYS')
    p.add_argument("--lifestyle", help=" | ".join(LIFESTYLE))
    p.add_argument("--value", help='craft: the market value when the SRD has no price ("50 gp")')
    p.add_argument("--goal", help="research/recuperate/work: days needed")
    p.add_argument("--no-clock", action="store_true", help="don't move the clock (several PCs at once)")
    p.set_defaults(func=cmd_downtime)
