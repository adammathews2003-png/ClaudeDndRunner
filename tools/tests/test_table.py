"""Phase 5: the table client's local logic — input conventions, the narration renderer
(spoiler banners, bracket lines, activity line), the permission gate — and the guards
(plan.md Phase 5 → Guards). The live SDK checks are recorded in CLIENT-CHECKS.md."""
import io
import re
import tempfile
import unittest
from pathlib import Path

from fixture import TOOLS
import table

R = table.ROOT


class Input(unittest.TestCase):
    def test_conventions(self):
        s = table.InputState()
        self.assertEqual(s.handle("Kira: I check the trapdoor"), ("send", "Kira: I check the trapdoor"))
        self.assertEqual(s.handle("what time is it?"), ("send", "what time is it?"))  # table talk
        self.assertEqual(s.handle(":as Kira"), ("local", "as", "Kira"))
        self.assertEqual(s.handle("I open the door"), ("send", "Kira: I open the door"))
        self.assertEqual(s.handle("Kael: I follow"), ("send", "Kael: I follow"))
        self.assertEqual(s.handle("/overrule Kira wasn't seen"), ("send", "/overrule Kira wasn't seen"))
        self.assertEqual(s.handle("!brief"), ("send", "!brief"))
        self.assertEqual(s.handle(":gm-view on"), ("local", "gm-view", "on"))
        self.assertEqual(s.handle(":quit"), ("local", "quit", ""))
        self.assertEqual(s.handle("   "), ("skip",))
        s.handle(":as")
        self.assertEqual(s.handle("hello"), ("send", "hello"))


class Render(unittest.TestCase):
    def out(self, chunks, color=False, end=True):
        buf = io.StringIO()
        r = table.Renderer(out=buf, color=color, width=40)
        for c in chunks:
            if c is None:
                r.activity()
            else:
                r.text(c)
        if end:
            r.end_message()
        return buf.getvalue().splitlines()

    def test_streamed_lines(self):
        self.assertEqual(self.out(["The fire cra", "ckles.\nMara looks", " up."]),
                         ["The fire crackles.", "Mara looks up."])

    def test_activity_once_per_turn(self):
        lines = self.out(["Hmm.\n", None, None, "Done."])
        self.assertEqual(lines.count(table.ACTIVITY), 1)

    def test_bracket_lines_dim(self):
        lines = self.out(["You swing.\n[Kael → Veskar: d20 13+5=18 vs AC 15 — HIT]\n"], color=True)
        self.assertEqual(lines[0], "You swing.")
        self.assertTrue(lines[1].startswith(table.DIM))

    def test_spoiler_banner(self):
        lines = self.out(["Sure.\n<<SPOILERS major/answer>>\nVeskar is the buyer.\n<<END SPOILERS>>\nBack to it."])
        self.assertEqual(lines[0], "Sure.")
        self.assertTrue(lines[1].startswith("── SPOILERS · major · answer "))
        self.assertEqual(lines[2], "Veskar is the buyer.")
        self.assertTrue(lines[3].startswith("── END SPOILERS"))
        self.assertEqual(lines[4], "Back to it.")

    def test_spoiler_markers_split_and_inline(self):
        lines = self.out(["<<SPOI", "LERS minor/hint>> a hint <<END SPOILERS>> after"])
        self.assertTrue(lines[0].startswith("── SPOILERS · minor · hint"))
        self.assertEqual(lines[1], " a hint ")
        self.assertTrue(lines[2].startswith("── END SPOILERS"))
        self.assertEqual(lines[3], " after")

    def test_unbalanced_closed_at_message_end(self):
        lines = self.out(["<<SPOILERS major/full>>\nthe truth is"])
        self.assertTrue(lines[-1].startswith("── END SPOILERS"))


class Gate(unittest.TestCase):
    def test_commands(self):
        ok = ["python tools/gm.py roll 1d20", 'python tools/gm.py do "log \'a; b\'; hp Kael -3"',
              "py tools/space.py map --player-view", f'cd "{R}" && python tools/gm.py brief',
              f'python "{R / "tools" / "gm.py"}" roll 1d20',
              r'python tools/gm.py do "attitude mara wary \"asked; deflecting\"; log \"Kira asked\""']
        bad = ["whoami", "python tools/gm.py roll 1d20; whoami", 'python tools/gm.py log "$(whoami)"',
               "python tools/gm.py roll 1d20 | tee x", "python tools/gm.py roll 1d20 > x.txt",
               "python tools/gm.pyx", 'python tools/gm.py log "unclosed', "python tools/gm.py a\nwhoami",
               "cd C:/Windows && python tools/gm.py roll 1d20", "python tools/gm.py log `whoami`",
               f'cd "{R}" && python tools/gm.py brief && whoami', "rm -rf poc",
               r'python tools/gm.py do "log \"a\"" ; whoami', r'python tools/gm.py log "a\\"; whoami']
        for c in ok:
            self.assertTrue(table.command_ok(c), c)
        for c in bad:
            self.assertFalse(table.command_ok(c), c)

    def test_decide(self):
        self.assertEqual(table.decide("Skill", {}), (True, ""))
        self.assertTrue(table.decide("Read", {"file_path": "poc/state/current.md"})[0])
        self.assertTrue(table.decide("Grep", {})[0])
        self.assertFalse(table.decide("Read", {"file_path": "C:/Windows/win.ini"})[0])
        self.assertFalse(table.decide("Read", {"file_path": str(R.parent / "secret.md")})[0])
        for tool in ("Write", "Edit", "WebFetch", "Task", "NotebookEdit"):
            self.assertFalse(table.decide(tool, {})[0], tool)
        self.assertTrue(table.decide("Bash", {"command": "python tools/gm.py brief"})[0])
        self.assertFalse(table.decide("PowerShell", {"command": "Get-ChildItem"})[0])

    def test_denial_log(self):
        camp = Path(tempfile.mkdtemp())
        table.log_denial(camp, "Bash", {"command": "whoami"}, "Bash command not allowed at the table")
        text = (camp / ".gm" / "client.log").read_text(encoding="utf-8")
        self.assertRegex(text, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d DENIED Bash: whoami — ")


class Guards(unittest.TestCase):
    def test_sdk_only_in_table(self):
        users = [p.name for p in list(TOOLS.rglob("*.py"))
                 if "tests" not in p.parts and "claude_agent_sdk" in p.read_text(encoding="utf-8")]
        self.assertEqual(users, ["table.py"])

    def test_table_writes_only_gm_scratch(self):
        src = (TOOLS / "table.py").read_text(encoding="utf-8")
        writes = re.findall(r"(\w+)\.(?:write_text|open)\(", src)
        # every write goes through a path built under `<campaign>/.gm/`
        for line in src.splitlines():
            if re.search(r"\.write_text\(|\.open\(\"a\"", line):
                self.assertTrue(re.search(r"\bp\.|path\.|_sid_path|\.gm", line), line)
        self.assertIn('".gm"', src)
        self.assertNotIn("md.save", src)
        self.assertTrue(writes)

    def test_sdk_import_is_lazy(self):
        top = (TOOLS / "table.py").read_text(encoding="utf-8").split("\nclass Table")[0]
        self.assertNotRegex(top, r"^(from|import) claude_agent_sdk", "module import must stay stdlib-only")


if __name__ == "__main__":
    unittest.main()
