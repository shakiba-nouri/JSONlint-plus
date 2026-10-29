import pytest
from jsonlint_plus.diagnostics import analyze
from jsonlint_plus.parser import parse


@pytest.mark.parametrize("source", ['{"a": 1,}', '[1,]', '{"a" 1}', '[1 2]', '{"a": 1', '[1', '"hello'])
def test_suggested_fixes_produce_valid_json(source):
    diagnostic = analyze(source)["diagnostics"][0]
    fix = diagnostic["fix"]
    parse(source[:fix["start"]] + fix["text"] + source[fix["end"]:])


def test_valid_document_and_unfixable_error():
    assert analyze('{"ok": true}') == {"diagnostics": []}
    assert "fix" not in analyze('{"a": @}')['diagnostics'][0]


def test_unicode_offsets_and_location():
    diagnostic = analyze('{"😀": 1,}')['diagnostics'][0]
    assert diagnostic['column'] == 8
    assert diagnostic['fix']['start'] == 7
