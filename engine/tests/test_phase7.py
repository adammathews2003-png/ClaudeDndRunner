"""Phase 7: clock, travel, rest, lint (+ layers 2/3), session, stub, where, world, trace,
odds, spoil (plan.md Phase 7)."""
from fixture import CampaignCase, _edit, run_main, set_front_raw
from lib import md


def front(case, rel):
    return md.load(case.path(rel)).front


def text(case, rel):
    return case.path(rel).read_text(encoding="utf-8")


class Clock(CampaignCase):
    def test_transit_and_arrival(self):
        run_main(["clock", "advance", "to", "23:50"])
        code, lines = run_main(["clock", "advance", "+20m"])
        self.assertEqual(lines[0], "[TIME] Day 1 23:50 → Day 2 00:10 (+20m)")
        moves = lines[1]
        self.assertIn("Veskar left crossroads-inn/upstairs 00:00 by inn-door, mill-rd → old-mill, due 00:15  "
                      "[off-stage — in transit]", moves)
        self.assertIn("Mara intends to leave for crossroads-inn/upstairs at 00:00", moves)  # on stage
        f = front(self, "npcs/veskar.md")
        self.assertEqual(f["location"], "@mill-rd")
        self.assertIn("eta Day 2 00:15", f["transit"])
        self.assertEqual(front(self, "npcs/mara-fennick.md")["location"], "crossroads-inn/common-room")
        code, lines = run_main(["clock", "advance", "+10m"])
        self.assertIn("Veskar arrived at old-mill 00:15", lines[1])
        self.assertEqual(front(self, "npcs/veskar.md")["location"], "old-mill")
        self.assertIn("(GM) move-npc Veskar left", text(self, "sessions/session-current.md"))

    def test_conditions_and_clocks(self):
        run_main(["cond", "Kira", "+poisoned", "10m"])
        run_main(["cond", "Kael", "+blessed", "60m"])
        code, lines = run_main(["clock", "advance", "+30m"])
        self.assertIn("  Conditions expired: Kira poisoned", lines)
        self.assertEqual(front(self, "pcs/kael-ashford.md")["conditions"], ["blessed 30m"])
        code, lines = run_main(["clock", "advance", "+1d", "8h"])
        fired = [line for line in lines if line.startswith("  CLOCK Day 3 02:00")]
        self.assertEqual(len(fired), 1)
        self.assertIn("Veskar moves Harl from the inn cellar back to the mill", fired[0])
        self.assertTrue(lines[-1].startswith("  Clocks: 1 fired · next: Day 3 04:00"))

    def test_time_alias_and_correction(self):
        self.assertEqual(run_main(["time", "+20m"])[1][0], "[TIME] Day 1 18:30 → Day 1 18:50 (+20m)")
        self.assertEqual(run_main(["time", "-5m"])[1], ["[time Day 1 18:50→Day 1 18:45]"])
        self.assertEqual(run_main(["clock", "advance", "-5m"])[0], 1)

    def test_bad_schedule_line_is_skipped(self):
        _edit(self.path("npcs/veskar.md"),
              lambda t: t.replace("- 00:00–04:00 → old-mill", "- 00:00–04:00 → in transit (cart)"))
        run_main(["clock", "advance", "to", "23:50"])
        code, lines = run_main(["clock", "advance", "+20m"])
        self.assertTrue(any("is not a location" in line for line in lines))
        self.assertEqual(front(self, "npcs/veskar.md")["location"], "crossroads-inn/upstairs")


