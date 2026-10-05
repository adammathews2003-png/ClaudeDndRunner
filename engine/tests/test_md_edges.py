"""Edge cases of the 04 parsing contract pinned against lib/md.py: quoted commas,
empty containers, bare keys, '#' inside quotes, Windows paths, unicode, BOM, fences,
table layout variants (plan.md Phase 1 item 6; review items 7, 10, 12, 14, 21)."""
import unittest

from fixture import CampaignCase, md

FRONT = '''---
scene: "Common room, dinner rush"   # quoted comma
tags: []
overrides: {}
level-pending:
glyph: "#"                           # hash inside quotes
note: 'single #quoted'
path: "C:\\\\tmp\\\\poc"
dash: Day 1 → Day 2 · 19:40–00:10 · Thugs ×3
nums: {a: 1, b: -2.5, c: 1e3}
mix: [x, "y, z", 3, true]
---
# Body
'''

BODY = '''# Title

## Tight
| id | v |
|----|---|
| a  | 1 |

## Two tables
| id | v |
|----|---|
| first | 1 |

| id | v |
|----|---|
| second | 2 |

## Code
```
# not a heading
## nor this
```
~~~
### fenced
~~~
## After
| id | v |
|----|---|
| after | 9 |
'''


class Frontmatter(CampaignCase):
    def doc(self, text=FRONT, name="edge.md"):
        p = self.path(name)
        p.write_text(text, encoding="utf-8", newline="")
        return md.load(p)

    def test_edge_values(self):
        f = self.doc().front
        self.assertEqual(f["scene"], "Common room, dinner rush")
        self.assertEqual(f["tags"], [])
        self.assertEqual(f["overrides"], {})
        self.assertIsNone(f["level-pending"])
        self.assertEqual(f["glyph"], "#")
        self.assertEqual(f["note"], "single #quoted")
        self.assertEqual(f["path"], "C:\\tmp\\poc")
        self.assertEqual(f["dash"], "Day 1 → Day 2 · 19:40–00:10 · Thugs ×3")
        self.assertEqual(f["nums"], {"a": 1, "b": -2.5, "c": 1000.0})
        self.assertEqual(f["mix"], ["x", "y, z", 3, True])
        d = self.doc()
        self.assertEqual(d.front_comments["glyph"], "# hash inside quotes")
        self.assertNotIn("note", d.front_comments)

    def test_round_trip_edges(self):
        d = self.doc()
        d.save()
        self.assertEqual(self.path("edge.md").read_bytes().decode("utf-8"), FRONT)

    def test_quotes_and_backslashes_survive_set_front(self):
        d = self.doc()
        d.set_front("j", 'say "hi"')
        d.set_front("win", "C:\\Users\\x")
        d.save()
        again = md.load(self.path("edge.md"))
        self.assertEqual(again.front["j"], 'say "hi"')
        self.assertEqual(again.front["win"], "C:\\Users\\x")
        again.set_front("j", again.front["j"])  # second cycle, same text
        again.save()
        self.assertEqual(md.load(self.path("edge.md")).front["j"], 'say "hi"')

    def test_value_starting_with_quote_survives_two_cycles(self):
        d = self.doc()
        d.set_front("q", '"quoted" start')
        d.save()
        once = self.path("edge.md").read_text(encoding="utf-8")
        again = md.load(self.path("edge.md"))
        self.assertEqual(again.front["q"], '"quoted" start')
        again.set_front("q", again.front["q"])
        again.save()
        self.assertEqual(self.path("edge.md").read_text(encoding="utf-8"), once)
        self.assertEqual(md.load(self.path("edge.md")).front["q"], '"quoted" start')

    def test_bom_is_kept(self):
        p = self.path("bom.md")
        p.write_bytes(b"\xef\xbb\xbf---\nname: X\n---\n# X\n")
        d = md.load(p)
        self.assertTrue(d.bom)
        self.assertEqual(d.front["name"], "X")
        self.assertEqual(d.head[0], "---")
        d.save()
        self.assertEqual(p.read_bytes(), b"\xef\xbb\xbf---\nname: X\n---\n# X\n")
        d.set_front("name", "Y")
        d.save()
        self.assertEqual(p.read_bytes(), b"\xef\xbb\xbf---\nname: Y\n---\n# X\n")


class Body(CampaignCase):
    def doc(self):
        p = self.path("body.md")
        p.write_text(BODY, encoding="utf-8", newline="")
        return md.load(p)

    def test_table_with_no_blank_line_after_heading(self):
        t = self.doc().table("Tight")
        self.assertEqual(t.rows, [{"id": "a", "v": "1"}])

    def test_two_tables_under_one_heading_first_wins(self):
        t = self.doc().table("Two tables")
        self.assertEqual([r["id"] for r in t.rows], ["first"])

    def test_fenced_hashes_are_not_headings(self):
        d = self.doc()
        self.assertEqual([t for _, _, t in d.headings()], ["Title", "Tight", "Two tables", "Code", "After"])
        self.assertIsNone(d.section("not a heading"))
        self.assertIsNone(d.section("fenced"))
        self.assertEqual(d.table("After").rows[0]["id"], "after")
        start, end = d.section("Code")
        self.assertEqual(d.body[end], "## After")

    def test_short_and_long_rows(self):
        p = self.path("rows.md")
        p.write_text("## T\n| a | b | c |\n|---|---|---|\n| 1 |\n| 1 | 2 | 3 | extra | more |\n",
                     encoding="utf-8", newline="")
        d = md.load(p)
        t = d.table("T")
        self.assertEqual(t.rows[0], {"a": "1", "b": "", "c": ""})
        self.assertEqual(t.rows[1], {"a": "1", "b": "2", "c": "3"})
        self.assertEqual(t.extras, [[], ["extra", "more"]])
        t.set(1, "b", "X")
        self.assertEqual(d.body[t.start + 3], "| 1 | X | 3 | extra | more |")
        t.set(0, "c", "Z")
        self.assertEqual(d.body[t.start + 2], "| 1 |   | Z |")
        with self.assertRaises(KeyError):
            t.set(0, "nope", 1)
        t.remove(0)
        self.assertEqual(t.extras, [["extra", "more"]])
        d.save()
        self.assertEqual(md.load(p).table("T").extras, [["extra", "more"]])


if __name__ == "__main__":
    unittest.main()
