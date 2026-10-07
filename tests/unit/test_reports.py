"""What the reports may contain, checked on the files: every formula stays in the semantic layer.

Cube rewrites `sum`/`avg` of a ratio measure into the ratio, but it accepts an `avg` over a subquery
of a measure, and `MEASURE(a) / MEASURE(b)` -- new formulas outside the layer. So a page holds no
SQL, and a component names a column or `MEASURE(x)`, nothing that computes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from config import settings

REPORTS = settings.REPO_ROOT / "reports"
# A Markdoc tag, its attributes possibly spread over several lines.
TAG = re.compile(r"\{%\s*(\w+)(.*?)/?%\}", flags=re.DOTALL)
ATTRIBUTE = re.compile(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\[[^\]]*\]|\{[^}]*\}|[^\s%/]+)')
QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')
# Attributes holding a column. `value` does only on a table's column tags; an option's is a literal.
COLUMN_KEYS = {"x", "y", "y2", "series", "size", "value_column", "label_column"}
COLUMN_TAGS = {"measure", "dimension"}
# A column, a template variable, or a measure -- possibly picked by a template variable.
NAMES = re.compile(r"\w+|\{\{[^}]*\}\}|MEASURE\((?:\w+|\{\{[^}]*\}\})\)", flags=re.IGNORECASE)
CONNECTION = {
    "host": "${CUBE_HOST}",
    "user": "${CUBEJS_SQL_USER}",
    "password": "${CUBEJS_SQL_PASSWORD}",
}


def _tags(text: str) -> list[tuple[str, dict[str, str]]]:
    return [(m.group(1), dict(ATTRIBUTE.findall(m.group(2)))) for m in TAG.finditer(text)]


def _offences(text: str) -> list[str]:
    found = ["a SQL block"] if re.search(r"^```sql", text, flags=re.MULTILINE) else []
    for tag, attributes in _tags(text):
        for key, raw in attributes.items():
            for item in QUOTED.findall(raw) or [raw]:
                column = key in COLUMN_KEYS or (key == "value" and tag in COLUMN_TAGS)
                if (column or "MEASURE(" in item.upper()) and not NAMES.fullmatch(item.strip()):
                    found.append(f"{tag} {key}={item!r}")
    return found


def _pages() -> list[Path]:
    return sorted(REPORTS.rglob("*.md"))


def test_the_pages_name_measures() -> None:
    """Guards the scan below: with no measure named anywhere, it would pass on nothing."""
    assert any("MEASURE(" in path.read_text() for path in _pages())


def test_the_reports_define_nothing() -> None:
    assert not (REPORTS / "metrics").exists(), "metrics/ is Evidence's own semantic layer: use Cube"
    assert not list(REPORTS.rglob("*.sql")), "SQL files compute; name a Cube measure instead"
    found = {path.name: offences for path in _pages() if (offences := _offences(path.read_text()))}
    assert not found, f"a formula in a page -- define it in semantic/model/: {found}"


def test_every_table_turns_subtotals_off() -> None:
    """Subtotals are on by default and fail on a Cube connection; `evidence validate` misses it."""
    missing = [
        path.name
        for path in _pages()
        for tag, attributes in _tags(path.read_text())
        if tag == "table" and attributes.get("subtotals") != "false"
    ]
    assert not missing, f"table without subtotals=false: {missing}"


def test_the_connection_reaches_cube_with_the_reports_login() -> None:
    """Committed, so it holds references; and only these, or it could name an admin secret."""
    connection = yaml.safe_load((REPORTS / "connection.yaml").read_text())
    assert connection["type"] == "cube", "the reports read the semantic layer, never the lake"
    assert {key: connection.get(key) for key in CONNECTION} == CONNECTION


def test_the_images_are_pinned() -> None:
    """The CLI runs from the serve image, so the image's tag is the project's Evidence version."""
    config = yaml.safe_load((REPORTS / "evidence.config.yaml").read_text())
    serve = re.search(
        r"evidencedev/serve:([\w.]+)@sha256:[0-9a-f]{64}", (REPORTS / "Dockerfile").read_text()
    )
    assert serve and serve.group(1) == config["project"]["evidence"], (
        "pin serve by digest, at the project's version"
    )
    compose = (settings.REPO_ROOT / "docker-compose.yml").read_text()
    assert re.search(r"cubejs/cube:[\w.]+@sha256:[0-9a-f]{64}", compose), (
        "pin cubejs/cube by digest"
    )


@pytest.mark.parametrize(
    "page",
    [
        '{% bar_chart data="sales" y="sum(in_full_rate)" /%}',
        '{% line_chart\n    data="sales"\n    y=["MEASURE(a)", "MEASURE(a) * 100"]\n/%}',
        '{% bar_chart data="sales" y="MEASURE(sales.in_full_rate)" /%}',
        '{% bar_chart data="sales" y="MEASURE(r)" having="MEASURE(a) / MEASURE(b) > 0.5" /%}',
        "```sql r\nSELECT avg(r) FROM (SELECT MEASURE(x) AS r FROM sales GROUP BY 1)\n```",
    ],
)
def test_the_scan_catches_a_formula(page: str) -> None:
    assert _offences(page)


def test_the_scan_lets_names_literals_and_prose_through() -> None:
    page = (
        "Line count (order lines) is the max (per month), a/b in prose.\n"
        '{% dropdown id="m" title="Max (per month)" %}\n'
        '{% option value="North America" /%}{% /dropdown %}\n'
        '{% bar_chart data="sales" x="brand" y="MEASURE({{ m.literal }})" filters=["brand"] /%}\n'
    )
    assert _offences(page) == []
