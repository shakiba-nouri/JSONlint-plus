"""Recursive-descent parser for JSONLint+.

The parser consumes the token stream produced by :class:`jsonlint_plus.lexer.Lexer`
and verifies the document against the grammar in ``docs/grammar.ebnf``.
It raises :class:`ParserError` for any syntax violation, reporting the
line and column of the offending token.

For now the parsed value is returned as plain Python objects (``dict``,
``list``, ``str``, ``int``, ``float``, ``bool`` and ``None``). Dedicated
AST node classes are introduced in a later step.
"""

from __future__ import annotations

from typing import Any

from jsonlint_plus.tokens import Token, TokenType


class ParserError(Exception):
    """Raised when the token stream does not match the JSON grammar."""

    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")


_STRING_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def decode_string_literal(raw: str) -> str:
    """Turn a raw JSON string token (including quotes) into its value."""
    characters: list[str] = []
    index = 1
    end = len(raw) - 1

    while index < end:
        char = raw[index]

        if char != "\\":
            characters.append(char)
            index += 1
            continue

        escaped = raw[index + 1]

        if escaped == "u":
            code = int(raw[index + 2:index + 6], 16)
            characters.append(chr(code))
            index += 6
            continue

        characters.append(_STRING_ESCAPES[escaped])
        index += 2

    return "".join(characters)


def number_value(raw: str) -> int | float:
    """Convert a JSON number token into an ``int`` or ``float``."""
    if any(char in raw for char in ".eE"):
        return float(raw)
    return int(raw)


class Parser:
    """Parse a JSON token stream into a value."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0

    @property
    def _current(self) -> Token:
        if self.position >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[self.position]

    def _advance(self) -> Token:
        token = self._current
        if token.type != TokenType.EOF:
            self.position += 1
        return token

    def _check(self, token_type: TokenType) -> bool:
        return self._current.type == token_type

    def _match(self, token_type: TokenType) -> Token | None:
        if self._check(token_type):
            return self._advance()
        return None

    def _expect(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        token = self._current
        raise ParserError(message, token.line, token.column)

    def _describe(self, token: Token) -> str:
        if token.type == TokenType.EOF:
            return "end of input"
        return repr(token.value)

    def parse(self) -> Any:
        """Parse a single JSON value and require end of input."""
        value = self._parse_value()

        if not self._check(TokenType.EOF):
            token = self._current
            raise ParserError(
                f"Unexpected trailing token: {self._describe(token)}",
                token.line,
                token.column,
            )

        return value

    def _parse_value(self) -> Any:
        token = self._current

        if token.type == TokenType.LBRACE:
            return self._parse_object()

        if token.type == TokenType.LBRACKET:
            return self._parse_array()

        if token.type == TokenType.STRING:
            self._advance()
            return decode_string_literal(token.value)

        if token.type == TokenType.NUMBER:
            self._advance()
            return number_value(token.value)

        if token.type == TokenType.TRUE:
            self._advance()
            return True

        if token.type == TokenType.FALSE:
            self._advance()
            return False

        if token.type == TokenType.NULL:
            self._advance()
            return None

        raise ParserError(
            f"Expected a value but found {self._describe(token)}",
            token.line,
            token.column,
        )

    def _parse_object(self) -> dict[str, Any]:
        self._expect(TokenType.LBRACE, "Expected '{' to start an object")

        members: dict[str, Any] = {}

        if self._match(TokenType.RBRACE):
            return members

        while True:
            key_token = self._expect(
                TokenType.STRING,
                "Expected a string key in object",
            )
            key = decode_string_literal(key_token.value)

            self._expect(TokenType.COLON, "Expected ':' after object key")
            members[key] = self._parse_value()

            comma = self._match(TokenType.COMMA)
            if comma is None:
                break

            if self._check(TokenType.RBRACE):
                raise ParserError(
                    "Trailing comma is not allowed in an object",
                    comma.line,
                    comma.column,
                )

        self._expect(TokenType.RBRACE, "Expected '}' to close object")
        return members

    def _parse_array(self) -> list[Any]:
        self._expect(TokenType.LBRACKET, "Expected '[' to start an array")

        elements: list[Any] = []

        if self._match(TokenType.RBRACKET):
            return elements

        while True:
            elements.append(self._parse_value())

            comma = self._match(TokenType.COMMA)
            if comma is None:
                break

            if self._check(TokenType.RBRACKET):
                raise ParserError(
                    "Trailing comma is not allowed in an array",
                    comma.line,
                    comma.column,
                )

        self._expect(TokenType.RBRACKET, "Expected ']' to close array")
        return elements


def parse(source: str) -> Any:
    """Tokenize and parse a JSON document from source text."""
    from jsonlint_plus.lexer import Lexer

    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()
