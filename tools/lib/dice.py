"""Dice: the only RNG in the tools (planning/06 → `gm.py roll` L96-109, principle 6
L44-45; planning/02 → Dice L167-176; planning/05 #2; plan.md Phase 2 item 1).

Grammar (06 L104-105): an expression of `NdM` terms (`d20` = `1d20`, `d%` = `d100`)
with optional `khK`/`klK` (keep highest/lowest K), `+`/`-` constants and further dice;
then optional words `adv` / `dis` (the first single d20 rolls twice, keeps one),
`crit` (doubles the dice count, never the modifiers) and `xN` (repeat N times).
`table:<slug>` rolls on `<campaign>/tables/<slug>.md` (`| roll | result |`, ranges
like `1-3`; planning/04 L600-608).

Output text matches 06 L97-102 exactly:
    [1d20+5: 14+5 = 19]
    [1d20+3 adv: (6, 17)→17+3 = 20]
    [2d6+3 crit: 4d6 (2,5,6,1)+3 = 17]
    [SECRET 3d6: 11]
`Roller(seed=None)` uses `random.SystemRandom()`; a seed gives a `random.Random(seed)`
for tests (`--seed N`). No other module may touch `random`.

d20 tests (atk/save/check/contest) use `Roller.d20(bonus, mode)` and
`reported(bonus, d20=, total=)`; their text is the attack-line form of 06 L37-38
(`d20 13+5=18`, `d20 (6, 17)→17+5=22`, `total 19`). Outcomes are decided in
lib/resolve.py, never here.
"""
import random
import re

from .errors import ToolError


class DiceError(ToolError):
    pass


_TERM = re.compile(r"([+-]?)(?:(\d*)d(\d+|%)(?:(kh|kl)(\d+))?|(\d+))", re.I)
_REPEAT = re.compile(r"^x(\d+)$", re.I)


def _sign(n):
    return f"{n:+d}"


class Term:
    """One parsed term: dice (`n`, `m`, `keep` ('kh'|'kl'|None), `k`) or a constant
    (`m` None, `value`). `sign` is +1/-1."""

    def __init__(self, sign, n=None, m=None, keep=None, k=None, value=None):
        self.sign, self.n, self.m, self.keep, self.k, self.value = sign, n, m, keep, k, value

    @property
    def is_dice(self):
        return self.m is not None


def parse(expr):
    """`'2d6+1d4-1'` -> [Term]. Raises DiceError on anything else."""
    text = re.sub(r"\s+", "", expr)
    if not text:
        raise DiceError("empty dice expression")
    terms, pos = [], 0
    while pos < len(text):
        m = _TERM.match(text, pos)
        if not m or m.end() == pos or (pos > 0 and not m.group(1)):
            raise DiceError(f"bad dice expression {expr!r} (want e.g. 2d6+3, 1d20+5 adv, 4d6kh3)")
        sign = -1 if m.group(1) == "-" else 1
        if m.group(6) is not None:
            terms.append(Term(sign, value=int(m.group(6))))
        else:
            n = int(m.group(2) or 1)
            sides = 100 if m.group(3) == "%" else int(m.group(3))
            if n < 1 or sides < 1 or n > 1000:
                raise DiceError(f"bad dice term {m.group(0)!r}")
            keep = m.group(4).lower() if m.group(4) else None
            k = int(m.group(5)) if m.group(5) else None
            if keep and not 1 <= k <= n:
                raise DiceError(f"cannot keep {k} of {n} dice in {m.group(0)!r}")
            terms.append(Term(sign, n, sides, keep, k))
        pos = m.end()
    return terms


def dice_max(expr):
    """Sum of the maximum faces of every dice term (kept dice only); constants ignored.
    Used by resolve.py for the `crit-damage=max+roll` table rule (06 L197)."""
    total = 0
    for t in parse(expr):
        if t.is_dice:
            total += t.sign * (t.k if t.keep else t.n) * t.m
    return total


