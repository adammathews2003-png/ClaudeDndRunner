"""Phase 4: geometry, scene enter, tempo/pos/intent/onstage, combat start/next/end, srd,
space.py placement and player view (plan.md Phase 4 → Verify and Guards)."""
import io
import json
import re
import unittest
from contextlib import redirect_stdout
from unittest import mock

from fixture import TOOLS, CampaignCase, Scripted, _edit, run_main, set_front_raw
from lib import campaign, geo, md, srd


def state_text(case):
    return case.path("state/current.md").read_text(encoding="utf-8")


class Geo(CampaignCase):
    def test_inn_to_mill(self):
        plan = geo.find_route("crossroads-inn/common-room", "old-mill")
        self.assertEqual(plan.rounded, 15)
        self.assertEqual([r.id for r in plan.routes], ["inn-door", "mill-rd"])
        town = geo.load("thornbury")
        d = geo.edge_distance(town.place("inn"), town.place("mill"))
        self.assertEqual(geo.distance_text(d), "0.8 mi")
        self.assertEqual(geo.bearing(town.place("inn").center(), town.place("mill").center()), "N")

    def test_reeve(self):
        town = geo.load("thornbury")
        d = geo.edge_distance(town.place("inn"), town.place("reeve"))
        self.assertEqual(geo.distance_text(d), "135 ft")
        self.assertEqual(geo.bearing(town.place("inn").center(), town.place("reeve").center()), "W")

    def test_to_parent_round_trips(self):
        inn = geo.load("crossroads-inn")
        for p in [(0, 0, 0), (45, 35, 10), (-5, 12.5, -10)]:
            self.assertEqual(geo.from_parent(inn, geo.to_parent(inn, p)), tuple(float(v) for v in p))
        self.assertEqual(geo.to_parent(inn, (0, 0, 0)), (65.0, -20.0, 0.0))
        town = geo.load("thornbury")  # ft → mi
        self.assertEqual(geo.to_parent(town, (5280, 0, 0)), (1.0, 0.0, 0.0))

    def test_factors_and_rounding(self):
        town = geo.load("thornbury")
        r = next(x for x in town.routes if x.id == "mill-rd")
        base = geo.route_minutes(town, r)
        self.assertAlmostEqual(geo.route_minutes(town, r, pace="fast"), base * 0.75)
        self.assertAlmostEqual(geo.route_minutes(town, r, pace="slow"), base * 1.5)
        self.assertAlmostEqual(geo.route_minutes(town, r, by="horse"), base * 0.5)
        self.assertAlmostEqual(geo.route_minutes(town, r, by="cart"), base)
        r.kind = "trail"
        self.assertAlmostEqual(geo.route_minutes(town, r), base * 1.5)
        r.time = "45m — switchbacks"
        self.assertEqual(geo.route_minutes(town, r), 45)
        self.assertEqual([geo.round_minutes(x) for x in (0.2, 14.01, 61, 92)], [1, 15, 65, 95])
        self.assertEqual(geo.parse_time("1h30m"), 90)
        self.assertEqual(geo.parse_time("2d"), 2880)

    def test_bearing_band_distance(self):
        o = (0, 0, 0)
        got = [geo.bearing(o, p) for p in [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]]
        self.assertEqual(got, ["E", "NE", "N", "NW", "W", "SW", "S", "SE"])
        self.assertEqual([geo.band(x) for x in (5, 30, 45, 100, 500)],
                         ["adjacent", "close", "nearby", "far", "distant"])
        self.assertEqual(geo.distance_text(4), "adjacent")
        self.assertEqual(geo.distance_text(2, "mi"), "2.0 mi")


