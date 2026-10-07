"""Social stakes as data: the attitude × ask DC table, flair steps, NPC tastes and the
result tiers (docs/design/02 → Table mechanics → Phase 14 → Social stakes; 06 → Table
mechanics → Phase 14; plan.md Phase 14 item 3).

Pure functions only; engine/social.py reads the files, writes `state/social.md` and
logs. The DMG's conversation table mapped onto the five attitudes, with "won't"
turned into long shots (the hardest cell is 30):
"""

ATTITUDES = ("ally", "friendly", "neutral", "wary", "hostile")
ASKS = ("none", "free", "minor", "major")
ASK_TEXT = {"none": "stand aside / no harm", "free": "help at no cost",
            "minor": "minor risk or cost", "major": "major risk"}
DCS = {
    "ally":     (0, 0, 0, 10),
    "friendly": (0, 0, 10, 20),
    "neutral":  (0, 10, 20, 25),
    "wary":     (5, 15, 25, 30),
    "hostile":  (10, 20, 25, 30),
}
# creativity → (DC taken off for flair 1, 2, 3; the lowest flair that gives advantage)
CREATIVITY = {"off": ((0, 0, 0), None), "light": ((2, 5, 8), 3), "generous": ((5, 8, 10), 2)}
TASTES = ("audacity", "honesty", "flattery", "humour", "piety", "coin", "nothing")
BAND = 5
SKILLS = ("persuasion", "deception", "intimidation")
STAGES = {1: "stage 1: show a feeling",
          2: "stage 2: have them name what it would take",
          3: "stage 3+: a different approach starts a band lower; offer a route around them"}


def attitude(text):
    """The five attitudes; anything else reads as neutral."""
    t = str(text or "").strip().lower()
    return t if t in ATTITUDES else "neutral"


def starting_dc(att, ask):
    return DCS[attitude(att)][ASKS.index(ask)]


def worse(att):
    """One attitude step down (hostile stays hostile)."""
    i = ATTITUDES.index(attitude(att))
    return ATTITUDES[min(i + 1, len(ATTITUDES) - 1)]


def tastes(value):
    """`moved-by:` as a lower-case list (a bare word is a one-item list)."""
    if value is None or value == "":
        return []
    items = value if isinstance(value, list) else [value]
    return [str(x).strip().lower() for x in items if str(x).strip()]


def adjust_flair(flair, moved_by, appeal=None, grates=False):
    """(flair after the NPC's taste, reason or ""). `nothing` takes one off any flair
    pitch; an `appeal` the NPC is moved by adds one; `grates` takes one off. 0–3."""
    if flair <= 0:
        return 0, ""
    out, why = flair, []
    if "nothing" in moved_by:
        out -= 1
        why.append("moved by nothing")
    elif appeal and appeal.lower() in moved_by:
        out += 1
        why.append(f"moved by {appeal.lower()}")
    if grates:
        out -= 1
        why.append("it grates")
    out = max(0, min(3, out))
    return out, (", ".join(why) + f": {flair}→{out}") if out != flair else ""


def flair_off(flair, mode):
    """(DC taken off, advantage) for a final flair under the `creativity` setting."""
    steps, adv_from = CREATIVITY.get(mode, CREATIVITY["light"])
    if flair <= 0:
        return 0, False
    return steps[min(flair, 3) - 1], adv_from is not None and flair >= adv_from


def tier(margin, flair):
    """The result tier from the check's margin (total − DC): yes, and · yes · yes, but
    · no, but · no, and."""
    if margin >= 5:
        return "yes, and"
    if margin >= 0:
        return "yes"
    if margin > -5:
        return "yes, but" if flair >= 2 else "no, but"
    return "no, and"


def stage(fails):
    if fails <= 0:
        return ""
    return STAGES[min(fails, 3)]
