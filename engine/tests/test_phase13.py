"""Phase 13: concentration, dying, carried light, supplies, exhaustion, content
boundaries and the X-card (plan.md Phase 13 → Verify; docs/design/02 → Table mechanics
→ Phase 13; 06 → Table mechanics → Phase 13)."""
import io
import json
from unittest import mock

from fixture import CampaignCase, _edit, give_custom_veskar, run_main, set_front_raw
from lib import md

# Kira and Kael in a fight with Veskar (custom block, AC 15) at the inn
COMBAT = """## Combat — round 1 · up: Kira
Map: crossroads-inn / common-room (frame: site crossroads-inn; layout: locations/crossroads-inn.md)
Bounds: x 0–45 · y 0–35 · z 0–10 · origin (0,0,0) = inside the front door, SW corner · +x east · +y north · +z up · ft

### Combatants
| init | name      | glyph | side  | pos       | size | ref                 | HP    | AC | conditions | notes |
|------|-----------|-------|-------|-----------|------|---------------------|-------|----|------------|-------|
| 18   | Kira (PC) | R     | party | (10,0,0)  | M    | pcs/kira-thornwood  | 30/30 | 14 | —          |       |
| 15   | Veskar    | V     | foe   | (10,30,0) | M    | npcs/veskar         | 65/65 | 15 | —          |       |
| 12   | Kael (PC) | K     | party | (15,0,0)  | M    | pcs/kael-ashford    | 30/30 | 18 | —          |       |

### Moves log (this round; cleared at round end, summarized into the session log)"""


