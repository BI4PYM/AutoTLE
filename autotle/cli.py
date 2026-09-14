from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import PipelineOptions, delete_state_records, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update AutoTLE OMM/TLE satellite files")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--list", action="append", dest="lists", help="satellite list JSON (repeatable)")
    parser.add_argument("--state", help="pickle state path (default: ROOT/satellites.pkl)")
    parser.add_argument("--output-dir", help="output directory (default: ROOT/satellites)")
    parser.add_argument("--source", action="append", choices=["celestrak", "satnogs", "localtle", "localjson", "local"], help="source order")
    parser.add_argument("--celestrak-format", action="append", help="CelesTrak source format order")
    parser.add_argument("--timeout", type=float, help="HTTP timeout seconds")
    parser.add_argument("--retries", type=int, help="HTTP retries")
    parser.add_argument("--proxy", help="HTTP/HTTPS proxy URL")
    parser.add_argument("--offline", action="store_true", help="use only local TLE/state files")
    parser.add_argument("--dry-run", action="store_true", help="fetch and merge without writing files")
    parser.add_argument("--delete-id", action="append", dest="delete_ids", metavar="ID", help="delete a cached record by NORAD/TLE alias or INTDES; repeatable")
    parser.add_argument("--limit", type=int, help="process only the first N satellites in each list")
    parser.add_argument("--quiet", action="store_true", help="only print summary")
    return parser


def _options_from_args(args: argparse.Namespace) -> PipelineOptions:
    options = PipelineOptions.from_root(args.root)
    if args.lists:
        options.list_paths = [Path(item).resolve() for item in args.lists]
    if args.state:
        options.state_path = Path(args.state).resolve()
    if args.output_dir:
        options.output_dir = Path(args.output_dir).resolve()
    if args.source:
        options.sources = tuple(args.source)
    if args.celestrak_format:
        options.celestrak_formats = tuple(item.upper() for item in args.celestrak_format)
    if args.timeout is not None:
        options.timeout = args.timeout
    if args.retries is not None:
        options.retries = args.retries
    if args.proxy is not None:
        options.proxy = args.proxy
    options.offline = args.offline or options.offline
    options.dry_run = args.dry_run
    options.limit = args.limit
    options.quiet = args.quiet or options.quiet
    return options


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = _options_from_args(args)
    try:
        if args.delete_ids:
            result = delete_state_records(options, args.delete_ids)
            print(
                "AutoTLE delete: requested={requested} deleted={deleted} missing={missing} "
                "remaining={remaining}".format(**result)
            )
            if not args.quiet:
                for item in result["details"]:
                    print(f"  {item['id']}: {item['status']}" + (f" ({item['detail']})" if item.get("detail") else ""))
            return 0 if result["deleted"] else 1
        result = run_pipeline(options)
    except Exception as exc:
        print(f"AutoTLE failed: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print(
        "AutoTLE: lists={lists} satellites={satellites} added={added} updated={updated} "
        "stale={stale} same={same} skipped={skipped} errors={errors}".format(**summary)
    )
    if not args.quiet:
        for report in result["reports"]:
            print(f"[{report.config.source_name}] {len(report.keys)} satellites")
            for output in report.outputs:
                print(f"  wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
