"""Social stakes: attitude-based DCs, flair, NPC tastes, the wall and the result tiers
(docs/design/02 → Table mechanics → Phase 14 → Social stakes; 04 → Scene state added
(`state/social.md`), NPC file `moved-by:`; 06 → Table mechanics → Phase 14; plan.md
Phase 14 item 3).

    check Kira persuasion --vs mara --ask none|free|minor|major [--leverage -5..5]
          [--flair 0-3 --pitch "goat grandfather" [--appeal audacity] [--grates]]
          [--why "…"] [--goal "get the ledger"] [--core] [--dc N] [<total> | --d20 N]
    social status [<npc>] | social drop <npc> "<goal>" | social wall on|off|<n>

`check … --ask` (roll.py hands it here) starts from the 02 table (`social-dcs: dmg`;
under `gm` the GM's `--dc` is the start), then: `--leverage` adds; flair (after the
NPC's `moved-by:` taste: `--appeal <taste>` it is moved by +1, `nothing` −1 on any flair
pitch, `--grates` −1; a `--pitch` already scored on this NPC is 0) takes off the
`creativity` steps; the wall takes one band (5) off once `fails` ≥ `social-wall` and
this attempt's skill or `--why` is new for the goal. DC floor 0. The sum is printed for
the GM and logged as one `(GM)` line before any result. Without a total it stops there;
with one it runs the check (roll.ability_check) and prints the tier. Flair, pitches and
stages never go into a public line.

`state/social.md` (`| npc | goal | fails | approaches | pitches | since |`): one row per
open goal, keyed by the NPC's file slug; success removes it. A row with goal `—` is the
NPC's pitch memory for flair tried without a goal (or while the wall is off), so a
repeated trick scores 0 either way. `social-wall: off` writes no goal rows and prints
no stages; rows already open are kept for when it's switched back on.

Python API: `check(...)` (roll.py), `brief_line(state)` (brief.py), `intro_line()`
(intro.py), `wall_setting()`.
"""
from pathlib import Path

from lib import campaign, creatures, journal, md, resolve
from lib import social as data
from lib.errors import ToolError

HEADER = ["# Social goals",
          "<!-- One row per open social goal (02 → Social stakes; 04 → state/social.md). Written by",
          "     gm.py check --vs … --goal; removed on success. goal `—` = pitches tried without a goal. -->",
          "",
          "| npc | goal | fails | approaches | pitches | since |",
          "|-----|------|-------|------------|---------|-------|"]
NO_GOAL = "—"
CORE = "no roll: core scenario — steer to another route to the same goal"


class SocialError(ToolError):
    def __init__(self, message, output=()):
        super().__init__(message)
        self.output = list(output)


def _setting(key):
    return str(campaign.settings().get(key, campaign.SETTINGS[key])).strip().lower()


def wall_setting():
    """The wall's threshold (an int), or None when `social-wall: off`."""
    v = campaign.settings().get("social-wall", campaign.SETTINGS["social-wall"])
    t = str(v).strip().lower()
    if t in ("off", "false", "0", ""):
        return None
    if t in ("on", "true"):
        return 3
    try:
        return max(1, int(t))
    except ValueError:
        return 3


# ---------- state/social.md ----------

def _path():
    return campaign.root() / "state" / "social.md"


def _doc(create=False):
    p = _path()
    if p.exists():
        return md.load(p)
    if not create:
        return None
    state = campaign.load_state()
    doc = md.Doc(str(p), "\n".join(HEADER) + "\n", state.newline)
    return doc


def _rows(doc):
    t = doc.table("Social goals") if doc is not None else None
    return t


def _items(cell):
    cell = (cell or "").strip()
    return [] if cell in ("", NO_GOAL, "-") else [x.strip() for x in cell.split(";") if x.strip()]


def _cell(items):
    return "; ".join(items) if items else NO_GOAL


def _clean(text):
    return " ".join(str(text or "").replace("|", "/").replace(";", ",").split())


def _find(t, npc, goal):
    for i, r in enumerate(t.rows if t else []):
        if r.get("npc", "").strip().lower() == npc and r.get("goal", "").strip().lower() == goal.lower():
            return i
    return None


