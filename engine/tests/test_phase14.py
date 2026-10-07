"""Phase 14: travel activities and getting lost, social DCs and the wall, morale, chases,
traps and hazards, hiding as a stored state (plan.md Phase 14 → Verify and Guards;
docs/design/02 → Table mechanics → Phase 14; 06 → Table mechanics → Phase 14)."""
import json

from fixture import CampaignCase, _edit, give_custom_veskar, run_main, set_front_raw
from lib import md

# a site deep in the woods north-east of the square, reached by a trackless route
HOLLOW = """---
name: Witch Hollow
tier: site
type: clearing
parent: thornbury
tags: []
---

# Witch Hollow

## Description
A clearing in the deep wood.

## Areas
- **clearing** — the open ground

## Hidden
(none yet)
"""
HOLLOW_PLACE = "| hollow | H     | Witch Hollow       | (9000,9000,0) | (9000,9000,0) | (9100,9100,0) | a clearing | hollow | scenario |\n"
HOLLOW_ROUTE = "| wood-tr  | square | hollow   |                                      | trackless | obvious |      | terrain: forest; forage: scarce |\n"
PIT = ("- DC 15: TRAP pit (common-room) · trigger: step on the loose boards (GM: Veskar rigged it last night) · "
       "disarm: DC 12 thieves' tools · effect: DEX save DC 13 or fall 20 ft · state: armed\n")
