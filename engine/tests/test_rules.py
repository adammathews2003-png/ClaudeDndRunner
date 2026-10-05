"""Overrules: rule add|end|list, retcon, overrule-undo, end_scope (docs/design/06
L170-217; docs/design/04 L540-557; plan.md Phase 2 item 6 and Verify)."""
import json
import unittest

from fixture import CampaignCase, give_custom_veskar
from lib import journal, md, resolve
from fixture import run_main
import rules


class Base(CampaignCase):
    def setUp(self):
        super().setUp()
        give_custom_veskar(self)

    def ok(self, *argv):
        code, lines = run_main(list(argv))
        self.assertEqual(code, 0, lines)
        return lines

    def fails(self, *argv):
        code, lines = run_main(list(argv))
        self.assertEqual(code, 1, lines)
        return lines[-1]

    def rows(self):
        return md.load(self.path("state/table-rules.md")).table("Table rules").rows

    def log(self):
        return self.path("sessions/session-current.md").read_text(encoding="utf-8").splitlines()

    def manifests(self):
        return [m for _, m in journal.entries()]


class RuleCommands(Base):
    def test_add_list_end(self):
        self.assertEqual(self.ok("rule", "add", "Crits on 19–20 for this fight", "--scope", "combat",
                                 "--key", "crit-range=19"),
                         ["[rule R1 added · combat · crit-range=19]"])
        self.assertEqual(self.ok("rule", "add", "Potions are a bonus action", "--scope", "campaign"),
                         ["[rule R2 added · campaign]"])
        r = self.rows()
        self.assertEqual(r[0], {"id": "R1", "rule": "Crits on 19–20 for this fight", "key": "crit-range=19",
                                "scope": "combat", "since": "S1 t1", "status": "active"})
        self.assertEqual(self.ok("rule", "list"), [
            "[R1 · Crits on 19–20 for this fight · crit-range=19 · combat · S1 t1 · active]",
            "[R2 · Potions are a bonus action · campaign · S1 t1 · active]",
        ])
        self.assertEqual(self.ok("rule", "end", "R1", "--reason", "boss down"), ["[rule R1 ended — boss down]"])
        self.assertEqual(self.rows()[0]["status"], "ended (boss down)")
        self.assertEqual(self.ok("rule", "end", "R2"), ["[rule R2 ended]"])
        self.assertEqual(self.rows()[1]["status"], "ended")
        self.assertEqual(self.log()[-4:], [
            "  - [overrule] rule R1 added: Crits on 19–20 for this fight (combat)",
            "  - [overrule] rule R2 added: Potions are a bonus action (campaign)",
            "  - [overrule] rule R1 ended: boss down",
            "  - [overrule] rule R2 ended",
        ])
        self.assertTrue(all(m["overrule"] for m in self.manifests()))
        self.assertIn("already ended", self.fails("rule", "end", "R1"))

    def test_newer_wins_and_reports_override(self):
        self.ok("rule", "add", "crit 19", "--scope", "combat", "--key", "crit-range=19")
        self.assertEqual(self.ok("rule", "add", "crit 18", "--scope", "session", "--key", "crit-range=18"),
                         ["[rule R2 added · session · crit-range=18 · overrides R1 (crit-range=19)]"])
        self.assertEqual(resolve.crit_threshold(), (18, "R2"))
        self.assertEqual(self.ok("rule", "list")[0],
                         "[R1 · crit 19 · crit-range=19 · combat · S1 t1 · active · overridden]")

    def test_key_validation(self):
        self.assertIn("not a valid value", self.fails("rule", "add", "x", "--scope", "combat", "--key", "crit-range=12"))
        self.assertIn("scope is", self.fails("rule", "add", "x", "--scope", "forever"))
        self.assertEqual(self.ok("rule", "add", "Fumbles", "--scope", "until we reach Thornbury", "--key", "fumbles=on"),
                         ["[rule R1 added · until we reach Thornbury · fumbles=on · unknown key 'fumbles': free text only]"])
        self.assertEqual(resolve.active_keys(), {})

    def test_since_uses_session_and_turn(self):
        self.ok("log", "one")
        self.ok("log", "two")
        (self.camp / "sessions" / "history" / "session-01.md").write_text("# s1\n", encoding="utf-8")
        self.ok("rule", "add", "x", "--scope", "session")
        self.assertEqual(self.rows()[0]["since"], "S2 t3")

    def test_crit_range_rule_makes_19_crit(self):
        # seed 1 rolls a natural 5; find the seed whose first d20 is 19
        from lib import dice
        seed = next(s for s in range(200) if dice.Roller(s).d20().natural == 19)
        lines = self.ok("atk", "Veskar", "Kael", "--with", "dagger", "--no-apply", "--seed", str(seed))
        self.assertIn("— HIT ·", lines[0])
        self.ok("rule", "add", "Crits on 19–20 for this fight", "--scope", "combat", "--key", "crit-range=19")
        lines = self.ok("atk", "Veskar", "Kael", "--with", "dagger", "--no-apply", "--seed", str(seed))
        self.assertIn("d20 19+5=24 vs AC 18 — CRIT (nat 19, crit-range 19 (R1))", lines[0])

    def test_ties_raw_rule(self):
        self.ok("rule", "add", "RAW ties tonight", "--scope", "session", "--key", "ties=raw")
        code, lines = run_main(["save", "Kael", "dex", "14", "--d20", "14"])
        self.assertEqual(lines, ["[Kael Ashford DEX save: d20 14+0=14 vs DC 14 — SAVE by 0]"])

    def test_dice_mode_rule(self):
        self.assertIn("rolls their own d20", self.fails("save", "Kael", "dex", "14"))
        self.ok("rule", "add", "GM rolls everything", "--scope", "scene", "--key", "dice-mode=gm-rolls-all")
        self.assertEqual(self.ok("save", "Kael", "dex", "14", "--seed", "1"),
                         ["[Kael Ashford DEX save: d20 5+0=5 vs DC 14 — FAIL by 9]"])


