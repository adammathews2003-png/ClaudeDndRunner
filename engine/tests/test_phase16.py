"""Phase 16: pre-rolls (`--rolled-as`, two-die `--d20`), the how-to-play talk in `intro`,
carousing (`carouse`, `table import`, the starter table) and the critical hit die (plan.md
Phase 16 → Verify and Guards; docs/design/02 → Dice → Pre-rolls, How to play, Table
mechanics → Phase 16; 06 → Phase 16 — table extras)."""
import random
import re
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from fixture import CampaignCase, TOOLS, _edit, give_custom_veskar, run_main, set_front_raw
from lib import campaign, md, tables
from test_phase13 import COMBAT

LOG = "sessions/session-current.md"
PRE_PHASE16_CRIT = "[Kira → Veskar: d20 20+5=25 vs AC 15 — CRIT (nat 20) · 10 pierce · Veskar 65→55/65]"
CAROUSING = """---
die: d2
cost: 1d6x10gp
---
# Carousing (test table)

| roll | result | effect | tags |
|------|--------|--------|------|
| 1 | You befriend a stray goat. | item +"a goat" | animals |
| 2 | You win at dice and buy a fine hat with it. | coin +3d6; item +"a fine hat" | gambling |
"""
PASTED = """Carousing results (a table found elsewhere)
01-10 You wake up in a haystack.
11-20 You owe a dwarf money.
   He is not amused.
31-60 You sing all night.
61-00 Nothing happens.
"""


def seed_for(pred, start=0):
    """The first seed whose Random gives faces satisfying pred(rng)."""
    for s in range(start, start + 5000):
        if pred(random.Random(s)):
            return s
    raise AssertionError("no seed found")


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

    def fight(self, veskar_at="(10,5,0)"):
        _edit(self.path("state/current.md"), lambda t: t.replace(
            "## Combat\n(not in combat)", COMBAT.replace("(10,30,0)", veskar_at), 1))

    def row(self, name):
        t = md.load(self.path("state/current.md")).table("Combatants")
        return next(r for r in t.rows if r["name"].startswith(name))

    def log_lines(self):
        return [x for x in self.text(LOG).splitlines() if x.startswith("  - ")]

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


class Defaults(CampaignCase):
    def test_settings(self):
        s = campaign.SETTINGS
        self.assertEqual((s["carousing"], s["crit-die"], s["crit-die-pcs"]), ("on", "off", "dying"))


# ---------- (1) pre-rolls ----------

