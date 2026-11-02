"""The browser report includes the actual AST for valid source only."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('web_server', Path(__file__).resolve().parents[1] / 'web' / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def test_web_report_includes_actual_nested_ast_and_duplicate_keys():
    report = server.analyze('{"a": [1, true], "a": null}')
    parser = next(stage for stage in report['stages'] if stage['id'] == 'parser')
    assert parser['status'] == 'ok'
    tree = parser['ast']
    assert tree['type'] == 'object'
    assert [child['key'] for child in tree['children']] == ['a', 'a']
    assert [node['type'] for node in tree['children'][0]['children'][0]['children']] == ['number', 'true']


def test_web_invalid_json_has_no_ast():
    report = server.analyze('{"a": [1,]}')
    parser = next(stage for stage in report['stages'] if stage['id'] == 'parser')
    assert parser['status'] == 'error'
    assert 'ast' not in parser
