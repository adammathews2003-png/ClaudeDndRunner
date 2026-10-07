"""Magic items as inventory text (docs/design/02 → Table mechanics → Phase 15 → Magic
items; 04 → PC file, Added by Phases 13–15; 06 → Table mechanics → Phase 15).

An item carries its tags in parentheses on its `## Inventory` entry:

    wand of magic missiles (uncommon, charges 5/7, recharge 1d6+1 dawn, destroy on 1)
    cloak of protection (uncommon, attune, ac +1, saves +1)
    unidentified: smoky glass ring (GM: ring of mind shielding)

Tags: a rarity (common … artifact), `attune` (needs attunement), `charges N/M`,
`recharge <dice> <dawn|dusk|midnight|noon>`, `destroy on 1` (the d20 when the last charge
is spent), and bonuses `ac +1`, `saves +1`, `attack +1`, `damage +1`. A bonus counts while
the item is on the `- Equipped:` line and, when it needs attunement, is in the PC's
`attuned:` list. The `(GM: …)` part is the true name, stripped from anything a player sees
(`public`). Pure parsing: engine/magic.py writes and logs.
"""
import re

from . import srd

RARITIES = ("very rare", "uncommon", "common", "rare", "legendary", "artifact")
BONUS_KEYS = ("ac", "saves", "attack", "damage")
MAX_ATTUNED = 3
_GM = re.compile(r"\s*\(\s*GM:\s*([^)]*)\)", re.I)
_PAREN = re.compile(r"\(([^()]*)\)")
_BONUS = re.compile(r"^(ac|saves|attack|damage)\s*([+-]\s*\d+)$", re.I)
_CHARGES = re.compile(r"^charges\s+(\d+)\s*/\s*(\d+)$", re.I)
_RECHARGE = re.compile(r"^recharge\s+(.+?)\s+(dawn|dusk|midnight|noon)$", re.I)


class Item:
    """One inventory entry with magic tags (or an unidentified one)."""

    def __init__(self, text, line=None, index=None, equipped=False):
        self.text = text
        self.line, self.index, self.equipped = line, index, equipped
        gm = _GM.search(text)
        self.gm = gm.group(1).strip() if gm else None
        bare = _GM.sub("", text).strip()
        self.unidentified = bool(re.match(r"^unidentified\s*:", bare, re.I))
        bare = re.sub(r"^unidentified\s*:\s*", "", bare, flags=re.I)
        self.rarity, self.attune, self.charges, self.recharge, self.destroy = None, False, None, None, False
        self.bonus = {}
        self.tag_span = None
        for m in _PAREN.finditer(bare):
            tags = [t.strip() for t in m.group(1).split(",") if t.strip()]
            if any(_tag_kind(t) for t in tags):
                self.tag_span = m.span()
                for t in tags:
                    self._take(t)
                break
        name = bare if self.tag_span is None else bare[:self.tag_span[0]] + bare[self.tag_span[1]:]
        self.name = re.sub(r"\s{2,}", " ", name).strip()

    def _take(self, tag):
        low = tag.lower()
        if low in RARITIES:
            self.rarity = low
        elif low in ("attune", "attunement", "requires attunement"):
            self.attune = True
        elif low == "destroy on 1":
            self.destroy = True
        elif _CHARGES.match(tag):
            m = _CHARGES.match(tag)
            self.charges = (int(m.group(1)), int(m.group(2)))
        elif _RECHARGE.match(tag):
            m = _RECHARGE.match(tag)
            self.recharge = (m.group(1).replace(" ", ""), m.group(2).lower())
        elif _BONUS.match(tag):
            m = _BONUS.match(tag)
            self.bonus[m.group(1).lower()] = self.bonus.get(m.group(1).lower(), 0) + int(m.group(2).replace(" ", ""))

    @property
    def magic(self):
        return self.tag_span is not None or self.unidentified

    def label(self):
        """What a player sees: `smoky glass ring (unidentified)`, else the name."""
        return f"{self.name} (unidentified)" if self.unidentified else self.name

    def with_charges(self, n):
        """The entry text with `charges n/max`."""
        return re.sub(r"charges\s+\d+\s*/\s*(\d+)", lambda m: f"charges {n}/{m.group(1)}", self.text, count=1, flags=re.I)


def _tag_kind(tag):
    low = tag.strip().lower()
    return (low in RARITIES or low in ("attune", "attunement", "requires attunement", "destroy on 1")
            or bool(_CHARGES.match(tag.strip()) or _RECHARGE.match(tag.strip()) or _BONUS.match(tag.strip())))


