
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
