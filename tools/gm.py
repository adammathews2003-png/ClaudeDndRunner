"""Entry point for the GM tools: `python tools/gm.py <command> …` (planning/06 →
Design principles L25-49, Code layout L60-81; plan.md Phase 1 item 5).

Global options (`--campaign DIR`, `--seed N`, `--json`) are accepted before the
command or after it, so a `do` step can carry its own. Subcommands come from the
command modules that exist beside this file (each exposes `register(sub, globals)`);
`space` forwards to space.py; `do "<cmd>; <cmd>"` runs the steps left to right inside
one undo batch and stops at the first failure, listing what already applied; `log
"<summary>"` closes the open turn block (06 L156-168). Nothing else lives here.
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

from lib import campaign, gametime, journal  # noqa: E402

USAGE_LINE = "gm.py [--campaign DIR] [--seed N] [--json] <command> [args…]"
USAGE = "usage: " + USAGE_LINE
COMMAND_MODULES = ("scene", "combat", "clock", "travel", "rest", "lint", "session",
                   "srd", "pc", "world", "mutations", "roll", "rules")


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

    def __init__(self, args):
        self.args = args
        self.seed = getattr(args, "seed", None)
        self.json = bool(getattr(args, "json", False))
        self.lines = []
        self.result = {}

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
    for i, step in enumerate(steps, start=1):
        try:
            argv = split_args(step)
        except ValueError as e:
            raise CommandError(f"step {i} `{step}` failed: {e}") from None
        if argv and argv[0] == "do":
            raise CommandError(f"step {i} `{step}` failed: do cannot nest")
        try:
            sub = run(argv, batch=False)
        except CommandError as e:
            done = ", ".join(f"{n} `{s}`" for n, s in zip(range(1, i), steps)) or "(none)"
            raise CommandError(f"step {i} `{step}` failed: {e}\n[do] applied: {done}",
                               output=applied) from None
        applied.extend(sub.lines)
        ctx.result[f"step {i}"] = sub.result
    for line in applied:
        ctx.emit(line)


# ---------- dispatch ----------

def run(argv, batch=True):
    """Parse and run one command line (a list of tokens). Returns its Ctx; raises
    CommandError. With batch=True the command runs inside its own journal Batch."""
    parser = build_parser()
    name = command_name(argv)
    if not name:
        raise CommandError(f"no command given\n{USAGE}")
    if name not in parser.commands:
        raise CommandError(f"unknown command {name!r}\n{USAGE}")
    try:
        args = parser.parse_args(argv)
    except CommandError as e:
        raise CommandError(f"{e}\n{USAGE}") from None
    if hasattr(args, "campaign"):
        campaign.set_override(args.campaign)
    ctx = Ctx(args)
    try:
        if batch:
            with journal.Batch("gm.py " + " ".join(shlex.quote(a) for a in argv)):
                args.func(ctx)
        else:
            args.func(ctx)
    except CommandError:
        raise
    except (campaign.CampaignError, journal.JournalError, gametime.TimeError,
            FileNotFoundError) as e:
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