class Scopes(Base):
    def test_end_scope(self):
        self.ok("rule", "add", "a", "--scope", "combat", "--key", "crit-range=19")
        self.ok("rule", "add", "b", "--scope", "scene")
        self.ok("rule", "add", "c", "--scope", "combat")
        self.assertEqual(rules.end_scope("combat"), ["[rule R1 ended — combat over]", "[rule R3 ended — combat over]"])
        self.assertEqual([r["status"] for r in self.rows()], ["ended (combat over)", "active", "ended (combat over)"])
        self.assertEqual(rules.end_scope("combat"), [])
        self.assertEqual(rules.end_scope("scene"), ["[rule R2 ended — scene over]"])
        self.assertEqual(self.log()[-1], "  - rule R2 ended — scene over")


class Retcon(Base):
    def test_retcon_is_public_overrule(self):
        self.ok("log", "Kira climbs")
        self.assertEqual(self.ok("do", "retcon \"Kira's climb went unseen\" --turn 1; hp Kira -2"),
                         ["[retcon of turn 1 logged]", "[hp Kira Thornwood 30→28/30]"])
        self.assertEqual(self.log()[-2:], ["  - [overrule] retcon turn 1: Kira's climb went unseen",
                                           "  - hp Kira Thornwood 30→28/30"])
        self.assertTrue(self.manifests()[-1]["overrule"])


class OverruleUndo(Base):
    def test_undo_overrule_after_unrelated_turns(self):
        rules_before = self.read_bytes("state/table-rules.md")
        kira_before = self.read_bytes("pcs/kira-thornwood.md")
        self.ok("do", "retcon \"Kira wasn't hit\" --turn 1; hp Kira -2; rule add \"x\" --scope combat")
        self.ok("hp", "Kael", "-3")  # an ordinary later turn on another file
        self.ok("log", "later")
        lines = self.ok("overrule-undo")
        self.assertTrue(lines[0].startswith("[overrule undone: gm.py do "), lines)
        self.assertTrue(lines[0].endswith("restored pcs/kira-thornwood.md, state/table-rules.md]"), lines)
        self.assertEqual(self.read_bytes("state/table-rules.md"), rules_before)
        self.assertEqual(self.read_bytes("pcs/kira-thornwood.md"), kira_before)
        self.assertEqual(md.load(self.path("pcs/kael-ashford.md")).front["hp"]["current"], 27)
        self.assertTrue(self.log()[-1].startswith("  - [overrule] undo of overrule batch 0001: gm.py do "))
        self.assertIn("no overrule batch", self.fails("overrule-undo"))
        # the overrule-undo itself is journaled: plain undo brings the rule back
        self.ok("undo")
        self.assertEqual(self.rows()[0]["id"], "R1")

    def test_overrule_undo_again_after_plain_undo(self):
        rules_before = self.read_bytes("state/table-rules.md")
        self.ok("rule", "add", "x", "--scope", "combat", "--campaign", str(self.camp))
        self.ok("overrule-undo")
        self.assertEqual(self.read_bytes("state/table-rules.md"), rules_before)
        undo_batch = self.manifests()[-1]
        self.assertEqual(undo_batch["undoes"], "0001")
        self.assertNotIn("undone", self.manifests()[0])  # old manifests are never edited
        self.assertTrue(self.log()[-1].endswith("gm.py rule add x --scope combat"), self.log()[-1])
        self.ok("undo")
        self.assertEqual(self.rows()[0]["id"], "R1")
        lines = self.ok("overrule-undo")
        self.assertTrue(lines[0].startswith("[overrule undone: gm.py rule add x"), lines)
        self.assertEqual(self.read_bytes("state/table-rules.md"), rules_before)

    def test_refuses_on_conflicting_later_batch(self):
        self.ok("do", "rule add \"x\" --scope combat; hp Kira -2")
        self.ok("hp", "Kira", "-1")
        msg = self.fails("overrule-undo")
        self.assertIn("refused: later batches touched the same files", msg)
        self.assertIn("pcs/kira-thornwood.md", msg)
        self.assertEqual(self.rows()[0]["status"], "active")

    def test_manifest_flag(self):
        self.ok("rule", "add", "x", "--scope", "combat")
        self.ok("hp", "Kira", "-1")
        ms = self.manifests()
        self.assertEqual([m["overrule"] for m in ms], [True, False])
        raw = json.loads((self.camp / ".gm" / "journal" / "0001" / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(raw["overrule"])


if __name__ == "__main__":
    unittest.main()
