# Development Guide

This guide covers setting up the development environment, code style guidelines, repository layout, and CI/CD pipelines.

---

## 💻 Environment Setup

Clone the repository and install development dependencies:

```bash
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor

python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Dev dependencies (`pyproject.toml`):
- `pytest`, `pytest-cov` (Test suite & coverage)
- `black`, `isort`, `flake8` (Code formatting & linting)
- `mypy` (Static type checking)

---

## 📁 Repository Layout

```text
autotune/
├── src/autotune/
│   ├── analysis/       # AST & feature extraction (features.py)
│   ├── benchmark/      # Timing backends, models, correctness (macos.py, correctness.py)
│   ├── doctor/         # Diagnostic checks (checks.py, errors.py)
│   ├── llm/            # LLM client & schema prompts (client.py, models.py)
│   ├── llvm/           # Pass validation, compiler driver (passes.py, compiler.py)
│   ├── reporting/      # Manifest & report exporters (manifest.py, report.py)
│   ├── sandbox/        # Process execution sandbox (executor.py)
│   ├── search/         # GA engine, persistent cache, fitness, seeds (genetic.py, cache.py)
│   ├── stress/         # Batch suite orchestrator (orchestrator.py)
│   ├── ui/             # Terminal dashboards & formatting (terminal.py)
│   ├── cli.py          # Typer CLI application entry point
│   └── config.py       # Credential store & settings
├── tests/
│   ├── unit/           # Unit test modules (47 tests)
│   └── integration/    # Integration test modules (4 tests)
├── examples/           # Target example workloads (matrix_transpose, simple_loop)
├── polybench/          # PolyBench/C benchmark suite kernels
├── docs/               # Technical documentation library
└── pyproject.toml      # Build metadata & dependency definitions
```

---

## 🎨 Code Style & Standards

- **Formatting**: Format code using `black` and `isort`:
  ```bash
  black src/ tests/
  isort src/ tests/
  ```
- **Type Annotations**: Enforce type annotations on all public functions and classes (`mypy src/`).
- **Docstrings**: Include Google-style docstrings for module exports and classes.