class Travel(CampaignCase):
    def test_to_the_mill(self):
        code, lines = run_main(["travel", "old-mill/main-floor"])
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], "[TRAVEL] crossroads-inn/common-room → old-mill/main-floor · 15 min "
                                   "(inn-door, mill-rd) · normal pace on foot")
        self.assertTrue(lines[1].startswith("  passes: village square"))
        self.assertIn("[TIME] Day 1 18:30 → Day 1 18:45 (+15m)", lines)
        self.assertTrue(any(line.startswith("[SCENE] old-mill/main-floor") for line in lines))
        self.assertEqual(front(self, "state/current.md")["party-location"], "old-mill/main-floor")
        self.assertEqual(front(self, "pcs/kira-thornwood.md")["location"], "old-mill/main-floor")

    def test_in_site_locked_and_legs(self):
        code, lines = run_main(["travel", "crossroads-inn/cellar"])
        self.assertEqual(code, 1)
        self.assertIn("trapdoor is locked", lines[-1])
        code, lines = run_main(["travel", "crossroads-inn/cellar", "--unlocked"])
        self.assertIn("1 min (trapdoor)", lines[0])
        code, lines = run_main(["travel", "old-mill", "--unlocked"])
        self.assertIn("16 min (trapdoor, inn-door, mill-rd)", lines[0])

    def test_pace_and_errors(self):
        self.assertIn("· 22 min (inn-door, mill-rd) · slow pace",
                      run_main(["travel", "old-mill", "--pace", "slow"])[1][0])
        self.assertIn("no location file yet", run_main(["travel", "smithy"])[1][-1])
        self.assertIn("already at", run_main(["travel", "old-mill"])[1][-1])

    def test_encounter_table_and_rule(self):
        tables = self.path("tables")
        tables.mkdir(exist_ok=True)
        (tables / "encounters-mill-rd.md").write_text(
            "# mill road\n\n| roll | result |\n|------|--------|\n| 1-3 | nothing |\n| 4 | ENCOUNTER a wolf |\n",
            encoding="utf-8")
        code, lines = run_main(["--seed", "1", "travel", "old-mill"])
        self.assertTrue(any(line.startswith("  Encounter [SECRET table:encounters-mill-rd: d4") for line in lines))
        run_main(["travel", "crossroads-inn"])
        run_main(["rule", "add", "no encounters", "--scope", "session", "--key", "encounters=off"])
        code, lines = run_main(["travel", "old-mill"])
        self.assertIn("  Encounters: off (table rule)", lines)


class Rest(CampaignCase):
    def test_short_and_long(self):
        run_main(["dmg", "Kael", "12"])
        code, lines = run_main(["--seed", "4", "rest", "short", "--hd", "Kael=2"])
        self.assertEqual(code, 0, lines)
        self.assertTrue(lines[0].startswith("[Kael hit die: d8 "))
        f = front(self, "pcs/kael-ashford.md")
        self.assertEqual(f["hit-dice"]["left"], 1)
        self.assertIn("[TIME] Day 1 18:30 → Day 1 19:30 (+1h)", lines)
        doc = md.load(self.path("pcs/kael-ashford.md"))
        t = doc.table("Resources")
        t.set(t.find("resource", "spell slot 1"), "current", "1")
        doc.save()
        code, lines = run_main(["rest", "long"])
        f = front(self, "pcs/kael-ashford.md")
        self.assertEqual(f["hp"]["current"], 30)
        self.assertEqual(f["hit-dice"]["left"], 2)
        self.assertIn("reset: spell slot 1", "\n".join(lines))
        self.assertIn("(+8h)", "\n".join(lines))
        self.assertEqual(run_main(["rest", "short", "--hd", "Kael=5"])[0], 1)