class Scene(CampaignCase):
    def test_packet(self):
        code, lines = run_main(["scene", "enter", "crossroads-inn/common-room"])
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], "[SCENE] crossroads-inn/common-room (site · building, in thornbury) · light: bright")
        self.assertEqual(lines[2], "Exits: stairs → upstairs (W) · kitchen (NE) · trapdoor → cellar "
                                   "(locked (Mara); DC 12 to notice, N) · front door → village square "
                                   "(adjacent, W) · back-lane → village square (adjacent, W)")
        self.assertEqual(lines[3], "Nearby: village square adjacent W, 1 min · shrine of Chauntea 75 ft SW, no route"
                                   " · smithy 110 ft NW, no route · reeve's house 135 ft W, 1 min (via inn-door, "
                                   "reeve-path) · Harl's watermill 0.8 mi N, 15 min (via inn-door, mill-rd)")
        self.assertEqual(lines[4], "Present: Mara (npc, neutral) · Tobin (npc, friendly) · Kael, Kira (party)")
        self.assertTrue(lines[5].startswith("Not on stage but here: Veskar (upstairs — Movements: 04:00–00:00"))
        self.assertIn("Kael (PP 13) → DC 13 dried mud", lines[6])
        self.assertTrue(lines[7].startswith("Triggers mentioning this place/these NPCs: beat 1 (inn, Mara)"))
        self.assertEqual(lines[8], "Layout: common-room (11 features) — `gm.py space map` to draw")

    def test_light(self):
        code, lines = run_main(["scene", "enter", "old-mill/main-floor", "--light", "dim"])
        notices = next(line for line in lines if line.startswith("Passive notices"))
        self.assertIn("Kael (PP 13→8 dim) → nothing", notices)
        self.assertIn("Kira (PP 15) → DC 11 dark spatter", notices)  # darkvision ignores dim
        code, lines = run_main(["scene", "enter", "old-mill/main-floor", "--light", "dark"])
        notices = next(line for line in lines if line.startswith("Passive notices"))
        self.assertIn("Kael (dark, no darkvision) → nothing", notices)
        self.assertIn("Kira (PP 15→10 dark) → nothing", notices)

    def test_write_and_onstage(self):
        run_main(["rule", "add", "mist gives advantage", "--scope", "scene"])
        code, lines = run_main(["scene", "enter", "old-mill/main-floor", "--write",
                                "--summary", "The mill at dusk.", "--scene", "The old mill"])
        self.assertEqual(code, 0, lines)
        self.assertIn("[rule R1 ended — scene over]", lines)
        doc = md.load(self.path("state/current.md"))
        self.assertEqual(doc.front["party-location"], "old-mill/main-floor")
        self.assertEqual(doc.front["scene"], "The old mill")
        self.assertEqual(md.load(self.path("pcs/kael-ashford.md")).front["location"], "old-mill/main-floor")
        text = state_text(self)
        self.assertIn("## Summary\nThe mill at dusk.", text.replace("\r\n", "\n"))
        self.assertIn("beat 3", text)
        self.assertEqual(text.count("Day 3 02:00"), 1)
        run_main(["onstage", "Tobin", "--goal", "follow the party", "--note", "by the door"])
        self.assertIn("- **Tobin** (npcs/tobin-hale.md) — by the door; goal: follow the party", state_text(self))
        run_main(["onstage", "Tobin", "--remove"])
        self.assertNotIn("**Tobin**", state_text(self))

    def test_write_refused_in_combat(self):
        run_main(["tempo", "tense"])
        run_main(["combat", "start", "--init", "Kael=10", "--init", "Kira=10", "--seed", "1"])
        code, lines = run_main(["scene", "enter", "old-mill", "--write"])
        self.assertEqual(code, 1)
        self.assertIn("combat is running", lines[-1])


