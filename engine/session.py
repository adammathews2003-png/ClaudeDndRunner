"""`gm.py session start | archive --summary-file F [--force] [--no-commit]` (docs/design/06 →
`gm.py session archive`; 04 → Session log, Table rules; 01 → Session lifecycle; 05 #4;
plan.md Phase 7 item 5).

`start` sets `in-session: true` (turns the brief hook on; `/gm` runs it). It prints a
`[MECHANICS] read rules/mechanics/<name>.md` line for each `mechanics:` entry in campaign.md,
every session. At the campaign's first start (no session history, how-to-play not yet given)
it also prints the campaign-start block (02 → Campaign start, decided 2026-10-11): `[CAMPAIGN
START]`, the title card ("Our tale begins", logged as `[intro] curtain raised` so `intro`
doesn't repeat it), `[PITCH]` (name, tone, length, level, party size), `[PREGENS]` (unclaimed
PCs) and the `[OPENING QUESTIONS]` the GM asks in one message instead of the roster check.

`archive` is the mechanics of `/end-session`:
1. a full `lint` (refuses on errors unless `--force`),
2. ends `session`-scoped table rules; ended rule rows move into the history file,
3. writes `sessions/history/session-NN.md`: the model's summary (`--summary-file`), the
   public changes (every `  - ` delta that isn't `(GM)`), the behind-the-screen lines,
   the ended table rules, and the raw turn log (for `trace`),
4. resets `sessions/session-current.md` (`sessions/spoilers.md` is never reset),
5. clears `in-session` (a split party stays split: `## Split at session end` records
   each group, and the next `session start` says which group to open with),
6. `git add -A && git commit -m "session NN"` in the campaign's own repository (the
   campaign folder is the repo root). A campaign folder without its own repo is never
   committed, so the engine repo around it is never touched (`--no-commit` skips it).
"""
import re
import subprocess
from pathlib import Path

from lib import campaign, journal, md
from lib import lint as checks
from lib.errors import ToolError
import rules

LOG_HEADER = """# Session log — current

<!-- Written by gm.py (docs/design/06), not by hand. Each mutation adds a delta line to the
open turn; `gm.py log "..."` writes the summary and closes it:
[turn N] summary
  - delta
  - (GM) delta players must not hear (secret rolls, off-screen moves, fired clocks)
  - [overrule] ... / [spoilers] ...
/end-session (gm.py session archive) files this as sessions/history/session-NN.md and resets it. -->

(no turns yet — new session)
"""


class SessionError(ToolError):
    pass


def start():
    state = campaign.load_state()
    state.set_front("in-session", True)
    state.save()
    journal.log_delta("session start")
    out = ["[session start · in-session: true · the brief hook is on]"]
    import split
    split.reset_slice()
    line = split.resume_line()
    if line:
        out.append(line)
    out += mechanics_lines()
    if is_campaign_start():
        out += campaign_start_lines()
    return out, {}


def mechanics_lines():
    """`[MECHANICS] read rules/mechanics/<name>.md` per campaign.md `mechanics:` entry."""
    p = campaign.campaign_doc_path()
    if not p.exists():
        return []
    names = md.load(p).front.get("mechanics") or []
    if isinstance(names, str):
        names = [x.strip() for x in names.strip("[]").split(",")]
    out = []
    rules_dir = Path(__file__).resolve().parent.parent / "rules" / "mechanics"
    for name in (str(x).strip() for x in names):
        if not name:
            continue
        f = rules_dir / f"{name}.md"
        out.append(f"[MECHANICS] read rules/mechanics/{name}.md now and follow it all session"
                   if f.exists() else f"[MECHANICS] {name}: no rules/mechanics/{name}.md; run it from campaign.md")
    return out


def is_campaign_start():
    """The campaign's first session, before the how-to-play talk: no history yet."""
    import intro
    return intro.sessions_played() == 0 and not intro._given()


CURTAIN = "[intro] curtain raised"


def campaign_start_lines():
    import intro
    from lib import banner
    out = ["[CAMPAIGN START] first time this campaign is opened: run the gm skill's Campaign start, "
           "not the roster check (no \"since last time\": nothing has happened yet)"]
    out += banner.card(intro.title(), "Our tale begins")
    log = campaign.session_log_path()
    if not log.exists() or CURTAIN not in log.read_text(encoding="utf-8"):
        journal.log_delta(CURTAIN)
    p = campaign.campaign_doc_path()
    front = md.load(p).front if p.exists() else {}
    bits = [str(front.get("name") or intro.title())]
    for key, fmt in (("tone", "{}"), ("length", "{}"), ("start-level", "level {}"), ("players", "{} players")):
        if front.get(key) not in (None, ""):
            bits.append(fmt.format(front[key]))
    out.append("[PITCH] " + " · ".join(bits))
    pregens = [str(d.front.get("name")) for d in campaign.pcs() if not campaign.player_of(d)]
    if pregens:
        out.append("[PREGENS] " + ", ".join(pregens))
    out.append("[OPENING QUESTIONS] (one message) who's playing (player names) · anyone want an NPC "
               "companion to round out the party? · build your own character or take a pregen?")
    bf = campaign.boundaries_front()
    if "lines" not in bf and "veils" not in bf:
        out.append("[OPENING QUESTIONS] + lines and veils: anything you never want in the game, or want "
                   "kept off screen? (`campaign boundaries ...`; `!x` any time)")
    return out


