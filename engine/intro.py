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
`intro --why "<text>"` records the answer as that `Chosen:` line (the section is created
after `## Premise` when missing) and logs it.
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


def lines():
    n = sessions_played()
    first = n == 0
    out = banner.card(title(), "Our tale begins" if first else "Our tale continues")
    out.append(f"[INTRO {'first' if first else 'resume'} · session {n + 1}]")
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
    for line in lines():
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("intro", parents=[g], help='the title card, premise and why-you\'re-here; --why "…" records it')
    p.add_argument("--why", nargs="+")
    p.set_defaults(func=cmd_intro)