QUIET_TABLE = """# Chase complications — urban (test: nothing breaks line of sight)

| roll  | result | effect |
|-------|--------|--------|
| 1-10  | A cart in the way: lose 10 ft on a failed DC 10 DEX save | -10 ft on a fail |
| 11-20 | No complication | |
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
        return lines

    def front(self, rel):
        return md.load(self.path(rel)).front

    def text(self, rel):
        return self.path(rel).read_text(encoding="utf-8")

    def log(self):
        return self.text("sessions/session-current.md")

    def setting(self, key, value):
        set_front_raw(self, "state/current.md", key, value)

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

    def add_hollow(self):
        self.path("locations/hollow.md").write_text(HOLLOW, encoding="utf-8")
        _edit(self.path("locations/thornbury.md"), lambda t: t.replace(
            "| mill   | M     | Harl's watermill", HOLLOW_PLACE + "| mill   | M     | Harl's watermill", 1)
            .replace("| mill-rd  | square | mill", HOLLOW_ROUTE + "| mill-rd  | square | mill", 1))

    def add_pit(self):
        _edit(self.path("locations/crossroads-inn.md"), lambda t: t.replace("## Hidden\n", "## Hidden\n" + PIT, 1))


class Defaults(CampaignCase):
    def test_settings(self):
        from lib import campaign
        s = campaign.SETTINGS
        self.assertEqual((s["travel-detail"], s["getting-lost"], s["social-dcs"], s["creativity"],
                          s["social-wall"], s["morale"], s["chases"]),
                         ("summary", "on", "dmg", "light", 3, "on", "dmg"))
        self.assertEqual(s["supplies"], "off")   # foraging follows it: off by default


# ---------- travel ----------

class Travel(Base):
    def setUp(self):
        super().setUp()
        self.add_hollow()
        self.setting("travel-detail", "activities")

    def test_plan_on_the_road(self):
        self.setting("supplies", "loose")
        before = self.snapshot()
        out = self.ok("travel", "old-mill", "--plan", "--activities", "Kira=navigate,Kael=forage")
        self.assertEqual(self.snapshot(), before)                    # a dry run
        self.assertTrue(out[0].startswith("[TRAVEL PLAN] crossroads-inn/common-room → old-mill"))
        self.assertIn("  Navigate: on the road (inn-door, mill-rd) — no check", out)
        self.assertIn("  Forage: Kael, Survival DC 15 (limited)", out)
        out = self.ok("travel", "old-mill")                       # no --nav asked for on the road
        self.assertTrue(any(x.startswith("[SCENE] old-mill") for x in out), out)
        self.assertIn("Forage: Kael — no total given", "\n".join(out))

    def test_plan_trackless_prints_dcs(self):
        self.setting("supplies", "loose")
        self.ok("order", "front=Kael", "back=Kira")
        out = self.ok("travel", "hollow", "--plan", "--activities", "Kira=navigate,Kael=forage", "--hours", "10")
        self.assertIn("  Navigate: Kira, Survival DC 15 (forest, trackless)", out)
        self.assertIn("  Forage: Kael, Survival DC 20 (scarce)", out)
        self.assertIn("  Marching order: front Kael · back Kira", out)
        self.assertIn("    hour 9: CON save DC 11 (gm.py save <PC> con 11 · fail → gm.py exhaust <PC> +1 "
                      "\"forced march\")", out)
        self.assertIn("    hour 10: CON save DC 12", "\n".join(out))
        self.assertIn("  Next: gm.py travel hollow --nav <Kira's Survival total> --forage Kael=<total>", out)
        self.assertIn("off the road", self.fails("travel", "hollow")[-1])   # the navigator's total is asked

    def test_lost_and_found(self):
        self.ok("travel", "hollow", "--plan", "--activities", "Kira=navigate")
        before = self.snapshot()
        out = self.ok("--seed", "3", "travel", "hollow", "--nav", "8")
        text = "\n".join(out)
        self.assertIn("Navigate: Kira 8 vs DC 15 — off course", text)
        self.assertIn("  Lost: ", text)
        self.assertIn("not at hollow", text)
        self.assertFalse(any(x.startswith("[SCENE]") for x in out))
        st = self.front("state/current.md")
        self.assertEqual(st["party-location"], "@lost")
        self.assertRegex(st["lost"], r"^to hollow · at \([-\d.]+,[-\d.]+,0\) world · bearing \w+ \(meant \w+\) · "
                                     r"terrain forest · since Day 1 ")
        self.assertEqual(self.front("pcs/kira-thornwood.md")["location"], "@lost")
        self.assertNotIn("hollow", str(self.front("pcs/kael-ashford.md")["location"]))
        self.assertIn("(GM) move-party crossroads-inn/common-room→@lost", self.log())
        found = [x for x in run_main(["lint"])[1] if "@lost" in x]
        self.assertEqual(found, [])
        # the navigator checks again: straight-line cross-country from where they are
        out = self.ok("travel", "hollow", "--nav", "18")
        self.assertTrue(out[0].startswith("[TRAVEL] @lost → hollow · "), out[0])
        self.assertIn("(cross-country (off course))", out[0])
        self.assertTrue(any(x.startswith("[SCENE] hollow") for x in out))
        st = self.front("state/current.md")
        self.assertEqual(st["party-location"], "hollow")
        self.assertNotIn("lost", st)
        self.ok("undo")
        self.ok("undo")
        self.assertEqual(self.snapshot(), before)

    def test_lost_starts_where_the_road_ends(self):
        """Guard: the road legs are walked, then the wrong bearing; no route the party
        didn't take, no straight line to the goal."""
        from lib import campaign, geo
        import explore
        self.ok("--seed", "5", "travel", "hollow", "--nav", "1", "--activities", "Kira=navigate")
        info = explore.lost_info()
        top, goal = explore.site_point("hollow")
        _, start = explore.world_point(geo.load("thornbury"), (0.0, 0.0, 0.0))
        self.assertEqual(top.slug, "world")
        import math
        d_goal = math.dist(info["at"][:2], goal[:2])
        self.assertGreater(d_goal, 0.5)                     # nowhere near the destination
        self.assertNotEqual(info["bearing"], info["meant"])
        self.assertNotIn("travel crossroads-inn/common-room → hollow", self.log())   # never "arrived"
        campaign.set_override(str(self.camp))

    def test_getting_lost_off_and_summary(self):
        self.setting("getting-lost", "off")
        out = self.ok("travel", "hollow")
        self.assertIn("  Navigate: getting-lost: off (wood-tr)", out)
        self.ok("undo")
        self.setting("travel-detail", "summary")
        out = self.ok("travel", "hollow")
        self.assertFalse(any("Navigate" in x for x in out))

    def test_forage_and_supplies_off(self):
        inv = self.text("pcs/kael-ashford.md")
        out = self.ok("travel", "hollow", "--nav", "20", "--activities", "Kira=navigate,Kael=forage",
                      "--forage", "Kael=25")
        self.assertIn("  Forage: Kael — supplies: off, nothing is counted", out)
        self.assertEqual(self.text("pcs/kael-ashford.md").split("## Inventory")[1],
                         inv.split("## Inventory")[1])
        self.ok("undo")
        self.setting("supplies", "loose")
        out = self.ok("--seed", "2", "travel", "hollow", "--nav", "20", "--activities", "Kira=navigate,Kael=forage",
                      "--forage", "Kael=25")
        line = next(x for x in out if x.startswith("  Forage: Kael 25 vs DC 20 (scarce)"))
        self.assertIn("days of rations", line)
        self.assertRegex(self.text("pcs/kael-ashford.md"), r"\d+ days rations")
        self.assertIn("  Watch: nobody — only watchers notice an ambush", out)

    def test_watchers_and_fast_pace(self):
        out = self.ok("travel", "hollow", "--plan", "--pace", "fast", "--activities", "Kira=navigate")
        self.assertIn("  Watch: Kael (passive 13; fast pace −5 → 8)", out)

    def test_order(self):
        out = self.assert_undoes("order", "front=Kael", "middle=Kira")
        self.assertEqual(out, ["[order front Kael · middle Kira]"])
        self.ok("order", "front=Kael", "back=Kira")
        self.assertEqual(self.front("state/current.md")["marching-order"], {"front": ["Kael"], "back": ["Kira"]})
        self.assertIn("Marching order: front Kael · back Kira", self.ok("scene", "enter", "crossroads-inn/common-room"))
        self.assertEqual(self.ok("order"), ["[Marching order: front Kael · back Kira]"])
        self.ok("order", "clear")
        self.assertNotIn("marching-order", self.front("state/current.md"))


