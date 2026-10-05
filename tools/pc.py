"""`gm.py pc draft|check|card|write|edit|roster|level-pending|levelup` — character intake,
edits and level-ups (planning/06 → Character tools; 02 → Session start & characters,
Character intake loop, Level-up flow; 04 → PC file; rules/house-rules.md → HP max or
roll; plan.md Phase 6).

Drafts live in `<campaign>/.gm/drafts/<slug>.json` until `pc write` (02: interrupted
intake resumes). Every number comes from lib/chargen.py (SRD data + `hp-method`); the
model only turns the player's words into `--set` fields. `overrides` are never
re-derived.

    pc draft <slug> --set race="half-orc" class=barbarian level=3 subclass=berserker \\
                    --equip "greataxe; 4 javelins; explorer's pack" [--item +"…" | -"…"]
                    [--from-sheet <file>] [--hp-rolls 7,9]
    pc check <slug> · pc card <slug> · pc write <slug>
    pc edit <pc> --set … --item +"longbow"          (an existing PC file, same checks)
    pc roster [--present Kira,Kael] [--absent Bren]
    pc level-pending <pc> [--to N]
    pc levelup <pc> --plan | --choose asi="dex+2" spells="+guiding bolt" [--hp-roll N] --apply

`hp-method: roll` rolls the hit die publicly when a draft first needs it (levels 2..N)
or at `levelup --apply` (`--hp-rolls` / `--hp-roll` take player-reported rolls instead).
"""
import json
import re
from pathlib import Path

from lib import campaign, chargen, gametime, journal, md, xp
from lib.chargen import ABBR, as_list, key, mod, sign
from lib.errors import ToolError

ORDER = ["name", "player", "location", "race", "class", "subclass", "level", "background", "hp", "ac",
         "passive-perception", "passive-investigation", "speed", "conditions", "scores", "prof", "saves",
         "skills", "senses", "hit-dice", "hp-method", "autopilot", "present", "level-pending", "xp",
         "overrides"]
LIST_KEYS = {"skills", "race-skills", "expertise", "cantrips", "spells", "prepared", "equipment",
             "ability-bonuses", "asi", "hp-rolls", "skill-profs"}
SCORE_KEYS = {"scores", "base-scores"}
DEFAULT_AUTOPILOT = "follows the group, defends themselves, makes no major decisions"


class PcError(ToolError):
    pass


# ---------- drafts ----------

def draft_path(slug):
    return campaign.root() / ".gm" / "drafts" / f"{campaign.slugify(slug)}.json"


