# JSONLint+

A VS Code extension for validating strict JSON using a custom Python lexer and recursive-descent parser. Errors appear in the editor and Problems panel as you type. Quick Fix (`Ctrl+.` / `Cmd+.`) offers a repair when a single safe edit makes the document valid, including common missing commas or colons, trailing commas, and some missing closing characters.

## Requirements

- VS Code 1.85 or newer
- Python 3.11 or newer available on PATH. If needed, set `jsonlintPlus.pythonPath` in VS Code settings to the Python executable.

## Run the extension

1. Open this project folder in VS Code.
2. Press `F5` to launch an Extension Development Host.
3. Open a `.json` file in the new window. Errors are underlined; place the cursor on one and use Quick Fix.

The extension analyzes unsaved changes as well as saved files. It reports the first syntax error, so fix it to reveal any later errors. Suggestions are shown only if the resulting document parses successfully. VS Code's built-in JSON validation may also report diagnostics; disable `json.validate.enable` if you prefer only JSONLint+ diagnostics. JSON with comments (JSONC) is not supported.

To package for installation, run `npx @vscode/vsce package`, then use **Extensions: Install from VSIX** in VS Code. Python must also be installed on the target machine. The extension bundles the Python source; installing the Python package separately is not required.

## Development

Create a virtual environment and install the project and test dependencies:

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
```

The grammar is documented in `docs/grammar.ebnf`. The Python CLI currently supports `--help` and `--version`.
