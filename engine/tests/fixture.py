"""Test fixture: a throwaway copy of poc/ as the active campaign (plan.md Phase 1
item 6; docs/design/06 L754-755).

`CampaignCase.setUp` copies `poc/` into a fresh temp dir and points the campaign root
at it through `campaign.set_override` and `GM_CAMPAIGN` (the same path `--campaign`
takes, and the one gm.py subprocesses read), so the real `campaigns/.active` and the real POC
files are never touched. `tearDown` removes the copy.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent  # dnd-adventure/
POC = TOOLS / "tests" / "fixtures" / "poc"          # a frozen copy: playing campaigns/poc never moves the tests
LOOP_PLAY = TOOLS / "tests" / "fixtures" / "loop-play"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from lib import campaign, md  # noqa: E402

# every markdown file in poc/ (campaign-relative, posix form)
POC_FILES = sorted(p.relative_to(POC).as_posix() for p in POC.rglob("*.md"))


class CampaignCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gm-test-"))
        self.camp = self.tmp / "poc"
        shutil.copytree(POC, self.camp)
        campaign.set_override(str(self.camp))
        self._env = os.environ.get("GM_CAMPAIGN")
        os.environ["GM_CAMPAIGN"] = str(self.camp)
        md.before_write.clear()

    def tearDown(self):
        campaign.set_override(None)
        if self._env is None:
            os.environ.pop("GM_CAMPAIGN", None)
        else:
            os.environ["GM_CAMPAIGN"] = self._env
        md.before_write.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, rel):
        return self.camp / rel

    def read_bytes(self, rel):
        return self.path(rel).read_bytes()

    def write_lf_copy(self, rel):
        """An LF-only copy of a campaign file, beside it, as <name>.lf.md."""
        src = self.path(rel)
        dst = src.with_name(src.stem + ".lf.md")
        dst.write_bytes(src.read_bytes().replace(b"\r\n", b"\n"))
        return dst

    def write_crlf_copy(self, rel):
        src = self.path(rel)
        dst = src.with_name(src.stem + ".crlf.md")
        dst.write_bytes(src.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        return dst


# ---------- Phase 2 helpers (test data only; the real poc/ files are never edited) ----------

VESKAR_CUSTOM = (
    'statblock: "custom: see below"   # test-only custom block (srd arrives in Phase 4)\n'
    "scores: {str: 15, dex: 16, con: 14, int: 14, wis: 11, cha: 14}\n"
    "prof: 2\n"
    "saves: [str, dex, wis]\n"
    "skills: {athletics: 4, deception: 4, stealth: 5}\n"
    "ac: 15\n"
    "hp: {current: 65, max: 65}\n"
    "resistances: [poison]"
)
VESKAR_ATTACKS = (
    "## Attacks\n"
    "| name     | hit | damage         | range | notes |\n"
    "|----------|-----|----------------|-------|-------|\n"
    "| scimitar | +14 | 1d6+3 slashing | 5     | test value |\n"
    "| dagger   | +5  | 1d4+3 pierce   | 20/60 |       |\n"
    "\n"
)

COMBAT_BLOCK = """## Combat — round 2 · up: Kael
Map: crossroads-inn / common-room (frame: site crossroads-inn; layout: locations/crossroads-inn.md)
Bounds: x 0–45 · y 0–35 · z 0–10 · origin (0,0,0) = inside the front door, SW corner · +x east · +y north · +z up · ft

### Combatants
| init | name      | glyph | side  | pos       | size     | ref              | HP      | AC | conditions  | notes |
|------|-----------|-------|-------|-----------|----------|------------------|---------|----|-------------|-------|
| 18   | Veskar    | V     | foe   | (10,10,0) | M        | npcs/veskar      | 22/22   | 14 | —           |       |
| 15   | Kael (PC) | K     | party | (10,5,0)  | M        | pcs/kael-ashford | 9/11    | 15 | poisoned 3r |       |
| 12   | Thugs ×3  | T     | foe   | (25,15,0) | group r5 | srd:thug         | 7/11 ea | 12 | —           |       |

### Moves log (this round; cleared at round end, summarized into the session log)"""


def _edit(path, fn):
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    text = fn(raw.replace("\r\n", "\n"))
    path.write_bytes(text.replace("\n", nl).encode("utf-8"))


def give_custom_veskar(case):
    """Swap Veskar's SRD statblock for a custom block in the temp copy."""
    def fn(t):
        t = t.replace("statblock: bandit captain", VESKAR_CUSTOM, 1)
        return t.replace("## Movements", VESKAR_ATTACKS + "## Movements", 1)
    _edit(case.path("npcs/veskar.md"), fn)


def start_combat(case):
    """Replace `(not in combat)` with a Combat block (04 L507-538) in the temp copy."""
    _edit(case.path("state/current.md"),
          lambda t: t.replace("## Combat\n(not in combat)", COMBAT_BLOCK, 1))


def set_front_raw(case, rel, key, value):
    """Rewrite one frontmatter line in a temp copy (test setup only)."""
    doc = md.load(case.path(rel))
    doc.set_front(key, value)
    doc.save()


class Scripted:
    """A dice.Roller stand-in that returns scripted die faces in order."""

    def __init__(self, faces):
        from lib import dice
        self._faces = list(faces)
        self._roller = dice.Roller(0)
        self._roller.die = self.die

    def die(self, sides):
        if not self._faces:
            raise AssertionError("scripted dice ran out")
        v = self._faces.pop(0)
        assert 1 <= v <= sides, (v, sides)
        return v

    def __getattr__(self, name):
        return getattr(self._roller, name)


def run_main(argv):
    """Run gm.main in-process; returns (exit code, output lines)."""
    import io
    from contextlib import redirect_stdout
    import gm
    out = io.StringIO()
    with redirect_stdout(out):
        code = gm.main(argv)
    return code, out.getvalue().splitlines()
