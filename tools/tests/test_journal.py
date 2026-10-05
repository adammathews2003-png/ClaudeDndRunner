"""lib/journal.py: batches, snapshots, undo, turn blocks (plan.md Phase 1 item 6)."""
import json
import unittest

from fixture import CampaignCase, campaign, md
from lib import journal


class TurnBlocks(CampaignCase):
    def log_lines(self):
        return self.path("sessions/session-current.md").read_text(encoding="utf-8").splitlines()

    def test_first_delta_opens_turn_1_and_replaces_placeholder(self):
        self.assertEqual(journal.current_turn(), (1, False))
        n = journal.log_delta("coin Kira 35→30 gp")
        self.assertEqual(n, 1)
        lines = self.log_lines()
        self.assertNotIn("(no turns yet — campaign not started)", lines)
        self.assertEqual(lines[-2:], ["[turn 1]", "  - coin Kira 35→30 gp"])
        self.assertEqual(journal.current_turn(), (1, True))

    def test_block_shape_matches_06_156(self):
        journal.log_delta("coin Kira 35→30 gp")
        journal.log_delta("attitude Tobin neutral→friendly")
        journal.log_delta("roll SECRET 1d20+2 = 9 (Mara insight vs Kira deception 15) — fail", gm=True)
        n = journal.log_turn("Kira buys Tobin a drink; cart story told")
        self.assertEqual(n, 1)
        self.assertEqual(self.log_lines()[-4:], [
            "[turn 1] Kira buys Tobin a drink; cart story told",
            "  - coin Kira 35→30 gp",
            "  - attitude Tobin neutral→friendly",
            "  - (GM) roll SECRET 1d20+2 = 9 (Mara insight vs Kira deception 15) — fail",
        ])
        self.assertEqual(journal.current_turn(), (2, False))
        journal.log_delta("hp Kael 30→22")
        self.assertEqual(self.log_lines()[-2:], ["[turn 2]", "  - hp Kael 30→22"])

    def test_log_without_deltas_writes_closed_block(self):
        journal.log_turn("nothing happened")
        journal.log_turn("still nothing")
        self.assertEqual(self.log_lines()[-2:], ["[turn 1] nothing happened", "[turn 2] still nothing"])

    def test_log_keeps_lf_newline(self):
        journal.log_delta("x")
        raw = self.path("sessions/session-current.md").read_bytes()
        self.assertNotIn(b"\r\n", raw)
        self.assertTrue(raw.endswith(b"\n"))


