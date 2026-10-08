"""The players' command list (docs/design/06 → Table client → Player commands).

`table.py` prints SHORT when the table opens (and posts it to Discord when the bridge is
on); `/commands` (or `/help`) at the console or on Discord shows DETAILED. Both are
answered by the client itself: they never reach the GM and cost no turn.
"""

SHORT = """\
── Player commands (/commands for details) ──
Kira: I check the trapdoor   act or speak as your character (add "rolled 16" to roll ahead)
(OOC: how far is the door?)  ask out of character, alone or after an action; /ooc … works too
/table-talk …   chat with the table; the GM never sees it (/tt for short)
/overrule …     retcon something or add a table rule
/spoilers …     ask about the secrets behind the screen, or a "what if"
/character …    make a character or change yours      /map   show the map
/end-session    wrap up and save                      !x     X-card: skip what just happened
Discord: /execute-queue sends the waiting queue · /queue on|off"""

DETAILED = """\
── Player commands ──

PLAYING
• Kira: I check the trapdoor
  Start a line with your character's name to act or speak as them. Your own name works
  if you play one character. Say what you try, not how it ends.
• Kira: I search the desk, rolled 16
  Roll ahead: give the die (or the total) and the GM answers straight away. Two dice if
  you think you have advantage.
• A line with no name is table talk to the GM: a question, a ruling, "what do I see?".

OUT OF CHARACTER
• Kira: I climb the wall (OOC: how long is our rope?)
  An OOC aside with an action: the GM resolves the action first, then answers the aside
  in parentheses at the bottom of the reply.
• (OOC: can we take a break after this fight?)   also: OOC: …  /ooc …  [ooc …]  ((…))
  A whole line out of character: the GM answers in parentheses and the story doesn't move.
  Ask for game things in plain words here too ("OOC: turn the queue off").

TABLE CHAT
• /table-talk pizza's here   (or /tt …)
  A message for the other players only. It never goes to the GM and costs no turn.

THE TABLE'S POWERS (honor system: typing it is the choice)
• /overrule <what>   Retcon something that happened, or add a table rule
                     ("/overrule Kira had the rope after all", "/overrule no crits on PCs tonight").
• /spoilers <question>   Ask about the secrets, or what would have happened if…
                     The answer shows between spoiler banners (hidden on Discord until clicked).
• !x                 X-card: the GM rewinds and steers away from what just happened, no questions.

CHARACTERS AND SESSIONS
• /character <description or sheet>   A new character, or a change to yours (gear, HP method…).
• /level-up          Level up when the GM says one is due.
• /map               The tactical map of the current fight or tense scene.
• /end-session       Wrap up: summary, world tick, save.
• /commands          This list (/help works too).

DISCORD
• Same as the console: start with your character's name, or just type if you play one PC.
• /execute-queue     Send everything waiting in the queue to the GM now. Add it to a line
                     ("I open the door /execute-queue") to send that line along with it.
• /queue on|off      Queue on: lines wait (the bot posts what's queued). Off: lines go to
                     the GM in batches as they come. Or ask the GM: "OOC: turn the queue off".
• Edit or delete your message before it's sent and the queue follows.
• ✅ sent · 🗑️ dropped · ✏️ edited by the host

HOST CONSOLE ONLY
• :as Kira  default speaker · :q  show the queue · :send (or empty Enter)  send it
• :edit 2 <text> · :drop 2 · :clear · :discord queue|auto|off · :gm-view on|off · :quit"""


def is_request(text):
    """True for `/commands` or `/help` (with nothing after it)."""
    return (text or "").strip().lower() in ("/commands", "/help")
