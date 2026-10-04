"""Personal data is classified where it is published. See the package docstring."""


# No `from __future__ import annotations`: dbt-score reads each rule's argument annotation at
# import time to tell a model rule from a source rule, and a string annotation defeats that.
import re
from typing import Any

from dbt_score import Model, RuleViolation, rule
from dbt_score.models import Column

PUBLISHED = {"core", "marts"}
CLASSES = {"person", "none"}
# Names that hold identity or contact details often enough that each must be decided, not missed.
SENSITIVE_NAME = re.compile(
    r"full_name|preferred_name|email|phone|fax|address|postal_code|website|logon|password|photo"
)


def _meta(item: Model | Column) -> dict[str, Any]:
    # dbt 1.10+ moved meta under config; read both so either spelling counts.
    return {**item.meta, **item.config.get("meta", {})}


@rule
def sensitive_columns_are_classified(model: Model) -> RuleViolation | None:
    """A published column whose name suggests identity or contact data declares meta.pii."""
    if model.config.get("schema") not in PUBLISHED:
        return None
    unclassified = [
        column.name
        for column in model.columns
        if SENSITIVE_NAME.search(column.name) and _meta(column).get("pii") not in CLASSES
    ]
    invalid = [
        column.name
        for column in model.columns
        if "pii" in _meta(column) and _meta(column)["pii"] not in CLASSES
    ]
    if unclassified or invalid:
        return RuleViolation(
            "set meta.pii to person or none on: " + ", ".join(sorted(set(unclassified + invalid)))
        )
    return None


@rule
def models_with_personal_data_say_so(model: Model) -> RuleViolation | None:
    """A model carries meta.contains_pii: true exactly when one of its columns is pii: person."""
    personal = any(_meta(column).get("pii") == "person" for column in model.columns)
    declared = _meta(model).get("contains_pii") is True
    if personal and not declared:
        return RuleViolation("a column is pii: person, so set meta.contains_pii: true on the model")
    if declared and not personal:
        return RuleViolation("meta.contains_pii is true, but no column is pii: person")
    return None
