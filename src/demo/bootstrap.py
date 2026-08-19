#!/usr/bin/env python
"""Give a fresh clone a working `.env`, so the demo is one command and not also a form.

Fills only the credentials that guard containers this repository starts and throws away. The source
connection string is left empty on purpose: the transform half must never reach the source, and a
demo that quietly acquired the means to would be the wrong thing to make convenient.

    wwi bootstrap
"""

from __future__ import annotations

import secrets

from config import settings
from utils.exceptions import ToolingError

ENV = settings.REPO_ROOT / ".env"
EXAMPLE = settings.REPO_ROOT / ".env.example"

# Values generated here; everything else in .env.example already carries a usable default.
GENERATED = ("S3_ACCESS_KEY", "S3_SECRET_KEY", "CATALOG_PASSWORD")
# A login name, not a secret. Fixed so the value in .env matches what the docs and the profile show.
FIXED = {"CATALOG_USER": "ducklake"}


def write_env() -> str:
    if ENV.exists():
        return f"{ENV.name} already exists -- leaving it alone"
    if not EXAMPLE.exists():
        raise ToolingError(f"{EXAMPLE.name} is missing -- cannot derive a {ENV.name} from it")

    filled = 0
    lines = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines(keepends=True):
        key = line.split("=", 1)[0] if "=" in line and not line.startswith("#") else None
        if key in FIXED:
            lines.append(f"{key}={FIXED[key]}\n")
            filled += 1
        elif key in GENERATED:
            # 24 bytes of urlsafe randomness. Local-only, but generated rather than defaulted: the
            # code must not be able to tell this store from a real bucket, and a value committed
            # anywhere is a value someone can read.
            lines.append(f"{key}={secrets.token_urlsafe(24)}\n")
            filled += 1
        else:
            lines.append(line)

    ENV.write_text("".join(lines), encoding="utf-8")
    ENV.chmod(0o600)
    return (
        f"wrote {ENV.name} from {EXAMPLE.name}: {filled} credentials generated, source left unset\n"
        "  docker-compose.yml still has no defaults -- an unset credential stops the stack."
    )
