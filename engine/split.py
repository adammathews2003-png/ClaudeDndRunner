"""`gm.py split` — splitting the party (docs/design/02 → Splitting the party; 04 → Split
party; 06 → `gm.py split`; plan.md Phase 12).

    split mill=Grusk inn=Kael,Kira [--active mill]   form groups (names: PC or player)
    split cut [<group>] [--force]                    park the active scene, load the next
    split status                                     groups, clocks, whose slice is due
    split sense <group> on|off|auto                  override "can sense the other's fight"
    split task <group> "<what>" <30m>                a long task spanning slices
    split join <group> <group>                       merge two groups at one site

`state/current.md` always holds the **active** group's scene, so every other tool works
unchanged; each waiting group's scene is parked in `state/split/<group>.md`. A cut
swaps the body and the scene keys (`SCENE_KEYS`) and keeps the campaign-wide
frontmatter (`in-session`, settings, …) where it is. `state/split.md` holds the groups.
The exchange counter is hook scratch in `.gm/split-slice` (not canon, not undone).

Python API used by brief/clock: `info()`, `brief_lines(state)`, `heartbeat_bit(state)`,
`count_prompt(prompt)`, `world_window(old, new)`, `ahead_warning(new)`,
`tasks_done(new)`, `on_stage_elsewhere()`.
"""
import re

from lib import campaign, gametime, geo, journal, md, sight
from lib.errors import ToolError

SCENE_KEYS = ("in-game-datetime", "party-location", "scene", "light")
_GROUP = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_COMBAT = re.compile(r"^Combat\s*[—-]\s*round\s*(\d+)", re.I)
_TEMPO = re.compile(r"^Tempo:\s*([a-z]+)", re.I)
_TASK = re.compile(r"^\s*-\s*([a-z0-9-]+):\s*(.+?)\s*\((\S+)\)\s*—\s*(Day -?\d+ \d\d:\d\d)\s*→\s*(Day -?\d+ \d\d:\d\d)\s*$")
HEADER = ("# Split party\n<!-- Written by gm.py split. state/current.md is the active group's scene; "
          "the others are parked in state/split/<group>.md. -->\n")


class SplitError(ToolError):
    pass


# ---------- files ----------

def parked_path(group):
    return campaign.root() / "state" / "split" / f"{group}.md"


def _slice_path():
    return campaign.root() / ".gm" / "split-slice"


def _settings():
    s = campaign.settings()
    return {k: int(s.get(k)) for k in ("split-exchanges", "split-combat-rounds", "split-sense-ft",
                                       "split-max-ahead")}


def _remove(path):
    """Delete a canon file so `undo` can bring it back (the journal snapshots it)."""
    if path.exists():
        for hook in md.before_write:
            hook(str(path))
        path.unlink()


def load():
    """{'active', 'groups': [{'group','pcs':[names],'sense'}], 'tasks': [...], 'doc'} or None."""
    p = campaign.split_path()
    if not p.exists():
        return None
    doc = md.load(p)
    t = doc.table("Split party")
    groups = []
    for r in (t.rows if t else []):
        groups.append({"group": r.get("group", ""), "sense": (r.get("sense") or "auto").lower(),
                       "pcs": [n.strip() for n in r.get("pcs", "").split(",") if n.strip()]})
    tasks = []
    span = doc.section("Long tasks")
    for i in range(span[0] + 1, span[1]) if span else []:
        m = _TASK.match(doc.body[i])
        if m:
            tasks.append({"group": m.group(1), "what": m.group(2), "dur": m.group(3),
                          "start": gametime.parse(m.group(4)), "end": gametime.parse(m.group(5))})
    return {"active": str(doc.front.get("active") or ""), "groups": groups, "tasks": tasks,
            "slice-round": int(doc.front.get("slice-round") or 0), "doc": doc}


def info():
    return load()


def scene_doc(sp, group):
    """The group's scene: current.md when active, else its parked file."""
    if group == sp["active"]:
        return campaign.load_state()
    p = parked_path(group)
    if not p.exists():
        raise SplitError(f"group {group!r} has no parked scene ({p.name} is missing)")
    return md.load(p)


