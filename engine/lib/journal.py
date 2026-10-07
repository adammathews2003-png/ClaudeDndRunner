"""Undo journal and session-log delta writer (docs/design/06 → Undo journal L219-222,
turn blocks L156-168, touched-files lint L431-434; docs/design/04 → session log
L609-620 and tool-owned files L600-608; docs/design/05 #4; plan.md Phase 1 item 3).

`Batch` snapshots the before-image of every file saved through lib/md.py while it
is active into `<campaign>/.gm/journal/<NNNN>/` with a `manifest.json`
(`files`, `command line`, `turn`, `step`, `overrule`). The last 50 batches are kept.
`undo()` restores the latest batch and logs `undo turn N step M`.

Turn blocks in `sessions/session-current.md`: `[turn N]` with nothing after it is the
open block; `log_delta` opens one (first delta after a `log`) and appends `  - text`
lines; `log_turn(summary)` closes it by writing `[turn N] summary`.
"""
import json
import os
import re
import shutil
import time
from pathlib import Path

from . import campaign, md

KEEP = 50
_TURN = re.compile(r"^\[turn (\d+)\](.*)$")
_PLACEHOLDER = re.compile(r"^\(no turns yet.*\)\s*$")

_active = None  # the current Batch, if any
_gm_only = 0    # > 0 inside gm_only(): every delta is a (GM) line (carousing, Phase 16)


class JournalError(Exception):
    pass


class NothingToUndo(JournalError):
    pass


def journal_dir(root=None):
    """`<campaign>/.gm/journal` (of `root`, default the active campaign)."""
    return (root or campaign.root()) / ".gm" / "journal"


def _entries(root=None):
    """Batch directories, numerically ordered (0001 … 9999, 10000 …)."""
    d = journal_dir(root)
    if not d.is_dir():
        return []
    return sorted((p for p in d.iterdir() if p.is_dir() and p.name.isdigit()),
                  key=lambda p: int(p.name))


def _rel(path):
    """Campaign-relative posix path, or JournalError for a path outside the campaign."""
    try:
        return Path(path).resolve().relative_to(campaign.root()).as_posix()
    except ValueError:
        raise JournalError(f"refusing to write outside the campaign: {path}") from None


