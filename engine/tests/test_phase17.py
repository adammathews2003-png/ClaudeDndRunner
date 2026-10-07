"""Phase 17: the Discord bridge (plan.md Phase 17 → Verify and Guards; 06 → Table client →
Discord bridge; 04 → discord.md). Everything runs against fakes: a fake Discord I/O,
an injected clock, and a fake `claude_agent_sdk` for the GM-view check. No network."""
import argparse
import asyncio
import io
import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from fixture import TOOLS
import discord_bridge as db
import table

TOKEN = "MTIz.fake-token-for-tests.abcdefXYZ"
db.TOKEN_FILE = Path(tempfile.gettempdir()) / "gm-no-such-dir" / "discord-token"   # never the host's real token
CHAN = 123456789012345678

DISCORD_MD = ("---\ndiscord: queue          # off | queue | auto\nchannel: 123456789012345678\n"
              "debounce: 4             # auto mode: seconds of quiet before a batch is sent\n---\n"
              "| discord user | player |\n|--------------|--------|\n| sam_the_bard | Sam    |\n"
              "| ada_lace     | Ada    |\n| 99887766     | Bo     |\n")


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class FakeIO:
    """The bridge's I/O interface with no network."""

    def __init__(self, token=None, bridge=None, fail_post=False, run_errors=()):
        self.ready = True
        self.posts = []
        self.reactions = []
        self.closed = False
        self.fail_post = fail_post
        self.run_errors = list(run_errors)
        self.runs = 0

    async def run(self):
        self.runs += 1
        if self.run_errors:
            raise self.run_errors.pop(0)
        self.ready = True
        while not self.closed:              # one connection's lifetime, like discord.py's start()
            await asyncio.sleep(0.01)

    async def post(self, text):
        if self.fail_post:
            raise RuntimeError(f"HTTP 401 with token {TOKEN}")
        self.posts.append(text)

    async def react(self, msg_id, emoji):
        self.reactions.append((msg_id, emoji))

    async def close(self):
        self.closed = True


def camp_dir():
    d = Path(tempfile.mkdtemp(prefix="gm-discord-"))
    (d / "pcs").mkdir()
    (d / "pcs" / "kira.md").write_text("---\nname: Kira Thornwood\nplayer: Sam\npresent: true\n---\n", encoding="utf-8")
    (d / "pcs" / "kael.md").write_text("---\nname: Kael Ashford\nplayer: Ada\n---\n", encoding="utf-8")
    (d / "pcs" / "bren.md").write_text("---\nname: Bren Hollow\nplayer: Ada\n---\n", encoding="utf-8")
    (d / "pcs" / "_template.md").write_text("---\nname:\nplayer: Sam\n---\n", encoding="utf-8")
    (d / "discord.md").write_text(DISCORD_MD, encoding="utf-8")
    return d


def make(mode="queue", clock=None, interpret=None, io_=None):
    camp = camp_dir()
    cfg = db.load_config(camp)
    cfg.mode = mode
    notices = []
    b = db.Bridge(cfg, io=io_ or FakeIO(), notice=notices.append, interpret=interpret,
                  pcs=lambda: db.player_pcs(camp), clock=clock or Clock(), token=TOKEN)
    return b, notices


def msg(i, text, author="sam_the_bard", channel=CHAN, **kw):
    return db.Incoming(id=i, author=author, text=text, channel_id=channel, **kw)


def flush(b):
    asyncio.run(b.flush_out())


