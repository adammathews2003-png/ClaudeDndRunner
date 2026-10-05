"""Phase 6: pc draft/check/card/write/edit/roster/level-pending/levelup and xp
(plan.md Phase 6 → Verify and Guards)."""
import json

from fixture import CampaignCase, run_main, set_front_raw
from lib import chargen, md
import pc

GRASK = ["pc", "draft", "grask", "--set", 'race=half-orc', "class=barbarian", "level=3", "subclass=berserker",
         "--equip", "greataxe; 4 javelins; explorer's pack"]
GRASK_DONE = ["pc", "draft", "grask", "--set", "name=Grask", "base-scores=str 15 con 14 dex 13 wis 12 cha 10 int 8",
              "skills=athletics, perception", "hp-method=max"]


def front(case, rel):
    return md.load(case.path(rel)).front


class Intake(CampaignCase):
    def test_check_matches_spec(self):
        code, lines = run_main(GRASK)
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], "[PC CHECK] grask · half-orc barbarian (berserker) 3")
        self.assertEqual(lines[1], "DERIVED   speed 30 · prof +2 · darkvision 60 · hit die d12 · saves STR, CON")
        text = "\n".join(lines)
        self.assertIn("rage 3/long", text)
        self.assertIn("half-orc: +2 STR +1 CON", text)
        self.assertIn("HP for levels 2–3: by hp-method (level 1 = 12)", text)
        self.assertIn("standard array → STR 15 CON 14 DEX 13 WIS 12 CHA 10 INT 8 before racial bonuses, "
                      "so STR 17, CON 15", text)
        self.assertIn("2 barbarian skills from: Animal Handling, Athletics, Intimidation, Nature, Perception, Survival",
                      text)
        self.assertIn("hp-method: max or roll", text)
        for label in ("PENDING", "MISSING", "DEFAULTS", "CONFLICTS", "CUSTOM"):
            self.assertTrue(any(line.startswith(label) for line in lines), label)

    def test_write_round_trips_in_order(self):
        run_main(GRASK)
        self.assertEqual(run_main(["pc", "write", "grask"])[0], 1)  # still missing things
        run_main(GRASK_DONE)
        code, lines = run_main(["pc", "card", "grask"])
        self.assertIn("HP 42 · AC 13 · speed 30", "\n".join(lines))
        code, lines = run_main(["pc", "write", "grask"])
        self.assertEqual(lines, ["[pc written: pcs/grask.md · HP 42 · AC 13]"])
        doc = md.load(self.path("pcs/grask.md"))
        self.assertEqual(list(doc.front), pc.ORDER)
        self.assertEqual(len(pc.ORDER), 26)
        self.assertEqual(doc.front["hp"], {"current": 42, "max": 42})
        self.assertEqual(doc.front["skills"], {"athletics": 5, "intimidation": 2, "perception": 3})
        self.assertEqual(doc.front["xp"], 900)
        self.assertIsNone(doc.front["level-pending"])
        self.assertEqual(doc.table("Attacks").rows[0]["hit"], "+5")
        again = md.load(self.path("pcs/grask.md"))
        self.assertEqual(again.text(), doc.text())
        self.assertFalse(pc.draft_path("grask").exists())
        self.assertIn("Grask 42/42 AC13", "\n".join(run_main(["brief"])[1]))

    def test_kael_rederived_from_scratch(self):
        d = {"name": "Kael", "race": "human", "class": "cleric", "subclass": "life", "level": 3,
             "background": "acolyte", "scores": {"str": 15, "dex": 11, "con": 14, "int": 9, "wis": 16, "cha": 12},
             "skills": "medicine, persuasion", "hp-method": "max",
             "equipment": "chain mail; shield; mace", "cantrips": "sacred flame, guidance, spare the dying"}
        s = chargen.derive(d)
        kael = front(self, "pcs/kael-ashford.md")
        for k in ("ac", "hp", "skills", "passive-perception", "prof", "saves"):
            self.assertEqual(s.fields[k], kael[k], k)
        self.assertEqual(s.fields["spell-dc"], 13)
        self.assertEqual(s.attacks[0]["hit"], "+4")

    def test_roll_method_and_reported_rolls(self):
        run_main(GRASK)
        run_main(GRASK_DONE[:-1] + ["hp-method=roll"])  # draft re-run: rolls 2 dice
        d = pc.load_draft("grask")
        self.assertEqual(len(d["hp-rolls"]), 2)
        log = self.path("sessions/session-current.md").read_text(encoding="utf-8")
        self.assertIn("HP roll grask level 2: d12", log)
        run_main(["pc", "draft", "grask", "--hp-rolls", "1,12"])
        s = chargen.derive(pc.load_draft("grask"))
        self.assertEqual(s.fields["hp"]["max"], 14 + 3 + 14)  # 12+2, 1+2, 12+2

    def test_warnings_not_blocks(self):
        run_main(["pc", "draft", "x", "--set", "name=X", "race=human", "class=wizard", "level=1",
                  "base-scores=15,15,15,15,15,8", "hp-method=max", "--equip", "plate armor"])
        code, lines = run_main(["pc", "check", "x"])
        text = "\n".join(lines)
        self.assertIn("point buy costs 45 (> 27)", text)
        self.assertIn("not proficient with Plate Armor", text)
        self.assertIn("3 wizard cantrips", text)

    def test_from_sheet(self):
        sheet = self.tmp / "sheet.txt"
        sheet.write_text("Name: Bren Ashdown\nRace: Hill Dwarf\nClass: Fighter\nLevel: 2\n"
                         "STR 16 DEX 12 CON 15 INT 10 WIS 13 CHA 8\nEquipment: chain mail, longsword, shield\n",
                         encoding="utf-8")
        code, lines = run_main(["pc", "draft", "bren", "--from-sheet", str(sheet), "--set", "hp-method=max",
                                "fighting-style=defense", "skills=athletics, perception"])
        d = pc.load_draft("bren")
        self.assertEqual(d["race"], "Hill Dwarf")
        self.assertEqual(d["scores"]["con"], 15)
        s = chargen.derive(d)
        self.assertEqual(s.fields["ac"], 16 + 2 + 1)            # chain + shield + Defense
        self.assertEqual(s.fields["hp"]["max"], 10 + 2 + 1 + 10 + 2 + 1)   # dwarven toughness


