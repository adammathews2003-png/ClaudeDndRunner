"""Phase 15: inspiration, readied actions, magic items, downtime, allied creatures,
weather, encumbrance, faction renown, mounts and lingering injuries (plan.md Phase 15 →
Verify and Guards; docs/design/02 → Table mechanics → Phase 15; 06 → Table mechanics →
Phase 15)."""
from pathlib import Path

from fixture import CampaignCase, _edit, give_custom_veskar, run_main, set_front_raw
from lib import md
from test_phase13 import COMBAT

CLOAK = "cloak of protection (uncommon, attune, ac +1, saves +1)"
WAND = "wand of magic missiles (uncommon, charges 1/7, recharge 1d6+1 dawn, destroy on 1)"
INJURIES = """# Lingering injuries (test table)

| roll | result | effect | cure |
|------|--------|--------|------|
| 1-10 | Lose an eye | disadvantage on sight Perception and ranged attacks | regenerate |
| 11-20 | Festering wound | HP max −1 each day | a DC 15 Medicine check |
"""


class Base(CampaignCase):
    def setUp(self):
        super().setUp()
        give_custom_veskar(self)
        from lib import journal
        journal.log_delta("(test) the session is under way")   # an open turn: undo restores to it

    def ok(self, *argv):
        code, lines = run_main(list(argv))
        self.assertEqual(code, 0, lines)
        return lines

    def fails(self, *argv):
        code, lines = run_main(list(argv))
        self.assertEqual(code, 1, lines)
        return lines[-1]

    def front(self, rel):
        return md.load(self.path(rel)).front

    def text(self, rel):
        return self.path(rel).read_text(encoding="utf-8")

    def setting(self, key, value):
        set_front_raw(self, "state/current.md", key, value)

    def fight(self):
        _edit(self.path("state/current.md"), lambda t: t.replace("## Combat\n(not in combat)", COMBAT, 1))

    def row(self, name):
        t = md.load(self.path("state/current.md")).table("Combatants")
        return next(r for r in t.rows if r["name"].startswith(name))

    def party(self):
        return next(x for x in self.ok("brief") if x.startswith("Party:"))

    def snapshot(self):
        out = {}
        for p in self.camp.rglob("*.md"):
            if ".gm" in p.parts:
                continue
            data = p.read_bytes()
            if p.name == "session-current.md":
                data = b"\n".join(x for x in data.splitlines() if b"  - undo turn" not in x)
            out[p.relative_to(self.camp).as_posix()] = data
        return out

    def assert_undoes(self, *argv):
        before = self.snapshot()
        out = self.ok(*argv)
        self.assertNotEqual(self.snapshot(), before, f"{argv} changed nothing")
        self.ok("undo")
        self.assertEqual(self.snapshot(), before, f"undo of {argv} left changes")
        return out

    def equip(self, entry):
        """Put an entry on Kira's Equipped line."""
        _edit(self.path("pcs/kira-thornwood.md"), lambda t: t.replace(
            "- Equipped: leather armor,", f"- Equipped: leather armor, {entry},", 1))


class Defaults(CampaignCase):
    def test_settings(self):
        from lib import campaign
        s = campaign.SETTINGS
        self.assertEqual((s["inspiration"], s["downtime"], s["weather"], s["encumbrance"], s["renown"],
                          s["lingering-injuries"], s["upkeep"]),
                         ("advantage", "light", "off", "off", "off", "off", "off"))


# ---------- (2) inspiration ----------