class Config(unittest.TestCase):
    def test_reads_the_04_example_crlf_and_lf(self):
        for nl in ("\n", "\r\n"):
            d = Path(tempfile.mkdtemp())
            (d / "discord.md").write_bytes(DISCORD_MD.replace("\n", nl).encode("utf-8"))
            cfg = db.load_config(d)
            self.assertEqual((cfg.mode, cfg.channel, cfg.debounce), ("queue", CHAN, 4.0))
            self.assertEqual(cfg.users, {"sam_the_bard": "Sam", "ada_lace": "Ada", "99887766": "Bo"})
            self.assertEqual(cfg.problems, [])

    def test_missing_and_bad(self):
        self.assertIsNone(db.load_config(Path(tempfile.mkdtemp())))
        d = Path(tempfile.mkdtemp())
        (d / "discord.md").write_text("---\ndiscord: loud\nchannel: general\ndebounce: soon\n---\n", encoding="utf-8")
        cfg = db.load_config(d)
        self.assertEqual((cfg.mode, cfg.channel, cfg.debounce), ("off", 0, 4.0))
        self.assertEqual(len(cfg.problems), 3)

    def test_speaker_resolution(self):
        camp = camp_dir()
        pcs = db.player_pcs(camp)
        self.assertEqual(pcs, {"sam": ["Kira"], "ada": ["Bren", "Kael"]})
        self.assertEqual(db.speaker_line("I check the trapdoor", "Sam", pcs), "Kira: I check the trapdoor")
        self.assertEqual(db.speaker_line("Kael: I follow", "Ada", pcs), "Kael: I follow")
        self.assertEqual(db.speaker_line("which of us is hurt?", "Ada", pcs), "(Ada, table talk) which of us is hurt?")
        self.assertEqual(db.speaker_line("hi", "Bo", pcs), "(Bo, table talk) hi")


class Queue(unittest.TestCase):
    def test_order_edit_drop_submit_as_one_prompt(self):
        b, notices = make("queue")
        b.on_message(msg(11, "I check the trapdoor (rolled 15)"))
        b.on_message(msg(12, "Kael: I watch the stairs", author="ada_lace"))
        b.host_line("Bren: I hold the lantern high")
        b.on_message(msg(13, "Kael: never mind", author="ada_lace"))
        self.assertIn("[Q1 sam_the_bard] Kira: I check the trapdoor (rolled 15)", notices)
        self.assertEqual([e.n for e in b.entries], [1, 2, 3, 4])
        self.assertIn("[Q2 ada_lace] Kael: I watch the stairs carefully", b.edit(2, "Kael: I watch the stairs carefully"))
        self.assertEqual(b.drop(4), "[dropped Q4]")
        self.assertEqual(b.listing(), ["[Q1 sam_the_bard] Kira: I check the trapdoor (rolled 15)",
                                       "[Q2 ada_lace] Kael: I watch the stairs carefully",
                                       "[Q3 host] Bren: I hold the lantern high"])
        self.assertEqual(b.take(), ["Kira: I check the trapdoor (rolled 15)\nKael: I watch the stairs carefully\n"
                                    "Bren: I hold the lantern high"])
        self.assertEqual(b.entries, [])
        flush(b)
        self.assertEqual(b.io.reactions, [(12, db.EDITED), (13, db.DROPPED), (11, db.SENT), (12, db.SENT)])
        b.on_message(msg(14, "again"))
        self.assertEqual(b.entries[0].n, 1)       # numbering restarts on an empty queue

    def test_discord_edit_and_delete_mirrored(self):
        b, notices = make("queue")
        b.on_message(msg(21, "I open the door"))
        b.on_message(msg(22, "I wait"))
        b.on_edit(21, "I kick the door")
        self.assertEqual(notices[-1], "[Q1 sam_the_bard] Kira: I kick the door (edited)")
        b.on_delete(22)
        self.assertEqual(b.take(), ["Kira: I kick the door"])

    def test_clear(self):
        b, _ = make("queue")
        b.on_message(msg(1, "a"))
        b.on_message(msg(2, "b"))
        self.assertIn("2 dropped", b.clear())
        flush(b)
        self.assertEqual(b.io.reactions, [(1, db.DROPPED), (2, db.DROPPED)])

    def test_slash_and_bang_lines_are_prompts_of_their_own(self):
        b, _ = make("queue", interpret=lambda t: t)
        b.on_message(msg(1, "I duck"))
        b.on_message(msg(2, "/overrule Kira wasn't seen"))
        b.on_message(msg(3, "Kael: I swing", author="ada_lace"))
        self.assertTrue(b.entries[1].flagged)
        self.assertIn("⚑", b.entries[1].show())
        self.assertEqual(b.take(), ["Kira: I duck", "/overrule Kira wasn't seen", "Kael: I swing"])

    def test_colon_commands_from_discord_ignored(self):
        b, _ = make("queue")
        b.on_message(msg(1, ":quit"))
        b.on_message(msg(2, ":discord off"))
        self.assertEqual((b.entries, b.mode), ([], "queue"))