def _save(sp):
    """Rewrite state/split.md from `sp` (the live columns are refreshed from the scenes)."""
    p = campaign.split_path()
    rows = []
    for g in sp["groups"]:
        d = scene_doc(sp, g["group"])
        rows.append([g["group"], ", ".join(g["pcs"]), str(d.front.get("party-location") or "?"),
                     str(d.front.get("in-game-datetime") or "?"), tempo_of(d), g.get("sense") or "auto"])
    cols = ["group", "pcs", "location", "time", "tempo", "sense"]
    widths = [max(len(c), *(len(r[i]) for r in rows)) for i, c in enumerate(cols)]
    line = lambda cells: "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"  # noqa: E731
    text = (f"---\nactive: {sp['active']}\nslice-round: {sp.get('slice-round', 0)}"
            "                    # the combat round the active slice began in (0 = not in combat)\n---\n\n"
            + HEADER + "\n" + line(cols) + "\n|" + "|".join("-" * (w + 2) for w in widths) + "|\n"
            + "\n".join(line(r) for r in rows) + "\n")
    if sp["tasks"]:
        text += "\n## Long tasks\n" + "".join(
            f"- {t['group']}: {t['what']} ({t['dur']}) — {gametime.fmt(t['start'])} → {gametime.fmt(t['end'])}\n"
            for t in sp["tasks"])
    p.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(p, text)


# ---------- reading a scene ----------

def tempo_of(doc):
    for _, _, text in doc.headings():
        if _COMBAT.match(text):
            return "combat"
    for _, _, text in doc.headings():
        m = _TEMPO.match(text)
        if m:
            return m.group(1).lower()
    return "calm"


def combat_round(doc):
    for _, _, text in doc.headings():
        m = _COMBAT.match(text)
        if m:
            return int(m.group(1))
    return 0


def time_of(doc):
    return gametime.parse(doc.front.get("in-game-datetime"))


def _short(name):
    return str(name).split()[0] if str(name).strip() else str(name)


def _label(g):
    return f"{g['group']} ({', '.join(_short(n) for n in g['pcs'])})"


def _group(sp, name):
    for g in sp["groups"]:
        if g["group"] == name:
            return g
    raise SplitError(f"no group {name!r} (groups: {', '.join(g['group'] for g in sp['groups'])})")


def _need():
    sp = load()
    if sp is None:
        raise SplitError("the party isn't split (split <group>=<PC,…> <group>=<PC,…>)")
    return sp


# ---------- sensing ----------

def _distance_ft(loc_a, loc_b):
    """Route distance in feet between two locations, 0 for the same site, None if unknown."""
    sa, sb = loc_a.split("/")[0], loc_b.split("/")[0]
    if sa == sb:
        return 0
    try:
        plan = geo.find_route(loc_a, sb)
    except geo.GeoError:
        return None
    total = 0.0
    for r in plan.routes:
        length = geo.route_length(plan.frame, r)
        if length is None:
            return None
        total += geo.to_ft(length, plan.frame.unit)
    return total


def senses_fight(sp, fighting, other, cfg=None):
    """(bool, why) — can group `other` sense group `fighting`'s fight?"""
    g = _group(sp, other)
    if g["sense"] in ("on", "off"):
        return g["sense"] == "on", f"set {g['sense']}"
    cfg = cfg or _settings()
    a = str(scene_doc(sp, fighting).front.get("party-location") or "")
    b = str(scene_doc(sp, other).front.get("party-location") or "")
    ft = _distance_ft(a, b)
    if ft is None:
        return False, "distance unknown — override with split sense"
    if ft == 0:
        return True, f"same site ({a.split('/')[0]})"
    reach = cfg["split-sense-ft"]
    names = {n.lower() for n in g["pcs"]}
    for d in campaign.pcs():
        if str(d.front.get("name") or "").lower() in names:
            for k, v in sight.senses(d).items():
                if k != "darkvision":
                    reach = max(reach, v)
    if ft <= reach:
        return True, f"{int(ft)} ft away"
    return False, f"{int(ft)} ft away"


# ---------- slice accounting ----------

def _read_slice():
    p = _slice_path()
    try:
        return int(p.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return 0


def _write_slice(n):
    p = _slice_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"{n}\n", encoding="utf-8")


