"""Shared error base for command modules (plan.md Phase 2). gm.py turns a ToolError
into the one-line `[command] message` failure (docs/design/06 L30-32, L37-43)."""


class ToolError(Exception):
    """A command could not do what was asked; the message is shown to the GM."""