class Inspiration(Base):
    def test_verify_spent_once(self):
        self.fight()
        out = self.assert_undoes("inspire", "Kira", "the toast to the dead")
        self.assertEqual(out, ["[inspire Kira — the toast to the dead · ★ (advantage)]"])
        self.ok("inspire", "Kira", "the toast to the dead")
        self.assertIn("already has inspiration", self.fails("inspire", "Kira"))
        self.assertIn("Kira 30/30 AC14 ★", self.party())
        out = self.ok("atk", "Kira", "Veskar", "--with", "shortbow", "--d20", "12", "--insp")
        self.assertIn("inspiration: advantage", out[0])
        self.assertNotIn("inspiration", self.front("pcs/kira-thornwood.md"))
        self.assertIn("has no inspiration", self.fails("atk", "Kira", "Veskar", "--with", "shortbow",
                                                       "--d20", "12", "--insp"))

    def test_tool_rolls_with_advantage_and_saves_checks(self):
        self.setting("dice-mode", "gm-rolls-all")
        self.ok("inspire", "Kira")
        out = self.ok("--seed", "4", "save", "Kira", "dex", "12", "--insp")
        self.assertIn("d20 (", out[0])                      # two dice
        self.assertIn("inspiration: advantage", out[0])
        self.ok("inspire", "Kira")
        out = self.ok("check", "Kira", "stealth", "12", "dis", "--d20", "9", "--insp")
        self.assertIn("inspiration: advantage, adv and dis cancel", out[0])

    def test_reroll_and_off(self):
        self.setting("inspiration", "reroll")
        self.ok("inspire", "Kira")
        out = self.ok("check", "Kira", "stealth", "12", "--d20", "15", "--insp")
        self.assertIn("inspiration: reroll (this roll stands)", out[0])
        self.setting("inspiration", "off")
        self.assertIn("inspiration: off", self.fails("inspire", "Kira"))
        self.assertIn("inspiration: off", self.fails("check", "Kira", "stealth", "12", "--d20", "3", "--insp"))
        self.setting("inspiration", "advantage")
        self.assertIn("is not a PC", self.fails("inspire", "Mara"))
        self.setting("inspiration", "advantage")
        self.assertIn("is not a PC", self.fails("inspire", "Mara"))


# ---------- (3) readied actions ----------

class Ready(Base):
    def test_verify_reminder_and_lapse(self):
        self.fight()
        out = self.assert_undoes("ready", "Kira", "shoot whoever opens the door, then duck")
        self.assertEqual(out, ["[ready Kira: shoot whoever opens the door; then duck]"])
        self.ok("ready", "Kira", "shoot whoever opens the door, then duck")
        self.assertIn("ready: shoot whoever opens the door; then duck", self.row("Kira")["conditions"])
        out = self.ok("combat", "next")                              # Veskar's turn
        self.assertEqual(out[0], "[round 1 · up: Veskar]")
        self.assertIn("[Readied: Kira — shoot whoever opens the door; then duck]", out)
        out = self.ok("combat", "next")                              # Kael's turn
        self.assertIn("[Readied: Kira — shoot whoever opens the door; then duck]", out)
        out = self.ok("combat", "next")                              # Kira's own turn: it lapses
        self.assertIn("[ready Kira lapsed (unused): shoot whoever opens the door; then duck]", out)
        self.assertFalse(any(x.startswith("[Readied") for x in out))
        self.assertEqual(self.row("Kira")["conditions"], "—")

    def test_fire_drop_and_spell(self):
        self.fight()
        self.ok("ready", "Kira", "stab the first guard through the door")
        self.assertIn("already has a readied action", self.fails("ready", "Kira", "x"))
        out = self.assert_undoes("ready", "Kira", "fire")
        self.assertEqual(out, ["[ready Kira fires: stab the first guard through the door · uses Kira's reaction]"])
        self.ok("ready", "Kira", "drop")
        self.assertIn("no readied action", self.fails("ready", "Kira", "fire"))
        out = self.ok("ready", "Kael", "when Veskar moves", "--spell", "hold person")
        self.assertIn("conc Kael hold-person · 2r", "\n".join(out))
        self.assertIn("conc hold-person", self.row("Kael")["conditions"])
        out = self.ok("ready", "Kael", "drop")
        self.assertIn("conc Kael ends hold-person (readied spell dropped)", "\n".join(out))
        self.ok("combat", "end")
        self.assertIn("only in combat", self.fails("ready", "Kira", "x"))

    def test_combat_end_strips_it(self):
        self.fight()
        self.ok("ready", "Kira", "shoot")
        self.ok("combat", "end")
        self.assertEqual(self.front("pcs/kira-thornwood.md")["conditions"], [])


# ---------- (4) magic items ----------

