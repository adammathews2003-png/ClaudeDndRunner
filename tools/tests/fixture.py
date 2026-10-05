"""Test fixture: a throwaway copy of poc/ as the active campaign (plan.md Phase 1
item 6; planning/06 L754-755).

`CampaignCase.setUp` copies `poc/` into a fresh temp dir and points the campaign root
at it through `campaign.set_override` and `GM_CAMPAIGN` (the same path `--campaign`
takes, and the one gm.py subprocesses read), so the real `.campaign` and the real POC
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
POC = ROOT / "poc"
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
