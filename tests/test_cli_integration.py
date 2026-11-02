import subprocess
import sys


def run_cli(*args, stdin=None):
    return subprocess.run([sys.executable, '-m', 'jsonlint_plus', *args], input=stdin, text=True, capture_output=True)


def test_cli_valid_file_and_invalid_file(tmp_path):
    path = tmp_path / 'input.json'
    path.write_text('{"a": 1}', encoding='utf-8')
    result = run_cli(str(path))
    assert result.returncode == 0 and 'valid JSON' in result.stdout
    path.write_text('{"a": 1,}', encoding='utf-8')
    result = run_cli(str(path))
    assert result.returncode == 1 and 'Trailing comma' in result.stderr
    assert ':1:8:' in result.stderr and 'Suggestion:' in result.stderr


def test_cli_text_stdin_and_file_errors(tmp_path):
    assert run_cli('--text', '[true]').returncode == 0
    assert run_cli('-', stdin='[1 2]').returncode == 1
    assert run_cli(stdin='null').returncode == 0
    result = run_cli(str(tmp_path / 'missing.json'))
    assert result.returncode == 2 and result.stderr
    path = tmp_path / 'bad.json'
    path.write_bytes(b'\xff')
    assert run_cli(str(path)).returncode == 2
