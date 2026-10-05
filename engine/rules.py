"""Player overrules: `rule add|end|list`, `retcon`, `overrule-undo`, and the scope
expiry hook `end_scope()` (docs/design/06 → L170-217, keys L194-204; docs/design/02 →
Overrule L230-305; docs/design/04 → table-rules L540-557, session log L609-627;
rules/house-rules.md → Overrules L35-38; plan.md Phase 2 item 6).

Rows live in `<campaign>/state/table-rules.md`: `| id | rule | key | scope | since |
status |`. `since` = `S<session> t<turn>` (session = archived sessions + 1; turn = the
open or next turn of the session log). Newer wins per key; `rule add` reports the
active rule it overrides. Every `rule add|end` and `retcon` marks its journal batch as
an overrule (manifest `overrule: true`) and logs a public `[overrule] …` delta.

`overrule-undo` reverses the most recent overrule batch that has not been undone: it
restores that batch's before-images (all files except the session log, which only
gains an `[overrule] undo …` line) — unless a later batch touched one of those files,
in which case it refuses and lists the conflicts (06 L185-188). The restore is itself
journaled (its manifest records `undoes: "<entry>"`), so `undo` can take it back; an
overrule counts as undone only while such a batch exists, so after `undo` it can be
overrule-undone again. Old manifests are never edited.

Python API for later phases: `active_keys()` (re-exported from lib/resolve.py),
`end_scope("scene" | "combat" | "session")` -> list of bracket lines,
`session_number()`, `since()`.
"""
import re
from pathlib import Path

from lib import campaign, journal, md, resolve
from lib.errors import ToolError

active_keys = resolve.active_keys
SCOPES = ("scene", "combat", "session", "campaign")
END_REASON = {"scene": "scene over", "combat": "combat over", "session": "session over"}


class RuleError(ToolError):
    pass


def _path():
    return resolve.table_rules_path()


def _load():
    p = _path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        doc = md.new(p, "# Table rules\n<!-- Active /overrule rules. Precedence: these > "
                        "rules/house-rules.md > RAW. -->\n\n"
                        "| id | rule | key | scope | since | status |\n"
                        "|----|------|-----|-------|-------|--------|\n")
    else:
        doc = md.load(p)
    table = doc.table("Table rules")
    if table is None:
        raise RuleError(f"{p} has no | id | rule | key | scope | since | status | table")
    return doc, table


def session_number():
    hist = campaign.root() / "sessions" / "history"
    n = len(list(hist.glob("session-*.md"))) if hist.is_dir() else 0
    return n + 1


def since():
    turn, _ = journal.current_turn()
    return f"S{session_number()} t{turn}"


def _mark_overrule():
    b = journal.current()
    if b is not None:
        b.overrule = True


def _rid(text):
    m = re.fullmatch(r"R?(\d+)", text.strip(), re.I)
    if not m:
        raise RuleError(f"not a rule id: {text!r} (want R3)")
    return f"R{int(m.group(1))}"


# ---------- rule add / end / list ----------

