"""Phase 11: encounter budget/build/threat, danger, loot/shop, loop, campaign (plan.md
Phase 11 → Verify and Guards). Uses a throwaway copy of loop-play with four test PCs;
the loop tests also make a throwaway git repository."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fixture import LOOP_PLAY, POC, ROOT, TOOLS, CampaignCase, run_main
from lib import campaign, md

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


class LoopPlayCase(unittest.TestCase):
    """A copy of loop-play (inside its own git repo when `git=True`) with four L3 PCs at
    the north gate, as the active campaign."""
    git = False

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gm-p11-"))
        self.camp = self.tmp / "lp"
        shutil.copytree(LOOP_PLAY, self.camp, ignore=shutil.ignore_patterns(".gm"))
        for src, name in (("kael-ashford", "Kael Ashford"), ("kira-thornwood", "Kira Thornwood"),
                          ("kira-thornwood", "Bren Ash"), ("kael-ashford", "Ash Vale")):
            text = (POC / "pcs" / f"{src}.md").read_text(encoding="utf-8")
            text = re.sub(r"^name: .*$", f"name: {name}", text, count=1, flags=re.M)
            text = re.sub(r"^location: .*$", "location: north-gate/yard", text, count=1, flags=re.M)
            (self.camp / "pcs" / f"{campaign.slugify(name)}.md").write_text(text, encoding="utf-8")
        campaign.set_override(str(self.camp))
        self._env = os.environ.get("GM_CAMPAIGN")
        os.environ["GM_CAMPAIGN"] = str(self.camp)
        md.before_write.clear()
        self._git_env = {k: os.environ.get(k) for k in GIT_ENV}
        os.environ.update(GIT_ENV)
        if self.git:
            subprocess.run(["git", "-C", str(self.tmp), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(self.tmp), "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(self.tmp), "commit", "-qm", "init"], check=True, capture_output=True)

    def tearDown(self):
        campaign.set_override(None)
        if self._env is None:
            os.environ.pop("GM_CAMPAIGN", None)
        else:
            os.environ["GM_CAMPAIGN"] = self._env
        for k, v in self._git_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        md.before_write.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, rel):
        return self.camp / rel

    def front(self, rel):
        return md.load(self.path(rel)).front

    def set_levels(self, n):
        for p in self.path("pcs").glob("[!_]*.md"):
            p.write_text(re.sub(r"^level: \d+", f"level: {n}", p.read_text(encoding="utf-8"), flags=re.M),
                         encoding="utf-8")


class Encounters(LoopPlayCase):
    def test_budget(self):
        code, lines = run_main(["encounter", "budget", "--present", "Kira,Kael,Bren,Ash"])
        self.assertEqual(lines, ["[BUDGET] 4 PCs (L3, L3, L3, L3) · easy 300 · medium 600 · hard 900 · "
                                 "deadly 1,600 · power +0 (none)"])

    def test_build_scales_count_not_level(self):
        four = run_main(["encounter", "build", "the roost"])[1]
        self.assertIn("target 1,600 → harpy ×4 (adj 1,600)", four[0])
        self.assertEqual(four[1], '[combat start … --add "srd:harpy x4"]')
        two = run_main(["encounter", "build", "the roost", "--present", "Kira,Kael"])[1]
        self.assertIn("target 800 → harpy ×2 (adj 800)", two[0])     # same per-PC pressure
        self.set_levels(5)                                            # level never changes the count
        self.assertIn("harpy ×4", run_main(["encounter", "build", "the roost"])[1][0])

    def test_item_power(self):
        p = self.path("pcs/kira-thornwood.md")
        p.write_text(p.read_text(encoding="utf-8").replace("- Equipped: leather armor",
                                                           "- Equipped: +1 rapier (rare), cloak of protection (rare), leather armor"),
                     encoding="utf-8")
        code, lines = run_main(["encounter", "budget"])
        self.assertIn("power +0.5 (2 rare)", lines[0])
        self.assertIn("harpy ×5", run_main(["encounter", "build", "the roost"])[1][0])   # the full roster and more

    def test_fixed_and_threat(self):
        lines = run_main(["encounter", "build", "the Court of Misrule"])[1]
        self.assertIn("fixed L5 deadly", lines[0])
        self.assertIn("[fixed L5 deadly — above the party]", lines)
        self.assertEqual(run_main(["encounter", "threat", "north-gate"])[1], ["[threat north-gate: xp 4,200 · fixed]"])
        line = run_main(["encounter", "threat", "hollow-glacier"])[1][0]
        self.assertIn("skipped (not SRD)", line)   # the yeti
        self.assertEqual(run_main(["encounter", "build", "nope"])[0], 1)

    def test_danger(self):
        self.assertEqual(run_main(["danger", "bellwether-keep"])[1], ["[DANGER bellwether-keep: red]"])
        # the generator hand-wrote threat 2,000 (5 harpies); the tool's deadly budget is 1,600
        self.assertEqual(run_main(["danger", "castle-lark"])[1], ["[DANGER castle-lark: red]"])
        run_main(["encounter", "threat", "castle-lark"])
        self.assertEqual(run_main(["danger", "castle-lark"])[1], ["[DANGER castle-lark: yellow]"])
        self.set_levels(5)
        self.assertIn(run_main(["danger", "bellwether-keep"])[1][0],
                      ("[DANGER bellwether-keep: yellow]", "[DANGER bellwether-keep: red]"))
        self.assertIn("yellow", run_main(["danger", "bellwether-keep"])[1][0])
        line = run_main(["danger", "--bearing", "N"])[1][0]
        self.assertTrue(line.startswith("[DANGER N] "))


class LootShop(LoopPlayCase):
    def test_loot_suggests_only(self):
        before = self.path("pcs/kira-thornwood.md").read_text(encoding="utf-8")
        code, lines = run_main(["--seed", "2", "loot", "roll", "tier-1-4"])
        self.assertTrue(lines[0].startswith("[LOOT loot-tier-1-4: d20 2 → "))
        self.assertIn("suggest (not applied)", lines[1])
        self.assertEqual(self.path("pcs/kira-thornwood.md").read_text(encoding="utf-8"), before)

    def test_buy_sell_restock(self):
        p = self.path("pcs/kira-thornwood.md")
        p.write_text(re.sub(r"^- Coin: .*$", "- Coin: 400 gp", p.read_text(encoding="utf-8"), flags=re.M),
                     encoding="utf-8")
        self.assertIn("(unrolled — --restock)", run_main(["shop", "orrin"])[1][0])
        run_main(["--seed", "5", "shop", "orrin", "--restock"])
        stock = md.load(self.path("npcs/orrin-fetch.md")).table("Stock").rows
        rolled = [r for r in stock if r.get("random")]
        self.assertTrue(all(not r["item"].startswith("(") for r in rolled))
        uncommon = next(r for r in rolled if "(uncommon)" in r["item"])
        code, lines = run_main(["shop", "orrin", "--buy", uncommon["item"], "--pc", "Kira"])
        self.assertEqual(code, 0, lines)
        price = int(re.match(r"(\d+)", uncommon["price"]).group(1))
        self.assertEqual(lines[0], f"[coin Kira Thornwood 400→{400 - price} gp]")
        self.assertIn(uncommon["item"], p.read_text(encoding="utf-8"))   # with its rarity tag
        code, lines = run_main(["shop", "orrin", "--buy", "a cheese", "--pc", "Kira"])
        stock = md.load(self.path("npcs/orrin-fetch.md")).table("Stock").rows
        self.assertEqual(next(r for r in stock if r["item"] == "a cheese, whole")["stock"], "2")
        code, lines = run_main(["shop", "orrin", "--sell", "crowbar", "--pc", "Kira", "--price", "2 gp"])
        self.assertEqual(lines[-1], f"[coin Kira Thornwood {400 - price - 1}→{400 - price} gp]")

    def test_daily_restock_on_clock(self):
        doc = md.load(self.path("npcs/orrin-fetch.md"))
        t = doc.table("Stock")
        for i, r in enumerate(t.rows):
            if r.get("random"):
                t.set(i, "restock", "daily")
        doc.save()
        lines = run_main(["clock", "advance", "+1d"])[1]
        self.assertTrue(any(line.startswith("  Restocked: ") and "Orrin" in line for line in lines))


class Loop(LoopPlayCase):
    git = True

    def test_reset_restores_world_not_pcs(self):
        self.assertTrue(run_main(["loop", "start", "--bed", "sleeping-marmot/loft"])[1][0].startswith("[loop start · loop 1"))
        self.assertRegex(str(self.front("state/current.md")["loop-baseline"]), r"^[0-9a-f]{12}$")
        run_main(["do", 'move-npc wil-groundsel market-square; item Kira + "the Song (uncommon)"; '
                        'dmg Kira 5; log "Kira took the Song"'])
        self.assertEqual(self.front("npcs/wil-groundsel.md")["location"], "market-square")
        code, lines = run_main(["loop", "reset", "--by", "death"])
        self.assertEqual(code, 0, lines)
        self.assertIn("loop 1 ended by death · loop 2 begins Day 1 06:00", lines[0])
        self.assertEqual(self.front("npcs/wil-groundsel.md")["location"], "north-gate/yard")   # world restored
        kira = self.path("pcs/kira-thornwood.md").read_text(encoding="utf-8")
        self.assertIn("the Song (uncommon)", kira)                                            # carried
        f = self.front("pcs/kira-thornwood.md")
        self.assertEqual((f["hp"]["current"], f["location"]), (30, "sleeping-marmot/loft"))
        self.assertIn("duplicate; hollow", self.path("locations/castle-lark.md").read_text(encoding="utf-8"))
        st = self.front("state/current.md")
        self.assertEqual((st["loop"], st["in-game-datetime"]), (2, "Day 1 06:00"))
        row = md.load(self.path("state/loops.md")).table("Loop").rows[-1]
        self.assertEqual((row["loop"], row["ended by"], row["learned"]), ("1", "death", "Kira took the Song"))
        self.assertIn("[loop] the day begins again: loop 2", self.path("sessions/session-current.md").read_text(encoding="utf-8"))

    def test_clock_end_triggers_reset_and_lint(self):
        self.assertIn("time loop not started", "\n".join(run_main(["lint"])[1]))
        run_main(["loop", "start", "--bed", "sleeping-marmot/loft"])
        run_main(["clock", "advance", "to", "23:59"])
        lines = run_main(["clock", "advance", "+5m"])[1]
        self.assertTrue(any("ended by time" in line for line in lines))
        st = md.load(self.path("state/current.md"))
        st.set_front("loop-baseline", "pending")
        st.save()
        self.assertIn("without a loop-baseline", "\n".join(run_main(["lint"])[1]))


class NoLoop(CampaignCase):
    def test_rejected_without_mechanic(self):
        for args in (["loop", "status"], ["loop", "start"], ["loop", "reset", "--by", "death"]):
            code, lines = run_main(args)
            self.assertEqual(code, 1, args)
            self.assertIn("has no time loop", lines[0])


class Campaign(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gm-camp-"))
        self.patch = mock.patch.object(campaign, "CAMPAIGNS", self.tmp)
        self.patch.start()
        md.before_write.clear()

    def tearDown(self):
        self.patch.stop()
        campaign.set_override(None)
        md.before_write.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_new_fill_ledger_status(self):
        seed = self.tmp / "seed.txt"
        seed.write_text("A loop in a fishing town; funny; ghosts.", encoding="utf-8")
        code, lines = run_main(["campaign", "new", "gull", "--area", "Gull Harbour", "--set", "start-level=2",
                                "difficulty=hard", "shape=mystery", "mechanics=time-loop", "--seed-file", str(seed)])
        self.assertEqual(code, 0, lines)
        root = self.tmp / "gull"
        f = md.load(root / "campaign.md").front
        self.assertEqual((f["start-level"], f["difficulty"], f["mechanics"]), (2, "hard", ["time-loop"]))
        self.assertEqual((root / "campaign-seed.md").read_text(encoding="utf-8"), seed.read_text(encoding="utf-8"))
        self.assertTrue((root / "state" / "loops.md").exists())
        self.assertEqual(md.load(root / "state" / "current.md").front["loop"], 0)
        g = ["--campaign", str(root)]
        run_main(g + ["campaign", "fill", "--add", "Name of the town", "--default", "Gull Harbour"])
        self.assertEqual(run_main(g + ["campaign", "fill", "F1", "Netherby"])[1], ["[campaign fill F1: Netherby]"])
        run_main(g + ["campaign", "ledger", "add", "shape card", "--via", "campaign-new"])
        out = "\n".join(run_main(g + ["campaign", "status", "--level", "fill-in"])[1])
        self.assertIn("answered: Netherby", out)
        self.assertNotIn("Author notes", out)
        self.assertIn("Author notes", "\n".join(run_main(g + ["campaign", "status", "--level", "full"])[1]))
        self.assertEqual(run_main(["campaign", "new", "gull"])[0], 1)
        self.assertEqual(run_main(["campaign", "new", "x", "--area", "A", "--set", "shape=blob"])[0], 1)


class Skills(unittest.TestCase):
    def test_authoring_skills(self):
        d = TOOLS.parent / ".claude" / "skills"
        gen = (d / "campaign-generate" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("context: fork", gen)
        self.assertIn("context: fork", (d / "campaign-scenario" / "SKILL.md").read_text(encoding="utf-8"))
        for name in ("campaign-new", "campaign-fill", "campaign-status"):
            text = (d / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("context: fork", text, name)
            self.assertIn("disable-model-invocation: true", text, name)
        self.assertTrue((TOOLS.parent / "rules" / "mechanics" / "time-loop.md").exists())
        self.assertIn("rules/mechanics/", (d / "gm" / "SKILL.md").read_text(encoding="utf-8"))