class Auto(unittest.TestCase):
    def test_debounce_with_an_injected_clock(self):
        clock = Clock()
        b, _ = make("auto", clock=clock)
        b.on_message(msg(1, "I search the desk"))
        self.assertFalse(b.due())
        self.assertEqual(b.wait_time(), 4.0)
        clock.t += 3
        b.on_message(msg(2, "Kael: I keep watch", author="ada_lace"))
        clock.t += 3.9
        self.assertFalse(b.due())                 # 3.9 s since the last line
        clock.t += 0.1
        self.assertTrue(b.due())
        self.assertEqual(b.take(everything=False), ["Kira: I search the desk\nKael: I keep watch"])
        self.assertIsNone(b.wait_time())

    def test_lines_during_a_reply_go_when_it_ends(self):
        clock = Clock()
        b, _ = make("auto", clock=clock)
        b.busy = True
        b.on_message(msg(1, "I dodge"))
        b.on_message(msg(2, "Kael: I parry", author="ada_lace"))
        self.assertFalse(b.due())                 # the GM is still talking
        b.busy = False
        self.assertTrue(b.due())                  # no debounce wait after the reply
        self.assertEqual(b.take(everything=False), ["Kira: I dodge\nKael: I parry"])

    def test_host_lines_join_the_batch_and_send_it(self):
        clock = Clock()
        b, _ = make("auto", clock=clock)
        b.on_message(msg(1, "I dodge"))
        b.host_line("Bren: I shove him")
        self.assertTrue(b.due())
        self.assertEqual(b.take(everything=False), ["Kira: I dodge\nBren: I shove him"])

    def test_slash_from_discord_queues_in_auto_mode(self):
        clock = Clock()
        b, notices = make("auto", clock=clock, interpret=lambda t: t)
        b.on_message(msg(1, "/overrule the guard can't have seen me"))
        clock.t += 60
        self.assertFalse(b.due())                 # flagged lines never go by themselves
        self.assertIsNone(b.wait_time())
        self.assertIn("[Q1 sam_the_bard ⚑] /overrule the guard can't have seen me", notices)
        b.on_message(msg(2, "I hide"))
        clock.t += 5
        self.assertEqual(b.take(everything=False), ["Kira: I hide"])
        self.assertEqual(b.listing(), ["[Q1 sam_the_bard ⚑] /overrule the guard can't have seen me"])
        self.assertEqual(b.take(everything=True), ["/overrule the guard can't have seen me"])

    def test_unknown_slash_is_interpreted_like_the_console(self):
        inp = table.InputState(known={"overrule"})
        b, _ = make("auto", interpret=lambda t: inp.handle(t)[1])
        b.on_message(msg(1, "/rest long"))
        self.assertIn("a player typed `/rest long`", b.entries[0].prompt)
        self.assertTrue(b.entries[0].flagged)

    def test_mode_switch(self):
        b, _ = make("queue")
        self.assertEqual(b.set_mode("auto"), "[discord: auto]")
        self.assertEqual(b.set_mode("loud"), "[:discord queue|auto|off]")
        b.set_mode("off")
        b.on_message(msg(1, "hello?"))
        self.assertEqual(b.entries, [])
        flush(b)
        self.assertEqual(b.io.posts, [db.CLOSED_POST])
        b.set_mode("queue")
        flush(b)
        self.assertEqual(b.io.posts[-1], db.OPEN_POST)


