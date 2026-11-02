import json
import pytest
from jsonlint_plus.ast import inspect
from jsonlint_plus.diagnostics import analyze
from jsonlint_plus.formatter import format_json
from jsonlint_plus.lexer import LexerError
from jsonlint_plus.parser import ParserError, parse


def test_large_document_parses_and_ast_keeps_all_entries():
    source = json.dumps({'items': [{'id': n, 'name': 'sample'} for n in range(12000)]})
    assert len(source) > 350000
    assert analyze(source)['diagnostics'] == []
    ast = inspect(source)['ast']
    assert len(ast['children'][0]['children'][0]['children']) == 12000


def test_format_preserves_lexemes_duplicate_keys_and_line_endings():
    source = '{"a":1e2,"a":[true,{"x":"\\u0041"}]}\n'
    formatted = format_json(source, '\t', '\r\n')
    assert formatted == '{\r\n\t"a": 1e2,\r\n\t"a": [\r\n\t\ttrue,\r\n\t\t{\r\n\t\t\t"x": "\\u0041"\r\n\t\t}\r\n\t]\r\n}\r\n'
    assert parse(formatted) == parse(source)
    assert format_json(formatted, '\t', '\r\n') == formatted


def test_formatter_empty_collections_and_invalid_source():
    assert format_json('{"a":[],"b":{}}') == '{\n  "a": [],\n  "b": {}\n}'
    with pytest.raises((LexerError, ParserError)):
        format_json('{"a":1,}')
