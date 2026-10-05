"""XP thresholds and advancement helpers (planning/06 → `gm.py xp`; 04 → Advancement;
02 → Level-up flow; plan.md Phase 6 item 5).

The PHB table is data here, never recalled: `THRESHOLDS[level]` is the XP needed to
reach that level (L1 0 … L20 355,000).
"""
THRESHOLDS = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000,
              9: 48000, 10: 64000, 11: 85000, 12: 100000, 13: 120000, 14: 140000,
              15: 165000, 16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000}


def level_for(xp):
    """The highest level whose threshold `xp` meets."""
    best = 1
    for lvl, need in THRESHOLDS.items():
        if xp >= need:
            best = lvl
    return best


def next_threshold(level):
    """(next level, XP needed) or (None, None) at 20."""
    if level >= 20:
        return None, None
    return level + 1, THRESHOLDS[level + 1]


def start_xp(level):
    """The `xp:` a new PC of this level starts with (the level's threshold)."""
    return THRESHOLDS.get(int(level or 1), 0)


def current(front):
    """A PC's tracked XP; a file without `xp:` counts as its level's threshold."""
    v = front.get("xp")
    if isinstance(v, int):
        return v
    return start_xp(front.get("level") if isinstance(front.get("level"), int) else 1)
