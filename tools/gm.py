"""Entry point for the GM tools: `python tools/gm.py <command> …` (planning/06 →
Design principles L25-49, Code layout L60-81; plan.md Phase 1 item 5).

Global options (`--campaign DIR`, `--seed N`, `--json`) are accepted before the
command or after it, so a `do` step can carry its own. Subcommands come from the
command modules that exist beside this file (each exposes `register(sub, globals)`);
`space` forwards to space.py; `do "<cmd>; <cmd>"` runs the steps left to right inside
one undo batch and stops at the first failure, listing what already applied; `log
"<summary>"` closes the open turn block (06 L156-168). Both `do` and `log` first log
a pending Wacky Juice (lib/wacky.py; skipped when the batch has `juice waive`).
Nothing else lives here.
"""
import argparse
import contextlib
import importlib
import io
import json
import os
import shlex
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import campaign, dice, gametime, journal, wacky  # noqa: E402
from lib.errors import ToolError  # noqa: E402

USAGE_LINE = "gm.py [--campaign DIR] [--seed N] [--json] <command> [args…]"
USAGE = "usage: " + USAGE_LINE
COMMAND_MODULES = ("scene", "combat", "clock", "travel", "rest", "lint", "session",
                   "srd", "pc", "world", "mutations", "inventory", "roll", "rules",
                   "brief", "juice")


class CommandError(Exception):
    """A command failed; the message is printed as the failure line. `output` holds
    lines that still need printing first (what earlier `do` steps produced)."""

    def __init__(self, message, output=()):
        super().__init__(message)
        self.output = list(output)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CommandError(message)


class Ctx:
    """What a command gets: parsed args, campaign root, output sink."""

    def __init__(self, args, batch_roller=None):
        self.args = args
        self.seed = getattr(args, "seed", None)
        self.json = bool(getattr(args, "json", False))
        self.lines = []
        self.result = {}
        self.batch_roller = batch_roller
        self._roller = None

    @property
    def roller(self):
        """The dice for this command: its own `--seed`, else the `do` batch's shared
        Roller (seeded from `gm.py --seed N do …`), else a SystemRandom one."""
        if self._roller is None:
            seed = getattr(self.args, "seed", None)
            if seed is not None:
                self._roller = dice.Roller(seed)
            elif self.batch_roller is not None:
                self._roller = self.batch_roller
            else:
                self._roller = dice.Roller()
        return self._roller

    def emit(self, line):
        self.lines.append(line)


# ---------- parser ----------

def _globals():
    g = argparse.ArgumentParser(add_help=False)
    g.add_argument("--campaign", default=argparse.SUPPRESS, help="campaign folder (overrides .campaign)")
    g.add_argument("--seed", type=int, default=argparse.SUPPRESS, help="deterministic RNG")
    g.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="machine output")
    return g


def build_parser():
    g = _globals()
    parser = Parser(prog="gm.py", parents=[g], usage=USAGE_LINE)
    sub = parser.add_subparsers(dest="command", parser_class=Parser, metavar="<command>")

    p = sub.add_parser("do", parents=[g], help='run "cmd; cmd; …" as one batch')
    p.add_argument("steps", help="commands separated by ';'")
    p.set_defaults(func=cmd_do)

    p = sub.add_parser("log", parents=[g], help="close the open turn block with a summary")
    p.add_argument("summary")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("space", parents=[g], help="forward to space.py", add_help=False)
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_space)

    for name in COMMAND_MODULES:
        try:
            mod = importlib.import_module(name)
        except ImportError as e:
            if e.name != name:
                raise  # a broken import inside an existing module must surface
            continue
        if hasattr(mod, "register"):
            mod.register(sub, g)
    parser.commands = set(sub.choices)
    return parser


# ---------- built-in commands ----------

def cmd_log(ctx):
    wacky.consume()
    n = journal.log_turn(ctx.args.summary)
    ctx.emit(f"[turn {n} logged]")
    ctx.result = {"turn": n}


def cmd_space(ctx):
    """Run space.py's CLI in-process; its stdout becomes this command's output lines
    and a non-zero exit becomes a CommandError (so `do` ordering and --json hold)."""
    import space
    argv = list(ctx.args.rest)
    if argv[:1] == ["--"]:
        argv = argv[1:]
    old = sys.argv
    sys.argv = ["space.py"] + argv
    out = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()) as err:
            space.main()
    except SystemExit as e:
        code = e.code
    finally:
        sys.argv = old
    for line in out.getvalue().splitlines():
        ctx.emit(line)
    ctx.result = {"lines": out.getvalue().splitlines()}
    if code not in (None, 0):
        # space.py exits with a message string (code 1) or an argparse error (code 2, stderr)
        detail = code if isinstance(code, str) else (err.getvalue().strip().splitlines() or [""])[-1]
        n = 1 if isinstance(code, str) else code
        raise CommandError(f"space exited {n}: {detail}" if detail else f"space exited {n}")


def split_steps(text):
    """Split a `do` line on `;` outside quotes ("…" and '…' are honoured)."""
    steps, buf, q = [], [], None
    for ch in text:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            buf.append(ch)
        elif ch == ";":
            steps.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    steps.append("".join(buf))
    return [s.strip() for s in steps if s.strip()]


