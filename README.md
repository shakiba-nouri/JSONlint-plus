# JSONLint+

A command-line tool for JSON syntax analysis and repair suggestions,
built with Python.

## Features

- Custom lexical analyzer (Lexer)
- Custom recursive-descent parser
- Abstract Syntax Tree (AST)
- Syntax diagnostics with line and column information
- Controlled error recovery
- User-confirmed repair suggestions
- Simple schema validation
- Selected version compatibility checks

## Requirements

Python 3.11 or newer.

## Installation

Create and activate a virtual environment, then run:

    python -m pip install -e ".[dev]"

## Usage

Show help:

    jsonlint-plus --help

Show version:

    jsonlint-plus --version

Run tests:

    python -m pytest -q

## Project Status

Day 1: Project setup and grammar definition.