class Both(unittest.TestCase):
    def test_x_card_bypasses_the_queue(self):
        for mode in ("queue", "auto"):
            b, _ = make(mode)
            b.on_message(msg(1, "I open the box"))
            b.on_message(msg(2, "!x"))
            self.assertEqual([e.text for e in b.entries], ["I open the box"])
            self.assertEqual(b.take_urgent(), ["!x"])
            flush(b)
            self.assertEqual(b.io.reactions, [(2, db.SENT)])
            self.assertEqual(b.take_urgent(), [])

    def test_unmapped_dm_bot_and_other_channels_ignored(self):
        b, notices = make("queue")
        b.on_message(msg(1, "let me in", author="sam"))
        b.on_message(msg(2, "again", author="sam"))
        self.assertEqual(notices.count("[discord: ignoring @sam (not on the map)]"), 1)
        b.on_message(msg(3, "hi", channel=42))
        b.on_message(msg(4, "hi", dm=True))
        b.on_message(msg(5, "hi", bot=True))
        self.assertEqual(b.entries, [])
        b.on_message(msg(6, "hi", author="someone", author_id=99887766))   # mapped by id
        self.assertEqual(b.entries[0].prompt, "(Bo, table talk) hi")


class Output(unittest.TestCase):
    def pipe(self, mode="queue"):
        b, _ = make(mode)
        r = table.Renderer(out=io.StringIO(), color=False)
        r.tee = b.feed
        return b, r

    def test_long_reply_posts_as_three_chunks(self):
        b, r = self.pipe()
        words = ("The rain hammers the mill roof. " * 200)[:4500]
        r.text(words + "\n")
        r.end_message()
        flush(b)
        self.assertEqual(len(b.io.posts), 3)
        self.assertTrue(all(len(p) <= 2000 for p in b.io.posts))
        self.assertEqual(" ".join(b.io.posts).split(), words.split())

    def test_paragraphs_post_as_they_finish(self):
        b, r = self.pipe()
        r.text("The door opens.\n[Kira: d20 12+5=17 vs DC 15 — SUCCESS]\n\nMara looks up.")
        self.assertEqual(b.outbox, [("post", "The door opens.\n[Kira: d20 12+5=17 vs DC 15 — SUCCESS]")])
        r.end_message()
        self.assertEqual(b.outbox[-1], ("post", "Mara looks up."))

    def test_spoiler_banner_posts_inside_spoiler_bars(self):
        b, r = self.pipe()
        r.text("Sure.\n<<SPOILERS major/answer>>\nVeskar is the buyer.\n<<END SPOILERS>>\nBack to it.\n")
        r.end_message()
        flush(b)
        self.assertEqual(b.io.posts, ["Sure.", "── SPOILERS · major · answer ──\n||Veskar is the buyer.||", "Back to it."])

    def test_unbalanced_spoiler_still_hidden(self):
        b, r = self.pipe()
        r.text("<<SPOILERS major/full>>\nthe truth is")
        r.end_message()
        flush(b)
        self.assertEqual(b.io.posts, ["── SPOILERS · major · full ──\n||the truth is||"])

    def test_map_posts_in_a_code_block(self):
        b, r = self.pipe()
        r.text("Here:\n```\n  35 │ . K │\n  30 │ . . │\n```\nOn.\n")
        r.end_message()
        flush(b)
        self.assertEqual(b.io.posts, ["Here:", "```\n  35 │ . K │\n  30 │ . . │\n```", "On."])

    def test_notices_stay_on_the_terminal(self):
        b, r = self.pipe()
        r.activity()
        r.notice("[saved]")
        r.text("<<STAGE /end-session>>\n")
        r.end_message()
        self.assertEqual(b.outbox, [])

    def test_nothing_posts_while_off(self):
        b, r = self.pipe("off")
        r.text("hello\n")
        r.end_message()
        self.assertEqual(b.outbox, [])


# ---------- the client: a fake claude_agent_sdk for _turn ----------

def fake_sdk():
    sdk = types.ModuleType("claude_agent_sdk")
    tps = types.ModuleType("claude_agent_sdk.types")

    def cls(_type, **defaults):
        def init(self, **kw):
            for k, v in {**defaults, **kw}.items():
                setattr(self, k, v)
        return type(_type, (), {"__init__": init})
    sdk.StreamEvent = cls("StreamEvent", parent_tool_use_id=None, event=None)
    sdk.AssistantMessage = cls("AssistantMessage", parent_tool_use_id=None, content=())
    sdk.UserMessage = cls("UserMessage", content=())
    sdk.SystemMessage = cls("SystemMessage", subtype="", data=None)
    sdk.ResultMessage = cls("ResultMessage", session_id=None, num_turns=1, total_cost_usd=0)
    tps.TextBlock = cls("TextBlock", text="")
    tps.ThinkingBlock = cls("ThinkingBlock", thinking="")
    tps.ToolResultBlock = cls("ToolResultBlock", content="")
    tps.ToolUseBlock = cls("ToolUseBlock", name="", input=None)
    sdk.types = tps
    return sdk, tps


