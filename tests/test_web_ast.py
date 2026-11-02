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


def test_web_reports_suggested_fix_from_shared_diagnostics():
    source = '{"😀": 1,}'
    report = server.analyze(source)
    diagnostics = report['diagnostics']
    assert len(diagnostics) == 1
    fix = diagnostics[0]['fix']
    assert fix['title'] == 'Remove trailing comma'
    assert source[:fix['start']] + fix['text'] + source[fix['end']:] == '{"😀": 1}'
    assert next(stage for stage in report['stages'] if stage['id'] == 'repair')['suggestion_count'] == 1


def test_web_reports_no_fix_for_unsupported_error():
    report = server.analyze('{"x": @}')
    assert report['diagnostics']
    assert 'fix' not in report['diagnostics'][0]


def test_web_reports_multiple_suggestions():
    report = server.analyze('{"a" 1, "b" 2}')
    assert len(report['diagnostics']) == 2
    assert all(item['fix']['title'] == 'Insert missing colon' for item in report['diagnostics'])