def add(text, scope, key=None):
    text = text.strip()
    if not text:
        raise RuleError("rule add: the rule text is empty")
    scope = scope.strip()
    if scope.lower() not in SCOPES and not scope.lower().startswith("until "):
        raise RuleError(f"rule add: scope is {' | '.join(SCOPES)} | \"until …\"")
    note = ""
    if key:
        k, sep, v = key.partition("=")
        k, v = k.strip().lower(), v.strip().lower()
        if not sep or not k or not v:
            raise RuleError(f"rule add: --key is name=value, got {key!r}")
        if k in resolve.V1_KEYS:
            if not resolve.valid_value(k, v):
                raise RuleError(f"rule add: {k}={v} is not a valid value "
                                f"({resolve.V1_VALUES[k].replace(chr(92), '')})")
        else:
            note = f" · unknown key {k!r}: free text only"
        key = f"{k}={v}"
    _mark_overrule()
    doc, table = _load()
    overridden = None
    if key:
        k = key.split("=")[0]
        prev = resolve.active_keys(table.rows)
        if k in prev:
            overridden = prev[k]
    n = max((int(m.group(1)) for r in table.rows for m in [re.match(r"R(\d+)", r.get("id", ""))] if m),
            default=0) + 1
    rid = f"R{n}"
    table.append({"id": rid, "rule": text, "key": key or "", "scope": scope, "since": since(),
                  "status": "active"})
    doc.save()
    line = f"[rule {rid} added · {scope}" + (f" · {key}" if key else "")
    if overridden:
        line += f" · overrides {overridden['id']} ({key.split('=')[0]}={overridden['value']})"
    line += note + "]"
    journal.log_delta(f"[overrule] rule {rid} added: {text} ({scope})"
                      + (f" — overrides {overridden['id']}" if overridden else ""))
    return line, {"id": rid, "key": key, "scope": scope,
                  "overrides": overridden["id"] if overridden else None}


def end(rule_id, reason=None):
    rid = _rid(rule_id)
    _mark_overrule()
    doc, table = _load()
    i = table.find("id", rid)
    if i < 0:
        raise RuleError(f"no rule {rid}")
    if table.rows[i]["status"].lower() != "active":
        raise RuleError(f"{rid} is already {table.rows[i]['status']}")
    table.set(i, "status", f"ended ({reason})" if reason else "ended")
    doc.save()
    journal.log_delta(f"[overrule] rule {rid} ended" + (f": {reason}" if reason else ""))
    return f"[rule {rid} ended" + (f" — {reason}" if reason else "") + "]", {"id": rid, "reason": reason}


def list_rules():
    p = _path()
    if not p.exists():
        return ["[no table rules]"], {"rules": []}
    table = md.load(p).table("Table rules")
    rows = table.rows if table else []
    if not rows:
        return ["[no table rules]"], {"rules": []}
    winners = {v["id"] for v in resolve.active_keys(rows).values()}
    lines = []
    for r in rows:
        extra = ""
        if r["status"].lower() == "active" and r.get("key") and r["id"] not in winners \
                and r["key"].split("=")[0].strip().lower() in resolve.V1_KEYS:
            extra = " · overridden"
        lines.append(f"[{r['id']} · {r['rule']}" + (f" · {r['key']}" if r.get("key") else "")
                     + f" · {r['scope']} · {r['since']} · {r['status']}{extra}]")
    return lines, {"rules": rows}


def end_scope(scope):
    """End every active rule with this scope ('scene' | 'combat' | 'session'); called
    by `scene enter`, `combat end`, `session archive` (06 L209-211). Returns the
    `[rule R3 ended — combat over]` lines for the GM to announce."""
    if scope not in END_REASON:
        raise RuleError(f"end_scope: scope is {' | '.join(END_REASON)}")
    p = _path()
    if not p.exists():
        return []
    doc, table = _load()
    why = END_REASON[scope]
    lines = []
    for i, r in enumerate(table.rows):
        if r["status"].lower() == "active" and r["scope"].strip().lower() == scope:
            table.set(i, "status", f"ended ({why})")
            lines.append(f"[rule {r['id']} ended — {why}]")
    if lines:
        doc.save()
        for line in lines:
            journal.log_delta(line[1:-1])
    return lines


# ---------- retcon / overrule-undo ----------

