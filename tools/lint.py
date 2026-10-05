"""`gm.py lint [--fix-safe] [--files a.md b.md …]` — the consistency sweep (planning/06 →
`gm.py lint`; lib/lint.py holds the checks). Prints `[LINT] N errors · M warnings` and
one line per finding; exits 1 when there are errors. `--fix-safe` only adds a missing
sub-area to a site's `## Areas` (marked `<!-- added by lint, check me -->`).
"""
from lib import lint as checks
from lib.errors import ToolError


class LintFailed(ToolError):
    def __init__(self, message, output):
        super().__init__(message)
        self.output = output


def cmd_lint(ctx):
    a = ctx.args
    found = checks.run(files=a.files or None, fix_safe=a.fix_safe)
    errs = [f for f in found if f.level == "error"]
    lines = [f"[LINT] {len(errs)} error{'s' if len(errs) != 1 else ''} · "
             f"{len(found) - len(errs)} warning{'s' if len(found) - len(errs) != 1 else ''}"]
    lines += ["  " + f.line() for f in sorted(found, key=lambda f: (f.level != "error", f.path))]
    ctx.result = {"errors": [f.line() for f in errs], "warnings": [f.line() for f in found if f.level != "error"]}
    if errs:
        raise LintFailed(f"{len(errs)} error(s)", lines)
    for line in lines:
        ctx.emit(line)


def register(sub, g):
    p = sub.add_parser("lint", parents=[g], help="consistency sweep (exit 1 on errors)")
    p.add_argument("--fix-safe", action="store_true")
    p.add_argument("--files", nargs="+")
    p.set_defaults(func=cmd_lint)
