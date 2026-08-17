# Autotune Development Guide

## Prerequisites

- macOS (Apple Silicon or Intel) or Linux
- Python 3.11+
- LLVM / Clang toolchain installed (`clang` and `opt`)

On macOS via Homebrew:
```bash
brew install llvm python@3.11
```

## Setup Environment

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

Run the full pytest suite:

```bash
pytest -v
```

Run unit tests only:

```bash
pytest -v tests/unit/
```

Run integration tests only:

```bash
pytest -v tests/integration/
```

## Code Quality Standards

- Maintain type hints across all Python functions.
- Keep dependencies minimal (Typer, Rich, Pydantic, Pytest).
- Do not create monolithic files; follow module separation under `src/autotune/`.