class PreRolls(Base):
    def test_verify_rolled_as(self):
        # Kira: Perception +5, Investigation +3 → the die was 12
        out = self.ok("check", "Kira", "investigation", "15", "--total", "17", "--rolled-as", "perception")
        self.assertEqual(out, ["[Kira Thornwood investigation (reported as perception total 17): d20 12+3=15 "
                               "vs DC 15 — SUCCESS by 0 (tie→PC)]"])
        self.assertIn("investigation (reported as perception", self.text(LOG))

    def test_rolled_as_with_a_die_save_and_contest(self):
        out = self.ok("check", "Kira", "investigation", "15", "--d20", "14", "--rolled-as", "perception")
        self.assertIn("investigation (reported as perception): d20 14+3=17", out[0])
        out = self.ok("save", "Kira", "con", "12", "--total", "9", "--rolled-as", "dex save")
        self.assertIn("CON save (reported as DEX save total 9): d20 4+2=6", out[0])   # DEX +5, CON +2
        out = self.ok("--seed", "1", "contest", "Kira", "stealth", "Mara", "perception", "--total", "20",
                      "--rolled-as", "acrobatics")
        self.assertIn("Kira Thornwood stealth d20 15+7=22 (reported as acrobatics total 20)", out[0])
        self.assertIn("--rolled-as goes with", self.fails("--seed", "1", "check", "Mara", "insight", "12",
                                                          "--rolled-as", "perception"))
        self.assertIn("unknown skill", self.fails("check", "Kira", "stealth", "12", "--total", "9",
                                                  "--rolled-as", "juggling"))

    def test_verify_one_die_with_advantage(self):
        s = seed_for(lambda r: r.randint(1, 20) < 14)
        out = self.ok("--seed", str(s), "check", "Kira", "stealth", "12", "adv", "--d20", "14")
        second = random.Random(s).randint(1, 20)
        self.assertEqual(out, [f"[Kira Thornwood stealth: d20 (14, tool {second})→14+7=21 vs DC 12 — "
                               "SUCCESS by 9 (advantage: second die rolled)]"])
        s = seed_for(lambda r: r.randint(1, 20) > 14)
        out = self.ok("--seed", str(s), "check", "Kira", "stealth", "12", "adv", "--d20", "14")
        hi = random.Random(s).randint(1, 20)
        self.assertIn(f"→{hi}+7={hi + 7}", out[0])               # keeps the higher

    def test_two_dice(self):
        out = self.ok("check", "Kira", "stealth", "12", "dis", "--d20", "14,6")
        self.assertEqual(out, ["[Kira Thornwood stealth: d20 (14, 6)→6+7=13 vs DC 12 — SUCCESS by 1]"])
        out = self.ok("check", "Kira", "stealth", "12", "--d20", "14,6")
        self.assertIn("d20 14+7=21", out[0])
        self.assertIn("second die 6 unused: no adv/dis", out[0])
        self.assertIn("1-20", self.fails("check", "Kira", "stealth", "12", "--d20", "14,26"))
        self.assertEqual(run_main(["check", "Kira", "stealth", "12", "--d20", "1,2,3"])[0], 1)

    def test_exhaustion_disadvantage_rolls_the_second_die(self):
        """The known bug: a check under exhaustion with one --d20 used just that die."""
        set_front_raw(self, "pcs/kira-thornwood.md", "exhaustion", 1)
        s = seed_for(lambda r: r.randint(1, 20) < 14)
        low = random.Random(s).randint(1, 20)
        out = self.ok("--seed", str(s), "check", "Kira", "stealth", "12", "--d20", "14")
        self.assertIn(f"d20 (14, tool {low})→{low}+7", out[0])
        self.assertIn("exhaustion 1: disadvantage", out[0])

    def test_atk_and_save_take_two_dice(self):
        self.fight()
        out = self.ok("atk", "Kira", "Veskar", "adv", "--with", "shortsword", "--d20", "3,18", "--no-apply")
        self.assertIn("d20 (3, 18)→18+5=23", out[0])
        out = self.ok("save", "Kira", "dex", "12", "dis", "--d20", "15,4")
        self.assertIn("d20 (15, 4)→4+5=9", out[0])


# ---------- (5b) how to play ----------

