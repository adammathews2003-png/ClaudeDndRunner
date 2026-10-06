"""The session opening and the bigger map: `gm.py intro` (title card, premise, why you're
here, `--why`), lib/banner.py, and `space map` (whole Layout, cell size, `--at` sketches in a
calm scene, unique letters) (docs/design/06 → `gm.py intro`; Tactical map size)."""
from fixture import CampaignCase, _edit, run_main
from lib import banner, md


class Banner(CampaignCase):
    def test_card_wraps_and_fits(self):
        lines = banner.card("The Missing Miller", "Our tale begins")
        self.assertTrue(all(len(x) <= 72 for x in lines))
        self.assertEqual(sum(1 for x in lines if "█" in x), 10)        # two rows of 5
        self.assertTrue(any("Our tale begins" in x for x in lines))
        long = banner.card("Supercalifragilisticexpialidocious", "x")
        self.assertTrue(any("S U P E R" in x for x in long))          # spaced capitals fallback


class Intro(CampaignCase):
    def test_first_session_without_a_why(self):
        code, lines = run_main(["intro"])
        self.assertEqual(code, 0, lines)
        self.assertTrue(any("Our tale begins" in x for x in lines))
        self.assertIn("[INTRO first · session 1]", lines)
        self.assertTrue(any(x.startswith("[PREMISE] Harl the miller") for x in lines))
        self.assertTrue(lines[-1].startswith("[WHY none]"))

    def test_options_fixed_and_chosen(self):
        scen = "scenarios/the-missing-miller.md"
        _edit(self.path(scen), lambda t: t.replace(
            "## The truth", "## Why you're here (player-safe)\n- Hired by the reeve.\n"
            "- On your own road,\n  and the inn is the only bed.\n\n## The truth", 1))
        self.assertEqual(run_main(["intro"])[1][-1],
                         "[WHY options] 1. Hired by the reeve. | 2. On your own road, and the inn is the only bed.")
        code, lines = run_main(["intro", "--why", "Hired by the reeve"])
        self.assertEqual(lines, ["[intro: why you're here → Hired by the reeve]"])
        self.assertEqual(run_main(["intro"])[1][-1], "[WHY chosen] Hired by the reeve")
        run_main(["intro", "--why", "Owed a favour by Mara"])            # replaced, not added
        text = self.path(scen).read_text(encoding="utf-8")
        self.assertEqual(text.count("Chosen:"), 1)
        self.assertIn("why we're here: Owed a favour by Mara", self.path("sessions/session-current.md")
                      .read_text(encoding="utf-8"))

    def test_why_section_created_and_resume(self):
        run_main(["intro", "--why", "Passing through"])
        doc = md.load(self.path("scenarios/the-missing-miller.md"))
        span = doc.section("Why you're here")
        self.assertIsNotNone(span)
        self.assertLess(doc.section("Premise")[0], span[0])
        self.assertLess(span[0], doc.section("The truth")[0])
        (self.camp / "sessions" / "history").mkdir(exist_ok=True)
        (self.camp / "sessions" / "history" / "session-01.md").write_text("# s1\n", encoding="utf-8")
        lines = run_main(["intro"])[1]
        self.assertTrue(any("Our tale continues" in x for x in lines))
        self.assertIn("[INTRO resume · session 2]", lines)


class Map(CampaignCase):
    def test_calm_room_sketch_is_big_and_saves_nothing(self):
        before = self.path("state/current.md").read_text(encoding="utf-8")
        code, lines = run_main(["space", "map", "--player-view", "--from", "Kael",
                                "--at", "Kael=@tables-w", "--at", "Kira=near Kael", "--at", "Mara=@bar N"])
        self.assertEqual(code, 0, lines)
        self.assertEqual(self.path("state/current.md").read_text(encoding="utf-8"), before)
        grid = [x for x in lines if "│" in x]
        self.assertEqual(len(grid), 16)                  # y 0-35 → 8 cells × 2 rows
        self.assertTrue(all(len(x) == len(grid[0]) for x in grid))
        self.assertTrue(any("[K]" in x for x in grid) and any("[I]" in x for x in grid))   # Kael K, Kira I
        self.assertTrue(any("bbbb" in x for x in grid))  # the bar is drawn
        self.assertFalse(any("trapdoor" in x for x in lines))
        self.assertTrue(any(x.startswith("  I Kira") and "5 ft from Kael" in x for x in lines))

    def test_area_less_location_uses_the_sites_layout(self):
        _edit(self.path("state/current.md"),
              lambda t: t.replace("party-location: crossroads-inn/common-room", "party-location: crossroads-inn"))
        code, lines = run_main(["space", "map"])
        self.assertEqual(code, 0, lines)
        self.assertTrue(any("bbbb" in x for x in lines))

    def test_bad_sketch_spec(self):
        self.assertEqual(run_main(["space", "map", "--at", "Kael"])[0], 1)


