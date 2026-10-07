"""Mutations, turn-block deltas and undo (docs/design/06 L137-168, L219-222; plan.md
Phase 2 item 5 and Verify)."""
import unittest

from fixture import CampaignCase, give_custom_veskar, start_combat
from lib import md
from fixture import run_main


class Base(CampaignCase):
    def setUp(self):
        super().setUp()
        give_custom_veskar(self)

    def log(self):
        return self.path("sessions/session-current.md").read_text(encoding="utf-8").splitlines()

    def front(self, rel):
        return md.load(self.path(rel)).front

    def ok(self, *argv):
        code, lines = run_main(list(argv))
        self.assertEqual(code, 0, lines)
        return lines

    def fails(self, *argv):
        code, lines = run_main(list(argv))
        self.assertEqual(code, 1, lines)
        return lines[-1]


class VerifyScenario(Base):
    def test_do_atk_dmg_log_deltas_and_undo(self):
        # one delta per command: the atk line carries its own HP change (review M6),
        # so `atk; dmg; log` writes two deltas, not three
        pc_before = self.read_bytes("pcs/kael-ashford.md")
        lines = self.ok("do", "atk Veskar Kael --seed 1; dmg Kael 3; log x")
        self.assertEqual(lines, [
            "[Veskar → Kael Ashford: d20 5+14=19 vs AC 18 — HIT · 8 slashing · Kael Ashford 30→22/30]",
            "[dmg Kael Ashford 3 · Kael Ashford 22→19/30]",
            "[turn 1 logged]",
        ])
        log = self.log()
        i = log.index("[turn 1] x")
        self.assertEqual(log[i + 1:], [
            "  - atk Veskar → Kael Ashford: d20 5+14=19 vs AC 18 — HIT · 8 slashing · Kael Ashford 30→22/30 "
            "[1d6+3: 5+3 = 8]",
            "  - dmg Kael Ashford 3 · Kael Ashford 22→19/30",
        ])
        self.assertNotEqual(self.read_bytes("pcs/kael-ashford.md"), pc_before)
        lines = self.ok("undo")
        self.assertEqual(lines[0], "[undo turn 1 step 1 · gm.py do 'atk Veskar Kael; dmg Kael 3; log x' · "
                                   "restored pcs/kael-ashford.md, sessions/session-current.md]")
        self.assertEqual(self.read_bytes("pcs/kael-ashford.md"), pc_before)
        self.assertEqual(self.log()[-1], "  - undo turn 1 step 1")

    def test_journal_line_drops_global_flags(self):
        self.ok("--campaign", str(self.camp), "hp", "Kael", "-1", "--json")
        lines = self.ok("undo", "--campaign", str(self.camp))
        self.assertEqual(lines[0], "[undo turn 1 step 1 · gm.py hp Kael -1 · restored pcs/kael-ashford.md, "
                                   "sessions/session-current.md]")

    def test_undo_with_nothing(self):
        self.assertIn("nothing to undo", self.fails("undo"))


