"""Phase 3: `brief`, the hook mode (hash, heartbeat, forced refresh, SessionStart) and
Wacky Juice (plan.md Phase 3 → Verify; planning/06 → brief + hooks, `gm.py juice`)."""
import io
import json
import subprocess
import sys
import time
import unittest
from unittest import mock

from fixture import TOOLS, CampaignCase, _edit, run_main, set_front_raw, start_combat
from lib import md


def hook(event="UserPromptSubmit", prompt="I look around", source=None, seed=None, long=False):
    data = {"hook_event_name": event}
    if prompt is not None and event == "UserPromptSubmit":
        data["prompt"] = prompt
    if source:
        data["source"] = source
    argv = ["brief", "--hook"] + (["--long"] if long else []) + (["--seed", str(seed)] if seed is not None else [])
    with mock.patch("sys.stdin", io.StringIO(json.dumps(data))):
        code, lines = run_main(argv)
    assert code == 0, lines
    return lines


class Brief(CampaignCase):
    def test_shapes(self):
        code, lines = run_main(["brief"])
        self.assertEqual(code, 0)
        self.assertLessEqual(len(lines), 20)
        self.assertEqual(lines[0], "[GM BRIEF] poc · Day 1 18:30 (dusk) · crossroads-inn — "
                                   "Common room, dinner rush · tempo: calm")
        self.assertEqual(lines[1], "On stage: Mara (neutral) goal: a quiet evening · "
                                   "Tobin (friendly) goal: find someone who'll listen")
        self.assertEqual(lines[2], "Party: Kael 30/30 AC18 · Kira 30/30 AC14")
        self.assertEqual(lines[3], "Rules: —")
        self.assertTrue(lines[4].startswith("Watch: Party asks Mara about Harl → beat 1 · "))
        self.assertTrue(lines[4].endswith("Next clock: Day 3 02:00 (Veskar moves Harl to the mill) in 1d 7h30m"))
        self.assertEqual(lines[5:], ["Combat: —", "Log: no turns yet"])

    def test_long(self):
        code, lines = run_main(["brief", "--long"])
        self.assertTrue(any(line.startswith("Summary: The party has just arrived") for line in lines))
        self.assertIn("Recent log: (no turns yet)", lines)
        self.assertIn("Spoilers: none", lines)

    def test_combat_order_party_and_rules(self):
        start_combat(self)
        run_main(["rule", "add", "crits on 19-20", "--scope", "combat", "--key", "crit-range=19"])
        code, lines = run_main(["brief"])
        self.assertIn("tempo: combat", lines[0])
        self.assertIn("Order: Veskar 18 · Kael 15 · Thugs ×3 12", lines)
        party = next(line for line in lines if line.startswith("Party:"))
        self.assertIn("Kael 9/11 AC15 [poisoned 3r]", party)
        self.assertIn("Rules: R1 crit-range=19 (combat)", lines)
        self.assertIn("Combat: round 2 · up: Kael", lines)

    def test_absent_pc_and_log_line(self):
        set_front_raw(self, "pcs/kira-thornwood.md", "present", False)
        run_main(["do", "hp Kael -3"])
        code, lines = run_main(["brief"])
        self.assertIn("Party: Kael 27/30 AC18 · Kira (autopilot)", lines)
        self.assertEqual(lines[-1], "Log: turn 1 open (1 delta)")


