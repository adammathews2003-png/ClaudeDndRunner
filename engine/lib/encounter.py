"""Encounter math from the 2014 DMG, as data (docs/design/07 → Difficulty scaled to the
table, Item power, The danger stone; 06 → `gm.py encounter`, `gm.py danger`; plan.md
Phase 11 item 1). Thresholds and multipliers are tables here, never recalled.

- `THRESHOLDS[level] = (easy, medium, hard, deadly)` per character.
- `MULTIPLIERS`: monster-count multiplier (1 ×1 · 2 ×1.5 · 3–6 ×2 · 7–10 ×2.5 · 11–14 ×3 ·
  15+ ×4), shifted one step up for parties under 3 and one step down for 6+.
- `party_thresholds(levels, power)`, `item_power(pcs)`, `parse_line(text)`,
  `fit(entries, word, start_level, size, power)`, `adjusted(xps, party_size)`.
"""
import math
import re

from . import srd
from .errors import ToolError

WORDS = ("easy", "medium", "hard", "deadly")
THRESHOLDS = {
    1: (25, 50, 75, 100), 2: (50, 100, 150, 200), 3: (75, 150, 225, 400), 4: (125, 250, 375, 500),
    5: (250, 500, 750, 1100), 6: (300, 600, 900, 1400), 7: (350, 750, 1100, 1700),
    8: (450, 900, 1400, 2100), 9: (550, 1100, 1600, 2400), 10: (600, 1200, 1900, 2800),
    11: (800, 1600, 2400, 3600), 12: (1000, 2000, 3000, 4500), 13: (1100, 2200, 3400, 5100),
    14: (1250, 2500, 3800, 5700), 15: (1400, 2800, 4300, 6400), 16: (1600, 3200, 4800, 7200),
    17: (2000, 3900, 5900, 8800), 18: (2100, 4200, 6300, 9500), 19: (2400, 4900, 7300, 10900),
    20: (2800, 5700, 8500, 12700),
}
STEPS = (0.5, 1, 1.5, 2, 2.5, 3, 4, 5)              # the multiplier ladder incl. the shifts
POWER = {"uncommon": 0.25, "rare": 0.5, "very rare": 1, "legendary": 2}
NOMINAL_PARTY = 4
_LINE = re.compile(r"ENCOUNTER\s+(?:(fixed)\s+L(\d+)\s+)?(easy|medium|hard|deadly)\s+\"([^\"]+)\"\s*:\s*(.+)$",
                   re.I)


class EncounterError(ToolError):
    pass


def _step_index(count):
    if count <= 1:
        return 1
    if count == 2:
        return 2
    if count <= 6:
        return 3
    if count <= 10:
        return 4
    if count <= 14:
        return 5
    return 6


def multiplier(count, party_size=NOMINAL_PARTY):
    i = _step_index(count)
    if party_size < 3:
        i += 1
    elif party_size >= 6:
        i -= 1
    return STEPS[max(0, min(len(STEPS) - 1, i))]


def adjusted(xps, party_size=NOMINAL_PARTY):
    """Adjusted XP of a list of per-monster XP values."""
    return int(round(sum(xps) * multiplier(len(xps), party_size)))


def threshold(level, word):
    """Per-character threshold at a (possibly half-step) level, 1–20."""
    k = WORDS.index(word)
    lo = max(1, min(20, math.floor(level)))
    hi = max(1, min(20, math.ceil(level)))
    a, b = THRESHOLDS[lo][k], THRESHOLDS[hi][k]
    return a + (b - a) * (level - lo) if hi != lo else a


def party_thresholds(levels, power=0.0):
    """{word: total} for a list of PC levels, each shifted by `power` levels."""
    return {w: int(round(sum(threshold(lv + power, w) for lv in levels))) for w in WORDS}


def round_half(x):
    """To the nearest half-step, halves rounding up (0.25 → 0.5, 0.75 → 1)."""
    return math.floor(x * 2 + 0.5) / 2


def item_power(docs):
    """(power in virtual levels, description) from PC Inventory rarity tags: permanent
    magic items only (potions and scrolls skipped); summed, divided by PCs, to ½ steps."""
    counts = {k: 0 for k in POWER}
    for d in docs:
        span = d.section("Inventory")
        text = " ".join(d.body[span[0] + 1:span[1]]) if span else ""
        for item in re.split(r"[;,]|\n", text):
            if re.search(r"potion|scroll|ammunition|arrow", item, re.I):
                continue
            for k in sorted(POWER, key=len, reverse=True):
                if re.search(rf"\(\s*{k}\s*\)", item, re.I):
                    counts[k] += 1
                    break
    total = sum(POWER[k] * n for k, n in counts.items())
    power = round_half(total / max(1, len(docs)))
    desc = ", ".join(f"{n} {k}" for k, n in counts.items() if n) or "none"
    return power, desc


# ---------- ENCOUNTER lines ----------

class Entry:
    def __init__(self, text):
        t = re.sub(r"\s*\([^)]*\)", "", text).strip()
        m = re.match(r"^(.+?)\s*[×x]\s*(n|\d+)$", t, re.I)
        if m:
            self.name, cnt = m.group(1).strip(), m.group(2).lower()
            self.scales = cnt == "n"
            self.count = None if self.scales else int(cnt)
        else:
            self.name, self.scales, self.count = t, False, 1
        self.xp = None

    def monster_xp(self):
        if self.xp is None:
            try:
                self.xp = srd.monster(self.name).xp
            except srd.SrdError as e:
                raise EncounterError(f"ENCOUNTER entry {self.name!r}: {e}") from None
        return self.xp


class Line:
    def __init__(self, m, source=""):
        self.fixed = bool(m.group(1))
        self.level = int(m.group(2)) if m.group(2) else None
        self.word = m.group(3).lower()
        self.name = m.group(4)
        # the roster ends at a comment (`# …`), a dash note (`— …`) or a table cell edge (`|`)
        roster = re.split(r"\s+#|\s+—\s+|\s*\|", m.group(5))[0]
        self.entries = [Entry(e) for e in _split_roster(roster) if e.strip()]
        self.source = source


def _split_roster(text):
    out, depth, buf = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return out


def parse_line(text, source=""):
    m = _LINE.search(text)
    return Line(m, source) if m else None


def fit(line, start_level, size=NOMINAL_PARTY, power=0.0):
    """(n, roster [(name, count)], adjusted XP, target) for a template line built for
    `size` PCs at the campaign's start level shifted by item power. `fixed` lines keep
    their roster (n = 1 for any ×n) at their own level for 4 PCs."""
    if line.fixed:
        roster = [(e.name, e.count or 1) for e in line.entries]
        xps = [e.monster_xp() for e in line.entries for _ in range(e.count or 1)]
        return 1, roster, adjusted(xps, NOMINAL_PARTY), None
    target = threshold(start_level + power, line.word) * size
    fixed_xps = [e.monster_xp() for e in line.entries if not e.scales for _ in range(e.count or 1)]
    scaling = [e for e in line.entries if e.scales]
    if not scaling:
        roster = [(e.name, e.count or 1) for e in line.entries]
        return 1, roster, adjusted(fixed_xps, size), target
    best = None
    for n in range(1, 31):
        xps = fixed_xps + [e.monster_xp() for e in scaling for _ in range(n)]
        adj = adjusted(xps, size)
        key = (abs(adj - target), -n)
        if best is None or key < best[0]:
            best = (key, n, adj)
    n, adj = best[1], best[2]
    roster = [(e.name, n if e.scales else (e.count or 1)) for e in line.entries]
    return n, roster, adj, target
