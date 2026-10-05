"""`tempo tense|calm`, `pos`, `intent` — scene tempo and named placement (docs/design/06 →
`gm.py tempo`; 01 → Scene tempo L84-104; 02 → Spatial model; 04 → Stage table;
plan.md Phase 4 item 3).

`tempo tense [--adj "Mara +5 watching the room"] [--pos Mara @bar …]` writes the Stage
table under `## Tempo: tense`: everyone on stage (On stage bullets + present PCs) with
passive initiative 10 + DEX mod ± adj, ties → PCs. Running it again keeps existing
rows' positions, adjustments and intents (a new actor joined). `tempo calm` logs the
positions to the session log and drops the table.

`pos <name> <spec>` places a creature by name: `@feature`, `@feature N|S|E|W`,
`near <creature>`, or a raw `x,y,z` (space.py `State.place`, the one resolver). It edits
the Stage row, or the Combatants row in combat. `intent <name> "<text>"` sets a Stage
row's intent for this beat.

Also the shared current.md helpers `set_section()` and `set_tempo()` (scene, combat).
"""
import re
from pathlib import Path

from lib import campaign, creatures, journal, md, resolve, srd
from lib.errors import ToolError
import space

STAGE_HEADER = ["| init | name | glyph | side | pos | size | ref | adj | intent |",
                "|------|------|-------|------|-----|------|-----|-----|--------|"]
_ADJ = re.compile(r"^\s*(.+?)\s+([+\-−–]\s*\d+)\s*(.*)$")


class TempoError(ToolError):
    pass


# ---------- current.md helpers ----------

def set_section(doc, heading, lines):
    """Replace the body of the section starting with `heading` (keeping the heading
    line and one blank line before the next heading). Missing → appended."""
    span = doc.section(heading)
    if span is None:
        if doc.body and doc.body[-1].strip():
            doc.body.append("")
        doc.body += [f"## {heading}"] + list(lines)
        return
    start, end = span
    tail = [""] if end < len(doc.body) else []
    doc.body[start + 1:end] = list(lines) + tail


def tempo_word(doc):
    for _, lvl, text in doc.headings():
        m = re.match(r"^Tempo:\s*([a-z]+)", text, re.I)
        if m and lvl == 2:
            return m.group(1).lower()
    return "calm"


def set_tempo(doc, word, sub=()):
    """Rewrite the `## Tempo: …` heading (its trailing comment kept) and replace what
    sits under it (the Stage table, if any) with `sub`."""
    for i, lvl, text in doc.headings():
        if lvl == 2 and re.match(r"^Tempo:", text, re.I):
            m = re.search(r"\s*<!--.*-->\s*$", doc.body[i])
            doc.body[i] = f"## Tempo: {word}" + (("  " + m.group(0).strip()) if m else "")
            set_section(doc, "Tempo:", list(sub))
            return
    set_section(doc, f"Tempo: {word}", list(sub))


def in_combat(doc):
    return doc.table("Combatants") is not None


