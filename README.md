# Autotune — Phase-Ordering CLI Doctor

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PyPI Package](https://img.shields.io/badge/PyPI-autotune--doctor-blue.svg)](https://pypi.org/project/autotune-doctor/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![LLVM](https://img.shields.io/badge/LLVM-15%2B-orange.svg)](https://llvm.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey.svg)](docs/benchmarking.md)
[![CI/CD Pipeline](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/actions/workflows/ci.yml)

Autotune is an AI-guided compiler optimization system and phase-ordering doctor for C/C++ workloads. It discovers code-specific LLVM optimization pass sequences that outperform standard compiler optimization flags (such as `-O3`), verifies program correctness against trusted baselines under isolated execution, measures performance with empirical statistical hygiene, and generates reproducible compiler prescriptions.

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

---

## CLI Usage and Commands

### 1. Toolchain Health Check (`autotune doctor`)

Inspects local compiler binaries, LLVM toolchain, and measurement capabilities:

```bash
autotune doctor
```

---

### 2. Baseline Performance Diagnosis (`autotune diagnose`)

Establishes `-O3` baseline performance, verifies execution correctness, and prepares the workload for search:

```bash
autotune diagnose ./examples/simple_loop/kernel.c \
    --workload ./examples/simple_loop/input.txt
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
```

---

## License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