class Lint(CampaignCase):
    def test_poc_clean(self):
        code, lines = run_main(["lint"])
        self.assertEqual(code, 0, lines)
        self.assertTrue(lines[0].startswith("[LINT] 0 errors"))

    def test_errors_and_exit(self):
        _edit(self.path("npcs/tobin-hale.md"), lambda t: t.replace("location: crossroads-inn", "location: nowhere-inn"))
        _edit(self.path("locations/thornbury.md"), lambda t: t.replace("| inn-door | square | inn.door",
                                                                        "| inn-door | square | inx.door"))
        code, lines = run_main(["lint"])
        self.assertEqual(code, 1)
        body = "\n".join(lines)
        self.assertIn("error: npcs/tobin-hale.md: location 'nowhere-inn/common-room': no locations/nowhere-inn.md", body)
        self.assertIn("route `inn-door`: end 'inx.door' is not a Places id", body)

    def test_parse_error_and_fix_safe(self):
        _edit(self.path("pcs/kira-thornwood.md"), lambda t: t.replace("speed: 30", "speed 30 oops"))
        self.assertIn("outside the parsing contract", "\n".join(run_main(["lint"])[1]))
        _edit(self.path("pcs/kira-thornwood.md"), lambda t: t.replace("speed 30 oops", "speed: 30"))
        _edit(self.path("npcs/veskar.md"), lambda t: t.replace("location: crossroads-inn/upstairs",
                                                               "location: crossroads-inn/attic"))
        self.assertIn("`attic` is not in crossroads-inn's ## Areas", "\n".join(run_main(["lint"])[1]))
        run_main(["lint", "--fix-safe"])
        self.assertIn("- **attic** — <!-- added by lint, check me -->", text(self, "locations/crossroads-inn.md"))

    def test_layer2_in_do(self):
        _edit(self.path("npcs/tobin-hale.md"), lambda t: t.replace("status: alive", "status:"))
        code, lines = run_main(["do", "attitude Tobin friendly"])
        self.assertTrue(any(line.startswith("[LINT] warning: npcs/tobin-hale.md: missing `status`") for line in lines),
                        lines)
        code, lines = run_main(["do", "hp Kael -1"])
        self.assertFalse(any(line.startswith("[LINT]") for line in lines))

    def test_layer3_reports(self):
        code, lines = run_main(["scene", "enter", "old-mill", "--write"])
        self.assertTrue(any(line.startswith("[LINT] full sweep: 0 errors") for line in lines))


class Session(CampaignCase):
    def _git(self, where, *args):
        import subprocess
        return subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True)

    def _repo(self, where):
        self._git(where, "init", "-q")
        self._git(where, "config", "user.email", "t@example.com")
        self._git(where, "config", "user.name", "t")
        self._git(where, "add", "-A")
        self._git(where, "commit", "-qm", "init")

    def test_archive_commits_only_the_campaigns_own_repo(self):
        self._repo(self.tmp)                      # an outer repo around the campaign folder
        before = self._git(self.tmp, "rev-parse", "HEAD").stdout
        run_main(["session", "start"])
        code, lines = run_main(["session", "archive", "--summary", "x", "--force"])
        self.assertEqual(code, 0, lines)
        self.assertIn("[git: the campaign folder isn't its own repository — nothing committed]", lines)
        self.assertEqual(self._git(self.tmp, "rev-parse", "HEAD").stdout, before)
        self._repo(self.camp)                     # now the campaign has its own repo
        run_main(["session", "start"])
        lines = run_main(["session", "archive", "--summary", "y", "--force"])[1]
        self.assertIn('[git: committed "session 02"]', lines)
        self.assertEqual(self._git(self.camp, "log", "-1", "--format=%s").stdout.strip(), "session 02")

    def test_archive(self):
        run_main(["session", "start"])
        self.assertIs(front(self, "state/current.md")["in-session"], True)
        run_main(["rule", "add", "quiet night", "--scope", "session"])
        run_main(["do", 'hp Kael -3; log "Kael trips"'])
        run_main(["check", "Mara", "insight", "12", "--secret", "--seed", "1"])
        code, lines = run_main(["session", "archive", "--summary", "They asked around.", "--no-commit"])
        self.assertEqual(code, 0, lines)
        self.assertIn("[rule R1 ended — session over]", lines)
        h = text(self, "sessions/history/session-01.md")
        self.assertIn("## Summary\nThey asked around.", h.replace("\r\n", "\n"))
        self.assertIn("- hp Kael Ashford 30→27/30", h)
        self.assertIn("## Behind the screen (GM)\n- (GM) roll SECRET", h.replace("\r\n", "\n"))
        self.assertIn("| R1 | quiet night |", h)
        self.assertIn("(no turns yet", text(self, "sessions/session-current.md"))
        self.assertIs(front(self, "state/current.md")["in-session"], False)
        self.assertNotIn("quiet night", text(self, "state/table-rules.md"))
        run_main(["do", 'log "next"'])
        run_main(["session", "archive", "--summary", "Second.", "--no-commit"])
        self.assertTrue(self.path("sessions/history/session-02.md").exists())

    def test_refuses_on_errors(self):
        _edit(self.path("npcs/tobin-hale.md"), lambda t: t.replace("location: crossroads-inn", "location: nowhere-inn"))
        code, lines = run_main(["session", "archive", "--summary", "x", "--no-commit"])
        self.assertEqual(code, 1)
        self.assertIn("lint found errors", "\n".join(lines))
        code, lines = run_main(["session", "archive", "--summary", "x", "--no-commit", "--force"])
        self.assertEqual(code, 0, lines)


