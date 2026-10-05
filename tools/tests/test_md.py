"""lib/md.py against the real POC files (plan.md Phase 1 item 6)."""
import unittest

from fixture import POC, POC_FILES, CampaignCase, md


class RoundTrip(CampaignCase):
    def test_every_poc_file_round_trips_as_is(self):
        for rel in POC_FILES:
            with self.subTest(file=rel):
                before = self.read_bytes(rel)
                md.load(self.path(rel)).save()
                self.assertEqual(self.read_bytes(rel), before)

    def test_crlf_and_lf_forms_both_round_trip(self):
        for rel in POC_FILES:
            for make, nl in ((self.write_lf_copy, b"\r\n"), (self.write_crlf_copy, b"\n")):
                p = make(rel)
                with self.subTest(file=rel, form=p.suffixes[0]):
                    before = p.read_bytes()
                    self.assertNotIn(nl, before.replace(b"\r\n", b"") if nl == b"\n" else before)
                    doc = md.load(p)
                    doc.save()
                    self.assertEqual(p.read_bytes(), before)

    def test_newline_detection(self):
        self.assertEqual(md.load(self.path("state/current.md")).newline, "\r\n")
        self.assertEqual(md.load(self.path("state/table-rules.md")).newline, "\n")
        self.assertEqual(md.load(self.write_lf_copy("state/current.md")).newline, "\n")

    def test_save_is_atomic_leaves_no_tmp(self):
        doc = md.load(self.path("npcs/veskar.md"))
        doc.set_front("status", "dead")
        doc.save()
        self.assertFalse(self.path("npcs/veskar.md.tmp").exists())
        self.assertEqual(md.load(self.path("npcs/veskar.md")).front["status"], "dead")

    def test_real_poc_files_untouched(self):
        # the fixture never writes to the repo's poc/
        for rel in POC_FILES:
            self.assertEqual((POC / rel).read_bytes(), self.read_bytes(rel))


class Frontmatter(CampaignCase):
    def test_values_parsed_per_contract(self):
        k = md.load(self.path("pcs/kael-ashford.md")).front
        self.assertEqual(k["name"], "Kael Ashford")
        self.assertEqual(k["level"], 3)
        self.assertEqual(k["hp"], {"current": 30, "max": 30})
        self.assertEqual(k["saves"], ["wis", "cha"])
        self.assertEqual(k["conditions"], [])
        self.assertEqual(k["overrides"], {})
        self.assertIsNone(k["level-pending"])
        self.assertIs(k["present"], True)
        self.assertEqual(k["hit-dice"], {"die": "d8", "left": 3})
        self.assertEqual(list(k)[:4], ["name", "player", "location", "race"])
        s = md.load(self.path("state/current.md")).front
        self.assertEqual(s["in-game-datetime"], "Day 1 18:30")  # quoted → unquoted
        self.assertIs(s["in-session"], False)
        self.assertEqual(s["scene"], "Common room, dinner rush")

    def test_comments_kept_separately(self):
        doc = md.load(self.path("state/current.md"))
        self.assertEqual(doc.front_comments["light"], "# bright | dim | dark")
        self.assertNotIn("campaign", doc.front_comments)

    def test_set_front_keeps_comment_position_and_quotes(self):
        doc = md.load(self.path("state/current.md"))
        before = doc.head[:]
        doc.set_front("light", "dim")
        doc.set_front("in-session", True)
        doc.set_front("in-game-datetime", "Day 2 00:10")
        self.assertEqual(doc.head[5], "light: dim                     # bright | dim | dark")
        self.assertEqual(doc.head[6], "in-session: true                 # /gm sets true (turns on the brief hook)")
        self.assertEqual(doc.head[2], 'in-game-datetime: "Day 2 00:10"   # dusk arrival; absolute day + 24 h clock')
        for i in (0, 1, 3, 4, 7, 8):
            self.assertEqual(doc.head[i], before[i])
        doc.save()
        again = md.load(self.path("state/current.md"))
        self.assertEqual(again.front["light"], "dim")
        self.assertIs(again.front["in-session"], True)
        self.assertEqual(again.front_comments["light"], "# bright | dim | dark")
        self.assertEqual(again.body, doc.body)

    def test_set_front_dict_list_none_and_new_key(self):
        doc = md.load(self.path("pcs/kael-ashford.md"))
        doc.set_front("hp", {"current": 22, "max": 30})
        doc.set_front("conditions", ["poisoned (10m)"])
        doc.set_front("level-pending", 4)
        doc.set_front("xp", None)
        self.assertEqual(doc.head[9], "hp: {current: 22, max: 30}   # max HP per level (house rule)")
        self.assertEqual(doc.head[14], "conditions: [poisoned (10m)]")
        self.assertEqual(doc.head[24], "level-pending: 4")
        self.assertEqual(doc.head[-2], "xp:")
        self.assertEqual(doc.head[-1], "---")
        doc.save()
        again = md.load(self.path("pcs/kael-ashford.md"))
        self.assertEqual(again.front["hp"], {"current": 22, "max": 30})
        self.assertEqual(again.front["conditions"], ["poisoned (10m)"])
        self.assertIsNone(again.front["xp"])
        self.assertEqual(list(again.front)[-1], "xp")

    def test_file_without_frontmatter(self):
        doc = md.load(self.path("state/table-rules.md"))
        self.assertEqual(doc.front, {})
        self.assertEqual(doc.head, [])
        self.assertEqual(doc.body[0], "# Table rules")


