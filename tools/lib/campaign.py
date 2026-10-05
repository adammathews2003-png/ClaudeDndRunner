"""Locate the active campaign and its files; resolve creature names
(planning/06 → Campaign selection L51-53 and Names L55-58; planning/04 → Where
people are L289-293 and who-is-here L307-308; plan.md Phase 1 item 2).

Campaign root, in order: `set_override()` (the `--campaign` flag), the `GM_CAMPAIGN`
environment variable, then the folder named in `dnd-adventure/.campaign`. A name is
relative to `dnd-adventure/`; an absolute path is used as-is.
"""
import os
import re
import unicodedata
from pathlib import Path

from . import md

BASE = Path(__file__).resolve().parents[2]  # dnd-adventure/
CAMPAIGN_FILE = BASE / ".campaign"
KINDS = ("pcs", "npcs", "locations", "scenarios", "tables", "state", "sessions")

_override = None


class CampaignError(Exception):
    pass


class Ambiguous(CampaignError):
    def __init__(self, name, candidates):
        self.name = name
        self.candidates = candidates
        names = ", ".join(c.label() for c in candidates)
        super().__init__(f"'{name}' is ambiguous: {names}")


class NotFound(CampaignError):
    pass


def set_override(path):
    """`--campaign <dir>`; None clears it."""
    global _override
    _override = None if path is None else str(path)


def root():
    """Absolute Path of the active campaign folder."""
    name = _override or os.environ.get("GM_CAMPAIGN")
    if not name:
        if not CAMPAIGN_FILE.exists():
            raise CampaignError(f"no campaign: {CAMPAIGN_FILE} is missing (use --campaign)")
        name = CAMPAIGN_FILE.read_text(encoding="utf-8").strip()
        if not name:
            raise CampaignError(f"{CAMPAIGN_FILE} is empty")
    p = Path(name)
    p = p if p.is_absolute() else BASE / p
    if not p.is_dir():
        raise CampaignError(f"campaign folder not found: {p}")
    return p.resolve()


def path(kind, slug):
    """`<campaign>/<kind>/<slug>.md` for pcs/npcs/locations/scenarios/tables (and
    state/sessions). `slug` may already end in .md."""
    if kind not in KINDS:
        raise CampaignError(f"unknown kind {kind!r} (one of {', '.join(KINDS)})")
    name = slug if slug.endswith(".md") else slug + ".md"
    return root() / kind / name


def state_path():
    """`<campaign>/state/current.md`."""
    return root() / "state" / "current.md"


def session_log_path():
    """`<campaign>/sessions/session-current.md`."""
    return root() / "sessions" / "session-current.md"