def load_draft(slug, must=True):
    p = draft_path(slug)
    if not p.exists():
        if must:
            raise PcError(f"no draft for {slug!r} (pc draft {slug} --set …)")
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_draft(slug, d):
    p = draft_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(p, json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def parse_scores(text):
    """'str 15 dex 14 …' / 'str:15, dex:14' / '15,14,13,12,10,8' (STR..CHA order)."""
    pairs = re.findall(r"(str|dex|con|int|wis|cha)\w*\s*[:= ]\s*(\d+)", text, re.I)
    if pairs:
        return {a.lower()[:3]: int(v) for a, v in pairs}
    nums = [int(n) for n in re.findall(r"\d+", text)]
    if len(nums) == 6:
        return dict(zip(ABBR, nums))
    raise PcError(f"can't read scores {text!r} (want 'str 15 dex 14 …' or six numbers STR..CHA)")


def apply_sets(d, sets):
    for item in sets or []:
        k, sep, v = item.partition("=")
        if not sep:
            raise PcError(f"--set wants key=value, got {item!r}")
        k, v = k.strip().lower(), v.strip().strip('"')
        if k in ABBR:
            d.setdefault("scores", {})[k] = int(v)
        elif k in SCORE_KEYS:
            d[k] = parse_scores(v)
        elif k == "overrides":
            ov = d.setdefault("overrides", {})
            for part in as_list(v):
                ok, _, ovv = part.partition(":")
                ov[ok.strip()] = int(ovv) if ovv.strip().lstrip("-").isdigit() else ovv.strip()
        elif k in LIST_KEYS:
            d[k] = as_list(v)
        elif k == "level":
            d[k] = int(v)
        elif v == "":
            d.pop(k, None)
        else:
            d[k] = v


def apply_items(d, items):
    eq = list(d.get("equipment") or [])
    for it in items or []:
        it = it.strip()
        if it.startswith("-"):
            name = it[1:].strip().strip('"').lower()
            hit = next((x for x in eq if x.lower() == name or chargen.parse_item(x)[1].lower() == name), None)
            if hit is None:
                raise PcError(f"--item {it!r}: not in the equipment ({'; '.join(eq) or 'none'})")
            eq.remove(hit)
        else:
            eq.append(it.lstrip("+").strip().strip('"'))
    d["equipment"] = eq


def from_sheet(text):
    """Best-effort fields from a pasted sheet (`Name: …`, `Race: …`, `STR 15` …)."""
    d = {}
    for label, k in (("name", "name"), ("player", "player"), ("race", "race"), ("class", "class"),
                     ("subclass", "subclass"), ("archetype", "subclass"), ("level", "level"),
                     ("background", "background"), ("equipment", "equipment"), ("skills", "skills"),
                     ("cantrips", "cantrips"), ("spells", "spells")):
        m = re.search(rf"^\s*{label}\s*:\s*(.+)$", text, re.I | re.M)
        if m and k not in d:
            d[k] = m.group(1).strip()
    m = re.search(r"\bclass\s*(?:&|and)?\s*level\s*:\s*([a-z]+)\s+(\d+)", text, re.I)
    if m:
        d["class"], d["level"] = m.group(1), m.group(2)
    pairs = re.findall(r"\b(STR|DEX|CON|INT|WIS|CHA)\w*\s*[: ]\s*(\d{1,2})\b", text, re.I)
    if len({a.upper() for a, _ in pairs}) == 6:
        d["scores"] = {a.lower()[:3]: int(v) for a, v in pairs}
    out = {}
    for k, v in d.items():
        if k in LIST_KEYS:
            out[k] = as_list(v)
        elif k == "level":
            out[k] = int(re.sub(r"\D", "", str(v)) or 1)
        else:
            out[k] = v
    return out


def roll_hp(d, roller, label):
    """Roll missing hit-die rolls publicly (hp-method roll). Returns bracket lines."""
    if str(d.get("hp-method") or "").lower() != "roll":
        return []
    cls = chargen.find("Classes", d.get("class", "")) if d.get("class") else None
    lvl = int(d.get("level") or 1)
    if not cls:
        return []
    rolls = [int(x) for x in as_list(d.get("hp-rolls")) if str(x).isdigit()]
    out = []
    die = int(cls["hit_die"])
    while len(rolls) < lvl - 1:
        n = roller.die(die)
        rolls.append(n)
        line = f"HP roll {label} level {len(rolls) + 1}: d{die} {n}"
        journal.log_delta(line)
        out.append(f"[{line}]")
    d["hp-rolls"] = [str(r) for r in rolls]
    return out


# ---------- PC file ↔ draft ----------

def pc_doc(name):
    m = campaign.resolve(name)
    if not m.is_pc or not m.path:
        raise PcError(f"{name!r} is not a PC file")
    return md.load(m.path)


def _section_lines(doc, heading):
    span = doc.section(heading)
    return [] if span is None else doc.body[span[0] + 1:span[1]]


def equipped(doc):
    for line in _section_lines(doc, "Inventory"):
        m = re.match(r"^\s*-\s*Equipped:\s*(.*)$", line, re.I)
        if m:
            parts = re.split(r",|;|\s\+\s", m.group(1))
            return [p.strip() for p in parts if p.strip()]
    return []


def draft_from_file(doc):
    f = doc.front
    d = {"_file": True}
    for k in ("name", "player", "location", "race", "class", "subclass", "background", "hp-method",
              "autopilot", "present", "level-pending", "xp"):
        if f.get(k) not in (None, ""):
            d[k] = f[k]
    d["level"] = int(f.get("level") or 1)
    scores = f.get("scores") if isinstance(f.get("scores"), dict) else {}
    d["scores"] = {a: int(scores.get(a, 10)) for a in ABBR}
    d["overrides"] = dict(f.get("overrides") or {})
    prof = 2 + (d["level"] - 1) // 4
    profs, expert = [], []
    for sk, v in (f.get("skills") or {}).items():
        sk = key(sk)
        ab = chargen.SKILL_ABILITY.get(sk)
        if not ab or not isinstance(v, int):
            continue
        m = mod(d["scores"][ab])
        if v >= m + 2 * prof:
            expert.append(sk)
            profs.append(sk)
        elif v >= m + prof:
            profs.append(sk)
    d["skill-profs"], d["expertise"] = profs, expert
    d["equipment"] = equipped(doc)
    t = doc.table("Spells")
    for r in (t.rows if t else []):
        src = r.get("source", "").lower()
        name = r.get("spell", "").strip()
        if not name:
            continue
        if "high elf" in r.get("notes", "").lower():
            d["race-cantrip"] = name
        elif src == "cantrip":
            d.setdefault("cantrips", []).append(name)
        elif src in ("known", "spellbook"):
            d.setdefault("spells", []).append(name)
    return d


def _fmt_row(cols, row):
    return "| " + " | ".join(str(row.get(c, "")) for c in cols) + " |"


def _set_table(doc, heading, cols, rows, keep):
    """Replace a section's table rows: `rows` (derived) plus existing rows for which
    `keep(row)` is true. Creates the section/table when missing."""
    t = doc.table(heading)
    old = [r for r in (t.rows if t else []) if keep(r)]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("-" * (len(c) + 2) for c in cols) + "|"]
    lines += [_fmt_row(cols, r) for r in rows + old]
    span = doc.section(heading)
    if span is None:
        if doc.body and doc.body[-1].strip():
            doc.body.append("")
        doc.body += [f"## {heading}"] + lines
        return
    if t is not None:
        start = t.start
        end = start + 2 + len(t.rows)
        doc.body[start:end] = lines
    else:
        at = span[0] + 1
        while at < span[1] and doc.body[at].strip().startswith("<!--"):
            at += 1
        doc.body[at:at] = lines


