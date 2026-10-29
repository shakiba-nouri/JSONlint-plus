"""Diagnostics, bounded error recovery and conservative repair suggestions."""
from __future__ import annotations

import json
import re
from jsonlint_plus.lexer import LexerError
from jsonlint_plus.parser import ParserError, parse


def _error(source):
    try:
        parse(source)
        return None
    except (LexerError, ParserError) as error:
        return error


def _offset(source, error):
    lines = source.splitlines(keepends=True)
    return min(sum(len(line) for line in lines[:error.line - 1]) + error.column - 1, len(source))


def _candidate(source, error, offset):
    message = error.message
    if message.startswith('Trailing comma'):
        return offset, offset + 1, '', 'Remove trailing comma'
    if message == "Expected ':' after object key":
        return offset, offset, ': ', 'Insert missing colon'
    if message in ("Expected '}' to close object", "Expected ']' to close array"):
        closing = '}' if "'}'" in message else ']'
        return (offset, offset, closing, f'Insert missing {closing}') if offset == len(source) else (offset, offset, ', ', 'Insert missing comma')
    if message == 'Unterminated string' and '\n' not in source[offset:]:
        return len(source), len(source), '"', 'Close string'
    if message.startswith('Unexpected identifier:'):
        match = re.match(r'[A-Za-z_][A-Za-z_0-9]*', source[offset:])
        if match and re.match(r'\s*:', source[offset + len(match.group()):]):
            word = match.group()
            return offset, offset + len(word), json.dumps(word), 'Quote object key'
    if source[offset:offset + 1] == "'":
        match = re.match(r"'([^'\\\r\n]*)'", source[offset:])
        if match:
            return offset, offset + len(match.group()), json.dumps(match.group(1), ensure_ascii=False), 'Use double quotes'
    return None


def analyze(source: str) -> dict:
    # Work on a temporary copy; the position map always points into the original.
    working = source
    positions = list(range(len(source) + 1))
    diagnostics = []
    seen = set()
    for _ in range(30):
        error = _error(working)
        if error is None:
            break
        pos = _offset(working, error)
        original_pos = positions[pos]
        signature = (original_pos, error.message)
        if signature in seen:
            break
        seen.add(signature)
        line = source.count('\n', 0, original_pos) + 1
        last_newline = source.rfind('\n', 0, original_pos)
        column = original_pos - last_newline
        message = error.message
        if message == 'Expected a string key in object' or (message.startswith('Unexpected identifier:') and re.match(r'[A-Za-z_][A-Za-z_0-9]*\s*:', working[pos:])):
            message += '. Object keys must use double quotes, for example "name".'
        elif message == "Expected ':' after object key":
            message += '. Add a colon between the key and its value, for example "name": "Ali".'
        elif message.startswith('Trailing comma'):
            message += '. Remove the comma before the closing bracket.'
        elif message.startswith('Expected a value'):
            message += '. Use a string, number, object, array, true, false, or null.'
        elif message in ("Expected '}' to close object", "Expected ']' to close array"):
            message += '. Check for a missing comma or closing bracket.'
        candidate = _candidate(working, error, pos)
        diagnostic = {'message': message, 'line': line, 'column': column}
        if candidate:
            start, end, replacement, title = candidate
            changed = working[:start] + replacement + working[end:]
            next_error = _error(changed)
            # Recovery must progress beyond this error; no edit is applied automatically.
            if next_error is None or _offset(changed, next_error) >= start + len(replacement):
                original_start, original_end = positions[start], positions[end]
                diagnostic['fix'] = {'start': original_start, 'end': original_end, 'text': replacement, 'title': title}
                diagnostics.append(diagnostic)
                positions = positions[:start] + [original_start] * len(replacement) + positions[end:]
                working = changed
                continue
        diagnostics.append(diagnostic)
        # Synchronize at a structural delimiter while preserving original offsets.
        # Do not invent a fix for unrecognized input.
        if pos >= len(working):
            break
        next_delimiter = re.search(r'[,\]}]', working[pos + 1:])
        if not next_delimiter:
            break
        stop = pos + 1 + next_delimiter.start()
        working = working[:pos] + 'null' + working[stop:]
        positions = positions[:pos] + [original_pos] * 4 + positions[stop:]
    return {'diagnostics': diagnostics}
