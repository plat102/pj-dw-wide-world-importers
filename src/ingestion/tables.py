"""The extraction contract: which tables and columns the lake's bronze schema must carry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config import settings


def load(path: Path = settings.TABLES_CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
