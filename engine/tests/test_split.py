"""Phase 12: `split` — groups, slices, per-group clocks, sensing, join
(plan.md Phase 12 → Verify; docs/design/02 → Splitting the party; 06 → `gm.py split`)."""
import io
import json
from unittest import mock

from fixture import CampaignCase, run_main, set_front_raw
from lib import md


def hook(prompt):
    data = {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
    with mock.patch("sys.stdin", io.StringIO(json.dumps(data))):
        code, lines = run_main(["brief", "--hook"])
    assert code == 0, lines
    return lines


class Split(CampaignCase):
    def split(self):
        code, lines = run_main(["split", "a=Kael", "b=Kira"])
        self.assertEqual(code, 0, lines)
        return lines

    def brief(self):
        return "\n".join(run_main(["brief"])[1])

    def front(self, rel):
        return md.load(self.path(rel)).front

    def round_to(self, n):
        for _ in range(40):
            if f"round {n} " in self.brief().split("Combat:")[1]:
                return
            run_main(["combat", "next", "--seed", "1"])
        self.fail(f"never reached round {n}")

    def test_form_and_brief(self):
        self.assertIn("[split a (Kael) · b (Kira) · active a", self.split()[0])
        text = self.brief()
        self.assertIn("Split: ▶ a (Kael) · b (Kira) crossroads-inn/common-room Day 1 18:30 calm, level", text)
        self.assertIn("Slice: exchange 0/3", text)
        self.assertTrue(self.path("state/split/b.md").exists())

    def test_form_guards(self):
        code, lines = run_main(["split", "a=Kael"])
        self.assertEqual(code, 1)
        self.assertIn("at least two groups", lines[-1])
        code, lines = run_main(["split", "a=Kael", "b=Kael"])
        self.assertIn("in both a and b", lines[-1])
        self.split()
        code, lines = run_main(["split", "c=Kael", "d=Kira"])
        self.assertIn("already split", lines[-1])

    def test_exchanges_and_cue(self):
        set_front_raw(self, "state/current.md", "in-session", True)
        self.split()
        hook("Kael: I check the door")
        hook("/spoilers what was that")   # commands aren't exchanges
        hook("Kael: I listen")
        self.assertIn("Slice: exchange 2/3", self.brief())
        out = hook("Kael: I open it")
        self.assertIn("Cut due: 3 exchanges", self.brief())
        self.assertTrue(any("CUT DUE" in l or "Cut due" in l for l in out), out)

    def test_cut_swaps_scenes_and_groups_move_alone(self):
        self.split()
        run_main(["time", "+20m"])
        code, lines = run_main(["split", "cut"])
        self.assertIn("[split cut: a → b (Kira)", lines[-1])
        self.assertEqual(self.front("state/current.md")["in-game-datetime"], "Day 1 18:30")
        self.assertEqual(self.front("state/split/a.md")["in-game-datetime"], "Day 1 18:50")
        self.assertFalse(self.path("state/split/b.md").exists())
        run_main(["move-party", "old-mill"])
        self.assertEqual(self.front("pcs/kira-thornwood.md")["location"], "old-mill")
        self.assertEqual(self.front("pcs/kael-ashford.md")["location"], "crossroads-inn/common-room")
        self.assertIn("a (Kael) crossroads-inn/common-room Day 1 18:50 calm, 20m ahead", self.brief())

    def test_ahead_warning_and_refusal(self):
        self.split()
        code, lines = run_main(["time", "+40m"])
        self.assertIn("[split: a is now 40m ahead of b", "\n".join(lines))
        self.assertIn("Cut due: b is 40m behind", self.brief())
        run_main(["split", "cut"])
        code, lines = run_main(["split", "cut", "a"])
        self.assertEqual(code, 1)
        self.assertIn("40m ahead of the earliest group", lines[-1])
        self.assertEqual(run_main(["split", "cut", "a", "--force"])[0], 0)

    def test_world_clock_waits_for_the_earliest_group(self):
        doc = md.load(self.path("state/current.md"))
        doc.append_line("Clocks", "- Day 1 18:45: the bell tolls (test)")
        doc.save()
        self.split()
        code, lines = run_main(["time", "+30m"])
        text = "\n".join(lines)
        self.assertNotIn("the bell tolls", text.split("Clocks:")[0])
        self.assertIn("World clock (earliest group): Day 1 18:30 → Day 1 18:30", text)
        run_main(["split", "cut"])
        code, lines = run_main(["time", "+20m"])
        self.assertIn("CLOCK Day 1 18:45 (current): the bell tolls", "\n".join(lines))

    def test_combat_slices(self):
        self.split()
        code, lines = run_main(["combat", "start", "--add", "srd:bandit", "--init", "Kael=10", "--seed", "1"])
        self.assertEqual(code, 0, lines)
        names = " ".join(r["name"] for r in md.load(self.path("state/current.md")).table("Combatants").rows)
        self.assertIn("Kael", names)
        self.assertNotIn("Kira", names)          # b isn't in this scene
        self.round_to(2)
        self.assertIn("Cut every round: b can sense the fight", self.brief())   # same site
        run_main(["split", "sense", "b", "off"])
        self.assertIn("Slice: round 2 of 6", self.brief())
        self.round_to(7)
        self.assertIn("Cut due: 6 rounds played", self.brief())
        code, lines = run_main(["combat", "end"])
        self.assertIn("[split: 7 combat rounds → the group's clock]", lines)
        self.assertEqual(self.front("state/current.md")["in-game-datetime"], "Day 1 18:31")

    def test_tasks(self):
        self.split()
        run_main(["split", "task", "a", "search the cellar", "30m"])
        self.assertIn("Tasks: a: search the cellar until 19:00", self.brief())
        code, lines = run_main(["time", "+30m"])
        self.assertIn("Long task done: a — search the cellar (19:00)", "\n".join(lines))
        self.assertNotIn("Tasks:", self.brief())

    def test_join(self):
        self.split()
        run_main(["time", "+5m"])
        code, lines = run_main(["split", "join", "a", "b"])
        self.assertEqual(code, 0, lines)
        self.assertIn("the party is together again", lines[0])
        self.assertIn("summarise b's last 5m", lines[1])
        self.assertFalse(self.path("state/split.md").exists())
        self.assertNotIn("Split:", self.brief())
        run_main(["undo"])
        self.assertTrue(self.path("state/split.md").exists())
        self.assertTrue(self.path("state/split/b.md").exists())

    def test_join_needs_one_site(self):
        self.split()
        run_main(["move-party", "old-mill"])
        code, lines = run_main(["split", "join", "a", "b"])
        self.assertEqual(code, 1)
        self.assertIn("same site first", lines[-1])

    def test_end_session_keeps_the_split(self):
        run_main(["session", "start"])
        self.split()
        run_main(["time", "+20m"])
        run_main(["split", "task", "a", "search the cellar", "30m"])
        code, lines = run_main(["session", "archive", "--summary", "Kael waits; Kira scouts.", "--no-commit", "--force"])
        self.assertEqual(code, 0, lines)
        self.assertIn("still split (2 groups, resumes next session)", lines[-1])
        hist = sorted(self.path("sessions/history").glob("session-*.md"))[-1].read_text(encoding="utf-8")
        self.assertIn("## Split at session end", hist)
        self.assertIn("- ▶ a (Kael) · crossroads-inn/common-room · Day 1 18:50 · calm", hist)
        self.assertIn("- b (Kira) · crossroads-inn/common-room · Day 1 18:30 · calm", hist)
        self.assertIn("- task a: search the cellar until Day 1 19:20", hist)
        self.assertTrue(self.path("state/split.md").exists())
        code, lines = run_main(["session", "start"])
        self.assertIn("[SPLIT] the party is still split", lines[-1])
        self.assertIn("open with b (furthest behind; `split cut b` first)", lines[-1])
        self.assertIn("[SPLIT]", "\n".join(run_main(["intro"])[1]))