class Tempo(CampaignCase):
    def test_tense_positions(self):
        code, lines = run_main(["tempo", "tense", "--adj", "Mara +5 watching the room", "--adj", "Tobin −5 drunk",
                                "--pos", "Mara @bar", "--pos", "Tobin @tables-e", "--pos", "Kael near Tobin",
                                "--pos", "Kira @door"])
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], "[tempo tense: Mara 15 · Kira (PC) 13 · Kael (PC) 10 · Tobin 5]")
        stage = md.load(self.path("state/current.md")).table("Stage")
        for r in stage.rows:
            x, y, z = md.parse_point(r["pos"])
            self.assertTrue(x % 5 == 0 and y % 5 == 0 and z % 5 == 0, r)
            self.assertTrue(0 <= x <= 45 and 0 <= y <= 35, r)
        self.assertEqual(len({r["pos"] for r in stage.rows}), 4)

    def test_ties_to_pc_and_rerun_keeps(self):
        run_main(["tempo", "tense", "--adj", "Mara +3"])  # Mara 13 = Kira 13 → Kira first
        code, lines = run_main(["tempo", "tense"])
        self.assertEqual(lines[0], "[tempo tense: Kira (PC) 13 · Mara 13 · Kael (PC) 10 · Tobin 10]")

    def test_pos_side_intent_calm(self):
        run_main(["tempo", "tense"])
        # (25,30) north of the bar's middle is the locked trapdoor (a shut door is a wall)
        self.assertEqual(run_main(["pos", "Mara", "@bar", "N"])[1], ["[pos Mara @bar N → (20,30,0)]"])
        code, lines = run_main(["pos", "Kael", "@hearth"])  # a hazard: beside it, never in it
        x, y, _ = md.parse_point(lines[0].split("→")[1].strip(" ]"))
        self.assertNotEqual(x, 45)
        run_main(["intent", "Mara", "get", "the", "letter"])
        self.assertIn("get the letter", state_text(self))
        self.assertEqual(run_main(["pos", "Mara", "@nowhere"])[0], 1)
        run_main(["tempo", "calm"])
        self.assertNotIn("### Stage", state_text(self))
        log = self.path("sessions/session-current.md").read_text(encoding="utf-8")
        self.assertIn("(GM) positions at calm: ", log)
        self.assertIn("Mara (20,30,0)", log)


class Combat(CampaignCase):
    def start(self, *extra):
        run_main(["tempo", "tense", "--pos", "Mara @bar", "--pos", "Tobin @tables-e",
                  "--pos", "Kael near Tobin", "--pos", "Kira @door"])
        return run_main(["--seed", "1", "combat", "start", "--init", "Kael=15", "--init", "Kira=12", *extra])

    def test_start_requires_pc_init(self):
        run_main(["tempo", "tense"])
        code, lines = run_main(["combat", "start", "--init", "Kael=15"])
        self.assertEqual(code, 1)
        self.assertIn("--init Kira=N", lines[-1])
        self.assertEqual(run_main(["combat", "start", "--frame", "thornbury"])[0], 1)

    def test_start_map_next_end(self):
        code, lines = self.start("--add", "srd:thug x3 @25,15,0", "--add", "srd:bandit captain @bar N",
                                 "--surprised", "Tobin")
        self.assertEqual(code, 0, lines)
        self.assertTrue(lines[0].startswith("[combat start · round 1 · order: "))
        self.assertIn("[pos Bandit Captain @bar N → (20,30,0)]", lines)
        self.assertTrue(any(line.startswith("  35 ") for line in lines))     # the map
        self.assertFalse(any(" x " in line and "trapdoor" in line for line in lines))  # secret: player view
        doc = md.load(self.path("state/current.md"))
        rows = doc.table("Combatants").rows
        self.assertEqual(next(r for r in rows if r["name"] == "Thugs ×3")["hp"], "32/32 ea")
        self.assertEqual(next(r for r in rows if r["name"] == "Bandit Captain")["ac"], "15")
        self.assertIn("surprised 1r", next(r for r in rows if r["name"] == "Tobin")["conditions"])
        self.assertIsNotNone(doc.table("Terrain"))
        self.assertIn("Bounds: x 0–45", state_text(self))
        # space map renders from the block
        code, lines = run_main(["space", "map"])
        self.assertEqual(code, 0)
        # damage, round wrap ticks durations
        run_main(["do", "dmg Bandit 65; dmg Tobin 4; cond Kael +poisoned 2r; dmg Kael 7"])
        seen = []
        for _ in range(len(rows) + 1):
            code, lines = run_main(["combat", "next"])
            seen.append(lines[0])
        self.assertTrue(any(s.startswith("[round 2") for s in seen))
        self.assertFalse(any("up: Bandit Captain" in s or "up: Tobin" in s for s in seen))  # dead NPCs skipped
        self.assertIn("poisoned 1r", state_text(self))
        code, lines = run_main(["combat", "end", "--count", "Thugs"])
        self.assertEqual(code, 0, lines)
        self.assertIn("[Tobin: status dead]", lines)
        self.assertIn("[XP available: 750 (Bandit Captain defeated, Thugs ×3 counted) → 375 each for 2 present"
                      " · award with: xp award from-combat]", lines)
        kael = md.load(self.path("pcs/kael-ashford.md")).front
        self.assertEqual(kael["hp"], {"current": 23, "max": 30})
        self.assertEqual(kael["conditions"], [])  # round-based conditions end with the fight
        self.assertEqual(md.load(self.path("npcs/tobin-hale.md")).front["status"], "dead")
        self.assertIn("## Combat\n(not in combat)", state_text(self).replace("\r\n", "\n"))
        data = json.loads(self.path(".gm/last-combat.json").read_text(encoding="utf-8"))
        self.assertEqual(data["total"], 750)

    def test_xp_off(self):
        set_front_raw(self, "state/current.md", "xp-tracking", "off")
        self.start()
        code, lines = run_main(["combat", "end"])
        self.assertFalse(any("XP available" in line for line in lines))