def update_file(doc, draft, s, extra_features=(), equipment_changed=False):
    """Write the derived fields into an existing PC file (overrides win; other rows,
    sections and prose are kept)."""
    ov = doc.front.get("overrides") or draft.get("overrides") or {}
    f = s.fields
    old_level = int(doc.front.get("level") or 1)

    def put(k, v):
        if k in ov:
            return
        doc.set_front(k, v)

    for k in ("race", "class", "subclass", "background", "hp-method", "autopilot", "name", "player"):
        if draft.get(k) not in (None, "") and k not in ov:
            doc.set_front(k, draft[k])
    put("level", f["level"])
    if "hp" in f and "hp" not in ov:
        old = doc.front.get("hp") if isinstance(doc.front.get("hp"), dict) else {}
        new_max = f["hp"]["max"]
        cur = int(old.get("current", new_max)) + (new_max - int(old.get("max", new_max)))
        h = {"current": max(0, min(cur, new_max)), "max": new_max}
        if old.get("temp"):
            h["temp"] = old["temp"]
        doc.set_front("hp", h)
    for k in ("ac", "passive-perception", "passive-investigation", "speed", "scores", "prof", "saves",
              "skills", "senses"):
        if k in f:
            put(k, f[k])
    if "hit-dice" in f and "hit-dice" not in ov:
        old = doc.front.get("hit-dice") if isinstance(doc.front.get("hit-dice"), dict) else {}
        left = int(old.get("left", old_level)) + (f["level"] - old_level)
        doc.set_front("hit-dice", {"die": f["hit-dice"]["die"], "left": max(0, min(left, f["level"]))})
    weapons = {a["name"] for a in s.attacks}
    srd_weapon = lambda r: chargen.equipment_record(r.get("name", "")) is not None and (  # noqa: E731
        (chargen.equipment_record(r.get("name", "")) or {}).get("equipment_category", {}).get("index") == "weapon")
    if s.attacks or equipment_changed:
        _set_table(doc, "Attacks", ["name", "hit", "damage", "range", "notes"], s.attacks,
                   keep=lambda r: r.get("name") not in weapons and not srd_weapon(r))
    if s.resources:
        old = {r.get("resource"): r for r in (doc.table("Resources").rows if doc.table("Resources") else [])}
        rows = []
        for r in s.resources:
            o = old.get(r["resource"])
            if o and str(o.get("max")) == str(r["max"]):
                r = dict(r, current=o.get("current", r["max"]))
            rows.append(r)
        names = {r["resource"] for r in rows}
        _set_table(doc, "Resources", ["resource", "current", "max", "recovers"], rows,
                   keep=lambda r: r.get("resource") not in names)
    if s.spells:
        t = doc.table("Spells")
        have = {r.get("spell", "").lower() for r in (t.rows if t else [])}
        new = [r for r in s.spells if r["spell"].lower() not in have]
        if new:
            _set_table(doc, "Spells", ["spell", "level", "source", "notes"], new, keep=lambda r: True)
    if "spell-dc" in f:
        _refresh_spell_numbers(doc, f, s)
    for feat in extra_features:
        doc.append_line("Features & abilities", feat)
    if equipment_changed:
        eq = "; ".join(draft.get("equipment") or [])
        span = doc.section("Inventory")
        done = False
        if span is not None:
            for i in range(span[0] + 1, span[1]):
                if re.match(r"^\s*-\s*Equipped:", doc.body[i], re.I):
                    doc.body[i] = f"- Equipped: {eq}"
                    done = True
                    break
        if not done:
            doc.append_line("Inventory", f"- Equipped: {eq}")
    stats = " | ".join(f"{a.upper()} {f['scores'][a]} ({sign(mod(f['scores'][a]))})" for a in ABBR) \
        if f.get("scores") else None
    if stats:
        span = doc.section("Stats")
        if span is not None:
            for i in range(span[0] + 1, span[1]):
                if re.match(r"^\s*STR\b", doc.body[i]):
                    doc.body[i] = stats
                else:
                    doc.body[i] = _refresh_prose(doc.body[i], f)


