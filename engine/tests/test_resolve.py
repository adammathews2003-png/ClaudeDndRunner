"""lib/resolve.py and atk/save/check/contest (docs/design/06 L111-134, keys L194-204;
rules/house-rules.md L24-32; rules/combat-basics.md L20-27; plan.md Phase 2 items 2
and 4 and Verify): one test per tie case, crit/cover rules, and the line formats of
06 L112-119 by string equality."""
import unittest
from unittest import mock

from fixture import CampaignCase, Scripted, give_custom_veskar, set_front_raw, start_combat
from lib import dice, resolve
from fixture import run_main
import roll

PC, NPC = True, False
NO_RULES = {}
RAW = {"ties": {"value": "raw", "id": "R9", "rule": "", "scope": "session"}}


def nat(n, bonus=0):
    return dice.reported(bonus, d20=n)


def tot(t):
    return dice.reported(0, total=t)


class HouseRuleTies(unittest.TestCase):
    """rules/house-rules.md L24-32, one test per bullet (and the toggle)."""

    def test_pc_roll_equals_ac_hits(self):
        self.assertEqual(resolve.attack(nat(10, 5), 15, attacker_is_pc=PC, target_is_pc=NPC, rules=NO_RULES),
                         ("HIT", "tie→PC"))

    def test_pc_roll_equals_dc_succeeds(self):
        self.assertEqual(resolve.check(nat(10, 2), 12, checker_is_pc=PC, rules=NO_RULES), ("SUCCESS", "tie→PC"))
        self.assertEqual(resolve.save(nat(10, 4), 14, saver_is_pc=PC, rules=NO_RULES), ("SAVE", "tie→PC"))

    def test_contest_tie_pc_attacker_wins(self):
        self.assertEqual(resolve.contest(15, 15, a_is_pc=PC, b_is_pc=NPC, rules=NO_RULES), ("A", "tie→PC"))

    def test_contest_tie_pc_defender_wins(self):
        self.assertEqual(resolve.contest(15, 15, a_is_pc=NPC, b_is_pc=PC, rules=NO_RULES), ("B", "tie→PC"))

    def test_npc_roll_equals_pc_ac_misses(self):
        self.assertEqual(resolve.attack(nat(13, 5), 18, attacker_is_pc=NPC, target_is_pc=PC, rules=NO_RULES),
                         ("MISS", "tie→PC"))

    def test_npc_save_equals_pc_dc_fails(self):
        self.assertEqual(resolve.save(nat(11, 2), 13, saver_is_pc=NPC, dc_from_pc=True, rules=NO_RULES),
                         ("FAIL", "tie→PC"))

    def test_npc_check_equals_pc_passive_spotted(self):
        self.assertEqual(resolve.check(nat(10, 5), 15, checker_is_pc=NPC, vs_pc=True, rules=NO_RULES),
                         ("FAIL", "tie→PC"))

    def test_initiative_tie_pc_first(self):
        order = resolve.initiative_order([("Veskar", 15, NPC), ("Kael", 15, PC), ("Mara", 17, NPC)],
                                         rules=NO_RULES)
        self.assertEqual([e[0] for e in order], ["Mara", "Kael", "Veskar"])

    def test_pc_vs_pc_no_house_rule(self):
        self.assertEqual(resolve.contest(12, 12, a_is_pc=PC, b_is_pc=PC, rules=NO_RULES),
                         ("TIE", "PC vs PC: re-roll or players decide"))
        self.assertEqual(resolve.attack(nat(10, 5), 15, attacker_is_pc=PC, target_is_pc=PC, rules=NO_RULES),
                         ("HIT", ""))

    def test_ties_raw_rule_turns_it_off(self):
        self.assertEqual(resolve.attack(nat(13, 5), 18, attacker_is_pc=NPC, target_is_pc=PC, rules=RAW),
                         ("HIT", ""))
        self.assertEqual(resolve.contest(15, 15, a_is_pc=NPC, b_is_pc=PC, rules=RAW),
                         ("TIE", "no change (RAW)"))
        order = resolve.initiative_order([("Veskar", 15, NPC), ("Kael", 15, PC)], rules=RAW)
        self.assertEqual(order[0][0], "Veskar")

    def test_npc_vs_npc_raw(self):
        self.assertEqual(resolve.attack(nat(9, 5), 14, attacker_is_pc=NPC, target_is_pc=NPC, rules=NO_RULES),
                         ("HIT", ""))