class Hook(CampaignCase):
    def setUp(self):
        super().setUp()
        set_front_raw(self, "state/current.md", "wacky-juice", "off")

    def start(self):
        set_front_raw(self, "state/current.md", "in-session", True)

    def test_silent_out_of_session(self):
        self.assertEqual(hook(), [])
        self.assertEqual(hook("SessionStart", source="startup"), [])

    def test_full_then_heartbeat_then_change(self):
        self.start()
        full = hook()
        self.assertTrue(full[0].startswith("[GM BRIEF] poc"))
        self.assertGreater(len(full), 5)
        beat = hook()
        self.assertEqual(beat, ["[GM BRIEF] unchanged since turn 1 · Day 1 18:30 · calm"])
        run_main(["do", 'log "Kira orders ale"'])  # only the Log: line changes
        self.assertEqual(len(hook()), 1)
        run_main(["do", "hp Kael -3"])
        again = hook()
        self.assertIn("Party: Kael 27/30 AC18 · Kira 30/30 AC14", again)
        self.assertEqual(hook(), ["[GM BRIEF] unchanged since turn 2 · Day 1 18:30 · calm · Kael 27/30"])

    def test_heartbeat_in_combat(self):
        self.start()
        start_combat(self)
        run_main(["rule", "add", "crits on 19-20", "--scope", "combat", "--key", "crit-range=19"])
        hook()
        self.assertEqual(hook(), ["[GM BRIEF] unchanged since turn 1 · Day 1 18:30 · combat · "
                                  "Kael 9/11 poisoned · up: Kael · R1"])

    def test_forced_full(self):
        self.start()
        hook()
        self.assertEqual(len(hook(prompt="!brief")), len(hook(prompt="!brief")))
        self.assertGreater(len(hook(prompt="!brief please")), 1)
        counts = [len(hook()) for _ in range(15)]
        self.assertEqual(counts[:14], [1] * 14)
        self.assertGreater(counts[14], 1)  # the 15th prompt since the last full brief

    def test_session_start_long_and_reset(self):
        self.start()
        hook()
        lines = hook("SessionStart", source="compact", long=True)
        self.assertTrue(any(line.startswith("Summary:") for line in lines))
        self.assertFalse(self.path(".gm/brief-hash").exists())
        self.assertGreater(len(hook()), 1)  # next prompt: full brief

    def test_errors_never_fail(self):
        self.start()
        self.path("state/current.md").write_text("---\nin-session: true\nin-game-datetime: nonsense\n---\n",
                                                 encoding="utf-8")
        lines = hook()
        self.assertTrue(lines)
        with mock.patch("sys.stdin", io.StringIO("")):
            self.assertEqual(run_main(["brief", "--hook"])[0], 0)

    def test_unavailable_line(self):
        self.start()
        with mock.patch("brief.build", side_effect=RuntimeError("boom")):
            self.assertEqual(hook(), ["[GM BRIEF] unavailable: RuntimeError: boom"])

    def test_subprocess_and_speed(self):
        self.start()
        data = json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hi"})
        out = subprocess.run([sys.executable, str(TOOLS / "gm.py"), "brief", "--hook"], input=data,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0)
        self.assertTrue(out.stdout.startswith("[GM BRIEF] poc"))
        t = time.perf_counter()
        hook()
        self.assertLess(time.perf_counter() - t, 0.2)


