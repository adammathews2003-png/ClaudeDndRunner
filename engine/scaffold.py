"""`gm.py scaffold <slug> --area "<starting area name>" [--type settlement] [--start "Day 1 08:00"]
[--activate]` — a new, empty, valid campaign folder (docs/design/02 → `/new-campaign`; 04 →
every file format; plan.md Phase 9). Phase 11's `campaign new` builds on this.

Creates `dnd-adventure/campaigns/<slug>/` — its own git repository (`.gitignore`
for `.gm/`, an initial commit) — with `locations/` (the starting area file and
`world.md` with the area at (0,0,0), via `world init`), `npcs/`, `pcs/_template.md`,
`scenarios/`, `tables/`, `sessions/{session-current.md, spoilers.md, history/}`,
`state/{current.md, table-rules.md}`. `--activate` writes `campaigns/.active`.
Refuses if the folder exists. Runs lint on the result.
"""
import subprocess
from pathlib import Path

from lib import campaign, md
from lib import lint as checks
from lib.errors import ToolError
import session
import spoil
import world

STATE = """---
campaign: {slug}
in-game-datetime: "{start}"
party-location: {area}
scene: "Arrival"
light: bright                     # bright | dim | dark
in-session: false                 # /gm sets true (turns on the brief hook)
dice-mode: players-roll-d20s      # players-roll-d20s | gm-rolls-all
---

# Current scene

## Summary
(the opening scene: write it with `scene enter {area} --write --summary "…"`)

## On stage
(nobody)

## Watch for
(nothing yet)

## Clocks
(none)

## Tempo: calm  <!-- calm | tense | combat — see docs/design/01, Scene tempo -->

## Combat
(not in combat)
"""

RULES = """# Table rules
<!-- Active /overrule rules (docs/design/02 → Overrule; written by gm.py rule).
     Precedence: these > rules/house-rules.md > RAW. -->

| id | rule | key | scope | since | status |
|----|------|-----|-------|-------|--------|
"""

AREA = """---
name: {name}
tier: area
type: {type}
parent: world
tags: []
---

# {name}

## Description
(what you see coming in; the lay of the land)

## Hidden
(none yet)

## Frame
origin (0,0,0) = the centre of {name} · +x east · +y north · +z up · ft

## Places
| id | glyph | feature | at | from | to | effect | ref | source |
|----|-------|---------|----|------|----|--------|-----|--------|

## Routes
| id | from | to | via | kind | access | time | notes |
|----|------|----|-----|------|--------|------|-------|

## Notes / current state
(none yet)
"""


class ScaffoldError(ToolError):
    pass


def scaffold(slug, area_name, type_="settlement", start="Day 1 08:00", activate=False):
    slug = campaign.slugify(slug)
    root = campaign.CAMPAIGNS / slug
    if root.exists():
        raise ScaffoldError(f"scaffold: {root} already exists")
    area = campaign.slugify(area_name)
    for d in ("locations", "npcs", "pcs", "scenarios", "tables", "sessions/history", "state", ".gm"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "sessions" / "history" / ".gitkeep").write_text("", encoding="utf-8")
    old = campaign._override
    campaign.set_override(str(root))   # every write below lands inside the new campaign
    try:
        tpl = Path(__file__).resolve().parent / "templates" / "pc.md"
        if tpl.exists():
            text = tpl.read_text(encoding="utf-8").replace("location: crossroads-inn/common-room",
                                                           f"location: {area}")
            md.new(root / "pcs" / "_template.md", text).save()
        md.new(root / "state" / "current.md", STATE.format(slug=slug, start=start, area=area)).save()
        md.new(root / "state" / "table-rules.md", RULES).save()
        md.new(root / "sessions" / "session-current.md", session.LOG_HEADER).save()
        md.new(root / "sessions" / "spoilers.md", spoil.HEADER).save()
        md.new(root / "locations" / f"{area}.md", AREA.format(name=area_name, type=type_)).save()
        world.init(area)
        found = checks.run()
    finally:
        campaign.set_override(old)
    git_init(root, f"new campaign {slug}")
    if activate:
        campaign.CAMPAIGN_FILE.parent.mkdir(parents=True, exist_ok=True)
        campaign.CAMPAIGN_FILE.write_text(slug + "\n", encoding="utf-8")
    errs = [f for f in found if f.level == "error"]
    lines = [f"[scaffold: {slug}/ · starting area {area} (area) · world.md with {area} at (0,0,0)"
             + (" · active" if activate else "") + " · own git repo]",
             f"[LINT] {len(errs)} errors · {len(found) - len(errs)} warnings"]
    return lines


GITIGNORE = ".gm/\n__pycache__/\n"


def git_init(root, message):
    """Make a campaign folder its own repository (no-op if it already is one)."""
    root = Path(root)
    if not (root / ".gitignore").exists():
        (root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    if (root / ".git").exists():
        return
    try:
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
        # the engine repo's own identity (never fall back to a global work identity)
        for key in ("user.name", "user.email"):
            r = subprocess.run(["git", "-C", str(campaign.BASE), "config", "--local", key],
                               capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                subprocess.run(["git", "-C", str(root), "config", key, r.stdout.strip()], capture_output=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", message], capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pass   # no git: the campaign still works; archive and loop will say so


def cmd_scaffold(ctx):
    a = ctx.args
    if not a.area:
        raise ScaffoldError('scaffold <slug> --area "<starting area name>"')
    for line in scaffold(a.slug, a.area, a.type, a.start, a.activate):
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("scaffold", parents=[g], help='scaffold <slug> --area "<name>" [--activate]')
    p.add_argument("slug")
    p.add_argument("--area")
    p.add_argument("--type", default="settlement")
    p.add_argument("--start", default="Day 1 08:00")
    p.add_argument("--activate", action="store_true")
    p.set_defaults(func=cmd_scaffold)
