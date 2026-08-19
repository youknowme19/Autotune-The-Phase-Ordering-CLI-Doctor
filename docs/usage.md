# Usage Workflows

This document outlines common execution workflows, tri-state execution modes, and batch suite benchmarking.

---

## 🔄 Tri-State Execution Modes

Autotune supports three distinct execution modes for candidate seed generation:

### 1. Auto-Detect Mode (Default)
```bash
autotune search ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt
```
Automatically checks OS Keychain or environment variables for API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`). If found, invokes LLM seeding; otherwise, gracefully falls back to offline AST heuristics.

### 2. Explicit AI Mode (`--llm`)
```bash
autotune search ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt --llm --llm-provider openai
```
Forces LLM proposal generation for Generation 0. Raises a clear CLI error if no valid API key is present in OS Keychain or environment.

### 3. Explicit Offline Mode (`--no-llm`)
```bash
autotune search ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt --no-llm -s 42
```
Runs 100% offline using deterministic AST heuristics and random seed 42. Makes zero network calls and guarantees 100% reproducible population initialization.

---

## 🏃 Multi-Worker Parallel Search (`--workers`)

Autotune supports multi-threaded parallel evaluation across CPU cores:

```bash
autotune search ./examples/matrix_transpose/kernel.c \
  -w ./examples/matrix_transpose/input.txt \
  --no-llm \
  -p 20 \
  -g 10 \
  -w 4 \
  -s 42
```

Parallel worker execution is protected by thread-safe disaggregated cache operations with atomic temporary file replacements (`tempfile.NamedTemporaryFile` + `os.fsync` + `os.replace`).

---

## 📊 Batch Suite Benchmarking (`autotune bench-suite`)

Run automated offline optimization across a directory containing multiple C benchmark kernels (e.g., PolyBench/C):

```bash
autotune bench-suite ./polybench/ \
    --no-llm \
    --population 10 \
    --generations 5 \
    --seed 42 \
    --workers 4 \
    --fresh-benchmark \
    --runs 20 \
    --warmup 5 \
    --output-report stress_test_report.json
```

### Result Categorization
Workloads are classified into:
- `SUCCESSFUL_SPEEDUP`: Verified correct and statistically faster than `-O3` ($p < 0.05$).
- `PARITY`: Correct execution with performance statistically indistinguishable from `-O3`.
- `STATISTICAL_REGRESSION`: Valid execution but statistically slower than `-O3`.
- `SILENT_MISCOMPILATION`: Program compiles and runs, but output diverges from baseline.
- `COMPILER_CRASH`: Compiler segfault or signal failure during compilation.