# ---------- social ----------

class Social(Base):
    def ask(self, *extra):
        return self.ok("check", "Kira", "persuasion", "--vs", "mara", "--ask", "major", *extra)

    def test_verify_dcs_flair_and_tastes(self):
        self.ok("attitude", "Mara", "wary")
        out = self.ask()
        self.assertEqual(out[0], "[social] Kira persuasion vs Mara · wary · major: DC 30")
        self.assertIn("ask: Kira persuasion vs DC 30", out[-1])
        out = self.ask("--flair", "3", "--pitch", "x")
        self.assertEqual(out[1], '  leverage 0 · flair 3 ("x"): −8, advantage → DC 22')
        self.assertIn("DC 22 with advantage", out[-1])
        set_front_raw(self, "npcs/mara-fennick.md", "moved-by", ["nothing"])
        out = self.ask("--flair", "3", "--pitch", "y")
        self.assertEqual(out[1], '  leverage 0 · flair 2 (moved by nothing: 3→2, "y"): −5 → DC 25')
        self.assertNotIn("advantage", out[-1])
        set_front_raw(self, "npcs/mara-fennick.md", "moved-by", ["audacity"])
        out = self.ask("--flair", "2", "--pitch", "z", "--appeal", "audacity")
        self.assertIn("flair 3 (moved by audacity: 2→3", out[1])

    def test_repeat_pitch_scores_zero(self):
        self.ok("attitude", "Mara", "wary")
        out = self.ask("--flair", "3", "--pitch", "x", "25")
        self.assertEqual(out[2], "[Kira Thornwood persuasion: total 25 vs DC 22 — SUCCESS by 3]")
        self.assertEqual(out[3], "[social] yes")
        out = self.ask("--flair", "3", "--pitch", "x")
        self.assertIn("flair 0 (already tried on Mara", out[1])
        self.assertIn("→ DC 30", out[1])

    def test_friendly_and_no_refusal(self):
        self.ok("attitude", "Mara", "friendly")
        self.assertEqual(self.ask()[0], "[social] Kira persuasion vs Mara · friendly · major: DC 20")
        self.ok("attitude", "Mara", "hostile")
        out = self.ask("--leverage", "5")                 # Guard: a long shot, never a refusal
        self.assertIn("leverage +5 → DC 35", out[1])

    def test_core_is_the_only_refusal(self):
        lines = self.fails("check", "Kira", "persuasion", "--vs", "mara", "--ask", "major", "--core")
        self.assertIn("[social] no roll: core scenario — steer to another route to the same goal", lines)

    def test_wall_stages_band_and_success(self):
        self.ok("attitude", "Mara", "wary")
        goal = ("--goal", "get the ledger")
        cues = []
        for _ in range(3):
            out = self.ask(*goal, "5")
            cues.append(out[-1])
        self.assertTrue(cues[0].startswith("[social] stage 1: show a feeling"), cues)
        self.assertTrue(cues[1].startswith("[social] stage 2: have them name what it would take"), cues)
        self.assertTrue(cues[2].startswith("[social] stage 3+: a different approach starts a band lower"), cues)
        row = md.load(self.path("state/social.md")).table("Social goals").rows[0]
        self.assertEqual((row["npc"], row["goal"], row["fails"], row["approaches"]),
                         ("mara-fennick", "get the ledger", "3", "persuasion"))
        same = self.ask(*goal)
        self.assertIn("→ DC 30", same[-2])
        self.assertNotIn("new approach", "\n".join(same))
        new = self.ok("check", "Kira", "deception", "--vs", "mara", "--ask", "major", *goal)
        self.assertIn("new approach: −5 → DC 25", "\n".join(new))
        why = self.ask(*goal, "--why", "her brother's debts")
        self.assertIn("new approach: −5 → DC 25", "\n".join(why))
        self.assertIn('Social: Mara "get the ledger" 3 fails', self.ok("brief"))
        self.assertIn("Mara \"get the ledger\" · 3 fails", "\n".join(self.ok("social", "status")))
        out = self.ok("check", "Kira", "deception", "--vs", "mara", "--ask", "major", *goal, "30")
        self.assertIn('[social] "get the ledger" won after 4 tries — row closed', out)
        self.assertEqual(md.load(self.path("state/social.md")).table("Social goals").rows, [])
        self.assertIn("[social] get the ledger — won after 4 tries", self.log())

    def test_wall_off_and_intro(self):
        self.assertTrue(any(x.startswith("[TELL THE TABLE] social-wall on") for x in self.ok("intro")))
        out = self.assert_undoes("social", "wall", "off")
        self.assertEqual(out, ["[social] wall off (table's choice)"])
        self.ok("social", "wall", "off")
        self.assertEqual(self.front("state/current.md")["social-wall"], "off")
        self.assertFalse(any(x.startswith("[TELL THE TABLE]") for x in self.ok("intro")))
        out = self.ask("--goal", "get the ledger", "5")
        self.assertFalse(any("stage" in x for x in out))
        self.assertFalse(self.path("state/social.md").exists())
        self.ok("social", "wall", "on")
        self.assertEqual(self.front("state/current.md")["social-wall"], 3)
        self.assertIn("[social] wall on (table's choice)", self.log())

    def test_flair_is_gm_only_and_logged_first(self):
        """Guard: flair and pitches only in (GM) lines, written before the result."""
        self.ok("attitude", "Mara", "wary")
        self.ask("--flair", "3", "--pitch", "goat grandfather", "--goal", "cross", "12")
        log = self.log().splitlines()
        gm = next(i for i, x in enumerate(log) if x.startswith("  - (GM) [social]") and "flair 3" in x)
        roll = next(i for i, x in enumerate(log) if "persuasion: total 12" in x)
        self.assertLess(gm, roll)
        public = [x for x in log if x.startswith("  - ") and not x.startswith("  - (GM)")]
        self.assertFalse(any("flair" in x or "goat" in x or "stage" in x for x in public), public)

    def test_social_dcs_gm_and_drop(self):
        self.setting("social-dcs", "gm")
        self.assertIn("--dc N", self.fails("check", "Kira", "persuasion", "--vs", "mara", "--ask", "minor")[-1])
        out = self.ok("check", "Kira", "persuasion", "--vs", "mara", "--ask", "minor", "--dc", "18")
        self.assertIn("DC 18", out[0])
        self.ok("check", "Kira", "persuasion", "--vs", "mara", "--ask", "minor", "--dc", "18", "--goal", "g", "3")
        out = self.assert_undoes("social", "drop", "mara", "g")
        self.assertEqual(out, ['[social] Mara "g" dropped (the party gave up on it)'])

    def test_plain_check_unchanged(self):
        out = self.ok("check", "Kira", "stealth", "12", "--d20", "10")
        self.assertEqual(out, ["[Kira Thornwood stealth: d20 10+7=17 vs DC 12 — SUCCESS by 5]"])
        self.assertIn("DC is missing", self.fails("check", "Kira", "stealth")[-1])