class AttackRules(unittest.TestCase):
    def test_nat20_and_nat1(self):
        self.assertEqual(resolve.attack(nat(20, -5), 30, attacker_is_pc=PC, target_is_pc=NPC, rules=NO_RULES),
                         ("CRIT", "nat 20"))
        self.assertEqual(resolve.attack(nat(1, 30), 10, attacker_is_pc=PC, target_is_pc=NPC, rules=NO_RULES),
                         ("MISS", "nat 1"))

    def test_total_only_has_no_crit(self):
        self.assertEqual(resolve.attack(tot(25), 15, attacker_is_pc=PC, target_is_pc=NPC, rules=NO_RULES),
                         ("HIT", ""))

    def test_crit_range_rule(self):
        rules = {"crit-range": {"value": "19", "id": "R3", "rule": "", "scope": "combat"}}
        self.assertEqual(resolve.attack(nat(19, 0), 30, attacker_is_pc=NPC, target_is_pc=PC, rules=rules),
                         ("CRIT", "nat 19, crit-range 19 (R3)"))
        self.assertEqual(resolve.attack(nat(19, 0), 30, attacker_is_pc=NPC, target_is_pc=PC, rules=NO_RULES),
                         ("MISS", ""))

    def test_cover(self):
        self.assertEqual(resolve.attack(nat(10, 5), 14, attacker_is_pc=NPC, target_is_pc=PC, cover="half",
                                        rules=NO_RULES), ("MISS", "half cover +2"))
        self.assertEqual(resolve.attack(nat(10, 5), 10, attacker_is_pc=NPC, target_is_pc=PC,
                                        cover="three-quarters", rules=NO_RULES), ("MISS", "tie→PC, three-quarters cover +5"))
        self.assertEqual(resolve.attack(nat(20, 5), 10, attacker_is_pc=NPC, target_is_pc=PC, cover="total",
                                        rules=NO_RULES), ("NO TARGET", "total cover"))
        self.assertEqual(resolve.save(nat(10, 2), 13, saver_is_pc=PC, cover="half", ability="dex",
                                      rules=NO_RULES), ("SAVE", "half cover +2"))

    def test_attack_mode(self):
        self.assertEqual(resolve.attack_mode(None, rules=NO_RULES), (None, 0, []))
        self.assertEqual(resolve.attack_mode("adv", long_range=True, rules=NO_RULES),
                         (None, 0, ["long range: disadvantage", "adv and dis cancel"]))
        self.assertEqual(resolve.attack_mode(None, long_range=True, rules=NO_RULES),
                         ("dis", 0, ["long range: disadvantage"]))
        fl = {"flanking": {"value": "+2", "id": "R2", "rule": "", "scope": "combat"}}
        self.assertEqual(resolve.attack_mode(None, flanked=True, rules=fl), (None, 2, ["flanking +2 (R2)"]))
        fa = {"flanking": {"value": "adv", "id": "R2", "rule": "", "scope": "combat"}}
        self.assertEqual(resolve.attack_mode(None, flanked=True, rules=fa), ("adv", 0, ["flanking adv (R2)"]))
        self.assertEqual(resolve.attack_mode(None, flanked=True, rules=NO_RULES), (None, 0, []))

    def test_total_cover_only_matters_for_dex_saves(self):
        self.assertEqual(resolve.save(nat(5, 0), 13, saver_is_pc=PC, cover="total", ability="wis", rules=NO_RULES),
                         ("FAIL", ""))
        self.assertEqual(resolve.save(nat(5, 0), 13, saver_is_pc=PC, cover="half", ability="con", rules=NO_RULES),
                         ("FAIL", ""))

    def test_crit_damage_modes(self):
        self.assertEqual(resolve.crit_damage(Scripted([2, 5, 6, 1]), "2d6+3", NO_RULES), (17, "4d6 (2,5,6,1)+3 = 17"))
        rules = {"crit-damage": {"value": "max+roll", "id": "R4", "rule": "", "scope": "session"}}
        self.assertEqual(resolve.crit_damage(Scripted([2, 5]), "2d6+3", rules),
                         (22, "2d6 (2,5)+3 = 10 +12 max (R4) = 22"))

    def test_hp_arithmetic(self):
        self.assertEqual(resolve.apply_hp(9, 11, 0, "-", 20), (0, 0, ""))
        self.assertEqual(resolve.apply_hp(9, 11, 0, "+", 20), (11, 0, ""))
        self.assertEqual(resolve.apply_hp(9, 11, 5, "-", 7), (7, 0, "temp absorbed 5"))
        self.assertEqual(resolve.apply_hp(9, 11, 5, "temp", 3), (9, 5, "temp HP don't stack (kept 5)"))
        ds = {"death-saves": {"value": "off", "id": "R5", "rule": "", "scope": "session"}}
        self.assertEqual(resolve.apply_hp(9, 11, 0, "-", 20, is_pc=True, rules=ds),
                         (1, 0, "death-saves off (R5): 1 HP"))

    def test_resistance(self):
        self.assertEqual(resolve.adjust_damage(9, "fire", resist=["fire"]), (4, "resistant"))
        self.assertEqual(resolve.adjust_damage(9, "fire", immune=["fire"]), (0, "immune"))
        self.assertEqual(resolve.adjust_damage(9, "fire", vuln=["fire"]), (18, "vulnerable"))
        self.assertEqual(resolve.adjust_damage(9, "cold", resist=["fire"]), (9, ""))


