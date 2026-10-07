"""House rule: material spell components are waived (rules/house-rules.md → Spell components)."""
import unittest

from fixture import CampaignCase, run_main


class SpellComponents(CampaignCase):
    def test_material_is_waived(self):
        head = run_main(["srd", "spell", "fireball"])[1][0]
        self.assertIn("V, S, M (material waived: ", head)

    def test_no_material_unchanged(self):
        head = run_main(["srd", "spell", "magic missile"])[1][0]
        self.assertIn("· V, S ·", head)
        self.assertNotIn("waived", head)


if __name__ == "__main__":
    unittest.main()
