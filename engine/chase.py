"""Chases (docs/design/02 → Table mechanics → Phase 14 → Chases; 04 → Scene state added
(`## Chase`); 06 → Table mechanics → Phase 14; plan.md Phase 14 item 5).

    chase start --quarry Veskar [--pursuers Kael,Kira] [--lead 60] [--env urban|wild]
    chase next [--no-dash] [--lose N]      the participant who is up takes their turn
    chase dash <who>                       an extra Dash (a bonus action, e.g. Cunning Action)
    chase end [caught|escaped|gave-up]

`chases: dmg` (default). The `## Combat` heading becomes `## Chase — round N · up: X ·
env: urban` with a `| name | role | pos ft | speed | dashes | exh | notes |` table (a
chase and a fight never overlap); `chase end` puts `## Combat (not in combat)` back.
Quarry start at `--lead` ft (default 60), pursuers at 0; the order is the table's (quarry
first, then pursuers as named). Speeds come from the files (exhaustion applied,
lib/turnstate.speed_of); Dashes `used/free` with 3 + CON modifier free.

`chase next` moves the participant who is up by their speed, twice that when they Dash
(the default; `--no-dash` for a plain move; `--lose N` for ground lost to a
complication). A Dash past the free ones is a DC 10 CON save or a level of exhaustion:
the tool asks a player for it and rolls it for an NPC (a failure applies `exhaust +1`).
Then the next participant is up and the tool rolls d20 on the environment's
complication table (`tables/chase-<env>.md` from the campaign, else the engine's in
engine/templates/tables/): 1–10 is a complication for them. After a quarry's turn, if it
is out of the pursuers' sight (the gap is beyond their sight — bright: 120 ft urban,
300 ft wild; dim: half; dark: their best darkvision — or a `los` complication hid it),
it tries to escape: Stealth against the pursuers' best passive Perception (the tool
rolls for an NPC; a PC quarry is asked). A pursuer reaching the quarry ends it
`[caught: start combat or grapple]`; a won escape ends it `[escaped]`. Rounds are 6 s:
`chase end` moves the clock by the rounds run (rounded up to the minute; while split,
that is the active group's clock, as for a fight). `chases: narrative` plays a chase as
a contest or two, as before.
"""
import math
import re
from pathlib import Path

from lib import campaign, creatures, dice, journal, md, resolve, turnstate
from lib.errors import ToolError
import tempo

COLS = ["name", "role", "pos ft", "speed", "dashes", "exh", "notes"]
_HEAD = re.compile(r"^Chase\s*[—-]\s*round\s*(\d+)\s*·\s*up:\s*(.+?)\s*·\s*env:\s*(\w+)\s*$", re.I)
SIGHT = {"urban": 120, "wild": 300}
TEMPLATES = Path(__file__).resolve().parent / "templates" / "tables"


class ChaseError(ToolError):
    pass


def _setting(key):
    return str(campaign.settings().get(key, campaign.SETTINGS[key])).strip().lower()


def _heading(doc, word):
    for i, lvl, text in doc.headings():
        if lvl == 2 and text.lower().startswith(word):
            return i, text
    return None, None


def status(state=None):
    """(round, up, env) while a chase runs, else None."""
    state = state or campaign.load_state()
    _, text = _heading(state, "chase")
    if text is None:
        return None
    m = _HEAD.match(text)
    if not m:
        raise ChaseError("can't read the ## Chase heading")
    return int(m.group(1)), m.group(2).strip(), m.group(3).lower()


def _table(state):
    t = state.table("Chase")
    if t is None:
        raise ChaseError("chase: no chase running (gm.py chase start)")
    return t


def _write(state, rnd, up, env, rows=None):
    i, _ = _heading(state, "chase")
    if i is None:
        i, _ = _heading(state, "combat")
    state.body[i] = f"## Chase — round {rnd} · up: {up} · env: {env}"
    if rows is not None:
        lines = ["| " + " | ".join(COLS) + " |", "|" + "|".join("---" for _ in COLS) + "|"]
        lines += ["| " + " | ".join(str(r.get(c, "")) for c in COLS) + " |" for r in rows]
        tempo.set_section(state, state.body[i][3:], lines)


def _con_mod(c):
    try:
        return c.mod("con")
    except ToolError:
        return 0


