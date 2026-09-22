"""SHA256 over a file, in one place: the manifest is only worth what its checksums are worth."""

from __future__ import annotations

import hashlib
from typing import BinaryIO

# One MiB. Large enough that the loop is not the cost, small enough not to hold a snapshot in RAM.
CHUNK_BYTES = 1024 * 1024


def sha256_stream(handle: BinaryIO) -> str:
    """Digest an already-open binary stream, as the verifier reads objects off the store."""
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(CHUNK_BYTES), b""):
        digest.update(block)
    return digest.hexdigest()