class Srd(CampaignCase):
    def test_bandit_captain(self):
        code, lines = run_main(["srd", "monster", "bandit captain"])
        self.assertEqual(code, 0)
        self.assertIn("AC 15", lines[0])
        self.assertIn("HP 65 (10d8+20)", lines[0])

    def test_write(self):
        code, lines = run_main(["srd", "monster", "bandit captain", "--write", "Veskar"])
        self.assertEqual(code, 0, lines)
        doc = md.load(self.path("npcs/veskar.md"))
        self.assertEqual(doc.front["statblock"], "custom (srd: Bandit Captain)")
        self.assertEqual(doc.front["hp"], {"current": 65, "max": 65})
        self.assertEqual(doc.table("Attacks").rows[0]["name"], "scimitar")
        self.assertEqual(run_main(["srd", "monster", "bandit captain", "--write", "Veskar"])[0], 1)

    def test_spell_condition_and_errors(self):
        self.assertIn("Damage (fire, by slot level): 3: 8d6", run_main(["srd", "spell", "fireball"])[1][2])
        self.assertEqual(run_main(["srd", "condition", "poisoned"])[1][0], "[SRD Poisoned]")
        code, lines = run_main(["srd", "monster", "young"])
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", lines[0])


class Space(CampaignCase):
    def test_player_view_and_hidden(self):
        run_main(["tempo", "tense", "--pos", "Mara @bar", "--pos", "Tobin @tables-e",
                  "--pos", "Kael near Tobin", "--pos", "Kira @door"])
        run_main(["--seed", "1", "combat", "start", "--init", "Kael=15", "--init", "Kira=12"])
        run_main(["cond", "Tobin", "+invisible"])
        full = run_main(["space", "map"])[1]
        pv = run_main(["space", "map", "--player-view"])[1]
        self.assertTrue(any("trapdoor" in line for line in full))
        self.assertFalse(any("trapdoor" in line for line in pv))
        self.assertTrue(any(" Tobin " in line for line in full))
        self.assertFalse(any(" Tobin " in line for line in pv))

    def test_no_walking_on_air(self):
        run_main(["tempo", "tense", "--pos", "Kael 10,5,0", "--pos", "Mara 30,30,0",
                  "--pos", "Tobin 20,15,0", "--pos", "Kira 15,15,0"])
        code, lines = run_main(["space", "move", "Kael", "--to", "Mara"])
        path = lines[0]
        self.assertNotRegex(path, r",5\)")  # never at z 5 off the stairs
        code, lines = run_main(["space", "move", "Kael", "--to", "@landing"])
        self.assertIn("(0,15,0)", lines[0] + lines[1])  # goes up the stairs


class Guards(unittest.TestCase):
    def test_no_hand_typed_directions(self):
        for name in ("lib/geo.py", "scene.py"):
            text = (TOOLS / name).read_text(encoding="utf-8")
            body = re.sub(r'def bearing\(.*?\n(?=\S)', "", text, flags=re.S)  # bearing() is the one place
            self.assertIsNone(re.search(r'"(N|NE|E|SE|S|SW|W|NW)"', body), name)

    def test_no_network_in_gm_commands(self):
        for p in list(TOOLS.glob("*.py")) + list((TOOLS / "lib").glob("*.py")):
            if p.name == "fetch_srd.py":
                continue
            text = p.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\bimport (urllib|requests|http\.client|socket)\b", p.name)


if __name__ == "__main__":
    unittest.main()
