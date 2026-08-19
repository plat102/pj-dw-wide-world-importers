"""SHA256 over a file, in one place.

Four copies of these eight lines existed -- in the manifest generator, the fixture cutter, the
uploader and the verifier -- with three different local naming styles and two spellings of the
chunk size. The manifest is only worth what its checksums are worth, so they agree here or nowhere.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

# One MiB. Large enough that the loop is not the cost, small enough not to hold a snapshot in RAM.
CHUNK_BYTES = 1024 * 1024


def sha256_stream(handle: BinaryIO) -> str:
    """Digest an already-open binary stream. The verifier reads objects off the store this way."""
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(CHUNK_BYTES), b""):
        digest.update(block)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return sha256_stream(handle)
