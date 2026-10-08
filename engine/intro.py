"""`gm.py intro [--why "<the party's reason>"]` — the opening of a session (docs/design/02
→ Session start; 04 → Campaign file `## Why you're here`).

`intro` prints the title card (block letters; "Our tale begins" for the campaign's first
session, "Our tale continues" after that) for the GM to paste in a code block, then GM-only
bracket lines:
- `[INTRO first|resume · session N]`
- `[PREMISE] …`: the player-safe premise (campaign.md, else the active scenario)
- `[WHY …]`: why the party is here. `## Why you're here (player-safe)` in campaign.md
  (else the active scenario) holds `- ` bullets: one bullet is the reason; several are
  options the players choose from; none means the GM invents 2–4 that fit the premise
  and the opening and asks "Why are you here?". A `Chosen: …` line is the answer.
- `[TELL THE TABLE] …` (after the INTRO line; first session only, while `social-wall` is on; Phase 14): the
  one plain-words mention that repeated tries with an NPC can get easier.
`intro --why "<text>"` records the answer as that `Chosen:` line (the section is created
after `## Premise` when missing) and logs it.

How to play (02 → How to play; 06 → `intro`; Phase 16): at the first session, until it
has been given, `intro` opens with `[HOW TO PLAY]` lines (before the title card) for the
GM to say in table voice once the characters are settled: name prefixes, intent over
outcome, rolling ahead (example from a present PC; left out under `dice-mode:
gm-rolls-all`), asking anything, and the Discord line while `discord.md` has the bridge
on. It is logged once per campaign as `[intro] how to play given`, so a second `intro`
in session 1 doesn't repeat it. `intro --how-to-play [--for <PC>]` prints it on demand
(`--for`: the short version for a new player, addressed to them). The first session's
`[TELL THE TABLE]` lines also name the crit die while it's on (carousing is offered in the
fiction instead, once per tavern: `carouse --offer`).
"""
import re

from lib import banner, campaign, journal, md
from lib.errors import ToolError

WHY = "Why you're here (player-safe)"


class IntroError(ToolError):
    pass


def _section(doc, heading):
    span = doc.section(heading)
    if span is None:
        return None
    return [line for line in doc.body[span[0] + 1:span[1]] if not line.strip().startswith("<!--")]


def _scenario_docs():
    d = campaign.root() / "scenarios"
    docs = [md.load(p) for p in sorted(d.glob("*.md"))] if d.is_dir() else []
    active = [x for x in docs if str(x.front.get("status") or "").lower() == "active"]
    return active + [x for x in docs if x not in active]


def _sources():
    """Docs to read premise/why from, in order: campaign.md, then scenarios (active first)."""
    out = []
    p = campaign.campaign_doc_path()
    if p.exists():
        out.append(md.load(p))
    return out + _scenario_docs()


def title():
    for doc in _sources():
        name = doc.front.get("name")
        if name:
            return str(name)
    return campaign.root().name.replace("-", " ").title()


def premise():
    for doc in _sources():
        lines = _section(doc, "Premise")
        text = " ".join(x.strip() for x in lines or [] if x.strip())
        if text and not text.startswith("("):
            return text
    return ""


def why():
    """(doc, options, chosen) from the first source with a Why section, else (None, [], None)."""
    for doc in _sources():
        lines = _section(doc, "Why you")
        if lines is None:
            continue
        chosen = next((m.group(1).strip() for x in lines
                       for m in [re.match(r"^\s*Chosen:\s*(.+)$", x)] if m), None)
        options = []
        for x in lines:
            if re.match(r"^\s*[-*]\s+\S", x):
                options.append(re.sub(r"^\s*[-*]\s+", "", x).strip())
            elif options and x.startswith((" ", "\t")) and x.strip():   # a wrapped bullet
                options[-1] += " " + x.strip()
        return doc, options, chosen
    return None, [], None


def sessions_played():
    d = campaign.root() / "sessions" / "history"
    return len(list(d.glob("session-*.md"))) if d.is_dir() else 0


def record(text):
    text = " ".join(str(text).split())
    if not text:
        raise IntroError('intro --why "<the party\'s reason for being here>"')
    doc, _, _ = why()
    if doc is None:
        sources = _sources()
        if not sources:
            raise IntroError("intro --why: no campaign.md and no scenario file to record it in")
        doc = sources[0]
        span = doc.section("Premise")
        at = span[1] if span else len(doc.body)
        while at > 0 and not doc.body[at - 1].strip():
            at -= 1
        doc.body[at:at] = ["", f"## {WHY}", f"Chosen: {text}"]
    else:
        start, end = doc.section("Why you")
        for i in range(start + 1, end):
            if re.match(r"^\s*Chosen:", doc.body[i]):
                doc.body[i] = f"Chosen: {text}"
                break
        else:
            doc.body.insert(start + 1, f"Chosen: {text}")
    doc.save()
    journal.log_delta(f"why we're here: {text}")
    return f"[intro: why you're here → {text}]"


# ---------- how to play (Phase 16) ----------

GIVEN = "[intro] how to play given"


def _given():
    """True once `[intro] how to play given` is in the session log or the history."""
    root = campaign.root() / "sessions"
    paths = [campaign.session_log_path()] + (sorted((root / "history").glob("*.md")) if root.is_dir() else [])
    for p in paths:
        try:
            if GIVEN in p.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def _example_pc(want=None):
    pcs = [d for d in campaign.pcs() if d.front.get("present") is not False]
    if want:
        c = campaign.resolve(want)
        if not c.is_pc:
            raise IntroError(f"intro --for: {c.name} is not a PC")
        return c.name.split()[0]
    return str(pcs[0].front.get("name")).split()[0] if pcs else "Kira"


