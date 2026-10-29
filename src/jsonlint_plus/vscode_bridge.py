"""Small stdin/stdout bridge used by the VS Code extension."""
import json
import sys

from jsonlint_plus.diagnostics import analyze


def main():
    request = json.load(sys.stdin)
    json.dump(analyze(request["text"]), sys.stdout, ensure_ascii=True)


if __name__ == "__main__":
    main()