class ActiveKeys(unittest.TestCase):
    def test_v1_only_newest_wins(self):
        rows = [
            {"id": "R1", "rule": "a", "key": "crit-range=19", "scope": "combat", "since": "", "status": "active"},
            {"id": "R2", "rule": "b", "key": "crit-range=18", "scope": "session", "since": "", "status": "active"},
            {"id": "R3", "rule": "c", "key": "made-up=1", "scope": "session", "since": "", "status": "active"},
            {"id": "R4", "rule": "d", "key": "ties=raw", "scope": "session", "since": "", "status": "ended (x)"},
        ]
        keys = resolve.active_keys(rows)
        self.assertEqual(set(keys), {"crit-range"})
        self.assertEqual(keys["crit-range"]["id"], "R2")
        self.assertEqual(resolve.crit_threshold(keys), (18, "R2"))


class CommandLines(CampaignCase):
    """Line formats for the commands at 06 L112-119."""

    def setUp(self):
        super().setUp()
        give_custom_veskar(self)

    def test_atk_npc_vs_pc_tie(self):
        # scimitar +14 (test block) vs Kael AC 18: natural 4 → 18 = AC → MISS (tie→PC)
        lines, data = roll.attack("Veskar", "Kael", roller=Scripted([4]))
        self.assertEqual(lines, ["[Veskar → Kael Ashford: d20 4+14=18 vs AC 18 — MISS (tie→PC)]"])
        self.assertEqual(data["outcome"], "MISS")

    def test_atk_hit_applies_damage(self):
        lines, _ = roll.attack("Veskar", "Kael", roller=Scripted([10, 4]))
        self.assertEqual(lines, ["[Veskar → Kael Ashford: d20 10+14=24 vs AC 18 — HIT · 7 slashing · "
                                 "Kael Ashford 30→23/30]"])
        self.assertIn("hp: {current: 23, max: 30}", self.path("pcs/kael-ashford.md").read_text(encoding="utf-8"))

    def test_atk_no_apply(self):
        before = self.read_bytes("pcs/kael-ashford.md")
        lines, _ = roll.attack("Veskar", "Kael", apply=False, roller=Scripted([10, 4]))
        self.assertEqual(lines, ["[Veskar → Kael Ashford: d20 10+14=24 vs AC 18 — HIT · 7 slashing · not applied]"])
        self.assertEqual(self.read_bytes("pcs/kael-ashford.md"), before)

    def test_atk_pc_reports_d20_and_total(self):
        code, lines = run_main(["atk", "Kira", "Veskar", "--d20", "12", "--with", "shortsword", "--seed", "1"])
        self.assertEqual(lines, ["[Kira Thornwood → Veskar: d20 12+5=17 vs AC 15 — HIT · 5 pierce · Veskar 65→60/65]"])
        code, lines = run_main(["atk", "Kira", "Veskar", "--total", "15", "--no-apply", "--seed", "1"])
        self.assertEqual(lines, ["[Kira Thornwood → Veskar: total 15 vs AC 15 — HIT (tie→PC) · 5 pierce · not applied]"])

    def test_atk_pc_without_roll_needs_dice_mode(self):
        code, lines = run_main(["atk", "Kael", "Veskar"])
        self.assertEqual(code, 1)
        self.assertIn("rolls their own d20", lines[0])
        set_front_raw(self, "state/current.md", "dice-mode", "gm-rolls-all")
        code, lines = run_main(["atk", "Kael", "Veskar", "--seed", "1"])
        self.assertEqual(code, 0, lines)
        self.assertTrue(lines[0].startswith("[Kael Ashford → Veskar: d20 5+4=9 vs AC 15 — MISS"), lines)

    def test_atk_crit_and_cover(self):
        lines, _ = roll.attack("Veskar", "Kael", cover="half", roller=Scripted([20, 2, 5]))
        self.assertEqual(lines, ["[Veskar → Kael Ashford: d20 20+14=34 vs AC 20 — CRIT (nat 20, half cover +2) · "
                                 "10 slashing · Kael Ashford 30→20/30]"])

    def test_atk_adv(self):
        code, lines = run_main(["atk", "Veskar", "Kael", "dis", "--no-apply", "--seed", "1"])
        self.assertEqual(lines, ["[Veskar → Kael Ashford: d20 (5, 19)→5+14=19 vs AC 18 — HIT · 4 slashing · not applied]"])

    def test_save(self):
        line, _ = roll.saving_throw("Kael", "dex", 14, d20=14)
        self.assertEqual(line, "[Kael Ashford DEX save: d20 14+0=14 vs DC 14 — SAVE by 0 (tie→PC)]")
        line, _ = roll.saving_throw("Veskar", "wis", 13, by="Kael", roller=Scripted([9]))
        self.assertEqual(line, "[Veskar WIS save: d20 9+2=11 vs DC 13 — FAIL by 2]")
        line, _ = roll.saving_throw("Veskar", "wis", 13, by="Kael", roller=Scripted([11]))
        self.assertEqual(line, "[Veskar WIS save: d20 11+2=13 vs DC 13 — FAIL by 0 (tie→PC)]")

    def test_d20_and_total_exclusive(self):
        code, lines = run_main(["atk", "Kira", "Veskar", "--d20", "12", "--total", "15"])
        self.assertEqual(code, 1)
        self.assertIn("not allowed with argument", lines[0])

    def test_flat_damage_attack(self):
        from fixture import _edit
        _edit(self.path("npcs/veskar.md"),
              lambda t: t.replace("| dagger   | +5  | 1d4+3 pierce   |", "| kick     | +5  | 3 bludgeoning  |"))
        lines, _ = roll.attack("Veskar", "Kael", with_="kick", roller=Scripted([20]))
        self.assertEqual(lines, ["[Veskar → Kael Ashford: d20 20+5=25 vs AC 18 — CRIT (nat 20) · 3 bludgeoning · "
                                 "Kael Ashford 30→27/30]"])

    def test_check_secret(self):
        code, lines = run_main(["check", "Veskar", "deception", "12", "--secret", "--seed", "1"])
        self.assertEqual(lines, ["[SECRET Veskar deception: d20 5+4=9 vs DC 12 — FAIL by 3]"])
        log = self.path("sessions/session-current.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(log[-1], "  - (GM) roll SECRET Veskar deception: d20 5+4=9 vs DC 12 — FAIL by 3")
        public = [x for x in log if x.startswith("  - ") and "(GM)" not in x]
        self.assertFalse(any("9" in x for x in public))

    def test_check_vs_pc_passive(self):
        line, _ = roll.ability_check("Veskar", "stealth", 15, vs="Kira", roller=Scripted([10]))
        self.assertEqual(line, "[Veskar stealth: d20 10+5=15 vs DC 15 — FAIL by 0 (tie→PC)]")

    def test_contest(self):
        code, lines = run_main(["contest", "Kira", "stealth", "Veskar", "perception", "--d20", "15", "--seed", "1"])
        self.assertEqual(lines, ["[Kira Thornwood stealth d20 15+7=22 vs Veskar perception d20 5+0=5 — Kira Thornwood wins by 17]"])
        # bare adv/dis like the other commands (--mode stays an alias)
        code, lines = run_main(["contest", "Veskar", "stealth", "adv", "Kira", "perception", "--d20", "3", "--seed", "1"])
        self.assertEqual(lines, ["[Veskar stealth d20 (5, 19)→19+5=24 vs Kira Thornwood perception d20 3+5=8 — Veskar wins by 16]"])
        code, lines = run_main(["contest", "Veskar", "stealth", "Kira", "perception", "--mode", "adv",
                                "--d20", "3", "--seed", "1"])
        self.assertEqual(code, 0, lines)

    def test_contest_tie_defender_pc(self):
        line, _ = roll.contest("Veskar", "deception", "Kira", "insight", d20=11, roller=Scripted([10]))
        self.assertEqual(line, "[Veskar deception d20 10+4=14 vs Kira Thornwood insight d20 11+3=14 — "
                               "Kira Thornwood wins by 0 (tie→PC)]")

    def test_contest_passive(self):
        code, lines = run_main(["contest", "Veskar", "stealth", "passive", "--seed", "1"])
        self.assertEqual(lines, ["[Veskar stealth d20 5+5=10 vs passive perception: Kael Ashford 13 — "
                                 "Kael Ashford wins by 3 · Kira Thornwood 15 — Kira Thornwood wins by 5]"])

    def test_contest_passive_skips_srd_npcs(self):
        from lib import md
        doc = md.load(self.path("state/current.md"))
        doc.append_line("On stage", "- **Veskar** (npcs/veskar.md) — at the bar")
        doc.save()
        code, lines = run_main(["contest", "Kira", "stealth", "passive", "--d20", "10"])
        self.assertEqual(lines, ["[Kira Thornwood stealth d20 10+7=17 vs passive perception: "
                                 "Mara 10 — Kira Thornwood wins by 7 · Tobin 10 — Kira Thornwood wins by 7 · "
                                 "Veskar 10 — Kira Thornwood wins by 7]"])

    def test_srd_statblock_numbers(self):
        # commoner: WIS 10, no skills → insight +0
        code, lines = run_main(["check", "Mara", "insight", "12", "--seed", "1"])
        self.assertEqual(code, 0, lines)
        self.assertRegex(lines[0], r"^\[Mara insight: d20 \d+\+0=\d+ vs DC 12")

    def test_srd_missing_data(self):
        from lib import srd
        with mock.patch.object(srd, "DATA", self.tmp / "no-srd"), mock.patch.dict(srd._cache, clear=True):
            code, lines = run_main(["check", "Mara", "insight", "12", "--seed", "1"])
        self.assertEqual(code, 1)
        self.assertIn("run `python engine/fetch_srd.py` once", lines[0])

    def test_out_of_reach(self):
        start_combat(self)
        # move Kael 25 ft away from Veskar (10,10,0)
        from lib import md
        doc = md.load(self.path("state/current.md"))
        t = doc.table("Combatants")
        t.set(t.find("name", "Kael (PC)"), "pos", "(10,35,0)")
        doc.save()
        lines, data = roll.attack("Veskar", "Kael", roller=Scripted([10, 4]))
        self.assertEqual(lines, ["[Veskar → Kael: out of reach (25 ft)]"])
        lines, data = roll.attack("Veskar", "Kael", with_="dagger", roller=Scripted([10, 14]))
        self.assertEqual(lines, ["[Veskar → Kael: d20 (10, 14)→10+5=15 vs AC 15 — MISS "
                                 "(long range: disadvantage, tie→PC)]"])

    def test_srd_ref_in_combat(self):
        # thug: Mace +4, 1d6+2 bludgeoning; AC from the row (Kael 15)
        start_combat(self)
        from lib import md
        doc = md.load(self.path("state/current.md"))
        t = doc.table("Combatants")
        t.set(t.find("name", "Kael (PC)"), "pos", "(15,10,0)")  # 5 ft from the group's edge
        doc.save()
        lines, _ = roll.attack("Thugs", "Kael", roller=Scripted([12, 3]))
        self.assertEqual(lines, ["[Thugs ×3 → Kael: d20 12+4=16 vs AC 15 — HIT · 5 bludgeoning · Kael 9→4/11]"])

    def test_combat_row_ac_and_hp(self):
        start_combat(self)
        lines, _ = roll.attack("Veskar", "Kael", roller=Scripted([2, 4]))
        self.assertEqual(lines, ["[Veskar → Kael: d20 2+14=16 vs AC 15 — HIT · 7 slashing · Kael 9→2/11]"])


if __name__ == "__main__":
    unittest.main()