def _discord_on():
    p = campaign.root() / "discord.md"
    if not p.exists():
        return False
    return str(md.load(p).front.get("discord") or "off").strip().lower() in ("queue", "auto")


def how_to_play(for_pc=None):
    """The [HOW TO PLAY] lines (02 → How to play): the full talk, or the short one for a
    new player (`for_pc`)."""
    from lib import resolve
    rolls = resolve.dice_mode(campaign.load_state().front) != "gm-rolls-all"
    who = _example_pc(for_pc)
    if for_pc:
        out = [f"[HOW TO PLAY for {who}] (short, to the new player, in table voice) Start a line with "
               f"\"{who}:\" when it's your character speaking or acting; no name is table talk. Say what "
               "you try, not how it ends."]
        if rolls:
            out.append(f"[HOW TO PLAY for {who}] Roll ahead if you like: \"{who}: I search the desk, rolled "
                       "16\". The die or the total is fine; I'll use the right skill. Ask me anything, any time.")
        else:
            out.append(f"[HOW TO PLAY for {who}] I roll the dice. Ask me anything, any time.")
        if _discord_on():
            out.append(f"[HOW TO PLAY for {who}] On Discord it's the same: start with your character's name.")
        return out
    out = ["[HOW TO PLAY] (say it in your own table voice once the characters are settled, before the "
           "title card: six lines at most, one example each)",
           f"[HOW TO PLAY] Speak as your character: start the line with their name, \"{who}: I check the "
           "trapdoor.\" Your own name works too if you play one character. A line with no name is table "
           "talk: questions for me, or chatter among yourselves.",
           "[HOW TO PLAY] Say what you try, not how it ends: \"I try to pick the lock\", not \"I pick the lock "
           "and grab the ledger.\" I'll tell you when something needs a roll."]
    if rolls:
        out.append(f"[HOW TO PLAY] Roll ahead to save time: \"{who}: I search the desk, rolled 16\" gets an "
                   f"answer straight away; \"{who}: I search the desk\" works too, and I'll ask for the roll. "
                   "The number on the die or the total, either is fine, and don't worry about naming the "
                   "right skill. If you might have advantage, roll two dice and give both.")
    out.append("[HOW TO PLAY] Ask anything: what your character sees, knows or remembers, and how a rule "
               "works. Questions about your own character always get a straight answer. Out of character, wrap it: "
               "\"Kira: I climb (OOC: how long is our rope?)\" or a whole line \"(OOC: …)\". /commands lists everything "
               "you can type.")
    if _discord_on():
        out.append("[HOW TO PLAY] On Discord it's the same: start with your character's name; /table-talk is chat I never see, "
                   "and /execute-queue sends what's waiting.")
    return out


def tell_the_table():
    """The first session's [TELL THE TABLE] lines for settings that change play."""
    out = []
    import social
    tell = social.intro_line()   # the social wall is mentioned once, plainly (Phase 14)
    if tell:
        out.append(tell)
    s = campaign.settings()
    if str(s.get("crit-die", "off")).lower() == "on":
        out.append("[TELL THE TABLE] crit die on: a critical hit rolls on a table instead of just doubling "
                   "the dice, for monsters too, and its worst face can kill outright")
    return out


def _log_given():
    if not _given():
        journal.log_delta(GIVEN)


def lines():
    n = sessions_played()
    first = n == 0
    out = []
    if first and not _given():   # the how-to-play talk, once per campaign (Phase 16)
        out += how_to_play()
        _log_given()
    out += banner.card(title(), "Our tale begins" if first else "Our tale continues")
    out.append(f"[INTRO {'first' if first else 'resume'} · session {n + 1}]")
    if first:
        out += tell_the_table()
    import split
    resume = split.resume_line()
    if resume:
        out.append(resume)
    p = premise()
    out.append(f"[PREMISE] {p}" if p else "[PREMISE] (none written: use the scenario and the opening scene)")
    _, options, chosen = why()
    if chosen:
        out.append(f"[WHY chosen] {chosen}")
    elif len(options) == 1:
        out.append(f"[WHY fixed] {options[0]}")
    elif options:
        out.append("[WHY options] " + " | ".join(f"{i}. {o}" for i, o in enumerate(options, 1)))
    else:
        out.append("[WHY none] the premise says why? use it. Else invent 2-4 reasons that fit "
                   "the premise and the opening, and ask the table")
    return out


def cmd_intro(ctx):
    a = ctx.args
    if a.why:
        ctx.emit(record(" ".join(a.why)))
        return
    if a.how_to_play or a.for_:
        for line in how_to_play(a.for_):
            ctx.emit(line)
        if not a.for_:
            _log_given()
        return
    for line in lines():
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("intro", parents=[g], help='the title card, premise and why-you\'re-here; --why "…" records it')
    p.add_argument("--why", nargs="+")
    p.add_argument("--how-to-play", dest="how_to_play", action="store_true",
                   help="the how-to-play talk on demand (Phase 16)")
    p.add_argument("--for", dest="for_", help="with --how-to-play: the short version for a new player's PC")
    p.set_defaults(func=cmd_intro)