# ---------- morale ----------

class Morale(Base):
    def start(self):
        self.ok("--seed", "2", "combat", "start", "--init", "Kael=10", "--init", "Kira=12",
                "--add", "srd:bandit x3 @20,20,0")

    def test_once_per_trigger(self):
        self.start()
        self.ok("dmg", "Bandits", "6")                                   # Bandit 1 5/11: below half
        out = self.ok("combat", "next")
        morale = [x for x in out if x.startswith("[Morale")]
        self.assertEqual(morale, ["[Morale (half HP): Bandits — WIS save DC 10 (gm.py save Bandits wis 10); "
                                  "fail → flee or surrender (gm.py cond Bandits +fled | +surrendered)]"])
        self.ok("dmg", "Bandits", "7")                                   # another below half: same trigger
        for _ in range(4):
            self.assertFalse(any(x.startswith("[Morale") for x in self.ok("combat", "next")))
        self.assertIn("Morale: bandit (half HP)", self.text("state/current.md"))

    def test_never_for_the_party_and_off(self):
        self.start()
        self.ok("hp", "Kira", "-20")
        self.assertFalse(any("Morale" in x for x in self.ok("combat", "next")))
        self.setting("morale", "off")
        self.ok("dmg", "Bandits", "8")
        self.assertFalse(any("Morale" in x for x in self.ok("combat", "next")))

    def test_exempt_undead_and_fearless(self):
        self.ok("--seed", "2", "combat", "start", "--init", "Kael=10", "--init", "Kira=12",
                "--add", "srd:zombie x2 @20,20,0")
        self.ok("dmg", "Zombies", "15")
        self.assertFalse(any("Morale" in x for x in self.ok("combat", "next")))

    def test_fled_counts_for_xp_and_prisoners(self):
        self.start()
        self.ok("dmg", "Bandits", "6")
        self.ok("cond", "Bandit 1", "+fled")
        self.ok("cond", "Bandits", "+surrendered")
        names = [x for x in self.ok("combat", "next") if x.startswith("[round")]
        self.assertFalse(any("Bandit" in x for x in names))              # out of the turn order
        out = self.ok("combat", "end")
        self.assertIn("[Bandits ×2 surrendered: on stage as a prisoner]", out)
        xp = next(x for x in out if x.startswith("[XP available"))
        self.assertIn("Bandit 1 fled", xp)
        self.assertIn("Bandits ×2 surrendered", xp)
        self.assertIn("[XP available: 75 ", xp)
        self.assertIn("- **Bandits ×2** — prisoner (surrendered)", self.text("state/current.md"))
        out = self.ok("xp", "award", "from-combat", "--reason", "the bandits")
        self.assertIn("XP +37 each", out[0])