class HitPoints(Base):
    def test_hp_clamp_and_set(self):
        self.assertEqual(self.ok("hp", "Kael", "-6"), ["[hp Kael Ashford 30→24/30]"])
        self.assertEqual(self.ok("hp", "Kael", "+40"), ["[hp Kael Ashford 24→30/30]"])
        self.assertEqual(self.ok("hp", "Kael", "=11"), ["[hp Kael Ashford 30→11/30]"])
        # Phase 13: 88 damage past 0 is at least the HP maximum, so it kills (massive damage)
        self.assertEqual(self.ok("hp", "Kael", "-99"), ["[hp Kael Ashford 11→0/30]",
                                                        "[Kael is dead (massive damage: 88 past 0 ≥ HP max 30)]"])
        self.assertEqual(self.front("pcs/kael-ashford.md")["hp"], {"current": 0, "max": 30})
        text = self.path("pcs/kael-ashford.md").read_text(encoding="utf-8")
        self.assertIn("hp: {current: 0, max: 30}   # max HP per level (house rule)", text)

    def test_temp_hp(self):
        self.assertEqual(self.ok("hp", "Kael", "+temp", "5"), ["[hp Kael Ashford 30→30/30 · temp 0→5]"])
        self.assertEqual(self.front("pcs/kael-ashford.md")["hp"], {"current": 30, "max": 30, "temp": 5})
        self.assertEqual(self.ok("hp", "Kael", "-7"),
                         ["[hp Kael Ashford 30→28/30 · temp 5→0 (temp absorbed 5)]"])
        self.assertEqual(self.front("pcs/kael-ashford.md")["hp"], {"current": 28, "max": 30})

    def test_dmg_resistance_note(self):
        self.assertEqual(self.ok("dmg", "Veskar", "8", "poison"),
                         ["[dmg Veskar 8 poison → 4 (resistant) · Veskar 65→61/65]"])
        self.assertEqual(self.ok("dmg", "Veskar", "8", "fire"), ["[dmg Veskar 8 fire · Veskar 61→53/65]"])

    def test_negative_damage_refused(self):
        self.assertIn("never negative", self.fails("dmg", "Kael", "-5"))
        self.assertEqual(self.front("pcs/kael-ashford.md")["hp"], {"current": 30, "max": 30})
        from lib import resolve
        with self.assertRaises(resolve.ResolveError):
            resolve.apply_hp(10, 30, 0, "-", -5)

    def test_zero_is_a_noop(self):
        before = (self.read_bytes("pcs/kael-ashford.md"), self.read_bytes("sessions/session-current.md"))
        self.assertEqual(self.ok("hp", "Kael", "-0"), ["[hp Kael Ashford no change]"])
        self.assertEqual(self.ok("hp", "Kael", "+temp", "0"), ["[hp Kael Ashford no change]"])
        self.assertEqual((self.read_bytes("pcs/kael-ashford.md"), self.read_bytes("sessions/session-current.md")),
                         before)

    def test_damage_at_zero_notes_death_save(self):
        # Phase 13: the note became the write (death-saves: in the PC file)
        self.ok("hp", "Kael", "=0")
        self.assertEqual(self.ok("dmg", "Kael", "4"),
                         ["[dmg Kael Ashford 4 · Kael Ashford 0→0/30]",
                          "[Kael: damage at 0 HP — a death save failure · dying ✓0 ✗1]"])

    def test_srd_npc_without_hp_line(self):
        # Mara is an SRD commoner (4 HP) with no hp: line; the first change writes one
        code, lines = run_main(["hp", "Mara", "-3"])
        self.assertEqual(code, 0, lines)
        from lib import md
        self.assertEqual(md.load(self.path("npcs/mara-fennick.md")).front["hp"], {"current": 1, "max": 4})

    def test_bad_hp_args(self):
        self.assertIn("want -N", self.fails("hp", "Kael", "six"))


class GroupSplit(Base):
    def setUp(self):
        super().setUp()
        start_combat(self)

    def names_hp(self):
        t = md.load(self.path("state/current.md")).table("Combatants")
        return [(r["name"], r["hp"], r["size"]) for r in t.rows]

    def test_split(self):
        self.assertEqual(self.ok("hp", "Thugs", "-5"), ["[hp Thug 1 7→2/11 (split from Thugs ×3)]"])
        # the group keeps its footprint; a split member is one creature, not a swarm
        self.assertEqual(self.names_hp()[2:], [("Thugs ×2", "7/11 ea", "group r5"), ("Thug 1", "2/11", "M")])
        self.assertEqual(self.ok("hp", "Thugs", "-3"), ["[hp Thug 2 7→4/11 (split from Thugs ×2)]"])
        # the remaining group row stays first, split members follow in number order;
        # the last member stops being a group, so it loses the footprint too
        self.assertEqual([(n, s) for n, _, s in self.names_hp()[2:]], [("Thug 3", "M"), ("Thug 1", "M"), ("Thug 2", "M")])
        self.assertEqual(self.ok("hp", "Thug 1", "-2"), ["[hp Thug 1 2→0/11]"])

    def test_full_name_hits_the_combat_row(self):
        kael_file = self.read_bytes("pcs/kael-ashford.md")
        self.assertEqual(self.ok("hp", "Kael Ashford", "-1"), ["[hp Kael 9→8/11]"])
        self.assertEqual(self.ok("hp", "Kael", "-1"), ["[hp Kael 8→7/11]"])
        self.assertEqual(self.ok("cond", "kael-ashford", "+prone"), ["[cond Kael +prone · now poisoned 3r, prone]"])
        self.assertEqual(self.read_bytes("pcs/kael-ashford.md"), kael_file)
        from fixture import Scripted
        import roll
        lines, _ = roll.attack("Veskar", "Kael Ashford", roller=Scripted([1 + 0]))
        self.assertEqual(lines, ["[Veskar → Kael: d20 1+14=15 vs AC 15 — MISS (nat 1)]"])  # row AC 15, not file AC 18

    def test_combat_row_hp_and_cond(self):
        self.assertEqual(self.ok("hp", "Kael", "-4"), ["[hp Kael 9→5/11]"])
        self.assertEqual(self.ok("cond", "Kael", "+prone"), ["[cond Kael +prone · now poisoned 3r, prone]"])
        self.assertEqual(self.ok("cond", "Kael", "-poisoned"), ["[cond Kael -poisoned · now prone]"])
        row = md.load(self.path("state/current.md")).table("Combatants").rows[1]
        self.assertEqual((row["hp"], row["conditions"]), ("5/11", "prone"))
        # the PC file is untouched while in combat (06 L141: combat row, else frontmatter)
        self.assertEqual(self.front("pcs/kael-ashford.md")["hp"], {"current": 30, "max": 30})


