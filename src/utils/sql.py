"""Quoting for values that end up inside DuckDB SQL text."""

from __future__ import annotations


def literal(value: str) -> str:
    """A SQL string literal, with any single quote doubled.

    Unescaped, a `'` in a secret ends the literal early: the statement fails to parse, and the
    parser error prints the statement -- secret included.
    """
    return "'" + value.replace("'", "''") + "'"