class HowToPlay(Base):
    def test_verify_first_session(self):
        out = self.ok("intro")
        htp = [x for x in out if x.startswith("[HOW TO PLAY]")]
        self.assertTrue(htp and out[0].startswith("[HOW TO PLAY]"))          # before the title card
        self.assertLess(out.index(htp[-1]), next(i for i, x in enumerate(out) if "Our tale begins" in x))
        self.assertTrue(any("rolled 16" in x and "Roll ahead" in x for x in htp))
        self.assertTrue(any('"Kael: I check the trapdoor."' in x for x in htp))   # a present PC's name
        self.assertLessEqual(len(htp), 7)
        self.assertIn("[intro] how to play given", self.text(LOG))
        again = self.ok("intro")                                               # same session: not repeated
        self.assertFalse(any(x.startswith("[HOW TO PLAY") for x in again))
        self.assertTrue(any("Our tale begins" in x for x in again))

    def test_gm_rolls_all_drops_roll_ahead(self):
        self.setting("dice-mode", "gm-rolls-all")
        out = self.ok("intro")
        htp = [x for x in out if x.startswith("[HOW TO PLAY]")]
        self.assertTrue(htp)
        self.assertFalse(any("rolled 16" in x or "Roll ahead" in x for x in htp))

    def test_for_a_new_player_and_on_demand(self):
        out = self.ok("intro", "--how-to-play", "--for", "Kira")
        self.assertTrue(all(x.startswith("[HOW TO PLAY for Kira]") for x in out))
        self.assertLessEqual(len(out), 3)
        self.assertTrue(any('"Kira: I search the desk, rolled 16"' in x for x in out))
        self.assertNotIn("how to play given", self.text(LOG))                 # --for doesn't count as the talk
        self.assertIn("is not a PC", self.fails("intro", "--how-to-play", "--for", "Mara"))
        out = self.ok("intro", "--how-to-play")
        self.assertTrue(out and all(x.startswith("[HOW TO PLAY]") for x in out))
        self.assertEqual(self.text(LOG).count("how to play given"), 1)
        self.ok("intro", "--how-to-play")                                      # asked again: logged once
        self.assertEqual(self.text(LOG).count("how to play given"), 1)

    def test_later_sessions_and_tell_the_table(self):
        self.setting("carousing", "on")
        self.setting("crit-die", "on")
        out = self.ok("intro")
        self.assertFalse(any("carousing" in x for x in out))           # offered in the fiction instead
        self.assertTrue(any(x.startswith("[TELL THE TABLE] crit die on") for x in out))
        (self.camp / "sessions" / "history").mkdir(exist_ok=True)
        (self.camp / "sessions" / "history" / "session-01.md").write_text("# s1\n", encoding="utf-8")
        _edit(self.path(LOG), lambda t: t.replace("[intro] how to play given", "x"))
        out = self.ok("intro")
        self.assertFalse(any(x.startswith(("[HOW TO PLAY", "[TELL THE TABLE]")) for x in out))

    def test_discord_line_and_undo(self):
        self.path("discord.md").write_text("---\ndiscord: queue\n---\n", encoding="utf-8")
        out = self.assert_undoes("intro")
        self.assertTrue(any("On Discord it's the same" in x for x in out))


# ---------- (3)+(4) tables and table import ----------

class TableImport(Base):
    def paste(self, text):
        p = self.tmp / "pasted.txt"
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_verify_gap_reported(self):
        out = self.assert_undoes("table", "import", self.paste(PASTED), "--as", "carousing")
        self.assertIn("gaps: 21-30", out[0])
        self.assertIn("overlaps: none", out[0])
        self.assertIn("d100", out[0])
        self.assertIn("1 wrapped line(s) joined", out[0])
        self.ok("table", "import", self.paste(PASTED), "--as", "carousing")
        t = tables.load("carousing", fallback=False)
        self.assertEqual(t.die, 100)
        self.assertEqual(t.front.get("cost"), "1d6x10gp")
        self.assertEqual([r.roll for r in t.rows], ["1-10", "11-20", "31-60", "61-100"])
        self.assertEqual(t.rows[1].result, "You owe a dwarf money. He is not amused.")
        self.assertEqual([r.effect for r in t.rows], ["", "", "", ""])     # codes are never guessed
        self.assertIn("table import carousing", self.text(LOG))
        self.assertTrue(all("(GM) table import" in x for x in self.log_lines() if "table import" in x))

    def test_overlap_numbered_list_and_die(self):
        out = self.ok("table", "import", self.paste("1. a\n2. b\n2. c\n4) d\n"), "--as", "odd-things", "--die", "d6")
        self.assertIn("gaps: 3, 5-6", out[0])
        self.assertIn("overlaps: 2", out[0])
        self.assertTrue(self.path("tables/odd-things.md").exists())
        self.assertIn("no numbered lines", self.fails("table", "import", self.paste("nothing here\n"), "--as", "x"))

    def test_codes_and_boundaries(self):
        self.assertEqual(tables.codes('coin -2d6x10; item +"a; b"; clock +3d "x"'),
                         ['coin -2d6x10', 'item +"a; b"', 'clock +3d "x"'])
        self.assertTrue(tables.matches(["animals"], "harm to animals"))
        self.assertTrue(tables.matches(["spider"], "spiders"))
        self.assertFalse(tables.matches(["gambling", "drink"], "harm to children"))