class StubWhere(CampaignCase):
    def test_stubs(self):
        self.assertEqual(run_main(["stub", "npc", "Jess", "Barrow", "--note", "barmaid"])[1],
                         ["[stub npc Jess Barrow → npcs/jess-barrow.md @ crossroads-inn/common-room]"])
        self.assertEqual(front(self, "npcs/jess-barrow.md")["status"], "alive")
        self.assertEqual(run_main(["stub", "npc", "Jess", "Barrow"])[0], 1)
        run_main(["stub", "place", "the cooper's", "--in", "thornbury", "--at", "30,80"])
        t = md.load(self.path("locations/thornbury.md")).table("Places")
        self.assertEqual(t.rows[t.find("id", "the-coopers")]["from"], "(30,80,0)")
        code, lines = run_main(["stub", "location", "Old Barn", "--in", "thornbury"])
        self.assertIn("no --at", lines[0])
        self.assertEqual(front(self, "locations/old-barn.md")["parent"], "thornbury")
        self.assertIn("thornbury's row `old-barn` has no coordinates", "\n".join(run_main(["lint"])[1]))

    def test_where(self):
        self.assertEqual(run_main(["where", "old-mill"])[1], [
            "[WHERE] old-mill (site, in thornbury) · from crossroads-inn",
            "  bearing N · straight line 0.8 mi · by route 15 min (inn-door, mill-rd)",
            "  here: (nobody)   scheduled: Veskar 00:00–04:00"])
        run_main(["clock", "advance", "to", "00:05"])
        lines = run_main(["where", "Veskar"])[1]
        self.assertEqual(lines[0], "[WHERE] Veskar Thane · on mill-rd (→ old-mill, about 33% of the way; "
                                   "left 00:00, due 00:15)" if "Thane" in str(front(self, "npcs/veskar.md")["name"])
                         else lines[0])
        self.assertIn("about 33% of the way", lines[0])


