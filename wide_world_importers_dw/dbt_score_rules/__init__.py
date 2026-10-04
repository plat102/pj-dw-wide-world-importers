"""Governance rules, run by dbt-score on the manifest in `make check` (`make score`).

Personal data is classified where it is published -- core and marts, the schemas a BI tool reads --
so that the semantic layer, a catalog page or a masking step can find it by metadata rather than by
someone remembering which columns hold it. docs/naming_convention.md, "Personal data", has the rule
and why a customer's phone number is `none` while a contact's is `person`.

dbt-score loads the rules from the modules of this package, never from this file: a rule defined
here would not run, and the score would stay at 10 with nothing checked.
"""
