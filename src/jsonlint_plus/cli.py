"""Command-line interface for validating JSON files, text, or stdin."""
import argparse
import sys
from pathlib import Path

from jsonlint_plus import __version__
from jsonlint_plus.diagnostics import analyze


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jsonlint-plus",
        description="Analyze JSON syntax and structure, and suggest safe repairs.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("file", nargs="?", help="JSON file to validate; use - or omit to read stdin")
    source.add_argument("--text", help="JSON text to validate")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    label = '<text>' if args.text is not None else (args.file or '<stdin>')
    try:
        source = args.text if args.text is not None else (
            sys.stdin.read() if not args.file or args.file == '-' else Path(args.file).read_text(encoding='utf-8')
        )
        result = analyze(source)
    except (OSError, UnicodeError, RecursionError, ValueError) as error:
        print(f'{label}: {error}', file=sys.stderr)
        return 2
    if not result['diagnostics']:
        print(f'{label}: valid JSON')
        return 0
    for item in result['diagnostics']:
        print(f"{label}:{item['line']}:{item['column']}: {item['message']}", file=sys.stderr)
        if 'fix' in item:
            print(f"  Suggestion: {item['fix']['title']}", file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