def _refresh_prose(line, f):
    """Numbers in hand-written Stats prose: `Spell save DC 13 · spell attack +5`,
    `Saves WIS +5, CHA +3`, `Insight +5`. The words are left alone."""
    if "spell-dc" in f:
        line = re.sub(r"(?i)(spell save DC )\d+", lambda m: f"{m.group(1)}{f['spell-dc']}", line)
        line = re.sub(r"(?i)(spell attack )[+-]\d+", lambda m: f"{m.group(1)}{sign(f['spell-attack'])}", line)
    if re.search(r"(?i)\bsaves\b", line) and f.get("scores"):
        for ab in f.get("saves", []):
            total = mod(f["scores"][ab]) + f["prof"]
            line = re.sub(rf"\b{ab.upper()} [+-]\d+", f"{ab.upper()} {sign(total)}", line)
    for sk, v in (f.get("skills") or {}).items():
        label = sk.replace("-", " ")
        line = re.sub(rf"(?i)\b({re.escape(label)}) [+-]\d+", lambda m, v=v: f"{m.group(1)} {sign(v)}", line)
    return line


def _refresh_spell_numbers(doc, f, s):
    """Spell save DC / attack wherever the file states them: the Spells summary line
    (`save DC 13 · attack +5 · … = 6 per long rest`) and Attacks rows for spells
    (`DC 13 DEX` / `+5`)."""
    dc, atk = f["spell-dc"], sign(f["spell-attack"])
    span = doc.section("Spells")
    if span is not None:
        for i in range(span[0] + 1, span[1]):
            line = doc.body[i]
            if re.search(r"save DC \d+", line):
                line = re.sub(r"save DC \d+", f"save DC {dc}", line)
                line = re.sub(r"attack [+-]\d+", f"attack {atk}", line)
                cls = getattr(s, "cls", None) or {}
                factor = chargen.PREPARED.get(cls.get("index", ""))
                if factor and s.mods:
                    n = max(1, s.mods[s.spell_ability] + int(f["level"] * factor))
                    line = re.sub(r"= \d+ per long rest", f"= {n} per long rest", line)
                doc.body[i] = line
    t = doc.table("Spells")
    spells = {r.get("spell", "").lower() for r in (t.rows if t else [])}
    t = doc.table("Attacks")
    if t is None:
        return
    for i, r in enumerate(t.rows):
        name = r.get("name", "").strip().lower()
        if name not in spells and chargen.find("Spells", name) is None:
            continue
        hit = r.get("hit", "")
        if re.match(r"^DC \d+", hit):
            t.set(i, "hit", re.sub(r"^DC \d+", f"DC {dc}", hit))
        elif re.fullmatch(r"[+-]\d+", hit.strip()):
            t.set(i, "hit", atk)


