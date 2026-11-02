"""Local web server that runs the real JSONLint+ pipeline.

Run it with:

    python web/server.py

Then open http://127.0.0.1:8765/ in a browser. The page sends the JSON
you type to ``POST /api/analyze`` and receives a structured report of
every pipeline stage, so you can watch what JSONLint+ does to a file.

The pipeline is defined by ``PIPELINE`` below. Each stage is a small
function that reads from (and writes to) a shared ``context`` dict.
Add, remove, or reorder stages there to match how JSONLint+ evolves.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import platform
import sys
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

WEB_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WEB_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


# --------------------------------------------------------------------------
# Serialization helpers
# --------------------------------------------------------------------------

def to_jsonable(value: Any, depth: int = 0) -> Any:
    """Convert arbitrary parser output into JSON-serializable data."""
    if depth > 12:
        return repr(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, type):
        return value.__name__
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value), depth + 1)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v, depth + 1) for v in value]
    if hasattr(value, "name") and hasattr(value, "value") and type(value).__mro__[1].__name__ == "Enum":
        return value.name
    if hasattr(value, "__dict__"):
        return {
            k: to_jsonable(v, depth + 1)
            for k, v in vars(value).items()
            if not k.startswith("_")
        }
    return repr(value)


def error_info(exc: BaseException) -> dict[str, Any]:
    """Extract message/line/column from an exception when available."""
    info: dict[str, Any] = {"message": str(exc), "type": type(exc).__name__}
    for attr in ("line", "column"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            info[attr] = value
    return info


def import_optional(module_name: str) -> Any | None:
    """Import a module, returning None when it does not exist yet."""
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name or module_name.startswith(exc.name or ""):
            return None
        raise


# --------------------------------------------------------------------------
# Pipeline stages
# --------------------------------------------------------------------------

def run_lexer(context: dict[str, Any]) -> dict[str, Any]:
    """Tokenize the source with the real jsonlint_plus lexer."""
    source = context["source"]
    try:
        from jsonlint_plus.lexer import Lexer, LexerError
    except ModuleNotFoundError:
        return {"status": "missing", "message": "jsonlint_plus.lexer not found."}

    try:
        tokens = Lexer(source).tokenize()
    except LexerError as exc:
        return {"status": "error", "error": error_info(exc)}

    context["tokens"] = tokens
    rows = [
        {"type": token.type.name, "value": token.value, "line": token.line, "column": token.column}
        for token in tokens
    ]
    return {"status": "ok", "tokens": rows, "token_count": len(rows)}


def run_parser(context: dict[str, Any]) -> dict[str, Any]:
    """Run the parser stage when jsonlint_plus.parser exists."""
    module = import_optional("jsonlint_plus.parser")
    if module is None:
        return {
            "status": "missing",
            "message": "Add src/jsonlint_plus/parser.py to enable this stage.",
        }

    tokens = context.get("tokens")
    source = context["source"]

    if tokens is None:
        return {
            "status": "blocked",
            "message": "Lexer did not produce tokens, so parsing was skipped.",
        }

    for name in ("parse", "parse_source"):
        func = getattr(module, name, None)
        if callable(func):
            try:
                result = func(source)
            except Exception as exc:  # noqa: BLE001 - report any stage failure
                return {"status": "error", "error": error_info(exc)}
            from jsonlint_plus.ast import inspect

            ast = inspect(source)["ast"]
            context["parse_result"] = result
            return {"status": "ok", "result": to_jsonable(result), "ast": ast}

    parser_cls = getattr(module, "Parser", None)
    if parser_cls is not None:
        try:
            result = parser_cls(tokens).parse()
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": error_info(exc)}
        context["parse_result"] = result
        return {"status": "ok", "result": to_jsonable(result)}

    return {
        "status": "missing",
        "message": "jsonlint_plus.parser has no supported entry point "
        "(expected parse(), parse_source(), or Parser class).",
    }


def run_repair(context: dict[str, Any]) -> dict[str, Any]:
    """Report suggestions from the same diagnostic engine as the extension."""
    from jsonlint_plus.diagnostics import analyze as analyze_diagnostics

    items = analyze_diagnostics(context["source"])["diagnostics"]
    context["diagnostics"] = [
        {**item, "stage": "JSONLint+", "severity": "error", "type": "Syntax error"}
        for item in items
    ]
    return {"status": "ok", "suggestion_count": sum("fix" in item for item in items)}


PIPELINE: list[dict[str, Any]] = [
    {"id": "lexer", "name": "Lexer", "run": run_lexer},
    {"id": "parser", "name": "Parser & AST", "run": run_parser},
    {"id": "repair", "name": "Repair suggestions", "run": run_repair},
]


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

def collect_diagnostics(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn stage failures into a flat diagnostics list."""
    diagnostics: list[dict[str, Any]] = []
    for stage in stages:
        if stage.get("status") != "error":
            continue
        error = stage.get("error", {})
        diagnostics.append(
            {
                "stage": stage["name"],
                "severity": "error",
                "message": error.get("message", "Unknown error"),
                "type": error.get("type", "Error"),
                "line": error.get("line"),
                "column": error.get("column"),
            }
        )
    return diagnostics


def analyze(source: str) -> dict[str, Any]:
    """Run every pipeline stage over the source and return a full report."""
    context: dict[str, Any] = {"source": source}
    stages: list[dict[str, Any]] = []

    for spec in PIPELINE:
        started = time.perf_counter()
        try:
            outcome = spec["run"](context)
        except Exception as exc:  # noqa: BLE001 - never crash the endpoint
            outcome = {"status": "error", "error": error_info(exc)}
        outcome.setdefault("id", spec["id"])
        outcome.setdefault("name", spec["name"])
        outcome["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        stages.append(outcome)

    try:
        from jsonlint_plus import __version__ as package_version
    except ModuleNotFoundError:
        package_version = "not installed"

    return {
        "source": source,
        "python_version": platform.python_version(),
        "package_version": package_version,
        "stages": stages,
        "diagnostics": context.get("diagnostics", collect_diagnostics(stages)),
    }


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    """Serve the visualizer UI and the analysis endpoint."""

    server_version = "JSONLintPlusVisualizer/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[jsonlint-plus-web] " + fmt % args + "\n")

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404, "Not found")
            return
        content_type = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        route = self.path.split("?", 1)[0]
        if route in ("/", ""):
            self._send_file(WEB_DIR / "index.html")
            return
        candidate = (WEB_DIR / route.lstrip("/")).resolve()
        if WEB_DIR not in candidate.parents and candidate != WEB_DIR:
            self.send_error(403, "Forbidden")
            return
        self._send_file(candidate)

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        route = self.path.split("?", 1)[0]
        if route != "/api/analyze":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            self._send_json({"error": f"Invalid UTF-8: {exc}"}, status=400)
            return
        try:
            report = analyze(source)
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                {"error": str(exc), "traceback": traceback.format_exc()},
                status=500,
            )
            return
        self._send_json(report)


def main() -> int:
    """Parse arguments and serve the visualizer."""
    parser = argparse.ArgumentParser(description="JSONLint+ visual debugger server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser.")
    args = parser.parse_args()

    address = (args.host, args.port)
    httpd = ThreadingHTTPServer(address, Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"JSONLint+ visual debugger running at {url}")
    print("Press Ctrl+C to stop.")

    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