# ---------- chases ----------

class Chase(Base):
    def setUp(self):
        super().setUp()
        (self.camp / "tables").mkdir(exist_ok=True)
        self.path("tables/chase-urban.md").write_text(QUIET_TABLE, encoding="utf-8")
        _edit(self.path("npcs/veskar.md"), lambda t: t.replace("con: 14", "con: 8", 1))   # 3 − 1 = 2 free

    def test_verify_dashes(self):
        out = self.ok("chase", "start", "--quarry", "Veskar", "--pursuers", "Kael")
        self.assertEqual(out[0], "[chase start · quarry Veskar · pursuers Kael · lead 60 ft · env urban]")
        self.assertIn("## Chase — round 1 · up: Veskar · env: urban", self.text("state/current.md"))
        for k in range(4):
            out = self.ok("--seed", str(k), "chase", "next")
            self.assertFalse(any("CON save" in x for x in out), out)
        out = self.ok("--seed", "9", "chase", "next")                   # Veskar's third Dash, two free
        self.assertIn("[Veskar dashes past their free Dashes (3/2): CON save DC 10]", out)
        self.assertTrue(any("Veskar CON save" in x for x in out), out)
        t = md.load(self.path("state/current.md")).table("Chase")
        self.assertEqual([r["dashes"] for r in t.rows], ["3/2", "2/5"])
        self.assertIn("Combat: chase round 3 · up: Kael", "\n".join(self.ok("brief")))

    def test_pc_dash_asks_and_caught(self):
        self.ok("chase", "start", "--quarry", "Veskar", "--pursuers", "Kira", "--lead", "10")
        self.ok("--seed", "1", "chase", "next", "--no-dash")             # Veskar 10 → 40
        out = self.ok("--seed", "1", "chase", "next")                    # Kira 0 → 70: caught
        self.assertIn("[chase end · caught: start combat or grapple]", out)
        self.assertIn("## Combat\n(not in combat)", self.text("state/current.md").replace("\r\n", "\n"))
        self.assertTrue(any(x.startswith("[TIME] Day 1 18:30 → Day 1 18:31") for x in out))

    def test_escape_out_of_sight(self):
        self.setting("light", "dark")
        self.ok("chase", "start", "--quarry", "Veskar", "--pursuers", "Kael")
        out = self.ok("--seed", "4", "chase", "next")                    # gap 120 > Kael's sight (no darkvision)
        self.assertTrue(any("is out of sight (gap 120 ft > sight 0 ft): Stealth" in x for x in out), out)

    def test_refusals_narrative_and_undo(self):
        self.assert_undoes("chase", "start", "--quarry", "Veskar", "--pursuers", "Kael")
        self.ok("chase", "start", "--quarry", "Veskar", "--pursuers", "Kael")
        self.assertIn("chase is running", self.fails("combat", "start", "--init", "Kael=3", "--init", "Kira=3")[-1])
        self.assertIn("chase is running", self.fails("travel", "old-mill")[-1])
        self.assert_undoes("--seed", "1", "chase", "next")
        self.assert_undoes("chase", "end", "gave-up")
        self.ok("chase", "end")
        self.setting("chases", "narrative")
        self.assertIn("chases: narrative", self.ok("chase", "start", "--quarry", "Veskar")[0])


