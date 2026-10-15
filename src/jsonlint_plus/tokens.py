
"""Token definitions for JSONLint+."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COLON = auto()
    COMMA = auto()

    STRING = auto()
    NUMBER = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()

    EOF = auto()


@dataclass(frozen=True)
class Token:
    """A token produced by the lexer."""

    type: TokenType
    value: str
    line: int
    column: int
