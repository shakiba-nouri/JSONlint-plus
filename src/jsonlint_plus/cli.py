"""Command-line interface for JSONLint+."""

import argparse

from jsonlint_plus import __version__


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="jsonlint-plus",
        description=(
            "Analyze JSON syntax and structure, "
            "and suggest safe repairs."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def main() -> int:
    """Run the command-line interface."""
    parser = build_parser()
    parser.parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())