"""Custom monsters: one `custom-bestiary/` per campaign (lib/bestiary.py), `gm.py monster
new|list|show` including copying from another campaign at creation, custom monsters in
combat/atk/encounter, and the lint checks for ENCOUNTER rosters and custom-bestiary files
(docs/design/04 → Custom-bestiary file; 07 → Custom monsters)."""
import shutil
from unittest import mock

from fixture import TOOLS, CampaignCase, _edit, run_main
from lib import campaign, md, srd

YETI = TOOLS / "tests" / "fixtures" / "frost-yeti.md"


class Bestiary(CampaignCase):
    def setUp(self):
        super().setUp()
        (self.camp / "custom-bestiary").mkdir()
        shutil.copy(YETI, self.camp / "custom-bestiary" / "frost-yeti.md")
        # a second campaign beside this one, for the cross-campaign rules
        self.other = self.tmp / "other"
        (self.other / "custom-bestiary").mkdir(parents=True)
        shutil.copy(YETI, self.other / "custom-bestiary" / "snow-beast.md")
        _edit(self.other / "custom-bestiary" / "snow-beast.md",
              lambda t: t.replace("name: Frost Yeti", "name: Snow Beast").replace("# Frost Yeti", "# Snow Beast"))
        self.p = mock.patch.object(campaign, "CAMPAIGNS", self.tmp)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        super().tearDown()

    def test_campaign_lookup_and_block(self):
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

    def test_other_campaigns_are_invisible_in_play(self):
        with self.assertRaises(srd.SrdError):
            srd.monster("snow beast")
        self.assertEqual(run_main(["srd", "monster", "snow", "beast"])[0], 1)

    def test_new_from_srd_and_from_another_campaign(self):
        code, lines = run_main(["monster", "new", "Ice Bear", "--from", "brown bear"])
        self.assertEqual(code, 0, lines)
        self.assertIn("campaigns/poc/custom-bestiary/ice-bear.md", lines[0])
        self.assertEqual(md.load(self.path("custom-bestiary/ice-bear.md")).front["based-on"], "Brown Bear (SRD)")
        self.assertEqual(run_main(["monster", "new", "Ice Bear", "--from", "brown bear"])[0], 1)
        run_main(["monster", "new", "Glacier Bear", "--from", "frost yeti"])   # this campaign's custom one
        self.assertIn("Frost Yeti (custom)", md.load(self.path("custom-bestiary/glacier-bear.md")).front["based-on"])
        code, lines = run_main(["monster", "new", "Rime Beast", "--from", "other:snow beast"])
        self.assertEqual(code, 0, lines)
        p = self.path("custom-bestiary/rime-beast.md")
        f = md.load(p).front
        self.assertEqual(f["name"], "Rime Beast")
        self.assertTrue(f["based-on"].startswith("Snow Beast from campaigns/other ("))
        self.assertIn("## Backstory", p.read_text(encoding="utf-8"))          # copied as it is
        self.assertEqual(srd.monster("rime beast").xp, 700)
        self.assertEqual(run_main(["monster", "new", "X", "--from", "other:nothing"])[0], 1)
        mine = run_main(["monster", "list"])[1]
        self.assertTrue(all("· poc ·" in line for line in mine))
        everywhere = "\n".join(run_main(["monster", "list", "--all"])[1])
        self.assertIn("Snow Beast · CR 3 (700 XP) · other", everywhere)

    def test_custom_in_combat_and_encounters(self):
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
        run_main(["combat", "end"])
        _edit(self.path("locations/old-mill.md"),
              lambda t: t.replace("## Hidden", "## Encounters\n- ENCOUNTER hard \"the cold thing\": frost yeti ×n\n\n## Hidden", 1))
        self.assertIn("frost yeti ×", run_main(["encounter", "build", "the cold thing"])[1][0])

    def test_lint(self):
        _edit(self.path("locations/old-mill.md"),
              lambda t: t.replace("## Hidden", "## Encounters\n- ENCOUNTER hard \"bad\": snow beast ×1 | table cell\n"
                                               "- ENCOUNTER easy \"ok\": frost yeti ×n — notes here\n\n## Hidden", 1))
        found = "\n".join(run_main(["lint"])[1])
        self.assertIn("ENCOUNTER \"bad\": 'snow beast' is not an SRD or custom-bestiary monster", found)
        self.assertNotIn("\"ok\"", found)
        self.path("custom-bestiary/broken.md").write_text("---\nname: Broken\n---\n# Broken\n", encoding="utf-8")
        code, lines = run_main(["lint"])
        self.assertEqual(code, 1)
        self.assertIn("custom-bestiary: missing `ac`", "\n".join(lines))

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
