# Autotune — Phase-Ordering CLI Doctor

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![LLVM](https://img.shields.io/badge/LLVM-15%2B-orange.svg)](https://llvm.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey.svg)](docs/benchmarking.md)
[![CI/CD Pipeline](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/actions/workflows/ci.yml)

**Autotune** is an AI-guided compiler optimization and phase-ordering doctor for C/C++ workloads. It discovers code-specific LLVM optimization pass sequences that outperform standard compiler optimization pipelines (such as `-O3`), verifies program correctness against trusted baselines under isolated execution, measures performance with empirical statistical hygiene, and generates reproducible compiler prescriptions.

---

## 💡 The Problem: Compiler Phase Ordering

Standard compiler optimization flags like `-O3` apply a fixed, fixed-order sequence of generic optimization passes to every function regardless of its unique structure.

However, compiler passes interact dynamically:
- Running `licm` (Loop Invariant Code Motion) before `loop-unroll` can unlock vectorization opportunities that `-O3` misses.
- Running `gvn` (Global Value Numbering) after `instcombine` might eliminate redundant memory loads in compute-heavy kernels.
- The order and choice of passes (the **phase-ordering problem**) creates a massive search space where code-specific pass pipelines can achieve **15% to 40%+ performance gains** over standard `-O3`.

**Autotune** automates the discovery of these optimal pass pipelines using LLM structural analysis and Genetic Algorithms without sacrificing program correctness or relying on unverified claims.

---

## 🛡️ Core Philosophy

> **"Never recommend an optimization merely because an AI says it might be faster. Compile it, execute it, verify correctness, and measure it first."**

Autotune enforces empirical validation at every step:
1. **Zero Hallucinated Passes**: Proposed LLVM passes are validated against the local toolchain before compilation.
2. **Strict Correctness First**: Candidates that produce fast but incorrect output are discarded immediately.
3. **No Fake Hardware Metrics**: On macOS, Autotune uses high-precision CPU timing with statistical noise calculation, explicitly signaling `[WARN] E-01` rather than reporting fake cycle counts.

---

## ✨ Key Features

- **🩺 Environment & Toolchain Doctor (`autotune doctor`)**: Validates local Python 3.11+, Clang, LLVM `opt`, operating system, CPU architecture, and measurement capabilities.
- **🔬 Code Feature Extraction**: Analyzes C/C++ AST structure (loops, memory access patterns, compute density) and extracts compact JSON features to prompt the LLM safely without raw code dumps.
- **🤖 LLM Pass Pipeline Seeding**: Generates domain-tailored initial pass sequences using LLM intelligence, validated against local LLVM capabilities.
- **🧬 Deterministic Genetic Algorithm Search**: Mutates (insert, delete, swap) and crosses over (2-point crossover) pass pipelines with reproducible random seeding (`--seed 42`).
- **🔒 Isolated Sandbox Execution**: Runs candidate binaries in isolated process groups (`start_new_session=True`) with strict timeouts and `SIGKILL` cleanup.
- **✅ Ground-Truth Correctness Validator**: Compares candidate stdout/stderr and exit codes against trusted `-O3` baseline runs to reject divergent outputs.
- **📊 Cross-Platform Performance Runners**: Platform-specific backends (`MacOSPerformanceRunner` and `LinuxPerformanceRunner`) with statistical sampling (median, stddev, relative noise ratio).
- **📋 Reproducible Compiler Prescriptions**: Generates exact, copy-pasteable `clang` and `opt` compilation commands for production integration.

---

## 🏗️ System Architecture

```text
               C/C++ Source Code
                      │
                      ▼
        [ AST & Feature Extractor ]
                      │
                      ▼ (Compact Structural JSON)
              [ LLM Client ]
                      │
                      ▼ (Proposed Pass Pipelines)
           [ LLVM Pass Validator ] ◄── Rejects Hallucinated Passes
                      │
                      ▼
         [ Genetic Algorithm Engine ] ◄── Selection, Crossover, Mutators
                      │
                      ▼
          [ Compiler Driver (clang/opt) ]
                      │
                      ▼ (Candidate Binary)
             [ Sandbox Executor ]
                      │
             ┌────────┴────────┐
             ▼                 ▼
   [Correctness Validator] [Performance Runner]
   (Must match -O3 output) (Statistical Sampling & Noise)
             │                 │
             └────────┬────────┘
                      ▼
          [ Reproducible Prescription ]
```

### Repository Structure

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
│   ├── reporting/     # Compiler prescription builder & report renderer
│   ├── ui/            # Rich terminal dashboard formatting
│   └── cli.py         # Typer CLI application entry point
├── tests/
│   ├── unit/          # Tests for pass logic, GA, correctness, & config
│   └── integration/   # Tests for compilation drivers & CLI commands
├── examples/          # Sample C benchmark kernels (simple_loop, vector_sum)
└── docs/              # Deep-dive architecture & benchmarking specifications
```

---

## 🚀 Quick Start

### Prerequisites

- **macOS** (Apple Silicon or Intel) or **Linux**
- **Python 3.11+**
- **LLVM / Clang** toolchain (`clang` and `opt`)

On macOS via Homebrew:
```bash
brew install llvm python@3.11
```

### Installation

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

## 💻 CLI Commands & Usage

### 1. Toolchain Health Check (`autotune doctor`)

Inspects local compiler binaries, LLVM toolchain, and measurement capabilities:

```bash
autotune doctor
```

**Example Output:**
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

**Example Output:**
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

### 3. AI & Genetic Optimization Search (`autotune search`)

Runs the full AI-seeded Genetic Algorithm optimization loop over multiple generations:

```bash
autotune search ./examples/simple_loop/kernel.c \
    --workload ./examples/simple_loop/input.txt \
    --generations 10 \
    --population 20 \
    --seed 42
```

**Example Output:**
```text
Starting optimization search on ./examples/simple_loop/kernel.c...

Optimization Search Complete!
Best Pass Sequence: ['mem2reg', 'sroa', 'early-cse', 'gvn', 'loop-vectorize', 'slp-vectorize']
Speedup: 1.28x

Reproducible Command:
/usr/bin/clang -O0 -Xclang -disable-O0-optnone -emit-llvm -S ./examples/simple_loop/kernel.c -o - | /opt/homebrew/opt/llvm/bin/opt -passes='mem2reg,sroa,early-cse,gvn,loop-vectorize,slp-vectorize' -S -o - | /usr/bin/clang -x assembler - -o optimized_kernel.bin
```

---

### 4. Direct Binary Benchmarking (`autotune benchmark`)

Measures an arbitrary executable binary directly across multiple iterations:

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

## 🧪 Testing

Autotune includes a comprehensive suite of unit and integration tests:

```bash
# Run all tests
pytest -v

# Run unit tests only
pytest -v tests/unit/

# Run integration tests only
pytest -v tests/integration/
```

---

## ⚡ Platform Capabilities & Notes

| Feature / Platform | macOS (Apple Silicon M4) | Linux (x86_64 / ARM64) |
| :--- | :--- | :--- |
| **Compiler Driver** | Apple Clang / Homebrew LLVM | Native Clang / LLVM |
| **Measurement Backend** | Monotonic CPU Timing (`time.perf_counter_ns`) | `perf_event_open` Hardware Counters |
| **Diagnostic Notice** | Transparent `[WARN] E-01` | Native Counter Metrics |
| **Process Isolation** | Process Group Isolation (`start_new_session`) | Namespaces & Process Groups |

---

## 📄 License

Distributed under the **Apache 2.0 License**. See [`LICENSE`](LICENSE) for details.
