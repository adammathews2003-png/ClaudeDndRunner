"""Frontmatter + markdown-table read/write for campaign files (planning/06 → Parsing
contract, L83-92; planning/04 → Parsing contract, L7-11; plan.md Phase 1 item 1).

A `Doc` is the file as lines. The frontmatter is parsed once into `Doc.front`
(insertion-ordered, values typed per the 04 subset); trailing `# comments` are kept
apart in `Doc.front_comments`. Every edit rewrites single lines, never the whole file
from parsed data, so comments, key order and untouched lines survive byte-for-byte.

Line endings (plan.md 0.2): read with utf-8 + splitlines(); write with the newline the
file already uses (`\\r\\n` if present, else `\\n`); new files get `\\n`. Writes are
atomic: `path + ".tmp"` then `os.replace`.

`parse_point` is moved here verbatim from space.py L29-35 (space.py will import it in
Phase 4).

`before_write` is a list of callables `(path) -> None` run before each save; the undo
journal (lib/journal.py) registers itself there so md.py stays dependency-free.
"""
import os
import re

before_write = []  # hooks: f(path) called before a Doc (or write_text) overwrites path

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
BOM = "﻿"


# ---------- geometry helper (verbatim from space.py) ----------

def parse_point(text):
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]
    if len(nums) == 2:
        nums.append(0.0)
    if len(nums) != 3:
        raise ValueError(f"not a point: {text!r}")
    return tuple(nums)


# ---------- atomic file writing ----------

def read_text(path):
    """Returns (text, newline, bom): the file's newline ('\\r\\n' or '\\n') and whether
    it started with a U+FEFF byte-order mark (stripped from `text`)."""
    with open(path, encoding="utf-8", newline="") as f:
        raw = f.read()
    bom = raw.startswith(BOM)
    if bom:
        raw = raw[1:]
    return raw, ("\r\n" if "\r\n" in raw else "\n"), bom


def write_text(path, text, newline="\n"):
    """Atomic write: path.tmp then os.replace. `text` uses '\\n'; it is rewritten to
    `newline` on the way out. Runs the `before_write` hooks first."""
    for hook in before_write:
        hook(path)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", newline) if newline != "\n" else text)
    os.replace(tmp, path)


# ---------- frontmatter values ----------

def _split_comment(text):
    """Split an unquoted value from its trailing comment: a '#' at the start or preceded
    by whitespace. Returns (value, comment_with_leading_space)."""
    if text.lstrip().startswith("#"):
        return "", text
    m = re.search(r"\s#", text)
    if m:
        return text[:m.start()], text[m.start():]
    return text, ""


def _split_quoted(text):
    """`text` starts with a quote. Returns (inner, rest_after_closing_quote). Inside
    double quotes `\\"` and `\\\\` are unescaped (the inverse of fmt_scalar)."""
    q = text[0]
    out = []
    i = 1
    while i < len(text):
        ch = text[i]
        if ch == "\\" and q == '"' and i + 1 < len(text) and text[i + 1] in '"\\':
            out.append(text[i + 1])
            i += 2
            continue
        if ch == q:
            return "".join(out), text[i + 1:]
        out.append(ch)
        i += 1
    return "".join(out), ""  # unterminated: take the rest


def _split_items(text):
    """Split a list/map body on top-level commas, honouring quotes."""
    items, buf, q = [], [], None
    for ch in text:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            buf.append(ch)
        elif ch == ",":
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf or items:
        items.append("".join(buf))
    return [s.strip() for s in items if s.strip()]


def parse_scalar(text):
    """int / float / bool / None (empty) / str; quoted strings unquoted."""
    text = text.strip()
    if text == "":
        return None
    if text[0] in "\"'":
        inner, _ = _split_quoted(text)
        return inner
    low = text.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"[+-]?\d+", text):
        return int(text)
    if re.fullmatch(r"[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?", text):
        return float(text)
    return text


def parse_value(text):
    """Value part of a frontmatter line (comment already removed)."""
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return [parse_scalar(s) for s in _split_items(text[1:-1])]
    if text.startswith("{") and text.endswith("}"):
        out = {}
        for item in _split_items(text[1:-1]):
            k, _, v = item.partition(":")
            out[k.strip()] = parse_scalar(v)
        return out
    return parse_scalar(text)