class Magic(Base):
    def test_verify_fourth_attunement_refused(self):
        for item in ("ring of protection (rare, attune, ac +1, saves +1)", "amulet of health (rare, attune)",
                     "ring of warmth (uncommon, attune)", CLOAK):
            self.ok("item", "Kira", "+", item)
        self.assertIn("takes a short rest", self.fails("attune", "Kira", "ring of protection"))
        out = self.assert_undoes("attune", "Kira", "ring of protection", "--during-rest")
        self.assertEqual(out[0], "[attune Kira ring of protection (1/3) · not on the Equipped line, "
                                 "so its bonuses don't count yet]")
        for item in ("ring of protection", "amulet of health", "ring of warmth"):
            self.ok("attune", "Kira", item, "--during-rest")
        self.assertIn("attuned to 3 items already", self.fails("attune", "Kira", "cloak of protection", "--during-rest"))
        self.assertIn("already attuned", self.fails("attune", "Kira", "ring of warmth", "--during-rest"))
        self.assertEqual(self.front("pcs/kira-thornwood.md")["attuned"],
                         ["ring of protection", "amulet of health", "ring of warmth"])
        self.ok("item", "Kira", "+", "bag of holding (uncommon)")
        self.assertIn("doesn't need attunement", self.fails("attune", "Kira", "bag of holding", "--during-rest"))
        self.assert_undoes("unattune", "Kira", "ring of warmth")

    def test_bonuses_feed_the_numbers(self):
        self.equip(CLOAK)
        self.equip("shortsword +1 (uncommon, attack +1, damage +1)")
        self.ok("item", "Kira", "-shortsword")                  # the plain one goes
        out = self.ok("save", "Kira", "dex", "15", "--d20", "10")
        self.assertIn("d20 10+5=15", out[0])                    # not attuned: no bonus yet
        out = self.ok("rest", "short", "Kira", "--attune", 'Kira=cloak of protection')
        self.assertIn("[attune Kira cloak of protection (1/3)]", out)
        out = self.ok("save", "Kira", "dex", "15", "--d20", "10")
        self.assertIn("d20 10+6=16", out[0])
        self.assertIn("Kira 30/30 AC15", self.party())
        card = "\n".join(self.ok("pc", "card", "Kira"))
        self.assertIn("AC 15 (14 + items)", card)
        self.assertIn("cloak of protection (attuned, ac +1, saves +1)", card)
        self.assertIn("attuned 1/3", card)
        self.assertIn("Attack: shortsword +6, 1d6+3+1 pierce (5)", card)
        self.assertIn("Attack: shortbow +5, 1d6+3 pierce", card)   # the bonus is the named weapon's
        self.fight()
        out = self.ok("atk", "Veskar", "Kira", "--with", "dagger", "--seed", "1")
        self.assertIn("vs AC 14", out[0])                       # the Combatants row's AC wins in a fight

    def test_verify_charge_and_dawn_recharge(self):
        self.ok("item", "Kira", "+", WAND)
        self.assertIn("can't spend 2", self.fails("charge", "Kira", "wand", "-2"))
        out = self.assert_undoes("--seed", "3", "charge", "Kira", "wand", "-1")
        self.assertTrue(out[0].startswith("[charge Kira wand of magic missiles 1→0/7 · last charge: d20 "), out)
        out = self.ok("--seed", "3", "charge", "Kira", "wand", "-1")
        self.assertIn("charges 0/7", self.text("pcs/kira-thornwood.md"))
        out = self.ok("--seed", "5", "time", "to", "dawn")
        rec = next(x for x in out if "Recharge (dawn)" in x)
        self.assertIn("Kira's wand of magic missiles 0→", rec)
        n = int(rec.split("0→")[1].split("/")[0])
        self.assertTrue(2 <= n <= 7, rec)
        self.assertIn(f"charges {n}/7", self.text("pcs/kira-thornwood.md"))
        self.assertFalse(any("Recharge" in x for x in self.ok("time", "+2h")))

    def test_destroyed_on_a_one(self):
        self.ok("item", "Kira", "+", WAND)
        for seed in range(40):          # find a seed whose d20 is a 1
            from lib import dice
            if dice.Roller(seed).die(20) == 1:
                break
        out = self.ok("--seed", str(seed), "charge", "Kira", "wand", "-1")
        self.assertIn("d20 1 — destroyed", out[0])
        self.assertNotIn("wand", self.text("pcs/kira-thornwood.md"))

    def test_identify_and_gm_name_stays_private(self):
        out = self.ok("item", "Kira", "+", "unidentified: smoky glass ring (GM: ring of protection)")
        public = [x for x in self.text("sessions/session-current.md").splitlines()
                  if x.startswith("  - ") and not x.startswith("  - (GM)")]
        self.assertFalse(any("ring of protection" in x for x in public))
        self.assertIn("smoky glass ring (unidentified)", "\n".join(self.ok("pc", "card", "Kira")))
        self.assertNotIn("ring of protection", "\n".join(self.ok("pc", "card", "Kira")))
        self.assertIn("isn't identified yet", self.fails("attune", "Kira", "smoky glass ring", "--during-rest"))
        out = self.assert_undoes("identify", "Kira", "smoky glass ring", "--spell")
        self.assertEqual(out, ["[identify Kira smoky glass ring → ring of protection (identify spell) · "
                               "rare, attune, ac +1, saves +1]"])
        self.ok("identify", "Kira", "smoky glass ring")
        self.assertIn("ring of protection (rare, attune, ac +1, saves +1)", self.text("pcs/kira-thornwood.md"))

    def test_srd_item(self):
        out = self.ok("srd", "item", "wand", "of", "magic", "missiles")
        self.assertEqual(out[-1], "Inventory: wand of magic missiles (uncommon, charges 7/7, recharge 1d6+1 dawn, destroy on 1)")

    def test_lf_file(self):
        p = self.path("pcs/kira-thornwood.md")
        p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
        self.equip(CLOAK)
        self.ok("attune", "Kira", "cloak of protection", "--during-rest")
        self.assertIn("Kira 30/30 AC15", self.party())
        self.assertNotIn(b"\r\n", p.read_bytes())


