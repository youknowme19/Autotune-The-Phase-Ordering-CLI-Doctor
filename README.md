# Autotune — Phase-Ordering CLI Doctor

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![LLVM](https://img.shields.io/badge/LLVM-15%2B-orange.svg)](https://llvm.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey.svg)](docs/benchmarking.md)
[![CI/CD Pipeline](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/actions/workflows/ci.yml)

Autotune is an AI-guided compiler optimization system and phase-ordering doctor for C/C++ workloads. It discovers code-specific LLVM optimization pass sequences that outperform standard compiler optimization flags (such as `-O3`), verifies program correctness against trusted baselines under isolated execution, measures performance with empirical statistical hygiene, and generates reproducible compiler prescriptions.

---

## Overview and Background

### The Compiler Phase-Ordering Problem

Standard compiler optimization flags like `-O3` apply a fixed, general-purpose sequence of optimization passes to every source file regardless of its specific code structure.

However, compiler optimization passes interact dynamically:
- Running `licm` (Loop Invariant Code Motion) before `loop-unroll` can expose vectorization opportunities that standard `-O3` pipelines miss.
- Running `gvn` (Global Value Numbering) after `instcombine` can eliminate redundant memory loads in compute-dense inner loops.
- The selection, order, and repetition of passes (the compiler phase-ordering problem) creates a combinatorial search space where workload-specific pass pipelines can yield significant performance improvements over default compiler pipelines.

Autotune automates the discovery of optimal LLVM pass pipelines using Clang AST structural analysis, LLM pass proposal seeding, and Genetic Algorithm search, backed by strict sandboxed execution and correctness gating.

---

## Core Engineering Philosophy

> "Never recommend an optimization merely because an AI says it might be faster. Compile it, execute it, verify correctness, and measure it first."

Autotune enforces rigorous empirical validation:

1. Zero Hallucinated Passes: Proposed LLVM passes are validated against the local toolchain before compilation. Invalid pass names are filtered out automatically.
2. Strict Correctness First: Candidates that produce fast but incorrect output (diverging stdout, stderr, or exit code) are assigned infinite cost (`float('inf')`) and discarded.
3. Transparent Performance Metrics: On macOS, Autotune uses high-precision CPU monotonic timing with statistical noise and IQR calculations, explicitly signaling warning code `E-01` rather than outputting simulated cycle metrics.

---

## System Architecture

```text
               C/C++ Source Code
                      │
                      ▼
        [ AST & Feature Extractor ]  (Clang -ast-dump=json)
                      │
                      ▼ (Compact Structural JSON)
              [ LLM Client ]
                      │
                      ▼ (Proposed Pass Pipelines)
           [ LLVM Pass Validator ]  (Rejects Hallucinated Passes)
                      │
                      ▼
         [ Genetic Algorithm Engine ]  (Selection, Crossover, Mutators)
                      │
                      ▼
       [ 3-Step LLVM Compiler Driver ]
         1. clang -O0 -Xclang -disable-O0-optnone -emit-llvm -c source.c -o raw.bc
         2. opt -passes="pass1,pass2" raw.bc -o opt.bc
         3. clang -arch arm64 opt.bc -o candidate.bin
                      │
                      ▼ (Candidate Executable)
             [ Sandbox Executor ]
                      │
             ┌────────┴────────┐
             ▼                 ▼
   [Correctness Validator] [Performance Runner]
   (Must match -O3 output) (3 Warmups, Median & IQR Noise)
             │                 │
             └────────┬────────┘
                      ▼
        [ Reproducible Prescription & JSON Report ]
```

### Module Structure

```text
autotune/
├── src/autotune/
│   ├── analysis/      # C/C++ AST parser & compact JSON feature extraction
│   ├── doctor/        # System diagnostic checks & error codes (E-01 to E-05)
│   ├── llvm/          # Clang/Opt compiler driver, PassSequence, & validation
│   ├── benchmark/     # MacOS & Linux performance runners & correctness checking
│   ├── sandbox/       # Subprocess executor with process group isolation & timeouts
│   ├── llm/           # Provider-agnostic LLM interface & structured schema
│   ├── search/        # Genetic Algorithm engine, fitness ordering, & mutators
│   ├── reporting/     # Compiler prescription builder & JSON report exporter
│   ├── ui/            # Rich terminal dashboard formatting
│   └── cli.py         # Typer CLI application entry point
├── tests/
│   ├── unit/          # Tests for passes, GA, AST, LLM, correctness, & config
│   └── integration/   # Tests for compiler drivers & CLI commands
├── examples/          # Sample benchmark kernels (simple_loop, vector_sum, sha256, matrix_mult)
└── docs/              # Technical architecture & benchmarking specifications
```

---

## Key Features

- Environment and Toolchain Doctor (`autotune doctor`): Validates local Python 3.11+, Clang, LLVM `opt`, operating system, CPU architecture, and measurement capabilities.
- AST Feature Extraction: Parses C/C++ AST structure using `clang -Xclang -ast-dump=json` (loops, operations, array indexing, function calls) and extracts compact JSON summaries.
- LLM Pass Pipeline Seeding: Generates workload-tailored initial pass sequences using LLM intelligence, validated against local LLVM capabilities.
- Pass Validation Gate: Intercepts raw LLM proposals and filters out hallucinated pass names before seeding the GA population.
- Deterministic Genetic Algorithm Search: Mutates (insert, delete, swap) and crosses over (2-point crossover) pass pipelines with reproducible random seeding (`--seed 42`).
- Early Stopping and Stopping Criteria: Supports generation limits, fitness plateau detection (`max_stagnant_generations`), and search timeout limits.
- Isolated Sandbox Execution: Runs candidate binaries in isolated process groups (`start_new_session=True`) with strict timeouts and `SIGKILL` cleanup.
- Ground-Truth Correctness Validator: Compares candidate stdout, stderr, and exit codes against trusted `-O3` baseline runs to reject divergent outputs.
- Cross-Platform Performance Runners: Platform-specific backends (`MacOSPerformanceRunner` and `LinuxPerformanceRunner`) with 3 warmup runs and statistical sampling (median, stddev, IQR noise ratio).
- Reproducible Compiler Prescriptions: Generates exact, copy-pasteable `clang` and `opt` compilation commands for production integration.
- Structured JSON Report Exporter: Exports full execution metadata, doctor details, baseline performance metrics, and timing sample arrays.

---

## Installation

### Prerequisites

- macOS (Apple Silicon or Intel) or Linux
- Python 3.11+
- LLVM / Clang toolchain (`clang` and `opt`)

On macOS via Homebrew:
```bash
brew install llvm python@3.11
```

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor

# Create virtual environment and install autotune
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## CLI Usage and Commands

### 1. Toolchain Health Check (`autotune doctor`)

Inspects local compiler binaries, LLVM toolchain, and measurement capabilities:

```bash
autotune doctor
```

Output format:
```text
Autotune v0.1.0
Phase-Ordering CLI Doctor

                         System & Toolchain Diagnostics                         
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check Component     ┃ Status ┃ Details                                       ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Python Version      │ [OK]   │ 3.11.15                                       │
│ OS & Architecture   │ [OK]   │ Darwin (arm64 - Apple Silicon (ARM64))        │
│ Clang Compiler      │ [OK]   │ /usr/bin/clang (Apple clang version 21.0.0)   │
│ LLVM Opt Binary     │ [OK]   │ /opt/homebrew/opt/llvm/bin/opt (LLVM 22.1.8) │
│ Measurement Backend │ [OK]   │ macOS high-precision timing                   │
└─────────────────────┴────────┴───────────────────────────────────────────────┘

[WARN] E-01
Hardware performance counters are not available through the Linux backend on macOS.
Using macOS timing backend for development.
```

---

### 2. Baseline Performance Diagnosis (`autotune diagnose`)

Establishes `-O3` baseline performance, verifies execution correctness, and prepares the workload for search:

```bash
autotune diagnose ./examples/simple_loop/kernel.c \
    --workload ./examples/simple_loop/input.txt
```

Output format:
```text
Autotune v0.1.0
Phase-Ordering CLI Doctor

[OK] Source detected
[OK] Compiler detected
[OK] LLVM toolchain detected
[OK] Baseline compiled
[OK] Benchmark executed
[OK] Correctness verified

Baseline
────────────────────────
Compiler:     /usr/bin/clang
Optimization: -O3
Target:       arm64
Measurement:  macOS high-precision timing
Median Time:  3.312 ms (noise: 1.21%)

Result
────────────────────────
Status: READY FOR SEARCH
```

---

### 3. AI and Genetic Optimization Search (`autotune search`)

Runs the full AI-seeded Genetic Algorithm optimization loop over multiple generations with live terminal UI progress:

```bash
autotune search ./examples/simple_loop/kernel.c \
    --workload ./examples/simple_loop/input.txt \
    --generations 10 \
    --population 20 \
    --seed 42 \
    --output-json report.json
```

Output format:
```text
Starting optimization search on ./examples/simple_loop/kernel.c...

Optimization Search Complete!
Best Pass Sequence: ['mem2reg', 'sroa', 'early-cse', 'gvn', 'loop-vectorize', 'slp-vectorize']
Speedup: 1.28x (21.9% improvement over -O3)

Baseline (-O3):   3.667 ms
Candidate Best:   2.864 ms

Reproducible Compiler Command:
/usr/bin/clang -O0 -Xclang -disable-O0-optnone -emit-llvm -S ./examples/simple_loop/kernel.c -o - | /opt/homebrew/opt/llvm/bin/opt -passes='mem2reg,sroa,early-cse,gvn,loop-vectorize,slp-vectorize' -S -o - | /usr/bin/clang -x assembler - -o optimized_kernel.bin

Report exported to report.json
```

---

### 4. Direct Binary Benchmarking (`autotune benchmark`)

Measures an arbitrary executable binary directly across multiple iterations with warmup runs:

```bash
autotune benchmark ./path/to/binary --workload ./input.txt --repetitions 20
```

---

### 5. Candidate Correctness Validation (`autotune validate`)

Verifies output matching between a candidate binary and the C source `-O3` baseline:

```bash
autotune validate ./examples/simple_loop/kernel.c ./path/to/candidate.bin --workload ./examples/simple_loop/input.txt
```

---

## JSON Report Schema

When running `autotune search --output-json report.json`, Autotune exports a structured diagnostic document:

```json
{
  "timestamp": "2026-08-17T23:42:00.780202",
  "source_path": "./examples/sha256/kernel.c",
  "workload_path": "./examples/sha256/input.txt",
  "doctor_report": {
    "python_version": "3.11.15",
    "python_ok": true,
    "os_name": "Darwin",
    "arch": "arm64",
    "cpu_info": "Apple Silicon (ARM64)",
    "clang_path": "/usr/bin/clang",
    "opt_path": "/opt/homebrew/opt/llvm/bin/opt",
    "measurement_backend": "macOS high-precision timing"
  },
  "baseline_result": {
    "success": true,
    "metrics": {
      "median_time_ns": 3666500.0,
      "mean_time_ns": 3680041.6,
      "stddev_time_ns": 565337.45,
      "noise_ratio": 0.154,
      "iqr_time_ns": 772322.75,
      "iqr_noise_ratio": 0.210
    }
  },
  "prescription": {
    "pass_sequence": {
      "passes": ["mem2reg", "loop-reduce", "simplifycfg", "sccp", "dce", "memcpyopt", "gvn"]
    },
    "reproducible_clang_command": "/usr/bin/clang -O0 -Xclang -disable-O0-optnone -emit-llvm -S ./examples/sha256/kernel.c -o - | /opt/homebrew/opt/llvm/bin/opt -passes='mem2reg,loop-reduce,simplifycfg,sccp,dce,memcpyopt,gvn' -S -o - | /usr/bin/clang -x assembler - -o optimized_kernel.bin",
    "baseline_time_ms": 3.667,
    "candidate_time_ms": 4.67,
    "speedup_ratio": 0.79
  },
  "generations_searched": 5,
  "population_size": 10,
  "seed": 42
}
```

---

## Testing and Verification

Autotune includes a unit and integration test suite:

```bash
# Run all tests
pytest -v

# Run unit tests only
pytest -v tests/unit/

# Run integration tests only
pytest -v tests/integration/
```

---

## Platform Capabilities and Technical Notes

| Feature / Capability | macOS (Apple Silicon M4) | Linux (x86_64 / ARM64) |
| :--- | :--- | :--- |
| Compiler Driver | Apple Clang / Homebrew LLVM | Native Clang / LLVM |
| Measurement Backend | Monotonic CPU Timing (`time.perf_counter_ns`) | Linux Timing / `perf_event_open` |
| Diagnostic Code | Transparent Warning `E-01` | Native Linux Backend |
| Process Isolation | Process Group Sandbox (`start_new_session`) | Namespaces & Process Groups |
| Warmup Runs | 3 Warmup Iterations | 3 Warmup Iterations |
| Statistical Noise | Standard Deviation & IQR Noise | Standard Deviation & IQR Noise |

---

## License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