def hook(prompt):
    data = {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
    with mock.patch("sys.stdin", io.StringIO(json.dumps(data))):
        code, lines = run_main(["brief", "--hook"])
    assert code == 0, lines
    return lines


class Base(CampaignCase):
    def setUp(self):
        super().setUp()
        give_custom_veskar(self)
        # Both default to off; these tests exercise the tracking itself.
        set_front_raw(self, "state/current.md", "track-light", "on")
        set_front_raw(self, "state/current.md", "supplies", "loose")

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

    def brief(self):
        return "\n".join(self.ok("brief"))

    def party(self):
        return next(line for line in self.ok("brief") if line.startswith("Party:"))

    def fight(self):
        _edit(self.path("state/current.md"), lambda t: t.replace("## Combat\n(not in combat)", COMBAT, 1))

    def row(self, name):
        t = md.load(self.path("state/current.md")).table("Combatants")
        return next(r for r in t.rows if r["name"].startswith(name))

    def snapshot(self):
        """Every campaign file; the session log without `undo` lines (undo logs itself)."""
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


class Defaults(CampaignCase):
    def test_tracking_off_by_default(self):
        from lib import campaign
        self.assertEqual(campaign.SETTINGS["track-light"], "off")
        self.assertEqual(campaign.SETTINGS["supplies"], "off")
        self.assertEqual(campaign.SETTINGS["ammo"], "special")


class Concentration(Base):
    def test_verify_damage_save_and_strip(self):
        out = self.ok("conc", "Kael", "bless", "--on", "Kael,Kira", "1m")
        self.assertEqual(out, ["[conc Kael bless · 1m · on Kael, Kira]"])
        self.assertEqual(self.front("pcs/kael-ashford.md")["concentration"],
                         {"spell": "bless", "until": "Day 1 18:31", "on": ["Kael", "Kira"]})
        self.assertEqual(self.front("pcs/kira-thornwood.md")["conditions"], ["bless 1m"])
        self.assertIn("[conc bless 1m]", self.party())
        out = self.ok("dmg", "Kael", "14")
        self.assertIn("[concentration: CON save DC 10 to keep bless (gm.py save Kael con 10)]", out)
        out = self.ok("save", "Kael", "con", "10", "--d20", "3")     # 3+2 = 5: FAIL
        self.assertIn("[conc Kael ends bless (failed save) · Kael, Kira lose bless]", out)
        self.assertEqual(self.front("pcs/kira-thornwood.md")["conditions"], [])
        self.assertNotIn("concentration", self.front("pcs/kael-ashford.md"))

    def test_saved_keeps_it_and_unmatched_save_does_nothing(self):
        self.ok("conc", "Kael", "bless", "--on", "Kira", "1m")
        self.ok("dmg", "Kael", "24")                                # DC 12
        out = self.ok("save", "Kael", "con", "11", "--d20", "1")   # not the DC owed (12)
        self.assertEqual(len(out), 1)
        out = self.ok("save", "Kael", "con", "12", "--d20", "15")
        self.assertIn("[concentration: Kael keeps bless]", out)
        self.assertNotIn("save", self.front("pcs/kael-ashford.md")["concentration"])

    def test_auto_ends(self):
        self.ok("conc", "Kael", "bless", "--on", "Kira", "1m")
        out = self.ok("conc", "Kael", "shield-of-faith", "--on", "Kira", "10m")   # a new one ends it
        self.assertEqual(out[0], "[conc Kael ends bless (a new concentration spell) · Kira lose bless]")
        self.assertEqual(self.front("pcs/kira-thornwood.md")["conditions"], ["shield-of-faith 10m"])
        out = self.ok("cond", "Kael", "+stunned")
        self.assertIn("[conc Kael ends shield-of-faith (stunned) · Kira lose shield-of-faith]", out)
        self.ok("cond", "Kael", "-stunned")
        self.ok("conc", "Kael", "bless", "--on", "Kira", "1m")
        out = self.ok("hp", "Kael", "=0")
        self.assertTrue(any("ends bless (dropped to 0 HP)" in x for x in out), out)

    def test_expires_on_the_clock(self):
        self.ok("conc", "Kael", "shield-of-faith", "--on", "Kira", "10m")
        out = self.ok("time", "+10m")
        self.assertIn("  Conditions expired: Kira shield-of-faith", out)
        self.assertIn("  Concentration: conc Kael ends shield-of-faith (duration ended)", out)
        self.assertNotIn("concentration", self.front("pcs/kael-ashford.md"))

    def test_in_combat_rounds(self):
        self.fight()
        self.ok("conc", "Kael", "bless", "--on", "Kael,Kira", "1m")
        self.assertEqual(self.row("Kael")["conditions"], "bless 10r, conc bless 10r")
        self.assertEqual(self.row("Kira")["conditions"], "bless 10r")
        self.assertIn("Kael 30/30 AC18 [bless 10r] [conc bless 10r]", self.party())
        for _ in range(3 * 10):                    # ten rounds of three
            out = self.ok("combat", "next")
            if any("ends bless (duration ended)" in x for x in out):
                break
        else:
            self.fail("bless never ran out")
        self.assertNotIn("concentration", self.front("pcs/kael-ashford.md"))
        self.assertEqual(self.row("Kira")["conditions"], "—")

    def test_srd_caster_without_file(self):
        self.fight()
        _edit(self.path("state/current.md"), lambda s: s.replace(
            "| 15   | Veskar    | V     | foe   | (10,30,0) | M    | npcs/veskar         | 65/65 | 15 | —          |       |",
            "| 15   | Thug      | T     | foe   | (10,30,0) | M    | srd:thug            | 32/32 | 11 | —          |       |"))
        self.ok("conc", "Thug", "hold-person", "--on", "Kira", "1m")
        self.assertEqual(self.row("Thug")["conditions"], "conc hold-person 10r")
        self.assertIn("conc→Kira", self.row("Thug")["notes"])
        out = self.ok("dmg", "Thug", "8")
        self.assertIn("[concentration: CON save DC 10 to keep hold-person (gm.py save Thug con 10)]", out)
        out = self.ok("save", "Thug", "con", "10", "--seed", "3")
        if "FAIL" in out[0]:
            self.assertIn("lose hold-person", out[-1])
            self.assertEqual(self.row("Kira")["conditions"], "—")
            self.assertNotIn("conc", self.row("Thug")["notes"])
        else:
            self.assertEqual(out[-1], "[concentration: Thug keeps hold-person]")
            self.assertNotIn("conc-save", self.row("Thug")["notes"])


class Dying(Base):
    def test_verify_death_saves(self):
        out = self.ok("hp", "Kira", "=0")
        self.assertIn("[Kira is dying: unconscious, death saves ✓0 ✗0]", out)
        self.assertEqual(self.front("pcs/kira-thornwood.md")["death-saves"], {"ok": 0, "fail": 0})
        self.assertIn("Kira 0/30 AC14 DYING ✓0 ✗0 [unconscious]", self.party())
        out = self.ok("deathsave", "Kira", "1")
        self.assertEqual(out, ["[deathsave Kira: d20 1 — two failures · dying ✓0 ✗2]"])
        out = self.ok("deathsave", "Kira", "20")
        self.assertEqual(out[0], "[deathsave Kira: d20 20 — natural 20: back up with 1 HP]")
        self.assertIn("[Kira is conscious again (healed)]", out)
        f = self.front("pcs/kira-thornwood.md")
        self.assertEqual(f["hp"]["current"], 1)
        self.assertNotIn("death-saves", f)
        self.assertEqual(f["conditions"], [])

    def test_massive_damage_at_zero(self):
        self.ok("hp", "Kira", "=0")
        out = self.ok("dmg", "Kira", "30")
        self.assertIn("[Kira is dead (30 damage at 0 HP ≥ HP max 30)]", out)
        f = self.front("pcs/kira-thornwood.md")
        self.assertEqual(f["conditions"], ["dead"])
        self.assertNotIn("death-saves", f)

    def test_failures_crits_and_three(self):
        self.ok("hp", "Kira", "=0")
        self.assertIn("dying ✓0 ✗2", self.ok("dmg", "Kira", "3", "--crit")[-1])
        out = self.ok("dmg", "Kira", "3")
        self.assertIn("[Kira is dead (three death save failures)]", out)

    def test_player_rolls_unless_secret(self):
        self.ok("hp", "Kira", "=0")
        self.assertIn("ask for a d20 (gm.py deathsave Kira <d20>)", self.fails("deathsave", "Kira"))
        set_front_raw(self, "state/current.md", "death-save-rolls", "secret")
        out = self.ok("deathsave", "Kira", "--seed", "1")
        self.assertTrue(out[0].startswith("[SECRET deathsave Kira: d20 "), out)
        self.assertIn("  - (GM) deathsave Kira", self.text("sessions/session-current.md"))

    def test_three_successes_stable_then_wakes(self):
        self.ok("hp", "Kira", "=0")
        self.ok("deathsave", "Kira", "12")
        self.ok("deathsave", "Kira", "15")
        out = self.ok("deathsave", "Kira", "10", "--seed", "2")
        self.assertRegex(out[-1], r"^\[Kira is stable \(wakes with 1 HP in (\d)h, 1d4: \1\)\]$")
        hours = int(out[-1].split("in ")[1][0])
        f = self.front("pcs/kira-thornwood.md")
        self.assertIn(f"stable {hours}h", f["conditions"])
        self.assertNotIn("death-saves", f)
        out = self.ok("time", f"+{hours}h")
        self.assertIn("Kira stable (wakes with 1 HP)", "\n".join(out))
        f = self.front("pcs/kira-thornwood.md")
        self.assertEqual(f["hp"]["current"], 1)
        self.assertEqual(f["conditions"], [])

    def test_stabilize(self):
        self.ok("hp", "Kira", "=0")
        out = self.ok("stabilize", "Kira", "--by", "Kael", "4")     # 4+5 = 9: fails DC 10
        self.assertEqual(len(out), 1)
        self.assertIn("FAIL", out[0])
        out = self.ok("stabilize", "Kira", "--kit", "--seed", "1")
        self.assertIn("[res Kael Ashford healer's kit uses 10→9/10]", out)
        self.assertTrue(out[-1].startswith("[Kira is stable"))
        self.assertIn("Kira Thornwood is not dying", self.fails("stabilize", "Kira", "--kit"))

    def test_rule_off_and_dc(self):
        self.ok("rule", "add", "no death saves", "--scope", "campaign", "--key", "death-saves=off")
        out = self.ok("hp", "Kira", "=0")
        self.assertIn("1 HP", out[0])
        self.assertNotIn("death-saves", self.front("pcs/kira-thornwood.md"))

    def test_combat_next_prompts(self):
        self.fight()
        self.ok("hp", "Kira", "=0")
        self.assertEqual(self.row("Kira")["conditions"], "dying ✓0 ✗0, unconscious")
        self.ok("combat", "next")
        self.ok("combat", "next")
        out = self.ok("combat", "next")          # round 2: Kira is up
        self.assertIn("[Kira is dying (✓0 ✗0): death save — ask for a d20 (gm.py deathsave Kira <d20>)]", out)
        self.ok("deathsave", "Kira", "5")
        self.assertEqual(self.row("Kira")["conditions"], "dying ✓0 ✗1, unconscious")
        out = self.ok("combat", "end")
        f = self.front("pcs/kira-thornwood.md")
        self.assertEqual(f["conditions"], ["unconscious"])       # mirrors aren't written back
        self.assertEqual(f["death-saves"], {"ok": 0, "fail": 1})

    def test_heartbeat_carries_dying(self):
        set_front_raw(self, "state/current.md", "in-session", True)
        set_front_raw(self, "state/current.md", "wacky-juice", "off")
        self.ok("hp", "Kira", "=0")
        hook("look")
        self.assertIn("Kira 0/30 DYING ✓0 ✗0 unconscious", hook("look")[0])


class Light(Base):
    def setUp(self):
        super().setUp()
        self.ok("item", "Kael", "+", "torches (4)")
        set_front_raw(self, "state/current.md", "light", "dark")

    def test_verify_torch(self):
        self.assertIn("Kael blind without a light", self.brief())
        out = self.ok("light", "Kael", "torch")
        self.assertEqual(out, ["[light Kael torch · bright 20 ft, dim 40 ft · 1h · torches 4→3]"])
        self.assertIn("torches (3)", self.text("pcs/kael-ashford.md"))
        self.assertEqual(self.front("pcs/kael-ashford.md")["lit"], ["torch 60m"])
        self.assertIn("Sight (dark · Kael's torch 60m: bright 20 ft, dim 40 ft): Kael sees normally · "
                      "Kira sees normally", self.brief())
        self.assertEqual(self.front("state/current.md")["light"], "dark")   # ambient untouched
        out = self.ok("time", "+50m")
        self.assertIn("  Light low: Kael's torch (10m left)", out)
        out = self.ok("time", "+11m")
        self.assertIn("  Light out: Kael's torch (Day 1 19:30)", out)
        self.assertNotIn("lit", self.front("pcs/kael-ashford.md"))
        self.assertIn("Kael blind without a light", self.brief())

    def test_sources_and_out(self):
        out = self.ok("light", "Kira", "lantern")
        self.assertIn("oil 2→1 flasks", out[0])
        self.assertIn("1 flask of oil", self.text("pcs/kira-thornwood.md"))
        self.ok("light", "Kael", "cantrip")
        self.assertIn("doesn't have the daylight spell", self.fails("light", "Kael", "daylight"))
        self.assertIn("Kira has no candle", self.fails("light", "Kira", "candle"))
        self.assertEqual(self.ok("light", "Kael", "out"), ["[light Kael out: light 60m]"])
        self.assertIn("Kira's lantern 360m: bright 30 ft, dim 60 ft", self.brief())

    def test_radius_in_combat(self):
        self.fight()
        self.ok("item", "Kira", "+", "torches (2)")
        self.ok("light", "Kira", "torch")
        self.assertIn("Kael sees normally · Kira sees normally", self.brief())     # 5 ft apart
        _edit(self.path("state/current.md"), lambda s: s.replace("| (15,0,0)  |", "| (45,30,0) |"))
        self.assertIn("Kael dim (sight Perception at disadv.)", self.brief())       # 35 ft: the dim ring
        _edit(self.path("state/current.md"), lambda s: s.replace("| (10,0,0)  |", "| (0,0,0)   |"))
        self.assertIn("Kael blind without a light", self.brief())                   # 45 ft: out of it

    def test_track_light_off(self):
        set_front_raw(self, "state/current.md", "track-light", "off")
        before = self.text("pcs/kael-ashford.md").split("## Inventory")[1]
        self.assertEqual(self.ok("light", "Kael", "torch"),
                         ["[light Kael torch · bright 20 ft, dim 40 ft · not counted]"])
        self.assertEqual(self.text("pcs/kael-ashford.md").split("## Inventory")[1], before)
        self.assertEqual(self.front("pcs/kael-ashford.md")["lit"], ["torch"])
        out = self.ok("time", "+3h")
        self.assertFalse(any("Light" in x for x in out))


class Supplies(Base):
    def setUp(self):
        super().setUp()
        _edit(self.path("pcs/kira-thornwood.md"), lambda s: s.replace(
            "| 80/320 | 20 arrows                              |",
            "| 80/320 | ammo arrows                            |"))
        self.fight()

    def shoot(self, n):
        for _ in range(n):
            self.ok("atk", "Kira", "Veskar", "--with", "shortbow", "--d20", "2")

    def test_verify_all(self):
        set_front_raw(self, "state/current.md", "ammo", "all")
        self.shoot(3)
        self.assertIn("quiver (17 arrows)", self.text("pcs/kira-thornwood.md"))
        self.assertIn("Ammo spent: Kira arrows 3", self.text("state/current.md"))
        out = self.ok("combat", "end")
        self.assertIn("[Ammo: Kira spent 3 arrows; after a search, 1 can be recovered "
                      "(gm.py item Kira +1 arrows)]", out)
        self.ok("item", "Kira", "+1", "arrows")
        self.assertIn("quiver (18 arrows)", self.text("pcs/kira-thornwood.md"))

    def test_tracked_refuses_at_zero(self):
        set_front_raw(self, "state/current.md", "ammo", "all")
        self.ok("item", "Kira", "-20", "arrows")
        self.assertIn("quiver (0 arrows)", self.text("pcs/kira-thornwood.md"))
        self.assertIn("Kira has no arrows", self.fails("atk", "Kira", "Veskar", "--with", "shortbow", "--d20", "2"))

    def test_default_tracks_only_special_ammo(self):
        self.shoot(2)
        self.assertIn("quiver (20 arrows)", self.text("pcs/kira-thornwood.md"))
        self.assertNotIn("Ammo spent", self.text("state/current.md"))
        _edit(self.path("pcs/kira-thornwood.md"), lambda s: s.replace(
            "| ammo arrows ", "| special ammo arrows "))
        self.shoot(2)
        self.assertIn("quiver (18 arrows)", self.text("pcs/kira-thornwood.md"))
        self.assertIn("Ammo spent: Kira arrows 2", self.text("state/current.md"))

    def test_off_changes_nothing(self):
        set_front_raw(self, "state/current.md", "supplies", "off")
        set_front_raw(self, "state/current.md", "ammo", "off")
        inv = self.text("pcs/kira-thornwood.md").split("## Inventory")[1]
        self.shoot(2)
        self.assertNotIn("Ammo", self.text("state/current.md"))
        self.assertFalse(any("Ammo" in x for x in self.ok("combat", "end")))
        self.assertEqual(self.ok("eat"), ["[eat: supplies: off — nothing is counted]"])
        self.ok("rest", "long")
        self.assertEqual(self.text("pcs/kira-thornwood.md").split("## Inventory")[1], inv)


class Food(Base):
    def test_eat_and_buy(self):
        out = self.ok("eat", "Kira")
        self.assertEqual(out, ["[eat Kira · rations 5→4 · waterskin full→half · fed Day 1]"])
        self.assertIn("4 days rations, waterskin (half)", self.text("pcs/kira-thornwood.md"))
        self.ok("eat", "Kira")
        out = self.ok("eat", "Kira")
        self.assertIn("no water", out[0])
        self.assertTrue(out[1].startswith("[Kira has no water today: DC 15 CON save"))
        out = self.ok("eat", "Kael", "--bought", "3 gp")
        self.assertIn("[coin Kael Ashford 15→12 gp]", out)
        self.assertEqual(self.front("pcs/kael-ashford.md")["fed"], "Day 1")

    def test_verify_hunger(self):
        set_front_raw(self, "pcs/kira-thornwood.md", "fed", "Day 1")   # CON 14: +2 → 5 days
        out = self.ok("time", "+6d")                                    # Day 7 18:30
        self.assertIn("  Supplies: Kira last ate Day 1 (5 days; exhaustion after 5)", out)
        self.assertNotIn("exhaustion", self.front("pcs/kira-thornwood.md"))
        out = self.ok("clock", "advance", "to", "dawn")                  # Day 8: 6 days
        self.assertIn("  Supplies: Kira last ate Day 1 (6 days; exhaustion after 5) · +1 exhaustion (hunger)", out)
        self.assertEqual(self.front("pcs/kira-thornwood.md")["exhaustion"], 1)

    def test_rest_long_eats_and_recovers(self):
        self.ok("exhaust", "Kira", "+2")
        out = self.ok("rest", "long", "Kira")
        self.assertTrue(any(x.startswith("[eat Kira · rations 5→4") for x in out), out)
        self.assertTrue(any(x.startswith("[exhaust Kira 2→1 (long rest)") for x in out), out)

    def test_services_site_skips_under_loose(self):
        _edit(self.path("locations/crossroads-inn.md"), lambda s: s.replace("tags: [social, safe]",
                                                                              "tags: [social, safe, services]"))
        inv = self.text("pcs/kira-thornwood.md").split("## Inventory")[1]
        self.ok("rest", "long")
        self.assertEqual(self.text("pcs/kira-thornwood.md").split("## Inventory")[1], inv)


class Exhaustion(Base):
    def test_verify_disadvantage(self):
        out = self.ok("exhaust", "Kira", "=3")
        self.assertEqual(out, ["[exhaust Kira 0→3 · disadvantage on ability checks; speed halved; "
                               "disadvantage on attacks and saves]"])
        self.assertIn("Kira 30/30 AC14 [exh 3]", self.party())
        out = self.ok("check", "Kira", "stealth", "12", "--d20", "15")
        self.assertIn("(exhaustion 3: disadvantage", out[0])
        set_front_raw(self, "state/current.md", "dice-mode", "gm-rolls-all")
        out = self.ok("check", "Kira", "stealth", "12", "--seed", "4")
        self.assertRegex(out[0], r"d20 \(\d+, \d+\)→\d+\+7=")
        out = self.ok("atk", "Kira", "Veskar", "--with", "shortsword", "--seed", "4")
        self.assertRegex(out[0], r"d20 \(\d+, \d+\)→")
        self.assertIn("exhaustion 3: disadvantage", out[0])
        out = self.ok("check", "Kira", "stealth", "12", "adv", "--seed", "4")   # adv and dis cancel
        self.assertRegex(out[0], r"d20 \d+\+7=")

    def test_speed_hp_max_and_death(self):
        self.fight()
        self.ok("exhaust", "Kira", "=2")
        self.assertEqual(self.row("Kira")["conditions"], "exh 2")
        self.ok("combat", "next")
        self.ok("combat", "next")
        out = self.ok("combat", "next")
        self.assertIn("15 ft of movement", "\n".join(out))
        out = self.ok("exhaust", "Kira", "+2")
        self.assertIn("[hp Kira 30→15/15 (exhaustion 4: HP max halved)]", out)
        out = self.ok("hp", "Kira", "+10")
        self.assertEqual(out[0], "[hp Kira 15→15/30 (exhaustion 4: HP max 15)]")
        out = self.ok("exhaust", "Kira", "+2", "a curse")
        self.assertIn("[Kira is dead (exhaustion 6)]", out)

    def test_2024_rules(self):
        set_front_raw(self, "state/current.md", "exhaustion", 2024)
        self.ok("exhaust", "Kira", "+2")
        out = self.ok("check", "Kira", "stealth", "12", "--d20", "10")
        self.assertIn("d20 10+3=13", out[0])              # +7 − 4
        self.assertIn("exhaustion 2: −4", out[0])


class Boundaries(Base):
    def test_brief_and_command(self):
        self.assertIn("Table: boundaries not asked yet", self.brief())
        out = self.ok("campaign", "boundaries", "--line", "harm to children", "--veil", "torture")
        self.assertEqual(out, ["[boundaries · lines: harm to children · veils: torture]"])
        self.assertIn("Table: lines — harm to children; veils — torture", self.brief())
        log = self.text("sessions/session-current.md")
        self.assertIn("(GM) boundaries: 1 line(s), 1 veil(s)", log)
        self.assertNotIn("torture", log)
        self.ok("campaign", "boundaries", "--drop", "torture", "--drop", "harm to children")
        self.assertNotIn("Table:", self.brief())          # asked, none: no line
        self.ok("campaign", "boundaries", "--none")
        self.assertEqual(self.front("state/current.md")["lines"], [])

    def test_campaign_md_wins(self):
        self.path("campaign.md").write_text("---\nname: Test\n---\n# Test\n", encoding="utf-8")
        self.ok("campaign", "boundaries", "--veil", "torture")
        self.assertEqual(self.front("campaign.md")["veils"], ["torture"])
        self.assertNotIn("veils", self.front("state/current.md"))

    def test_x_card(self):
        set_front_raw(self, "state/current.md", "in-session", True)
        set_front_raw(self, "state/current.md", "wacky-juice", "off")
        self.ok("campaign", "boundaries", "--veil", "torture")
        hook("look")
        out = hook("!x")
        self.assertEqual(out[0], "X-card: the last thing described is out — rewind it in one line and "
                                 "steer away; don't ask why")
        self.assertTrue(out[1].startswith("[GM BRIEF] unchanged"))   # boundaries ride only the full brief
        self.assertNotIn("torture", "\n".join(out))
        log = self.text("sessions/session-current.md").splitlines()
        self.assertIn("  - x-card", log)


class Undo(Base):
    def test_every_command_undoes(self):
        self.ok("item", "Kael", "+", "torches (4)")
        self.assert_undoes("conc", "Kael", "bless", "--on", "Kael,Kira", "1m")
        self.ok("conc", "Kael", "bless", "--on", "Kira", "1m")
        self.assert_undoes("dmg", "Kael", "4")
        self.assert_undoes("conc", "Kael", "end", "lost focus")
        self.assert_undoes("hp", "Kira", "=0")
        self.ok("hp", "Kira", "=0")
        self.assert_undoes("deathsave", "Kira", "4")
        self.assert_undoes("stabilize", "Kira", "--kit", "--seed", "1")
        self.assert_undoes("light", "Kael", "torch")
        self.assert_undoes("eat", "Kael")
        self.assert_undoes("exhaust", "Kael", "+1", "forced march")
        self.assert_undoes("campaign", "boundaries", "--veil", "torture")
        self.ok("light", "Kael", "torch")
        self.assert_undoes("time", "+61m")
        _edit(self.path("pcs/kira-thornwood.md"), lambda s: s.replace(
            "| 80/320 | 20 arrows                              |",
            "| 80/320 | ammo arrows                            |"))
        set_front_raw(self, "state/current.md", "ammo", "all")
        self.fight()
        self.assert_undoes("atk", "Kira", "Veskar", "--with", "shortbow", "--d20", "2")


class Format(Base):
    def test_list_inside_a_map_and_del_front(self):
        v = md.parse_value('{spell: bless, until: "Day 1 18:31", on: [Kael, Kira], save: 12}')
        self.assertEqual(v, {"spell": "bless", "until": "Day 1 18:31", "on": ["Kael", "Kira"], "save": 12})
        self.assertEqual(md.fmt_value(v), "{spell: bless, until: Day 1 18:31, on: [Kael, Kira], save: 12}")
        self.assertEqual(md.parse_value(md.fmt_value(v)), v)
        doc = md.load(self.path("pcs/kira-thornwood.md"))
        doc.set_front("fed", "Day 1")
        doc.del_front("speed")
        doc.set_front("exhaustion", 2)
        doc.save()
        f = self.front("pcs/kira-thornwood.md")
        self.assertNotIn("speed", f)
        self.assertEqual((f["fed"], f["exhaustion"], f["conditions"]), ("Day 1", 2, []))

    def test_lf_and_crlf_files_keep_their_newlines(self):
        for rel in ("pcs/kael-ashford.md", "pcs/kira-thornwood.md"):
            self.assertIn(b"\r\n", self.read_bytes(rel))
        lf = self.path("pcs/kira-thornwood.md")
        lf.write_bytes(lf.read_bytes().replace(b"\r\n", b"\n"))
        self.ok("conc", "Kael", "bless", "--on", "Kira", "1m")
        self.ok("hp", "Kira", "=0")
        self.assertNotIn(b"\r\n", self.read_bytes("pcs/kira-thornwood.md"))
        self.assertIn(b"\r\n", self.read_bytes("pcs/kael-ashford.md"))
        self.assertEqual(self.front("pcs/kira-thornwood.md")["death-saves"], {"ok": 0, "fail": 0})