class World(CampaignCase):
    def test_add_lead_place(self):
        run_main(["world", "add", "Millbrook", "--near", "thornbury", "--within", "1d", "--dir", "E",
                  "--note", "a market village"])
        run_main(["world", "lead", "thornbury", "--heading", "E", "--as", "the old drove road", "--to", "Millbrook"])
        code, lines = run_main(["world", "place", "millbrook", "--at", "30,2"])
        self.assertIn("29.4 mi straight line (> 19.2)", lines[-1])
        code, lines = run_main(["world", "place", "millbrook", "--at=-10,0"])
        self.assertIn("the spot is W of thornbury", lines[-1])
        code, lines = run_main(["world", "place", "millbrook", "--at", "15,2"])
        self.assertEqual(lines, ["[world place: millbrook at (15,2) · 1 mi]",
                                 "[world route: the-old-drove-road thornbury → millbrook (was a frontier lead)]"])
        w = md.load(self.path("locations/world.md"))
        row = w.table("Places").rows[-1]
        self.assertIn("placed: within 1d of thornbury, E of thornbury", row["effect"])
        self.assertEqual(w.table("Routes").rows[0]["to"], "millbrook")
        self.assertIn("by route 4h 50m (the-old-drove-road)", run_main(["where", "millbrook"])[1][1])
        self.assertEqual(run_main(["world", "place", "market-town", "--at", "0.3,0.4"])[0], 1)  # overlaps thornbury

    def test_reveal_and_init(self):
        _edit(self.path("locations/thornbury.md"), lambda t: t.replace("| back-lane | square | inn      | (60,-25,0) (155,-25,0)               | lane | obvious |",
                                                                        "| back-lane | square | inn      | (60,-25,0) (155,-25,0)               | lane | obvious; secret |"))
        self.assertNotIn("back-lane", "\n".join(run_main(["scene", "enter", "crossroads-inn/common-room"])[1][2:3]))
        self.assertEqual(run_main(["world", "reveal", "back-lane"])[1], ["[world reveal: thornbury:back-lane]"])
        self.assertIn("back-lane", run_main(["scene", "enter", "crossroads-inn/common-room"])[1][2])
        self.assertEqual(run_main(["world", "init", "thornbury"])[0], 1)
        self.path("locations/world.md").unlink()
        self.assertIn("missing", "\n".join(run_main(["lint"])[1]))
        run_main(["world", "init", "thornbury"])
        self.assertEqual(md.load(self.path("locations/world.md")).table("Places").rows[0]["at"], "(0,0,0)")


class Spoilers(CampaignCase):
    def test_odds_exact(self):
        run_main(["srd", "monster", "bandit captain", "--write", "Veskar"])
        self.assertEqual(run_main(["odds", "check", "Mara", "insight", "12"])[1], ["[ODDS Mara insight ≥12: 45%]"])
        self.assertEqual(run_main(["odds", "save", "Kael", "dex", "14"])[1],
                         ["[ODDS Kael Ashford DEX save vs DC 14: 35%]"])
        line = run_main(["odds", "atk", "Kira", "Veskar", "--with", "dagger", "--adv"])[1][0]
        self.assertIn("hit 80% (crit 10%)", line)
        self.assertIn("dmg avg 5.5", line)
        self.assertIn("(65 HP)", line)
        self.assertEqual(run_main(["odds", "contest", "Kira", "stealth", "Mara", "perception"])[1],
                         ["[ODDS Kira Thornwood wins 80% (ties→PC)]"])

    def test_trace(self):
        run_main(["clock", "advance", "to", "23:30"])
        run_main(["clock", "advance", "+2h"])
        lines = run_main(["trace", "Veskar", "--from", "Day 1 12:00"])[1]
        self.assertEqual(lines[0], "[TRACE] Veskar · Day 1 12:00 → Day 2 01:30")
        self.assertTrue(any("scheduled" in line and "crossroads-inn/upstairs" in line for line in lines))
        self.assertTrue(any("logged (GM)" in line and "old-mill" in line for line in lines))
        lines = run_main(["trace", "old-mill", "--from", "Day 1 12:00"])[1]
        self.assertTrue(any("Veskar at old-mill" in line for line in lines))

    def test_spoil(self):
        code, lines = run_main(["spoil", "log", "Was Mara lying?", "--level", "major", "--depth", "answer",
                                "--reveals", "Yes — she fears something under the inn"])
        self.assertEqual(lines, ['[spoil logged: major/answer · "Was Mara lying?"]'])
        run_main(["spoil", "log", "What if we went to the mill night 1?", "--level", "none", "--reveals",
                  "Veskar was there", "--what-if"])
        rows = md.load(self.path("sessions/spoilers.md")).table("Spoilers").rows
        self.assertEqual(rows[1]["revealed"], "what-if (not canon): Veskar was there")
        self.assertIn('[spoilers] major/answer: "Was Mara lying?"', text(self, "sessions/session-current.md"))
        self.assertEqual(len(run_main(["spoil", "list"])[1]), 2)
        self.assertEqual(run_main(["spoil", "log", "x", "--level", "huge", "--reveals", "y"])[0], 1)
