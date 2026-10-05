"""`gm.py campaign new|fill|status|ledger` — maintains `<campaign>/campaign.md`
(planning/07 → Parameters, Reveal policy, Fill-in queue and author ledger; 06 → `gm.py
campaign`; plan.md Phase 11 item 4). The generation itself is skill work in a forked
context (`/campaign-new`, `/campaign-scenario`), never a tool.

    campaign new <slug> --area "<starting area>" [--set length=3-5 start-level=3 difficulty=hard shape=mystery …]
                 [--seed-file <path>] [--activate]         # scaffold (if new) + campaign.md + campaign-seed.md
    campaign fill <F1> "<answer>"                          # closes a fill-in row; answers are promises
    campaign fill --add "<question>" --default "<default>" # the generator queues one
    campaign status [--level shape-only|fill-in|outline|full]
    campaign ledger add "<what the driver was told>" --via <skill>

`status` prints only what the reveal level allows: shape-only = settings, the
player-safe premise, known places and frontier leads; fill-in adds the queue; outline
adds scenario titles and faction names; full adds the author notes. Never the truth
below that level.
"""
import datetime as _dt
import re
import shutil
from pathlib import Path

from lib import campaign, geo, md
from lib.errors import ToolError
from lib import journal
import scaffold

DEFAULTS = [
    ("name", ""), ("slug", ""), ("length", "3-5 sessions"), ("start-level", 1), ("players", "up to 4"),
    ("difficulty", "medium"), ("shape", "mystery"), ("secondary", []), ("tone", "adventurous"),
    ("weirdness", 2), ("jokes", 2), ("references", "none"), ("sidekick", "none"),
    ("advancement", "milestone"), ("xp-tracking", "on"), ("xp-absent", "full"),
    ("wacky-juice", "on"), ("wacky-juice-value", 5), ("wacky-juice-cooldown", 3),
    ("reveal-policy", "shape-only"), ("mechanics", []), ("seed-file", "campaign-seed.md"),
    ("status", "outlined"),
]
CHOICES = {
    "difficulty": ("easy", "medium", "hard", "deadly"),
    "shape": ("journey", "boss", "macguffin", "mystery", "sandbox", "heist", "siege"),
    "reveal-policy": ("shape-only", "fill-in", "outline", "full", "paired"),
    "status": ("outlined", "generated", "in-play", "finished"),
    "references": ("none", "light", "heavy"),
    "sidekick": ("none", "orphan", "animal", "either"),
    "advancement": ("milestone", "xp"),
}
LEVELS = ("shape-only", "fill-in", "outline", "full")
BODY = """
# {name}

## Premise (player-safe)
(written by the generator: what the players hear before the first session)

## Author notes (GM-only)
(the generator's notes: the truth's shape, arcs, what's left open)

## Reveal exceptions
(none)

## Fill-in queue
| id | question | default | status |
|----|----------|---------|--------|

## Author ledger
| when | what the driver was told | via |
|------|--------------------------|-----|
"""


class CampaignCmdError(ToolError):
    pass


def _value(k, v):
    if k in ("secondary", "mechanics"):
        return [x.strip() for x in re.split(r"[,;]", v.strip("[]")) if x.strip()]
    if k in ("start-level", "weirdness", "jokes", "wacky-juice-value", "wacky-juice-cooldown"):
        return int(v)
    if k in CHOICES and v not in CHOICES[k]:
        raise CampaignCmdError(f"campaign: {k} is one of {' | '.join(CHOICES[k])} (got {v!r})")
    return v


