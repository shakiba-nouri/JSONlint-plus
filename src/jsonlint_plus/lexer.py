
"""Lexical analyzer for JSONLint+."""

import re

from jsonlint_plus.tokens import Token, TokenType


class LexerError(Exception):
    """Raised when the lexer encounters invalid input."""

    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")


_NUMBER_PATTERN = re.compile(
    r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
)

_PUNCTUATION = {
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ":": TokenType.COLON,
    ",": TokenType.COMMA,
}

_KEYWORDS = {
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,
}


class Lexer:
    """Convert JSON text into a sequence of tokens."""

    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.line = 1
        self.column = 1

    def _current(self) -> str | None:
        if self.position >= len(self.source):
            return None
        return self.source[self.position]

    @staticmethod
    def _is_word_char(char: str) -> bool:
        """Return True for characters that may continue a keyword."""
        return char.isalnum() or char == "_"

    def _advance(self) -> str:
        char = self.source[self.position]
        self.position += 1

        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return char

    def _skip_whitespace(self) -> None:
        while self._current() in (" ", "\t", "\r", "\n"):
            self._advance()

    def _make_token(
        self,
        token_type: TokenType,
        value: str,
        line: int,
        column: int,
    ) -> Token:
        return Token(token_type, value, line, column)

    def _read_string(self) -> Token:
        start_line = self.line
        start_column = self.column
        start = self.position

        self._advance()  # Opening quote.

        while True:
            char = self._current()

            if char is None:
                raise LexerError(
                    "Unterminated string",
                    start_line,
                    start_column,
                )

            if char == '"':
                self._advance()
                break

            if ord(char) < 0x20:
                raise LexerError(
                    "Unescaped control character in string",
                    self.line,
                    self.column,
                )

            if char == "\\":
                escape_line = self.line
                escape_column = self.column
                self._advance()

                escaped = self._current()
                if escaped is None:
                    raise LexerError(
                        "Incomplete escape sequence",
                        escape_line,
                        escape_column,
                    )

                if escaped in '"\\/bfnrt':
                    self._advance()
                    continue

                if escaped == "u":
                    self._advance()

                    for _ in range(4):
                        digit = self._current()
                        if digit is None or digit not in "0123456789abcdefABCDEF":
                            raise LexerError(
                                "Invalid Unicode escape; expected four hex digits",
                                self.line,
                                self.column,
                            )
                        self._advance()

                    continue

                raise LexerError(
                    f"Invalid escape sequence: \\{escaped}",
                    escape_line,
                    escape_column,
                )

            self._advance()

        value = self.source[start:self.position]
        return self._make_token(
            TokenType.STRING,
            value,
            start_line,
            start_column,
        )

    def _read_number(self) -> Token:
        start_line = self.line
        start_column = self.column
        start = self.position

        match = _NUMBER_PATTERN.match(self.source, self.position)

        if match is None:
            raise LexerError("Invalid number", start_line, start_column)

        end = match.end()

        # Reject malformed numbers such as 01, 1. or 2e+.
        if end < len(self.source):
            next_char = self.source[end]
            if next_char.isalnum() or next_char in "._":
                raise LexerError(
                    "Invalid number",
                    start_line,
                    start_column,
                )

        while self.position < end:
            self._advance()

        value = self.source[start:self.position]
        return self._make_token(
            TokenType.NUMBER,
            value,
            start_line,
            start_column,
        )

    def tokenize(self) -> list[Token]:
        """Tokenize the complete source and append EOF."""
        tokens: list[Token] = []

        while self._current() is not None:
            self._skip_whitespace()
            char = self._current()

            if char is None:
                break

            line = self.line
            column = self.column

            if char in _PUNCTUATION:
                token_type = _PUNCTUATION[char]
                self._advance()
                tokens.append(self._make_token(token_type, char, line, column))
                continue

            if char == '"':
                tokens.append(self._read_string())
                continue

            if char == "-" or char.isdigit():
                tokens.append(self._read_number())
                continue

            if char.isalpha():
                start = self.position

                while self._current() is not None and self._is_word_char(
                    self._current()
                ):
                    self._advance()

                word = self.source[start:self.position]
                token_type = _KEYWORDS.get(word)

                if token_type is None:
                    raise LexerError(
                        f"Unexpected identifier: {word}",
                        line,
                        column,
                    )

                tokens.append(
                    self._make_token(token_type, word, line, column)
                )
                continue

            raise LexerError(
                f"Unexpected character: {char!r}",
                line,
                column,
            )

        tokens.append(
            self._make_token(TokenType.EOF, "", self.line, self.column)
        )
        return tokens