def _pitches(t, npc):
    out = set()
    for r in t.rows if t else []:
        if r.get("npc", "").strip().lower() == npc:
            out |= {p.lower() for p in _items(r.get("pitches"))}
    return out


def _npc(name):
    c = creatures.get(name)
    if c.is_pc:
        raise SocialError(f"check --vs {name}: social DCs are for NPCs (a PC decides for themself)")
    doc = c.doc
    slug = Path(doc.path).stem if doc is not None else campaign.slugify(c.name)
    short = c.name.split()[0] if doc is not None else c.name
    return c, slug, short


# ---------- the check ----------

def check(pc, skill, npc, ask, *, leverage=0, flair=0, pitch=None, appeal=None, grates=False,
          why=None, goal=None, core=False, dc=None, d20=None, total=None, mode=None, roller=None):
    if core:
        raise SocialError("core scenario (no roll)", output=[f"[social] {CORE}"])
    ask = (ask or "").strip().lower()
    if ask not in data.ASKS:
        raise SocialError(f"--ask {ask!r}: none | free | minor | major")
    if not -5 <= leverage <= 5:
        raise SocialError(f"--leverage {leverage}: −5..+5")
    if not 0 <= flair <= 3:
        raise SocialError(f"--flair {flair}: 0–3")
    if flair and not (pitch and pitch.strip()):
        raise SocialError('--flair needs --pitch "<short tag>" (so a repeated pitch scores 0)')
    if appeal and appeal.lower() not in data.TASTES:
        raise SocialError(f"--appeal {appeal!r}: {' | '.join(data.TASTES[:-1])}")
    state = campaign.load_state()
    who = creatures.get(pc, state)
    c, slug, short = _npc(npc)
    att = data.attitude(c.front.get("attitude-to-party"))
    if _setting("social-dcs") == "gm":
        if dc is None:
            raise SocialError("social-dcs: gm — give the starting DC with --dc N")
        base = dc
    else:
        base = dc if dc is not None else data.starting_dc(att, ask)
    sk = creatures.skill_key(skill)
    head = f"[social] {who.name.split()[0]} {sk} vs {short} · {att} · {ask}: DC {base}"
    parts = [f"leverage {leverage:+d}" if leverage else "leverage 0"]
    doc = _doc()
    t = _rows(doc)
    tag = _clean(pitch).lower() if pitch else ""
    eff = flair
    note = ""
    if flair and tag in _pitches(t, slug):
        eff, note = 0, "already tried on " + short
    else:
        eff, note = data.adjust_flair(flair, data.tastes(c.front.get("moved-by")), appeal, grates)
    off, adv = data.flair_off(eff, _setting("creativity"))
    if flair or pitch:
        bits = [x for x in (note, f'"{tag}"' if tag else "") if x]
        ftxt = f"flair {eff}" + (f" ({', '.join(bits)})" if bits else "")
        ftxt += f": −{off}" if off else ": no change"
        if adv:
            ftxt += ", advantage"
        parts.append(ftxt)
    wall = wall_setting()
    band = 0
    row_i = _find(t, slug, goal) if goal and t is not None else None
    fails = int(t.rows[row_i].get("fails") or 0) if row_i is not None else 0
    tried = {a.lower() for a in _items(t.rows[row_i].get("approaches"))} if row_i is not None else set()
    fresh = sk not in tried or (why is not None and f"why: {_clean(why)}".lower() not in tried)
    final = max(0, base + leverage - off)
    wall_txt = ""
    if goal and wall is not None and fails:
        wall_txt = f'wall: {fails} fail{"s" if fails != 1 else ""} on "{goal}" ({data.stage(fails)})'
        if fails >= wall and fresh:
            band = data.BAND
            wall_txt += f", new approach: −{band}"
        final = max(0, final - band)
    lines = [head, "  " + " · ".join(parts) + (f" → DC {final}" if not wall_txt else "")]
    if wall_txt:
        lines.append(f"  {wall_txt} → DC {final}")
    gm_line = " · ".join(x.strip() for x in [head[len('[social] '):]] + lines[1:])
    _log_once(f"[social] {gm_line}")
    result = {"npc": short, "attitude": att, "ask": ask, "base": base, "dc": final, "flair": eff,
              "advantage": adv, "band": band}
    if adv:
        mode = None if mode == "dis" else "adv"
    import roll
    rules = resolve.active_keys()
    if d20 is None and total is None and who.is_pc and resolve.dice_mode(state.front, rules) != "gm-rolls-all":
        lines.append(f"  ask: {who.name.split()[0]} {sk} vs DC {final}" + (" with advantage" if adv else "")
                     + f" (then gm.py check {who.name.split()[0]} {sk} --vs {slug} --ask {ask} … <total>)")
        return lines, result
    line, rd = roll.ability_check(pc, skill, final, mode=mode, d20=d20, total=total, roller=roller)
    lines.append(line)
    margin = rd["margin"] if rd["outcome"] == "SUCCESS" else -rd["margin"]
    res = data.tier(margin, eff)
    tail = f" — consider: attitude {short} {data.worse(att)}" if res == "no, and" else ""
    lines.append(f"[social] {res}{tail}")
    journal.log_delta(f"[social] {short}: {res}", gm=True)
    result.update({"tier": res, "outcome": rd["outcome"], "margin": margin})
    lines += _record(slug, short, goal, sk, why, tag if flair else "", rd["outcome"] == "SUCCESS", wall, state)
    return lines, result


