"""`gm.py table import <file> --as <name> [--die d100]` — bring a random table found
elsewhere into the campaign (docs/design/02 → Table mechanics → Phase 16 → Carousing; 06 →
Phase 16 — table extras; 04 → Random tables; plan.md Phase 16 item 4).

Reads pasted lines like `01-05 text`, `01–05. text`, `7: text`, `1. text`, `00 text` or
markdown rows `| 01-05 | text |`; a line without a number continues the previous result
(wrapped text). Writes `<campaign>/tables/<name>.md` as `| roll | result | effect | tags |`
with `die:` (given, else the highest roll) and, for `--as carousing`, `cost: 1d6x10gp`.
Effect codes and tags are never guessed: they're left blank for the driver to fill in.
Gaps and overlaps in the ranges are reported. The file stays in the campaign folder
(its rights belong to its author); it is never copied into the engine.
"""
import re
from pathlib import Path

from lib import campaign, journal, md, tables
from lib.errors import ToolError

_ROW = re.compile(r"^\s*(\d{1,3})(?:\s*[-–—]\s*(\d{1,3}))?\s*[.:)]?\s+(\S.*)$")
_MD = re.compile(r"^\s*\|\s*(\d{1,3})(?:\s*[-–—]\s*(\d{1,3}))?\s*\|\s*([^|]*?)\s*\|")


class TableImportError(ToolError):
    pass


def parse(text):
    """-> ([(lo, hi, result)], joined continuation lines)."""
    rows, joined = [], 0
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "<!--")):
            continue
        if re.match(r"^\s*\|?\s*-{3,}", line) or re.match(r"^\s*\|\s*roll\s*\|", line, re.I):
            continue
        m = _MD.match(line) or _ROW.match(line)
        if m:
            lo = int(m.group(1)) or 100
            hi = (int(m.group(2)) or 100) if m.group(2) else lo
            if hi < lo:
                raise TableImportError(f"table import: {line.strip()!r}: the range runs backwards")
            rows.append([lo, hi, m.group(3).strip()])
        elif rows:
            rows[-1][2] += " " + line.strip()
            joined += 1
    return [tuple(r) for r in rows], joined


def _cell(text):
    return " ".join(str(text).replace("|", "/").split())


def import_table(src, name, die=None):
    path = Path(src)
    if not path.exists():
        raise TableImportError(f"table import: no file {src}")
    slug = campaign.slugify(name)
    if not slug:
        raise TableImportError("table import: name the table with --as <name>")
    raw = path.read_text(encoding="utf-8-sig")
    rows, joined = parse(raw)
    if not rows:
        raise TableImportError("table import: no numbered lines found (want `01-05 text` or `1. text`)")
    if die:
        m = re.fullmatch(r"d?(\d+)", die.strip().lower())
        if not m:
            raise TableImportError(f"table import: --die wants e.g. d100, got {die!r}")
        sides = int(m.group(1))
    else:
        sides = max(hi for _, hi, _ in rows)
    width = 2 if sides == 100 else len(str(sides))

    def num(n):
        return "00" if sides == 100 and n == 100 else str(n).zfill(width)
    gaps, over = tables.gaps_overlaps([(lo, hi) for lo, hi, _ in rows], sides)
    beyond = [(lo, hi) for lo, hi, _ in rows if hi > sides]
    front = [f"die: d{sides}"] + (["cost: 1d6x10gp"] if slug == "carousing" else [])
    body = ["---"] + front + ["---", f"# {slug.replace('-', ' ').title()}",
            f"<!-- Imported by gm.py table import from {path.name}. It stays in this campaign (the rights",
            "     belong to its author). Fill in `effect` codes and `tags` by hand (04 → Random tables). -->",
            "", "| roll | result | effect | tags |", "|------|--------|--------|------|"]
    for lo, hi, text in rows:
        roll = num(lo) if lo == hi else f"{num(lo)}-{num(hi)}"
        body.append(f"| {roll} | {_cell(text)} |  |  |")
    target = campaign.root() / "tables" / f"{slug}.md"
    replaced = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    nl = md.read_text(target)[1] if replaced else "\n"   # a replaced file keeps its newline style
    md.write_text(target, "\n".join(body) + "\n", nl)
    report = (f"[table import: tables/{slug}.md · {len(rows)} rows · d{sides} · gaps: {tables.fmt_ranges(gaps)}"
              f" · overlaps: {tables.fmt_ranges(over)}" + (f" · past d{sides}: {tables.fmt_ranges(beyond)}" if beyond else "")
              + (f" · {joined} wrapped line(s) joined" if joined else "") + (" · replaced the old file" if replaced else "") + "]")
    journal.log_delta(f"table import {slug} ({len(rows)} rows, d{sides}; gaps {tables.fmt_ranges(gaps)}, "
                      f"overlaps {tables.fmt_ranges(over)})", gm=True)
    out = [report]
    if gaps or over or beyond:
        out.append("[fix the ranges in the file before rolling: a roll in a gap has no result]")
    out.append("[effect codes and tags are blank: fill them in (coin, item, clock, no-rest; tags for lines/veils)]")
    return out


def cmd_table(ctx):
    a = ctx.args
    if a.action != "import":
        raise TableImportError("table import <file> --as <name> [--die d100]")
    if not a.as_:
        raise TableImportError("table import: name the table with --as <name>")
    for line in import_table(a.file, a.as_, a.die):
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("table", parents=[g], help="table import <file> --as <name> [--die d100]")
    p.add_argument("action", choices=["import"])
    p.add_argument("file")
    p.add_argument("--as", dest="as_")
    p.add_argument("--die")
    p.set_defaults(func=cmd_table)