def _needs_quotes(s):
    return (s == "" or s != s.strip() or ": " in s or s.endswith(":") or " #" in s
            or s[0] in "\"'[{#&*!|>%@`" or s.lower() in ("true", "false", "null", "~")
            or re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", s) is not None)


def fmt_scalar(value, quoted=False):
    """One scalar as frontmatter text: None → '', bools → true/false, numbers as-is,
    strings bare unless they need quoting (or `quoted`); `\\` and `"` are escaped."""
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if quoted or _needs_quotes(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def fmt_value(value, quoted=False):
    """A frontmatter value as text: `[a, b]` for lists, `{a: 1}` for dicts, else a
    scalar (see fmt_scalar)."""
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(fmt_scalar(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {fmt_scalar(v)}" for k, v in value.items()) + "}"
    return fmt_scalar(value, quoted)


def _parse_front_line(line):
    """Returns (key, value, comment, quoted) or None for blank/comment-only lines."""
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    key, sep, rest = line.partition(":")
    if not sep or not re.fullmatch(r"[A-Za-z0-9_.-]+", key.strip()):
        return None
    rest = rest.lstrip(" \t") if rest[:1] in (" ", "\t") else rest
    if rest.strip().startswith(("\"", "'")):
        inner, tail = _split_quoted(rest.strip())
        return key.strip(), inner, tail.rstrip() if tail.strip().startswith("#") else "", True
    body, comment = _split_comment(rest)
    return key.strip(), parse_value(body), comment.rstrip(), False


# ---------- tables ----------

def _cells(line):
    return line.strip().strip("|").split("|")


class Table:
    """The first markdown table under a heading. `header` keeps the original case;
    `rows` are dicts keyed by lowercased header names with stripped values (short
    rows are padded with ''; cells beyond the header are kept in `extras` and written
    back on edit). Edits rewrite the row's line in place using the header row's
    column widths (pad, never truncate). `start` is the index of the header line in
    `doc.body`."""

    def __init__(self, doc, start):
        self.doc = doc
        self.start = start
        raw = _cells(doc.body[start])
        self.header = [h.strip() for h in raw]
        self.keys = [h.lower() for h in self.header]
        self.widths = [len(c) for c in raw]
        self.rows = []
        self.extras = []  # per row: cells beyond the header's columns
        n = len(self.keys)
        for line in doc.body[start + 2:]:
            if not line.lstrip().startswith("|"):
                break
            cells = [c.strip() for c in _cells(line)]
            cells += [""] * (n - len(cells))
            self.rows.append(dict(zip(self.keys, cells[:n])))
            self.extras.append(cells[n:])

    def __len__(self):
        return len(self.rows)

    def _line_index(self, i):
        return self.start + 2 + i

    def _render(self, row, extra=()):
        out = [(" " + str(row.get(key, "") or "") + " ").ljust(width)
               for key, width in zip(self.keys, self.widths)]
        out += [f" {cell} " for cell in extra]
        return "|" + "|".join(out) + "|"

    def _check(self, col):
        col = col.lower()
        if col not in self.keys:
            raise KeyError(f"no column {col!r} in table (columns: {', '.join(self.keys)})")
        return col

    def set(self, i, col, value):
        self.rows[i][self._check(col)] = "" if value is None else str(value).strip()
        self.doc.body[self._line_index(i)] = self._render(self.rows[i], self.extras[i])

    def append(self, row):
        clean = {self._check(k): ("" if v is None else str(v).strip()) for k, v in row.items()}
        full = {k: clean.get(k, "") for k in self.keys}
        self.rows.append(full)
        self.extras.append([])
        self.doc.body.insert(self._line_index(len(self.rows) - 1), self._render(full))

    def insert(self, i, row):
        """Insert a row before row index `i` (i == len(self) appends)."""
        clean = {self._check(k): ("" if v is None else str(v).strip()) for k, v in row.items()}
        full = {k: clean.get(k, "") for k in self.keys}
        i = max(0, min(i, len(self.rows)))
        self.rows.insert(i, full)
        self.extras.insert(i, [])
        self.doc.body.insert(self._line_index(i), self._render(full))

    def remove(self, i):
        del self.doc.body[self._line_index(i)]
        del self.extras[i]
        return self.rows.pop(i)

    def find(self, col, value):
        """Index of the first row whose `col` equals `value` (case-insensitive), or -1."""
        col, value = col.lower(), str(value).strip().lower()
        for i, row in enumerate(self.rows):
            if row.get(col, "").lower() == value:
                return i
        return -1


# ---------- documents ----------

class Doc:
    """One markdown file as lines: `head` (the frontmatter block, parsed into `front`)
    and `body`; edits touch single lines and `save()` writes them back as they were."""

    def __init__(self, path, raw, newline, bom=False):
        self.path = str(path)
        self.newline = newline
        self.bom = bom
        self.trailing_newline = raw.endswith(("\n", "\r"))
        lines = raw.splitlines()
        self.front = {}
        self.front_comments = {}
        self.front_quoted = set()
        self._front_lines = {}  # key -> index into self.head
        self.head = []
        if lines and lines[0].strip() == "---":
            close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
            if close is not None:
                self.head = lines[:close + 1]
                lines = lines[close + 1:]
                for i, line in enumerate(self.head[1:close], start=1):
                    parsed = _parse_front_line(line)
                    if parsed is None:
                        continue
                    key, value, comment, quoted = parsed
                    self.front[key] = value
                    if comment:
                        self.front_comments[key] = comment.strip()
                    if quoted:
                        self.front_quoted.add(key)
                    self._front_lines[key] = i
        self.body = lines

    # -- frontmatter --
    def set_front(self, key, value):
        """Rewrite one frontmatter line (keeps its comment and position); a new key is
        appended just before the closing ---."""
        text = fmt_value(value, quoted=key in self.front_quoted)
        if key in self._front_lines:
            i = self._front_lines[key]
            old = self.head[i]
            tail = ""
            if key in self.front_comments:
                at = old.rfind(self.front_comments[key])
                pre = old[:at]
                tail = pre[len(pre.rstrip()):] + old[at:]
            line = f"{key}: {text}" if text != "" else f"{key}:"
            self.head[i] = line + tail
        else:
            if not self.head:
                self.head = ["---", "---"]
            line = f"{key}: {text}" if text != "" else f"{key}:"
            self.head.insert(len(self.head) - 1, line)
            self._front_lines[key] = len(self.head) - 2
        self.front[key] = value

    # -- sections --
    def headings(self):
        """[(index, level, text)] for every heading line in the body; lines inside
        ``` / ~~~ fences are not headings."""
        out = []
        fence = None
        for i, line in enumerate(self.body):
            f = _FENCE.match(line)
            if f:
                if fence is None:
                    fence = f.group(1)
                elif f.group(1) == fence:
                    fence = None
                continue
            if fence:
                continue
            m = _HEADING.match(line)
            if m:
                out.append((i, len(m.group(1)), m.group(2)))
        return out

    def section(self, heading):
        """(start, end) of the first `## `/`### ` section (the `# ` title too, for
        files like table-rules.md whose table sits under it) whose text starts with
        `heading` (case-insensitive; leading #s in the argument are ignored). `end` is
        the index of the next heading of the same or a higher level, or len(body).
        None when absent."""
        want = heading.lstrip("#").strip().lower()
        heads = self.headings()
        for n, (i, level, text) in enumerate(heads):
            if text.lower().startswith(want):
                end = len(self.body)
                for j, lvl, _ in heads[n + 1:]:
                    if lvl <= level:
                        end = j
                        break
                return i, end
        return None

    def table(self, heading):
        """First table under the heading (table_rows semantics from space.py: skip to
        the first '|' line; another heading first means no table)."""
        span = self.section(heading)
        if span is None:
            return None
        i = span[0] + 1
        while i < span[1]:
            line = self.body[i]
            if line.lstrip().startswith("|"):
                if i + 1 < len(self.body) and re.match(r"^\s*\|?\s*:?-", self.body[i + 1]):
                    return Table(self, i)
                return None
            if _HEADING.match(line):  # a sub-heading (### under ##) comes first
                return None
            i += 1
        return None

    def append_line(self, heading, text):
        """Append a line at the end of a section (after its last non-blank line). The
        section is created at the end of the body when missing."""
        span = self.section(heading)
        if span is None:
            if self.body and self.body[-1].strip():
                self.body.append("")
            self.body.append(heading if heading.startswith("#") else f"## {heading}")
            self.body.append(text)
            return len(self.body) - 1
        start, end = span
        i = end
        while i > start + 1 and not self.body[i - 1].strip():
            i -= 1
        self.body.insert(i, text)
        return i

    # -- output --
    def text(self):
        """The whole file as '\\n'-joined text (BOM and trailing newline as loaded)."""
        out = "\n".join(self.head + self.body)
        if self.trailing_newline:
            out += "\n"
        return BOM + out if self.bom else out

    def save(self, path=None):
        """Write back atomically with the file's own newline (see write_text)."""
        write_text(path or self.path, self.text(), self.newline)


def load(path):
    """Read a campaign file into a Doc."""
    raw, newline, bom = read_text(path)
    return Doc(path, raw, newline, bom)


def new(path, text=""):
    """A Doc for a file that does not exist yet (newline '\\n')."""
    return Doc(path, text, "\n")