class Result:
    """`total` (sum of `totals` when repeated), `totals` (one per repeat), `parts`
    (per repeat: list of term dicts), `text` (the bracket line), `body` (the text
    after `label: ` without brackets, e.g. `4d6 (2,5,6,1)+3 = 17`), `natural` (the
    kept d20 of a single-d20 roll, else None)."""

    def __init__(self, total, parts, text, totals=None, natural=None, body=None, label=""):
        self.label = label  # the expression as shown before `: ` (`2d6+3 crit`, `table:x`)
        self.total = total
        self.parts = parts
        self.text = text
        self.body = body if body is not None else text
        self.totals = totals if totals is not None else [total]
        self.natural = natural

    def as_dict(self):
        return {"total": self.total, "totals": self.totals, "parts": self.parts,
                "text": self.text, "body": self.body, "natural": self.natural}


class D20:
    """A d20 test: `natural` (kept die, or None when only a total was reported),
    `rolls` (both dice under adv/dis), `bonus`, `total`, `text`."""

    def __init__(self, natural, rolls, bonus, total, text, reported=False):
        self.natural, self.rolls, self.bonus, self.total = natural, rolls, bonus, total
        self.text = text
        self.reported = reported

    def as_dict(self):
        return {"natural": self.natural, "rolls": self.rolls, "bonus": self.bonus,
                "total": self.total, "text": self.text, "reported": self.reported}


def reported(bonus, d20=None, total=None):
    """A player-reported roll (02 L170-174): `--d20 N` adds the bonus, `--total N` is
    taken as is (no natural, so no nat 20/1)."""
    if d20 is not None:
        if not 1 <= d20 <= 20:
            raise DiceError(f"--d20 must be 1-20, got {d20}")
        t = d20 + bonus
        return D20(d20, [d20], bonus, t, f"d20 {d20}{_sign(bonus)}={t}", reported=True)
    if total is None:
        raise DiceError("reported roll needs --d20 or --total")
    return D20(None, [], bonus, total, f"total {total}", reported=True)