class Conditions(Base):
    def test_cond_frontmatter(self):
        self.assertEqual(self.ok("cond", "Kira", "+poisoned", "1m"),
                         ["[cond Kira Thornwood +poisoned 1m · now poisoned 1m]"])
        self.assertEqual(self.ok("cond", "Kira", "+prone"),
                         ["[cond Kira Thornwood +prone · now poisoned 1m, prone]"])
        self.assertEqual(self.front("pcs/kira-thornwood.md")["conditions"], ["poisoned 1m", "prone"])
        self.ok("cond", "Kira", "-poisoned")
        self.assertEqual(self.front("pcs/kira-thornwood.md")["conditions"], ["prone"])
        self.assertIn("not stunned", self.fails("cond", "Kira", "-stunned"))
        self.assertIn("duration", self.fails("cond", "Kira", "+blinded", "3x"))


class Places(Base):
    def state(self):
        return md.load(self.path("state/current.md"))

    def test_move_npc_leaves_scene(self):
        self.assertEqual(self.ok("move-npc", "Mara", "crossroads-inn/kitchen"),
                         ["[move-npc Mara crossroads-inn/common-room→crossroads-inn/kitchen · left the scene]"])
        self.assertEqual(self.front("npcs/mara-fennick.md")["location"], "crossroads-inn/kitchen")
        self.assertFalse(any("**Mara**" in x for x in self.state().body))
        self.assertTrue(any("**Tobin**" in x for x in self.state().body))
        self.assertEqual(self.log()[-1], "  - move-npc Mara crossroads-inn/common-room→crossroads-inn/kitchen · left the scene")

    def test_move_npc_drops_stale_note_bullet(self):
        self.ok("move-npc", "Veskar", "old-mill")
        self.assertFalse(any(x.startswith("- (Veskar") for x in self.state().body))

    def test_move_npc_in_combat_refused(self):
        start_combat(self)
        self.assertIn("in combat — end combat or remove the row first", self.fails("move-npc", "Veskar", "old-mill"))

    def test_move_npc_offscreen_is_gm(self):
        self.assertEqual(self.ok("move-npc", "Veskar", "old-mill/loft"),
                         ["[move-npc Veskar crossroads-inn/upstairs→old-mill/loft]"])
        self.assertEqual(self.log()[-1], "  - (GM) move-npc Veskar crossroads-inn/upstairs→old-mill/loft")

    def test_move_validation(self):
        self.assertIn("no area 'attic'", self.fails("move-npc", "Veskar", "old-mill/attic"))
        self.assertIn("no location 'moon'", self.fails("move-npc", "Veskar", "moon"))
        self.assertIn("no area 'attic'", self.fails("move-party", "old-mill/attic"))
        self.assertIn("not an NPC", self.fails("move-npc", "Kael", "old-mill"))
        self.assertIn("not a location", self.fails("move-npc", "Veskar", "..\\pcs\\_template"))
        self.assertIn("not a location", self.fails("move-npc", "Veskar", "../pcs/_template"))
        self.assertIn("the world", self.fails("move-npc", "Veskar", "world"))
        self.assertIn("not a location", self.fails("move-party", "village-square/"))
        self.ok("move-npc", "Veskar", "thornbury")  # an area-tier location is a place
        self.assertEqual(self.front("npcs/veskar.md")["location"], "thornbury")

    def test_move_party(self):
        self.assertEqual(self.ok("move-party", "village-square/square"),
                         ["[move-party crossroads-inn/common-room→village-square/square (Kael Ashford, Kira Thornwood)]"])
        self.assertEqual(self.front("pcs/kael-ashford.md")["location"], "village-square/square")
        self.assertEqual(self.front("pcs/kira-thornwood.md")["location"], "village-square/square")
        self.assertEqual(self.state().front["party-location"], "village-square/square")

    def test_time(self):
        self.assertEqual(self.ok("time", "+20m")[0], "[TIME] Day 1 18:30 → Day 1 18:50 (+20m)")
        self.assertEqual(self.ok("time", "to", "dawn")[0], "[TIME] Day 1 18:50 → Day 2 06:00 (+11h10m)")
        text = self.path("state/current.md").read_text(encoding="utf-8")
        self.assertIn('in-game-datetime: "Day 2 06:00"   # dusk arrival', text)
        self.assertEqual(self.ok("time", "-5m"), ["[time Day 2 06:00→Day 2 05:55]"])


