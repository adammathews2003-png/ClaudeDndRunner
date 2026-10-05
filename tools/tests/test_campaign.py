"""lib/campaign.py: root, paths, loaders, name resolution (plan.md Phase 1 item 6)."""
import unittest

from fixture import ROOT, CampaignCase, campaign, md


class Root(CampaignCase):
    def test_override_wins(self):
        self.assertEqual(campaign.root(), self.camp.resolve())

    def test_dot_campaign_file_names_poc(self):
        campaign.set_override(None)
        import os
        os.environ.pop("GM_CAMPAIGN")
        self.assertEqual((ROOT / ".campaign").read_text(encoding="utf-8").strip(), "poc")
        self.assertEqual(campaign.root(), (ROOT / "poc").resolve())

    def test_missing_folder(self):
        campaign.set_override(str(self.tmp / "nope"))
        with self.assertRaises(campaign.CampaignError):
            campaign.root()

    def test_paths(self):
        self.assertEqual(campaign.path("pcs", "kael-ashford"), self.camp.resolve() / "pcs" / "kael-ashford.md")
        self.assertEqual(campaign.path("npcs", "veskar.md").name, "veskar.md")
        self.assertEqual(campaign.path("tables", "encounters-mill-rd").parent.name, "tables")
        self.assertEqual(campaign.state_path().name, "current.md")
        self.assertEqual(campaign.session_log_path().name, "session-current.md")
        with self.assertRaises(campaign.CampaignError):
            campaign.path("monsters", "x")

    def test_loaders(self):
        self.assertEqual([d.front["name"] for d in campaign.pcs()], ["Kael Ashford", "Kira Thornwood"])
        self.assertEqual([d.front["name"] for d in campaign.npcs()], ["Mara Fennick", "Tobin Hale", "Veskar"])
        self.assertEqual(len(campaign.locations()), 5)
        self.assertEqual(campaign.load_state().front["campaign"], "poc")


