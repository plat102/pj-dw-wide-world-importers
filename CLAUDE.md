@AGENTS.md

## Claude Code

- `.claude/settings.json` pre-approves the read-only and no-stack commands above, always asks before `make extract`, `make maintain`, `make clean_storage`, `docker compose down` and `git push`, and denies reading `.env`. Personal overrides go in `.claude/settings.local.json`, which is git-ignored.
- Hooks: an edit to `.env` or a generated file is refused with the command that writes it — run that command, do not work around the hook. After every edit, a `.py` file gets `ruff check` and a `.md` file is checked for hard-wrapped prose; fix what they report before moving on.
- Skills: `add-source-table` (a new table from the source, end to end) and `add-dbt-model` (a model in any layer, with its tests).
- Before reporting a non-trivial change done, run the `repo-reviewer` subagent on the diff; it checks the invariants in AGENTS.md and does not edit.
