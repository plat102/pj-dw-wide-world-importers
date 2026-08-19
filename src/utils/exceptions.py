"""One exception type for every predictable failure in this project.

Library code raises; `cli/` catches once, prints, and returns a non-zero exit code. Before this
there were four conventions -- `sys.exit` from inside a library, two different accumulate-and-return
shapes, and a bare RuntimeError -- and the `sys.exit` one made every module untestable without a
subprocess, because importing it could kill the interpreter.
"""

from __future__ import annotations


class ToolingError(Exception):
    """A failure the operator can act on: a missing file, an unset variable, a drifted checksum.

    Not for bugs. An IndexError or a TypeError should keep its traceback.
    """