# ---------- (5) downtime ----------

class Downtime(Base):
    def test_verify_craft(self):
        self.setting("upkeep", "on")
        out = self.assert_undoes("downtime", "Kira", "craft", "chain shirt", "10d", "--lifestyle", "modest")
        self.assertEqual(out[0], "[downtime Kira craft chain shirt · 10 days · progress 0 gp→50 gp of 50 gp · "
                                 "done: chain shirt added to the pack]")
        self.assertIn("[lifestyle modest × 10 days: 10 gp]", out)
        self.assertIn("[coin Kira Thornwood 10→0 gp]", out)        # 35 − 25 materials − 10 lifestyle
        self.assertTrue(any(x.startswith("[TIME] Day 1 18:30 → Day 11 18:30 (+10d)") for x in out), out)
        self.ok("downtime", "Kira", "craft", "chain shirt", "10d", "--lifestyle", "modest")
        self.assertIn("chain shirt", self.text("pcs/kira-thornwood.md").split("## Inventory")[1].split("## ")[0])

    def test_default_charges_nothing_and_progress_rows(self):
        out = self.ok("downtime", "Kira", "craft", "chain shirt", "4d", "--lifestyle", "modest", "--no-clock")
        self.assertIn("progress 0 gp→20 gp of 50 gp", out[0])
        self.assertIn("[materials (half the price) 25 gp — not charged (upkeep: off)]", out)
        self.assertIn("[lifestyle modest × 4 days 4 gp — not charged (upkeep: off)]", out)
        self.assertIn("35 gp", self.text("pcs/kira-thornwood.md"))
        self.assertFalse(any(x.startswith("[TIME]") for x in out))
        t = md.load(self.path("pcs/kira-thornwood.md")).table("Downtime")
        self.assertEqual(t.rows[0], {"activity": "craft chain shirt", "progress": "20 gp", "goal": "50 gp",
                                     "cost/day": "1 gp (modest)", "notes": ""})
        out = self.ok("downtime", "Kira", "craft", "chain shirt", "2d", "--no-clock")
        self.assertIn("progress 20 gp→30 gp of 50 gp", out[0])
        self.assertFalse(any("materials" in x for x in out))       # paid when the work started
        self.assertIn("Kira: craft chain shirt 30 gp/50 gp", self.ok("downtime", "status")[0])
        out = self.ok("downtime", "Kael", "train", "thieves' tools", "20d", "--no-clock")
        self.assertIn("progress 0→20/250 days", out[0])
        self.assertIn("training fees (20 days × 1 gp) 20 gp — not charged", "\n".join(out))

    def test_off_full_and_unaffordable(self):
        self.assertIn("craft | train", self.fails("downtime", "Kira", "crime", "heist", "3d"))
        self.setting("downtime", "full")
        self.assertIn("no campaign table", self.fails("downtime", "Kira", "crime", "heist", "3d"))
        (self.camp / "tables").mkdir(exist_ok=True)
        self.path("tables/downtime-crime.md").write_text(
            "| roll | result |\n|---|---|\n| 1-6 | the watch takes an interest |\n", encoding="utf-8")
        out = self.ok("--seed", "1", "downtime", "Kira", "crime", "heist", "3d", "--no-clock")
        self.assertIn("(GM) complication: d6", "\n".join(out))
        self.setting("upkeep", "on")
        self.assertIn("can't pay", self.fails("downtime", "Kira", "research", "x", "10d", "--lifestyle", "aristocratic"))
        self.setting("downtime", "off")
        self.assertIn("downtime: off", self.fails("downtime", "Kira", "craft", "chain shirt", "1d"))


# ---------- (6) allied creatures, (10) mounts ----------