class Slugify(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(campaign.slugify("Kael Ashford"), "kael-ashford")
        self.assertEqual(campaign.slugify("  The Missing Miller! "), "the-missing-miller")
        self.assertEqual(campaign.slugify("Réeve O'Dell"), "reeve-odell")  # apostrophes drop: matches files like shackletons-folly


class Resolve(CampaignCase):
    def test_pc_by_name_slug_prefix(self):
        for name in ("Kael", "kael", "ka", "Kael Ashford", "kael-ashford", "KAEL"):
            m = campaign.resolve(name)
            self.assertEqual(m.kind, "pc", name)
            self.assertEqual(m.name, "Kael Ashford", name)
            self.assertEqual(m.slug, "kael-ashford")
            self.assertTrue(m.is_pc)
            self.assertEqual(m.doc.front["level"], 3)

    def test_k_is_ambiguous(self):
        with self.assertRaises(campaign.Ambiguous) as cm:
            campaign.resolve("k")
        self.assertEqual([c.name for c in cm.exception.candidates], ["Kael Ashford", "Kira Thornwood"])
        self.assertIn("Kael Ashford (pc)", str(cm.exception))

    def test_npc_by_slug_and_prefix(self):
        self.assertEqual(campaign.resolve("veskar").kind, "npc")
        self.assertEqual(campaign.resolve("ves").name, "Veskar")
        self.assertFalse(campaign.resolve("ves").is_pc)
        with self.assertRaises(campaign.NotFound):
            campaign.resolve("zorblax")

    def test_on_stage_beats_files(self):
        m = campaign.resolve("Tobin")
        self.assertEqual(m.kind, "onstage")
        self.assertEqual(m.name, "Tobin")
        self.assertTrue(m.path.endswith("tobin-hale.md"))
        self.assertEqual(m.doc.front["role"], "stablehand")
        self.assertEqual(campaign.resolve("mara").kind, "onstage")
        # Veskar's bullet is a parenthetical note, not a bold name → found in npcs/
        self.assertEqual(campaign.resolve("Veskar").kind, "npc")

    def test_combat_rows_first(self):
        state = campaign.load_state()
        start, end = state.section("Combat")
        state.body[start:end] = [
            "## Combat — round 1 · up: Kael",
            "Map: crossroads-inn/common-room",
            "### Combatants",
            "| init | name       | glyph | side  | pos       | size | ref | HP    | AC | conditions | notes |",
            "|------|------------|-------|-------|-----------|------|-----|-------|----|------------|-------|",
            "| 15   | Kael (PC)  | K     | party | (10,20,0) | M    |     | 30/30 | 18 |            |       |",
            "| 12   | Thug 1     | T     | foe   | (20,20,0) | M    |     | 11/11 | 11 |            |       |",
            "| 12   | Thug 2     | T     | foe   | (25,20,0) | M    |     | 11/11 | 11 |            |       |",
        ]
        state.save()
        m = campaign.resolve("kael")
        self.assertEqual(m.kind, "combat")
        self.assertEqual(m.name, "Kael")
        self.assertEqual(m.row["hp"], "30/30")
        self.assertTrue(m.is_pc)
        self.assertEqual(m.doc.front["name"], "Kael Ashford")  # file located lazily
        self.assertEqual(campaign.resolve("thug 2").row["pos"], "(25,20,0)")
        with self.assertRaises(campaign.Ambiguous):
            campaign.resolve("thug")
        self.assertEqual(campaign.resolve("Tobin").kind, "onstage")  # not in combat → next tier

    def test_stage_table(self):
        state = campaign.load_state()
        start, end = state.section("Tempo")
        state.body[start:end] = [
            "## Tempo: tense",
            "### Stage",
            "| init | name  | glyph | side    | pos       | size | ref | adj | intent |",
            "|------|-------|-------|---------|-----------|------|-----|-----|--------|",
            "| 13   | Grask | G     | neutral | (30,5,0)  | M    |     |     | drinks |",
            "",
        ]
        state.save()
        self.assertEqual(campaign.resolve("gr").kind, "stage")
        self.assertIsNone(campaign.resolve("gr").doc)  # no file for Grask

    def test_stage_row_and_on_stage_bullet_dedupe(self):
        state = campaign.load_state()
        start, end = state.section("Tempo")
        state.body[start:end] = [
            "## Tempo: tense",
            "### Stage",
            "| init | name  | glyph | side    | pos       | size | ref | adj | intent |",
            "|------|-------|-------|---------|-----------|------|-----|-----|--------|",
            "| 13   | Mara  | M     | neutral | (25,30,0) | M    |     |     | serves |",
            "",
        ]
        state.save()
        m = campaign.resolve("ma")  # Mara is a Stage row AND an On stage bullet
        self.assertEqual(m.kind, "stage")
        self.assertEqual(m.row["pos"], "(25,30,0)")
        self.assertTrue(m.path.endswith("mara-fennick.md"))
        self.assertEqual(m.line, 8)
        self.assertEqual(len([c for c in campaign._stage_tier(campaign.load_state()) if c.name == "Mara"]), 1)


class WhoIsAt(CampaignCase):
    def test_site_and_area(self):
        names = lambda docs: sorted(d.front["name"] for d in docs)  # noqa: E731
        self.assertEqual(names(campaign.who_is_at("crossroads-inn")),
                         ["Kael Ashford", "Kira Thornwood", "Mara Fennick", "Tobin Hale", "Veskar"])
        self.assertEqual(names(campaign.who_is_at("crossroads-inn/upstairs")), ["Veskar"])
        self.assertEqual(campaign.who_is_at("old-mill"), [])
        v = md.load(self.path("npcs/veskar.md"))
        v.set_front("location", "old-mill")
        v.save()
        self.assertEqual(names(campaign.who_is_at("old-mill")), ["Veskar"])


if __name__ == "__main__":
    unittest.main()