def count_prompt(prompt):
    """Brief hook: one more exchange for the active group (commands don't count)."""
    if not campaign.split_path().exists():
        return
    if str(prompt or "").lstrip().startswith(("/", "!")):
        return
    _write_slice(_read_slice() + 1)


def _ahead_limit(sp, waiting):
    """Minutes the active group may run ahead of the waiting groups: about one minute
    while any of them is fighting (six rounds), else split-max-ahead."""
    return 1 if any(tempo_of(scene_doc(sp, g["group"])) == "combat" for g in waiting) \
        else _settings()["split-max-ahead"]


def rounds_played(sp, state):
    """Combat rounds the active group has fought this slice (0 when not fighting)."""
    rnd = combat_round(state)
    if not rnd:
        return 0
    return rnd - sp["slice-round"] + 1 if sp["slice-round"] else rnd


def charge_combat(played):
    """Combat doesn't move the clock; while split, a fight's rounds (6 s each, rounded
    up to the minute) are charged to its group when the GM cuts away or it ends."""
    if not played:
        return []
    import clock
    lines, _ = clock.advance(f"+{-(-played * 6 // 60)}m")
    return [f"[split: {played} combat round{'s' if played != 1 else ''} → the group's clock]"] + lines


def due(sp=None, state=None):
    """(slice text, cue or None) for the active group."""
    sp = sp or load()
    cfg = _settings()
    state = state or campaign.load_state()
    waiting = [g for g in sp["groups"] if g["group"] != sp["active"]]
    cue = None
    if tempo_of(state) == "combat":
        played = rounds_played(sp, state)
        sensed = [(g["group"], senses_fight(sp, sp["active"], g["group"], cfg)) for g in waiting]
        hear = [name for name, (yes, _) in sensed if yes]
        if hear:
            text = f"round {played} of 1 (every round: {', '.join(hear)} can sense the fight)"
            if played > 1:
                cue = f"Cut every round: {', '.join(hear)} can sense the fight"
        else:
            text = f"round {played} of {cfg['split-combat-rounds']}"
            if played > cfg["split-combat-rounds"]:
                cue = f"Cut due: {cfg['split-combat-rounds']} rounds played"
    else:
        n = _read_slice()
        text = f"exchange {n}/{cfg['split-exchanges']}"
        if n >= cfg["split-exchanges"]:
            cue = f"Cut due: {n} exchanges"
    now = time_of(state)
    behind = [(gametime.diff(time_of(scene_doc(sp, g["group"])), now), g["group"]) for g in waiting]
    if behind:
        gap, who = max(behind)
        if gap > _ahead_limit(sp, waiting):
            cue = f"Cut due: {who} is {gametime.fmt_delta(gap)} behind"
        elif cue and -gap > _settings()["split-max-ahead"]:   # everyone else is far ahead
            cue = f"Play on: {who} is {gametime.fmt_delta(-gap)} ahead (no cut until this group catches up)"
    return text, cue


# ---------- brief ----------

def brief_lines(state):
    """(split line, slice line) for the brief, or (None, None) when not split. The
    slice line changes every prompt, so the brief leaves it out of its hash."""
    sp = load()
    if sp is None:
        return None, None
    now = time_of(state)
    bits = []
    for g in sp["groups"]:
        if g["group"] == sp["active"]:
            bits.insert(0, "▶ " + _label(g))
            continue
        d = scene_doc(sp, g["group"])
        gap = gametime.diff(time_of(d), now)
        rel = "level" if gap == 0 else (f"{gametime.fmt_delta(gap)} behind" if gap > 0
                                         else f"{gametime.fmt_delta(-gap)} ahead")
        bits.append(f"{_label(g)} {d.front.get('party-location')} {gametime.fmt(time_of(d))} {tempo_of(d)}, {rel}")
    tasks = [f"{t['group']}: {t['what']} until {gametime.fmt_clock(t['end'][1])}" for t in sp["tasks"]]
    split_line = "Split: " + " · ".join(bits) + (" · Tasks: " + "; ".join(tasks) if tasks else "")
    text, cue = due(sp, state)
    return split_line, "Slice: " + text + (f" · {cue}" if cue else "")