def render_new(slug, draft, s):
    """A new PC file (04 → PC file; key order = ORDER)."""
    f = s.fields
    state = campaign.load_state()
    lines = ["---"]
    vals = {
        "name": draft.get("name"), "player": draft.get("player", ""),
        "location": state.front.get("party-location", ""), "race": draft.get("race"),
        "class": draft.get("class"), "subclass": draft.get("subclass", ""), "level": f["level"],
        "background": draft.get("background", ""), "hp": f.get("hp", {"current": 0, "max": 0}),
        "ac": f.get("ac", 10), "passive-perception": f.get("passive-perception", 10),
        "passive-investigation": f.get("passive-investigation", 10), "speed": f.get("speed", 30),
        "conditions": [], "scores": f.get("scores", {}), "prof": f["prof"], "saves": f.get("saves", []),
        "skills": f.get("skills", {}), "senses": f.get("senses", []), "hit-dice": f.get("hit-dice", {}),
        "hp-method": draft.get("hp-method", ""), "autopilot": draft.get("autopilot") or DEFAULT_AUTOPILOT,
        "present": True, "level-pending": "", "xp": draft.get("xp", xp.start_xp(f["level"])),
        "overrides": draft.get("overrides") or {},
    }
    for k in ORDER:
        v = md.fmt_value(None if vals[k] == "" else vals[k])
        lines.append(f"{k}: {v}" if v != "" else f"{k}:")
    lines.append("---")
    name = draft.get("name")
    body = ["", f"# {name}", "", "## Stats",
            " | ".join(f"{a.upper()} {f['scores'][a]} ({sign(mod(f['scores'][a]))})" for a in ABBR),
            "<!-- Human-readable mirror of the frontmatter; tools use the frontmatter. -->", "",
            "## Attacks", "| name | hit | damage | range | notes |", "|------|-----|--------|-------|-------|"]
    body += [_fmt_row(["name", "hit", "damage", "range", "notes"], a) for a in s.attacks]
    body += ["", "## Resources", "| resource | current | max | recovers |", "|----------|---------|-----|----------|"]
    body += [_fmt_row(["resource", "current", "max", "recovers"], r) for r in s.resources]
    body += ["", "## Spells", "<!-- Casters only. source: cantrip | known | prepared | always | custom -->"]
    if "spell-dc" in f:
        body.append(f"Spellcasting ability {s.spell_ability.upper()} · save DC {f['spell-dc']} · "
                    f"attack {sign(f['spell-attack'])}")
    body += ["| spell | level | source | notes |", "|-------|-------|--------|-------|"]
    body += [_fmt_row(["spell", "level", "source", "notes"], r) for r in s.spells]
    body += ["", "## Features & abilities"]
    body += [f"- **{x}**" for x in dict.fromkeys(s.features)] or ["(none yet)"]
    if s.race:
        body.append(f"- **{(s.sub or s.race)['name']}:** " + ", ".join(s.race_traits + (s.fields.get("senses") or [])))
    for c in as_list(draft.get("custom-features")):
        body.append(f"- {c} (custom)")
    eq = "; ".join(draft.get("equipment") or [])
    body += ["", "## Inventory", f"- Equipped: {eq}", "- Pack:", f"- Coin: {draft.get('coin', '')}".rstrip(),
             "", "## Background & story"]
    story = [draft.get(k) for k in ("look", "personality") if draft.get(k)]
    body += story or ["(short backstory + 1–2 goals the GM can hook)"]
    if draft.get("goal"):
        body.append(f"- **Goal:** {draft['goal']}")
    body += ["", "## Journal", "(GM appends durable developments here)", ""]
    return "\n".join(lines + body)


# ---------- commands ----------

def cmd_draft(ctx):
    a = ctx.args
    d = load_draft(a.slug, must=False)
    if a.from_sheet:
        p = Path(a.from_sheet)
        if not p.is_absolute():
            p = campaign.root() / ".gm" / "drafts" / a.from_sheet
            if not p.exists():
                p = Path(a.from_sheet)
        d.update(from_sheet(p.read_text(encoding="utf-8")))
    apply_sets(d, a.set)
    if a.equip is not None:
        d["equipment"] = as_list(a.equip)
    if a.item:
        apply_items(d, a.item)
    if a.hp_rolls:
        d["hp-rolls"] = as_list(a.hp_rolls)
    d.setdefault("xp", xp.start_xp(d.get("level") or 1))
    lines = roll_hp(d, ctx.roller, a.slug)
    save_draft(a.slug, d)
    s = chargen.derive(d)
    lines += chargen.check_lines(a.slug, d, s)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"draft": d, "missing": s.missing}


def cmd_check(ctx):
    d = load_draft(ctx.args.slug)
    s = chargen.derive(d)
    for line in chargen.check_lines(ctx.args.slug, d, s):
        ctx.emit(line)
    ctx.result = {"missing": s.missing, "fields": s.fields, "warnings": s.warnings}


def cmd_card(ctx):
    d = load_draft(ctx.args.slug)
    s = chargen.derive(d)
    for line in chargen.card_lines(ctx.args.slug, d, s):
        ctx.emit(line)
    ctx.result = {"fields": s.fields}


def cmd_write(ctx):
    slug = campaign.slugify(ctx.args.slug)
    d = load_draft(slug)
    s = chargen.derive(d)
    if s.missing:
        raise PcError("pc write: still missing — " + "; ".join(s.missing))
    p = campaign.path("pcs", slug)
    if p.exists():
        doc = md.load(p)
        update_file(doc, d, s, equipment_changed=True)
        doc.save()
        what = "updated"
    else:
        doc = md.new(p, render_new(slug, d, s))
        doc.save()
        what = "written"
    draft_path(slug).unlink()
    journal.log_delta(f"pc {what} {d.get('name')} ({d.get('race')} {d.get('class')} {s.fields['level']})")
    ctx.emit(f"[pc {what}: pcs/{slug}.md · HP {s.fields.get('hp', {}).get('max')} · AC {s.fields.get('ac')}]")
    ctx.result = {"path": str(p), "fields": s.fields}


