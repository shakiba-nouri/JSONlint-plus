"""Small stdin/stdout bridge used by the VS Code extension."""
import json
import sys
from jsonlint_plus.ast import inspect
from jsonlint_plus.diagnostics import analyze
from jsonlint_plus.schema import validate


def main():
    request = json.load(sys.stdin)
    source = request['text']
    result = analyze(source)
    if not result['diagnostics']:
        result.update(inspect(source))
        if 'schema' in request:
            errors, schema_error = validate(source, request['schema'])
            result['diagnostics'].extend(errors)
            if schema_error:
                result['schemaError'] = schema_error
    json.dump(result, sys.stdout, ensure_ascii=True)


if __name__ == '__main__':
    main()