def heartbeat_bit(state):
    """Short slice status for the heartbeat line, or None."""
    sp = load()
    if sp is None:
        return None
    text, cue = due(sp, state)
    return f"{sp['active']} {text.split(' (')[0]}" + (" · CUT DUE" if cue else "")


# ---------- clock integration ----------

def world_window(old, new):
    """While split: world events (NPC schedules, CLOCK beats, restock) run on the
    earliest group clock. Returns (w_old, w_new); equal means nothing to run."""
    sp = load()
    if sp is None:
        return old, new
    others = [time_of(scene_doc(sp, g["group"])) for g in sp["groups"] if g["group"] != sp["active"]]
    lo = lambda ts: min(ts, key=lambda t: (t[0], t[1]))  # noqa: E731
    w_old, w_new = lo(others + [old]), lo(others + [new])
    return w_old, w_new


def on_stage_elsewhere():
    """Lower-cased On stage names in the parked scenes (so clock never moves them)."""
    sp = load()
    if sp is None:
        return set()
    out = set()
    for g in sp["groups"]:
        if g["group"] == sp["active"]:
            continue
        for m in campaign.stage_matches(scene_doc(sp, g["group"])):
            out.add(m.name.lower())
    return out


def ahead_warning(new):
    sp = load()
    if sp is None:
        return []
    waiting = [g for g in sp["groups"] if g["group"] != sp["active"]]
    out = []
    limit = _ahead_limit(sp, waiting)
    for g in waiting:
        gap = gametime.diff(time_of(scene_doc(sp, g["group"])), new)
        if gap > limit:
            out.append(f"[split: {sp['active']} is now {gametime.fmt_delta(gap)} ahead of {g['group']} — "
                       "cut first or summarise their matching span]")
    return out


def tasks_done(new):
    """Lines for the active group's long tasks that finish by `new`; removes them."""
    sp = load()
    if sp is None:
        return []
    done = [t for t in sp["tasks"] if t["group"] == sp["active"] and gametime.diff(t["end"], new) >= 0]
    if not done:
        return []
    sp["tasks"] = [t for t in sp["tasks"] if t not in done]
    _save(sp)
    out = []
    for t in done:
        journal.log_delta(f"split task done: {t['group']} — {t['what']}")
        out.append(f"  Long task done: {t['group']} — {t['what']} ({gametime.fmt_clock(t['end'][1])})")
    return out


# ---------- commands ----------

def _resolve_pcs(spec):
    import pc
    out = []
    for n in [x.strip() for x in spec.split(",") if x.strip()]:
        try:
            out += [str(d.front.get("name")) for d in pc.roster_docs(n)]
        except (pc.PcError, campaign.CampaignError) as e:
            raise SplitError(f"{n!r}: {e}") from None
    return out


def form(specs, active=None):
    if load() is not None:
        raise SplitError("already split; `split join` first (or `split status`)")
    state = campaign.load_state()
    if tempo_of(state) == "combat":
        raise SplitError("can't split mid-combat: end the fight first, or keep everyone in it")
    groups, seen = [], {}
    for spec in specs:
        name, eq, who = spec.partition("=")
        name = name.strip().lower()
        if not eq or not _GROUP.match(name):
            raise SplitError(f"want <group>=<PC,…> with a lowercase group name, got {spec!r}")
        if any(g["group"] == name for g in groups):
            raise SplitError(f"group {name!r} named twice")
        pcs = _resolve_pcs(who)
        for p in pcs:
            if p in seen:
                raise SplitError(f"{p} is in both {seen[p]} and {name}")
            seen[p] = name
        groups.append({"group": name, "pcs": pcs, "sense": "auto"})
    if len(groups) < 2:
        raise SplitError("a split needs at least two groups")
    left = [str(d.front.get("name")) for d in campaign.pcs() if str(d.front.get("name")) not in seen]
    if left:
        raise SplitError("put every PC in a group (absent ones too): " + ", ".join(left))
    active = (active or groups[0]["group"]).lower()
    if not any(g["group"] == active for g in groups):
        raise SplitError(f"--active {active!r} is not one of the groups")
    text = state.text()
    for g in groups:
        if g["group"] != active:
            p = parked_path(g["group"])
            p.parent.mkdir(parents=True, exist_ok=True)
            md.write_text(p, text, state.newline)
    sp = {"active": active, "groups": groups, "tasks": [], "slice-round": 0}
    _save(sp)
    _write_slice(0)
    body = "split " + " · ".join(_label(g) for g in groups) + f" · active {active}"
    journal.log_delta(body)
    where = state.front.get("party-location")
    return [f"[{body} — all at {where} {state.front.get('in-game-datetime')}; move a group by making it "
            "active (split cut) and using scene enter / travel]"]