def stage_lines(rows):
    """Markdown lines for a Stage table (rows: dicts with the STAGE columns)."""
    cols = ["init", "name", "glyph", "side", "pos", "size", "ref", "adj", "intent"]
    return ["### Stage"] + STAGE_HEADER + [
        "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]


def unique_glyph(name, used):
    letters = [ch.upper() for ch in re.sub(r"\(PC\)", "", name) if ch.isalpha()]
    for ch in letters:
        if ch not in used:
            used.add(ch)
            return ch
    for d in "123456789":
        if d not in used:
            used.add(d)
            return d
    return "?"


def short_pc(doc):
    return str(doc.front.get("name") or "").split()[0]


# ---------- who is on stage ----------

class Actor:
    def __init__(self, name, ref, is_pc, creature=None, srd_name=None, goal=""):
        self.name, self.ref, self.is_pc = name, ref, is_pc
        self.creature, self.srd_name, self.goal = creature, srd_name, goal

    def dex(self):
        try:
            if self.creature is not None:
                return self.creature.mod("dex")
            if self.srd_name:
                return srd.monster(self.srd_name).mod("dex")
        except (creatures.CreatureError, creatures.SrdNotBuilt, srd.SrdError):
            pass
        return 0

    def size(self):
        try:
            if self.creature is not None:
                return self.creature.size()
            if self.srd_name:
                return srd.monster(self.srd_name).size
        except (creatures.CreatureError, creatures.SrdNotBuilt, srd.SrdError):
            pass
        return "M"

    def side(self):
        if self.is_pc:
            return "party"
        att = ""
        if self.creature is not None and self.creature.doc is not None:
            att = str(self.creature.front.get("attitude-to-party") or "").lower()
        return "foe" if att in ("hostile", "enemy") else "neutral"


def actors(state):
    """On stage NPC bullets + present PCs, in that order."""
    out = []
    for m in campaign.onstage(state):
        line = state.body[m.line]
        goal = re.search(r"goal:\s*(.+)$", line, re.I)
        goal = goal.group(1).strip() if goal else ""
        sm = re.search(r"\(\s*srd:\s*([^;×)]+?)\s*(?:[×x]\s*\d+)?\s*[;)]", line, re.I)
        if m.path:
            c = creatures.get(m.name, state)
            if c.is_pc:
                continue
            ref = "npcs/" + (m.slug or campaign.slugify(m.name))
            out.append(Actor(m.name, ref, False, c, None, goal or str(c.front.get("default-goal") or "")))
        elif sm:
            out.append(Actor(m.name, f"srd:{sm.group(1).strip().lower()}", False, None, sm.group(1).strip(), goal))
        else:
            out.append(Actor(m.name, "", False, None, None, goal))
    for doc in campaign.pcs():
        if doc.front.get("present") is False:
            continue
        slug = Path(doc.path).stem
        name = short_pc(doc)
        c = creatures.get(str(doc.front.get("name")), state)
        out.append(Actor(f"{name} (PC)", f"pcs/{slug}", True, c))
    return out


def parse_adj(texts):
    """{lower name: (int, "+5 watching the room")} from `--adj "Mara +5 watching"`."""
    out = {}
    for t in texts or []:
        m = _ADJ.match(t)
        if not m:
            raise TempoError(f"--adj wants \"<name> ±N [why]\", got {t!r}")
        n = int(re.sub(r"[−–]", "-", m.group(2)).replace(" ", ""))
        why = m.group(3).strip()
        out[m.group(1).strip().lower()] = (n, (f"{n:+d}" + (f" {why}" if why else "")))
    return out


def _adj_for(adj, name):
    key = re.sub(r"\s*\(pc\)", "", name.lower()).strip()
    for k, v in adj.items():
        if key == k or key.startswith(k) or k.startswith(key.split()[0]):
            return v
    return None


# ---------- commands ----------

def tense(adj_texts=(), pos_specs=()):
    state = campaign.load_state()
    if in_combat(state):
        raise TempoError("tempo: combat is running (combat end first)")
    adj = parse_adj(adj_texts)
    old = {re.sub(r"\s*\(pc\)", "", r.get("name", ""), flags=re.I).strip().lower(): r
           for r in (state.table("Stage").rows if state.table("Stage") else [])}
    rules = resolve.active_keys()
    rows, entries = {}, []
    used = set()
    for a in actors(state):
        key = re.sub(r"\s*\(pc\)", "", a.name, flags=re.I).strip().lower()
        prev = old.get(key, {})
        a_adj = _adj_for(adj, a.name)
        if a_adj is not None:
            n, text = a_adj
        else:
            m = re.match(r"^\s*([+\-−]\d+)", prev.get("adj", "") or "")
            n = int(m.group(1).replace("−", "-")) if m else 0
            text = prev.get("adj", "")
        init = 10 + a.dex() + n
        rows[a.name] = {"init": init, "name": a.name, "glyph": prev.get("glyph") or unique_glyph(a.name, used),
                        "side": prev.get("side") or a.side(), "pos": prev.get("pos") or "?",
                        "size": prev.get("size") or a.size(), "ref": a.ref, "adj": text,
                        "intent": prev.get("intent") or ("" if a.is_pc else a.goal)}
        used.add(rows[a.name]["glyph"])
        entries.append((a.name, init, a.is_pc))
    if not entries:
        raise TempoError("tempo tense: nobody on stage")
    ordered = [rows[name] for name, _, _ in resolve.initiative_order(entries, rules)]
    set_tempo(state, "tense", stage_lines(ordered))
    state.save()
    order = " · ".join(f"{r['name']} {r['init']}" for r in ordered)
    journal.log_delta(f"tempo tense · {order}", gm=True)
    lines = [f"[tempo tense: {order}]"]
    for spec in pos_specs or []:
        name, _, where = spec.partition(" ")
        if not where.strip():
            raise TempoError(f"--pos wants \"<name> <where>\", got {spec!r}")
        lines.append(place(name, where.strip())[0])
    return lines, {"order": [(r["name"], r["init"]) for r in ordered]}


def calm():
    state = campaign.load_state()
    if in_combat(state):
        raise TempoError("tempo: combat is running (combat end first)")
    stage = state.table("Stage")
    if stage is not None:
        placed = [f"{r['name']} {r['pos']}" for r in stage.rows if r.get("pos", "?") not in ("", "?")]
        if placed:
            journal.log_delta("positions at calm: " + " · ".join(placed), gm=True)
    set_tempo(state, "calm", [])
    state.save()
    journal.log_delta("tempo calm", gm=True)
    return ["[tempo calm]"], {}


def _row(state, name):
    """(table, index) of the creature's Combatants or Stage row."""
    c = creatures.get(name, state)
    if c.combat_index >= 0:
        return c, state.table("Combatants"), c.combat_index
    if c.stage_index >= 0:
        return c, state.table("Stage"), c.stage_index
    raise TempoError(f"{c.name} has no Stage or Combatants row (tempo tense first)")


def fmt_point(p):
    return "(" + ",".join(f"{v:g}" for v in p) + ")"


def place(name, spec):
    state = campaign.load_state()
    c, table, i = _row(state, name)
    row_name = re.sub(r"\s*\(PC\)", "", table.rows[i]["name"]).strip()
    st = space.State(str(campaign.state_path()))
    try:
        p = st.place(spec, mover=row_name)
    except space.SpaceError as e:
        raise TempoError(f"pos {row_name}: {e}") from None
    old = table.rows[i].get("pos", "?")
    table.set(i, "pos", fmt_point(p))
    state.save()
    journal.log_delta(f"pos {row_name} {spec} → {fmt_point(p)}" + (f" (was {old})" if old not in ("", "?") else ""),
                      gm=True)
    return f"[pos {row_name} {spec} → {fmt_point(p)}]", {"name": row_name, "pos": p}


def intent(name, text):
    state = campaign.load_state()
    c = creatures.get(name, state)
    if c.stage_index < 0:
        raise TempoError(f"{c.name} has no Stage row (tempo tense first)")
    t = state.table("Stage")
    t.set(c.stage_index, "intent", text.replace("|", "/"))
    state.save()
    journal.log_delta(f"intent {c.name}: {text}", gm=True)
    return f"[intent {c.name}: {text}]", {"name": c.name, "intent": text}


def cmd_tempo(ctx):
    a = ctx.args
    if a.mode == "tense":
        lines, data = tense(a.adj, a.pos)
    else:
        if a.adj or a.pos:
            raise TempoError("tempo calm takes no --adj/--pos")
        lines, data = calm()
    for line in lines:
        ctx.emit(line)
    ctx.result = data


def cmd_pos(ctx):
    line, data = place(ctx.args.name, " ".join(ctx.args.where))
    ctx.emit(line)
    ctx.result = data


def cmd_intent(ctx):
    line, data = intent(ctx.args.name, " ".join(ctx.args.text))
    ctx.emit(line)
    ctx.result = data


def register(sub, g):
    p = sub.add_parser("tempo", parents=[g], help="tense (Stage table, passive initiative) | calm")
    p.add_argument("mode", choices=["tense", "calm"])
    p.add_argument("--adj", action="append", default=[], help='"Mara +5 watching the room"')
    p.add_argument("--pos", action="append", default=[], help='"Mara @bar"')
    p.set_defaults(func=cmd_tempo)
    p = sub.add_parser("pos", parents=[g], help="place a creature: @feature [N|S|E|W] | near <creature> | x,y,z")
    p.add_argument("name")
    p.add_argument("where", nargs="+")
    p.set_defaults(func=cmd_pos)
    p = sub.add_parser("intent", parents=[g], help="set an NPC's intent for this beat")
    p.add_argument("name")
    p.add_argument("text", nargs="+")
    p.set_defaults(func=cmd_intent)
