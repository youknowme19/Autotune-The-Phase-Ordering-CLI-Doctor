# Autotune Architecture Specification

Autotune is designed around modular, loosely coupled components to ensure testability, safety, and cross-platform performance measurement.

## System Topology

```text
autotune/
├── src/autotune/
│   ├── analysis/     # C/C++ source structural inspection and feature JSON extraction
│   ├── benchmark/    # Hardware and timing performance runners & correctness checking
│   ├── doctor/       # Toolchain detection and diagnostic error reporting
│   ├── llm/          # Provider-agnostic LLM interface & prompt/schema management
│   ├── llvm/         # Clang/Opt driver, pass validation, and pipeline builders
│   ├── reporting/    # Compiler prescription and diagnostic report generator
│   ├── sandbox/      # Subprocess execution sandbox with timeout management
│   ├── search/       # Genetic Algorithm engine, fitness ordering, mutation operators
│   └── ui/           # Rich terminal dashboard formatting
```

## Key Workflows

### 1. Diagnosis Flow (`autotune diagnose`)

1. **Environment Check**: Runs diagnostic checks for `clang`, `opt`, and measurement backends.
2. **Baseline Compilation**: Compiles baseline binary with `-O3`.
3. **Execution & Correctness Baseline**: Runs binary in sandbox with workload input to record ground-truth output.
4. **Performance Measurement**: Measures baseline execution time/cycles across repetitions, reporting median and noise metrics.

### 2. Search Flow (`autotune search`)

1. **Feature Extraction**: Extract loop counts, array indexing, arithmetic density.
2. **LLM Seeding**: Request initial pass pipelines from LLM based on compact feature summary.
3. **Pass Validation**: Filter proposed passes through `PassValidator` to reject invalid or hallucinated LLVM passes.
4. **GA Evolution**: Seed population, perform selection, two-point crossover, and mutation (insert, delete, swap).
5. **Fitness Evaluation**:
   - Compilation failure $\rightarrow$ Worst score
   - Correctness divergence $\rightarrow$ Worst score
   - Valid candidate $\rightarrow$ Benchmark score (lower cost is better)
6. **Prescription Output**: Generate reproducible `clang` command with phase-ordering pass flags.