def _first(c):
    return c.name.split()[0] if c.is_pc else c.name


# ---------- start ----------

def start(quarry, pursuers=None, lead=60, env="urban"):
    if _setting("chases") == "narrative":
        return ["[chase: chases: narrative — play it as a contest or two (gm.py contest …)]"]
    state = campaign.load_state()
    if tempo.in_combat(state):
        raise ChaseError("chase start: combat is running (combat end first)")
    if status(state) is not None:
        raise ChaseError("chase start: a chase is already running (chase next / chase end)")
    if env not in SIGHT:
        raise ChaseError("--env urban | wild")
    q_names = [x.strip() for x in quarry.split(",") if x.strip()]
    if pursuers:
        p_names = [x.strip() for x in pursuers.split(",") if x.strip()]
    else:
        p_names = [str(d.front.get("name")) for d in campaign.scene_pcs()]
    rows = []
    for role, names in (("quarry", q_names), ("pursuer", p_names)):
        for n in names:
            c = creatures.get(n, state)
            free = max(0, 3 + _con_mod(c))
            rows.append({"name": _first(c), "role": role, "pos ft": lead if role == "quarry" else 0,
                         "speed": turnstate.speed_of(c), "dashes": f"0/{free}", "exh": c.exhaustion(),
                         "notes": ""})
    if not any(r["role"] == "quarry" for r in rows) or not any(r["role"] == "pursuer" for r in rows):
        raise ChaseError("chase start: it takes a quarry and at least one pursuer")
    _write(state, 1, rows[0]["name"], env, rows)
    state.save()
    body = (f"chase start · quarry {', '.join(r['name'] for r in rows if r['role'] == 'quarry')} · pursuers "
            f"{', '.join(r['name'] for r in rows if r['role'] == 'pursuer')} · lead {lead} ft · env {env}")
    journal.log_delta(body)
    out = [f"[{body}]"]
    out += [f"  {r['name']} ({r['role']}) at {r['pos ft']} ft · speed {r['speed']} · Dashes free {r['dashes'][2:]}"
            for r in rows]
    out.append(f"[{rows[0]['name']} is up: gm.py chase next (Dashes by default; --no-dash, --lose N)]")
    return out


# ---------- turns ----------

def _dash(state, t, i, rng):
    """Spend one Dash for row i (writes the cell). -> lines (the CON save past the free ones)."""
    used, free = (int(x) for x in t.rows[i]["dashes"].split("/"))
    used += 1
    t.set(i, "dashes", f"{used}/{free}")
    if used <= free:
        return []
    name = t.rows[i]["name"]
    c = creatures.get(name, state)
    if c.is_pc:
        return [f"[{name} dashes past their free Dashes ({used}/{free}): CON save DC 10 — ask for the d20 "
                f"(gm.py save {name} con 10 · fail → gm.py exhaust {name} +1 \"chase\")]"]
    state.save()
    import roll
    line, data = roll.saving_throw(name, "con", 10, roller=rng)
    out = [f"[{name} dashes past their free Dashes ({used}/{free}): CON save DC 10]", line]
    if data["outcome"] != "SUCCESS":
        import conditions_ext
        out += conditions_ext.exhaust(name, "+1", "chase")
    return out


def _refresh(state, t, i):
    """Speed and exhaustion of row i from the creature (exhaustion may have changed)."""
    try:
        c = creatures.get(t.rows[i]["name"], state)
    except (ToolError, campaign.CampaignError):
        return
    t.set(i, "exh", c.exhaustion())
    t.set(i, "speed", turnstate.speed_of(c))


def _notes(row):
    return [x.strip() for x in (row.get("notes") or "").split(";") if x.strip()]


def _sight(state, t, env):
    light = str(state.front.get("light") or "bright").lower()
    if light == "bright":
        return SIGHT[env]
    if light == "dim":
        return SIGHT[env] // 2
    best = 0
    for r in t.rows:
        if r["role"] != "pursuer":
            continue
        try:
            c = creatures.get(r["name"], state)
        except (ToolError, campaign.CampaignError):
            continue
        for s in (c.front.get("senses") or []):
            m = re.match(r"darkvision\s*(\d+)", str(s), re.I)
            if m:
                best = max(best, int(m.group(1)))
    return best