def cmd_edit(ctx):
    a = ctx.args
    doc = pc_doc(a.pc)
    d = draft_from_file(doc)
    before = dict(d)
    apply_sets(d, a.set)
    if a.item:
        apply_items(d, a.item)
    for k in ("hp-method", "autopilot", "player", "name"):
        if d.get(k) != before.get(k) and d.get(k) is not None:
            doc.set_front(k, d[k])
    s = chargen.derive(d)
    update_file(doc, d, s, equipment_changed=bool(a.item) or "equipment" in " ".join(a.set or []))
    if "overrides" in " ".join(a.set or []):
        doc.set_front("overrides", d["overrides"])
        for k, v in d["overrides"].items():
            doc.set_front(k, v)
    doc.save()
    changes = ", ".join((a.set or []) + [f"item {i}" for i in a.item or []])
    journal.log_delta(f"pc edit {doc.front.get('name')}: {changes}")
    ctx.emit(f"[pc edit {doc.front.get('name')} · {changes} · AC {doc.front.get('ac')} · "
             f"HP {doc.front.get('hp', {}).get('max') if isinstance(doc.front.get('hp'), dict) else '?'}]")
    for w in s.warnings:
        ctx.emit(f"[warning: {w}]")
    ctx.result = {"fields": s.fields, "warnings": s.warnings}


def cmd_roster(ctx):
    a = ctx.args
    present = [x.strip() for x in as_list(a.present)]
    absent = [x.strip() for x in as_list(a.absent)]
    out = []
    for names, flag in ((present, True), (absent, False)):
        for n in names:
            doc = pc_doc(n)
            doc.set_front("present", flag)
            doc.save()
            out.append(f"{doc.front.get('name')} {'present' if flag else 'absent (autopilot)'}")
    if not out:
        for doc in campaign.pcs():
            out.append(f"{doc.front.get('name')} {'present' if doc.front.get('present') is not False else 'absent'}")
        ctx.emit("[roster: " + " · ".join(out) + "]")
        return
    journal.log_delta("roster: " + " · ".join(out))
    ctx.emit("[roster: " + " · ".join(out) + "]")


def cmd_level_pending(ctx):
    doc = pc_doc(ctx.args.pc)
    lvl = int(doc.front.get("level") or 1)
    to = ctx.args.to or lvl + 1
    if to <= lvl or to > 20:
        raise PcError(f"level-pending: {to} must be above level {lvl} (max 20)")
    doc.set_front("level-pending", to)
    doc.save()
    journal.log_delta(f"level-pending {doc.front.get('name')} → {to}")
    ctx.emit(f"[level-pending {doc.front.get('name')}: {lvl} → {to}]")


# ---------- level-up ----------

def plan(doc):
    d = draft_from_file(doc)
    cur = d["level"]
    pending = doc.front.get("level-pending")
    if not isinstance(pending, int) or pending <= cur:
        raise PcError(f"{doc.front.get('name')}: no level-up pending (pc level-pending {doc.front.get('name').split()[0]})")
    to = cur + 1
    cls = chargen.find("Classes", d.get("class", ""))
    if cls is None:
        raise PcError(f"{d.get('class')!r} is not an SRD class: level it up by hand (custom)")
    ci = cls["index"]
    sub = next((x for x in chargen._load("Subclasses") if x["class"]["index"] == ci and
                chargen.key(d.get("subclass", "")) in (x["index"], chargen.key(x["name"]))), None)
    si = sub["index"] if sub else None
    b0, _ = chargen.level_rows(ci, cur, si)
    b1, s1 = chargen.level_rows(ci, to, si)
    die = int(cls["hit_die"])
    con = mod(d["scores"]["con"])
    granted, choices = [], []
    if b1.get("prof_bonus") != (b0 or {}).get("prof_bonus"):
        granted.append(f"proficiency +{b0.get('prof_bonus')} → +{b1['prof_bonus']}")
    granted.append(f"hit dice {cur}d{die} → {to}d{die}")
    method = str(d.get("hp-method") or "").lower()
    if method == "max":
        granted.append(f"HP +{max(1, die + con)} (max: d{die} {die} + CON {sign(con)})")
    elif method == "roll":
        granted.append(f"HP: d{die} {sign(con)} CON, rolled publicly at --apply (or --hp-roll N)")
    else:
        choices.append(("hp-method", "hp-method: max or roll (asked once)"))
    F = chargen._by_index("Features")
    new_feats = []
    for row in (b1, s1):
        for f in (row or {}).get("features", []):
            fs = (F.get(f["index"]) or {}).get("feature_specific") or {}
            if "ability-score-improvement" in f["index"]:
                choices.append(("asi", "ability score improvement: +2 to one score or +1 to two (or a feat: custom)"))
            elif "expertise_options" in fs:
                choices.append(("expertise", f"{f['name']}: 2 proficient skills for expertise"))
            elif "subfeature_options" in fs and "fighting-style" in f["index"]:
                choices.append(("fighting-style", f"{f['name']}"))
            elif f["name"].lower() in chargen.PLACEHOLDERS:
                if not si and f["name"].lower() not in ("domain spells", "oath spells", "circle spells"):
                    opts = [x["name"] for x in chargen._load("Subclasses") if x["class"]["index"] == ci]
                    choices.append(("subclass", f"subclass ({', '.join(opts)}; any other is custom)"))
            else:
                new_feats.append(f["name"])
                if "subfeature_options" in fs or "invocations" in fs:
                    choices.append((key(f["name"]), f"{f['name']}: choose per the SRD"))
    if new_feats:
        granted.append("features: " + ", ".join(new_feats))
    sc0, sc1 = (b0 or {}).get("spellcasting") or {}, (b1 or {}).get("spellcasting") or {}
    slot_diff = [f"slot {n}: {sc0.get(f'spell_slots_level_{n}', 0)}→{sc1.get(f'spell_slots_level_{n}', 0)}"
                 for n in range(1, 10) if sc1.get(f"spell_slots_level_{n}", 0) != sc0.get(f"spell_slots_level_{n}", 0)]
    if slot_diff:
        granted.append("spell " + ", ".join(slot_diff))
    dc = (sc1.get("cantrips_known") or 0) - (sc0.get("cantrips_known") or 0)
    if dc > 0:
        choices.append(("cantrips", f"{dc} new cantrip(s)"))
    if ci == "wizard":
        choices.append(("spells", "2 wizard spells for the spellbook (level ≤ highest slot)"))
    else:
        dk = (sc1.get("spells_known") or 0) - (sc0.get("spells_known") or 0)
        if dk > 0:
            choices.append(("spells", f"{dk} new spell(s) known (you may also swap one: -old)"))
    if to in (5, 11, 17) and sc1.get("cantrips_known"):
        granted.append("cantrip damage dice step up")
    return {"doc": doc, "draft": d, "cur": cur, "to": to, "cls": cls, "si": si, "die": die, "con": con,
            "granted": granted, "choices": choices, "features": new_feats}


