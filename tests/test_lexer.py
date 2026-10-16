
"""Tests for the JSONLint+ lexer."""

import pytest

from jsonlint_plus.lexer import Lexer, LexerError
from jsonlint_plus.tokens import TokenType


def test_tokenizes_json_object():
    tokens = Lexer('{"age": 20}').tokenize()

    assert [token.type for token in tokens] == [
        TokenType.LBRACE,
        TokenType.STRING,
        TokenType.COLON,
        TokenType.NUMBER,
        TokenType.RBRACE,
        TokenType.EOF,
    ]


def test_tokenizes_keywords_and_array():
    tokens = Lexer('[true, false, null]').tokenize()

    assert [token.type for token in tokens] == [
        TokenType.LBRACKET,
        TokenType.TRUE,
        TokenType.COMMA,
        TokenType.FALSE,
        TokenType.COMMA,
        TokenType.NULL,
        TokenType.RBRACKET,
        TokenType.EOF,
    ]


def test_preserves_string_and_number_values():
    tokens = Lexer('{"name": "Ali", "age": -2.5e2}').tokenize()

    values = [token.value for token in tokens]

    assert '"name"' in values
    assert '"Ali"' in values
    assert "-2.5e2" in values


def test_tracks_line_and_column():
    tokens = Lexer('{\n  "x": 1\n}').tokenize()

    string_token = next(
        token for token in tokens if token.type == TokenType.STRING
    )

    assert string_token.line == 2
    assert string_token.column == 3


@pytest.mark.parametrize(
    "source",
    [
        "@",
        "undefined",
        '"unfinished',
        '"bad\\q"',
        "01",
        "1.",
        "2e+",
    ],
)
def test_rejects_invalid_lexical_input(source):
    with pytest.raises(LexerError):
        Lexer(source).tokenize()


def test_error_reports_location():
    with pytest.raises(LexerError) as error:
        Lexer('{\n  @\n}').tokenize()

    assert error.value.line == 2
    assert error.value.column == 3


@pytest.mark.parametrize(
    "source",
    [
        r'"simple"',
        r'"quote \" inside"',
        r'"backslash \\ inside"',
        r'"controls \b\f\n\r\t"',
        r'"solidus \/"',
        r'"unicode \u0041\u00e9"',
        r'"null char \u0000"',
    ],
)
def test_accepts_valid_string_literals(source):
    tokens = Lexer(source).tokenize()

    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == source


@pytest.mark.parametrize(
    "source",
    [
        '"unterminated',
        '"dangling \\',
        r'"\u12"',
        r'"\u12G4"',
        r'"bad escape \q"',
        '"raw\nnewline"',
        '"raw\ttab"',
    ],
)
def test_rejects_invalid_string_literals(source):
    with pytest.raises(LexerError):
        Lexer(source).tokenize()


@pytest.mark.parametrize(
    "source",
    ["01", "-01", "00", "1.", "1.2.3", "2e+", "1e", "1.2e", "1_000", "-"],
)
def test_rejects_invalid_numbers(source):
    with pytest.raises(LexerError):
        Lexer(source).tokenize()


@pytest.mark.parametrize("source", ["+1", ".5", "0x1F"])
def test_rejects_malformed_number_prefixes(source):
    with pytest.raises(LexerError):
        Lexer(source).tokenize()


@pytest.mark.parametrize(
    "source",
    ["true1", "false2", "null3", "true_", "trueValue", "TRUE"],
)
def test_rejects_keywords_with_trailing_characters(source):
    with pytest.raises(LexerError):
        Lexer(source).tokenize()


def test_tracks_columns_across_lines():
    tokens = Lexer('{\n  "a": 1\n}').tokenize()

    rbrace = next(token for token in tokens if token.type == TokenType.RBRACE)

    assert rbrace.line == 3
    assert rbrace.column == 1


def test_error_location_on_later_line():
    source = '{\n  "key": [\n    1,\n    @\n  ]\n}'

    with pytest.raises(LexerError) as error:
        Lexer(source).tokenize()

    assert error.value.line == 4
    assert error.value.column == 5


def test_eof_token_records_final_position():
    tokens = Lexer("123").tokenize()

    eof = tokens[-1]

    assert eof.type == TokenType.EOF
    assert eof.line == 1
    assert eof.column == 4
