"""The semantic layer stays on the star dbt builds, and its view is the only way in.

Cube resolves a column only when a query reaches it, so a column renamed in dbt would surface as a
broken chart. These read the model files and dbt's schema YAML instead, with no stack.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from config import settings

CUBES = settings.REPO_ROOT / "semantic" / "model" / "cubes"
CORE_MODELS = settings.DBT_DIR / "models" / "marts" / "core"
# The star, not the flat mart: a dimension the mart does not carry -- brand -- must stay reachable.
STAR = "lake.core."
# `{CUBE}.column` names a column of the cube's own table; `{other}.column` one of a joined cube's.
COLUMN = re.compile(r"\{(\w+)\}\.(\w+)")


def _cubes() -> dict[str, dict[str, Any]]:
    found = [
        cube
        for path in sorted(CUBES.glob("*.yml"))
        for cube in yaml.safe_load(path.read_text())["cubes"]
    ]
    return {cube["name"]: cube for cube in found}


def _core_columns() -> dict[str, set[str]]:
    return {
        model["name"]: {column["name"] for column in model.get("columns", [])}
        for path in CORE_MODELS.glob("*.yml")
        for model in (yaml.safe_load(path.read_text()) or {}).get("models", [])
    }


def test_every_column_a_cube_names_is_a_column_of_the_star() -> None:
    cubes, core = _cubes(), _core_columns()
    checked, wrong = 0, []
    for cube in cubes.values():
        texts = [
            m.get("sql", "") for kind in ("dimensions", "measures") for m in cube.get(kind, [])
        ]
        texts += [join["sql"] for join in cube.get("joins", [])]
        for owner, column in (ref for text in texts for ref in COLUMN.findall(text)):
            target = cube if owner == "CUBE" else cubes.get(owner)
            if target is None:
                wrong.append(f"{cube['name']}: {{{owner}}} is not a cube")
                continue
            table = target["sql_table"]
            checked += 1
            if not table.startswith(STAR) or column not in core.get(
                table.removeprefix(STAR), set()
            ):
                wrong.append(f"{cube['name']}: {table}.{column}")
    assert checked, "COLUMN matched nothing; the check would pass vacuously"
    assert not wrong, f"not a column of a core model: {wrong}"


def test_only_the_view_is_public() -> None:
    """Cubes are public by default; a public one is a second way in, around the view."""
    public = [name for name, cube in _cubes().items() if cube.get("public") is not False]
    assert not public, f"set `public: false` on {public}"