# ---------- (6) carousing ----------

class Carousing(Base):
    def setUp(self):
        super().setUp()
        self.setting("carousing", "on")
        (self.camp / "tables").mkdir(exist_ok=True)
        self.path("tables/carousing.md").write_text(CAROUSING, encoding="utf-8")
        set_front_raw(self, "state/current.md", "lines", ["harm to animals"])

    def seed(self):
        # cost d6 (Kira), row d2 = 1 (the goat: re-rolled), d2 = 2, 3d6, then Kael's cost and row
        return seed_for(lambda r: r.randint(1, 6) and r.randint(1, 2) == 1)

    def test_verify(self):
        s = self.seed()
        before_kira = self.front("pcs/kira-thornwood.md")
        out = self.ok("--seed", str(s), "carouse", "Kira,Kael")
        self.assertTrue(out[0].startswith("[CAROUSE — GM only"))
        cost = [x for x in out if "the night costs" in x]
        self.assertEqual(len(cost), 2)                                         # charged per PC
        self.assertTrue(any(x.startswith("[coin Kira Thornwood 35→") for x in out))
        self.assertTrue(any("re-rolled 1 (line: harm to animals)" in x for x in out))
        self.assertFalse(any("a goat" in x for x in out if x.startswith("[item")))
        kira = self.text("pcs/kira-thornwood.md")
        self.assertIn("a fine hat", kira)                                     # the item code
        m = re.search(r"\[carouse Kira: coin \+3d6: \((\d+),(\d+),(\d+)\) = (\d+) gp\]", "\n".join(out))
        self.assertIsNotNone(m, out)                                          # the coin code
        paid = int(re.search(r"costs 1d6×10: \((\d)\)×10", cost[0]).group(1)) * 10
        self.assertIn(f"Coin: {35 - paid + int(m.group(4))} gp", kira)
        self.assertEqual(before_kira["name"], "Kira Thornwood")
        rec = md.load(self.path("state/carousing.md")).table("Carousing")
        self.assertEqual([r["pc"] for r in rec.rows], ["Kira", "Kael"])
        self.assertEqual(rec.rows[0]["roll"], "2")

    def test_guard_gm_side_only(self):
        before = len(self.log_lines())
        self.ok("--seed", str(self.seed()), "carouse", "Kira,Kael")
        new = self.log_lines()[before:]
        self.assertTrue(new)
        self.assertTrue(all(x.startswith("  - (GM) ") for x in new), new)    # never in the recap
        self.assertTrue(any('[carouse] Kira 2: "You win at dice' in x for x in new))

    def test_debt_reroll_and_undo(self):
        _edit(self.path("pcs/kael-ashford.md"), lambda t: re.sub(r"- Coin:.*", "- Coin: 3 gp", t, count=1))
        out = self.assert_undoes("--seed", str(self.seed()), "carouse", "Kael")
        self.assertTrue(any("couldn't pay" in x and "owes" in x for x in out))
        self.ok("--seed", str(self.seed()), "carouse", "Kael")
        clocks = self.text("state/current.md")
        self.assertIn("Kael owes", clocks)
        self.assertIn("a fine hat", self.text("pcs/kael-ashford.md"))
        # the re-roll takes back the row's effects (the hat, the winnings), never the cost
        _edit(self.path("tables/carousing.md"), lambda t: t.replace(
            '| 1 | You befriend a stray goat. | item +"a goat" | animals |',
            '| 1 | You lose a boot. | item -random | |'))
        out = self.assert_undoes("--seed", "3", "carouse", "--reroll", "Kael")
        out = self.ok("--seed", "3", "carouse", "--reroll", "Kael")
        self.assertNotIn("a fine hat", self.text("pcs/kael-ashford.md"))
        self.assertTrue(any("d2 1 → You lose a boot." in x for x in out))
        self.assertTrue(any(x.startswith("[item Kael Ashford -") for x in out))
        self.assertIn("Kael owes", self.text("state/current.md"))               # the debt stays
        self.assertIn("- Coin: 0 gp", self.text("pcs/kael-ashford.md"))       # the winnings went back
        self.assertTrue(any("(GM) [carouse] Kael re-rolled 2 → 1" in x for x in self.log_lines()))

    def test_veil_clock_and_off(self):
        _edit(self.path("tables/carousing.md"), lambda t: t.replace(
            '| 2 | You win at dice and buy a fine hat with it. | coin +3d6; item +"a fine hat" | gambling |',
            '| 2 | You wake up engaged. | clock +7d "the wedding"; no-rest; stub npc "the betrothed" | romance |'))
        set_front_raw(self, "state/current.md", "veils", ["romance"])
        out = self.ok("--seed", str(self.seed()), "carouse", "Kira")
        self.assertTrue(any("(veil: off screen (romance))" in x or "veil: off screen" in x for x in out))
        self.assertIn("- Day 8 18:30: the wedding (carousing: Kira)", self.text("state/current.md"))
        self.assertTrue(any("doesn't count as a long rest" in x for x in out))
        self.assertTrue(any(x == '[file for Kira: stub npc "the betrothed"]' for x in out))
        self.setting("carousing", "off")
        self.assertIn("carousing: off", self.fails("carouse", "Kira"))
        self.setting("carousing", "on")
        self.assertIn("is not a PC", self.fails("carouse", "Mara"))

    def test_offer_once_per_tavern(self):
        self.assert_undoes("carouse", "--offer")
        out = self.ok("carouse", "--offer")
        self.assertTrue(out[0].startswith("[carousing: first time at crossroads-inn"), out)
        self.assertTrue(self.ok("carouse", "--offer")[0].startswith("[carousing: already offered at crossroads-inn"))
        self.assertEqual(md.load(self.path("state/carousing.md")).front["offered"], ["crossroads-inn"])
        self.assertTrue(any(x.startswith("  - (GM) [carouse] offered at crossroads-inn") for x in self.log_lines()))
        self.setting("carousing", "off")
        self.assertIn("carousing: off", self.fails("carouse", "--offer"))

    def test_starter_table_fallback(self):
        self.path("tables/carousing.md").unlink()
        set_front_raw(self, "state/current.md", "lines", [])
        out = self.ok("--seed", "11", "carouse", "Kira")
        self.assertTrue(any(re.match(r"\[carouse Kira: d100 \d+ · d4 \d → ", x) for x in out))