def _log_once(text):
    """Log the GM sum unless the same line is already the open turn's last social line
    (the DC call and the roll call print the same sum)."""
    doc = journal._load_log()
    _, is_open = journal.current_turn(doc)
    if is_open:
        mine = [x for x in doc.body if x.startswith("  - (GM) [social] ") and "·" in x]
        if mine and mine[-1] == "  - (GM) " + text:
            return
    journal.log_delta(text, gm=True)


def _record(slug, short, goal, skill, why, tag, won, wall, state):
    """Write the attempt to state/social.md. -> lines."""
    if not tag and not (goal and wall is not None):
        return []
    doc = _doc(create=True)
    t = _rows(doc)
    now = str(state.front.get("in-game-datetime") or "")
    out = []
    if goal and wall is not None:
        i = _find(t, slug, goal)
        if won:
            if i is not None:
                tries = int(t.rows[i].get("fails") or 0) + 1
                left = _items(t.rows[i].get("pitches")) + ([tag] if tag else [])
                t.remove(i)
                journal.log_delta(f'[social] {goal} — won after {tries} tr{"ies" if tries != 1 else "y"}')
                out.append(f'[social] "{goal}" won after {tries} tr{"ies" if tries != 1 else "y"} — row closed')
                if left:
                    _remember(doc, slug, left, now)
            elif tag:
                _remember(doc, slug, [tag], now)
        else:
            if i is None:
                t.append({"npc": slug, "goal": _clean(goal), "fails": "0", "approaches": NO_GOAL,
                          "pitches": NO_GOAL, "since": now})
                t = _rows(doc)
                i = len(t.rows) - 1
            r = t.rows[i]
            fails = int(r.get("fails") or 0) + 1
            tried = _items(r.get("approaches"))
            for a in [skill] + ([f"why: {_clean(why)}"] if why else []):
                if a.lower() not in [x.lower() for x in tried]:
                    tried.append(a)
            pitches = _items(r.get("pitches")) + ([tag] if tag and tag not in _items(r.get("pitches")) else [])
            t.set(i, "fails", str(fails))
            t.set(i, "approaches", _cell(tried))
            t.set(i, "pitches", _cell(pitches))
            cue = data.stage(fails)
            out.append(f"[social] {cue} ({short}, \"{goal}\", {fails} fail{'s' if fails != 1 else ''})")
            journal.log_delta(f'[social] {short} "{goal}": {fails} fails · {cue}', gm=True)
    elif tag:
        _remember(doc, slug, [tag], now)
    doc.save()
    return out


