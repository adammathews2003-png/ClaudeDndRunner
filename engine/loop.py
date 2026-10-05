"""`gm.py loop start|reset|status` — the time-loop mechanic (docs/design/07 → Time loop; 06 →
`gm.py loop`; 04 → Time-loop campaigns; plan.md Phase 11 item 3). Only in campaigns whose
`campaign.md` lists `mechanics: [time-loop]`.

    loop start [--at "Day 1 06:00"] [--end "Day 2 00:00"] [--bed site/area]
    loop reset --by death|sleep|time
    loop status

- `start` at the loop day's first moment: sets the clock to `loop-start`, puts each PC in
  their `loop-bed` (`--bed`, else the PC's `loop-bed:`, else where they are), commits
  the repository, and records `loop-baseline: <sha>`, `loop: 1`, `loop-start`, `loop-end`
  in `current.md`.
- `reset` restores every file under `locations/`, `npcs/`, `scenarios/`, `tables/` and
  `state/current.md` from the baseline (`git checkout <sha> -- …`), re-applies the loop
  keys, sets the clock to `loop-start`, wakes the PCs in their `loop-bed` at full HP, full
  hit dice and resources, no conditions; increments `loop`; marks a regenerated
  `kind: campaign` Loot row whose item a PC still carries as `duplicate; hollow`; restocks
  `restock: loop` merchants; appends the `state/loops.md` row (learned = the turn
  summaries since the last reset, gained = item/coin/xp deltas); logs `(GM) loop N reset
  (by)` and a public `[loop]` line. **Never touches** `pcs/` (beyond waking them),
  `state/loops.md` (except its new row), `sessions/`, `campaign.md`. Files created after
  the baseline (stubs) stay: improvised canon is part of the world, not of the day.
- `clock advance` reaching `loop-end` runs `reset --by time`.
"""
import re
import subprocess

from lib import campaign, gametime, journal, md
from lib.errors import ToolError
import session

PATHS = ("locations", "npcs", "scenarios", "tables", "state/current.md")
LOOP_KEYS = ("loop", "loop-baseline", "loop-start", "loop-end")


class LoopError(ToolError):
    pass


def mechanics():
    p = campaign.campaign_doc_path()
    front = md.load(p).front if p.exists() else campaign.load_state().front
    v = front.get("mechanics") or []
    return [str(x).strip() for x in (v if isinstance(v, list) else [v])]


def is_loop_campaign():
    return "time-loop" in mechanics()


def _require():
    if not is_loop_campaign():
        raise LoopError("loop: this campaign has no time loop (campaign.md mechanics: [time-loop])")


