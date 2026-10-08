"""OOC asides, /table-talk, the queue echo, /execute-queue, /queue on|off, the GM's
<<QUEUE on|off>> line and the player command list (docs/design/06 → Table client)."""
import asyncio
import io
import sys
import time
import unittest
from unittest import mock

import fixture  # noqa: F401 — puts engine/ on the path
import discord_bridge as db
import player_commands
import table
from test_phase17 import CHAN, FakeIO, args, camp_dir, flush, make, msg, TOKEN


class Ooc(unittest.TestCase):
    def test_whole_line_forms(self):
        for line in ("/ooc how far is the door?", "OOC: how far is the door?", "ooc - how far is the door?",
                     "(OOC: how far is the door?)", "[ooc how far is the door?]", "((how far is the door?))"):
            self.assertEqual(db.ooc_only(line), "how far is the door?", line)

    def test_not_whole_line(self):
        for line in ("Kira: I climb (OOC: how long is the rope?)", "(OOC: a) Kira: I go (quietly)",
                     "Oocelot: I hiss", "I look around", "/oocish"):
            self.assertIsNone(db.ooc_only(line), line)

    def test_discord_labels_the_asker(self):
        pcs = db.player_pcs(camp_dir())
        self.assertEqual(db.speaker_line("OOC: can we break at 9?", "Sam", pcs), "(Sam, OOC) can we break at 9?")
        self.assertEqual(db.speaker_line("I climb (OOC: rope length?)", "Sam", pcs), "Kira: I climb (OOC: rope length?)")

    def test_discord_ooc_is_an_ordinary_line(self):
        b, _ = make("queue", interpret=lambda t: "INTERPRETED")
        b.on_message(msg(1, "/ooc can we break at 9?"))
        self.assertFalse(b.entries[0].flagged)
        self.assertEqual(b.take(), ["(Sam, OOC) can we break at 9?"])

    def test_console(self):
        inp = table.InputState(known={"overrule"})
        inp.handle(":as Kira")
        self.assertEqual(inp.handle("/ooc is the inn open?"), ("send", "(OOC) is the inn open?"))
        self.assertEqual(inp.handle("OOC: is the inn open?"), ("send", "(OOC) is the inn open?"))
        self.assertEqual(inp.handle("I knock (OOC: is the inn open?)"), ("send", "Kira: I knock (OOC: is the inn open?)"))


class TableTalk(unittest.TestCase):
    def test_from_discord_never_queued_or_sent(self):
        b, notices = make("queue")
        self.assertIsNone(b.on_message(msg(1, "/table-talk pizza's here")))
        self.assertIsNone(b.on_message(msg(2, "/tt brb")))
        self.assertEqual(b.entries, [])
        self.assertIn("[table talk] sam_the_bard: pizza's here", notices)
        flush(b)
        self.assertEqual(b.io.posts, [])                  # it's already in the channel

    def test_console(self):
        inp = table.InputState(known=set())
        self.assertEqual(inp.handle("/table-talk hi all"), ("local", "table-talk", "hi all"))
        self.assertEqual(inp.handle("/tt hi"), ("local", "table-talk", "hi"))


class QueueEcho(unittest.TestCase):
    def test_queue_posted_once_per_burst(self):
        b, _ = make("queue", interpret=lambda t: t)
        b.on_message(msg(1, "I check the trapdoor"))
        b.on_message(msg(2, "/spoilers who hired them?", author="ada_lace"))
        self.assertEqual(b.outbox.count(("queue",)), 1)
        flush(b)
        self.assertEqual(b.io.posts, ["[queue · 2 waiting — /execute-queue sends them]\n"
                                      "[Q1 sam_the_bard] Kira: I check the trapdoor\n"
                                      "[Q2 ada_lace ⚑] /spoilers who hired them?"])
        b.drop(2)
        flush(b)
        self.assertEqual(b.io.posts[-1], "[queue · 1 waiting — /execute-queue sends it]\n"
                                         "[Q1 sam_the_bard] Kira: I check the trapdoor")

    def test_no_echo_in_auto_or_once_sent(self):
        b, _ = make("auto")
        b.on_message(msg(1, "I dodge"))
        flush(b)
        self.assertEqual(b.io.posts, [])
        q, _ = make("queue")
        q.on_message(msg(1, "I dodge"))
        q.take()
        flush(q)
        self.assertEqual(q.io.posts, [])                  # sent before the post went out