class Allies(Base):
    def test_verify_familiar_in_combat(self):
        out = self.assert_undoes("companion", "add", "Kira", "Ash", "srd:owl", "--note", "familiar")
        self.assertEqual(out, ["[companion Kira + Ash (srd:owl, own init)]"])
        self.ok("companion", "add", "Kira", "Ash", "srd:owl", "--note", "familiar")
        t = md.load(self.path("pcs/kira-thornwood.md")).table("Companions")
        self.assertEqual(t.rows[0], {"name": "Ash", "ref": "srd:owl", "hp": "1/1", "acts": "own init", "notes": "familiar"})
        out = self.ok("--seed", "2", "combat", "start", "--init", "Kael=10", "--init", "Kira=12", "--init", "Ash=7")
        ash = self.row("Ash")
        self.assertEqual((ash["side"], ash["conditions"], ash["init"], ash["ref"]), ("party", "ctrl Kira", "7", "srd:owl"))
        names = []
        for _ in range(4):
            out = self.ok("combat", "next")
            names.append(out[0])
        self.assertIn("[round 1 · up: Ash (Kira's)]", names)
        self.ok("dmg", "Ash", "1")
        self.ok("combat", "end")
        t = md.load(self.path("pcs/kira-thornwood.md")).table("Companions")
        self.assertEqual(t.rows[0]["hp"], "0/1")
        self.assertIn("Kira: Ash (srd:owl, 0/1, own init)", self.ok("companion", "list")[0])
        self.assert_undoes("companion", "drop", "Kira", "Ash")

    def test_with_me_follows_the_controller(self):
        self.ok("companion", "add", "Kael", "Brindle", "srd:mastiff", "--acts", "with")
        self.ok("--seed", "2", "combat", "start", "--init", "Kael=10", "--init", "Kira=12")
        t = md.load(self.path("state/current.md")).table("Combatants")
        order = [r["name"] for r in t.rows]
        self.assertEqual(order[order.index("Kael (PC)") + 1], "Brindle")
        self.assertEqual(self.row("Brindle")["init"], "10")

    def test_verify_mounted_fight(self):
        self.ok("companion", "add", "Kael", "Horse", "srd:riding-horse", "--acts", "mount")
        self.assert_undoes("mount", "Kael", "Horse")
        self.ok("mount", "Kael", "Horse")
        self.assertIn("mounted on Horse", self.front("pcs/kael-ashford.md")["conditions"])
        self.ok("--seed", "2", "combat", "start", "--init", "Kael=10", "--init", "Kira=12")
        horse = self.row("Horse")
        self.assertEqual(horse["init"], "10")
        self.assertIn("ridden by Kael", horse["conditions"])
        t = md.load(self.path("state/current.md")).table("Combatants")
        order = [r["name"] for r in t.rows]
        self.assertEqual(order[order.index("Kael (PC)") + 1], "Horse")
        out = self.ok("combat", "next")                            # Kael
        out = self.ok("combat", "next")                            # the horse, right after
        self.assertEqual(out[0], "[round 1 · up: Horse (Kael's)]")
        self.assertIn("[Horse (Kael's mount): only Dash, Disengage or Dodge; it moves with Kael on Kael's "
                      "initiative]", out)
        out = self.ok("cond", "Kael", "+prone")
        self.assertIn("DC 10 DEX save or fall off Horse", out[1])
        self.ok("cond", "Kael", "-prone")
        out = self.ok("cond", "Horse", "+prone")
        self.assertIn("Kael is dismounted", out[1])
        out = self.assert_undoes("dismount", "Kael")
        self.assertEqual(out, ["[dismount Kael from Horse]"])

    def test_mount_in_combat_moves_the_init(self):
        self.fight()
        self.ok("combat", "end")
        self.ok("--seed", "2", "combat", "start", "--init", "Kael=10", "--init", "Kira=12",
                "--add", "srd:warhorse @20,20,0")
        out = self.ok("mount", "Kira", "Warhorse")
        self.assertIn("controlled: acts on Kira's initiative", out[0])
        t = md.load(self.path("state/current.md")).table("Combatants")
        order = [r["name"] for r in t.rows]
        self.assertEqual(order[order.index("Kira (PC)") + 1], "Warhorse")
        self.assertEqual(self.row("Warhorse")["init"], "12")
        self.assertIn("ctrl Kira", self.row("Warhorse")["conditions"])

    def test_hire_wages_and_morale(self):
        out = self.assert_undoes("hire", "Bren", "--wage", "2 gp/day", "--by", "Kira", "--loyalty", "6")
        self.assertEqual(out, ["[hire Bren · 2 gp/day · by Kira · loyalty 6 · wages not charged (upkeep: off)]"])
        self.ok("hire", "Bren", "--wage", "2 gp/day", "--by", "Kira", "--loyalty", "6")
        f = self.front("npcs/bren.md")
        self.assertEqual((f["hired-by"], f["wage"], f["loyalty"]), ("Kira", "2 gp/day", 6))
        self.assertFalse(any("Wages" in x for x in self.ok("time", "+1d")))
        self.setting("upkeep", "on")
        out = self.ok("time", "+1d")
        self.assertIn("  Wages: Bren 2 gp paid by Kira coin Kira Thornwood 35→33 gp", out)
        self.ok("onstage", "Bren")
        self.ok("--seed", "2", "combat", "start", "--init", "Kael=10", "--init", "Kira=12")
        self.assertEqual(self.row("Bren")["side"], "party")
        self.ok("dmg", "Bren", "3")
        out = self.ok("combat", "next")
        self.assertIn("[Morale (half HP): Bren (hireling, loyalty 6) — WIS save DC 14 (gm.py save Bren wis 14); "
                      "fail → flees or refuses (gm.py cond Bren +fled)]", out)