class StarterTables(CampaignCase):
    def test_original_and_well_formed(self):
        car = tables.load("carousing")
        self.assertEqual(Path(car.path).parent, tables.TEMPLATES)
        self.assertEqual(car.die, 100)
        self.assertEqual(car.front.get("cost"), "1d6x10gp")
        self.assertGreaterEqual(len(car.rows), 200)
        # the combined table: every number has four slotted rows (one per source); 100 is `twice`
        self.assertEqual([n for n in range(1, 100) if [r.slot for r in car.slots(n)] != [1, 2, 3, 4]], [])
        self.assertEqual(car.row_for(100).effect, "twice")
        crit = tables.load("crit-die")
        self.assertEqual((crit.die, len(crit.rows)), (10, 10))
        self.assertEqual([r.effect for r in crit.rows],
                         ["dice x2", "dice x2", "dice x2", "max+dice", "dice x3", "dice x2; disarm",
                          "dice x2; prone", "dice x2; stunned 1t", "dice x2; bleed 1d4", "kill"])
        self.assertIn("original text", Path(crit.path).read_text(encoding="utf-8"))
        self.assertIn("Original to this engine", Path(car.path).read_text(encoding="utf-8"))

    def test_guard_third_party_tables_are_credited(self):
        """A shipped table is the engine's own text or credits its sources (decided 2026-10-07);
        `table import` writes into the campaign, never the engine."""
        names = sorted(p.name for p in (TOOLS / "templates" / "tables").glob("*.md"))
        self.assertEqual(names, ["carousing.md", "chase-urban.md", "chase-wild.md", "crit-die.md"])
        for n in names:
            head = (TOOLS / "templates" / "tables" / n).read_text(encoding="utf-8")[:2000]
            self.assertTrue("Engine" in head or "## Credits" in head, n)
        src = self.tmp / "p.txt"
        src.write_text("1-50 a\n51-100 b\n", encoding="utf-8")
        before = {p.name: p.read_bytes() for p in (TOOLS / "templates" / "tables").glob("*.md")}
        self.assertEqual(run_main(["table", "import", str(src), "--as", "carousing"])[0], 0)
        self.assertTrue((self.camp / "tables" / "carousing.md").exists())
        self.assertEqual({p.name: p.read_bytes() for p in (TOOLS / "templates" / "tables").glob("*.md")}, before)

    def test_campaign_new_copies_them(self):
        tmp = Path(tempfile.mkdtemp(prefix="gm-camp-"))
        try:
            with mock.patch.object(campaign, "CAMPAIGNS", tmp):
                code, lines = run_main(["campaign", "new", "gull", "--area", "Gull Harbour",
                                        "--set", "crit-die=on", "carousing=on"])
                self.assertEqual(code, 0, lines)
                for n in ("carousing", "crit-die"):
                    self.assertEqual((tmp / "gull" / "tables" / f"{n}.md").read_bytes().replace(b"\r\n", b"\n"),
                                     (TOOLS / "templates" / "tables" / f"{n}.md").read_bytes().replace(b"\r\n", b"\n"))
                self.assertTrue(any("starter tables" in x for x in lines))
                f = md.load(tmp / "gull" / "campaign.md").front
                self.assertEqual((f["crit-die"], f["carousing"]), ("on", "on"))
        finally:
            campaign.set_override(str(self.camp))
            shutil.rmtree(tmp, ignore_errors=True)