def _best_passive(state, t):
    best, who = None, None
    for r in t.rows:
        if r["role"] != "pursuer":
            continue
        try:
            p = creatures.get(r["name"], state).passive("perception")
        except (ToolError, campaign.CampaignError):
            continue
        if best is None or p > best:
            best, who = p, r["name"]
    return best, who


def _complication(env, rng):
    """(d20, result, effect) from the campaign's tables/chase-<env>.md, else the engine's."""
    p = campaign.root() / "tables" / f"chase-{env}.md"
    if not p.exists():
        p = TEMPLATES / f"chase-{env}.md"
    doc = md.load(p)
    t = None
    for i, line in enumerate(doc.body):
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and "roll" in cells and "result" in cells:
            t = md.Table(doc, i)
            break
    if t is None:
        raise ChaseError(f"{p.name}: no | roll | result | table")
    n = rng.die(20)
    for r in t.rows:
        lo, hi = dice._range(r.get("roll", ""), p.stem)
        if lo <= n <= hi:
            return n, r.get("result", ""), (r.get("effect") or "").strip()
    return n, "no complication", ""


def next_turn(dash=True, lose=0, roller=None):
    rng = roller or dice.Roller()
    state = campaign.load_state()
    st = status(state)
    if st is None:
        raise ChaseError("chase next: no chase running")
    rnd, up, env = st
    t = _table(state)
    i = next((k for k, r in enumerate(t.rows) if r["name"].lower() == up.lower()), None)
    if i is None:
        raise ChaseError(f"chase next: {up} is not in the Chase table")
    _refresh(state, t, i)
    row = t.rows[i]
    lines = []
    speed = int(row["speed"] or 0)
    notes = _notes(row)
    owed = sum(int(m.group(1)) for n in notes for m in [re.match(r"^-(\d+) ft$", n)] if m)
    notes = [n for n in notes if not re.match(r"^-\d+ ft$", n)]
    if dash:
        lines += _dash(state, t, i, rng)
    move = max(0, speed * (2 if dash else 1) - lose - owed)
    old = int(row["pos ft"])
    new = old + move
    t.set(i, "pos ft", new)
    t.set(i, "notes", "; ".join(notes))
    body = f"chase round {rnd} · {row['name']} {old}→{new} ft" + (f" (dash {t.rows[i]['dashes']})" if dash else "")
    journal.log_delta(body)
    lines.insert(0, f"[{body}]")
    # caught?
    quarry = [r for r in t.rows if r["role"] == "quarry"]
    lead = max(int(r["pos ft"]) for r in t.rows if r["role"] == "pursuer")
    if row["role"] == "pursuer" and any(new >= int(q["pos ft"]) for q in quarry):
        state.save()
        return lines + end("caught")
    if row["role"] == "quarry":
        gap = new - lead
        sight = _sight(state, t, env)
        hidden = "out of sight" in _notes(t.rows[i])
        if gap > sight or hidden:
            out, escaped = _escape(state, t, i, gap, sight, hidden, rng)
            lines += out
            if escaped:
                state.save()
                return lines + end("escaped")
    # the next participant is up; a complication for them
    j = (i + 1) % len(t.rows)
    if j == 0:
        rnd += 1
    nxt = t.rows[j]["name"]
    n, result, effect = _complication(env, rng)
    if n <= 10:
        lines.append(f"[complication for {nxt}: d20 {n} → {result}" + (f" ({effect})" if effect else "") + "]")
        if effect.lower() == "los" and t.rows[j]["role"] == "quarry":
            t.set(j, "notes", "; ".join(_notes(t.rows[j]) + ["out of sight"]))
        journal.log_delta(f"chase complication {nxt}: {result}")
    else:
        lines.append(f"[complication for {nxt}: d20 {n} → none]")
    _write(state, rnd, nxt, env)
    state.save()
    lines.append(f"[round {rnd} · up: {nxt} at {t.rows[j]['pos ft']} ft · gap {_gap_text(t)}]")
    return lines


def _gap_text(t):
    lead = max(int(r["pos ft"]) for r in t.rows if r["role"] == "pursuer")
    return ", ".join(f"{r['name']} {int(r['pos ft']) - lead} ft ahead" for r in t.rows if r["role"] == "quarry")


