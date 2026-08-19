# Testing Guide

Autotune maintains a 100% clean test suite covering unit and integration test modules.

---

## 🧪 Running the Test Suite

Execute pytest in the virtual environment:

```bash
source .venv/bin/activate
.venv/bin/pytest -v
```

Expected output:
```text
============================== 51 passed in 2.28s ==============================
```

---

## 📂 Test Organization

Tests are located under `tests/`:

### Unit Tests (`tests/unit/`)
- `test_ast.py`: Clang AST feature extraction tests.
- `test_passes.py`: LLVM NPM pass string parsing and normalizer tests.
- `test_genetic.py`: Genetic algorithm operators (selection, crossover, mutation, elitism).
- `test_persistent_cache.py`: Cache key disaggregation, atomic storage, and corruption recovery tests.
- `test_correctness.py`: Output diff matching, numeric tolerance, and failure rejection tests.
- `test_hardened_features.py`: Baseline-normalized fitness, seed archive manager, and multi-fidelity screening tests.
- `test_llm.py`: LLM schema models, mock generation, and pass validator gate tests.
- `test_config.py`: Environment variable and keyring credential resolution tests.
- `test_bench_suite.py`: Batch stress suite orchestrator tests.

### Integration Tests (`tests/integration/`)
- `test_cache_end_to_end.py`: End-to-end multi-layer cache run test (Run A misses, Run B compilation hits, Run C fresh timing).
- `test_compiler.py`: Compiler driver bitcode lowering and candidate compilation tests.
- `test_cli.py`: Typer CLI `doctor` and `diagnose` command tests.

---

## ✍️ Writing New Tests

When adding features or pass transformations:
1. Add corresponding unit tests in `tests/unit/`.
2. Verify all mock execution objects supply valid `metadata` (`BenchmarkEnvironmentMetadata`).
3. Ensure no external network calls or non-deterministic file paths are introduced.
