"""Command-line interface for NetBox Scribe."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from netbox_scribe import __version__
from netbox_scribe.client import NetBoxClient, NetBoxClientError
from netbox_scribe.exporter import export_devices


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser without reading configuration."""
    parser = argparse.ArgumentParser(
        prog="nbscribe",
        description="Versioned, AI-ready infrastructure context from NetBox.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subcommands = parser.add_subparsers(dest="command")
    export_parser = subcommands.add_parser(
        "export",
        help="Export canonical inventory from NetBox",
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        default=Path("snapshot/inventory/devices.yaml"),
        help="Canonical device YAML path (default: %(default)s)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1

    if args.command == "export":
        return _run_export(args.output)

    parser.print_help()
    return 0


def _run_export(output: Path) -> int:
    base_url = os.environ.get("NETBOX_URL")
    token = os.environ.get("NETBOX_TOKEN")
    if not base_url or not token:
        print("error: NETBOX_URL and NETBOX_TOKEN are required for export", file=sys.stderr)
        return 2

    try:
        with NetBoxClient(base_url, token) as client:
            count = export_devices(client, output)
    except NetBoxClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    noun = "device" if count == 1 else "devices"
    print(f"Exported {count} {noun} to {output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