class FakeClient:
    def __init__(self, msgs):
        self.msgs = msgs
        self.prompts = []

    async def query(self, text):
        self.prompts.append(text)

    async def receive_response(self):
        for m in self.msgs:
            yield m


def args(camp, **kw):
    return argparse.Namespace(campaign=str(camp), new=False, model=None, gm_view=kw.get("gm_view", False),
                              discord=kw.get("discord"))


class Client(unittest.TestCase):
    def table_with_bridge(self, gm_view=False, mode="queue"):
        camp = camp_dir()
        t = table.Table(args(camp, gm_view=gm_view), token=TOKEN)
        t.render = table.Renderer(out=io.StringIO(), color=False)
        t.io_factory = FakeIO
        b = t.bridge_setup(mode)
        self.assertIsNotNone(b)
        t.bridge = b
        t.public = table.Renderer(out=table._Null(), color=False)
        t.public.tee = b.feed
        return t, b

    def run_turn(self, t, msgs):
        sdk, tps = fake_sdk()
        with mock.patch.dict(sys.modules, {"claude_agent_sdk": sdk, "claude_agent_sdk.types": tps}):
            t.client = FakeClient(msgs(sdk, tps))
            asyncio.run(t._turn("Kira: I read the ledger"))
        flush(t.bridge)
        return t.render.out.getvalue(), "\n".join(t.bridge.io.posts)

    def test_gm_view_never_reaches_the_channel(self):
        def msgs(sdk, tps):
            S = sdk.StreamEvent
            return [
                S(event={"type": "content_block_start", "content_block": {"type": "text"}}),
                S(event={"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Let me check the brief."}}),
                S(event={"type": "content_block_start", "content_block": {"type": "tool_use"}}),
                sdk.AssistantMessage(content=[tps.TextBlock(text="Let me check the brief."),
                                              tps.ToolUseBlock(name="Bash", input={"command": "python engine/gm.py brief"}),
                                              tps.ThinkingBlock(thinking="SECRET-THINKING Veskar is the buyer")]),
                sdk.UserMessage(content=[tps.ToolResultBlock(content="SECRET-RESULT Truth: Veskar")]),
                sdk.SystemMessage(subtype="hook_response", data={"hook_name": "UserPromptSubmit", "output": "SECRET-BRIEF"}),
                S(event={"type": "content_block_start", "content_block": {"type": "text"}}),
                S(event={"type": "content_block_delta", "delta": {"type": "text_delta",
                                                                  "text": "The ledger is water-stained.\n\nOne name is scratched out."}}),
                S(event={"type": "message_stop"}),
                sdk.ResultMessage(session_id="sid-1", num_turns=3, total_cost_usd=0.01),
            ]
        t, b = self.table_with_bridge(gm_view=True)
        term, posted = self.run_turn(t, msgs)
        for secret in ("SECRET-THINKING", "SECRET-RESULT", "SECRET-BRIEF", "Let me check"):
            self.assertIn(secret, term)            # the host's GM view shows it…
            self.assertNotIn(secret, posted)       # …the channel never does
        self.assertNotIn("[gm-view]", posted)
        self.assertNotIn("gm.py", posted)
        self.assertIn("The ledger is water-stained.", posted)
        self.assertIn("One name is scratched out.", posted)

    def test_non_streamed_text_and_activity(self):
        def msgs(sdk, tps):
            return [sdk.AssistantMessage(content=[tps.TextBlock(text="Checking."), tps.ToolUseBlock(name="Bash", input={})]),
                    sdk.AssistantMessage(content=[tps.TextBlock(text="Dust everywhere.")]),
                    sdk.ResultMessage(session_id="sid-2")]
        t, b = self.table_with_bridge()
        term, posted = self.run_turn(t, msgs)
        self.assertEqual(b.io.posts, ["Dust everywhere."])
        self.assertNotIn(table.ACTIVITY, posted)

    def test_bridged_loop_queue_mode(self):
        """Keyboard lines, a Discord line, the empty Enter, a staged command and :quit,
        end to end through run_bridged with the GM faked."""
        t, b = self.table_with_bridge()
        sent = []

        async def fake_send(text):
            sent.append(text)
            if text.startswith("Kira"):
                t.render.staged.append("/end-session")
            return True
        t.send = fake_send
        t.inp = table.InputState(known={"gm", "overrule", "end-session"})
        lines = iter([":as Bren", "I hold the lantern", ":q", ":drop 9", "", "n", "!x", ":discord auto", ":quit"])

        def fake_input(prompt=""):
            try:
                return next(lines)
            except StopIteration:
                raise EOFError
        b.on_message(msg(31, "I check the trapdoor"))
        with mock.patch.object(table, "input", fake_input, create=True):
            async def go():
                t.start_bridge(b)
                return await t.run_bridged(first=["/gm"])
            self.assertEqual(asyncio.run(go()), 0)
        self.assertEqual(sent[0], "/gm")
        self.assertIn("Kira: I check the trapdoor\nBren: I hold the lantern", sent)
        self.assertIn("!x", sent)
        self.assertNotIn("/end-session", sent)         # the host said n
        out = t.render.out.getvalue()
        self.assertIn("[Q2 host] Bren: I hold the lantern", out)
        self.assertIn("[no Q9]", out)
        self.assertIn("Run /end-session? [y/N]", out)
        self.assertIn("[not run]", out)
        self.assertIn("[discord: auto]", out)
        self.assertIn(db.OPEN_POST, b.io.posts)
        self.assertEqual(b.io.posts[-1], db.CLOSED_POST)
        self.assertIn((31, db.SENT), b.io.reactions)
        self.assertTrue(b.io.closed)


