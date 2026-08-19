"""The extraction contract: which tables and columns the snapshot is required to carry.

`tables.yml` names columns explicitly rather than `*`, so the schema is deliberate and computed
columns survive. Editing that file changes the contract, which is what `schema_version` is for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config import settings


def load(path: Path = settings.TABLES_CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def schema_version(path: Path = settings.TABLES_CONFIG) -> int:
    """The schema this checkout expects. Read here so there is one copy of the answer."""
    return int(load(path)["schema_version"])


def specs(path: Path = settings.TABLES_CONFIG) -> list[dict[str, Any]]:
    return list(load(path)["tables"])
