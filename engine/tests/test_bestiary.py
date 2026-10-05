"""Custom monsters: lib/bestiary.py lookup order and scope, `gm.py monster new|list|show`,
custom monsters in combat/atk/encounter, and the lint checks for ENCOUNTER rosters and
bestiary files (docs/design/04 → Bestiary file; 07 → Custom monsters)."""
import shutil
from unittest import mock

from fixture import TOOLS, CampaignCase, _edit, run_main, start_combat
from lib import bestiary, md, srd

SHARED = TOOLS.parent / "bestiary"


class Bestiary(CampaignCase):
    def setUp(self):
        super().setUp()
        self.shared = self.tmp / "shared-bestiary"
        shutil.copytree(SHARED, self.shared)
        self.p = mock.patch.object(bestiary, "SHARED", self.shared)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        super().tearDown()

    def test_shared_lookup_and_block(self):
        m = srd.monster("frost yeti")
        self.assertTrue(getattr(m, "custom", False))
        self.assertEqual((m.ac, m.hp, m.xp, m.size), (13, 59, 700, "L"))
        self.assertEqual(m.immune, ["cold"])
        self.assertEqual(m.attacks()[0], {"name": "claw", "hit": "+6", "damage": "1d6+4 slashing + 1d6 cold",
                                          "range": "5", "notes": "rime-crusted claws"})
        lines = run_main(["srd", "monster", "frost", "yeti"])[1]
        self.assertTrue(lines[0].startswith("[CUSTOM Frost Yeti] Large monstrosity · CR 3 (700 XP) · AC 13"))
        self.assertIn("Traits: Ice Walk · Snow Camouflage · Keen Smell · Fear of Fire", lines)
        self.assertEqual(srd.monster("polar bear").name, "Polar Bear")   # the SRD still answers

    def test_campaign_scope_wins_and_new(self):
        code, lines = run_main(["monster", "new", "Frost Yeti", "--from", "brown bear"])
        self.assertEqual(code, 0, lines)
        p = self.path("bestiary/frost-yeti.md")
        self.assertEqual(md.load(p).front["based-on"], "Brown Bear (SRD)")
        self.assertEqual(srd.monster("frost yeti").name, "Frost Yeti")
        self.assertEqual(srd.monster("frost yeti").hp, md.load(p).front["hp"])   # the campaign copy wins
        self.assertEqual(run_main(["monster", "new", "Frost Yeti", "--from", "brown bear"])[0], 1)
        out = run_main(["monster", "list"])[1]
        self.assertTrue(any("Frost Yeti" in line and "campaign" in line for line in out))
        self.assertTrue(any("Flameskull" in line and "shared" in line for line in out))
        code, lines = run_main(["monster", "new", "Ice Bear", "--from", "frost yeti"])   # custom from custom
        self.assertEqual(code, 0, lines)
        self.assertIn("Frost Yeti (custom)", md.load(self.path("bestiary/ice-bear.md")).front["based-on"])

    def test_custom_in_combat_and_encounters(self):
        start_combat(self)
        run_main(["combat", "end"])
        run_main(["tempo", "tense", "--pos", "Mara @bar", "--pos", "Tobin @tables-e",
                  "--pos", "Kael near Tobin", "--pos", "Kira @door"])
        code, lines = run_main(["--seed", "1", "combat", "start", "--init", "Kael=15", "--init", "Kira=12",
                                "--add", "srd:frost yeti @near Kira"])
        self.assertEqual(code, 0, lines)
        row = next(r for r in md.load(self.path("state/current.md")).table("Combatants").rows
                   if r["name"] == "Frost Yeti")
        self.assertEqual((row["hp"], row["ac"], row["size"]), ("59/59", "13", "L"))
        code, lines = run_main(["--seed", "3", "atk", "Frost Yeti", "Kira", "--with", "claw"])
        self.assertEqual(code, 0, lines)
        self.assertIn("Frost Yeti → Kira", lines[0])
        _edit(self.path("locations/old-mill.md"),
              lambda t: t.replace("## Hidden", "## Encounters\n- ENCOUNTER hard \"the cold thing\": frost yeti ×n\n\n## Hidden", 1))
        self.assertIn("frost yeti ×", run_main(["encounter", "build", "the cold thing"])[1][0])

    def test_lint(self):
        _edit(self.path("locations/old-mill.md"),
              lambda t: t.replace("## Hidden", "## Encounters\n- ENCOUNTER hard \"bad\": yeti ×1 | table cell\n"
                                               "- ENCOUNTER easy \"ok\": frost yeti ×n — notes here\n\n## Hidden", 1))
        found = "\n".join(run_main(["lint"])[1])
        self.assertIn("ENCOUNTER \"bad\": 'yeti' is not an SRD or bestiary monster", found)
        self.assertNotIn("\"ok\"", found)
        self.path("bestiary").mkdir(exist_ok=True)
        self.path("bestiary/broken.md").write_text("---\nname: Broken\n---\n# Broken\n", encoding="utf-8")
        code, lines = run_main(["lint"])
        self.assertEqual(code, 1)
        self.assertIn("bestiary: missing `ac`", "\n".join(lines))

    def test_stacked_places_are_not_an_overlap(self):
        from lib.lint import _Out, check_location_file
        head = ["---", "name: Sky", "tier: area", "type: outdoor", "parent:", "---", "# Sky", "", "## Places",
                "| id | glyph | feature | at | from | to | effect | ref | source |",
                "|----|-------|---------|----|------|----|--------|-----|--------|",
                "| ridge | ^ | a ridge | | (0,0,0) | (100,100,50) | | crossroads-inn | scenario |"]

        def area(z):
            row = f"| castle | C | a flying castle | | (20,20,{z}) | (80,80,200) | aloft | old-mill | scenario |"
            self.path("locations/sky.md").write_text(chr(10).join(head + [row, ""]), encoding="utf-8")
            out = _Out()
            check_location_file(out, md.load(self.path("locations/sky.md")))
            return [f.msg for f in out if "overlap" in f.msg]
        self.assertEqual(area(50), [])                                        # stacked: heights only touch
        self.assertEqual(area(30), ["Places `ridge` and `castle` overlap"])   # heights overlap too