GLOBAL_VALUES = ("--campaign", "--seed")
GLOBAL_FLAGS = ("--json",)


def split_globals(argv):
    """Pull `--campaign X`, `--seed N` and `--json` out of a command line wherever they
    stand (before `--`), so positional catch-alls never swallow them. Returns
    (rest, {dest: value})."""
    rest, found, i = [], {}, 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--":
            rest.extend(argv[i:])
            break
        if tok in GLOBAL_VALUES and i + 1 < len(argv):
            val = argv[i + 1]
            if tok == "--seed":
                try:
                    val = int(val)
                except ValueError:
                    raise CommandError(f"--seed wants a number, got {val!r}") from None
            found[tok[2:]] = val
            i += 2
            continue
        if tok in GLOBAL_FLAGS:
            found[tok[2:]] = True
        else:
            rest.append(tok)
        i += 1
    return rest, found


def clean_line(argv):
    """The command line as recorded in the journal and log lines: global flags
    (--campaign/--seed/--json) left out, also inside `do` steps."""
    rest, _ = split_globals(argv)
    if command_name(rest) == "do":
        i = rest.index("do")
        if i + 1 < len(rest):
            steps = []
            for step in split_steps(rest[i + 1]):
                try:
                    toks = split_args(step)
                except ValueError:
                    steps.append(step)
                    continue
                kept, found = split_globals(toks)
                steps.append(" ".join(shlex.quote(t) for t in kept) if found else step)
            rest = rest[:i + 1] + ["; ".join(steps)] + rest[i + 2:]
    return "gm.py " + " ".join(shlex.quote(a) for a in rest)


def split_args(step):
    """Tokenize one step like a shell, but with backslashes literal so Windows paths
    (`C:\\tmp\\poc`) survive."""
    lex = shlex.shlex(step, posix=True, punctuation_chars=False)
    lex.whitespace_split = True
    lex.escape = ""
    lex.escapedquotes = ""
    return list(lex)


def cmd_do(ctx):
    steps = split_steps(ctx.args.steps)
    if not steps:
        raise CommandError("do: no steps given")
    applied = []
    shared = dice.Roller(ctx.seed) if ctx.seed is not None else None
    if not any(_is_waive(step) for step in steps):
        wacky.consume()
    wacky._suppress = True
    try:
        _run_steps(ctx, steps, applied, shared)
    finally:
        wacky._suppress = False
    for line in applied:
        ctx.emit(line)


def _is_waive(step):
    try:
        toks, _ = split_globals(split_args(step))
    except (ValueError, CommandError):
        return False
    return [t.lower() for t in toks[:2]] == ["juice", "waive"]


def _run_steps(ctx, steps, applied, shared):
    for i, step in enumerate(steps, start=1):
        try:
            argv = split_args(step)
        except ValueError as e:
            raise CommandError(f"step {i} `{step}` failed: {e}") from None
        if argv and argv[0] == "do":
            raise CommandError(f"step {i} `{step}` failed: do cannot nest")
        try:
            sub = run(argv, batch=False, roller=shared)
        except CommandError as e:
            done = ", ".join(f"{n} `{s}`" for n, s in zip(range(1, i), steps)) or "(none)"
            raise CommandError(f"step {i} `{step}` failed: {e}\n[do] applied: {done}",
                               output=applied) from None
        applied.extend(sub.lines)
        ctx.result[f"step {i}"] = sub.result


# ---------- dispatch ----------

def run(argv, batch=True, roller=None):
    """Parse and run one command line (a list of tokens). Returns its Ctx; raises
    CommandError. With batch=True the command runs inside its own journal Batch;
    `roller` is the `do` batch's shared Roller (Ctx.roller)."""
    parser = build_parser()
    full = list(argv)
    argv, found = split_globals(argv)
    name = command_name(argv)
    if not name:
        raise CommandError(f"no command given\n{USAGE}")
    if name not in parser.commands:
        raise CommandError(f"unknown command {name!r}\n{USAGE}")
    try:
        args = parser.parse_args(argv)
    except CommandError as e:
        raise CommandError(f"{e}\n{USAGE}") from None
    for key, value in found.items():
        setattr(args, key, value)
    if hasattr(args, "campaign"):
        campaign.set_override(args.campaign)
    ctx = Ctx(args, roller)
    try:
        if batch:
            with journal.Batch(clean_line(full)):
                args.func(ctx)
        else:
            args.func(ctx)
    except CommandError:
        raise
    except (campaign.CampaignError, journal.JournalError, gametime.TimeError,
            ToolError, FileNotFoundError) as e:
        if os.environ.get("GM_DEBUG"):
            traceback.print_exc()
        raise CommandError(str(e)) from None
    return ctx


def command_name(argv):
    """The command token of a command line, skipping leading global options."""
    skip = False
    for tok in argv:
        if skip:
            skip = False
        elif tok in ("--campaign", "--seed"):
            skip = True
        elif not tok.startswith("-"):
            return tok
    return ""


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        build_parser().print_help()
        return 0
    try:
        ctx = run(argv)
    except CommandError as e:
        for line in e.output:
            print(line)
        print(f"[{command_name(argv) or 'gm.py'}] {e}")
        return 1
    if ctx.json:
        print(json.dumps(ctx.result, ensure_ascii=False))
    else:
        for line in ctx.lines:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
