# JSONLint+

A VS Code extension that checks strict JSON with a custom Python lexer and recursive-descent parser. It reports syntax errors while you edit and offers Quick Fixes for common mistakes. It can also display tokens and an abstract syntax tree (AST), validate against a local JSON Schema, and format valid JSON.

## Requirements

- VS Code 1.85 or newer.
- Python 3.11 or newer on PATH. If necessary, set `jsonlintPlus.pythonPath` to the Python executable.
- For schema validation only, install `jsonschema` into that same Python environment: `python -m pip install "jsonschema>=4.18,<5"`. Syntax validation, Quick Fixes, tokens, and AST do not require it.

## Run and use

1. Open this folder in VS Code and press `F5` to launch an Extension Development Host.
2. Open a `.json` file. Errors are underlined and appear in Problems. Place the cursor on a diagnostic and press `Ctrl+.` (`Cmd+.` on macOS) to see available Quick Fixes.
3. Run **JSONLint+: Show Tokens** or **JSONLint+: Show AST** from the Command Palette. These commands show the latest analysis in a document beside the source. Fix syntax errors before inspecting the AST and tokens.

Recovery attempts to report multiple syntax errors by analyzing a temporary copy. Recovery is bounded and best effort: a malformed section may prevent later errors from being discovered or lead to follow-on diagnostics. Suggested edits are never applied automatically. Fixes include missing commas or colons, trailing commas, unquoted keys, and simple single-quoted strings. A fix may resolve one error while other errors remain.

The extension analyzes unsaved changes. VS Code's built-in JSON validation may also report diagnostics; disable `json.validate.enable` if you prefer only JSONLint+ diagnostics. JSON with comments (JSONC) is not supported.

## Command line

After `python -m pip install -e .`, validate a file, direct text, or stdin:

```sh
jsonlint-plus examples/valid.json
jsonlint-plus --text '{"name": "Ali"}'
cat examples/valid.json | jsonlint-plus -
```

Exit status is `0` for valid JSON, `1` for syntax errors, and `2` for a file, decoding, or other input error. Syntax diagnostics go to stderr and can include repair suggestions. A path containing spaces should be quoted. On PowerShell, single quotes around the JSON text avoid escaping double quotes.

## Formatting

Run **Format Document With...** and select **JSONLint+**. Set it as the default JSON formatter if desired. The formatter uses the editor's indentation and line endings, preserves token spelling and duplicate keys, and refuses to change invalid JSON.

## Architecture

1. The VS Code extension sends the current unsaved text to `vscode_bridge.py` through stdin; the CLI passes input to the same diagnostic engine.
2. `lexer.py` reads characters into typed tokens with line and column positions. `parser.py` checks those tokens using recursive descent and `docs/grammar.ebnf`.
3. `diagnostics.py` converts errors into editor diagnostics and attempts bounded recovery on a temporary copy. A suggested edit is applied only when the user chooses it.
4. For valid text, `ast.py` builds the AST and token views. If configured, `schema.py` uses `jsonschema` to check values against a local JSON Schema.
5. `formatter.py` validates input and adds whitespace around the original token spellings. The extension returns the result as a VS Code formatting edit.

## JSON Schema

Set `jsonlintPlus.schemaPath` to an absolute path or a path relative to the JSON file's workspace folder, for example `examples/person.schema.json`. The selected schema applies to JSON documents in that workspace. Leave it empty to disable schema validation. Syntax must be valid before schema validation runs. Schema diagnostics point to the relevant value or containing object; library installation, invalid schema and reference errors are reported separately.

The schema's `$schema` selects a supported draft, defaulting to the installed library's default draft. Internal `$ref` references work. External file and network references are not retrieved. Save or change the JSON document after modifying its schema to trigger validation again.

For example, this workspace setting enables the included sample:

```json
{ "jsonlintPlus.schemaPath": "examples/person.schema.json" }
```

## Installation and development

To package for installation, run `npx @vscode/vsce package` and use **Extensions: Install from VSIX**. The package includes the Python source, but the target computer needs Python and, for schema validation, `jsonschema` separately.

For development:

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
```

The grammar is in `docs/grammar.ebnf`. `tests/vscode-runner.cjs` exercises the extension inside a VS Code Extension Development Host. The test suite includes a roughly 385 KB document, but no general performance guarantee is made.
