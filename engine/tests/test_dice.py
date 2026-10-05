"""lib/dice.py and `gm.py roll` (docs/design/06 L96-109; plan.md Phase 2 item 1 and Verify):
every bracket format at 06 L97-102, by string equality, scripted and seeded."""
import unittest

from fixture import CampaignCase, Scripted
from lib import dice
from fixture import run_main


class SpecFormats(unittest.TestCase):
    """The exact lines printed in 06 L97-102, reproduced with scripted dice."""

    def test_plain(self):
        self.assertEqual(Scripted([14]).roll("1d20+5").text, "[1d20+5: 14+5 = 19]")

    def test_adv(self):
        self.assertEqual(Scripted([6, 17]).roll("1d20+3 adv").text, "[1d20+3 adv: (6, 17)→17+3 = 20]")

    def test_crit_doubles_dice_not_modifier(self):
        r = Scripted([2, 5, 6, 1]).roll("2d6+3 crit")
        self.assertEqual(r.text, "[2d6+3 crit: 4d6 (2,5,6,1)+3 = 17]")
        self.assertEqual(r.total, 17)

    def test_secret(self):
        self.assertEqual(Scripted([3, 4, 4]).roll("3d6", secret=True).text, "[SECRET 3d6: 11]")


class Seeded(unittest.TestCase):
    def test_seeded_formats(self):
        cases = {
            "1d20+5": "[1d20+5: 5+5 = 10]",
            "1d20+3 adv": "[1d20+3 adv: (5, 19)→19+3 = 22]",
            "2d6+3 crit": "[2d6+3 crit: 4d6 (2,5,1,3)+3 = 14]",
            "3d6": "[3d6: 3d6 (2,5,1) = 8]",
            "1d6+2 x3": "[1d6+2 x3: 2+2 = 4 · 5+2 = 7 · 1+2 = 3]",
            "4d6kh3": "[4d6kh3: 4d6kh3 (2,5,1,3) = 10]",
            "1d20-1 dis": "[1d20-1 dis: (5, 19)→5-1 = 4]",
        }
        for expr, want in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(dice.Roller(1).roll(expr).text, want)
        self.assertEqual(dice.Roller(1).roll("3d6", secret=True).text, "[SECRET 3d6: 8]")

    def test_same_seed_same_result(self):
        self.assertEqual(dice.Roller(42).roll("8d6").text, dice.Roller(42).roll("8d6").text)

    def test_unseeded_uses_systemrandom(self):
        import random
        self.assertIsInstance(dice.Roller().rng, random.SystemRandom)

    def test_d20_test_text(self):
        self.assertEqual(dice.Roller(7).d20(5).text, "d20 11+5=16")
        self.assertEqual(dice.Roller(7).d20(5, "adv").text, "d20 (11, 5)→11+5=16")
        self.assertEqual(dice.reported(5, d20=12).text, "d20 12+5=17")
        self.assertEqual(dice.reported(-1, d20=12).text, "d20 12-1=11")
        self.assertEqual(dice.reported(5, total=19).text, "total 19")
        self.assertIsNone(dice.reported(5, total=19).natural)


