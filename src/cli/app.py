"""The `wwi` command: parse arguments, call the package that does the work, print the result.

A handler raises ToolingError on failure; `main()` is the one place that turns it into an exit code.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from config import settings
from utils.exceptions import ToolingError

Handler = Callable[[argparse.Namespace], str]

# Each handler imports what it needs only when it is chosen: `wwi shape` must not pay for
# sqlalchemy and dlt -- see the PLC0415 exemption for this file in pyproject.toml.


def _wait_storage(args: argparse.Namespace) -> str:
    from connectors import s3

    return s3.wait_until_ready(timeout=args.timeout, interval=args.interval)


def _extract(args: argparse.Namespace) -> str:
    from ingestion.pipeline import extract

    return extract(args.source_db, Path(args.manifest))


def _verify(args: argparse.Namespace) -> str:
    from contracts import manifest
    from ingestion import verify

    loaded = manifest.load(Path(args.manifest))
    source = verify.StoreSource(loaded)
    found = verify.failures(loaded, source)
    if found:
        raise ToolingError(
            "\n".join(f"FAIL {f}" for f in found) + f"\n\n{len(found)} check(s) failed"
        )
    return verify.summary(loaded, source)


def _sources(args: argparse.Namespace) -> str:
    from contracts import dbt_sources, manifest

    loaded = manifest.load(Path(args.manifest))
    output = Path(args.output)
    return dbt_sources.check(loaded, output) if args.check else dbt_sources.write(loaded, output)


def _shape(_: argparse.Namespace) -> str:
    from connectors import ducklake
    from warehouse import shape

    return shape.report(ducklake.connect())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wwi", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("wait-storage", help="create the bucket and block until it takes a write")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--interval", type=float, default=2.0)
    p.set_defaults(handler=_wait_storage)

    p = sub.add_parser("extract", help="load the source into bronze and write the manifest")
    p.add_argument("--source-db", default="WideWorldImporters")
    p.add_argument("--manifest", default=str(settings.SNAPSHOT_MANIFEST))
    p.set_defaults(handler=_extract)

    p = sub.add_parser("verify", help="check the published snapshot against its manifest")
    p.add_argument("--manifest", default=str(settings.SNAPSHOT_MANIFEST))
    p.set_defaults(handler=_verify)

    p = sub.add_parser("sources", help="project the manifest into dbt's sources.yml")
    p.add_argument("--manifest", default=str(settings.SNAPSHOT_MANIFEST))
    p.add_argument("--output", default=str(settings.DBT_DIR / "models" / "sources.yml"))
    p.add_argument(
        "--check", action="store_true", help="exit 1 if it would differ, without writing"
    )
    p.set_defaults(handler=_sources)

    p = sub.add_parser("shape", help="every relation with its row and column count")
    p.set_defaults(handler=_shape)

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
