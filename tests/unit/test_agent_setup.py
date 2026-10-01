"""What the agent instructions claim must hold in the code they describe.

AGENTS.md is loaded into every agent's context and acted on without a second look, so a command
or path in it that has stopped existing is worse than none. The hooks under .claude/hooks are
checked the same way: a guard pointing at a renamed file passes everything.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from config import settings

ROOT = settings.REPO_ROOT
HOOKS = ROOT / ".claude" / "hooks"
INSTRUCTIONS = [
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    *sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")),
    *sorted((ROOT / ".claude" / "agents").glob("*.md")),
]
# A hook exits 2 to block the tool call and hand its stderr to the agent.
BLOCKED = 2
# `make check`, `make up extract build`: every word after `make` up to the closing backtick.
MAKE_INLINE = re.compile(r"`make ([a-z_ ]+?)(?: [A-Z_]+=\S*)?`")
# A command line in a fenced block: `make check   # comment`.
MAKE_LINE = re.compile(r"^\s*make ([a-z_ ]+)", flags=re.MULTILINE)
# Named in the instructions but personal or git-ignored, so absent from a fresh clone.
OPTIONAL = {".claude/settings.local.json", ".env"}
# A backticked repository path: a directory, a file with one of these extensions, or `path:line`.
REPO_PATH = re.compile(
    r"`((?:[\w.-]+/)+[\w.-]*|[\w./-]*[\w-]\.(?:md|py|sql|toml|yml|yaml|json|lock|example)"
    r"|[\w./-]+:\d+)`"
)
MARKDOWN_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
# Every `path:line` the always-loaded files point at, with text that line must still hold. A
# line number that drifts onto a comment would otherwise still pass a length check.
LINE_REFERENCES = {
    "Makefile:6": "-include .env",
    "Makefile:11": "LAKE_ENV :=",
    "Makefile:16": "unexport MSSQL_CONNECTION_STRING",
    "Makefile:78": "build:",
    "Makefile:84": "extract: export MSSQL_CONNECTION_STRING",
    "wide_world_importers_dw/tests/assert_dim_date_calendar.sql:33": "ref('dim_date').render()",
    "wide_world_importers_dw/models/marts/sales/_sales__models.yml:13": "contract:",
}
ALWAYS_LOADED = (ROOT / "AGENTS.md", ROOT / "CLAUDE.md")


def _hook(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_targets() -> set[str]:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    return set(re.findall(r"^([a-z_]+):", text, flags=re.MULTILINE))


def test_every_make_target_the_instructions_name_exists() -> None:
    targets = _make_targets()
    named = {
        (path.relative_to(ROOT).as_posix(), word)
        for path in INSTRUCTIONS
        for pattern in (MAKE_INLINE, MAKE_LINE)
        for call in pattern.findall(path.read_text(encoding="utf-8"))
        for word in call.split()
    }
    assert ("AGENTS.md", "check") in named, "the patterns no longer find `make check` in AGENTS.md"
    missing = sorted(f"{path}: make {word}" for path, word in named if word not in targets)
    assert not missing, f"targets the Makefile does not define: {missing}"


def _tracked_names() -> set[str]:
    """Basenames of the files in the repository, for a bare `tables.yml` that names one by name."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return {Path(name).name for name in listed}


def _references(path: Path) -> list[str]:
    return REPO_PATH.findall(path.read_text(encoding="utf-8"))


def test_every_path_the_always_loaded_files_name_exists() -> None:
    """Backticked paths resolve from the root; Markdown links from the file that holds them."""
    broken = []
    tracked = _tracked_names() if shutil.which("git") else None
    for path in ALWAYS_LOADED:
        text = path.read_text(encoding="utf-8")
        for reference in _references(path):
            name = reference.partition(":")[0]
            if name in OPTIONAL or (ROOT / name).exists():
                continue
            # A bare file name is shorthand for a file elsewhere in the tree; it must still exist.
            if "/" not in name and (tracked is None or name in tracked):
                continue
            broken.append(f"{path.name}: `{reference}` does not exist")
        for link in MARKDOWN_LINK.findall(text):
            if "://" not in link and not (path.parent / link).exists():
                broken.append(f"{path.name}: link {link} does not resolve")
    assert _references(ROOT / "AGENTS.md"), "REPO_PATH no longer matches anything in AGENTS.md"
    assert not broken, broken


def test_every_line_reference_still_points_at_its_line() -> None:
    found = {
        reference
        for path in ALWAYS_LOADED
        for reference in _references(path)
        if re.search(r":\d+$", reference)
    }
    assert found == set(LINE_REFERENCES), (
        "add new `path:line` references to LINE_REFERENCES and drop stale ones: "
        f"unlisted {sorted(found - set(LINE_REFERENCES))}, "
        f"gone {sorted(set(LINE_REFERENCES) - found)}"
    )
    drifted = []
    for reference, expected in LINE_REFERENCES.items():
        name, _, line = reference.rpartition(":")
        lines = (ROOT / name).read_text(encoding="utf-8").splitlines()
        if int(line) > len(lines) or expected not in lines[int(line) - 1]:
            drifted.append(f"{reference} no longer holds {expected!r}")
    assert not drifted, drifted


def test_every_file_the_edit_guard_protects_exists() -> None:
    missing = [name for name in _hook("protect_files").GENERATED if not (ROOT / name).is_file()]
    assert not missing, f"protect_files.py guards files that are gone: {missing}"


def _guard(path: Path) -> int:
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    return subprocess.run(
        [sys.executable, str(HOOKS / "protect_files.py")],
        input=payload,
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(ROOT)},
        check=False,
    ).returncode


@pytest.mark.parametrize(
    "relative",
    ["src/ingestion/raw_schema.sql", "docs/data_warehouse_catalog.md", "uv.lock", ".env"],
)
def test_the_edit_guard_blocks_generated_files_and_credentials(relative: str) -> None:
    assert _guard(ROOT / relative) == BLOCKED


@pytest.mark.parametrize("relative", ["src/ingestion/tables.yml", ".env.example", "AGENTS.md"])
def test_the_edit_guard_lets_source_files_through(relative: str) -> None:
    assert _guard(ROOT / relative) == 0


def test_the_wrap_check_tells_a_wrapped_paragraph_from_structure() -> None:
    wrapped_lines = _hook("post_edit_check").wrapped_lines
    assert wrapped_lines("# Title\n\nOne sentence\ncarried on.\n") == [4]
    structure = "---\nname: x\ndescription: y\n---\n\nOne line.\n\n- a\n- b\n\n| a |\n| b |\n"
    assert wrapped_lines(structure + "```\ncode\nmore\n```\n") == []


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git to list tracked files")
def test_no_tracked_markdown_is_hard_wrapped() -> None:
    """docs/naming_convention.md: one paragraph is one line. The edit hook checks the same."""
    wrapped_lines = _hook("post_edit_check").wrapped_lines
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    # A generated page is fixed in its generator and conforms from the next regeneration.
    generated = set(_hook("protect_files").GENERATED)
    offenders = {
        name: found
        for name in listed
        if name not in generated
        and (ROOT / name).is_file()
        and (found := wrapped_lines((ROOT / name).read_text(encoding="utf-8")))
    }
    assert not offenders, f"hard-wrapped prose (file: lines): {offenders}"