def new(slug, area=None, sets=(), seed_file=None, activate=False):
    slug = campaign.slugify(slug)
    root = campaign.BASE / slug
    lines = []
    if not root.exists():
        if not area:
            raise CampaignCmdError('campaign new: a new folder needs --area "<starting area>"')
        lines += scaffold.scaffold(slug, area, activate=activate)
    if (root / "campaign.md").exists():
        raise CampaignCmdError(f"campaign new: {slug}/campaign.md already exists")
    vals = dict(DEFAULTS)
    vals["slug"] = slug
    vals["name"] = slug.replace("-", " ").title()
    for item in sets or []:
        k, sep, v = item.partition("=")
        if not sep or k.strip() not in vals:
            raise CampaignCmdError(f"campaign new: unknown setting {item!r} ({', '.join(vals)})")
        vals[k.strip()] = _value(k.strip(), v.strip())
    head = ["---"] + [f"{k}: {md.fmt_value(v)}" if md.fmt_value(v) != "" else f"{k}:" for k, v in vals.items()] + ["---"]
    old = campaign._override
    campaign.set_override(str(root))
    try:
        md.new(root / "campaign.md", "\n".join(head) + "\n" + BODY.format(name=vals["name"])).save()
        if seed_file:
            src = Path(seed_file)
            if not src.exists():
                raise CampaignCmdError(f"campaign new: no seed file {seed_file}")
            md.new(root / "campaign-seed.md", src.read_text(encoding="utf-8")).save()
        if "time-loop" in vals["mechanics"]:
            st = campaign.load_state()
            for k, v in (("loop", 0), ("loop-baseline", "pending"), ("loop-start", "Day 1 06:00"),
                         ("loop-end", "Day 2 00:00")):
                if k not in st.front:
                    st.set_front(k, v)
            st.save()
            lp = root / "state" / "loops.md"
            if not lp.exists():
                md.new(lp, "# Loop ledger\n<!-- One row per reset, appended by gm.py loop reset. -->\n\n"
                           "| loop | ended by | learned | gained | notes |\n"
                           "|------|----------|---------|--------|-------|\n").save()
        journal.log_delta(f"campaign new {slug} ({vals['shape']}, {vals['difficulty']}, L{vals['start-level']})")
    finally:
        campaign.set_override(old)
    lines.append(f"[campaign new: {slug}/campaign.md · {vals['length']} · start L{vals['start-level']} · "
                 f"{vals['difficulty']} {vals['shape']} · reveal {vals['reveal-policy']}"
                 + (f" · mechanics {', '.join(vals['mechanics'])}" if vals["mechanics"] else "") + "]")
    return lines


def _doc():
    p = campaign.campaign_doc_path()
    if not p.exists():
        raise CampaignCmdError("campaign: this campaign has no campaign.md (gm.py campaign new)")
    return md.load(p)


def fill(rid=None, answer=None, add=None, default=""):
    doc = _doc()
    t = doc.table("Fill-in queue")
    if t is None:
        raise CampaignCmdError("campaign fill: campaign.md has no ## Fill-in queue table")
    if add:
        n = 1 + max([int(re.sub(r"\D", "", r.get("id", "0")) or 0) for r in t.rows] or [0])
        t.append({"id": f"F{n}", "question": add.replace("|", "/"), "default": default.replace("|", "/"),
                  "status": "open"})
        doc.save()
        return f"[campaign fill: F{n} queued]"
    i = t.find("id", rid.upper())
    if i < 0:
        raise CampaignCmdError(f"campaign fill: no row {rid}")
    ans = (answer or "").strip() or t.rows[i].get("default", "")
    t.set(i, "status", f"answered: {ans}".replace("|", "/"))
    doc.save()
    journal.log_delta(f"campaign fill {rid.upper()}: {ans}")
    return f"[campaign fill {rid.upper()}: {ans}]"


def ledger(what, via):
    doc = _doc()
    t = doc.table("Author ledger")
    if t is None:
        raise CampaignCmdError("campaign ledger: campaign.md has no ## Author ledger table")
    t.append({"when": _dt.date.today().isoformat(), "what the driver was told": what.replace("|", "/"),
              "via": via})
    doc.save()
    return f"[campaign ledger: {what} (via {via})]"


