"""One module per external system, each named after what it actually speaks.

`mssql` is the only module in this project permitted to reach the source database. The rule is
enforced rather than described -- see the import-linter contracts in pyproject.toml.
"""
