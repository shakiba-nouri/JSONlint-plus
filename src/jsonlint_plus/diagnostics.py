"""JSON diagnostics and conservative, validated single-edit repairs."""
from __future__ import annotations

from jsonlint_plus.lexer import LexerError
from jsonlint_plus.parser import ParserError, parse


def analyze(source: str) -> dict:
    try:
        parse(source)
        return {"diagnostics": []}
    except (LexerError, ParserError) as error:
        lines = source.splitlines(keepends=True)
        offset = sum(len(line) for line in lines[:error.line - 1]) + error.column - 1
        offset = min(offset, len(source))
        diagnostic = {"message": error.message, "line": error.line, "column": error.column}
        candidates = []
        if error.message.startswith("Trailing comma"):
            candidates.append((offset, offset + 1, "", "Remove trailing comma"))
        elif error.message == "Expected ':' after object key":
            candidates.append((offset, offset, ": ", "Insert missing colon"))
        elif error.message in ("Expected '}' to close object", "Expected ']' to close array"):
            closing = "}" if "'}'" in error.message else "]"
            if offset == len(source):
                candidates.append((offset, offset, closing, f"Insert missing {closing}"))
            else:
                candidates.append((offset, offset, ", ", "Insert missing comma"))
        elif error.message == "Unterminated string" and "\n" not in source[offset:]:
            candidates.append((len(source), len(source), '"', "Close string"))
        for start, end, replacement, title in candidates:
            try:
                parse(source[:start] + replacement + source[end:])
            except (LexerError, ParserError):
                continue
            diagnostic["fix"] = {"start": start, "end": end, "text": replacement, "title": title}
            break
        return {"diagnostics": [diagnostic]}
