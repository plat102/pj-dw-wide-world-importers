"""One module per external system, each named after what it speaks.

`mssql` is the only module permitted to reach the source database -- enforced by the import-linter
contracts in pyproject.toml.
"""