class Batch:
    """`with Batch("do atk …") as b:` — every md.save inside snapshots its file first.
    `b.touched` lists the campaign-relative paths written (for lint layer 2). Entering
    is free: the campaign is located and the journal entry (turn, step, directory)
    opened on the first write, so read-only commands never touch the campaign."""

    def __init__(self, command_line="", overrule=False):
        self.command_line = command_line
        self.overrule = overrule
        self.extra = {}  # further manifest keys (e.g. `undoes` for overrule-undo)
        self.touched = []
        self.files = {}  # rel path -> snapshot file name or None (did not exist)
        self.dir = None
        self.root = None
        self.turn = None
        self.step = None
        self._outer = None

    # -- context manager --
    def __enter__(self):
        global _active
        if _active is not None:
            # nested batches (a command inside `do`) share the outer one
            self._outer = _active
            return _active
        _active = self
        md.before_write.append(self.snapshot)
        return self

    def __exit__(self, exc_type, exc, tb):
        global _active
        if self._outer is not None:
            return False
        md.before_write.remove(self.snapshot)
        _active = None
        if self.dir is not None:
            self._write_manifest()
            _prune(self.root)
        return False

    def _open(self):
        """First write: number the turn/step and create the entry directory."""
        self.turn, _ = current_turn()
        self.root = campaign.root()   # a command may switch campaigns later (scaffold)
        self.step = 1 + sum(1 for e in _entries(self.root) if _manifest(e).get("turn") == self.turn)
        self.dir = _next_dir(self.root)
        self.dir.mkdir(parents=True, exist_ok=True)

    # -- snapshots --
    def snapshot(self, path):
        rel = _rel(path)
        if rel == ".gm" or rel.startswith(".gm/"):
            return  # tool scratch (brief-hash, drafts, the journal itself) is not canon
        if rel in self.files:
            return
        if self.dir is None:
            self._open()
        if os.path.exists(path):
            name = rel.replace("/", "__")
            shutil.copyfile(path, self.dir / name)
            self.files[rel] = name
        else:
            self.files[rel] = None
        self.touched.append(rel)
        self._write_manifest()

    def _write_manifest(self):
        manifest = {
            "files": self.files,
            "command line": self.command_line,
            "turn": self.turn,
            "step": self.step,
            "overrule": self.overrule,
            **self.extra,
            "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        tmp = self.dir / "manifest.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        os.replace(tmp, self.dir / "manifest.json")


def current():
    """The active Batch or None."""
    return _active


def _next_dir(root=None):
    """The next entry directory: highest number + 1, zero-padded to four digits."""
    entries = _entries(root)
    n = max(int(e.name) for e in entries) + 1 if entries else 1
    return journal_dir(root) / f"{n:04d}"


def _manifest(entry):
    try:
        return json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _prune(root=None):
    entries = _entries(root)
    for old in entries[:-KEEP] if len(entries) > KEEP else []:
        shutil.rmtree(old, ignore_errors=True)


def entries():
    """[(dir, manifest)] oldest first."""
    return [(e, _manifest(e)) for e in _entries()]


def undo():
    """Restore the latest batch's before-images (deleting files it created), drop the
    batch from the journal, and log `undo turn N step M`. Returns the manifest."""
    found = _entries()
    if not found:
        raise NothingToUndo("nothing to undo")
    entry = found[-1]
    manifest = _manifest(entry)
    restore(entry, manifest.get("files", {}))
    shutil.rmtree(entry, ignore_errors=True)
    turn, step = manifest.get("turn"), manifest.get("step")
    _without_journal(log_delta, f"undo turn {turn} step {step}")
    return manifest


def restore(entry, files, journaled=False):
    """Copy the before-images `files` ({rel: snapshot name or None}) of journal entry
    directory `entry` back into the campaign; None means the batch created the file,
    so it is deleted. With `journaled`, the active Batch snapshots each file first
    (so the restore itself can be undone)."""
    root = campaign.root()
    for rel, name in files.items():
        target = root / rel
        if journaled and _active is not None:
            _active.snapshot(str(target))
        if name is None:
            if target.exists():
                target.unlink()
            continue
        tmp = str(target) + ".tmp"
        shutil.copyfile(Path(entry) / name, tmp)
        os.replace(tmp, target)


def _without_journal(fn, *args, **kwargs):
    """Run fn with the active batch's snapshot hook suspended."""
    hooks = list(md.before_write)
    md.before_write[:] = [h for h in hooks if getattr(h, "__self__", None) is not _active]
    try:
        return fn(*args, **kwargs)
    finally:
        md.before_write[:] = hooks


# ---------- session log ----------

def _load_log():
    p = campaign.session_log_path()
    if p.exists():
        return md.load(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    return md.new(p, "# Session log — current\n")


def _scan(doc):
    """(index_of_last_turn_line, number, is_open) or (None, 0, False)."""
    last = None
    for i, line in enumerate(doc.body):
        m = _TURN.match(line)
        if m:
            last = (i, int(m.group(1)), m.group(2).strip() == "")
    return last or (None, 0, False)


def current_turn(doc=None):
    """(N, is_open): the open turn's number, or the number the next delta would open."""
    doc = doc or _load_log()
    _, n, is_open = _scan(doc)
    return (n, True) if is_open else (n + 1, False)


def _append(doc, line):
    """Append a line at the end of the log (replacing the 'no turns yet' placeholder)."""
    for i in range(len(doc.body) - 1, -1, -1):
        if _PLACEHOLDER.match(doc.body[i]):
            doc.body[i] = line
            return i
        if doc.body[i].strip():
            break
    while doc.body and not doc.body[-1].strip():
        doc.body.pop()
    doc.body.append(line)
    doc.trailing_newline = True
    return len(doc.body) - 1


class gm_only:
    """`with journal.gm_only():` logs every delta inside as a `(GM)` line (carousing's
    results stay behind the screen until the morning reveal, 02 → Phase 16)."""

    def __enter__(self):
        global _gm_only
        _gm_only += 1
        return self

    def __exit__(self, *exc):
        global _gm_only
        _gm_only -= 1
        return False


def log_delta(text, gm=False):
    """Append `  - text` under the open turn block, opening `[turn N]` first when none
    is open. `(GM) ` prefixes GM-only lines. Returns N."""
    gm = gm or _gm_only > 0
    doc = _load_log()
    idx, n, is_open = _scan(doc)
    if not is_open:
        n += 1
        idx = _append(doc, f"[turn {n}]")
    # insert after the last delta of the open block
    end = idx + 1
    while end < len(doc.body) and doc.body[end].startswith("  - "):
        end += 1
    doc.body.insert(end, "  - " + ("(GM) " if gm else "") + text)
    doc.save()
    return n


def log_turn(summary):
    """`log "<summary>"`: write the summary on the open `[turn N]` line and close it;
    with no open block, write a closed `[turn N] summary` block. Returns N."""
    summary = summary.strip()
    if not summary:
        raise JournalError("log: the summary is empty")
    doc = _load_log()
    idx, n, is_open = _scan(doc)
    if is_open:
        doc.body[idx] = f"[turn {n}] {summary}"
    else:
        n += 1
        _append(doc, f"[turn {n}] {summary}")
    doc.save()
    return n