def _choose(text):
    out = {}
    for item in text or []:
        k, sep, v = item.partition("=")
        if not sep:
            raise PcError(f"--choose wants key=value, got {item!r}")
        out[k.strip().lower()] = v.strip().strip('"')
    return out


def cmd_levelup(ctx):
    a = ctx.args
    doc = pc_doc(a.pc)
    p = plan(doc)
    name = doc.front.get("name")
    chosen = _choose(a.choose)
    if a.plan or not a.apply:
        lines = [f"[LEVEL-UP PLAN] {name}: {p['cur']} → {p['to']}"]
        lines += [f"GRANTED   {g}" for g in p["granted"]]
        open_ = [c for c in p["choices"] if c[0] not in chosen]
        lines += [f"CHOICE    {k}: {t}" + (f" → {chosen[k]}" if k in chosen else "") for k, t in p["choices"]]
        if not p["choices"]:
            lines.append("CHOICE    — (nothing to choose)")
        lines.append(f"{len(open_)} choice(s) open — answer with --choose key=value …, then --apply"
                     if open_ else "ready: --apply")
        for line in lines:
            ctx.emit(line)
        ctx.result = {"granted": p["granted"], "choices": p["choices"]}
        return
    missing = [t for k, t in p["choices"] if k not in chosen]
    if missing:
        raise PcError("levelup --apply: unanswered — " + "; ".join(missing))
    d = p["draft"]
    note = []
    if "hp-method" in chosen:
        d["hp-method"] = chosen["hp-method"]
        doc.set_front("hp-method", chosen["hp-method"])
    if "asi" in chosen:
        for part in re.split(r"[\s,]+", chosen["asi"].lower()):
            m = re.match(r"^(str|dex|con|int|wis|cha)\+(\d)$", part)
            if m:
                d["scores"][m.group(1)] = min(20, d["scores"][m.group(1)] + int(m.group(2)))
            elif part:
                raise PcError(f"asi: can't read {part!r} (want dex+2 or str+1,con+1)")
        note.append(f"ASI {chosen['asi']}")
    if "feat" in chosen:
        note.append(f"feat {chosen['feat']} (custom)")
    if "subclass" in chosen:
        d["subclass"] = chosen["subclass"]
        doc.set_front("subclass", chosen["subclass"])
    if "expertise" in chosen:
        d["expertise"] = list(d.get("expertise") or []) + as_list(chosen["expertise"])
    if "fighting-style" in chosen:
        d["fighting-style"] = chosen["fighting-style"]
    for k in ("cantrips", "spells"):
        if k in chosen:
            cur = list(d.get(k) or [])
            for part in as_list(chosen[k]):
                if part.startswith("-"):
                    cur = [x for x in cur if key(x) != key(part[1:])]
                else:
                    cur.append(part.lstrip("+").strip())
            d[k] = cur
    # HP
    con_new = mod(d["scores"]["con"])
    method = str(d.get("hp-method") or "").lower()
    out = []
    if method == "roll":
        if a.hp_roll is not None:
            r = int(a.hp_roll)
        else:
            r = ctx.roller.die(p["die"])
        gain_txt = f"d{p['die']} {r} {sign(con_new)} CON"
        out.append(f"[HP roll {name} level {p['to']}: {gain_txt}]")
        gain = max(1, r + con_new)
    else:
        gain = max(1, p["die"] + con_new)
        gain_txt = f"max {p['die']} {sign(con_new)} CON"
    gain += (con_new - p["con"]) * p["cur"]      # a CON increase is retroactive (PHB)
    d["level"] = p["to"]
    s = chargen.derive(d)
    s.fields.pop("hp", None)     # HP grows by the level's gain, never re-derived here
    hp = doc.front.get("hp") if isinstance(doc.front.get("hp"), dict) else {"current": 0, "max": 0}
    old_max = int(hp.get("max", 0))
    new = {"current": int(hp.get("current", 0)) + gain, "max": old_max + gain}
    if hp.get("temp"):
        new["temp"] = hp["temp"]
    feats = [f"- **{x}** (level {p['to']})" for x in p["features"]]
    if "feat" in chosen:
        feats.append(f"- **{chosen['feat']}** (feat, level {p['to']}, custom)")
    for k, v in chosen.items():
        if k not in ("asi", "feat", "subclass", "expertise", "fighting-style", "cantrips", "spells", "hp-method"):
            feats.append(f"- {k}: {v} (level {p['to']})")
    update_file(doc, d, s, extra_features=feats)
    if "hp" not in (doc.front.get("overrides") or {}):
        doc.set_front("hp", new)
    pend = doc.front.get("level-pending")
    doc.set_front("level-pending", pend if isinstance(pend, int) and pend > p["to"] else None)
    state = campaign.load_state()
    when = state.front.get("in-game-datetime", "")
    summary = f"reached level {p['to']} — HP +{gain} ({gain_txt})" + (f"; {'; '.join(note)}" if note else "")
    doc.append_line("Journal", f"- {when}: {summary}")
    doc.save()
    journal.log_delta(f"levelup {name} {p['cur']}→{p['to']} · HP {old_max}→{old_max + gain}"
                      + (f" · {'; '.join(note)}" if note else ""))
    out.append(f"[levelup {name} {p['cur']}→{p['to']} · HP {old_max}→{old_max + gain} · AC {doc.front.get('ac')}"
               + (f" · {'; '.join(note)}" if note else "") + "]")
    for line in out:
        ctx.emit(line)
    ctx.result = {"level": p["to"], "hp": new}