class Batches(CampaignCase):
    def test_snapshot_manifest_and_touched(self):
        with journal.Batch("gm.py do \"hp Kael -8; log x\"") as b:
            doc = md.load(self.path("pcs/kael-ashford.md"))
            before = doc.text()
            doc.set_front("hp", {"current": 22, "max": 30})
            doc.save()
            doc.set_front("ac", 17)
            doc.save()  # second save of the same file: one snapshot
            journal.log_delta("hp Kael 30→22")
            self.assertEqual(b.touched, ["pcs/kael-ashford.md", "sessions/session-current.md"])
        entry = self.path(".gm/journal/0001")
        manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["command line"], "gm.py do \"hp Kael -8; log x\"")
        self.assertEqual(manifest["turn"], 1)
        self.assertEqual(manifest["step"], 1)
        self.assertIs(manifest["overrule"], False)
        self.assertEqual(set(manifest["files"]), {"pcs/kael-ashford.md", "sessions/session-current.md"})
        snap = (entry / manifest["files"]["pcs/kael-ashford.md"]).read_bytes()
        self.assertEqual(snap, before.replace("\n", "\r\n").encode("utf-8"))
        self.assertIsNone(journal.current())

    def test_batch_without_writes_leaves_nothing(self):
        with journal.Batch("gm.py do nonexistent") as b:
            pass
        self.assertEqual(b.touched, [])
        self.assertFalse(self.path(".gm/journal").exists())

    def test_nested_batch_shares_outer(self):
        with journal.Batch("outer") as outer:
            with journal.Batch("inner") as inner:
                self.assertIs(inner, outer)
                journal.log_delta("x")
            self.assertIs(journal.current(), outer)
        self.assertEqual(outer.touched, ["sessions/session-current.md"])

    def test_step_counts_batches_in_the_same_turn(self):
        with journal.Batch("a"):
            journal.log_delta("one")
        with journal.Batch("b"):
            journal.log_delta("two")
        with journal.Batch("c"):
            journal.log_turn("done")
        with journal.Batch("d"):
            journal.log_delta("next turn")
        steps = [(m["turn"], m["step"]) for _, m in journal.entries()]
        self.assertEqual(steps, [(1, 1), (1, 2), (1, 3), (2, 1)])

    def test_numbering_is_numeric_past_9999(self):
        for n in (9998, 9999, 10000):
            d = self.path(f".gm/journal/{n}")
            d.mkdir(parents=True)
            (d / "manifest.json").write_text('{"turn": 1}', encoding="utf-8")
        self.assertEqual(journal._next_dir().name, "10001")
        self.assertEqual([e.name for e, _ in journal.entries()], ["9998", "9999", "10000"])
        for i in range(50):
            with journal.Batch(f"b{i}"):
                journal.log_delta(f"d{i}")
        names = [e.name for e, _ in journal.entries()]
        self.assertEqual(len(names), 50)
        self.assertEqual(names[0], "10001")  # the numerically oldest were pruned
        self.assertEqual(names[-1], "10050")

    def test_snapshot_skips_gm_scratch_and_refuses_outside_root(self):
        self.path(".gm").mkdir()
        with journal.Batch("x") as b:
            md.new(self.path(".gm/brief-hash"), "abc\n").save()
            self.assertEqual(b.touched, [])
            self.assertIsNone(b.dir)
            with self.assertRaises(journal.JournalError):
                md.new(self.tmp / "outside.md", "x\n").save()
            self.assertFalse((self.tmp / "outside.md").exists())
        self.assertFalse(self.path(".gm/journal").exists())
        self.assertEqual(self.path(".gm/brief-hash").read_text(encoding="utf-8"), "abc\n")

    def test_batch_is_lazy_until_the_first_write(self):
        campaign.set_override(str(self.tmp / "missing"))
        with journal.Batch("read only") as b:
            self.assertIsNone(b.turn)
            self.assertIs(journal.current(), b)
        campaign.set_override(str(self.camp))
        with journal.Batch("write") as b:
            journal.log_delta("x")
            self.assertEqual((b.turn, b.step), (1, 1))

    def test_empty_summary_refused(self):
        with self.assertRaises(journal.JournalError):
            journal.log_turn("  ")
        self.assertEqual(journal.current_turn(), (1, False))

    def test_keeps_last_50(self):
        for i in range(53):
            with journal.Batch(f"b{i}"):
                journal.log_delta(f"d{i}")
        names = [e.name for e, _ in journal.entries()]
        self.assertEqual(len(names), 50)
        self.assertEqual(names[0], "0004")
        self.assertEqual(names[-1], "0053")


class Undo(CampaignCase):
    def test_undo_restores_bytes_and_logs(self):
        kael = self.path("pcs/kael-ashford.md")
        before = kael.read_bytes()
        with journal.Batch("gm.py hp Kael -8"):
            doc = md.load(kael)
            doc.set_front("hp", {"current": 22, "max": 30})
            doc.save()
            journal.log_delta("hp Kael 30→22")
        self.assertNotEqual(kael.read_bytes(), before)
        manifest = journal.undo()
        self.assertEqual(manifest["command line"], "gm.py hp Kael -8")
        self.assertEqual(kael.read_bytes(), before)
        log = self.path("sessions/session-current.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(log[-2:], ["[turn 1]", "  - undo turn 1 step 1"])
        self.assertFalse(self.path(".gm/journal/0001").exists())
        with self.assertRaises(journal.NothingToUndo):
            journal.undo()

    def test_undo_deletes_created_files(self):
        new = self.path("npcs/jess.md")
        with journal.Batch("gm.py stub npc Jess"):
            md.new(new, "---\nname: Jess\n---\n").save()
        self.assertTrue(new.exists())
        journal.undo()
        self.assertFalse(new.exists())

    def test_undo_inside_a_batch_is_not_journaled(self):
        with journal.Batch("first"):
            journal.log_delta("a")
        with journal.Batch("gm.py undo"):
            journal.undo()
        self.assertEqual(journal.entries(), [])
        log = self.path("sessions/session-current.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(log[-1], "  - undo turn 1 step 1")


if __name__ == "__main__":
    unittest.main()
