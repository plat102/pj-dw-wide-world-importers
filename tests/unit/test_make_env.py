"""What each make recipe hands its process: the lake's variables everywhere, the source credential
only to `extract`.

The real Makefile runs in a temporary directory with a fake `.env`, and a stand-in `uv` on PATH
writes out the environment it was given. So this checks the recipes as make runs them, not a
reading of the Makefile.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from config import settings

SOURCE = "MSSQL_CONNECTION_STRING"
SENTINEL = "mssql+pymssql://sentinel:sentinel@nowhere:1433/"

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="needs GNU make")


def _names_the_code_reads() -> set[str]:
    """Every variable wwi reads through settings, and every one the dbt profile reads."""
    python = re.compile(r"""\b(?:require|optional|flag)\(\s*["']([A-Z][A-Z0-9_]*)["']""")
    names = {
        name
        for path in (settings.REPO_ROOT / "src").rglob("*.py")
        for name in python.findall(path.read_text())
    }
    profile = (settings.REPO_ROOT / "profiles.yml").read_text()
    names |= set(re.findall(r"""env_var\(\s*'([A-Z][A-Z0-9_]*)'""", profile))
    # Read by the source connector alone, and only through `extract`: covered separately below.
    names.discard(SOURCE)
    return names


def _recipe_env(tmp_path: Path, target: str, dotenv: dict[str, str], shell: dict[str, str]) -> str:
    """The environment `uv` saw, for every call the recipe made."""
    shutil.copy(settings.REPO_ROOT / "Makefile", tmp_path / "Makefile")
    (tmp_path / "docs").mkdir()  # where `make catalog` writes its page
    (tmp_path / ".env").write_text("".join(f"{k}={v}\n" for k, v in dotenv.items()))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    dump = tmp_path / "env.txt"
    fake_uv = bin_dir / "uv"
    fake_uv.write_text('#!/bin/sh\nenv >> "$ENV_DUMP"\n')
    fake_uv.chmod(0o755)

    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "ENV_DUMP": str(dump), **shell}
    subprocess.run(["make", "-s", target], cwd=tmp_path, env=env, check=True, capture_output=True)
    return dump.read_text()


def test_the_code_reads_something() -> None:
    """Guards the scan below: a regex that matches nothing would pass every check vacuously."""
    assert {"S3_ACCESS_KEY", "CATALOG_USER"} <= _names_the_code_reads()


@pytest.mark.parametrize("target", ["build", "compare", "shape", "extract"])
def test_every_variable_the_code_reads_reaches_the_recipe(tmp_path: Path, target: str) -> None:
    """A name missing from LAKE_ENV would reach no recipe, and wwi would fall back to a default."""
    names = _names_the_code_reads()
    seen = _recipe_env(tmp_path, target, {name: f"v-{name}" for name in names}, {})
    missing = sorted(name for name in names if f"{name}=v-{name}\n" not in seen)
    assert not missing, f"not exported by the Makefile's LAKE_ENV: {', '.join(missing)}"


@pytest.mark.parametrize("target", ["build", "compare", "shape", "catalog", "maintain"])
@pytest.mark.parametrize("origin", ["dotenv", "shell"])
def test_the_source_credential_stays_out_of_the_other_recipes(
    tmp_path: Path, target: str, origin: str
) -> None:
    dotenv, shell = ({SOURCE: SENTINEL}, {}) if origin == "dotenv" else ({}, {SOURCE: SENTINEL})
    seen = _recipe_env(tmp_path, target, dotenv, shell)
    assert seen, f"the fake uv was never called by `make {target}`"
    assert f"{SOURCE}=" not in seen


@pytest.mark.parametrize("origin", ["dotenv", "shell"])
def test_extract_gets_the_source_credential(tmp_path: Path, origin: str) -> None:
    dotenv, shell = ({SOURCE: SENTINEL}, {}) if origin == "dotenv" else ({}, {SOURCE: SENTINEL})
    assert f"{SOURCE}={SENTINEL}\n" in _recipe_env(tmp_path, "extract", dotenv, shell)


def test_an_unset_optional_variable_is_not_exported_empty(tmp_path: Path) -> None:
    """Exported empty, `optional("S3_ENDPOINT", default)` would return "" instead of the default."""
    seen = _recipe_env(tmp_path, "build", {"S3_ACCESS_KEY": "k"}, {})
    assert "S3_ENDPOINT=" not in seen
    assert "S3_ACCESS_KEY=k\n" in seen