# ---------- (7) the crit die ----------

class CritDie(Base):
    def setUp(self):
        super().setUp()
        self.fight()
        self.setting("crit-die", "on")

    def test_verify_disarm_at_seed(self):
        s = seed_for(lambda r: r.randint(1, 10) == 6)
        out = self.assert_undoes("--seed", str(s), "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20")
        out = self.ok("--seed", str(s), "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20")
        self.assertIn("CRIT (nat 20) · CRIT DIE d10 → 6 dice x2; disarm", out[0])
        self.assertIn("[crit die: Veskar drops scimitar at (10,5,0) (disarm)]", out)
        self.assertIn("dropped scimitar at (10,5,0)", self.row("Veskar")["notes"])
        self.assertIn("crit die: Veskar drops scimitar", self.text(LOG))
        self.assertIn("crit die dice x2", self.text(LOG))                      # the damage roll note

    def test_verify_kill_on_a_pc_is_dying_by_default(self):
        s = seed_for(lambda r: r.randint(1, 20) == 20)
        out = self.ok("--seed", str(s), "atk", "Veskar", "Kira", "--crit-die", "10")
        self.assertIn("CRIT DIE d10 → 10 kill", out[0])
        self.assertIn("slain · Kira 30→0/30", out[0])
        self.assertEqual(self.row("Kira")["hp"], "0/30")
        self.assertIn("dying", self.row("Kira")["conditions"])
        self.assertIn("death-saves", self.front("pcs/kira-thornwood.md"))

    def test_kill_dead_rule_npc_and_legendary_resistance(self):
        s = seed_for(lambda r: r.randint(1, 20) == 20)
        self.setting("crit-die-pcs", "dead")
        out = self.ok("--seed", str(s), "atk", "Veskar", "Kira", "--crit-die", "10")
        self.assertTrue(any("Kira" in x and "is dead (crit die: slain" in x for x in out), out)
        self.assertIn("dead", self.row("Kira")["conditions"])
        out = self.ok("atk", "Kael", "Veskar", "--d20", "20", "--crit-die", "10")
        self.assertIn("Veskar 65→0/65", out[0])
        self.ok("hp", "Veskar", "=65")
        _edit(self.path("npcs/veskar.md"), lambda t: t.replace(
            "## Attacks", "## Resources\n| resource | current | max | recovers |\n|---|---|---|---|\n"
            "| legendary resistance | 1 | 3 | dawn |\n\nLegendary Resistance (3/Day).\n\n## Attacks", 1))
        out = self.ok("--seed", "2", "atk", "Kael", "Veskar", "--d20", "20", "--crit-die", "10")
        self.assertIn("Legendary Resistance: kill → dice x3", out[0])
        self.assertNotIn("Veskar 65→0/65", out[0])
        self.assertTrue(any(x.startswith("[LR: Veskar spends a Legendary Resistance") for x in out))
        self.assertIn("| legendary resistance | 0", self.text("npcs/veskar.md"))
        out = self.ok("atk", "Kael", "Veskar", "--d20", "20", "--crit-die", "10")   # none left: the kill stands
        self.assertIn("slain · Veskar", out[0])

    def test_conditions_bleed_and_fallback(self):
        self.ok("--seed", "1", "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20", "--crit-die", "7")
        self.assertIn("prone", self.row("Veskar")["conditions"])
        self.ok("cond", "Veskar", "-prone")
        self.ok("--seed", "1", "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20", "--crit-die", "8")
        self.assertIn("stunned 1r", self.row("Veskar")["conditions"])         # Veskar still acts this round
        self.ok("--seed", "1", "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20", "--crit-die", "9")
        self.assertIn("bleeding 1d4", self.row("Veskar")["conditions"])
        hp = int(self.row("Veskar")["hp"].split("/")[0])
        out = self.ok("--seed", "4", "combat", "next")                       # Veskar's turn: it bleeds
        bleed = [x for x in out if x.startswith("[Veskar bleeds: 1d4")]
        self.assertTrue(bleed, out)
        self.assertLess(int(self.row("Veskar")["hp"].split("/")[0]), hp)
        out = self.ok("hp", "Veskar", "+5")
        self.assertTrue(any("cond Veskar -bleeding" in x for x in out))
        self.assertNotIn("bleeding", self.row("Veskar")["conditions"])
        # a disarm against a bite falls back to dice x2
        _edit(self.path("npcs/veskar.md"), lambda t: t.replace("| scimitar |", "| bite     |", 1))
        out = self.ok("--seed", "1", "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20", "--crit-die", "6")
        self.assertIn("Veskar has no weapon to drop: dice x2 instead", out[0])
        self.assertFalse(any("drops" in x for x in out))

    def test_damage_codes(self):
        out = self.ok("--seed", "1", "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20",
                      "--crit-die", "5", "--no-apply")
        self.assertIn("3d6+3", self.text(LOG))                                  # dice x3 of 1d6+3
        out = self.ok("--seed", "1", "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20",
                      "--crit-die", "4", "--no-apply")
        self.assertIn("+6 max", self.text(LOG))
        self.assertIn("d10", self.fails("atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20",
                                        "--crit-die", "11"))

    def test_guard_never_on_checks_or_saves(self):
        for argv in (["check", "Kira", "stealth", "12", "--d20", "20"], ["save", "Kira", "dex", "12", "--d20", "20"]):
            out = self.ok("--seed", "1", *argv)
            self.assertNotIn("CRIT", out[0])
        self.assertNotIn("CRIT DIE", self.text(LOG))
        self.assertNotIn("crit die", self.text(LOG))

    def test_guard_off_is_byte_identical(self):
        argv = ["--seed", "1", "atk", "Kira", "Veskar", "--with", "shortsword", "--d20", "20"]
        on = self.ok(*argv)
        self.assertIn("CRIT DIE", on[0])
        self.ok("undo")
        doc = md.load(self.path("state/current.md"))
        doc.del_front("crit-die")                         # the default: no key at all
        doc.save()
        default = self.ok(*argv)
        default_files = self.snapshot()
        self.assertEqual(default, [PRE_PHASE16_CRIT])     # what atk printed before Phase 16
        self.ok("undo")
        self.setting("crit-die", "off")
        off = self.ok(*argv)
        off_files = self.snapshot()
        self.assertEqual(off, default)
        norm = lambda b: b.replace(b"\r\n", b"\n").replace(b"crit-die: off\n", b"")  # noqa: E731
        for rel, data in default_files.items():
            self.assertEqual(norm(off_files[rel]), norm(data), rel)


