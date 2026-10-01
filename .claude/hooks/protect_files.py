"""PreToolUse hook: refuse an Edit or Write on a file that is generated, or that holds credentials.

Claude Code hands the tool call over stdin as JSON. Exit 2 blocks the call and shows stderr to the
agent, which is told the command that writes the file instead. A generated file still changes
through `make`, which runs under Bash and never passes through here.

Standard library only: this runs under whatever `python3` is on PATH, outside the project's venv.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Repository-relative path -> what to do instead. tests/unit/test_agent_setup.py checks that each
# of these paths exists, so a rename cannot leave the guard pointing at nothing.
GENERATED = {
    "docs/data_warehouse_catalog.md": "regenerate it with `make catalog`; schema.yml is the source",
    "src/ingestion/raw_schema.sql": "regenerate it with `make raw_schema` after `make extract`",
    "uv.lock": "change pyproject.toml and run `uv lock`",
}
CREDENTIALS = "holds real credentials and is the user's to edit; change .env.example instead"


def _is_credentials(name: str) -> bool:
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def reason(path: Path, root: Path) -> str | None:
    """Why `path` must not be edited by hand, or None when it may be."""
    # The path as written and the file it resolves to are both checked: a `.env` that is a
    # symlink to a file elsewhere is still the credentials file.
    written = Path(os.path.abspath(root / path))
    for candidate in (written, written.resolve()):
        if _is_credentials(candidate.name):
            return CREDENTIALS
        try:
            relative = candidate.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if relative in GENERATED:
            return GENERATED[relative]
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Fail closed: a guard that cannot read the call must not wave it through.
        print("protect_files.py could not parse the tool call; refusing the edit.", file=sys.stderr)
        return 2
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or Path.cwd())
    why = reason(Path(file_path), root)
    if why is None:
        return 0
    print(f"{file_path} is not edited by hand: {why}.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