def _remember(doc, slug, tags, now):
    """Add pitch tags to the NPC's `—` row (pitch memory without a goal)."""
    t = _rows(doc)
    i = _find(t, slug, NO_GOAL)
    if i is None:
        t.append({"npc": slug, "goal": NO_GOAL, "fails": "0", "approaches": NO_GOAL,
                  "pitches": _cell(tags), "since": now})
        return
    have = _items(t.rows[i].get("pitches"))
    t.set(i, "pitches", _cell(have + [x for x in tags if x not in have]))


# ---------- social status | drop | wall ----------

def _goal_rows(npc_slug=None):
    t = _rows(_doc())
    out = []
    for r in t.rows if t else []:
        if r.get("goal", "").strip() in (NO_GOAL, "-", ""):
            continue
        if npc_slug and r.get("npc", "").strip().lower() != npc_slug:
            continue
        out.append(r)
    return out


def _short_of(slug):
    p = campaign.path("npcs", slug)
    if p.exists():
        return str(md.load(p).front.get("name") or slug).split()[0]
    return slug


def status(npc=None):
    slug = _npc(npc)[1] if npc else None
    rows = _goal_rows(slug)
    wall = wall_setting()
    head = f"[social] wall: {'off' if wall is None else f'{wall} fails'}"
    if not rows:
        return [head + " · no open goals"]
    out = [head]
    for r in rows:
        fails = int(r.get("fails") or 0)
        out.append(f'  {_short_of(r["npc"])} "{r["goal"]}" · {fails} fail{"s" if fails != 1 else ""}'
                   f' ({data.stage(fails) or "—"}) · tried: {r.get("approaches")} · since {r.get("since")}')
    return out


def drop(npc, goal):
    slug = _npc(npc)[1]
    doc = _doc()
    t = _rows(doc)
    i = _find(t, slug, _clean(goal)) if t is not None else None
    if i is None:
        raise SocialError(f'no open goal "{goal}" for {npc} (gm.py social status)')
    t.remove(i)
    doc.save()
    body = f'[social] {_short_of(slug)} "{goal}" dropped (the party gave up on it)'
    journal.log_delta(body)
    return [body]


def set_wall(value):
    v = value.strip().lower()
    if v == "on":
        new = 3
    elif v == "off":
        new = "off"
    elif v.isdigit() and int(v) >= 1:
        new = int(v)
    else:
        raise SocialError("social wall on | off | <n>")
    doc = campaign.settings_doc()
    doc.set_front("social-wall", new)
    doc.save()
    body = f"[social] wall {v} (table's choice)"
    journal.log_delta(body)
    return [body]


# ---------- brief / intro ----------

def brief_line(state):
    """`Social: Mara "get the ledger" 2 fails` for open goals of NPCs on stage (wall on)."""
    if wall_setting() is None or not _path().exists():
        return None
    here = set()
    for m in campaign.stage_matches(state):
        if m.is_pc:
            continue
        if m.slug:
            here.add(m.slug.lower())
        here.add(campaign.slugify(m.name))
    bits = []
    for r in _goal_rows():
        if r["npc"].strip().lower() in here:
            fails = int(r.get("fails") or 0)
            bits.append(f'{_short_of(r["npc"])} "{r["goal"]}" {fails} fail{"s" if fails != 1 else ""}')
    return "Social: " + " · ".join(bits) if bits else None


def intro_line():
    if wall_setting() is None:
        return None
    return ("[TELL THE TABLE] social-wall on: mention once, plainly, that repeated tries with an "
            "NPC can get easier and that they can ask to turn it off")


# ---------- CLI ----------

def cmd_social(ctx):
    a = ctx.args
    if a.action == "status":
        lines = status(a.args[0] if a.args else None)
    elif a.action == "drop":
        if len(a.args) < 2:
            raise SocialError('social drop <npc> "<goal>"')
        lines = drop(a.args[0], " ".join(a.args[1:]))
    else:
        if len(a.args) != 1:
            raise SocialError("social wall on | off | <n>")
        lines = set_wall(a.args[0])
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("social", parents=[g], help='social status [npc] | drop <npc> "<goal>" | wall on|off|<n>')
    p.add_argument("action", choices=["status", "drop", "wall"])
    p.add_argument("args", nargs="*")
    p.set_defaults(func=cmd_social)
