"""The `wwi` command. Argument wiring and one place where a ToolingError becomes an exit code.

Every subcommand is a thin adapter: parse, call into the package that does the work, print what it
returns. Keeping `main()` out of the working modules is what makes them importable by a test
without a subprocess -- previously each module carried its own argparse and could exit the
interpreter on import.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from config import settings
from utils.exceptions import ToolingError

Handler = Callable[[argparse.Namespace], str]


def _extract(args: argparse.Namespace) -> str:
    from ingestion.pipeline import extract

    return extract(args.source_db, Path(args.output_dir))


def _manifest(args: argparse.Namespace) -> str:
    from contracts import manifest

    return manifest.generate(Path(args.input_dir), Path(args.output))


def _sources(args: argparse.Namespace) -> str:
    from contracts import dbt_sources, manifest

    loaded = manifest.load(Path(args.manifest))
    output = Path(args.output)
    return dbt_sources.check(loaded, output) if args.check else dbt_sources.write(loaded, output)


def _seed(args: argparse.Namespace) -> str:
    from connectors import s3
    from contracts import manifest
    from contracts.paths import bronze_prefix
    from ingestion import upload

    loaded = manifest.load(Path(args.manifest))
    bucket = settings.bucket()
    fs = s3.client()
    # <prefix>/<snapshot-id>, so a new extraction lands beside the previous one. The contract
    # requires a new identifier, not a replaced file.
    prefix = bronze_prefix(loaded)
    total = len(loaded["tables"])

    if args.empty:
        # sources.yml names this prefix, so an empty seed writes the keys the real snapshot holds.
        if not args.force and upload.published_snapshot_present(fs, bucket, prefix, loaded):
            raise ToolingError(
                f"s3://{bucket}/{prefix}/ already holds the published snapshot -- refusing to "
                "replace it with empty files. Pass --force if that is really what you want"
            )
        problems = upload.seed_empty(loaded, bucket, prefix)
        verb = f"wrote {total} zero-row tables"
    else:
        problems = upload.upload(loaded, fs, bucket, prefix, Path(args.data_dir))
        verb = f"uploaded {total} tables"

    if problems:
        raise ToolingError(
            f"{len(problems)} problem(s) across {total} tables:\n"
            + "\n".join(f"  {p}" for p in problems)
        )
    return f"{verb} to s3://{bucket}/{prefix}/"


def _verify(args: argparse.Namespace) -> str:
    from contracts import manifest
    from ingestion import verify

    loaded = manifest.load(Path(args.manifest))
    source = verify.StoreSource(loaded)
    failures = verify.failures(loaded, source)
    if failures:
        raise ToolingError(
            "\n".join(f"FAIL {f}" for f in failures) + f"\n\n{len(failures)} check(s) failed"
        )
    return verify.summary(loaded, source)


def _shape(_: argparse.Namespace) -> str:
    from connectors import ducklake
    from warehouse import shape

    return shape.report(ducklake.connect())


def _wait_storage(args: argparse.Namespace) -> str:
    from connectors import s3

    return s3.wait_until_ready(timeout=args.timeout, interval=args.interval)


def _bootstrap(_: argparse.Namespace) -> str:
    from demo.bootstrap import write_env

    return write_env()


def _demo(args: argparse.Namespace) -> str:
    from demo.run import walkthrough

    return walkthrough(keep_warehouse=args.keep_warehouse)


def _demo_fixture(args: argparse.Namespace) -> str:
    from demo.fixture import cut

    return cut(
        Path(args.input_dir), Path(args.output_dir), Path(args.source_manifest), args.from_date
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wwi", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("extract", help="read the source into data/raw/ as Parquet")
    p.add_argument("--source-db", default="WideWorldImporters")
    p.add_argument("--output-dir", default=str(settings.RAW_DIR))
    p.set_defaults(handler=_extract)

    p = sub.add_parser("manifest", help="describe data/raw/ as a committed manifest")
    p.add_argument("--input-dir", default=str(settings.RAW_DIR))
    p.add_argument("--output", default=str(settings.SNAPSHOT_MANIFEST))
    p.set_defaults(handler=_manifest)

    p = sub.add_parser("sources", help="project the manifest into dbt's sources.yml")
    p.add_argument("--manifest", default=str(settings.SNAPSHOT_MANIFEST))
    p.add_argument("--output", default=str(settings.DBT_DIR / "models" / "sources.yml"))
    p.add_argument(
        "--check", action="store_true", help="exit 1 if it would differ, without writing"
    )
    p.set_defaults(handler=_sources)

    # A manifest and the Parquet it describes are passed separately because they do not live
    # together: the snapshot's manifest is committed while its Parquet is not, so they sit in
    # different directories. The fixture keeps both in one place; neither is special-cased.
    p = sub.add_parser("seed", help="publish a snapshot to the store's bronze layer")
    p.add_argument("--manifest", default=str(settings.SNAPSHOT_MANIFEST))
    p.add_argument("--data-dir", default=str(settings.RAW_DIR))
    p.add_argument("--empty", action="store_true", help="write zero-row Parquet with the schema")
    p.add_argument("--force", action="store_true", help="with --empty, overwrite a real snapshot")
    p.set_defaults(handler=_seed)

    p = sub.add_parser("verify", help="check the published snapshot against its manifest")
    p.add_argument("--manifest", default=str(settings.SNAPSHOT_MANIFEST))
    p.set_defaults(handler=_verify)

    p = sub.add_parser("shape", help="every relation with its row and column count")
    p.set_defaults(handler=_shape)

    p = sub.add_parser("wait-storage", help="create the bucket and block until it takes a write")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--interval", type=float, default=2.0)
    p.set_defaults(handler=_wait_storage)

    p = sub.add_parser("bootstrap", help="write a .env with generated local credentials")
    p.set_defaults(handler=_bootstrap)

    p = sub.add_parser("demo", help="a fresh clone to a queryable star schema, in one command")
    p.add_argument("--keep-warehouse", action="store_true", help="skip the provenance guard")
    p.set_defaults(handler=_demo)

    p = sub.add_parser("demo-fixture", help="cut the committed fixture from the full snapshot")
    p.add_argument("--input-dir", default=str(settings.RAW_DIR))
    p.add_argument("--source-manifest", default=str(settings.SNAPSHOT_MANIFEST))
    p.add_argument("--output-dir", default=str(settings.DEMO_DIR))
    p.add_argument("--from-date", default="2018-01-01")
    p.set_defaults(handler=_demo_fixture)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        print(args.handler(args))
    except ToolingError as error:
        print(error, file=sys.stderr)
        return 1
    return 0
