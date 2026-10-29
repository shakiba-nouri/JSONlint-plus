"""Build a location-aware JSON abstract syntax tree from valid tokens."""
from jsonlint_plus.lexer import Lexer
from jsonlint_plus.parser import decode_string_literal, number_value
from jsonlint_plus.tokens import TokenType


def inspect(source: str) -> dict:
    tokens = Lexer(source).tokenize()
    index = 0

    def value():
        nonlocal index
        token = tokens[index]
        index += 1
        node = {"type": token.type.name.lower(), "line": token.line, "column": token.column}
        if token.type == TokenType.LBRACE:
            node["type"] = "object"
            node["children"] = []
            while tokens[index].type != TokenType.RBRACE:
                key = tokens[index]
                index += 2  # key and colon
                child = value()
                node["children"].append({"type": "property", "key": decode_string_literal(key.value),
                                         "line": key.line, "column": key.column, "children": [child]})
                if tokens[index].type != TokenType.COMMA:
                    break
                index += 1
            index += 1
        elif token.type == TokenType.LBRACKET:
            node["type"] = "array"
            node["children"] = []
            while tokens[index].type != TokenType.RBRACKET:
                node["children"].append(value())
                if tokens[index].type != TokenType.COMMA:
                    break
                index += 1
            index += 1
        elif token.type == TokenType.STRING:
            node["value"] = decode_string_literal(token.value)
        elif token.type == TokenType.NUMBER:
            node["value"] = number_value(token.value)
        elif token.type in (TokenType.TRUE, TokenType.FALSE, TokenType.NULL):
            node["value"] = {TokenType.TRUE: True, TokenType.FALSE: False, TokenType.NULL: None}[token.type]
        return node

    tree = value()
    return {"ast": tree, "tokens": [{"type": t.type.name, "value": t.value,
                                    "line": t.line, "column": t.column} for t in tokens]}
