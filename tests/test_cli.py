"""Tests for the JSONLint+ command-line interface."""

import pytest

from jsonlint_plus import __version__
from jsonlint_plus.cli import build_parser


def test_program_name():
    parser = build_parser()

    assert parser.prog == "jsonlint-plus"


def test_help_option(capsys):
    parser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--help"])

    assert error.value.code == 0
    assert "Analyze JSON syntax" in capsys.readouterr().out


def test_version_option(capsys):
    parser = build_parser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args(["--version"])

    assert error.value.code == 0
    assert __version__ in capsys.readouterr().out