def _swap_in(state, parked):
    """current.md becomes `parked`'s scene; campaign-wide frontmatter stays."""
    for k in SCENE_KEYS:
        if k in parked.front:
            state.set_front(k, parked.front.get(k))
    state.body = list(parked.body)
    state.trailing_newline = parked.trailing_newline


def pick_next(sp):
    """The waiting group with the earliest clock (ties → the next in table order)."""
    names = [g["group"] for g in sp["groups"]]
    i = names.index(sp["active"])
    order = names[i + 1:] + names[:i]
    return min(order, key=lambda n: (*time_of(scene_doc(sp, n)), order.index(n)))


def cut(group=None, force=False):
    sp = _need()
    target = (group or pick_next(sp)).lower()
    _group(sp, target)
    if target == sp["active"]:
        raise SplitError(f"{target} is already active")
    state = campaign.load_state()
    parked = scene_doc(sp, target)
    if not force:
        times = [time_of(scene_doc(sp, g["group"])) for g in sp["groups"]]
        earliest = min(times, key=lambda t: (t[0], t[1]))
        lead = gametime.diff(earliest, time_of(parked))
        if lead > _settings()["split-max-ahead"]:
            raise SplitError(f"{target} is {gametime.fmt_delta(lead)} ahead of the earliest group; "
                             "cut to the group that's behind, or pass --force")
    old = sp["active"]
    charged = charge_combat(rounds_played(sp, state)) if tempo_of(state) == "combat" else []
    if charged:
        state = campaign.load_state()
    out_path = parked_path(old)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(out_path, state.text(), state.newline)
    _swap_in(state, parked)
    state.save()
    _remove(parked_path(target))
    sp["active"] = target
    sp["slice-round"] = combat_round(state)
    _save(sp)
    _write_slice(0)
    journal.log_delta(f"split cut {old} → {target}")
    g = _group(sp, target)
    return charged + [f"[split cut: {old} → {_label(g)} · {state.front.get('party-location')} "
            f"{state.front.get('in-game-datetime')} · {tempo_of(state)}]"]


def status():
    sp = _need()
    state = campaign.load_state()
    out = ["[split status]"]
    for g in sp["groups"]:
        d = scene_doc(sp, g["group"])
        mark = "▶" if g["group"] == sp["active"] else " "
        out.append(f"  {mark} {_label(g)} · {d.front.get('party-location')} · {d.front.get('in-game-datetime')} · "
                   f"{tempo_of(d)} · light {d.front.get('light') or 'bright'}"
                   + (f" · sense {g['sense']}" if g["sense"] != "auto" else ""))
    for t in sp["tasks"]:
        out.append(f"  task {t['group']}: {t['what']} ({t['dur']}) {gametime.fmt(t['start'])} → {gametime.fmt(t['end'])}")
    text, cue = due(sp, state)
    out.append(f"  slice: {sp['active']} {text}" + (f" · {cue}" if cue else ""))
    out.append(f"  next by clock: {pick_next(sp)}")
    return out


def set_sense(group, value):
    sp = _need()
    g = _group(sp, group.lower())
    g["sense"] = value
    _save(sp)
    journal.log_delta(f"split sense {g['group']} {value}", gm=True)
    return [f"[split sense {g['group']} {value}]"]


def add_task(group, what, dur):
    sp = _need()
    g = _group(sp, group.lower())
    start = time_of(scene_doc(sp, g["group"]))
    end = gametime.add(start, dur if dur.startswith("+") else "+" + dur)
    sp["tasks"].append({"group": g["group"], "what": what, "dur": dur.lstrip("+"), "start": start, "end": end})
    _save(sp)
    journal.log_delta(f"split task {g['group']}: {what} until {gametime.fmt(end)}")
    return [f"[split task {g['group']}: {what} · {gametime.fmt(start)} → {gametime.fmt(end)}]"]


