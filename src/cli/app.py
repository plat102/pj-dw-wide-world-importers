"""The `wwi` command: parse arguments, call the package that does the work, print the result.

A handler raises ToolingError on failure; `main()` is the one place that turns it into an exit code.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from utils.exceptions import ToolingError

Handler = Callable[[argparse.Namespace], str]

# Each handler imports what it needs only when it is chosen: `wwi shape` must not pay for
# sqlalchemy and dlt -- see the PLC0415 exemption for this file in pyproject.toml.


def _wait_storage(args: argparse.Namespace) -> str:
    from connectors import s3

    return s3.wait_until_ready(timeout=args.timeout, interval=args.interval)


def _extract(args: argparse.Namespace) -> str:
    from ingestion.pipeline import extract

    return extract(args.source_db)


def _shape(_: argparse.Namespace) -> str:
    from connectors import ducklake
    from warehouse import shape

    return shape.report(ducklake.connect())


def _catalog(_: argparse.Namespace) -> str:
    from connectors import ducklake
    from warehouse import catalog

    return catalog.report(ducklake.connect())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wwi", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("wait-storage", help="create the bucket and block until it takes a write")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--interval", type=float, default=2.0)
    p.set_defaults(handler=_wait_storage)

    p = sub.add_parser("extract", help="load the source into the lake's raw schema")
    p.add_argument("--source-db", default="WideWorldImporters")
    p.set_defaults(handler=_extract)

    p = sub.add_parser("shape", help="every relation with its row and column count")
    p.set_defaults(handler=_shape)

    p = sub.add_parser("catalog", help="the column catalog, as markdown, from the manifest")
    p.set_defaults(handler=_catalog)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler: Handler = args.handler
    try:
        print(handler(args))
    except ToolingError as error:
        print(error, file=sys.stderr)
        return 1
    return 0