def _escape(state, t, i, gap, sight, hidden, rng):
    """The quarry is out of sight: Stealth vs the pursuers' best passive Perception."""
    row = t.rows[i]
    why = "a complication hid it" if hidden else f"gap {gap} ft > sight {sight} ft"
    best, who = _best_passive(state, t)
    c = creatures.get(row["name"], state)
    t.set(i, "notes", "; ".join(n for n in _notes(row) if n != "out of sight"))
    if best is None:
        return [f"[{row['name']} is out of sight ({why}); no pursuer has a passive Perception]"], False
    if c.is_pc:
        return [f"[{row['name']} is out of sight ({why}): Stealth vs passive Perception {best} ({who}) — "
                f"ask for the d20; if it beats it, gm.py chase end escaped]"], False
    roll = rng.d20(c.skill_bonus("stealth"))
    win, note = resolve.contest(roll.total, best, a_is_pc=False, b_is_pc=True, rules=resolve.active_keys())
    escaped = win == "A"
    body = (f"{row['name']} is out of sight ({why}): Stealth {roll.text} vs passive Perception {best} ({who}) — "
            + ("escaped" if escaped else "spotted again") + (f" ({note})" if note else ""))
    journal.log_delta(f"chase {body}")
    return [f"[{body}]"], escaped


def extra_dash(who, roller=None):
    rng = roller or dice.Roller()
    state = campaign.load_state()
    st = status(state)
    if st is None:
        raise ChaseError("chase dash: no chase running")
    t = _table(state)
    want = who.strip().lower()
    i = next((k for k, r in enumerate(t.rows) if r["name"].lower() == want or r["name"].lower().startswith(want)), None)
    if i is None:
        raise ChaseError(f"chase dash: {who} is not in the chase")
    lines = _dash(state, t, i, rng)
    old = int(t.rows[i]["pos ft"])
    new = old + int(t.rows[i]["speed"] or 0)
    t.set(i, "pos ft", new)
    state.save()
    body = f"chase {t.rows[i]['name']} dashes again: {old}→{new} ft ({t.rows[i]['dashes']})"
    journal.log_delta(body)
    return [f"[{body}]"] + lines


# ---------- end ----------

def end(outcome="ended"):
    state = campaign.load_state()
    st = status(state)
    if st is None:
        raise ChaseError("chase end: no chase running")
    rnd, _, _ = st
    i, _ = _heading(state, "chase")
    state.body[i] = "## Combat"
    tempo.set_section(state, "Combat", ["(not in combat)"])
    state.save()
    tag = {"caught": "caught: start combat or grapple", "escaped": "escaped",
           "gave-up": "the pursuers gave up"}.get(outcome, outcome)
    journal.log_delta(f"chase end ({tag}) after {rnd} round{'s' if rnd != 1 else ''}")
    lines = [f"[chase end · {tag}]"]
    import clock
    clk, _ = clock.advance(f"+{max(1, math.ceil(rnd * 6 / 60))}m")
    return lines + clk


# ---------- CLI ----------

def cmd_chase(ctx):
    a = ctx.args
    if a.action == "start":
        if not a.quarry:
            raise ChaseError("chase start --quarry <name> [--pursuers A,B] [--lead 60] [--env urban|wild]")
        lines = start(a.quarry, a.pursuers, a.lead, a.env)
    elif a.action == "next":
        lines = next_turn(not a.no_dash, a.lose, ctx.roller)
    elif a.action == "dash":
        if not a.who:
            raise ChaseError("chase dash <who>")
        lines = extra_dash(a.who, ctx.roller)
    else:
        lines = end(a.who or "ended")
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("chase", parents=[g], help="chase start --quarry X | next | dash <who> | end [caught|escaped|gave-up]")
    p.add_argument("action", choices=["start", "next", "dash", "end"])
    p.add_argument("who", nargs="?", help="dash: who dashes · end: caught | escaped | gave-up")
    p.add_argument("--quarry")
    p.add_argument("--pursuers")
    p.add_argument("--lead", type=int, default=60)
    p.add_argument("--env", choices=["urban", "wild"], default="urban")
    p.add_argument("--no-dash", action="store_true", help="next: a plain move, no Dash")
    p.add_argument("--lose", type=int, default=0, help="next: feet lost to a complication")
    p.set_defaults(func=cmd_chase)
