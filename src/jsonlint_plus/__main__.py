"""Allow running JSONLint+ as a Python module."""

from jsonlint_plus.cli import main


if __name__ == "__main__":
    raise SystemExit(main())