class Roller:
    def __init__(self, seed=None):
        self.rng = random.SystemRandom() if seed is None else random.Random(seed)

    def die(self, sides):
        return self.rng.randint(1, sides)

    # -- d20 tests --
    def d20(self, bonus=0, mode=None):
        """Roll a d20 test. mode: None | 'adv' | 'dis'."""
        if mode in ("adv", "dis"):
            a, b = self.die(20), self.die(20)
            kept = max(a, b) if mode == "adv" else min(a, b)
            t = kept + bonus
            return D20(kept, [a, b], bonus, t, f"d20 ({a}, {b})→{kept}{_sign(bonus)}={t}")
        n = self.die(20)
        t = n + bonus
        return D20(n, [n], bonus, t, f"d20 {n}{_sign(bonus)}={t}")

    # -- expressions --
    def _roll_once(self, terms, mode, crit):
        """One evaluation. Returns (total, parts, body_text, natural)."""
        parts, chunks, total, natural = [], [], 0, None
        adv_done = False
        single_d20 = sum(1 for t in terms if t.is_dice) == 1
        for i, t in enumerate(terms):
            sign = "-" if t.sign < 0 else ("+" if i else "")
            if not t.is_dice:
                total += t.sign * t.value
                parts.append({"const": t.sign * t.value})
                chunks.append(f"{sign}{t.value}")
                continue
            n = t.n * 2 if crit else t.n
            if mode and not adv_done and t.n == 1 and t.m == 20 and not t.keep:
                adv_done = True
                a, b = self.die(20), self.die(20)
                kept = max(a, b) if mode == "adv" else min(a, b)
                total += t.sign * kept
                parts.append({"dice": "1d20", "rolls": [a, b], "kept": [kept], "mode": mode})
                chunks.append(f"{sign}({a}, {b})→{kept}")
                if single_d20:
                    natural = kept
                continue
            rolls = [self.die(t.m) for _ in range(n)]
            if t.keep:
                k = t.k * 2 if crit else t.k
                kept = sorted(rolls, reverse=(t.keep == "kh"))[:k]
            else:
                kept = rolls
            value = sum(kept)
            total += t.sign * value
            label = f"{n}d{t.m}" + (f"{t.keep}{t.k * 2 if crit else t.k}" if t.keep else "")
            parts.append({"dice": label, "rolls": rolls, "kept": kept})
            if n == 1 and not t.keep and i == 0 and t.sign > 0:
                chunks.append(f"{sign}{rolls[0]}")
                if single_d20 and t.m == 20:
                    natural = rolls[0]
            elif t.keep and len(terms) > 1:
                chunks.append(f"{sign}{label} ({','.join(map(str, rolls))})→{value}")
            else:
                chunks.append(f"{sign}{label} ({','.join(map(str, rolls))})")
        return total, parts, "".join(chunks), natural

    def roll(self, expr, secret=False):
        """Roll a dice expression with its trailing words (adv, dis, crit, xN).
        `table:<slug>` is handled by roll_table()."""
        words = expr.split()
        mode, crit, repeat, dice_words = None, False, 1, []
        for w in words:
            lw = w.lower()
            if lw in ("adv", "dis"):
                if crit:
                    raise DiceError("crit damage rolls don't take adv/dis")
                if mode and mode != lw:
                    raise DiceError("adv and dis cancel out; roll plain instead")
                mode = lw
            elif lw == "crit":
                crit = True
                if mode:
                    raise DiceError("crit damage rolls don't take adv/dis")
            elif _REPEAT.match(lw):
                repeat = int(_REPEAT.match(lw).group(1))
                if not 1 <= repeat <= 100:
                    raise DiceError(f"bad repeat {w!r}")
            else:
                dice_words.append(w)
        if not dice_words:
            raise DiceError(f"no dice in {expr!r}")
        core = "".join(dice_words)
        terms = parse(core)  # constant-only (flat damage like `3`) is allowed
        if mode and not any(t.is_dice and t.n == 1 and t.m == 20 and not t.keep for t in terms):
            raise DiceError(f"{mode} needs a 1d20 term")
        label = " ".join([core] + [w for w in words if w.lower() in ("adv", "dis", "crit")]
                         + [w for w in words if _REPEAT.match(w.lower())])
        totals, all_parts, bodies, natural = [], [], [], None
        for _ in range(repeat):
            total, parts, body, nat = self._roll_once(terms, mode, crit)
            totals.append(total)
            all_parts.append(parts)
            bodies.append(str(total) if body == str(total) else f"{body} = {total}")
            natural = nat if repeat == 1 else None
        if secret:
            body = " · ".join(str(t) for t in totals)
            text = f"[SECRET {label}: {body}]"
        else:
            body = " · ".join(bodies)
            text = f"[{label}: {body}]"
        return Result(sum(totals), all_parts if repeat > 1 else all_parts[0], text, totals,
                      natural, body, label)

    # -- tables --
    def roll_table(self, path, slug, secret=False):
        """Roll on a `| roll | result |` table file. Ranges `1-3`, `4`, `00` = 100."""
        from . import md  # local: md is only needed for tables
        try:
            doc = md.load(path)
        except FileNotFoundError:
            raise DiceError(f"no table {slug!r} (expected {path})") from None
        table = None
        for i, line in enumerate(doc.body):
            cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
            if line.lstrip().startswith("|") and "roll" in cells and "result" in cells:
                table = md.Table(doc, i)
                break
        if table is None or not table.rows:
            raise DiceError(f"table {slug!r} has no | roll | result | rows")
        ranges = []
        for row in table.rows:
            lo, hi = _range(row.get("roll", ""), slug)
            ranges.append((lo, hi, row.get("result", "")))
        sides = max(hi for _, hi, _ in ranges)
        n = self.die(sides)
        hit = next((r for lo, hi, r in ranges if lo <= n <= hi), None)
        if hit is None:
            raise DiceError(f"table {slug!r}: no row covers {n} on d{sides}")
        body = f"d{sides} {n} → {hit}"
        text = f"[SECRET table:{slug}: {body}]" if secret else f"[table:{slug}: {body}]"
        return Result(n, [{"dice": f"1d{sides}", "rolls": [n], "kept": [n], "result": hit}],
                      text, [n], None, body, f"table:{slug}")


def _range(cell, slug):
    cell = cell.strip().replace("–", "-").replace("—", "-")
    m = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", cell)
    if not m:
        raise DiceError(f"table {slug!r}: bad roll cell {cell!r}")
    lo = int(m.group(1)) or 100
    hi = int(m.group(2)) if m.group(2) else lo
    hi = hi or 100
    return lo, hi