def retcon(text, turn=None, session=None):
    """Log a retcon. With `session` (a past session's number) an `Erratum:` line is also
    appended to that session's history file; its original text is never edited (04)."""
    text = text.strip()
    if not text:
        raise RuleError("retcon: say what changed")
    _mark_overrule()
    t = turn if turn is not None else journal.current_turn()[0]
    where = f"session {session:02d} turn {t}" if session else f"turn {t}"
    journal.log_delta(f"[overrule] retcon {where}: {text}")
    if session:
        p = campaign.root() / "sessions" / "history" / f"session-{session:02d}.md"
        if not p.exists():
            raise RuleError(f"retcon --session {session}: no {p.name}")
        doc = md.load(p)
        if doc.body and doc.body[-1].strip():
            doc.body.append("")
        doc.body.append(f"Erratum ({since()}): turn {t} — {text}")
        doc.trailing_newline = True
        doc.save()
    return f"[retcon of {where} logged]", {"turn": t, "text": text, "session": session}


def _session_log_rel():
    return Path(campaign.session_log_path()).resolve().relative_to(campaign.root()).as_posix()


def overrule_undo():
    entries = journal.entries()
    undone = {m.get("undoes") for _, m in entries if m.get("undoes")}
    target = None
    for idx in range(len(entries) - 1, -1, -1):
        d, m = entries[idx]
        if m.get("overrule") and not m.get("undoes") and d.name not in undone:
            target = idx
            break
    if target is None:
        raise RuleError("no overrule batch to undo")
    entry, manifest = entries[target]
    log_rel = _session_log_rel()
    files = {rel: name for rel, name in manifest.get("files", {}).items() if rel != log_rel}
    conflicts = []
    for d, m in entries[target + 1:]:
        hit = sorted(set(m.get("files", {})) & set(files))
        if hit:
            conflicts.append(f"{d.name} ({m.get('command line', '')}: {', '.join(hit)})")
    if conflicts:
        raise RuleError("refused: later batches touched the same files — "
                        + "; ".join(conflicts) + " (undo those first, or correct by hand)")
    batch = journal.current()
    if batch is not None:
        batch.extra["undoes"] = entry.name
    journal.restore(entry, files, journaled=True)
    what = manifest.get("command line", "")
    journal.log_delta(f"[overrule] undo of overrule batch {entry.name}: {what}")
    return (f"[overrule undone: {what} · restored {', '.join(sorted(files)) or 'nothing'}]",
            {"batch": entry.name, "command line": what, "restored": sorted(files)})


# ---------- CLI ----------

def _emit(ctx, out):
    line, data = out
    if isinstance(line, list):
        for x in line:
            ctx.emit(x)
    else:
        ctx.emit(line)
    ctx.result = data


def cmd_rule(ctx):
    a = ctx.args
    if a.action == "add":
        if not a.text or a.scope is None:
            raise RuleError('rule add "text" --scope scene|combat|session|campaign|"until …" [--key k=v]')
        _emit(ctx, add(" ".join(a.text), a.scope, a.key))
    elif a.action == "end":
        if not a.text:
            raise RuleError("rule end R3 [--reason …]")
        _emit(ctx, end(a.text[0], a.reason))
    else:
        _emit(ctx, list_rules())


def cmd_retcon(ctx):
    _emit(ctx, retcon(ctx.args.text, ctx.args.turn, ctx.args.session))


def cmd_overrule_undo(ctx):
    _emit(ctx, overrule_undo())


def register(sub, g):
    p = sub.add_parser("rule", parents=[g], help='rule add "…" --scope S [--key k=v] | end R3 | list')
    p.add_argument("action", choices=["add", "end", "list"])
    p.add_argument("text", nargs="*")
    p.add_argument("--scope")
    p.add_argument("--key")
    p.add_argument("--reason")
    p.set_defaults(func=cmd_rule)

    p = sub.add_parser("retcon", parents=[g], help='retcon "what changed" --turn N')
    p.add_argument("text")
    p.add_argument("--turn", type=int)
    p.add_argument("--session", type=int, help="a past session: also appends an Erratum line to its history")
    p.set_defaults(func=cmd_retcon)

    p = sub.add_parser("overrule-undo", parents=[g], help="reverse the most recent overrule batch")
    p.set_defaults(func=cmd_overrule_undo)