class Guards(unittest.TestCase):
    def test_token_from_the_environment_or_the_local_file(self):
        env = {db.TOKEN_ENV: f" {TOKEN} "}
        self.assertEqual(db.take_token(env), TOKEN)
        self.assertNotIn(db.TOKEN_ENV, env)       # the GM's session never inherits it
        self.assertEqual(db.take_token({}), "")
        f = Path(tempfile.mkdtemp(prefix="gm-tok-")) / "discord-token"
        f.write_text("# paste the bot token on the next line\n\n  other-token  \n", encoding="utf-8")
        self.assertEqual(db.take_token({}, f), "other-token")
        self.assertEqual(db.take_token({db.TOKEN_ENV: TOKEN}, f), TOKEN)  # the variable wins
        with mock.patch.dict(os.environ, {db.TOKEN_ENV: TOKEN}):
            t = table.Table(args(camp_dir()))
            self.assertEqual(t.token, TOKEN)
            self.assertNotIn(db.TOKEN_ENV, os.environ)

    def test_token_never_in_a_log_or_notice(self):
        camp = camp_dir()
        t = table.Table(args(camp), token=TOKEN)
        t.render = table.Renderer(out=io.StringIO(), color=False)
        t.io_factory = lambda token, b: FakeIO(fail_post=True, run_errors=[
            OSError(f"connect failed for Bot {TOKEN}"), db.BridgeFatal(f"login failed ({TOKEN})")])
        b = t.bridge_setup("queue")
        b.post("hello")

        async def go():
            await b.connect_loop(sleep=lambda s: asyncio.sleep(0))
            b.io.ready = True
            b.mode = "queue"
            b.post("again")
            await b.flush_out()
        asyncio.run(go())
        t._log_error(RuntimeError(f"SDK said {TOKEN}"))
        log = (camp / ".gm" / "client.log").read_text(encoding="utf-8")
        out = t.render.out.getvalue()
        self.assertIn("[token]", log)
        self.assertIn("[discord: disconnected — retrying]", out)
        self.assertIn("the table carries on without Discord", out)
        self.assertTrue(b.dead)
        for text in (log, out):
            self.assertNotIn(TOKEN, text)
        for p in camp.rglob("*"):
            if p.is_file():
                self.assertNotIn(TOKEN, p.read_text(encoding="utf-8", errors="ignore"), p)

    def test_no_code_stores_the_token(self):
        for name in ("table.py", "discord_bridge.py"):
            src = (TOOLS / name).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"environ\[[^\]]*TOKEN", src), [], name)
        src = (TOOLS / "discord_bridge.py").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"\.pop\(TOKEN_ENV", src)), 1)   # read once, by take_token
        self.assertNotIn("token", DISCORD_MD.lower())

    def test_missing_token_package_or_channel_runs_without_discord(self):
        camp = camp_dir()
        t = table.Table(args(camp), token="")
        t.render = table.Renderer(out=io.StringIO(), color=False)
        self.assertIsNone(t.bridge_setup("queue"))
        self.assertIn("DND_DISCORD_TOKEN environment variable isn't set", t.render.out.getvalue())
        t.token = TOKEN
        with mock.patch.object(db, "library_available", lambda: False):
            self.assertIsNone(t.bridge_setup("queue"))
        self.assertIn("pip install discord.py", t.render.out.getvalue())
        (camp / "discord.md").unlink()
        self.assertIsNone(t.bridge_setup("auto"))
        self.assertIsNone(t.bridge_setup(None))         # no file, no flag: silently off
        self.assertIn("no " + camp.name + "/discord.md", t.render.out.getvalue())

    def test_bridge_adds_no_permissions(self):
        src = (TOOLS / "discord_bridge.py").read_text(encoding="utf-8")
        for word in ("can_use_tool", "allowed_tools", "permission", "HookMatcher", "decide("):
            self.assertNotIn(word, src)
        # a Discord line is only ever a prompt string: an unknown slash is wrapped exactly as typed at the console
        inp = table.InputState(known={"overrule"})
        b, _ = make("queue", interpret=lambda t: inp.handle(t)[1])
        b.on_message(msg(1, "/allow Bash(*)"))
        self.assertEqual(b.take(), [table.INTERPRET.format(text="/allow Bash(*)")])
        self.assertEqual(table.ALLOWED, [f"{s}({p} engine/{g}.py:*)" for s in ("Bash", "PowerShell")
                                         for p in ("python", "py") for g in ("gm", "space")])

    def test_a_failing_bridge_never_stops_the_console(self):
        b, _ = make("queue", io_=FakeIO(fail_post=True))
        b.log = lambda text: None
        r = table.Renderer(out=io.StringIO(), color=False)
        r.tee = b.feed
        r.text("The fire crackles.\n")
        r.end_message()
        flush(b)                                  # the post fails: logged, not raised
        self.assertEqual(r.out.getvalue(), "The fire crackles.\n")
        r.tee = lambda *a: 1 / 0                  # even a broken tee can't stop the console
        r.text("Still here.\n")
        self.assertIn("Still here.", r.out.getvalue())
        self.assertIsNone(b.on_message(None))      # a malformed event is swallowed

    def test_discord_library_import_is_optional(self):
        src = (TOOLS / "discord_bridge.py").read_text(encoding="utf-8")
        top = [l for l in src.splitlines() if re.match(r"^(import|from) ", l)]
        self.assertFalse([l for l in top if "discord" in l], top)
        self.assertTrue(all(re.match(r"^(import (asyncio|os|re|time)|from (dataclasses|pathlib) import)", l) for l in top), top)
        tsrc = (TOOLS / "table.py").read_text(encoding="utf-8")
        self.assertNotRegex(tsrc, r"(?m)^\s*import discord\b")

    def test_intro_discord_line_follows_discord_md(self):
        from lib import campaign
        camp = camp_dir()
        (camp / "state").mkdir()
        campaign.set_override(str(camp))
        try:
            import intro
            self.assertTrue(intro._discord_on())
        finally:
            campaign.set_override(None)


if __name__ == "__main__":
    unittest.main()
