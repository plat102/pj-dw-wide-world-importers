"""The dbt-score gate in `make check` must have rules in it.

dbt-score loads rules from the modules of a namespace package and scores a project with no rules
10 out of 10. A rule moved into the package's `__init__.py`, or a namespace renamed in
pyproject.toml, would turn `make score` into a check of nothing that still passes.
"""

from __future__ import annotations

import subprocess

from config import settings

EXPECTED = {
    "wide_world_importers_dw.dbt_score_rules.pii.sensitive_columns_are_classified",
    "wide_world_importers_dw.dbt_score_rules.pii.models_with_personal_data_say_so",
}


def test_the_governance_rules_are_loaded() -> None:
    listed = subprocess.run(
        ["dbt-score", "list", "--format", "markdown"],
        cwd=settings.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    missing = sorted(name for name in EXPECTED if name not in listed)
    assert not missing, f"dbt-score does not load: {missing}"
