"""`gm.py spoil log "<question>" --level none|minor|major --depth hint|answer|full
--reveals "<one line>" [--what-if]` and `gm.py spoil list` (docs/design/06 → Spoiler
support; 02 → Spoilers; 04 → Spoiler record; plan.md Phase 7 item 7).

`log` appends a row to `sessions/spoilers.md` (never reset) and writes a public
`[spoilers] level/depth: "question"` line to the session log. What-ifs are recorded
as `what-if (not canon): …` and never as facts. `list` prints what's already spoiled.
"""
from lib import campaign, journal, md
from lib.errors import ToolError
import rules

COLS = ["when", "level", "depth", "question", "revealed"]
HEADER = ("# Spoilers revealed (player knowledge, not character knowledge)\n"
          "<!-- Append-only; written by gm.py spoil log (docs/design/02 → Spoilers). Never reset.\n"
          "     What-if guesses are recorded as \"what-if (not canon)\" — nothing here is a world fact. -->\n\n"
          "| when | level | depth | question | revealed |\n|------|-------|-------|----------|----------|\n")


class SpoilError(ToolError):
    pass


def _doc():
    p = campaign.root() / "sessions" / "spoilers.md"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        return md.new(p, HEADER)
    return md.load(p)


def log(question, level, depth, reveals, what_if=False):
    if level not in ("none", "minor", "major"):
        raise SpoilError("spoil log: --level none|minor|major")
    if depth not in ("hint", "answer", "full"):
        raise SpoilError("spoil log: --depth hint|answer|full")
    if not reveals:
        raise SpoilError("spoil log: --reveals \"one line of what was revealed\"")
    revealed = reveals.replace("|", "/")
    if what_if and not revealed.lower().startswith("what-if"):
        revealed = f"what-if (not canon): {revealed}"
    doc = _doc()
    t = doc.table("Spoilers")
    if t is None:
        raise SpoilError("sessions/spoilers.md has no | when | level | depth | question | revealed | table")
    t.append({"when": rules.since(), "level": level, "depth": depth, "question": question.replace("|", "/"),
              "revealed": revealed})
    doc.save()
    journal.log_delta(f'[spoilers] {level}/{depth}: "{question}"')
    return f'[spoil logged: {level}/{depth} · "{question}"]'


def list_lines():
    t = _doc().table("Spoilers")
    rows = t.rows if t else []
    if not rows:
        return ["[spoilers: none yet]"]
    return [f"[{r['when']} · {r['level']}/{r['depth']} · {r['question']} → {r['revealed']}]" for r in rows]


def cmd_spoil(ctx):
    a = ctx.args
    if a.action == "list":
        lines = list_lines()
    else:
        if not a.question:
            raise SpoilError('spoil log "<question>" --level … --depth … --reveals "…"')
        lines = [log(" ".join(a.question), a.level, a.depth or "answer", a.reveals, a.what_if)]
    for line in lines:
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("spoil", parents=[g], help="spoil log \"q\" --level --depth --reveals | spoil list")
    p.add_argument("action", choices=["log", "list"])
    p.add_argument("question", nargs="*")
    p.add_argument("--level")
    p.add_argument("--depth")
    p.add_argument("--reveals")
    p.add_argument("--what-if", action="store_true")
    p.set_defaults(func=cmd_spoil)
