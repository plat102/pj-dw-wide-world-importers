"""Every report page has a dbt exposure, every exposure a page, and each names what its page reads.

A hand-kept list of consumers is what drifts first: a page added without an exposure drops out of
`dbt ls --select +exposure:...`, and an exposure left behind by a deleted page claims a reader that
is gone. So the pairing is checked both ways, and depends_on is derived from the page itself: the
Cube views it queries, the cubes each view joins, and the core model each cube reads. No stack.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from config import settings

PAGES = settings.REPO_ROOT / "reports" / "pages"
SEMANTIC = settings.REPO_ROOT / "semantic" / "model"
MODELS = settings.DBT_DIR / "models"
STAR = "lake.core."
# The `data` attribute of a Markdoc tag names what the component queries: a Cube view.
DATA = re.compile(r'\bdata\s*=\s*"(\w+)"')
REF = re.compile(r"""^ref\(\s*['"](\w+)['"]\s*\)$""")


def _route(page: Path) -> str:
    parts = page.relative_to(PAGES).with_suffix("").parts
    return "/" + "/".join(parts[:-1] if parts[-1] == "index" else parts)


def _exposure_name(page: Path) -> str:
    return "__".join(page.relative_to(PAGES).with_suffix("").parts) + "_page"


def _load(directory: Path, key: str) -> list[dict[str, Any]]:
    return [
        item
        for path in sorted(directory.rglob("*.yml"))
        for item in (yaml.safe_load(path.read_text()) or {}).get(key) or []
    ]


def _models_behind(data: str) -> set[str]:
    """The core models a query of `data` reads: every cube on every join path of the view."""
    cubes = {cube["name"]: cube for cube in _load(SEMANTIC, "cubes")}
    views = {view["name"]: view for view in _load(SEMANTIC, "views")}
    if data in views:
        names = {name for entry in views[data]["cubes"] for name in entry["join_path"].split(".")}
    elif data in cubes:
        names = {data}
    else:
        raise AssertionError(f"data={data!r} is neither a view nor a cube of semantic/model/")
    tables = {cubes[name]["sql_table"] for name in names}
    outside = sorted(table for table in tables if not table.startswith(STAR))
    assert not outside, f"a cube reads outside the star: {outside}"
    return {table.removeprefix(STAR) for table in tables}


def _pages() -> dict[str, tuple[str, set[str]]]:
    """Expected exposure name -> (route, core models the page reads)."""
    return {
        _exposure_name(page): (
            _route(page),
            {model for data in DATA.findall(page.read_text()) for model in _models_behind(data)},
        )
        for page in sorted(PAGES.rglob("*.md"))
    }


def _exposures() -> dict[str, tuple[str, set[str]]]:
    """Declared exposure name -> (route of its url, models in depends_on)."""
    found: dict[str, tuple[str, set[str]]] = {}
    for exposure in _load(MODELS, "exposures"):
        refs = [REF.match(item.strip()) for item in exposure.get("depends_on") or []]
        assert all(refs), f"{exposure['name']}: depends_on holds something other than ref('...')"
        found[exposure["name"]] = (
            urlparse(exposure.get("url", "")).path or "/",
            {match.group(1) for match in refs if match},
        )
    return found


def _mismatches(
    pages: dict[str, tuple[str, set[str]]], exposures: dict[str, tuple[str, set[str]]]
) -> list[str]:
    found = [f"page without exposure: {name}" for name in sorted(pages.keys() - exposures)]
    found += [f"exposure without page: {name}" for name in sorted(exposures.keys() - pages)]
    for name in sorted(pages.keys() & exposures.keys()):
        (route, reads), (url, declared) = pages[name], exposures[name]
        if url != route:
            found.append(f"{name}: url path {url!r}, the page is served at {route!r}")
        if missing := sorted(reads - declared):
            found.append(f"{name}: depends_on lacks {missing}")
        if extra := sorted(declared - reads):
            found.append(f"{name}: depends_on names {extra}, which the page does not read")
    return found


def test_the_derivation_finds_what_a_page_reads() -> None:
    """Guards the check below: with no model derived anywhere, it would compare empty sets."""
    assert any(reads for _, reads in _pages().values())


def test_every_page_and_every_exposure_match() -> None:
    mismatches = _mismatches(_pages(), _exposures())
    assert not mismatches, (
        "keep wide_world_importers_dw/models/_reports__exposures.yml in step with reports/pages/: "
        f"{mismatches}"
    )


def test_the_comparison_catches_drift_both_ways() -> None:
    pages = {"index_page": ("/", set()), "sales_page": ("/sales", {"dim_date", "fct_x"})}
    exposures = {
        "index_page": ("/", set()),
        "sales_page": ("/orders", {"fct_x", "dim_customer"}),
        "gone_page": ("/gone", set()),
    }
    assert _mismatches(pages, exposures) == [
        "exposure without page: gone_page",
        "sales_page: url path '/orders', the page is served at '/sales'",
        "sales_page: depends_on lacks ['dim_date']",
        "sales_page: depends_on names ['dim_customer'], which the page does not read",
    ]
    assert _mismatches({**pages, "new_page": ("/new", set())}, pages) == [
        "page without exposure: new_page"
    ]


def test_pages_map_to_routes_and_exposure_names() -> None:
    assert _route(PAGES / "index.md") == "/"
    assert _route(PAGES / "sales.md") == "/sales"
    assert _route(PAGES / "sales" / "index.md") == "/sales"
    assert _exposure_name(PAGES / "sales" / "by_brand.md") == "sales__by_brand_page"