def items(doc, all_entries=False):
    """[Item] for the inventory's magic entries (every entry with `all_entries`)."""
    import inventory   # engine/inventory.py: the entry splitter
    span = doc.section("Inventory") if doc is not None else None
    if span is None:
        return []
    out = []
    for j in range(span[0] + 1, span[1]):
        line = doc.body[j]
        if not line.strip() or re.match(r"^\s*-\s+Coin:", line) or line.strip().startswith("<!--"):
            continue
        equipped = bool(re.match(r"^\s*-\s*Equipped:", line, re.I))
        _, entries, _ = inventory._split_entries(line)
        for k, e in enumerate(entries):
            it = Item(e, j, k, equipped)
            if it.magic or all_entries:
                out.append(it)
    return out


def find(doc, name):
    """The one magic item matching `name` (exact name, else a unique substring). Raises
    LookupError with the reason."""
    want = re.sub(r"^unidentified\s*:\s*", "", name.strip().lower())
    found = items(doc, all_entries=True)
    exact = [i for i in found if i.name.lower() == want or (i.gm or "").lower() == want]
    if exact:
        return exact[0]
    loose = [i for i in found if want in i.name.lower()]
    if len(loose) == 1:
        return loose[0]
    if len(loose) > 1:
        raise LookupError(f"{name!r} is ambiguous: " + "; ".join(i.name for i in loose))
    raise LookupError(f"no {name!r} in ## Inventory")


def attuned(doc):
    return [str(x) for x in (doc.front.get("attuned") or []) if str(x).strip()] if doc is not None else []


def is_attuned(doc, item):
    names = {a.lower() for a in attuned(doc)}
    return item.name.lower() in names


def active(doc):
    """Items whose bonuses count: equipped, and attuned when they need it."""
    return [i for i in items(doc) if i.bonus and i.equipped and not i.unidentified
            and (not i.attune or is_attuned(doc, i))]


def bonus(doc, key, attack=None):
    """The summed `key` bonus of the active items. For `attack`/`damage` with an Attacks
    row name: an item whose name names one of the creature's attacks counts only for
    that attack; any other item counts for every attack."""
    if doc is None:
        return 0
    total = 0
    names = []
    if attack is not None:
        t = doc.table("Attacks")
        names = [r.get("name", "").strip().lower() for r in (t.rows if t else []) if r.get("name", "").strip()]
    for it in active(doc):
        n = it.bonus.get(key, 0)
        if not n:
            continue
        if attack is not None:
            named = [w for w in names if w in it.name.lower()]
            if named and attack.strip().lower() not in named:
                continue
        total += n
    return total


def public(text):
    """Text with every `(GM: …)` part removed (player-facing output and public log lines)."""
    return re.sub(r"\s{2,}", " ", _GM.sub("", str(text))).strip()


def has_gm(text):
    return bool(_GM.search(str(text)))


# ---------- SRD (data/srd/5e-SRD-Magic-Items.json) ----------

def srd_record(name):
    """The SRD magic item for `name`, or None (no data, no such item)."""
    try:
        return srd.find("Magic-Items", name)
    except srd.SrdError:
        return None


def srd_tags(name):
    """The inventory tags the SRD text implies: rarity, attune, charges and recharge,
    destroy on 1, `+N bonus to AC and saving throws`. '' when nothing is found."""
    rec = srd_record(name)
    if rec is None:
        return ""
    desc = " ".join(rec.get("desc") or [])
    tags = []
    rarity = str((rec.get("rarity") or {}).get("name") or "").lower()
    if rarity in RARITIES:
        tags.append(rarity)
    if re.search(r"requires attunement", desc, re.I):
        tags.append("attune")
    m = re.search(r"has (\d+) charges", desc, re.I)
    if m:
        tags.append(f"charges {m.group(1)}/{m.group(1)}")
        r = re.search(r"regains (\d*d\d+(?:\s*\+\s*\d+)?) expended charges daily at (dawn|dusk|midnight|noon)", desc, re.I)
        if r:
            tags.append(f"recharge {r.group(1).replace(' ', '')} {r.group(2).lower()}")
        if re.search(r"roll a d20\. On a 1", desc, re.I):
            tags.append("destroy on 1")
    m = re.search(r"\+(\d) bonus to AC and saving throws", desc, re.I)
    if m:
        tags += [f"ac +{m.group(1)}", f"saves +{m.group(1)}"]
    else:
        m = re.search(r"\+(\d) bonus to (?:your )?AC\b", desc, re.I)
        if m:
            tags.append(f"ac +{m.group(1)}")
    m = re.search(r"\+(\d) bonus to attack and damage rolls", desc, re.I)
    if m:
        tags += [f"attack +{m.group(1)}", f"damage +{m.group(1)}"]
    return ", ".join(tags)
