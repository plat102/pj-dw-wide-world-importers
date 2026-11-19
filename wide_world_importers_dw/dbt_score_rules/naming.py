"""A column whose name asserts a type carries that type.

docs/naming_convention.md, "Columns", has the rule.
"""

# No `from __future__ import annotations`: dbt-score reads each rule's argument annotation at
# import time to tell a model rule from a source rule, and a string annotation defeats that.
import re

from dbt_score import Model, RuleViolation, rule

# `is_on_credit_hold`, `day_is_weekday`, `has_returns`, `discontinued_flag`: each promises a
# boolean.
BOOLEAN_NAME = re.compile(r"(^|_)(is|has)_|_flag$")


@rule
def boolean_names_are_boolean(model: Model) -> RuleViolation | None:
    """A column named as a boolean (is_, has_, _flag) that declares a data_type declares boolean.

    Only a declared type can be read from the manifest, so this guards contracted models, where the
    declared type is the one the build enforces.
    """
    wrong = [
        f"{column.name} ({column.data_type})"
        for column in model.columns
        if BOOLEAN_NAME.search(column.name)
        and column.data_type
        and column.data_type.strip().lower() not in {"boolean", "bool"}
    ]
    if wrong:
        return RuleViolation("named as a boolean but typed otherwise: " + ", ".join(sorted(wrong)))
    return None
