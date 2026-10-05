"""Wacky Juice: the per-prompt roll that lets a random on-stage NPC do something
unexpected and funny (docs/design/02 → Wacky Juice; 04 → Campaign file → Wacky Juice;
06 → `gm.py juice` and the brief's "Wacky Juice roll" bullet).

Config is the campaign settings (`campaign.settings()`): `wacky-juice` on|off,
`wacky-juice-value` (percent per eligible prompt), `wacky-juice-cooldown` (prompts).
Hook state is `<campaign>/.gm/juice` (tool scratch, never journaled):
    prompts-since: 3
    pending: tobin-hale
    pending-name: Tobin
`hook_roll()` runs in `brief --hook` on UserPromptSubmit; `consume()` runs at the start
of every `do` / `log`, so a used juice is logged without the GM doing anything.
"""
from pathlib import Path

from . import campaign, journal, md

# conditions that stop a creature from acting (SRD); `hp 0` and `status: dead` too
STOPPED = {"unconscious", "paralyzed", "petrified", "stunned", "incapacitated"}

_suppress = False  # set by `do` while its steps run, so a `log` step doesn't consume twice


def state_path():
    return campaign.root() / ".gm" / "juice"


def load():
    """{'prompts-since': int | None, 'pending': slug | None, 'pending-name': str | None}.
    `prompts-since` None = never fired (no cooldown applies)."""
    out = {"prompts-since": None, "pending": None, "pending-name": None}
    p = state_path()
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "prompts-since":
            out[key] = int(value) if value.isdigit() else None
        elif key in ("pending", "pending-name"):
            out[key] = value or None
    return out


def save(st):
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    since = "" if st["prompts-since"] is None else str(st["prompts-since"])
    md.write_text(p, f"prompts-since: {since}\npending: {st['pending'] or ''}\n"
                     f"pending-name: {st['pending-name'] or ''}\n")


def _int(value, default):
    try:
        return int(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return default


def config(state=None):
    """(on, value 0-100, cooldown >= 0)."""
    s = campaign.settings(state)
    on = str(s["wacky-juice"]).strip().lower() not in ("off", "false", "no", "0")
    value = max(0, min(100, _int(s["wacky-juice-value"], 5)))
    cooldown = max(0, _int(s["wacky-juice-cooldown"], 3))
    return on, value, cooldown


# ---------- who can be juiced ----------

def _stopped(conds, hp_text=None, front=None):
    for c in conds:
        if str(c).split()[0].lower() in STOPPED:
            return True
    if hp_text:
        cur = str(hp_text).split("/")[0].strip()
        if cur.isdigit() and int(cur) == 0:
            return True
    if front:
        hp = front.get("hp")
        if isinstance(hp, dict) and hp.get("current") == 0:
            return True
        if str(front.get("status") or "").lower() == "dead":
            return True
        if any(str(c).split()[0].lower() in STOPPED for c in (front.get("conditions") or []) if str(c).strip()):
            return True
    return False


def eligible(state=None):
    """[(display name, slug or None)] for the NPCs in the scene who can act: the
    non-PC Combatants rows in combat, else the Stage rows / On stage bullets."""
    state = state or campaign.load_state()
    out = []
    combat = state.table("Combatants")
    if combat is not None:
        for row in combat.rows:
            raw = row.get("name", "")
            if "(pc)" in raw.lower() or not raw.strip():
                continue
            if (row.get("side") or "").strip().lower() == "party":
                continue
            conds = [c.strip() for c in (row.get("conditions") or "").split(",")
                     if c.strip() and c.strip() not in ("—", "-")]
            if _stopped(conds, row.get("hp")):
                continue
            ref = (row.get("ref") or "").strip()
            slug = Path(ref).stem if ref.startswith("npcs/") else None
            out.append((raw.strip(), slug))
        return out
    for m in campaign.stage_matches(state):
        if m.is_pc:
            continue
        front = m.doc.front if m.doc is not None else {}
        if _stopped([], None, front):
            continue
        out.append((m.name, m.slug or (Path(m.path).stem if m.path else None)))
    return out


# ---------- the hook roll ----------

def hook_roll(prompt, roller, state=None):
    """Run once per UserPromptSubmit (06 → brief → Wacky Juice roll). Returns the line
    to append to the hook output, or None. Logs a pending juice that no `do`/`log`
    consumed as `(GM) [juice] Name — no turn logged`."""
    state = state or campaign.load_state()
    st = load()
    if st["pending"] or st["pending-name"]:
        # the hook runs inside gm.py's command Batch; this line is not an undoable action
        journal._without_journal(journal.log_delta,
                                 f"[juice] {st['pending-name'] or st['pending']} — no turn logged", gm=True)
        st["pending"] = st["pending-name"] = None
    on, value, cooldown = config(state)
    text = (prompt or "").lstrip()
    if not on or text.startswith(("/", "!")):
        save(st)
        return None
    since = st["prompts-since"]
    if since is not None and since < cooldown:
        st["prompts-since"] = since + 1
        save(st)
        return None
    who = eligible(state)
    if not who:
        save(st)
        return None
    if roller.die(100) > value:
        st["prompts-since"] = None if since is None else since + 1
        save(st)
        return None
    name, slug = roller.rng.choice(who)
    st.update({"prompts-since": 0, "pending": slug or campaign.slugify(name), "pending-name": name})
    save(st)
    return f"Juice: {name} — an unexpected, funny move this turn (02 → Wacky Juice)"


# ---------- consuming it ----------

def consume():
    """Log `(GM) [juice] Name` for a pending juice and clear it. Returns the name or None.
    No-op while a `do` batch has suppressed it, or outside a campaign with no state."""
    if _suppress:
        return None
    try:
        st = load()
    except Exception:
        return None
    if not (st["pending"] or st["pending-name"]):
        return None
    name = st["pending-name"] or st["pending"]
    journal.log_delta(f"[juice] {name}", gm=True)
    st["pending"] = st["pending-name"] = None
    save(st)
    return name


def waive():
    """Clear a pending juice as waived. Returns the name, or None when nothing pending."""
    st = load()
    if not (st["pending"] or st["pending-name"]):
        return None
    name = st["pending-name"] or st["pending"]
    journal.log_delta(f"[juice] {name} — waived", gm=True)
    st["pending"] = st["pending-name"] = None
    save(st)
    return name


def session_counts():
    """{'used', 'waived', 'unlogged'} from `(GM) [juice] …` lines in the current log."""
    p = campaign.session_log_path()
    counts = {"used": 0, "waived": 0, "unlogged": 0}
    if not p.exists():
        return counts
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("- (GM) [juice] "):
            continue
        if line.endswith("— waived"):
            counts["waived"] += 1
        elif line.endswith("— no turn logged"):
            counts["unlogged"] += 1
        else:
            counts["used"] += 1
    return counts