class Sections(CampaignCase):
    def test_section_prefix_match(self):
        doc = md.load(self.path("state/current.md"))
        start, end = doc.section("Tempo")
        self.assertTrue(doc.body[start].startswith("## Tempo: calm"))
        self.assertEqual(doc.body[end], "## Combat")
        self.assertEqual(doc.section("## On stage"), (7, 12))
        self.assertIsNone(doc.section("Nope"))

    def test_subsection_ends_at_next_heading(self):
        doc = md.load(self.path("locations/crossroads-inn.md"))
        start, end = doc.section("### common-room")
        self.assertEqual(doc.body[start], "### common-room")
        self.assertEqual(doc.body[end], "## Notes / current state")
        start, end = doc.section("Layout")
        self.assertEqual(doc.body[end], "## Notes / current state")

    def test_append_line(self):
        doc = md.load(self.path("pcs/kael-ashford.md"))
        i = doc.append_line("Journal", "- Day 1: met Tobin")
        self.assertEqual(doc.body[i - 1], "(GM appends durable developments here)")
        self.assertEqual(doc.body[i], "- Day 1: met Tobin")
        doc.append_line("History", "- first line")  # missing section → created at the end
        self.assertEqual(doc.body[-2:], ["## History", "- first line"])
        doc.save()
        self.assertEqual(md.load(self.path("pcs/kael-ashford.md")).body, doc.body)


class Tables(CampaignCase):
    def test_table_read_by_header_name(self):
        t = md.load(self.path("pcs/kael-ashford.md")).table("Attacks")
        self.assertEqual(t.header, ["name", "hit", "damage", "range", "notes"])
        self.assertEqual(len(t), 4)
        self.assertEqual(t.rows[1]["hit"], "DC 13 DEX")
        self.assertEqual(t.rows[3]["name"], "spiritual weapon")
        places = md.load(self.path("locations/thornbury.md")).table("Places")
        self.assertEqual(places.rows[2]["at"], "")
        self.assertEqual(places.rows[5]["ref"], "old-mill")
        self.assertEqual(places.find("id", "MILL"), 5)
        self.assertIsNone(md.load(self.path("state/current.md")).table("Combat"))
        self.assertIsNone(md.load(self.path("state/current.md")).table("On stage"))

    def test_set_keeps_column_widths(self):
        doc = md.load(self.path("pcs/kael-ashford.md"))
        t = doc.table("Resources")
        header = doc.body[t.start]
        t.set(0, "current", 3)
        line = doc.body[t.start + 2]
        self.assertEqual(line, "| spell slot 1      | 3       | 4   | long     |")
        self.assertEqual(len(line), len(header))
        self.assertEqual([len(c) for c in line.strip("|").split("|")], t.widths)
        t.set(1, "current", "a value far wider than the column")  # pad, never truncate
        self.assertIn("| a value far wider than the column |", doc.body[t.start + 3])
        doc.save()
        again = md.load(self.path("pcs/kael-ashford.md")).table("Resources")
        self.assertEqual(again.rows[0]["current"], "3")
        self.assertEqual(again.rows[1]["current"], "a value far wider than the column")

    def test_append_and_remove(self):
        doc = md.load(self.path("state/table-rules.md"))
        t = doc.table("Table rules")
        self.assertEqual(t.rows, [])
        t.append({"id": "R1", "rule": "Potions are a bonus action", "key": "potion=bonus",
                  "scope": "campaign", "since": "S1 t3", "status": "active"})
        self.assertEqual(doc.body[t.start + 2],
                         "| R1 | Potions are a bonus action | potion=bonus | campaign | S1 t3 | active |")
        t.append({"id": "R2", "rule": "x"})
        self.assertEqual(doc.body[t.start + 3], "| R2 | x    |     |       |       |        |")
        with self.assertRaises(KeyError):
            t.append({"nope": 1})
        removed = t.remove(0)
        self.assertEqual(removed["id"], "R1")
        self.assertEqual(doc.body[t.start + 2], "| R2 | x    |     |       |       |        |")
        self.assertEqual(len(doc.body), t.start + 3)
        doc.save()
        again = md.load(self.path("state/table-rules.md"))
        self.assertEqual(again.table("Table rules").rows[0]["id"], "R2")
        self.assertEqual(again.newline, "\n")

    def test_edit_touches_only_the_row(self):
        doc = md.load(self.path("locations/crossroads-inn.md"))
        before = doc.body[:]
        t = doc.table("Routes")
        t.set(3, "access", "open")
        changed = [i for i, (a, b) in enumerate(zip(before, doc.body)) if a != b]
        self.assertEqual(changed, [t.start + 2 + 3])
        self.assertEqual(len(doc.body[t.start + 5]), len(before[t.start + 5]))


class Points(unittest.TestCase):
    def test_parse_point(self):
        self.assertEqual(md.parse_point("(15,25,0)"), (15.0, 25.0, 0.0))
        self.assertEqual(md.parse_point("10,5"), (10.0, 5.0, 0.0))
        self.assertEqual(md.parse_point("(-0.1,-0.1,0)"), (-0.1, -0.1, 0.0))
        with self.assertRaises(ValueError):
            md.parse_point("x")


if __name__ == "__main__":
    unittest.main()
