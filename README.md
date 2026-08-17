# Autotune — Phase-Ordering CLI Doctor

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)

**Autotune** is an AI-guided compiler optimization system for C/C++ workloads. Its goal is to discover code-specific LLVM optimization pass sequences that outperform standard compiler optimization flags (like `-O3`), verify program correctness, benchmark candidate performance under controlled conditions, and produce reproducible compiler prescriptions.

---

## Central Philosophy

> **"Never recommend an optimization merely because an AI says it might be faster. Compile it, execute it, verify correctness, and measure it first."**

---

## Key Features

- **Toolchain Doctor**: Automatically inspects and validates `clang`, `opt`, LLVM versions, and available hardware/software measurement backends.
- **Pass Pipeline Abstraction**: Manages LLVM pass sequences (`PassSequence`), providing validation against installed toolchain capabilities to reject invalid or hallucinated passes before compilation.
- **Genetic Algorithm Optimization**: Combines LLM-generated seed pass pipelines with genetic mutations (insertion, deletion, swapping, 2-point crossover) to explore the LLVM phase-ordering space.
- **Strict Correctness Verification**: Runs candidate binaries inside isolated sandboxes, validating output against trusted `-O3` baselines before scoring performance.
- **Platform-Independent Benchmarking**: Supports macOS high-precision CPU timing with noise detection alongside Linux hardware performance counter abstractions (`perf_event_open`).

---

## Quick Start

### Installation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 1. Check Toolchain Health

```bash
autotune doctor
```

### 2. Run Baseline Diagnostics

```bash
autotune diagnose ./examples/simple_loop/kernel.c \
    --workload ./examples/simple_loop/input.txt
```

---

## Architecture Overview

```text
C/C++ Source
     │
     ▼
[AST & Feature Extractor] ──► Compact JSON ──► [LLM Client]
     │                                              │
     ▼                                              ▼
[Pass Validator] ◄────────────────────── Proposed LLVM Passes
     │
     ▼
[Genetic Algorithm Engine] ◄── Population & Mutators
     │
     ▼
[Compiler Driver (clang/opt)] ──► Candidate Binary
     │
     ▼
[Sandbox Executor]
     │
     ├─► [Correctness Validator] ──► Reject fast-but-incorrect
     │
     └─► [Performance Runner]   ──► MacOS / Linux Measurement
             │
             ▼
   [Reproducible Prescription]
```

---

## Platform Notes & Limitations

- **macOS / Apple Silicon (ARM64)**: Hardware performance counters (`perf_event_open`) are Linux-specific. On macOS, Autotune uses a high-precision CPU timing backend (`MacOSPerformanceRunner`) with statistical noise calculation, explicitly reporting `[WARN] E-01` to ensure timing fallback is transparent.
- **Linux**: Supports Linux performance counter infrastructure.

---

## Documentation

- [Architecture Guide](docs/architecture.md)
- [Development Guide](docs/development.md)
- [Benchmarking Specification](docs/benchmarking.md)