def _bullets_in(doc, heading):
    span = doc.section(heading)
    return [] if span is None else [doc.body[i] for i in range(span[0] + 1, span[1]) if doc.body[i].strip().startswith("- ")]


def join(a, b):
    import clock
    sp = _need()
    a, b = a.lower(), b.lower()
    ga, gb = _group(sp, a), _group(sp, b)
    if sp["active"] not in (a, b):
        raise SplitError(f"cut to {a} or {b} first (the join happens in the active scene)")
    keep, other = (ga, gb) if sp["active"] == a else (gb, ga)
    state = campaign.load_state()
    od = scene_doc(sp, other["group"])
    here, there = str(state.front.get("party-location") or ""), str(od.front.get("party-location") or "")
    if here.split("/")[0] != there.split("/")[0]:
        raise SplitError(f"{keep['group']} is at {here} and {other['group']} at {there}: "
                         "they must reach the same site first")
    if tempo_of(od) == "combat":
        raise SplitError(f"{other['group']} is mid-fight: cut to it and join from there")
    out = []
    t_keep, t_other = time_of(state), time_of(od)
    gap = gametime.diff(t_other, t_keep)
    if gap < 0:   # the active group is behind: bring it up to the later clock
        lines, _ = clock.advance("+" + gametime.fmt_delta(-gap))
        out += lines
        out.append(f"[split join: summarise {keep['group']}'s last {gametime.fmt_delta(-gap)} for the table]")
        state = campaign.load_state()
    elif gap > 0:
        out.append(f"[split join: summarise {other['group']}'s last {gametime.fmt_delta(gap)} for the table]")
    for heading in ("On stage", "Watch for"):
        have = {line.strip().lower() for line in _bullets_in(state, heading)}
        for line in _bullets_in(od, heading):
            if line.strip().lower() not in have:
                state.append_line(heading, line)
    names = {n.lower() for n in other["pcs"]}
    for d in campaign.pcs():
        if str(d.front.get("name") or "").lower() in names:
            d.set_front("location", here)
            d.save()
    state.save()
    if tempo_of(state) == "combat":
        out.append(f"[split join: {', '.join(_short(n) for n in other['pcs'])} arrive mid-fight — "
                   "ask for their initiative and add them to the Combatants]")
    keep["pcs"] = keep["pcs"] + other["pcs"]
    sp["groups"] = [g for g in sp["groups"] if g["group"] != other["group"]]
    sp["tasks"] = [t for t in sp["tasks"] if t["group"] != other["group"]]
    _remove(parked_path(other["group"]))
    if len(sp["groups"]) == 1:
        _remove(campaign.split_path())
        p = _slice_path()
        if p.exists():
            p.unlink()
        journal.log_delta(f"split join {other['group']} → {keep['group']} · party together again")
        out.insert(0, f"[split join: {_label(keep)} — the party is together again at {here}]")
        return out
    _save(sp)
    journal.log_delta(f"split join {other['group']} → {keep['group']}")
    out.insert(0, f"[split join: {_label(keep)} at {here}]")
    return out


def cmd_split(ctx):
    a = ctx.args
    words = list(a.words)
    head = words[0].lower() if words else "status"
    if head == "cut":
        lines = cut(words[1] if len(words) > 1 else None, a.force)
    elif head == "status":
        lines = status()
    elif head == "sense":
        if len(words) != 3 or words[2].lower() not in ("on", "off", "auto"):
            raise SplitError("split sense <group> on|off|auto")
        lines = set_sense(words[1], words[2].lower())
    elif head == "task":
        if len(words) != 4:
            raise SplitError('split task <group> "<what>" <30m>')
        lines = add_task(words[1], words[2], words[3])
    elif head == "join":
        if len(words) != 3:
            raise SplitError("split join <group> <group>")
        lines = join(words[1], words[2])
    else:
        lines = form(words, a.active)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("split", parents=[g], help="split the party: <g>=PC,… <g>=PC,… | cut | status | sense | task | join")
    p.add_argument("words", nargs="*")
    p.add_argument("--active")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_split)