# ---------- traps and hazards ----------

class Traps(Base):
    def setUp(self):
        super().setUp()
        self.add_pit()

    def test_verify_pit(self):
        out = self.ok("trap", "trigger", "pit", "--who", "Kael")
        self.assertEqual(out, ["[trap pit springs on Kael: DEX save DC 13 — ask for the d20 "
                               "(gm.py trap trigger pit --who Kael <total>)]"])
        out = self.assert_undoes("--seed", "1", "trap", "trigger", "pit", "--who", "Kael", "8")
        out = self.ok("--seed", "1", "trap", "trigger", "pit", "--who", "Kael", "8")
        self.assertEqual(out[0], "[trap pit triggered · Kael]")
        self.assertIn("[Kael Ashford DEX save: total 8 vs DC 13 — FAIL by 5]", out)
        self.assertTrue(any(x.startswith("[hazard fall Kael 20 ft: 2d6 ") for x in out), out)
        f = self.front("pcs/kael-ashford.md")
        self.assertLess(f["hp"]["current"], 30)
        self.assertIn("prone", f["conditions"])
        status = self.ok("trap", "status")
        self.assertIn("(GM)   pit (common-room) · triggered · notice DC 15", status[1])
        self.assertIn("state: triggered", self.text("locations/crossroads-inn.md"))

    def test_gm_details_never_public(self):
        """Guard: `(GM …)` notes and the disarm never reach player output or public log lines."""
        out = self.ok("--seed", "1", "trap", "trigger", "pit", "--who", "Kael", "8")
        public = [x for x in self.log().splitlines() if x.startswith("  - ") and not x.startswith("  - (GM)")]
        for text in out + public:
            self.assertNotIn("rigged", text)
            self.assertNotIn("thieves' tools", text)
        self.assertTrue(all(x.startswith("(GM)") for x in self.ok("trap", "status")))
        self.ok("undo")
        packet = "\n".join(self.ok("scene", "enter", "crossroads-inn/common-room"))
        self.assertIn("DC 15 TRAP pit (step on the loose boards)", packet)   # Kira's passive 15 notices it
        self.assertNotIn("rigged", packet)

    def test_disarm(self):
        out = self.assert_undoes("trap", "disarm", "pit", "--who", "Kira", "14")
        self.assertEqual(out, ["[trap pit: Kira 14 vs DC 12 — disarmed]"])
        out = self.ok("trap", "disarm", "pit", "--who", "Kira", "9")
        self.assertIn("not disarmed (still armed", out[0])
        out = self.ok("trap", "disarm", "pit", "--who", "Kira", "6")
        self.assertIn("missed by 6: it goes off", out[0])
        self.assertIn("ask for the d20", out[1])
        self.ok("trap", "disarm", "pit", "--who", "Kira", "13")
        self.assertIn("is disarmed, not armed", self.fails("trap", "trigger", "pit")[-1])
        self.assertNotIn("TRAP pit", "\n".join(self.ok("scene", "enter", "crossroads-inn/common-room")))

    def test_crlf_and_lf_trap_lines_parse(self):
        import hazard
        from lib import geo
        for conv in (lambda b: b.replace(b"\r\n", b"\n"), lambda b: b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")):
            p = self.path("locations/crossroads-inn.md")
            p.write_bytes(conv(p.read_bytes()))
            ts = hazard.traps(geo.load("crossroads-inn"))
            self.assertEqual([(t.id, t.area, t.notice, t.disarm_dc(), t.state) for t in ts],
                             [("pit", "common-room", 15, 12, "armed")])

    def test_lint(self):
        _edit(self.path("locations/crossroads-inn.md"), lambda t: t.replace(
            "## Hidden\n", "## Hidden\n- DC 12: TRAP\n- DC 10: TRAP dart · effect: +6 to hit, 1d4 piercing · state: bent\n", 1))
        _edit(self.path("locations/thornbury.md"), lambda t: t.replace(
            "tags: [village]", "tags: [village]\nterrain: moon\nforage: plenty", 1))
        found = "\n".join(run_main(["lint"])[1])
        self.assertIn("a TRAP line doesn't parse", found)
        self.assertIn("TRAP dart: state 'bent'", found)
        self.assertIn("file: terrain 'moon'", found)
        self.assertIn("file: forage 'plenty'", found)
        self.assertNotIn("TRAP pit", found)


class Hazards(Base):
    def test_verify_breath(self):
        _edit(self.path("pcs/kael-ashford.md"), lambda t: t.replace("con: 14", "con: 12", 1))
        out = self.assert_undoes("hazard", "breath", "Kael")
        self.assertTrue(out[0].startswith("[hazard Kael holding breath 2m (1 + CON +1) · then choking 1r"), out)
        self.ok("hazard", "breath", "Kael")
        self.assertEqual(self.front("pcs/kael-ashford.md")["conditions"], ["holding-breath 2m"])
        out = self.ok("time", "+2m")
        self.assertIn("  [Kael is out of breath: choking 1r, then 0 HP]", out)
        out = self.ok("time", "+1m")
        self.assertIn("  [Kael has choked: 0 HP]", out)
        self.assertEqual(self.front("pcs/kael-ashford.md")["death-saves"], {"ok": 0, "fail": 0})

    def test_fall(self):
        out = self.assert_undoes("--seed", "1", "hazard", "fall", "Kira", "250")
        self.assertTrue(out[0].startswith("[hazard fall Kira 250 ft: 20d6 "), out[0])
        self.assertIn("no damage", self.ok("hazard", "fall", "Kira", "5")[0])

    def test_env_cold_hourly(self):
        out = self.assert_undoes("hazard", "env", "extreme-cold")
        self.ok("hazard", "env", "extreme-cold")
        _edit(self.path("pcs/kira-thornwood.md"), lambda t: t.replace("dark hooded cloak", "dark hooded cloak, cold-weather gear", 1))
        out = self.ok("time", "+2h")
        self.assertIn('  Environment (extreme-cold) hour 1: CON save DC 10 — Kael (gm.py save <PC> con 10 · '
                      'fail → gm.py exhaust <PC> +1 "cold")', out)
        self.assertIn("  Environment: exempt — Kira", out)
        self.ok("hazard", "env", "extreme-heat")
        out = self.ok("time", "+2h")
        self.assertIn("hour 2: CON save DC 6", "\n".join(out))
        self.ok("hazard", "env", "none")
        self.assertNotIn("environment", self.front("state/current.md"))
        self.assertFalse(any("Environment" in x for x in self.ok("time", "+1h")))

    def test_underwater_attacks_and_fire(self):
        from test_phase13 import COMBAT
        _edit(self.path("state/current.md"), lambda t: t.replace("## Combat\n(not in combat)", COMBAT, 1))
        self.ok("hazard", "env", "underwater")
        self.ok("pos", "Veskar", "10,5,0")
        out = self.ok("atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "10")
        self.assertIn("underwater (piercing weapon: no penalty)", out[0])
        out = self.ok("atk", "Veskar", "Kira", "--with", "scimitar", "--seed", "1")
        self.assertIn("underwater melee: disadvantage", out[0])
        self.assertIn("d20 (", out[0])                                   # rolled twice
        self.ok("pos", "Veskar", "10,40,0")
        out = self.ok("atk", "Kira", "Veskar", "--with", "shortbow", "--d20", "10")
        self.assertIn("underwater ranged: disadvantage", out[0])
        self.ok("pos", "Veskar", "10,300,0")
        out = self.ok("atk", "Kira", "Veskar", "--with", "shortbow", "--d20", "20")
        self.assertIn("underwater, beyond normal range", out[0])
        self.assertIn("MISS", out[0])
        out = self.ok("dmg", "Kira", "10", "fire")
        self.assertIn("→ 5", out[0])


# ---------- hiding ----------

class Hiding(Base):
    def setUp(self):
        super().setUp()
        set_front_raw(self, "npcs/veskar.md", "passive-perception", 14)

    def test_verify_hide_scene_seek(self):
        out = self.assert_undoes("hide", "Kira", "17")
        self.ok("hide", "Kira", "17")
        self.assertEqual(self.front("pcs/kira-thornwood.md")["conditions"], ["hidden 17"])
        self.ok("move-npc", "Veskar", "crossroads-inn/common-room")
        packet = self.ok("scene", "enter", "crossroads-inn/common-room")
        line = next(x for x in packet if x.startswith("Hidden: Kira (17)"))
        self.assertIn("Veskar (passive 14)", line)
        self.assertNotIn("spotted", line)
        out = self.assert_undoes("seek", "Veskar", "18")
        self.assertEqual(out, ["[seek Veskar 18: spots Kira (hidden 17)]"])
        self.ok("seek", "Veskar", "18")
        self.assertEqual(self.front("pcs/kira-thornwood.md")["conditions"], [])

    def test_spotted_on_hide_and_missed_seek(self):
        self.ok("move-npc", "Veskar", "crossroads-inn/common-room")
        self.ok("onstage", "Veskar")
        out = self.ok("hide", "Kira", "14")
        self.assertIn("spotted by Veskar (passive 14)", out[0])
        self.assertTrue(any("plain view" in x for x in out))
        self.ok("hide", "Kira", "19")
        out = self.ok("seek", "Veskar", "12")
        self.assertEqual(out[0], "[seek Veskar 12: spots no one]")
        self.assertEqual(out[1], "(GM) still hidden: Kira")
        self.assertIn("(GM) seek Veskar 12: still hidden Kira", self.log())

    def test_group(self):
        self.ok("move-npc", "Veskar", "crossroads-inn/common-room")
        self.ok("onstage", "Veskar")
        out = self.ok("hide", "Kael,Kira", "9,18", "--group")
        self.assertIn("1 of 2 beat the best passive 14 → hidden", out[0])
        self.assertEqual(self.front("pcs/kael-ashford.md")["conditions"], ["hidden 9"])
        self.ok("cond", "Kael", "-hidden")
        self.ok("cond", "Kira", "-hidden")
        out = self.ok("hide", "Kael,Kira", "9,12", "--group")
        self.assertIn("0 of 2 beat the best passive 14 → spotted", out[0])
        self.assertEqual(self.front("pcs/kael-ashford.md")["conditions"], [])

    def test_combat_start_compares_and_attack_reveals(self):
        self.ok("hide", "Kira", "12")
        out = self.ok("--seed", "3", "combat", "start", "--init", "Kael=10", "--init", "Kira=12")
        self.assertIn("[hidden: Kira (12) — unseen by Tobin (passive 10), Mara (passive 10)]", out)
        self.ok("pos", "Kira", "10,10,0")
        self.ok("pos", "Mara", "10,15,0")
        out = self.ok("atk", "Kira", "Mara", "--d20", "10", "--with", "shortsword")
        self.assertIn("hidden (12): advantage", out[0])
        self.assertIn("[Kira is no longer hidden (attacked)]", out)
        t = md.load(self.path("state/current.md")).table("Combatants")
        kira = next(r for r in t.rows if r["name"].startswith("Kira"))
        self.assertNotIn("hidden", kira["conditions"])

    def test_player_rolls_their_own(self):
        self.assertIn("rolls their own Stealth", self.fails("hide", "Kira")[-1])
        out = self.ok("--seed", "1", "hide", "Veskar")
        self.assertIn("(Stealth d20 ", out[0])


class Undo(Base):
    """Every new mutating command undoes cleanly (the rest are covered above)."""

    def test_social_check_creates_and_undo_removes_the_file(self):
        self.assert_undoes("check", "Kira", "persuasion", "--vs", "mara", "--ask", "minor", "--goal", "g", "3")
        self.assertFalse(self.path("state/social.md").exists())

    def test_chase_dash_and_morale(self):
        (self.camp / "tables").mkdir(exist_ok=True)
        self.path("tables/chase-urban.md").write_text(QUIET_TABLE, encoding="utf-8")
        self.ok("chase", "start", "--quarry", "Veskar", "--pursuers", "Kira")
        out = self.assert_undoes("chase", "dash", "Kira")
        self.assertEqual(out[0], "[chase Kira dashes again: 0→30 ft (1/5)]")
        self.ok("chase", "end")
        self.ok("--seed", "2", "combat", "start", "--init", "Kael=10", "--init", "Kira=12",
                "--add", "srd:bandit x3 @20,20,0")
        self.ok("dmg", "Bandits", "6")
        out = self.assert_undoes("combat", "next")
        self.assertTrue(any(x.startswith("[Morale (half HP)") for x in out))


class CampaignNewSettings(CampaignCase):
    """`/campaign-new` asks social-wall with the other settings: `--set social-wall=off`."""

    def test_table_settings_at_creation(self):
        import shutil
        import tempfile
        from pathlib import Path
        from unittest import mock
        from lib import campaign
        tmp = Path(tempfile.mkdtemp(prefix="gm-camp-"))
        try:
            with mock.patch.object(campaign, "CAMPAIGNS", tmp):
                code, lines = run_main(["campaign", "new", "gull", "--area", "Gull Harbour",
                                        "--set", "social-wall=off", "creativity=generous"])
                self.assertEqual(code, 0, lines)
                f = md.load(tmp / "gull" / "campaign.md").front
                self.assertEqual((f["social-wall"], f["creativity"]), ("off", "generous"))
                self.assertNotIn("morale", f)                     # unset settings aren't written
                code, lines = run_main(["campaign", "new", "x", "--area", "A", "--set", "nonsense=1"])
                self.assertEqual(code, 1)
        finally:
            campaign.set_override(str(self.camp))
            shutil.rmtree(tmp, ignore_errors=True)