def _section_text(doc, heading):
    span = doc.section(heading)
    if span is None:
        return ""
    return "\n".join(line for line in doc.body[span[0] + 1:span[1]] if not line.strip().startswith("<!--")).strip()


def status(level=None):
    doc = _doc()
    f = doc.front
    level = level or ("full" if f.get("reveal-policy") == "full" else
                      f.get("reveal-policy") if f.get("reveal-policy") in LEVELS else "shape-only")
    if level not in LEVELS:
        raise CampaignCmdError(f"campaign status --level {' | '.join(LEVELS)}")
    k = LEVELS.index(level)
    out = [f"[CAMPAIGN] {f.get('name')} · {f.get('length')} · start L{f.get('start-level')} · {f.get('players')} · "
           f"{f.get('difficulty')} · {f.get('shape')}" + (f" + {', '.join(f.get('secondary') or [])}" if f.get("secondary") else "")
           + f" · {f.get('tone')} · status {f.get('status')} · shown at: {level}"]
    out.append("Premise: " + (_section_text(doc, "Premise").replace("\n", " ") or "—"))
    try:
        w = geo.load("world")
        out.append("Known places: " + (", ".join(p.feature for p in w.places if not p.secret) or "—"))
        t = w.doc.table("Known")
        if t is not None and t.rows:
            out.append("Heard of: " + ", ".join(r.get("feature", "") for r in t.rows))
        t = w.doc.table("Frontier")
        if t is not None and t.rows:
            out.append("Frontier: " + ", ".join(f"{r.get('known as')} ({r.get('heading')})" for r in t.rows))
    except geo.GeoError:
        pass
    if k >= 1:
        t = doc.table("Fill-in queue")
        for r in (t.rows if t else []):
            out.append(f"  {r.get('id')} {r.get('question')} — default: {r.get('default')} · {r.get('status')}")
    if k >= 2:
        scen = sorted(p.stem for p in (campaign.root() / "scenarios").glob("*.md"))
        out.append("Scenarios: " + (", ".join(scen) or "—"))
        facs = set()
        for p in (campaign.root() / "npcs").glob("*.md"):
            fa = str(md.load(p).front.get("faction") or "").strip()
            if fa and fa.lower() not in ("none", "—"):
                facs.add(fa)
        out.append("Factions: " + (", ".join(sorted(facs)) or "—"))
    if k >= 3:
        out.append("Author notes: " + (_section_text(doc, "Author notes").replace("\n", " ") or "—"))
    t = doc.table("Author ledger")
    out.append(f"Ledger: {len(t.rows) if t else 0} entries")
    return out


def cmd_campaign(ctx):
    a = ctx.args
    if a.action == "new":
        if not a.args:
            raise CampaignCmdError('campaign new <slug> --area "<starting area>" [--set k=v …]')
        lines = new(a.args[0], a.area, a.set, a.seed_file, a.activate)
    elif a.action == "fill":
        if a.add:
            lines = [fill(add=a.add, default=a.default or "")]
        else:
            if not a.args:
                raise CampaignCmdError('campaign fill <F1> "<answer>"')
            lines = [fill(a.args[0], " ".join(a.args[1:]))]
    elif a.action == "status":
        lines = status(a.level)
    else:
        if len(a.args) < 2 or a.args[0] != "add" or not a.via:
            raise CampaignCmdError('campaign ledger add "<what>" --via <skill>')
        lines = [ledger(" ".join(a.args[1:]), a.via)]
    for line in lines:
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("campaign", parents=[g], help="campaign new | fill | status | ledger")
    p.add_argument("action", choices=["new", "fill", "status", "ledger"])
    p.add_argument("args", nargs="*")
    p.add_argument("--area")
    p.add_argument("--set", action="extend", nargs="+", default=[])
    p.add_argument("--seed-file")
    p.add_argument("--activate", action="store_true")
    p.add_argument("--add")
    p.add_argument("--default")
    p.add_argument("--level")
    p.add_argument("--via")
    p.set_defaults(func=cmd_campaign)