class OpeningStrike(CampaignCase):
    def test_strike_then_initiative_with_notes(self):
        run_main(["tempo", "tense", "--pos", "Kael 15,15", "--pos", "Tobin near Kael",
                  "--pos", "Kira 20,15", "--pos", "Mara @bar N"])
        code, lines = run_main(["--seed", "2", "atk", "Kael", "Tobin", "--d20", "15"])   # before initiative
        self.assertEqual(code, 0, lines)
        self.assertIn("HIT", lines[0])
        code, lines = run_main(["--seed", "4", "combat", "start", "--init", "Kael=12", "--init", "Kira=8",
                                "--surprised", "Tobin", "--surprised", "Mara", "--opener", "Kael"])
        self.assertEqual(code, 0, lines)
        self.assertTrue(lines[0].startswith("[combat start · round 1 · order: Kael 12"))
        self.assertEqual(lines[1], "[Kael struck first: their action is spent; move and bonus action as normal]")
        rows = md.load(self.path("state/current.md")).table("Combatants").rows
        tobin = next(r for r in rows if r["name"] == "Tobin")
        self.assertIn("surprised 1r", tobin["conditions"])
        self.assertNotEqual(tobin["hp"].split("/")[0], tobin["hp"].split("/")[1])   # the strike's damage carried in
        seen = [run_main(["combat", "next"])[1][:2] for _ in range(4)]
        self.assertIn("[Tobin is surprised: no move and no action this turn; no reactions until it ends]",
                      [x for pair in seen for x in pair])


class TurnBudget(CampaignCase):
    def setUp(self):
        super().setUp()
        run_main(["tempo", "tense", "--pos", "Kael 5,5", "--pos", "Tobin @tables-e",
                  "--pos", "Kira 10,5", "--pos", "Mara @bar N"])
        code, self.start_lines = run_main(["--seed", "3", "combat", "start", "--init", "Kael=25", "--init", "Kira=12"])
        self.assertEqual(code, 0, self.start_lines)

    def turn_line(self):
        return next(x for x in md.load(self.path("state/current.md")).body if x.startswith("Turn:"))

    def test_attack_and_move_keep_the_turn(self):
        self.assertIn("[Kael's turn: action · bonus action · 30 ft of movement · object interaction · "
                      "reaction (once per round)]", self.start_lines)
        code, lines = run_main(["move", "Kael", "--to", "Tobin"])
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], "[move Kael (5,5,0) → (25,5,0) · 20 ft]")
        row = next(r for r in md.load(self.path("state/current.md")).table("Combatants").rows
                   if r["name"].startswith("Kael"))
        self.assertEqual(row["pos"], "(25,5,0)")                           # the move is saved
        lines = run_main(["--seed", "5", "atk", "Kael", "Tobin", "--d20", "12"])[1]
        self.assertTrue(lines[-1].startswith("[Kael still has: bonus action · 10 ft of movement · object interaction"))
        self.assertIn("up: Kael", "\n".join(md.load(self.path("state/current.md")).body))   # still Kael's turn
        code, lines = run_main(["move", "Kael", "--to", "@door"])
        self.assertEqual(code, 1)
        self.assertIn("ft left — stop short, or --dash", lines[-1])
        self.assertEqual(run_main(["move", "Kael", "--to", "@door", "--dash"])[0], 1)   # action already spent
        run_main(["turn", "use", "bonus"])
        run_main(["turn", "use", "object"])
        run_main(["move", "Kael", "--path", "25,0,0", "20,0,0"])
        self.assertEqual(run_main(["turn"])[1], ["[Kael has used everything this turn — combat next]"])
        self.assertIn("- Kael (5,5,0) → (25,5,0) (20 ft)", md.load(self.path("state/current.md")).body)
        lines = run_main(["combat", "next"])[1]
        self.assertRegex(lines[1], r"^\[(Kira|Mara)'s turn: action")       # Tobin is down: skipped
        self.assertRegex(self.turn_line(), r"^Turn: (Kira|Mara) · action yes · attacks 0/1 ")

    def test_mid_round_end_keeps_the_moves(self):
        run_main(["move", "Kael", "--to", "Tobin"])
        run_main(["combat", "end"])
        self.assertIn("move Kael (5,5,0) → (25,5,0) (20 ft)",
                      self.path("sessions/session-current.md").read_text(encoding="utf-8"))

    def test_multiattack_counts(self):
        from lib import srd, turnstate
        self.assertEqual(turnstate.multiattack(srd.monster("bandit captain").rec), 3)
        self.assertEqual(turnstate.multiattack(srd.monster("veteran").rec), 2)
        self.assertEqual(turnstate.multiattack(srd.monster("commoner").rec), 1)

    def test_extra_attack_and_dash(self):
        _edit(self.path("pcs/kael-ashford.md"), lambda t: t.replace("## Features & abilities",
                                                                    "## Features & abilities\n- Extra Attack", 1))
        run_main(["combat", "end"])
        run_main(["tempo", "tense", "--pos", "Kael 25,5", "--pos", "Tobin @tables-e"])
        run_main(["--seed", "3", "combat", "start", "--init", "Kael=25", "--init", "Kira=12"])
        self.assertIn("attacks 0/2", self.turn_line())
        lines = run_main(["--seed", "5", "atk", "Kael", "Tobin", "--d20", "2"])[1]
        self.assertIn("1 more attack this action", lines[-1])
        run_main(["--seed", "5", "atk", "Kael", "Tobin", "--d20", "2"])
        self.assertIn("action no", self.turn_line())
        self.assertEqual(run_main(["turn", "use", "dash"])[0], 1)