SLOTTED = """---
die: d2
cost: 1d6x10gp
---
# Carousing (combined test table)

| roll | result | effect | tags |
|------|--------|--------|------|
| 01.1 | You wake up in a hat shop. | item +"a red hat" | |
| 01.2 | You wake up on a ship that has set sail. | item +"a blue hat" | travel, disruptive |
| 02 | Roll twice more and combine. | twice | |
"""


class _Dice:
    def __init__(self, *faces):
        self.faces = list(faces)

    def die(self, n):
        return self.faces.pop(0)


class SlottedTables(Base):
    """Combined tables: rows sharing a number carry slots (`01.2`) and a second die picks
    one; `twice` rolls two more; `disruptive` rows print a scenario fit check."""
    def setUp(self):
        super().setUp()
        self.setting("carousing", "on")
        (self.camp / "tables").mkdir(exist_ok=True)
        self.path("tables/carousing.md").write_text(SLOTTED, encoding="utf-8")

    def test_slot_roll_and_labels(self):
        t = tables.load("carousing")
        n, row = t.roll(_Dice(1, 2))
        self.assertEqual((n, row.result), ("1.2", "You wake up on a ship that has set sail."))
        n, row = t.roll(_Dice(2))
        self.assertEqual((n, row.effect), (2, "twice"))
        self.assertEqual(t.row_for_label("1.1").result, "You wake up in a hat shop.")
        self.assertIsNone(t.row_for_label("1"))                         # a shared number needs its slot
        self.path("tables/carousing.md").write_text(SLOTTED.replace("| 01.2 |", "| 01 |"), encoding="utf-8")
        with self.assertRaises(tables.TableError):
            tables.load("carousing").roll(_Dice(1))                     # unslotted overlap

    def test_fit_check_and_reroll(self):
        s = seed_for(lambda r: r.randint(1, 6) and r.randint(1, 2) == 1 and r.randint(1, 2) == 2)
        out = self.ok("--seed", str(s), "carouse", "Kira")
        self.assertTrue(any("d2 1 · d2 2 → You wake up on a ship" in x for x in out), out)
        self.assertTrue(any(x.startswith("[fit check:") and "carouse --reroll Kira" in x for x in out))
        self.assertIn("a blue hat", self.text("pcs/kira-thornwood.md"))
        self.assertEqual(md.load(self.path("state/carousing.md")).table("Carousing").rows[0]["roll"], "1.2")
        out = self.ok("--seed", "5", "carouse", "--reroll", "Kira")
        kira = self.text("pcs/kira-thornwood.md")
        self.assertNotIn("a blue hat", kira)                            # the old slot's effects are taken back
        self.assertIn("a red hat", kira)                                # the only row left (never `twice`)

    def test_twice(self):
        s = seed_for(lambda r: r.randint(1, 6) and r.randint(1, 2) == 2)
        out = self.assert_undoes("--seed", str(s), "carouse", "Kira")
        out = self.ok("--seed", str(s), "carouse", "Kira")
        self.assertEqual(len([x for x in out if x.startswith("[carouse Kira: d2 1 · d2 ")]), 2, out)
        self.assertIn("[carouse Kira: combine the two into one night]", out)
        self.assertFalse(any(x.startswith("[file for Kira: twice") for x in out))
        self.assertTrue(md.load(self.path("state/carousing.md")).table("Carousing").rows[0]["roll"].startswith("2: 1."))
