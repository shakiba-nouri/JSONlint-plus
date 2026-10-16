"""Tests for the JSONLint+ parser."""

import pytest

from jsonlint_plus.lexer import Lexer, LexerError
from jsonlint_plus.parser import Parser, ParserError, parse


def test_parses_simple_object():
    assert parse('{"age": 20}') == {"age": 20}


def test_parses_nested_structures():
    source = '{"a": [1, {"b": true}], "c": null}'

    assert parse(source) == {"a": [1, {"b": True}], "c": None}


def test_parses_empty_object_and_array():
    assert parse("{}") == {}
    assert parse("[]") == []


def test_parses_top_level_scalars():
    assert parse("42") == 42
    assert parse('"hello"') == "hello"
    assert parse("true") is True
    assert parse("false") is False
    assert parse("null") is None


def test_decodes_string_escapes():
    assert parse(r'"line\nbreak"') == "line\nbreak"
    assert parse(r'"quote \" and slash \\"') == 'quote " and slash \\'
    assert parse(r'"tab\there"') == "tab\there"


def test_decodes_unicode_escapes():
    assert parse(r'"\u0041\u00e9"') == "A\u00e9"


@pytest.mark.parametrize(
    "source,expected",
    [
        ("0", 0),
        ("-17", -17),
        ("2.5", 2.5),
        ("-0.5", -0.5),
        ("1e3", 1000.0),
        ("2E-2", 0.02),
        ("1.5e2", 150.0),
    ],
)
def test_parses_number_types(source, expected):
    result = parse(source)

    assert result == expected
    if isinstance(expected, int):
        assert isinstance(result, int)
    else:
        assert isinstance(result, float)


@pytest.mark.parametrize(
    "source",
    [
        "{",
        '{"a": 1',
        '{"a": 1,}',
        '{"a" 1}',
        '{"a": 1 "b": 2}',
        '{"a": }',
        "{1: 2}",
        "[",
        "[1, 2",
        "[1, 2,]",
        "[1 2]",
        "",
        "{} {}",
        '{"a": 1}}',
        '{"a": 1} 5',
    ],
)
def test_rejects_invalid_syntax(source):
    with pytest.raises(ParserError):
        parse(source)


def test_reports_trailing_comma_location():
    source = '{\n  "a": 1,\n}'

    with pytest.raises(ParserError) as error:
        parse(source)

    assert "Trailing comma" in error.value.message
    assert error.value.line == 2
    assert error.value.column == 9


def test_reports_missing_colon_location():
    source = '{\n  "a" 1\n}'

    with pytest.raises(ParserError) as error:
        parse(source)

    assert "':'" in error.value.message
    assert error.value.line == 2
    assert error.value.column == 7


def test_error_points_at_first_problem():
    with pytest.raises(ParserError) as error:
        parse("[1, 2 3]")

    assert error.value.line == 1
    assert error.value.column == 7


def test_parser_accepts_token_list_directly():
    tokens = Lexer('{"ok": true}').tokenize()

    assert Parser(tokens).parse() == {"ok": True}


def test_lexer_errors_propagate_through_parse():
    with pytest.raises(LexerError):
        parse('{"a": @}')
