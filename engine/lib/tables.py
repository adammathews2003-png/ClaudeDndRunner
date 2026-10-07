"""Random tables with effect codes (docs/design/04 → Random tables (Phase 16); 02 → Table
mechanics → Phase 16; 06 → Phase 16 — table extras; plan.md Phase 16 item 3).

A table file is `<campaign>/tables/<name>.md` (else the engine's starter copy in
`engine/templates/tables/<name>.md`) with a `| roll | result | effect | tags |` table
(`effect` and `tags` optional). `roll` is a number or a range (`01-03`, `7`, `00` = 100);
the ranges are read by lib/dice.py's `_range`, the same reader as `roll table:` and the
loot tables. Frontmatter: `die: d100` (default: the highest roll) and, for carousing,
`cost: 1d6x10gp`.

`effect` holds `;`-separated codes. `codes(text)` splits them (a `;` inside quotes stays);
the commands that roll a table (carouse.py, crit.py) decide which codes they apply and
print the rest for the GM. `tags` is a comma list; `matches(tags, boundary)` is the
content-boundary test (02 → Content boundaries): any significant word of a `lines:` /
`veils:` entry that is also a tag word (plurals folded) counts, so a line errs on the
side of re-rolling.

`gaps_overlaps(ranges, die)` is the coverage report `table import` prints.
"""
import re
from pathlib import Path

from . import campaign, dice, md
from .errors import ToolError

TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "tables"
_STOP = {"a", "an", "the", "to", "of", "and", "or", "in", "on", "for", "with", "by", "any",
         "against", "harm", "graphic", "real", "people", "content"}


class TableError(ToolError):
    pass


class Row:
    def __init__(self, lo, hi, result, effect="", tags=()):
        self.lo, self.hi, self.result, self.effect, self.tags = lo, hi, result, effect, list(tags)

    @property
    def roll(self):
        return f"{self.lo}" if self.lo == self.hi else f"{self.lo}-{self.hi}"


class RandomTable:
    def __init__(self, name, path, front, rows):
        self.name, self.path, self.front, self.rows = name, path, front, rows
        die = str(front.get("die") or "").strip().lower()
        m = re.fullmatch(r"d(\d+|%)", die)
        self.die = (100 if m.group(1) == "%" else int(m.group(1))) if m else max(r.hi for r in rows)

    def row_for(self, n):
        hit = next((r for r in self.rows if r.lo <= n <= r.hi), None)
        if hit is None:
            raise TableError(f"tables/{self.name}.md: no row covers {n} on d{self.die}")
        return hit

    def roll(self, roller, face=None):
        """(n, Row). `face` is a physical die the table rolled."""
        if face is not None:
            if not 1 <= face <= self.die:
                raise TableError(f"{self.name}: the die is a d{self.die} (got {face})")
            n = face
        else:
            n = roller.die(self.die)
        return n, self.row_for(n)


def path_of(name, fallback=True):
    """The campaign's tables/<name>.md, else (fallback) the engine's starter copy, else None."""
    p = campaign.root() / "tables" / f"{name}.md"
    if p.exists():
        return p
    t = TEMPLATES / f"{name}.md"
    return t if fallback and t.exists() else None


def find_table(doc):
    for i, line in enumerate(doc.body):
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and "roll" in cells and "result" in cells:
            return md.Table(doc, i)
    return None


def load(name, fallback=True):
    p = path_of(name, fallback)
    if p is None:
        raise TableError(f"no table {name!r} (tables/{name}.md)")
    doc = md.load(p)
    t = find_table(doc)
    if t is None or not t.rows:
        raise TableError(f"{p.name}: no | roll | result | rows")
    rows = []
    for r in t.rows:
        try:
            lo, hi = dice._range(r.get("roll", ""), name)
        except dice.DiceError as e:
            raise TableError(str(e)) from None
        tags = [x.strip() for x in (r.get("tags") or "").split(",") if x.strip()]
        rows.append(Row(lo, hi, r.get("result", "").strip(), (r.get("effect") or "").strip(), tags))
    return RandomTable(name, p, doc.front, rows)


def codes(text):
    """'coin -2d6x10; item +"a; b"' -> ['coin -2d6x10', 'item +"a; b"']."""
    out, cur, quoted = [], "", False
    for ch in text or "":
        if ch == '"':
            quoted = not quoted
        if ch == ";" and not quoted:
            if cur.strip():
                out.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [c for c in out if c not in ("—", "-")]


def _words(text):
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w
            for w in re.findall(r"[a-z]+", str(text).lower())} - _STOP


def matches(tags, boundary):
    """True when a content boundary (`lines:`/`veils:` entry) touches these tags."""
    want = _words(boundary)
    have = set()
    for t in tags:
        have |= _words(t)
    return bool(want & have)


def gaps_overlaps(ranges, die):
    """([(lo, hi) gaps], [(lo, hi) overlaps]) of [(lo, hi)] against 1..die."""
    count = [0] * (die + 1)
    for lo, hi in ranges:
        for n in range(max(lo, 1), min(hi, die) + 1):
            count[n] += 1
    gaps, over = [], []

    def runs(pred):
        out, start = [], None
        for n in range(1, die + 2):
            ok = n <= die and pred(count[n])
            if ok and start is None:
                start = n
            elif not ok and start is not None:
                out.append((start, n - 1))
                start = None
        return out
    gaps = runs(lambda c: c == 0)
    over = runs(lambda c: c > 1)
    return gaps, over


def fmt_ranges(rs):
    return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in rs) or "none"