def _git(root, *args):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise LoopError(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout.strip()


def _repo():
    root = session._git_root(campaign.root())
    if not root:
        raise LoopError("loop: the campaign must be inside a git repository (the baseline is a commit)")
    rel = campaign.root().resolve().relative_to(__import__("pathlib").Path(root).resolve()).as_posix()
    return root, rel


def _bed(doc, override=None):
    return override or str(doc.front.get("loop-bed") or doc.front.get("location") or "")


def start(at=None, end=None, bed=None):
    _require()
    root, rel = _repo()
    state = campaign.load_state()
    t0 = at or str(state.front.get("loop-start") or "Day 1 06:00")
    t1 = end or str(state.front.get("loop-end") or "Day 2 00:00")
    gametime.parse(t0)
    gametime.parse(t1)
    if bed:
        import mutations
        bed = mutations.validate_location(bed)
    first_bed = None
    for d in campaign.pcs():
        b = _bed(d, bed)
        d.set_front("loop-bed", b)
        d.set_front("location", b)
        d.save()
        first_bed = first_bed or b
    state = campaign.load_state()
    state.set_front("in-game-datetime", t0)
    state.set_front("loop", 1)
    state.set_front("loop-start", t0)
    state.set_front("loop-end", t1)
    if first_bed:
        state.set_front("party-location", first_bed)
    state.save()
    _git(root, "add", "-A")
    status = subprocess.run(["git", "-C", root, "diff", "--cached", "--quiet"])
    if status.returncode != 0:
        _git(root, "commit", "-q", "-m", f"loop baseline ({rel})")
    sha = _git(root, "rev-parse", "--short=12", "HEAD")
    state = campaign.load_state()
    state.set_front("loop-baseline", sha)
    state.save()
    journal.log_delta(f"(loop) loop 1 begins {t0} · baseline {sha}", gm=True)
    journal.log_delta(f"[loop] the day begins: {t0}")
    return [f"[loop start · loop 1 · {t0} → {t1} · baseline {sha} · PCs in {first_bed or '?'}]"]


def _since_last_reset():
    """(turn summaries, gained deltas) in the session log after the last [loop] line."""
    p = campaign.session_log_path()
    lines = md.load(p).body if p.exists() else []
    start_i = 0
    for i, line in enumerate(lines):
        if "[loop]" in line:
            # the turn holding the [loop] line: its summary (written later by `log`) is
            # above it, and describes this loop's events
            j = i
            while j > 0 and not lines[j].startswith("[turn "):
                j -= 1
            start_i = j
    learned, gained = [], []
    for line in lines[start_i:]:
        m = re.match(r"^\[turn \d+\]\s+(.+)$", line)
        if m:
            learned.append(m.group(1).strip())
        elif re.match(r"^\s+- (item .+ \+|coin .+→|XP \+)", line):
            gained.append(line.strip()[2:])
    return learned, gained


def _cell(items, limit=300):
    text = "; ".join(items) or "—"
    text = text.replace("|", "/")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _carried_text():
    out = []
    for d in campaign.pcs():
        span = d.section("Inventory")
        out.append(" ".join(d.body[span[0] + 1:span[1]]).lower() if span else "")
    return " ".join(out)


def _mark_hollow():
    carried = _carried_text()
    marked = []
    for p in sorted((campaign.root() / "locations").glob("*.md")):
        doc = md.load(p)
        t = doc.table("Loot")
        if t is None:
            continue
        changed = False
        for i, r in enumerate(t.rows):
            if r.get("kind", "").strip().lower() != "campaign":
                continue
            name = re.sub(r"\s*\([^)]*\)", "", r.get("item", "")).strip().lower()
            if len(name) >= 3 and name in carried and "hollow" not in r.get("notes", "").lower():
                notes = r.get("notes", "").strip()
                t.set(i, "notes", (notes + "; " if notes else "") + "duplicate; hollow")
                marked.append(r.get("item"))
                changed = True
        if changed:
            doc.save()
    return marked


def reset(by):
    _require()
    if by not in ("death", "sleep", "time"):
        raise LoopError("loop reset --by death|sleep|time")
    state = campaign.load_state()
    sha = str(state.front.get("loop-baseline") or "")
    n = state.front.get("loop")
    if not isinstance(n, int) or n < 1 or not sha or sha == "pending":
        raise LoopError("loop reset: the loop hasn't started (gm.py loop start)")
    root, rel = _repo()
    keep = {k: state.front.get(k) for k in LOOP_KEYS + ("in-session",)}
    # the ledger row, from this loop's log
    learned, gained = _since_last_reset()
    lp = campaign.root() / "state" / "loops.md"
    if lp.exists():
        ldoc = md.load(lp)
        t = ldoc.table("Loop") or ldoc.table("loop")
        if t is not None:
            t.append({"loop": str(n), "ended by": by, "learned": _cell(learned), "gained": _cell(gained),
                      "notes": ""})
            ldoc.save()
    # restore the world
    paths = []
    for sub in PATHS:
        spec = f"{rel}/{sub}" if rel != "." else sub
        ok = subprocess.run(["git", "-C", root, "cat-file", "-e", f"{sha}:{spec}"], capture_output=True)
        if ok.returncode == 0:
            paths.append(spec)
    if paths:
        _git(root, "checkout", sha, "--", *paths)
    state = campaign.load_state()
    for k, v in keep.items():
        if v is not None:
            state.set_front(k, v)
    state.set_front("loop", n + 1)
    t0 = str(keep.get("loop-start") or state.front.get("loop-start"))
    state.set_front("in-game-datetime", t0)
    first_bed = None
    for d in campaign.pcs():
        b = _bed(d)
        hp = dict(d.front.get("hp") or {})
        hp.pop("temp", None)
        if "max" in hp:
            hp["current"] = hp["max"]
        d.set_front("hp", hp)
        d.set_front("conditions", [])
        d.set_front("location", b)
        hd = dict(d.front.get("hit-dice") or {})
        if hd:
            hd["left"] = int(d.front.get("level") or hd.get("left") or 1)
            d.set_front("hit-dice", hd)
        rt = d.table("Resources")
        for i, r in enumerate(rt.rows if rt else []):
            if r.get("recovers", "").strip().lower() in ("long", "short", "turn") and r.get("max"):
                rt.set(i, "current", r["max"])
        d.save()
        first_bed = first_bed or b
    if first_bed:
        state.set_front("party-location", first_bed)
    state.save()
    hollow = _mark_hollow()
    import loot
    restocked = loot.restock_all({"loop"})
    journal.log_delta(f"(loop) loop {n} reset ({by})", gm=True)
    journal.log_delta(f"[loop] the day begins again: loop {n + 1}, {t0}")
    out = [f"[loop reset · loop {n} ended by {by} · loop {n + 1} begins {t0} · PCs in {first_bed or '?'}"
           + (f" · hollow: {', '.join(hollow)}" if hollow else "")
           + (f" · restocked: {', '.join(restocked)}" if restocked else "") + "]"]
    return out


def status():
    _require()
    state = campaign.load_state()
    n = state.front.get("loop")
    now = state.front.get("in-game-datetime")
    end = state.front.get("loop-end")
    left = ""
    try:
        left = gametime.fmt_delta(gametime.diff(gametime.parse(now), gametime.parse(end)))
    except gametime.TimeError:
        pass
    out = [f"[LOOP {n} · {now} · {left} until the reset at {end} · baseline {state.front.get('loop-baseline')}]"]
    lp = campaign.root() / "state" / "loops.md"
    if lp.exists():
        t = md.load(lp).table("Loop") or md.load(lp).table("loop")
        for r in (t.rows if t else [])[-3:]:
            out.append(f"  loop {r.get('loop')} ({r.get('ended by')}): learned {r.get('learned')} · gained {r.get('gained')}")
    return out


def cmd_loop(ctx):
    a = ctx.args
    if a.action == "start":
        lines = start(a.at, a.end, a.bed)
    elif a.action == "reset":
        if not a.by:
            raise LoopError("loop reset --by death|sleep|time")
        lines = reset(a.by)
    else:
        lines = status()
    for line in lines:
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("loop", parents=[g], help="loop start|reset --by …|status (time-loop campaigns)")
    p.add_argument("action", choices=["start", "reset", "status"])
    p.add_argument("--by", choices=["death", "sleep", "time"])
    p.add_argument("--at")
    p.add_argument("--end")
    p.add_argument("--bed")
    p.set_defaults(func=cmd_loop)
