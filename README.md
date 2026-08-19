# Autotune — Phase-Ordering CLI Doctor

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PyPI Package](https://img.shields.io/badge/PyPI-autotune--doctor-blue.svg)](https://pypi.org/project/autotune-doctor/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![LLVM](https://img.shields.io/badge/LLVM-15%2B-orange.svg)](https://llvm.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey.svg)](docs/benchmarking.md)

Autotune is an AI/GA-guided compiler optimization system and phase-ordering doctor for C/C++ workloads. It searches custom LLVM optimization pass sequences rather than replacing Clang's standard optimization pipeline universally. It verifies program correctness against trusted baselines under isolated sandbox execution, measures performance with statistical hygiene, and generates reproducible compiler prescriptions.

---

## Core Engineering Philosophy

> **"Autotune does not ask the AI whether an optimization is better. It experimentally proves it."**

The LLVM pass ordering search space is vast and dynamic. AI models (OpenAI, Anthropic, Gemini, or offline heuristics) act strictly as **guides and seed generators** for Generation 0 proposals. They **never** directly decide the winner. 

Every candidate pipeline must experimentally satisfy five strict criteria:
1. **Compiles Successfully**: Must pass Clang bitcode lowering, NPM pass transformation, and native assembly without compiler crashes.
2. **Terminates Within Hard Bounds**: Protected by strict `COMPILATION_TIMEOUT` limits.
3. **Produces Correct Output**: Verified against trusted `-O3` baseline output using pluggable `CorrectnessStrategy` validators (exact byte diffs, numeric tolerance $\epsilon = 10^{-6}$, SHA-256 digests, or custom scripts).
4. **Runs Within Runtime Limits**: Protected by process sandbox execution timeouts.
5. **Demonstrates Statistically Credible Improvement**: Compared against baseline `-O3` timing using repeated measurements, Welch's t-test ($p < 0.05$), Mann-Whitney U test, and bootstrap confidence intervals.

---

## Primary Empirical Results

### Validated Workload Speedup (`matrix_transpose`)
Autotune's primary validated result is a statistically robust workload-specific improvement on [`matrix_transpose`](file:///Volumes/SSD/autotune/examples/matrix_transpose/kernel.c):

| Protocol | Baseline `-O3` Median | Candidate Best Median | Confirmed Speedup | $p$-value | Bootstrap 95% CI | Classification |
|---|---|---|---|---|---|---|
| **Phase G Interleaved (N=100)** | **70.446 ms** | **55.858 ms** | **1.26x** (20.7% runtime reduction) | **$2.47 \times 10^{-33}$** | **$[1.25x, 1.32x]$** | **`REPRODUCED_SPEEDUP`** |

- **Winning Pipeline**: `function(gvn,mem2reg,invalidate<all>,gvn,gvn-hoist)`
- **Correctness**: $100\%$ Match (`Matrix Transpose Check B[256][256]: 1313.2899`)
- **Protocol**: 100 warmups, 100 baseline + 100 candidate fresh timing measurements with deterministic random interleaving (seed 42).

---

### PolyBench/C Generalization Evaluation & Regression Detection
On dense linear-algebra loop kernels from PolyBench/C, small-budget offline search ($P=10, G=5$, `--no-llm`) demonstrates honest performance regression detection:

| Benchmark Kernel | Baseline `-O3` | Autotune Candidate | Confirmed Speedup | Correctness Status | Scientific Classification |
|---|---|---|---|---|---|
| `matrix_transpose` | 70.45 ms | **55.86 ms** | **1.26x** | **PASS** | **`REPRODUCED_SPEEDUP`** |
| `2mm` | 22.41 ms | 86.92 ms | 0.26x | **PASS** | **`STATISTICAL_REGRESSION`** |
| `cholesky` | 5.19 ms | 9.95 ms | 0.52x | **PASS** | **`STATISTICAL_REGRESSION`** |
| `atax` | 3.49 ms | 5.84 ms | 0.60x | **PASS** | **`STATISTICAL_REGRESSION`** |
| `gemm` | 5.96 ms | 45.59 ms | 0.13x | **PASS** | **`STATISTICAL_REGRESSION`** |
| `bicg` | 3.02 ms | 3.93 ms | 0.77x | **PASS** | **`STATISTICAL_REGRESSION`** |

> **Scientific Finding**: Autotune demonstrates that automated phase-order search can discover statistically robust workload-specific improvements beyond `-O3`, but the current evidence does not establish universal optimization superiority or broad cross-workload generalization.

---

## Installation Methods

### Method 1: PyPI Package
```bash
pip install autotune-doctor
```

---

### Method 2: From Source
```bash
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor

python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## System Architecture

```text
               C/C++ Source Code
                      │
                      ▼
        [ AST & Feature Extractor ]  (Clang -ast-dump=json)
                      │
                      ▼ (Compact Structural JSON)
          [ LLM / Heuristic Client ] (OpenAI / Anthropic / Gemini / Offline AST)
                      │
                      ▼ (Proposed Pass Pipelines)
           [ LLVM Pass Validator ]  (Rejects Hallucinated Passes & Normalizes NPM)
                      │
                      ▼
          [ Genetic Algorithm Engine ]  (Selection, Crossover, Mutators, Cache)
                      │
                      ▼
        [ 3-Step LLVM Compiler Driver ]
          1. clang -O0 -Xclang -disable-O0-optnone -emit-llvm -c source.c -o raw.bc
          2. opt -passes="function(...),loop-mssa(licm)" raw.bc -o opt.bc
          3. clang opt.bc -o candidate.bin
                      │
                      ▼ (Candidate Executable)
              [ Sandbox Executor ]
                      │
              ┌────────┴────────┐
              ▼                 ▼
    [Correctness Validator] [In-Process Performance Runner]
    (Byte Diff / Numeric)   (__AUTOTUNE_TIME_NS__ Monotonic Timing)
              │                 │
              └────────┬────────┘
                       ▼
    [ Experiment Manifest & Reproducible Prescription ]
```

---

## Execution Modes (`autotune search`)

- **Auto-Detect Mode (Default: `autotune search kernel.c`)**: Uses LLM if an API key is detected; otherwise, falls back to offline heuristic search.
- **Explicit AI Mode (`autotune search kernel.c --llm`)**: Forces LLM proposal generation.
- **Explicit Offline Mode (`autotune search kernel.c --no-llm`)**: Runs 100% offline using deterministic AST heuristics and `--seed 42`.

---

## Testing and Verification

Autotune maintains a 100% clean test suite across unit and integration tests:

```bash
# Run complete pytest test suite (51/51 passed)
.venv/bin/pytest -v
```

---

## License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
