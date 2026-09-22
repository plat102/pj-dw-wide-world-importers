"""One exception type for every predictable failure: library code raises, `cli/` catches once."""

from __future__ import annotations


class ToolingError(Exception):
    """A failure the operator can act on: a missing file, an unset variable, a row count that moved.

    Not for bugs. An IndexError or a TypeError should keep its traceback.
    """