class Juice(CampaignCase):
    def setUp(self):
        super().setUp()
        set_front_raw(self, "state/current.md", "in-session", True)
        set_front_raw(self, "state/current.md", "wacky-juice-value", 100)

    def log_text(self):
        return self.path("sessions/session-current.md").read_text(encoding="utf-8")

    def juice_lines(self, lines):
        return [line for line in lines if line.startswith("Juice:")]

    def test_fires_with_full_and_heartbeat_and_do_logs_it(self):
        first = hook(seed=1)
        self.assertEqual(len(self.juice_lines(first)), 1)
        self.assertRegex(first[-1], r"^Juice: (Mara|Tobin) — an unexpected, funny move this turn")
        name = first[-1].split()[1]
        run_main(["do", 'log "Tobin starts a conga line"'])
        self.assertIn(f"  - (GM) [juice] {name}", self.log_text())
        # cooldown 3: the next three prompts never fire, the fourth does (value 100)
        fired = [bool(self.juice_lines(hook(seed=2))) for _ in range(4)]
        self.assertEqual(fired, [False, False, False, True])
        # it rides on a heartbeat too
        self.assertEqual(len(hook(seed=3)), 1)  # cooldown, heartbeat only
        set_front_raw(self, "state/current.md", "wacky-juice-cooldown", 0)
        lines = hook(seed=4)
        self.assertTrue(lines[0].startswith("[GM BRIEF] unchanged"))
        self.assertTrue(lines[1].startswith("Juice:"))

    def test_juice_does_not_change_the_hash(self):
        hook(seed=1)
        self.assertTrue(hook(seed=1)[0].startswith("[GM BRIEF] unchanged"))

    def test_never_fires(self):
        cases = {
            "value 0": lambda: set_front_raw(self, "state/current.md", "wacky-juice-value", 0),
            "off": lambda: set_front_raw(self, "state/current.md", "wacky-juice", "off"),
        }
        for label, setup in cases.items():
            with self.subTest(label):
                setup()
                self.assertFalse(self.juice_lines(hook(seed=1)))
                set_front_raw(self, "state/current.md", "wacky-juice-value", 100)
                set_front_raw(self, "state/current.md", "wacky-juice", "on")
        for prompt in ("/overrule Kira hits", "!brief"):
            with self.subTest(prompt):
                self.assertFalse(self.juice_lines(hook(prompt=prompt, seed=1)))

    def test_nobody_who_can_act(self):
        set_front_raw(self, "npcs/mara-fennick.md", "conditions", ["unconscious"])
        set_front_raw(self, "npcs/tobin-hale.md", "conditions", ["stunned 1r"])
        self.assertFalse(self.juice_lines(hook(seed=1)))
        set_front_raw(self, "npcs/tobin-hale.md", "conditions", [])
        self.assertEqual(self.juice_lines(hook(seed=1))[0].split()[1], "Tobin")

    def test_nobody_on_stage(self):
        _edit(self.path("state/current.md"),
              lambda t: t.replace("- **Mara**", "- Mara").replace("- **Tobin**", "- Tobin"))
        self.assertFalse(self.juice_lines(hook(seed=1)))

    def test_combat_skips_party_and_downed(self):
        start_combat(self)
        set_front_raw(self, "state/current.md", "wacky-juice-cooldown", 0)
        seen = set()
        for s in range(30):
            got = self.juice_lines(hook(seed=s))
            seen.add(got[0].split(":")[1].split("—")[0].strip())
            run_main(["juice", "waive"])
        self.assertEqual(seen, {"Veskar", "Thugs ×3"})

    def test_waive_and_unlogged(self):
        name = hook(seed=1)[-1].split()[1]
        code, lines = run_main(["do", 'juice waive; log "nothing funny fit"'])
        self.assertEqual(lines[0], f"[juice waived: {name}]")
        self.assertIn(f"  - (GM) [juice] {name} — waived", self.log_text())
        self.assertNotIn(f"  - (GM) [juice] {name}\n", self.log_text().replace("\r\n", "\n"))
        self.assertEqual(run_main(["juice", "waive"])[1], ["[juice: nothing pending]"])
        set_front_raw(self, "state/current.md", "wacky-juice-cooldown", 0)
        name = hook(seed=2)[-1].split()[1]
        hook(prompt="/end-session", seed=3)  # no do/log in between
        self.assertIn(f"  - (GM) [juice] {name} — no turn logged", self.log_text())
        self.assertFalse(self.path(".gm/journal").exists() and
                         any("no turn logged" in p.read_text(encoding="utf-8", errors="ignore")
                             for p in self.path(".gm/journal").rglob("manifest.json")))
        code, lines = run_main(["juice"])
        self.assertIn("this session: 0 used, 1 waived, 1 unlogged", lines[0])

    def test_set_value_cooldown_on_off(self):
        code, lines = run_main(["juice", "10"])
        self.assertEqual(lines, ["[juice value 100 → 10]"])
        self.assertEqual(md.load(self.path("state/current.md")).front["wacky-juice-value"], 10)
        self.assertIn("  - [juice] value 100 → 10", self.log_text())
        self.assertEqual(run_main(["juice", "cooldown", "5"])[1], ["[juice cooldown 3 → 5]"])
        self.assertEqual(run_main(["juice", "off"])[1], ["[juice off]"])
        self.assertIn("[Juice: off · 10% · cooldown 5", run_main(["juice", "status"])[1][0])
        self.assertEqual(run_main(["juice", "101"])[0], 1)
        self.assertEqual(run_main(["juice", "sideways"])[0], 1)
        run_main(["undo"])  # setting changes are ordinary, undoable writes
        self.assertIsNone(md.load(self.path("state/current.md")).front.get("wacky-juice"))
        self.assertIn("[Juice: on ·", run_main(["juice"])[1][0])  # back to the default

    def test_campaign_md_wins(self):
        self.path("campaign.md").write_text("---\nname: T\nwacky-juice-value: 7\n---\n", encoding="utf-8")
        self.assertIn("· 7% ·", run_main(["juice"])[1][0])
        run_main(["juice", "8"])
        self.assertEqual(md.load(self.path("campaign.md")).front["wacky-juice-value"], 8)
        self.assertEqual(md.load(self.path("state/current.md")).front["wacky-juice-value"], 100)


if __name__ == "__main__":
    unittest.main()