class ExecuteQueue(unittest.TestCase):
    def test_a_player_sends_the_queue(self):
        b, notices = make("queue", interpret=lambda t: t)
        b.on_message(msg(1, "I duck"))
        b.on_message(msg(2, "/overrule Kira wasn't seen", author="ada_lace"))
        b.on_message(msg(3, "/execute-queue", author="ada_lace"))
        self.assertEqual(b.entries, [])
        self.assertEqual(b.take_released(), ["Kira: I duck", "/overrule Kira wasn't seen"])
        self.assertEqual(b.take_released(), [])
        self.assertIn("[discord: @ada_lace ran /execute-queue — sending]", notices)
        flush(b)
        self.assertIn((3, db.SENT), b.io.reactions)

    def test_empty(self):
        b, _ = make("queue")
        b.on_message(msg(1, "/execute-queue"))
        flush(b)
        self.assertEqual(b.io.posts, ["[queue empty]"])

    def test_host_types_it(self):
        self.assertEqual(table.InputState(known=set()).handle("/execute-queue"), ("local", "send", ""))


class QueueSwitch(unittest.TestCase):
    def test_from_discord(self):
        b, notices = make("queue")
        b.on_message(msg(1, "I wait"))
        b.on_message(msg(2, "/queue off"))
        self.assertEqual(b.mode, "auto")
        self.assertEqual(len(b.entries), 1)               # the waiting line now goes as a batch
        b.on_message(msg(3, "/queue on"))
        self.assertEqual(b.mode, "queue")
        self.assertIn("[discord: the queue is already on]", b.switch_queue("on"))
        flush(b)
        self.assertIn("[queue off — lines go to the GM as they come]", b.io.posts)
        self.assertIn("[queue on — lines wait; /execute-queue sends them]", b.io.posts)

    def test_bad_word_and_off_stays_off(self):
        b, _ = make("off")
        self.assertIn("/queue on|off", b.switch_queue("maybe"))
        b, _ = make("queue")
        b.on_message(msg(1, "/queue maybe"))
        self.assertEqual(b.mode, "queue")

    def test_gm_marker_is_hidden_and_recorded(self):
        out = io.StringIO()
        r = table.Renderer(out=out, color=False)
        r.text("(OOC: done — the queue is off.)\n<<QUEUE off>>\n")
        r.end_message()
        self.assertEqual(r.queue_switch, "off")
        self.assertNotIn("QUEUE", out.getvalue())


class Commands(unittest.TestCase):
    def test_lists(self):
        for cmd in ("/ooc", "/table-talk", "/overrule", "/spoilers", "/end-session", "!x", "/execute-queue",
                    "/queue on|off", "/commands"):
            self.assertIn(cmd, player_commands.SHORT + player_commands.DETAILED, cmd)
        self.assertTrue(all(len(c) <= db.LIMIT for c in db.chunks(player_commands.DETAILED)))
        self.assertTrue(player_commands.is_request("/commands"))
        self.assertTrue(player_commands.is_request(" /HELP "))
        self.assertFalse(player_commands.is_request("/commands please"))

    def test_from_discord_answered_without_the_gm(self):
        b, _ = make("queue")
        self.assertIsNone(b.on_message(msg(1, "/commands")))
        self.assertEqual(b.entries, [])
        flush(b)
        self.assertEqual(" ".join(b.io.posts).split(), player_commands.DETAILED.split())


class BridgedLoop(unittest.TestCase):
    def test_execute_table_talk_and_marker_through_the_loop(self):
        camp = camp_dir()
        t = table.Table(args(camp), token=TOKEN)
        t.render = table.Renderer(out=io.StringIO(), color=False)
        t.io_factory = FakeIO
        b = t.bridge_setup("queue")
        sent = []

        async def fake_send(text):
            sent.append(text)
            if text == "(OOC) turn the queue off":
                t.render.text("(OOC: done.)\n<<QUEUE off>>\n")
                t.render.end_message()
            return True
        t.send = fake_send
        t.inp = table.InputState(known={"gm"})
        lines = iter(["/table-talk snacks?", "/commands", "OOC: turn the queue off", "WAIT", ":quit"])

        def fake_input(prompt=""):
            try:
                line = next(lines)
            except StopIteration:
                raise EOFError
            if line == "WAIT":
                for _ in range(500):
                    if b.mode == "auto":
                        break
                    time.sleep(0.01)
                line = ":q"
            return line
        b.on_message(msg(41, "I check the trapdoor"))
        b.on_message(msg(42, "/execute-queue", author="ada_lace"))
        with mock.patch.object(table, "input", fake_input, create=True):
            async def go():
                t.start_bridge(b)
                return await t.run_bridged()
            self.assertEqual(asyncio.run(go()), 0)
        self.assertIn("Kira: I check the trapdoor", sent)          # sent by a player's /execute-queue
        self.assertNotIn("snacks?", " ".join(sent))
        self.assertIn("> (table talk) snacks?", b.io.posts)
        self.assertIn(player_commands.SHORT, b.io.posts)            # posted when the table opens
        self.assertIn("> OOC: turn the queue off", b.io.posts)
        self.assertEqual(b.mode, "auto")                            # the GM's <<QUEUE off>>
        self.assertIn("── Player commands ──", t.render.out.getvalue())


if __name__ == "__main__":
    unittest.main()