# ---------- (7) weather ----------

class Weather(Base):
    def setUp(self):
        super().setUp()
        self.setting("weather", "on")
        self.setting("party-location", "village-square")          # outdoors

    def test_verify_wind_snuffs_a_torch(self):
        self.ok("light", "Kael", "torch")
        self.ok("light", "Kira", "lantern")
        out = self.assert_undoes("weather", "set", "light rain, strong wind, cool")
        self.assertIn("  Light out: Kael's torch (strong wind)", out)
        self.ok("weather", "set", "light rain, strong wind, cool")
        self.assertNotIn("lit", self.front("pcs/kael-ashford.md"))
        self.assertEqual(self.front("pcs/kira-thornwood.md")["lit"], ["lantern"])   # lanterns don't go out
        self.assertIn("[strong wind: an open flame won't stay lit out here]", self.ok("light", "Kael", "torch"))
        head = self.ok("brief")[0]
        self.assertIn("· light rain, strong wind, cool · tempo", head)

    def test_ranged_disadvantage_and_indoors(self):
        self.fight()
        self.ok("weather", "set", "clear, strong wind, mild")
        out = self.ok("atk", "Kira", "Veskar", "--with", "shortbow", "--d20", "12")
        self.assertIn("strong wind: ranged at disadvantage", out[0])
        out = self.ok("atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "12")
        self.assertNotIn("wind", out[0])
        self.setting("party-location", "crossroads-inn/common-room")   # under a roof
        out = self.ok("atk", "Kira", "Veskar", "--with", "shortbow", "--d20", "12")
        self.assertNotIn("wind", out[0])

    def test_dawn_roll_climate_and_extremes(self):
        _edit(self.path("locations/thornbury.md"), lambda t: t.replace("tags: [village]", "tags: [village]\nclimate: arctic", 1))
        out = self.ok("--seed", "1", "time", "to", "dawn")
        self.assertTrue(any(x.strip().startswith("[weather Day 2 dawn:") for x in out), out)
        self.assertIn("weather-now", self.front("state/current.md"))
        self.assertIn("(GM) weather roll Day 2: arctic · temperature d20", self.text("sessions/session-current.md"))
        self.ok("weather", "set", "clear, calm, bitter cold")
        self.assertEqual(self.front("state/current.md")["environment"], "extreme-cold")
        self.ok("weather", "set", "clear, calm, cool")
        self.assertNotIn("environment", self.front("state/current.md"))
        self.assertIn("· cool · tempo", self.ok("brief")[0])

    def test_off(self):
        self.setting("weather", "off")
        self.assertIn("weather: off", self.fails("weather", "roll"))
        self.assertFalse(any("weather" in x for x in self.ok("--seed", "1", "time", "to", "dawn")))
        self.assertIn("[weather: not set · off", self.ok("weather")[0])


# ---------- (8) encumbrance ----------

KIRA_45 = ("- Equipped: leather armor, shortsword, shortbow + quiver (20 arrows)\n"
           "- Pack: chain shirt (29 lb)\n- Coin: a handful of copper\n")


class Encumbrance(Base):
    def load45(self):
        def fn(t):
            start = t.index("## Inventory\n") + len("## Inventory\n")
            end = t.index("\n## Background")
            return t[:start] + KIRA_45 + t[end:]
        _edit(self.path("pcs/kira-thornwood.md"), fn)

    def test_verify_variant(self):
        self.load45()
        self.setting("encumbrance", "variant")
        self.assertIn("Kira 30/30 AC14 [enc]", self.party())
        card = "\n".join(self.ok("pc", "card", "Kira"))
        self.assertIn("Load: load 45/120 lb (variant) [enc]", card)
        self.assertIn("speed 20 (base 30)", card)
        self.fight()
        self.ok("combat", "next")
        self.ok("combat", "next")
        out = self.ok("combat", "next")                            # Kira is up
        self.assertIn("20 ft of movement", out[1])

    def test_heavy_disadvantage_and_basic(self):
        self.load45()
        _edit(self.path("pcs/kira-thornwood.md"), lambda t: t.replace("chain shirt (29 lb)", "chain shirt (69 lb)", 1))
        self.setting("encumbrance", "variant")
        self.assertIn("[heavy]", self.party())
        out = self.ok("save", "Kira", "dex", "12", "--d20", "15")
        self.assertIn("heavily encumbered (85 lb): disadvantage", out[0])
        out = self.ok("save", "Kira", "wis", "12", "--d20", "15")
        self.assertNotIn("encumbered", out[0])
        out = self.ok("check", "Kira", "stealth", "12", "--d20", "15")
        self.assertIn("heavily encumbered", out[0])
        self.setting("encumbrance", "basic")                       # 85 ≤ 120: nothing
        self.assertNotIn("[", self.party().split("Kira")[1].split("·")[0])
        _edit(self.path("pcs/kira-thornwood.md"), lambda t: t.replace("chain shirt (69 lb)", "chain shirt (169 lb)", 1))
        self.assertIn("[heavy]", self.party())
        self.assertIn("speed 5 (base 30)", "\n".join(self.ok("pc", "card", "Kira")))

    def test_travel_takes_longer(self):
        self.load45()
        set_front_raw(self, "pcs/kael-ashford.md", "scores", {"str": 20, "dex": 11, "con": 14, "int": 9, "wis": 16, "cha": 12})
        self.setting("encumbrance", "variant")
        out = self.ok("travel", "old-mill", "--plan")
        self.assertIn("  note: Kira is encumbered (speed 20 of 30 ft): the party keeps Kira's pace (×1.5 time)", out)

    def test_weights(self):
        from lib import encumbrance
        doc = md.load(self.path("pcs/kira-thornwood.md"))
        lb, unknown = encumbrance.load(doc)
        self.assertEqual((lb, unknown), (55.7, ["dark hooded cloak"]))
        self.assertEqual(encumbrance.entry_weight("2 flasks of oil")[0], 2.0)
        self.assertEqual(encumbrance.entry_weight("quiver (20 arrows)")[0], 2.0)
        self.assertEqual(encumbrance.entry_weight("rations (5 days)")[0], 10.0)


# ---------- (9) renown ----------

class Renown(Base):
    def setUp(self):
        super().setUp()
        set_front_raw(self, "npcs/mara-fennick.md", "faction", "red-ledger")
        set_front_raw(self, "npcs/mara-fennick.md", "attitude-to-party", "wary")

    def test_verify_wary_member_reads_neutral(self):
        self.assertIn("renown: off", self.fails("renown", "Red Ledger", "+3", "x"))
        self.setting("renown", "party")
        out = self.assert_undoes("renown", "Red Ledger", "+3", "returned the ledger")
        self.assertEqual(out, ["[renown Red Ledger 0→3 (party): returned the ledger · its members' attitude "
                               "shifts a step warmer]"])
        self.ok("renown", "Red Ledger", "+3", "returned the ledger", "--rank", "Friend of the Ledger")
        self.assertIn("| Red Ledger | 3      | Friend of the Ledger | party | returned the ledger |",
                      self.text("state/factions.md"))
        out = self.ok("check", "Kira", "persuasion", "--vs", "mara", "--ask", "major")
        self.assertIn("· wary→neutral (Red Ledger 3) · major: DC 25", out[0])
        self.assertIn("Mara (wary→neutral, Red Ledger 3)", self.ok("brief")[1])
        self.ok("renown", "Red Ledger", "-4", "burned the ledger")
        out = self.ok("check", "Kira", "persuasion", "--vs", "mara", "--ask", "minor")
        self.assertIn("wary→hostile (Red Ledger -1) · minor: DC 25", out[0])

    def test_per_pc(self):
        self.setting("renown", "per-pc")
        self.assertIn("--who", self.fails("renown", "Red Ledger", "+3", "x"))
        self.ok("renown", "Red Ledger", "+3", "a favour", "--who", "Kira")
        self.assertIn("wary→neutral (Red Ledger 3, Kira)", self.ok("check", "Kira", "persuasion", "--vs", "mara",
                                                                     "--ask", "major")[0])
        self.assertIn("· wary · major: DC 30", self.ok("check", "Kael", "persuasion", "--vs", "mara", "--ask", "major")[0])
        self.assertIn("Mara (wary · Kira: neutral)", self.ok("brief")[1])
        self.assertIn("Red Ledger 3 — Kira", self.ok("renown")[0])


# ---------- (11) lingering injuries ----------

class Injury(Base):
    def test_consider_line_and_table(self):
        self.ok("hp", "Kira", "-29")
        self.assertNotIn("injury", "\n".join(self.ok("hp", "Kira", "-1")))
        self.ok("hp", "Kira", "=30")
        self.setting("lingering-injuries", "on")
        out = self.ok("hp", "Kira", "-30")
        self.assertIn("[consider: gm.py injury Kira]", out)
        self.ok("hp", "Kira", "=30")
        self.assertIn("[consider: gm.py injury Kira]", self.ok("dmg", "Kira", "3", "--crit"))
        self.assertIn("no tables/injuries.md", self.fails("injury", "Kira"))
        (self.camp / "tables").mkdir(exist_ok=True)
        self.path("tables/injuries.md").write_text(INJURIES, encoding="utf-8")
        out = self.assert_undoes("injury", "Kira", "--roll", "4")
        self.assertEqual(out, ["[injury Kira: d20 4 → Lose an eye (disadvantage on sight Perception and ranged "
                               "attacks) · cure: regenerate]"])
        self.ok("injury", "Kira", "--roll", "4")
        self.assertIn("- **Injury: Lose an eye** (injury) — disadvantage on sight Perception and ranged attacks · "
                      "cure: regenerate", self.text("pcs/kira-thornwood.md"))

    def test_off(self):
        self.assertIn("lingering-injuries: off", self.fails("injury", "Kira"))


# ---------- guards ----------

SCRIPT = [
    ["--seed", "1", "combat", "start", "--init", "Kael=10", "--init", "Kira=12", "--add", "srd:bandit x2 @20,20,0"],
    ["--seed", "3", "atk", "Kira", "Bandits", "--with", "shortbow", "--d20", "14"],
    ["save", "Kael", "dex", "12", "--d20", "9"],
    ["check", "Kira", "perception", "12", "--d20", "11"],
    ["combat", "next"], ["combat", "next"], ["combat", "end"],
    ["check", "Kira", "persuasion", "--vs", "mara", "--ask", "minor", "14"],
    ["light", "Kael", "torch"],
    ["--seed", "2", "time", "to", "dawn"],
    ["--seed", "2", "travel", "old-mill"],
    ["rest", "short"],
    ["brief"],
]


class Guards(Base):
    OFF = {"inspiration": "off", "downtime": "off", "weather": "off", "encumbrance": "off", "renown": "off",
           "lingering-injuries": "off", "upkeep": "off"}

    def run_script(self):
        out = []
        for argv in SCRIPT:
            code, lines = run_main(argv)
            out.append((code, [x for x in lines if not x.startswith("[LINT]")]))
        return out, {k: v for k, v in self.snapshot().items() if k != "state/current.md"}

    def test_off_leaves_existing_commands_unchanged(self):
        """Every subsystem switched off by hand gives the same output and files as the
        defaults (the Phase 1–14 suite runs on the defaults)."""
        default_out, default_files = self.run_script()
        self.tearDown()
        self.setUp()
        for k, v in self.OFF.items():
            self.setting(k, v)
        off_out, off_files = self.run_script()
        self.assertEqual(default_out, off_out)
        self.assertEqual(default_files, off_files)

    def test_on_but_unused_changes_nothing(self):
        """weather on with no weather set, renown on with no standings, injuries on without
        a PC going down: the same commands still print the same."""
        default_out, _ = self.run_script()
        self.tearDown()
        self.setUp()
        for k, v in (("renown", "party"), ("lingering-injuries", "on"), ("encumbrance", "basic")):
            self.setting(k, v)
        out, _ = self.run_script()
        self.assertEqual(default_out, out)

    def test_no_shipped_non_srd_tables(self):
        tables = Path(__file__).resolve().parents[1] / "templates" / "tables"
        names = {p.name for p in tables.glob("*.md")}
        self.assertFalse({n for n in names if n.startswith(("injur", "downtime"))}, names)
        self.assertFalse((Path(__file__).resolve().parents[2] / "rules" / "injuries.md").exists())
