"""gm.py dispatch: `do` stop-on-failure, `log`, unknown commands (plan.md Phase 1
items 5-6; planning/06 L30-32)."""
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

from fixture import TOOLS, CampaignCase, campaign
from lib import journal
import gm


def run_main(argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = gm.main(argv)
    return code, out.getvalue().splitlines()


class Do(CampaignCase):
    def log_lines(self):
        return self.path("sessions/session-current.md").read_text(encoding="utf-8").splitlines()

    def test_unknown_command_reports_the_step(self):
        code, lines = run_main(["do", "nonexistent"])
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], "[do] step 1 `nonexistent` failed: unknown command 'nonexistent'")
        self.assertTrue(lines[1].startswith("usage: gm.py"))
        self.assertEqual(lines[-1], "[do] applied: (none)")

    def test_stops_at_first_failure_and_lists_applied(self):
        code, lines = run_main(["do", 'log "turn one"; log "turn two"; nonexistent x; log "never"'])
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], "[turn 1 logged]")
        self.assertEqual(lines[1], "[turn 2 logged]")
        self.assertEqual(lines[2], "[do] step 3 `nonexistent x` failed: unknown command 'nonexistent'")
        self.assertEqual(lines[-1], '[do] applied: 1 `log "turn one"`, 2 `log "turn two"`')
        self.assertEqual(self.log_lines()[-2:], ["[turn 1] turn one", "[turn 2] turn two"])

    def test_all_steps_in_one_batch(self):
        code, lines = run_main(["do", 'log "a"; log "b"'])
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["[turn 1 logged]", "[turn 2 logged]"])
        entries = sorted(p.name for p in self.path(".gm/journal").iterdir())
        self.assertEqual(entries, ["0001"])
        manifest = json.loads((self.path(".gm/journal/0001/manifest.json")).read_text(encoding="utf-8"))
        self.assertEqual(manifest["command line"], "gm.py do 'log \"a\"; log \"b\"'")
        self.assertEqual(manifest["files"].keys(), {"sessions/session-current.md"})

    def test_bad_arguments_in_a_step(self):
        code, lines = run_main(["do", "log"])
        self.assertEqual(code, 1)
        self.assertIn("step 1 `log` failed:", lines[0])

    def test_semicolon_inside_quotes_is_one_step(self):
        self.assertEqual(gm.split_steps('log "Kira says hi; Tobin nods"; log \'a; b\''),
                         ['log "Kira says hi; Tobin nods"', "log 'a; b'"])
        code, lines = run_main(["do", 'log "Kira says hi; Tobin nods"'])
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["[turn 1 logged]"])
        self.assertEqual(self.log_lines()[-1], "[turn 1] Kira says hi; Tobin nods")

    def test_windows_path_survives_step_tokenizing(self):
        self.assertEqual(gm.split_args("log x --campaign C:\\tmp\\poc"),
                         ["log", "x", "--campaign", "C:\\tmp\\poc"])
        self.assertEqual(gm.split_args('log "C:\\tmp\\poc"'), ["log", "C:\\tmp\\poc"])
        code, lines = run_main(["do", f"log x --campaign {self.camp}"])
        self.assertEqual(code, 0)

    def test_space_failure_inside_do(self):
        code, lines = run_main(["do", 'log "a"; space bogus'])
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], "[turn 1 logged]")
        self.assertTrue(lines[1].startswith("[do] step 2 `space bogus` failed: space exited 2"), lines)
        self.assertEqual(lines[-1], '[do] applied: 1 `log "a"`')
        self.assertFalse(any("Traceback" in line or line.startswith("usage: space") for line in lines), lines)
        code, lines = run_main(["do", "space dist Nobody Kael; log never"])
        self.assertEqual(code, 1)
        self.assertIn("space exited 1: 'nobody': no combatant match", lines[0])
        self.assertEqual(self.log_lines()[-1], "[turn 1] a")  # `log never` did not run
        self.assertEqual(journal.current_turn(), (2, False))

    def test_empty_and_nested(self):
        self.assertEqual(run_main(["do", " ; "])[0], 1)
        code, lines = run_main(["do", 'do "log x"'])
        self.assertEqual(code, 1)
        self.assertIn("do cannot nest", lines[0])


class Dispatch(CampaignCase):
    def test_unknown_top_level_command(self):
        code, lines = run_main(["nonexistent"])
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], "[nonexistent] unknown command 'nonexistent'")
        self.assertTrue(lines[1].startswith("usage: gm.py"))

    def test_no_command_prints_help(self):
        code, lines = run_main([])
        self.assertEqual(code, 0)
        self.assertTrue(lines[0].startswith("usage: gm.py"))

    def test_log_json(self):
        code, lines = run_main(["--json", "log", "x"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(lines[0]), {"turn": 1})
        code, lines = run_main(["log", "y", "--json"])  # globals after the command too
        self.assertEqual(json.loads(lines[0]), {"turn": 2})

    def test_campaign_flag(self):
        code, lines = run_main(["--campaign", str(self.camp), "log", "z"])
        self.assertEqual(code, 0)
        code, lines = run_main(["--campaign", str(self.tmp / "nope"), "log", "z"])
        self.assertEqual(code, 1)
        self.assertIn("campaign folder not found", lines[0])

    def test_space_forwards(self):
        code, lines = run_main(["space", "dist", "0,0,0", "30,40,0"])
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["40 ft"])  # 5e diagonal rule, straight from space.py
        code, lines = run_main(["--json", "space", "dist", "0,0,0", "30,40,0"])
        self.assertEqual(json.loads(lines[0]), {"lines": ["40 ft"]})
        self.assertFalse(self.path(".gm").exists())

    def test_read_only_command_needs_no_campaign(self):
        os.environ["GM_CAMPAIGN"] = str(self.tmp / "missing")
        campaign.set_override(None)
        code, lines = run_main(["space", "dist", "0,0,0", "30,40,0"])
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["40 ft"])
        code, lines = run_main(["log", "x"])  # a write still needs one
        self.assertEqual(code, 1)
        self.assertIn("campaign folder not found", lines[0])

    def test_global_flag_before_unknown_command(self):
        code, lines = run_main(["--campaign", str(self.camp), "undo"])
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], "[undo] unknown command 'undo'")
        code, lines = run_main(["--json"])
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], "[gm.py] no command given")

    def test_empty_summary_refused(self):
        code, lines = run_main(["log", "   "])
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], "[log] log: the summary is empty")


class Subprocess(CampaignCase):
    def test_cli_do_nonexistent(self):
        res = subprocess.run([sys.executable, str(TOOLS / "gm.py"), "do", "nonexistent"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 1)
        self.assertIn("[do] step 1 `nonexistent` failed: unknown command 'nonexistent'", res.stdout)
        self.assertIn("[do] applied: (none)", res.stdout)
        self.assertFalse(self.path(".gm").exists())


if __name__ == "__main__":
    unittest.main()
