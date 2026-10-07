"""`gm.py srd monster|spell|condition|item <name> [--write <npc>]` — SRD lookups from the local
data (docs/design/06 → `gm.py srd`; 02 → Combat mode; plan.md Phase 4 item 5).

`monster` prints the compact stat block (lib/srd.py). `--write <npc>` copies its numbers
into that NPC file the first time it's used, so later edits stick: frontmatter
`statblock: custom (srd: <name>)`, `size`, `scores`, `prof`, `saves`, `skills`, `ac`,
`hp`, `xp` and damage traits, plus an `## Attacks` table. Refused when the file already
has `scores` (a block written earlier wins). Never touches the network.
"""
from lib import campaign, journal, md
from lib import srd as data
from lib.errors import ToolError


class SrdCmdError(ToolError):
    pass


def write_block(npc, mon):
    """Copy Monster `mon` into the NPC file named `npc` (slug, path or name)."""
    m = campaign.resolve(npc)
    if m.doc is None or m.is_pc:
        raise SrdCmdError(f"srd --write: {npc!r} is not an NPC file")
    doc = m.doc
    if "scores" in doc.front:
        raise SrdCmdError(f"srd --write: {doc.path} already has a stat block (scores); edit it instead")
    doc.set_front("statblock", f"custom (srd: {mon.name})")
    doc.set_front("size", mon.size)
    doc.set_front("scores", dict(mon.scores))
    doc.set_front("prof", mon.prof)
    doc.set_front("saves", [a for a in mon.saves])
    doc.set_front("skills", dict(mon.skills))
    doc.set_front("ac", mon.ac)
    doc.set_front("hp", {"current": mon.hp, "max": mon.hp})
    doc.set_front("passive-perception", mon.passive_perception())
    doc.set_front("xp", mon.xp)
    for key, vals in (("resistances", mon.resist), ("immunities", mon.immune),
                      ("vulnerabilities", mon.vuln)):
        if vals:
            doc.set_front(key, list(vals))
    attacks = mon.attacks()
    if attacks and doc.table("Attacks") is None:
        if doc.body and doc.body[-1].strip():
            doc.body.append("")
        doc.body += ["## Attacks", "| name | hit | damage | range | notes |", "|------|-----|--------|-------|-------|"]
        for a in attacks:
            doc.body.append(f"| {a['name']} | {a['hit']} | {a['damage']} | {a['range']} | {a['notes']} |")
        doc.trailing_newline = True
    doc.save()
    journal.log_delta(f"srd {mon.name} written to {campaign.slugify(m.name)}", gm=True)
    return f"[srd {mon.name} → {doc.path.replace(chr(92), '/').split('/')[-2]}/{doc.path.replace(chr(92), '/').split('/')[-1]}]"


def cmd_srd(ctx):
    a = ctx.args
    name = " ".join(a.name)
    if a.kind == "monster":
        mon = data.monster(name)
        lines = mon.block()
        if a.write:
            lines.append(write_block(a.write, mon))
    elif a.kind == "item":
        if a.write:
            raise SrdCmdError("srd --write is for monsters")
        lines = data.magic_item(name)
    elif a.kind == "spell":
        if a.write:
            raise SrdCmdError("srd --write is for monsters")
        lines = data.spell(name)
    else:
        if a.write:
            raise SrdCmdError("srd --write is for monsters")
        lines = data.condition(name)
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("srd", parents=[g], help="SRD monster | spell | condition | item lookup")
    p.add_argument("kind", choices=["monster", "spell", "condition", "item"])
    p.add_argument("name", nargs="+")
    p.add_argument("--write", metavar="NPC", help="monster: copy the block into this NPC file")
    p.set_defaults(func=cmd_srd)
