"""Faction renown (docs/design/02 → Table mechanics → Phase 15 → Faction renown; 04 →
`state/factions.md`; 06 → Table mechanics → Phase 15; plan.md Phase 15 item 9).

    renown "Red Ledger" +1 "returned the ledger" [--who Kira] [--rank "Initiate"]
    renown "Red Ledger" =3 "…" | renown                 (the standings)

`renown: off | party | per-pc` (default off; the command refuses while off). Standings
live in `state/factions.md` (`| faction | renown | rank | who | notes |`; `who` = party
or a PC's first name; `rank` is the campaign's free text; `notes` keeps the last
reason). Every change is a public log line with its reason. An NPC names its faction
with `faction: red-ledger` (the faction's slug). Its attitude toward the party is
shifted one step warmer at renown 3 or more and one step colder below 0; that shifted
attitude is what the brief shows (`Mara (wary→neutral, Red Ledger 3)`) and what the
social DC table reads (social.py). Under `per-pc` the social check uses the checking
PC's standing; the brief shows each PC's shifted attitude when they differ.

Python API: `shift(npc_front, attitude, pc=None)` -> (attitude, note).
"""
import re

from lib import campaign, journal, md
from lib import social as socialdata
from lib.errors import ToolError
import mutations

COLS = ["faction", "renown", "rank", "who", "notes"]
WARM_AT = 3


class RenownError(ToolError):
    pass


def setting():
    return str(campaign.settings().get("renown", "off")).strip().lower()


def path():
    return campaign.root() / "state" / "factions.md"


def _load():
    p = path()
    if p.exists():
        return md.load(p)
    return md.new(p, "# Factions\n\n| " + " | ".join(COLS) + " |\n|" + "|".join("-" * (len(c) + 2) for c in COLS) + "|\n")


def standings():
    p = path()
    if not p.exists():
        return []
    t = md.load(p).table("Factions")
    return [r for r in (t.rows if t else []) if r.get("faction", "").strip()]


def renown_of(faction_slug, who="party"):
    for r in standings():
        if campaign.slugify(r["faction"]) == faction_slug and r.get("who", "party").strip().lower() == who.lower():
            try:
                return int(r.get("renown") or 0), r["faction"]
            except ValueError:
                return 0, r["faction"]
    return None, None


def warmer(att):
    i = socialdata.ATTITUDES.index(socialdata.attitude(att))
    return socialdata.ATTITUDES[max(0, i - 1)]


def shift(front, att, pc=None):
    """(attitude after the NPC's faction renown, note or '') — 02: a step warmer at 3+,
    a step colder below 0. `pc` (a first name) under `renown: per-pc`."""
    mode = setting()
    if mode == "off":
        return att, ""
    slug = campaign.slugify(str(front.get("faction") or ""))
    if not slug or slug in ("none", "-"):
        return att, ""
    who = "party" if mode == "party" else (pc or "").split()[0] if pc else None
    if who is None:
        return att, ""
    n, name = renown_of(slug, who)
    if n is None:
        return att, ""
    new = warmer(att) if n >= WARM_AT else socialdata.worse(att) if n < 0 else att
    if new == socialdata.attitude(att):
        return att, ""
    return new, f"{name} {n}" + ("" if who == "party" else f", {who}")


def renown(faction, change, reason, who=None, rank=None):
    mode = setting()
    if mode == "off":
        raise RenownError("renown: off (campaign setting `renown: party | per-pc` turns it on)")
    m = re.fullmatch(r"\s*([+=-])\s*(\d+)\s*", change or "")
    if not m:
        raise RenownError(f"renown: want +N, -N or =N, got {change!r}")
    if not reason or not reason.strip():
        raise RenownError('renown: give the reason ("returned the ledger")')
    if mode == "per-pc":
        if not who:
            raise RenownError("renown: per-pc — name the PC with --who")
        c = mutations.creature(who)
        if not c.is_pc:
            raise RenownError(f"--who: {c.name} is not a PC")
        holder = c.name.split()[0]
    else:
        if who:
            raise RenownError("renown: party — standings are the party's (--who is for renown: per-pc)")
        holder = "party"
    doc = _load()
    t = doc.table("Factions")
    i = next((k for k, r in enumerate(t.rows) if campaign.slugify(r["faction"]) == campaign.slugify(faction)
              and r.get("who", "").strip().lower() == holder.lower()), None)
    if i is None:
        t.append({"faction": faction.strip(), "renown": "0", "rank": rank or "", "who": holder, "notes": ""})
        i = len(t.rows) - 1
    row = t.rows[i]
    old = int(row.get("renown") or 0)
    n = int(m.group(2))
    new = {"+": old + n, "-": old - n, "=": n}[m.group(1)]
    t.set(i, "renown", new)
    if rank is not None:
        t.set(i, "rank", rank)
    t.set(i, "notes", reason.strip().replace("|", "/"))
    doc.save()
    body = f"renown {row['faction']} {old}→{new} ({holder}): {reason.strip()}" + (f" · rank {rank}" if rank else "")
    journal.log_delta(body)
    tail = ""
    if (old >= WARM_AT) != (new >= WARM_AT) or (old < 0) != (new < 0):
        tail = " · its members' attitude shifts " + ("a step warmer" if new >= WARM_AT else
                                                     "a step colder" if new < 0 else "back")
    return [f"[{body}{tail}]"]


def lines():
    rows = standings()
    if not rows:
        return [f"[renown: none yet · renown: {setting()}]"]
    return ["[renown] " + " · ".join(f"{r['faction']} {r['renown']}" + (f" ({r['rank']})" if r.get("rank") else "")
                                     + ("" if r.get("who", "party") == "party" else f" — {r['who']}") for r in rows)]


def cmd_renown(ctx):
    a = ctx.args
    if a.faction is None:
        out = lines()
    else:
        if a.change is None:
            raise RenownError('renown "Faction" +1 "why"')
        out = renown(a.faction, a.change, a.reason, a.who, a.rank)
    for line in out:
        ctx.emit(line)
    ctx.result = {"lines": out}


def register(sub, g):
    p = mutations.allow_negative(sub.add_parser("renown", parents=[g], help='renown "Faction" +1 "why" [--who PC]'))
    p.add_argument("faction", nargs="?")
    p.add_argument("change", nargs="?")
    p.add_argument("reason", nargs="?")
    p.add_argument("--who", help="renown: per-pc — whose standing")
    p.add_argument("--rank", help="the campaign's rank name")
    p.set_defaults(func=cmd_renown)