class People(Base):
    def test_attitude(self):
        self.assertEqual(self.ok("attitude", "mara", "friendly", "paid for Tobin's drinks"),
                         ["[attitude Mara neutral→friendly (paid for Tobin's drinks)]"])
        doc = md.load(self.path("npcs/mara-fennick.md"))
        self.assertEqual(doc.front["attitude-to-party"], "friendly")
        s, e = doc.section("History with the party")
        self.assertIn("- Day 1 18:30: neutral→friendly — paid for Tobin's drinks", doc.body[s:e])
        self.assertIn("one of", self.fails("attitude", "mara", "smitten"))


class Inventory(Base):
    def inv(self, rel="pcs/kira-thornwood.md"):
        doc = md.load(self.path(rel))
        s, e = doc.section("Inventory")
        return doc.body[s + 1:e]

    def test_coin(self):
        self.assertEqual(self.ok("coin", "Kira", "-5gp"), ["[coin Kira Thornwood 35→30 gp]"])
        self.assertIn("- Coin: 30 gp, a handful of copper", self.inv())
        self.assertEqual(self.ok("coin", "Kira", "+12sp"), ["[coin Kira Thornwood 0→12 sp]"])
        self.assertIn("- Coin: 12 sp, 30 gp, a handful of copper", self.inv())
        self.assertIn("can't pay", self.fails("coin", "Kira", "-50gp"))
        self.assertEqual(self.log()[-2:], ["  - coin Kira Thornwood 35→30 gp", "  - coin Kira Thornwood 0→12 sp"])

    def test_item(self):
        self.assertEqual(self.ok("item", "Kira", "-dagger", "taken by guard"),
                         ["[item Kira Thornwood -dagger (taken by guard)]"])
        self.assertIn("- Equipped: leather armor, shortsword, 1 dagger, shortbow + quiver (20 arrows)", self.inv())
        self.ok("item", "Kira", "-dagger")
        self.assertIn("- Equipped: leather armor, shortsword, shortbow + quiver (20 arrows)", self.inv())
        self.assertEqual(self.ok("item", "Kira", "+", "brass key"), ["[item Kira Thornwood +brass key]"])
        self.assertIn("  bedroll, 5 days rations, waterskin, dark hooded cloak, brass key", self.inv())
        self.assertIn("no 'lute'", self.fails("item", "Kira", "-lute"))

    def test_item_counts_and_matching(self):
        # count in parentheses
        self.ok("item", "Kira", "-arrows")
        self.assertIn("- Equipped: leather armor, shortsword, 2 daggers, shortbow + quiver (19 arrows)", self.inv())
        # leading count, singularized when it reaches 1
        self.ok("item", "Kira", "-flask of oil")
        self.assertIn("- Pack: thieves' tools, 50 ft silk rope, crowbar, hooded lantern, 1 flask of oil,", self.inv())
        # substring fallback
        self.ok("item", "Kira", "-silk")
        self.assertIn("- Pack: thieves' tools, crowbar, hooded lantern, 1 flask of oil,", self.inv())
        # ambiguity lists the candidates
        msg = self.fails("item", "Kael", "-s")
        self.assertIn("ambiguous", msg)
        self.assertIn("shield bearing", msg)

    def test_res(self):
        self.assertEqual(self.ok("res", "Kael", "-spell slot 1"), ["[res Kael Ashford spell slot 1 4→3/4]"])
        self.assertEqual(self.ok("res", "Kira", "-arrows", "3"), ["[res Kira Thornwood arrows 20→17/20]"])
        self.assertEqual(self.ok("res", "Kira", "+arrows", "9"), ["[res Kira Thornwood arrows 17→20/20]"])
        self.assertIn("can't spend", self.fails("res", "Kael", "-channel", "2"))
        t = md.load(self.path("pcs/kael-ashford.md")).table("Resources")
        self.assertEqual(t.rows[0]["current"], "3")
        self.assertIn("| spell slot 1      | 3       | 4   | long     |",
                      self.path("pcs/kael-ashford.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
