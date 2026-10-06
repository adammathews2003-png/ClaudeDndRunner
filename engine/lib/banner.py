"""Block-letter title cards for `gm.py intro` (docs/design/02 → Session start: the
opening). Stdlib only: a 5-row font, greedy word wrap, centred in a framed card.

    card("The Missing Miller", "Our tale begins")  → list of lines (≤ 72 wide)
"""
FILL = "█"
FONT = {
    "A": [" ### ", "#   #", "#####", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#### ", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", " ####"],
    "D": ["#### ", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#### ", "#    ", "#####"],
    "F": ["#####", "#    ", "#### ", "#    ", "#    "],
    "G": [" ####", "#    ", "#  ##", "#   #", " ####"],
    "H": ["#   #", "#   #", "#####", "#   #", "#   #"],
    "I": ["###", " # ", " # ", " # ", "###"],
    "J": ["  ###", "    #", "    #", "#   #", " ### "],
    "K": ["#   #", "#  # ", "###  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#### ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
    "S": [" ####", "#    ", " ### ", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "# # #", "## ##", "#   #"],
    "X": ["#   #", " # # ", "  #  ", " # # ", "#   #"],
    "Y": ["#   #", " # # ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "   # ", "  #  ", " #   ", "#####"],
    "0": [" ### ", "#  ##", "# # #", "##  #", " ### "],
    "1": [" # ", "## ", " # ", " # ", "###"],
    "2": ["#### ", "    #", " ### ", "#    ", "#####"],
    "3": ["#### ", "    #", " ### ", "    #", "#### "],
    "4": ["#   #", "#   #", "#####", "    #", "    #"],
    "5": ["#####", "#    ", "#### ", "    #", "#### "],
    "6": [" ### ", "#    ", "#### ", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", "  #  "],
    "8": [" ### ", "#   #", " ### ", "#   #", " ### "],
    "9": [" ### ", "#   #", " ####", "    #", " ### "],
    "'": ["#", "#", " ", " ", " "],
    "-": ["   ", "   ", "###", "   ", "   "],
    "!": ["#", "#", "#", " ", "#"],
    "?": ["### ", "   #", " ## ", "    ", " #  "],
    ".": [" ", " ", " ", " ", "#"],
    ",": [" ", " ", " ", "#", "#"],
    ":": [" ", "#", " ", "#", " "],
    "&": [" ##  ", "#  # ", " ## #", "#  # ", " ## #"],
}
SPACE = ["   "] * 5
WIDTH = 72


def word(text):
    """The 5 rows of one word (unknown characters are dropped)."""
    glyphs = [FONT[ch] for ch in text.upper().replace("’", "'") if ch in FONT]
    if not glyphs:
        return [""] * 5
    return [" ".join(g[r] for g in glyphs).replace("#", FILL) for r in range(5)]


def big(text, width):
    """Block-letter rows for `text`, wrapped by word to `width`; None when a single word
    is wider than that."""
    lines, cur = [], None
    for w in text.split():
        rows = word(w)
        if len(rows[0]) > width:
            return None
        if cur is None:
            cur = rows
        elif len(cur[0]) + 1 + len(SPACE[0]) + 1 + len(rows[0]) <= width:
            cur = [a + " " + SPACE[0] + " " + b for a, b in zip(cur, rows)]
        else:
            lines.append(cur)
            cur = rows
    if cur is not None:
        lines.append(cur)
    out = []
    for n, block in enumerate(lines):
        if n:
            out.append("")
        out += block
    return out


def card(title, tagline, width=WIDTH):
    """The framed title card: block letters (spaced capitals when a word won't fit),
    then the tagline between rules."""
    inner = width - 4
    rows = big(title, inner - 4)
    if rows is None:
        rows = [" ".join(title.upper())]
    edge = "✦" + "═" * (width - 2) + "✦"
    out = [edge, ""]
    out += [("  " + r.center(inner)).rstrip() for r in rows]
    out.append("")
    tag = f"──── ✦  {tagline}  ✦ ────"
    out.append(("  " + tag.center(inner)).rstrip())
    out += ["", edge]
    return out