class Edit(CampaignCase):
    def test_overrides_survive_edit(self):
        run_main(["pc", "edit", "Kira", "--set", "overrides=ac:17"])
        self.assertEqual(front(self, "pcs/kira-thornwood.md")["ac"], 17)
        code, lines = run_main(["pc", "edit", "Kira", "--item", "+longbow"])
        self.assertEqual(code, 0, lines)
        f = front(self, "pcs/kira-thornwood.md")
        self.assertEqual(f["ac"], 17)
        self.assertEqual(f["overrides"], {"ac": 17})
        rows = md.load(self.path("pcs/kira-thornwood.md")).table("Attacks").rows
        self.assertIn(("longbow", "+5"), [(r["name"], r["hit"]) for r in rows])   # elf weapon training
        text = self.path("pcs/kira-thornwood.md").read_text(encoding="utf-8")
        self.assertIn("quiver (20 arrows); longbow", text)

    def test_edit_hp_method_keeps_hp(self):
        run_main(["pc", "edit", "Kira", "--set", "hp-method=roll"])
        f = front(self, "pcs/kira-thornwood.md")
        self.assertEqual(f["hp-method"], "roll")
        self.assertEqual(f["hp"], {"current": 30, "max": 30})

    def test_roster(self):
        code, lines = run_main(["pc", "roster", "--absent", "Kira", "--present", "Kael"])
        self.assertEqual(lines, ["[roster: Kael Ashford present · Kira Thornwood absent (autopilot)]"])
        self.assertIs(front(self, "pcs/kira-thornwood.md")["present"], False)
        self.assertIn("Kira (autopilot)", "\n".join(run_main(["brief"])[1]))


