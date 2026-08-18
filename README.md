# Autotune — Phase-Ordering CLI Doctor

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PyPI Package](https://img.shields.io/badge/PyPI-autotune--doctor-blue.svg)](https://pypi.org/project/autotune-doctor/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![LLVM](https://img.shields.io/badge/LLVM-15%2B-orange.svg)](https://llvm.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey.svg)](docs/benchmarking.md)
[![CI/CD Pipeline](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/actions/workflows/ci.yml)

Autotune is an AI-guided compiler optimization system and phase-ordering doctor for C/C++ workloads. It discovers code-specific LLVM optimization pass sequences that outperform standard compiler optimization flags (such as `-O3`), verifies program correctness against trusted baselines under isolated execution, measures performance with empirical statistical hygiene, and generates reproducible compiler prescriptions.

---

## Core Engineering Philosophy

> **"Autotune does not ask the AI whether an optimization is better. It experimentally proves it."**

The LLVM pass ordering search space is vast and dynamic. AI models (OpenAI, Anthropic, Gemini, or offline heuristics) act strictly as **guides and seed generators** for Generation 0 proposals. They **never** directly decide the winner. 

Every candidate pipeline must experimentally satisfy five strict criteria:
1. **Compiles Successfully**: Must pass Clang bitcode lowering, NPM pass transformation, and native assembly without compiler crashes.
2. **Terminates Within Hard Bounds**: Protected by strict `COMPILATION_TIMEOUT` limits.
3. **Produces Correct Output**: Verified against trusted `-O3` baseline output using pluggable `CorrectnessStrategy` validators (exact byte diffs, numeric tolerance $\epsilon = 10^{-6}$, SHA-256 digests, or custom scripts).
4. **Runs Within Runtime Limits**: Protected by process sandbox execution timeouts.
5. **Demonstrates Statistically Credible Improvement**: Compared against baseline `-O3` timing using repeated measurements and Welch's t-test hypothesis testing ($p < 0.05$).

---

## Installation Methods

### Method 1: PyPI Package (Universal Python Installation)

Install via `pip`, `uv`, or `pipx`:

```bash
pip install autotune-doctor

# Or isolated via uv tool / pipx
uv tool install autotune-doctor
# or
pipx install autotune-doctor
```

---

### Method 2: Standalone Executable Binary (No Python Required)

Download pre-compiled zero-dependency binaries directly from GitHub Releases:

#### macOS Apple Silicon (ARM64)
```bash
curl -LO https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/releases/download/v0.1.0/autotune-macos-arm64
chmod +x autotune-macos-arm64
sudo mv autotune-macos-arm64 /usr/local/bin/autotune
```

#### Linux (x86_64)
```bash
curl -LO https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/releases/download/v0.1.0/autotune-linux-x86_64
chmod +x autotune-linux-x86_64
sudo mv autotune-linux-x86_64 /usr/local/bin/autotune
```

---

### Method 3: From Source

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

## Secure Credential Management & Tri-State Execution Modes

Autotune supports secure API key storage in OS Keychain (macOS Keychain / Linux SecretService) and three execution modes:

### 1. Interactive Keyring Configuration (`autotune config`)

Securely store API keys into OS Keychain without ever writing secrets to disk or environment variables:

```bash
autotune config --provider openai
```

### 2. Tri-State Execution Modes (`autotune search`)

- **Auto-Detect Mode (Default: `autotune search kernel.c`)**:
  Automatically uses LLM if an API key is detected in the environment or OS Keychain; otherwise, falls back to offline heuristic search with an informational prompt.

- **Explicit AI Mode (`autotune search kernel.c --llm`)**:
  Forces LLM proposal generation. Raises a clear CLI error if no API key is found.

- **Explicit Offline Mode (`autotune search kernel.c --no-llm`)**:
  Runs 100% offline using deterministic AST heuristics. Ignores environment keys, makes zero network calls, and is fully reproducible when supplied with `--seed 42`.

---

## PolyBench/C Stress Testing & Batch Suites

Autotune includes a stress testing orchestrator to run offline GA optimization across standard C benchmark suites (PolyBench/C).

### Fetch PolyBench/C Suite
```bash
./scripts/fetch_polybench.sh
```

### Run Batch Suite Optimization
```bash
autotune bench-suite ./polybench/ \
    --no-llm \
    --population 20 \
    --generations 10 \
    --seed 42 \
    --workers 4 \
    --output-report stress_test_report.json
```

### Failure Category Classification
Workloads and candidates are strictly categorized into:
- `SUCCESSFUL_SPEEDUP`: Verified correct and statistically faster than `-O3` ($p < 0.05$).
- `PARITY`: Correct execution with performance statistically indistinguishable from `-O3`.
- `STATISTICAL_REGRESSION`: Valid execution but statistically slower than `-O3`.
- `COMPILER_CRASH`: Compiler segfault or signal failure during compilation.
- `COMPILATION_TIMEOUT`: `opt` or `clang` execution exceeded strict timeouts.
- `SILENT_MISCOMPILATION`: Program compiles and runs, but output diverges from baseline.
- `RUNTIME_TIMEOUT`: Binary execution exceeded runtime sandbox limits.

---

## Empirical Benchmark Leaderboard

| Benchmark Kernel | Baseline `-O3` | Autotune Best | Speedup | Statistical Significance | Winning Pipeline |
|---|---|---|---|---|---|
| `matrix_transpose` | 74.80 ms | **58.18 ms** | **1.29x** | $p < 0.001$ | `reassociate,inline,mem2reg,instcombine,loop-simplify,indvars` |
| `2mm` | 31.16 ms | 31.20 ms | 1.00x | Parity | `mem2reg,sroa,loop-rotate,instcombine` |
| `cholesky` | 12.45 ms | 12.48 ms | 1.00x | Parity | `mem2reg,gvn,sroa` |
| `atax` | 8.92 ms | 8.95 ms | 1.00x | Parity | `mem2reg,instcombine,dce` |

---

## JSON Stress Test Report Schema

When running `autotune bench-suite`, Autotune exports structured diagnostic reports:

```json
{
  "timestamp": "2026-08-18T23:09:14.114910",
  "total_workloads": 1,
  "successful_speedups": 1,
  "statistical_regressions": 0,
  "compiler_crashes": 0,
  "infinite_compile_timeouts": 0,
  "silent_miscompilations": 0,
  "runtime_timeouts": 0,
  "parities": 0,
  "overall_suite_speedup": 1.29,
  "results": [
    {
      "kernel_name": "matrix_transpose",
      "source_path": ".../examples/matrix_transpose/kernel.c",
      "workload_path": ".../examples/matrix_transpose/input.txt",
      "category": "SUCCESSFUL_SPEEDUP",
      "baseline_time_ms": 74.795,
      "best_candidate_time_ms": 58.178,
      "speedup_ratio": 1.29,
      "p_value": 0.0,
      "winning_passes": ["reassociate", "inline", "mem2reg", "instcombine", "loop-simplify", "indvars"],
      "miscompilation_count": 0,
      "crash_count": 0,
      "timeout_count": 0
    }
  ]
}
```

---

## Testing and Verification

Autotune maintains a 100% clean test suite across unit and integration tests:

```bash
# Run complete pytest test suite
.venv/bin/pytest -v
```

---

## License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
