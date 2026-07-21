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
from netbox_scribe.policy import ExportPolicy
from netbox_scribe.validation import SnapshotValidationError, validate_snapshot_text


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
    export_parser.add_argument(
        "--agent-index",
        type=Path,
        default=Path("snapshot/agent/INDEX.md"),
        help="Derived Markdown agent index path (default: %(default)s)",
    )
    export_parser.add_argument(
        "--allow-insecure-http",
        action="store_true",
        help="Allow plaintext HTTP token transport on a trusted network (unsafe)",
    )
    export_parser.add_argument("--include-field", action="append")
    export_parser.add_argument("--exclude-field", action="append", default=[])
    export_parser.add_argument("--include-custom-field", action="append", default=[])
    export_parser.add_argument("--exclude-custom-field", action="append", default=[])
    validate_parser = subcommands.add_parser(
        "validate",
        help="Validate a canonical snapshot against its published schema",
    )
    validate_parser.add_argument("snapshot", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1

    if args.command == "export":
        try:
            policy = ExportPolicy(
                include_fields=(
                    frozenset(args.include_field) if args.include_field is not None else None
                ),
                exclude_fields=frozenset(args.exclude_field),
                include_custom_fields=frozenset(args.include_custom_field),
                exclude_custom_fields=frozenset(args.exclude_custom_field),
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return _run_export(
            args.output,
            args.agent_index,
            policy,
            allow_insecure_http=args.allow_insecure_http,
        )
    if args.command == "validate":
        return _run_validate(args.snapshot)

    parser.print_help()
    return 0


def _run_validate(snapshot: Path) -> int:
    try:
        validate_snapshot_text(snapshot.read_text(encoding="utf-8"))
    except UnicodeError:
        print("error: snapshot is not valid UTF-8", file=sys.stderr)
        return 1
    except (OSError, SnapshotValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Valid snapshot: {snapshot}")
    return 0


def _run_export(
    output: Path,
    agent_index: Path,
    policy: ExportPolicy,
    *,
    allow_insecure_http: bool,
) -> int:
    base_url = os.environ.get("NETBOX_URL")
    token = os.environ.get("NETBOX_TOKEN")
    if not base_url or not token:
        print("error: NETBOX_URL and NETBOX_TOKEN are required for export", file=sys.stderr)
        return 2

    try:
        with NetBoxClient(
            base_url,
            token,
            allow_insecure_http=allow_insecure_http,
        ) as client:
            count = export_devices(client, output, agent_index=agent_index, policy=policy)
    except (NetBoxClientError, SnapshotValidationError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    noun = "device" if count == 1 else "devices"
    print(f"Exported {count} {noun} to {output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