class LevelUp(CampaignCase):
    def test_kael_to_4(self):
        self.assertEqual(run_main(["pc", "levelup", "Kael", "--plan"])[0], 1)   # nothing pending
        run_main(["pc", "level-pending", "Kael", "--to", "4"])
        code, lines = run_main(["pc", "levelup", "Kael", "--plan"])
        text = "\n".join(lines)
        self.assertIn("GRANTED   HP +10 (max: d8 8 + CON +2)", text)
        self.assertIn("CHOICE    asi:", text)
        code, lines = run_main(["pc", "levelup", "Kael", "--choose", "asi=wis+2", "--apply"])
        self.assertEqual(code, 1)
        self.assertIn("unanswered", lines[-1])
        code, lines = run_main(["pc", "levelup", "Kael", "--choose", "asi=wis+2", "cantrips=+thaumaturgy", "--apply"])
        self.assertEqual(lines, ["[levelup Kael Ashford 3→4 · HP 30→40 · AC 18 · ASI wis+2]"])
        f = front(self, "pcs/kael-ashford.md")
        self.assertEqual((f["level"], f["hp"], f["scores"]["wis"]), (4, {"current": 40, "max": 40}, 18))
        self.assertEqual(f["hit-dice"], {"die": "d8", "left": 4})
        self.assertIsNone(f["level-pending"])
        text = self.path("pcs/kael-ashford.md").read_text(encoding="utf-8")
        self.assertIn("reached level 4 — HP +10 (max 8 +2 CON); ASI wis+2", text)
        self.assertIn("Spell save DC 14 · spell attack +6.", text)
        self.assertIn("| sacred flame | DC 14 DEX", text)
        self.assertIn("| spell slot 2 | 3 | 3 | long |", text)
        log = self.path("sessions/session-current.md").read_text(encoding="utf-8")
        self.assertIn("levelup Kael Ashford 3→4 · HP 30→40 · ASI wis+2", log)

    def test_roll_method(self):
        set_front_raw(self, "pcs/kira-thornwood.md", "hp-method", "roll")
        run_main(["pc", "level-pending", "Kira"])
        code, lines = run_main(["pc", "levelup", "Kira", "--choose", "asi=dex+2", "--hp-roll", "1", "--apply"])
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], "[HP roll Kira Thornwood level 4: d8 1 +2 CON]")
        self.assertEqual(front(self, "pcs/kira-thornwood.md")["hp"]["max"], 33)

    def test_asi_con_is_retroactive(self):
        run_main(["pc", "level-pending", "Kira"])
        # rogue 4: ASI; CON 14→16 adds +1 for each of the 3 earlier levels
        code, lines = run_main(["pc", "levelup", "Kira", "--choose", "asi=con+2", "--apply"])
        self.assertEqual(code, 0, lines)
        self.assertEqual(front(self, "pcs/kira-thornwood.md")["hp"]["max"], 30 + 8 + 3 + 3)


class Xp(CampaignCase):
    def award(self, *args):
        return run_main(["xp", "award", *args, "--reason", "test"])

    def test_milestone_poc(self):
        code, lines = self.award("1800", "--present")
        self.assertEqual(lines, ["[XP +900 each → Kael 900→1,800 · Kira 900→1,800]"])
        code, lines = self.award("1800")
        self.assertIn("★ past the L4 threshold (milestone: no level-up)", lines[0])
        self.assertIsNone(front(self, "pcs/kael-ashford.md")["level-pending"])
        self.assertEqual(front(self, "pcs/kael-ashford.md")["xp"], 2700)

    def test_xp_advancement_and_undo(self):
        set_front_raw(self, "state/current.md", "advancement", "xp")
        self.award("1800")
        self.assertIsNone(front(self, "pcs/kira-thornwood.md")["level-pending"])
        code, lines = self.award("1800")
        self.assertIn("Kira 1,800→2,700 ★ L4 at 2,700: level-up pending", lines[0])
        self.assertEqual(front(self, "pcs/kira-thornwood.md")["level-pending"], 4)
        run_main(["undo"])
        self.assertEqual(front(self, "pcs/kira-thornwood.md")["xp"], 1800)
        self.assertIsNone(front(self, "pcs/kira-thornwood.md")["level-pending"])

    def test_absent_half(self):
        set_front_raw(self, "state/current.md", "xp-absent", "half")
        set_front_raw(self, "pcs/kira-thornwood.md", "present", False)
        code, lines = self.award("1000", "--to", "Kael,Kira")
        self.assertEqual(lines, ["[XP +1,000 each → Kael 900→1,900 · Kira 900→1,400 (absent: 500)]"])

    def test_from_combat_once(self):
        p = self.path(".gm/last-combat.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"total": 500, "foes": []}), encoding="utf-8")
        self.assertEqual(self.award("from-combat")[1], ["[XP +250 each → Kael 900→1,150 · Kira 900→1,150]"])
        code, lines = self.award("from-combat")
        self.assertEqual(code, 1)
        self.assertIn("already awarded", lines[0])

    def test_show_set_and_off(self):
        self.assertEqual(run_main(["xp", "show", "Kira"])[1], ["[Kira: L3 · 900 XP · L4 at 2,700]"])
        run_main(["xp", "set", "Kira", "1000", "--reason", "fix"])
        self.assertEqual(front(self, "pcs/kira-thornwood.md")["xp"], 1000)
        set_front_raw(self, "state/current.md", "xp-tracking", "off")
        for args in (["xp", "show"], ["xp", "award", "10", "--reason", "x"], ["xp", "set", "Kira", "1", "--reason", "x"]):
            code, lines = run_main(args)
            self.assertEqual(code, 1, args)
            self.assertIn("tracking is off", lines[0])
