"""Format validated JSON without changing token spelling or duplicate keys."""
from jsonlint_plus.lexer import Lexer
from jsonlint_plus.parser import parse
from jsonlint_plus.tokens import TokenType


def format_json(source: str, indent: str = '  ', eol: str = '\n') -> str:
    parse(source)
    tokens = Lexer(source).tokenize()
    parts = []
    depth = 0
    for i, token in enumerate(tokens[:-1]):
        kind = token.type
        previous = tokens[i - 1].type if i else None
        next_kind = tokens[i + 1].type
        if kind in (TokenType.LBRACE, TokenType.LBRACKET):
            parts.append(token.value)
            depth += 1
            if next_kind not in (TokenType.RBRACE, TokenType.RBRACKET):
                parts.append(eol + indent * depth)
        elif kind in (TokenType.RBRACE, TokenType.RBRACKET):
            depth -= 1
            if previous not in (TokenType.LBRACE, TokenType.LBRACKET):
                parts.append(eol + indent * depth)
            parts.append(token.value)
        elif kind == TokenType.COMMA:
            parts.append(',' + eol + indent * depth)
        elif kind == TokenType.COLON:
            parts.append(': ')
        else:
            parts.append(token.value)
    return ''.join(parts) + (eol if source.endswith(('\n', '\r')) else '')