def register(sub, g):
    p = sub.add_parser("pc", parents=[g], help="character intake, edits and level-ups")
    ps = p.add_subparsers(dest="pc_cmd", metavar="<pc command>")
    ps.required = True
    q = ps.add_parser("draft", parents=[g])
    q.add_argument("slug")
    q.add_argument("--set", action="extend", nargs="+", default=[])
    q.add_argument("--equip")
    q.add_argument("--item", action="extend", nargs="+", default=[])
    q.add_argument("--from-sheet")
    q.add_argument("--hp-rolls")
    q.set_defaults(func=cmd_draft)
    for name, fn in (("check", cmd_check), ("card", cmd_card), ("write", cmd_write)):
        q = ps.add_parser(name, parents=[g])
        q.add_argument("slug")
        q.set_defaults(func=fn)
    q = ps.add_parser("edit", parents=[g])
    q.add_argument("pc")
    q.add_argument("--set", action="extend", nargs="+", default=[])
    q.add_argument("--item", action="extend", nargs="+", default=[])
    q.set_defaults(func=cmd_edit)
    q = ps.add_parser("roster", parents=[g])
    q.add_argument("--present")
    q.add_argument("--absent")
    q.set_defaults(func=cmd_roster)
    q = ps.add_parser("level-pending", parents=[g])
    q.add_argument("pc")
    q.add_argument("--to", type=int)
    q.set_defaults(func=cmd_level_pending)
    q = ps.add_parser("levelup", parents=[g])
    q.add_argument("pc")
    q.add_argument("--plan", action="store_true")
    q.add_argument("--choose", nargs="+", default=[])
    q.add_argument("--hp-roll", type=int)
    q.add_argument("--apply", action="store_true")
    q.set_defaults(func=cmd_levelup)
