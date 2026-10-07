"""The pages reach Cube, and what Cube answers agrees with the star it reads.

Needs `make bi_up` and a built lake; `make bi_check` runs it with `--require-lake`, so a stack that
is not up fails instead of skipping. Every query goes through the Evidence CLI in the serve image,
with `reports/` mounted and the container's own Cube login: the path the pages take.
"""

from __future__ import annotations

import csv
import io
import json
import socket
import subprocess
from decimal import Decimal

import pytest

from config import settings
from connectors import ducklake

pytestmark = pytest.mark.integration

CUBE_SQL_API = ("127.0.0.1", 15442)
EVIDENCE = [
    "docker", "compose", "--profile", "bi", "run", "--rm", "--no-deps", "-T",
    "-v", "./reports:/project:ro", "evidence", "evidence",
]  # fmt: skip
AMOUNT_TOLERANCE = Decimal("0.005")
RATE_TOLERANCE = Decimal("1e-9")

# Each cut written twice: once naming Cube's measures, once as plain SQL over the star. The second
# is the reference, so it restates every formula on purpose.
MEASURES = (
    "MEASURE(ordered_amount_excl_tax) AS amount, MEASURE(ordered_quantity) AS quantity, "
    "MEASURE(order_lines) AS lines, MEASURE(in_full_rate) AS in_full_rate"
)
REFERENCE = (
    "sum(f.quantity * f.unit_price) as amount, sum(f.quantity) as quantity, count(*) as lines, "
    "avg(case when f.picked_quantity >= f.quantity then 1.0 else 0.0 end) as in_full_rate"
)
STAR = (
    "from lake.core.fct_sales_order_line as f "
    "left join lake.core.dim_date as d on f.order_date_key = d.date_key "
    "left join lake.core.dim_customer as c on f.customer_key = c.customer_key "
    "left join lake.core.dim_stock_item as s on f.stock_item_key = s.stock_item_key"
)
# Each cut as Cube is asked for it, and as the star answers it. The month cut is the one the line
# chart sends: a time dimension truncated to its grain.
CUTS = {
    "month": (
        "DATE_TRUNC('month', full_date)",
        "strftime(date_trunc('month', d.full_date), '%Y-%m-%d')",
    ),
    "customer_category": ("customer_category_name", "c.customer_category_name"),
    "brand": ("brand", "coalesce(s.brand, '(none)')"),
}


@pytest.fixture(scope="module", autouse=True)
def cube_is_up(request: pytest.FixtureRequest) -> None:
    try:
        socket.create_connection(CUBE_SQL_API, timeout=3).close()
    except OSError:
        not_ready = pytest.fail if request.config.getoption("--require-lake") else pytest.skip
        not_ready("Cube's SQL API is not reachable -- run `make bi_up`")


def _evidence(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*EVIDENCE, *args, "--project", "/project"],
        cwd=settings.REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_validate_checks_the_pages_against_cube() -> None:
    result = _evidence("validate", "--json")
    line = next((x for x in result.stdout.splitlines() if x.startswith("{")), None)
    assert line, (
        f"no JSON from evidence validate:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
    )
    report = json.loads(line)
    # With Cube unreachable, validate drops to syntax-only and still exits 0.
    assert report["mode"] == "warehouse", (
        f"validate never reached Cube: {report.get('metadataError')}"
    )
    assert report["valid"] and result.returncode == 0, json.dumps(report["files"], indent=1)


@pytest.mark.parametrize("cut", CUTS)
def test_the_measures_agree_with_the_star(cut: str) -> None:
    through_cube, through_star = CUTS[cut]
    sql = f"SELECT {through_cube} AS key, {MEASURES} FROM sales GROUP BY 1 ORDER BY 1"
    result = _evidence("query", sql, "--format", "csv", "--limit", "100000", "--quiet")
    if result.returncode != 0:
        pytest.fail(f"evidence query failed:\n{result.stderr[-2000:]}")
    cube = {row["key"]: row for row in csv.DictReader(io.StringIO(result.stdout))}

    conn = ducklake.connect()
    columns = ("key", "amount", "quantity", "lines", "in_full_rate")
    sql = f"select {through_star} as key, {REFERENCE} {STAR} group by 1"
    star = {
        str(row[0]): dict(zip(columns, row, strict=True)) for row in conn.execute(sql).fetchall()
    }
    conn.close()

    assert star, "the star is empty -- run `make build`"
    assert set(cube) == set(star), (
        f"groups differ: only in Cube {sorted(set(cube) - set(star))}, "
        f"only in the star {sorted(set(star) - set(cube))}"
    )
    wrong = []
    for key, expected in star.items():
        for column in columns[1:]:
            tolerance = RATE_TOLERANCE if column == "in_full_rate" else AMOUNT_TOLERANCE
            got = Decimal(cube[key][column])
            if abs(got - Decimal(str(expected[column]))) > tolerance:
                wrong.append(f"{key}.{column}: Cube {got}, star {expected[column]}")
    assert not wrong, wrong
