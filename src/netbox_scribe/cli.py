"""Command-line interface for NetBox Scribe."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from netbox_scribe import __version__


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    try:
        parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