def _history_dir():
    return campaign.root() / "sessions" / "history"


def next_number():
    d = _history_dir()
    nums = [int(m.group(1)) for p in d.glob("session-*.md") if (m := re.match(r"session-(\d+)", p.stem))] \
        if d.is_dir() else []
    return (max(nums) + 1) if nums else 1


def _log_lines():
    p = campaign.session_log_path()
    if not p.exists():
        return []
    doc = md.load(p)
    body, out, in_comment = doc.body, [], False
    for line in body:
        if line.strip().startswith("<!--"):
            in_comment = "-->" not in line
            continue
        if in_comment:
            in_comment = "-->" not in line
            continue
        if line.startswith("# ") or re.match(r"^\(no turns yet", line.strip()):
            continue
        out.append(line)
    while out and not out[0].strip():
        out.pop(0)
    return out


def _git_root(path):
    try:
        r = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def archive(summary_file=None, summary=None, force=False, commit=True):
    found = checks.run()
    errs = [f for f in found if f.level == "error"]
    lines = checks.summary(found)
    if errs and not force:
        raise SessionError("session archive: lint found errors — fix them or --force\n" + "\n".join(lines))
    if summary_file:
        p = Path(summary_file)
        if not p.is_absolute():
            p = campaign.root() / summary_file if (campaign.root() / summary_file).exists() else p
        summary = p.read_text(encoding="utf-8").strip()
    if not summary:
        raise SessionError("session archive: give --summary-file (the half-page summary the GM wrote)")
    lines += rules.end_scope("session")
    n = next_number()
    log = _log_lines()
    public = [line.strip() for line in log if line.startswith("  - ") and not line.startswith("  - (GM)")]
    secret = [line.strip() for line in log if line.startswith("  - (GM)")]
    # ended table rules move into the history
    ended_rows = []
    rp = campaign.root() / "state" / "table-rules.md"
    if rp.exists():
        rdoc = md.load(rp)
        t = rdoc.table("Table rules")
        if t is not None:
            for i in range(len(t.rows) - 1, -1, -1):
                r = t.rows[i]
                if r.get("status", "").lower().startswith("ended"):
                    ended_rows.insert(0, r)
                    t.remove(i)
            if ended_rows:
                rdoc.save()
    state = campaign.load_state()
    when = state.front.get("in-game-datetime", "")
    out = [f"# Session {n:02d}", f"<!-- Archived by gm.py session archive at {when}. Errata are appended below; "
                                 "the original text is never edited. -->", "", "## Summary", summary, "",
           "## Changes (public deltas)"]
    out += public or ["(none)"]
    out += ["", "## Behind the screen (GM)"] + (secret or ["(none)"])
    if ended_rows:
        cols = ["id", "rule", "key", "scope", "since", "status"]
        out += ["", "## Table rules ended", "| " + " | ".join(cols) + " |",
                "|" + "|".join("-" * (len(c) + 2) for c in cols) + "|"]
        out += ["| " + " | ".join(r.get(c, "") for c in cols) + " |" for r in ended_rows]
    import split
    sp = split.load()
    if sp is not None:   # the split carries over to the next session (02 → Splitting the party)
        out += ["", "## Split at session end"] + split.group_bullets(sp)
        split.reset_slice()
    out += ["", "## Turn log"] + (log or ["(empty)"]) + [""]
    hist = _history_dir() / f"session-{n:02d}.md"
    hist.parent.mkdir(parents=True, exist_ok=True)
    md.new(hist, "\n".join(out)).save()
    md.new(campaign.session_log_path(), LOG_HEADER).save()
    state = campaign.load_state()
    state.set_front("in-session", False)
    state.save()
    lines.append(f"[session {n:02d} archived → sessions/history/session-{n:02d}.md · {len(public)} changes · "
                 f"{len(secret)} GM lines · log reset · in-session off"
                 + (f" · still split ({len(sp['groups'])} groups, resumes next session)" if sp else "") + "]")
    if commit:
        root = _git_root(campaign.root())
        own = root and Path(root).resolve() == Path(campaign.root()).resolve()
        if root and not own:
            lines.append("[git: the campaign folder isn't its own repository — nothing committed]")
        elif root:
            r1 = subprocess.run(["git", "-C", root, "add", "-A"], capture_output=True, text=True)
            r2 = subprocess.run(["git", "-C", root, "commit", "-q", "-m", f"session {n:02d}"],
                                capture_output=True, text=True)
            if r1.returncode == 0 and r2.returncode == 0:
                lines.append(f"[git: committed \"session {n:02d}\"]")
            else:
                lines.append(f"[git: commit failed — {(r2.stderr or r1.stderr).strip()[:200]}]")
        else:
            lines.append("[git: not a repository — nothing committed]")
    return lines, {"number": n, "path": str(hist)}


def cmd_session(ctx):
    a = ctx.args
    if a.action == "start":
        lines, data = start()
    else:
        lines, data = archive(a.summary_file, a.summary, a.force, not a.no_commit)
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("session", parents=[g], help="session start | archive --summary-file F")
    p.add_argument("action", choices=["start", "archive"])
    p.add_argument("--summary-file")
    p.add_argument("--summary", help="the summary text inline (instead of --summary-file)")
    p.add_argument("--force", action="store_true", help="archive despite lint errors")
    p.add_argument("--no-commit", action="store_true")
    p.set_defaults(func=cmd_session)