def slugify(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = re.sub(r"['’]", "", s)   # "the cooper's" → the-coopers
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def _docs(kind):
    folder = root() / kind
    if not folder.is_dir():
        return []
    out = []
    for p in sorted(folder.glob("*.md")):
        if p.name.startswith("_"):
            continue  # templates
        out.append(md.load(p))
    return out


def pcs():
    """Loaded Docs for `pcs/*.md` (templates starting with `_` skipped)."""
    return _docs("pcs")


def npcs():
    """Loaded Docs for `npcs/*.md`."""
    return _docs("npcs")


def locations():
    """Loaded Docs for `locations/*.md`."""
    return _docs("locations")


def load_state():
    """The loaded `state/current.md`."""
    return md.load(state_path())


# ---------- campaign settings ----------

# Table configuration keys and their defaults (04 → Campaign file: Advancement,
# Wacky Juice). Read from campaign.md frontmatter, else current.md's (the POC has no
# campaign.md), else the default.
SETTINGS = {
    "advancement": "milestone",
    "xp-tracking": "on",
    "xp-absent": "full",
    "xp-split": "even",
    "wacky-juice": "on",
    "wacky-juice-value": 5,
    "wacky-juice-cooldown": 3,
}


def campaign_doc_path():
    """`<campaign>/campaign.md` (may not exist)."""
    return root() / "campaign.md"


def settings_doc():
    """The Doc that holds the settings keys: campaign.md when it exists, else current.md."""
    p = campaign_doc_path()
    return md.load(p) if p.exists() else load_state()


def settings(state=None):
    """{key: value} for every SETTINGS key. A key missing from campaign.md falls back to
    current.md, then to the default. `on`/`off` values are kept as written (strings);
    true/false are normalised to on/off."""
    docs = []
    p = campaign_doc_path()
    if p.exists():
        docs.append(md.load(p))
    docs.append(state or load_state())
    out = {}
    for key, default in SETTINGS.items():
        value = default
        for doc in docs:
            if doc.front.get(key) is not None:
                value = doc.front[key]
                break
        if value is True:
            value = "on"
        elif value is False:
            value = "off"
        out[key] = value
    return out


# ---------- name resolution ----------

class Match:
    """One resolved creature. `kind` is combat | stage | onstage | pc | npc.
    `name` is the display name as the source spells it; `slug`/`path`/`doc` point at
    the pc/npc file when there is one (lazily located for table rows); `row` is the
    table row (combat/stage) and `line` the On stage bullet index."""

    def __init__(self, kind, name, slug=None, path=None, doc=None, row=None, line=None):
        self.kind = kind
        self.name = name
        self.slug = slug
        self.path = path
        self._doc = doc
        self.row = row
        self.line = line

    def label(self):
        return f"{self.name} ({self.kind})"

    @property
    def doc(self):
        if self._doc is None and self.path:
            self._doc = md.load(self.path)
        if self._doc is None and self.kind in ("combat", "stage", "onstage"):
            hit = _file_for(self.name)
            if hit:
                self.slug, self.path, self._doc = hit.slug, hit.path, hit.doc
        return self._doc

    @property
    def is_pc(self):
        if self.kind == "pc":
            return True
        if self.row and "(pc)" in self.row.get("name", "").lower():
            return True
        p = self.path or (self.doc.path if self.doc else None)
        return bool(p) and Path(p).parent.name == "pcs"

    def __repr__(self):
        return f"Match({self.kind}, {self.name!r})"


def _file_matches(kind):
    out = []
    for doc in _docs(kind):
        slug = Path(doc.path).stem
        name = str(doc.front.get("name") or slug)
        out.append(Match("pc" if kind == "pcs" else "npc", name, slug, doc.path, doc))
    return out


def _file_for(name):
    """Unique pc/npc file for a display name (exact, else unique prefix), or None."""
    for kind in ("pcs", "npcs"):
        picked = _pick(name, _file_matches(kind), strict=False)
        if picked:
            return picked
    return None


def _pick(name, candidates, strict=True):
    """Exact name/slug match wins; else a unique prefix; several prefixes → Ambiguous
    (or None when not strict); none → None."""
    want = name.strip().lower()
    if not want:
        return None

    def keys(c):
        ks = [c.name.lower()]
        if c.slug:
            ks.append(c.slug.lower())
        ks.append(slugify(c.name))
        return ks

    exact = [c for c in candidates if want in keys(c)]
    if exact:
        return exact[0]
    prefix = [c for c in candidates if any(k.startswith(want) for k in keys(c))]
    if len(prefix) == 1:
        return prefix[0]
    if len(prefix) > 1:
        if strict:
            raise Ambiguous(name, prefix)
        return None
    return None


_BULLET = re.compile(r"^\s*-\s+\*\*(.+?)\*\*(?:\s*\((\S+?\.md)\))?")


def onstage(state=None):
    """Matches for the `## On stage` bullets of current.md (`- **Name** (file) — …`).
    Bullets without a bold name (parenthetical notes) are skipped."""
    state = state or load_state()
    span = state.section("On stage")
    if span is None:
        return []
    out = []
    for i in range(span[0] + 1, span[1]):
        m = _BULLET.match(state.body[i])
        if not m:
            continue
        name, ref = m.group(1).strip(), m.group(2)
        path = str(root() / ref) if ref and (root() / ref).exists() else None
        slug = Path(ref).stem if ref else None
        out.append(Match("onstage", name, slug, path, None, None, i))
    return out


def _rows(state, heading, kind):
    table = state.table(heading)
    if table is None:
        return []
    out = []
    for row in table.rows:
        name = re.sub(r"\s*\(PC\)", "", row.get("name", ""), flags=re.I).strip()
        if name:
            out.append(Match(kind, name, row=row))
    return out


def _stage_tier(state):
    """Stage rows plus On stage bullets, one Match per name: a Stage row wins and
    takes the bullet's file path and line."""
    out, seen = [], {}
    for m in _rows(state, "Stage", "stage"):
        seen[m.name.lower()] = m
        out.append(m)
    for b in onstage(state):
        hit = seen.get(b.name.lower())
        if hit is None:
            out.append(b)
        else:
            hit.slug, hit.path, hit.line = hit.slug or b.slug, hit.path or b.path, b.line
    return out


def stage_matches(state=None):
    """Everyone in the scene outside combat: Stage table rows plus On stage bullets,
    one Match per name (the Stage/On stage tier of `resolve`)."""
    return _stage_tier(state or load_state())


def resolve(name, state=None):
    """Find a creature by display name, slug or unique prefix. Order (06:55-58):
    Combat block rows → Stage table / On stage bullets → pcs/ → npcs/. The first tier
    with any match decides; several prefix matches there raise Ambiguous."""
    state = state or load_state()
    tiers = (
        lambda: _rows(state, "Combatants", "combat"),
        lambda: _stage_tier(state),
        lambda: _file_matches("pcs"),
        lambda: _file_matches("npcs"),
    )
    for tier in tiers:
        hit = _pick(name, tier())
        if hit:
            return hit
    raise NotFound(f"no creature named {name!r}")


def who_is_at(site_or_area):
    """PC and NPC docs whose `location:` is at the site (any area) or exactly at
    `site/area` (planning/04 L307-308)."""
    want = site_or_area.strip().lower()
    out = []
    for doc in pcs() + npcs():
        loc = str(doc.front.get("location") or "").strip().lower()
        if not loc:
            continue
        if loc == want or ("/" not in want and loc.split("/")[0] == want):
            out.append(doc)
    return out