class Grammar(unittest.TestCase):
    def test_terms(self):
        r = Scripted([3, 4, 2]).roll("2d6+1d4-1")
        self.assertEqual(r.text, "[2d6+1d4-1: 2d6 (3,4)+1d4 (2)-1 = 8]")
        self.assertEqual(Scripted([5, 2, 6, 1]).roll("4d6kh3").total, 13)
        self.assertEqual(Scripted([5, 2]).roll("2d20kl1").total, 2)
        self.assertEqual(Scripted([9]).roll("d20").text, "[d20: 9]")
        self.assertEqual(Scripted([9]).roll("1d20").natural, 9)

    def test_crit_with_keep_and_repeat(self):
        r = Scripted([1, 2, 3, 4, 5, 6]).roll("1d6 x3")
        self.assertEqual(r.totals, [1, 2, 3])
        self.assertEqual(r.total, 6)

    def test_errors(self):
        for bad in ("", "abc", "1d20+", "2d6 adv", "1d20 adv dis", "1d6 x0", "1d20 adv crit",
                    "2d6 crit dis"):
            with self.subTest(expr=bad), self.assertRaises(dice.DiceError):
                dice.Roller(1).roll(bad)

    def test_constant_only(self):
        # flat damage ("3 bludgeoning") is a constant-only expression; crit doubles no dice
        self.assertEqual(dice.Roller(1).roll("3").text, "[3: 3]")
        self.assertEqual(dice.Roller(1).roll("3 crit").total, 3)
        self.assertEqual(dice.Roller(1).roll("-1d4+5").body, "-1d4 (2)+5 = 3")

    def test_body(self):
        r = Scripted([2, 5, 6, 1]).roll("2d6+3 crit")
        self.assertEqual(r.body, "4d6 (2,5,6,1)+3 = 17")
        self.assertEqual(Scripted([3, 4, 4]).roll("3d6", secret=True).body, "11")

    def test_dice_max(self):
        self.assertEqual(dice.dice_max("2d6+3"), 12)
        self.assertEqual(dice.dice_max("4d6kh3"), 18)


class RollCommand(CampaignCase):
    def log(self):
        return self.path("sessions/session-current.md").read_text(encoding="utf-8").splitlines()

    def test_roll_seeded(self):
        code, lines = run_main(["roll", "1d20+5", "--seed", "1"])
        self.assertEqual((code, lines), (0, ["[1d20+5: 5+5 = 10]"]))
        code, lines = run_main(["roll", "2d6+3", "crit", "--seed", "1"])
        self.assertEqual(lines, ["[2d6+3 crit: 4d6 (2,5,1,3)+3 = 14]"])

    def test_public_roll_is_not_logged(self):
        before = self.read_bytes("sessions/session-current.md")
        run_main(["roll", "1d20", "--seed", "1"])
        self.assertEqual(self.read_bytes("sessions/session-current.md"), before)

    def test_secret_roll_logged_gm_only(self):
        code, lines = run_main(["roll", "3d6", "--secret", "--seed", "1"])
        self.assertEqual(lines, ["[SECRET 3d6: 8]"])
        log = self.log()
        self.assertEqual(log[-1], "  - (GM) roll SECRET 3d6: 8")
        for line in log:
            if line.startswith("  - ") and "(GM)" not in line:
                self.assertNotIn("8", line)

    def test_negative_leading_expression(self):
        code, lines = run_main(["roll", "-1d4", "--seed", "1"])
        self.assertEqual((code, lines), (0, ["[-1d4: -1d4 (2) = -2]"]))

    def test_outer_seed_drives_do_steps(self):
        runs = [run_main(["--seed", "3", "do", "roll 1d20; roll 1d20; roll 1d20"])[1] for _ in range(2)]
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(len(set(runs[0])), 3, runs[0])  # one Roller per batch, not reseeded per step
        code, lines = run_main(["--seed", "3", "do", "roll 1d20 --seed 1; roll 1d20"])
        self.assertEqual(lines[0], "[1d20: 5]")  # a per-step --seed overrides
        self.assertEqual(lines[1], runs[0][0])

    def test_table_roll(self):
        (self.camp / "tables").mkdir()
        (self.camp / "tables" / "road.md").write_text(
            "# Road\n\n| roll | result |\n|------|--------|\n| 1-3 | wolves |\n| 4–5 | a cart |\n| 6 | nothing |\n",
            encoding="utf-8")
        code, lines = run_main(["roll", "table:road", "--seed", "1"])
        self.assertEqual((code, lines), (0, ["[table:road: d6 2 → wolves]"]))
        code, lines = run_main(["roll", "table:nope"])
        self.assertEqual(code, 1)
        self.assertIn("no table 'nope'", lines[0])


if __name__ == "__main__":
    unittest.main()
