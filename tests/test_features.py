import json
import subprocess
import sys

from jsonlint_plus.ast import inspect
from jsonlint_plus.diagnostics import analyze
from jsonlint_plus.parser import parse
from jsonlint_plus.schema import validate


def test_recovery_reports_multiple_original_positions_and_independent_fixes():
    source = '{"a" 1, "b" 2}'
    items = analyze(source)['diagnostics']
    assert [item['column'] for item in items] == [6, 13]
    for item in reversed(items):
        fix = item['fix']
        source = source[:fix['start']] + fix['text'] + source[fix['end']:]
    assert parse(source) == {'a': 1, 'b': 2}


def test_lexical_recovery_and_safe_quote_fixes():
    source = "{'name': 'Ali'}"
    fixes = [item['fix'] for item in analyze(source)['diagnostics']]
    for fix in reversed(fixes):
        source = source[:fix['start']] + fix['text'] + source[fix['end']:]
    assert parse(source) == {'name': 'Ali'}
    assert analyze('{name: 1}')['diagnostics'][0]['fix']['text'] == '"name"'
    assert len(analyze('{"a": @, "b": @}')['diagnostics']) == 2


def test_ast_retains_nested_structure_and_positions():
    result = inspect('{"items": [true, 3]}')
    prop = result['ast']['children'][0]
    assert prop['key'] == 'items'
    assert prop['column'] == 2
    assert [node['type'] for node in prop['children'][0]['children']] == ['true', 'number']
    assert result['tokens'][-1]['type'] == 'EOF'


def test_schema_type_required_and_nested_locations():
    schema = {'type': 'object', 'required': ['name'], 'properties': {'age': {'type': 'integer'}}}
    diagnostics, error = validate('{\n "age": "young"\n}', schema)
    assert error is None
    assert len(diagnostics) == 2
    assert any(d['line'] == 2 and 'integer' in d['message'] for d in diagnostics)
    assert any('required' in d['message'] for d in diagnostics)


def test_invalid_schema_is_reported():
    diagnostics, error = validate('{}', {'type': 'not-a-type'})
    assert diagnostics == []
    assert 'JSON Schema validation failed' in error


def test_bridge_round_trip():
    request = {'text': '{"age": "x"}', 'schema': {'properties': {'age': {'type': 'integer'}}}}
    proc = subprocess.run([sys.executable, '-m', 'jsonlint_plus.vscode_bridge'], input=json.dumps(request), text=True, capture_output=True, check=True)
    result = json.loads(proc.stdout)
    assert result['ast']['type'] == 'object'
    assert result['tokens'][0]['type'] == 'LBRACE'
    assert 'integer' in result['diagnostics'][0]['message']
