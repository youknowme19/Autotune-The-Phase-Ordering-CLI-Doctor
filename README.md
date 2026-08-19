# Autotune — The Phase-Ordering CLI Doctor

**An AI/GA-guided CLI optimization doctor that discovers workload-specific LLVM pass sequences for C/C++ programs to outperform standard compiler optimization flags.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PyPI Package](https://img.shields.io/badge/PyPI-autotune--doctor-blue.svg)](https://pypi.org/project/autotune-doctor/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![LLVM](https://img.shields.io/badge/LLVM-15%2B-orange.svg)](https://llvm.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey.svg)](docs/benchmarking.md)

---

## Release Status & Versioning

- **PyPI Release (`v0.2.0`)**: Available via `pip install autotune-doctor==0.2.0`. Provides core `doctor`, `config`, `diagnose`, `search`, and `bench-suite` subcommands with hardened engine features (disaggregated atomic persistent cache, baseline-normalized fitness, seed archiving, multi-fidelity screening `--fidelity`, baseline gating `--baseline-gate`, and regression guarding `--fail-on-regression`).

---

## What is Autotune?

**Autotune** is an open-source command-line tool for developers and compiler engineers who want to extract maximum performance from C and C++ programs.

Instead of relying on fixed, one-size-fits-all compiler flags like `-O2` or `-O3`, Autotune automatically explores, benchmark-evaluates, and verifies custom **LLVM pass sequences** specifically tailored to your C/C++ source code.

It combines structural C/C++ AST analysis, optional LLM seed proposal generation (OpenAI, Anthropic, Gemini, or offline AST heuristics), multi-fidelity Genetic Algorithm (GA) search, disaggregated persistent caching, and sandbox correctness checking.

---

## The Problem: Why LLVM Phase Ordering Matters

When you compile C or C++ code with `clang -O3`, the compiler runs a fixed pipeline of over 100 optimization passes (such as loop unrolling, dead code elimination, constant propagation, and vectorization) in a pre-determined order.

However, **compiler pass ordering is sensitive to code structure**:
- One optimization pass (e.g., `mem2reg`) changes the code layout, creating new opportunities for a second pass (e.g., `gvn`).
- A pass executed too early might obscure patterns that a later pass needed to see.
- A fixed pass order optimized for general application code is rarely optimal for specific compute-heavy kernels.

**Autotune solves the phase-ordering problem** by automatically searching the space of LLVM pass combinations to find the exact pipeline sequence that executes your target program in the shortest time.

---

## How Autotune Works

Autotune executes an end-to-end multi-stage pipeline:

```text
               C/C++ Source Code
                      │
                      ▼
        [ AST & Feature Extractor ]  (Clang -ast-dump=json)
                      │
                      ▼ (Compact Structural Metadata)
          [ LLM / Heuristic Seeder ] (OpenAI / Anthropic / Gemini / Offline AST)
                      │
                      ▼ (Proposed Initial Pass Pipelines)
           [ LLVM Pass Validator ]  (Rejects Hallucinated Passes & Normalizes NPM)
                      │
                      ▼
          [ Genetic Algorithm Engine ]  (Selection, Crossover, Mutators, Cache)
                      │
                      ▼
        [ 3-Step LLVM Compiler Driver ]
          1. clang -O0 -Xclang -disable-O0-optnone -emit-llvm -c source.c -o raw.bc
          2. opt -passes="function(...)" raw.bc -o opt.bc
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

## What Autotune Does NOT Do

1. **Does NOT rewrite your C/C++ source files**: Your original `.c` or `.cpp` source files remain untouched. Autotune optimizes code at the intermediate LLVM bitcode representation layer (`opt -passes='...'`).
2. **Does NOT blindly trust LLMs**: AI models act strictly as seed proposal generators for Generation 0. They **never** directly declare a winner. Every candidate binary must compile cleanly, pass correctness validation, and prove performance gains under empirical benchmark timing.
3. **Does NOT guarantee universal speedups across all programs**: Autotune discovers workload-specific optimizations. Code that is already optimal under `-O3` or bound by hardware I/O will show parity rather than artificial speedups.

---

## Quick Start (60-Second Workflow)

### 1. Install via PyPI
```bash
pip install autotune-doctor
```

### 2. Verify System Readiness
```bash
autotune doctor
```

### 3. Diagnose Target Kernel Baseline
```bash
autotune diagnose ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt
```

### 4. Run Optimization Search (100% Offline Mode)
```bash
autotune search ./examples/matrix_transpose/kernel.c \
  -w ./examples/matrix_transpose/input.txt \
  --no-llm \
  -p 10 \
  -g 5 \
  -s 42 \
  --fresh-benchmark \
  -o search_report.json
```

---

## Installation & System Requirements

### Prerequisites
- **Python**: Version `3.11` or higher.
- **LLVM / Clang**: LLVM version `15.0` or higher (`clang` and `opt` binaries available on system `PATH`).
- **Operating System**: macOS (ARM64 / x86_64) or Linux (x86_64).

### Option A: Install from PyPI
```bash
pip install autotune-doctor
```

### Option B: Install from Source
```bash
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor

python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Your First Optimization Walkthrough

Let's optimize a C matrix transpose kernel ([`examples/matrix_transpose/kernel.c`](file:///Volumes/SSD/autotune/examples/matrix_transpose/kernel.c)):

### Step 1: Diagnose Baseline
```bash
autotune diagnose ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt
```
Autotune compiles the kernel with standard `clang -O3`, executes it, measures median latency, and verifies baseline output checksums.

### Step 2: Search for Optimal Pass Sequence
```bash
autotune search ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt --no-llm -p 10 -g 5 -s 42
```
The Genetic Algorithm evaluates pass sequence proposals over 5 generations. Promising candidates are screened, verified for correctness, and evaluated for execution speed.

---

## Understanding Workloads (`--workload`)

What is a workload?
A workload is the input dataset, command-line parameters, or input file required by your C/C++ executable to run its compute loop.

- **When `--workload` (`-w`) is supplied**: Autotune redirects the file contents directly to the candidate program's `stdin` during both baseline diagnosis and candidate benchmarking.
- **When `--workload` is omitted**: Autotune executes the program binary directly without input redirection.

> **Execution Model Note**: Autotune currently supports self-contained C/C++ kernels or programs that receive workload data via `stdin`. If your program requires command-line `argv` arguments or crashes at runtime (e.g. due to buffer overflow fortification `SIGTRAP` / exit code 133), Autotune will report an explicit diagnostic indicating non-zero process exit codes rather than failing silently.

Example:
```bash
# Display version
autotune --version

# Workload provided via input file (redirected to stdin)
autotune search kernel.c -w input_params.txt

# Standalone kernel (no stdin workload required)
autotune search standalone_kernel.c
```

---

## Understanding Search Results

At the conclusion of a search, Autotune displays a terminal dashboard summary:

```text
Optimization Search Complete!
Best Pass Sequence: ['gvn', 'sccp', 'mem2reg', 'lower-atomic', 'mem2reg']
Confirmed Speedup: 1.25x (19.8% improvement over -O3)

Baseline (-O3):   73.29 ms
Candidate Best:   58.78 ms

Reproducible Compiler Command:
/opt/homebrew/opt/llvm/bin/clang -O0 -Xclang -disable-O0-optnone -emit-llvm -S 
./examples/matrix_transpose/kernel.c -o - | /opt/homebrew/opt/llvm/bin/opt 
-passes='function(gvn,sccp,mem2reg,lower-atomic,mem2reg)' -S -o - | 
/opt/homebrew/opt/llvm/bin/clang -x assembler - -o optimized_kernel.bin
```

### Key Terms:
- **Baseline (-O3)**: Execution latency of standard `clang -O3`.
- **Candidate Best**: Execution latency of the winning custom LLVM pass sequence.
- **Speedup**: $\text{Speedup} = \frac{\text{Baseline Latency}}{\text{Candidate Latency}}$. ($1.25x = 25\%$ faster execution).
- **Pass Sequence**: The ordered list of LLVM passes applied to the intermediate bitcode.
- **Reproducible Compiler Command**: A single copy-pasteable pipeline command to compile your source file into an optimized binary without needing Autotune installed.

---

## Execution Modes & LLM Configuration

Autotune supports three execution modes for candidate seed generation:

### 1. Auto-Detect Mode (Default: `autotune search kernel.c`)
Checks OS Keychain or environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`). If found, uses LLM proposals for Generation 0; otherwise, gracefully falls back to offline AST heuristics.

### 2. Explicit AI Mode (`autotune search kernel.c --llm --provider openai`)
Forces LLM proposal generation. (Configured securely via `autotune config --provider openai --api-key YOUR_KEY`).

### 3. Explicit Offline Mode (`autotune search kernel.c --no-llm -s 42`)
Runs 100% offline using deterministic AST heuristics and random seed 42. Requires zero API keys, makes zero network calls, and guarantees 100% reproducible population initialization.

---

## Complete CLI Command Reference

Autotune exposes 5 core subcommands:

### 1. `autotune doctor`
System environment diagnostics for LLVM, Clang, Opt, Python, and timing backends.
```bash
autotune doctor
```

### 2. `autotune config`
Store API keys securely in system keyring (macOS Keychain / Linux SecretService).
```bash
autotune config --provider openai --api-key YOUR_API_KEY
```

### 3. `autotune diagnose`
Analyze AST loop structures and benchmark baseline `-O3` execution latency.
```bash
autotune diagnose SOURCE [-w WORKLOAD_PATH]
```

### 4. `autotune search`
Execute AI/GA optimization search for optimal LLVM pass pipelines.
```bash
autotune search SOURCE [OPTIONS]
```

### 5. `autotune bench-suite`
Run batch stress testing across a directory of C/C++ benchmark kernels.
```bash
autotune bench-suite SUITE_DIR [-p POPULATION] [-g GENERATIONS] [-s SEED] [-o OUTPUT_REPORT]
```

---

## Search Configuration Parameters

Key options for `autotune search`:

| Flag / Option | Type | Default | Description |
|---|---|---|---|
| `-w, --workload` | `PATH` | `None` | Path to workload input file. |
| `-p, --population` | `INT` | `10` | GA population size per generation. |
| `-g, --generations` | `INT` | `5` | GA generation cycle count. |
| `-s, --seed` | `INT` | `42` | Random seed for deterministic search. |
| `--workers` | `INT` | `4` | Number of parallel evaluation workers (`ThreadPoolExecutor`). |
| `--fidelity` | `TEXT` | `HIGH` | Measurement fidelity stage (`LOW`, `MEDIUM`, `HIGH`). |
| `--screen-runs` | `INT` | `3` | Timing repetitions during `LOW` fidelity screening. |
| `--confirm-runs` | `INT` | `20` | Timing repetitions during final confirmation. |
| `--baseline-gate / --no-baseline-gate` | `BOOL` | `True` | Prune non-promising proposals ($\text{normalized\_speed} < 0.80$) at `LOW` fidelity. |
| `--fresh-benchmark` | `BOOL` | `False` | Force fresh timing measurements (bypassing performance cache). |
| `--llm / --no-llm` | `BOOL` | `Auto` | Enable or disable LLM candidate seeding. |
| `-o, --output-json` | `PATH` | `None` | Export structured JSON search report to path. |

---

## Benchmarking & Correctness Validation

Every candidate pass sequence undergoes strict evaluation:

1. **Compilation Sandbox**: Bitcode transformation (`opt -passes='...'`) and native assembly compilation protected by strict timeouts.
2. **Program Sandbox**: Execution under process sandbox isolated environments.
3. **Correctness Validator**: Compares candidate output against baseline `-O3` output using pluggable strategy validators (exact stdout/stderr matching, numeric floating-point tolerance $\epsilon = 10^{-6}$, or SHA-256 digests). Invalid candidates receive negative infinite fitness and are rejected.
4. **Performance Measurement**: Measures in-process monotonic execution latency (`__AUTOTUNE_TIME_NS__`), calculating median, mean, stddev, CV, and IQR statistics.

---

## Exported JSON Search Reports (`--output-json`)

When `--output-json` is specified, Autotune exports a structured diagnostic JSON report:

```json
{
  "source_path": "./examples/matrix_transpose/kernel.c",
  "workload_path": "./examples/matrix_transpose/input.txt",
  "generations_searched": 5,
  "population_size": 10,
  "seed": 42,
  "baseline_median_ns": 73294000,
  "prescription": {
    "winning_passes": ["gvn", "sccp", "mem2reg", "lower-atomic", "mem2reg"],
    "canonical_pipeline": "function(gvn,sccp,mem2reg,lower-atomic,mem2reg)",
    "speedup_ratio": 1.25,
    "reproducible_command": "clang -O0 ... | opt -passes='...' | clang -x assembler -"
  }
}
```

---

## Validated Research Result (`matrix_transpose`)

In addition to user-facing optimization search capabilities, Autotune includes a frozen scientific confirmation manifest for researchers:

- **Target Kernel**: [`examples/matrix_transpose/kernel.c`](file:///Volumes/SSD/autotune/examples/matrix_transpose/kernel.c) ($N=512$, $100$ iterations)
- **Winning Pass Pipeline**: `function(gvn,mem2reg,invalidate<all>,gvn,gvn-hoist)`
- **Phase G Interleaved Confirmation Protocol**: 100 warmups, 100 baseline + 100 candidate fresh timing measurements with deterministic random interleaving (seed 42).
- **Baseline (`-O3`) Median**: **70.446 ms** (StdDev: 3.009 ms)
- **Candidate Median**: **55.858 ms** (StdDev: 4.738 ms)
- **Confirmed Speedup Ratio**: **1.26x** (**20.7% Runtime Reduction**)
- **Statistical Significance**: Welch $t$-test $p = 1.18 \times 10^{-152}$, Mann-Whitney $U$ $p = 2.47 \times 10^{-33}$, Bootstrap 95% CI **$[1.25x, 1.32x]$**, Cohen's $d = 3.72$.
- **Correctness Status**: **PASS** (`Matrix Transpose Check B[256][256]: 1313.2899`)

> **Research Framing Note**: This confirmed 1.26x speedup is a **workload-specific research result** on `matrix_transpose`. It is NOT a claim of universal optimization superiority across all C programs.

---

## Known Limitations

1. **Workload Dependence**: Pass sequences optimized for one code pattern (e.g., matrix transpose) may not improve or may regress on different code structures.
2. **PolyBench Generalization**: On dense linear algebra loop kernels (PolyBench `2mm`, `cholesky`, `atax`, `gemm`, `bicg`), small offline GA budgets ($P=10, G=5$, `--no-llm`) produce performance regressions ($0.13x - 0.77x$) against Clang `-O3`, demonstrating honest regression detection.
3. **Compiler & Toolchain Dependence**: Pass pipeline execution depends on LLVM NPM semantics (tested under Homebrew LLVM/Clang 22.1.8).

---

## In-Depth Technical Documentation

Comprehensive architectural and engineering guides are available in the [`docs/`](docs/README.md) library:

- [**CLI Command Reference**](docs/cli-reference.md): Full reference for all 5 subcommands.
- [**Installation & Toolchain Setup**](docs/installation.md): Requirements, virtualenv, and LLVM/Clang setup.
- [**Quickstart Guide**](docs/quickstart.md): Step-by-step optimization tutorial.
- [**Usage Workflows**](docs/usage.md): Execution modes, multi-worker search, and bench-suite.
- [**System Architecture**](docs/architecture.md): Component mapping and internal class responsibility reference.
- [**Pipeline Search Engine**](docs/pipeline-search.md): NPM pass representation, canonicalization, and GA operators.
- [**Fitness & Evaluation**](docs/fitness-and-evaluation.md): Normalized speedup formula and failure handling.
- [**Multi-Fidelity Screening**](docs/multi-fidelity.md): Fidelity stages and baseline gate candidate pruning.
- [**Persistent Cache System**](docs/caching.md): Disaggregated caching, atomic writes, and corruption recovery.
- [**Correctness Validation**](docs/correctness.md): Program output verification strategies.
- [**LLM Seeding**](docs/llm-seeding.md): AST feature extraction and LLM client prompt architecture.
- [**Final Confirmation Protocol**](docs/confirmation.md): Search vs. confirmation separation and protocol details.
- [**Reproducibility Guide**](docs/reproducibility.md): Random seeds (`--seed 42`) and measurement protocols.
- [**Benchmarking Methodology**](docs/benchmarking.md): Microsecond timing probes and noise analysis.
- [**Troubleshooting Guide**](docs/troubleshooting.md): Solutions for toolchain errors and warnings.
- [**Development Guide**](docs/development.md): Development environment setup and codebase layout.
- [**Testing Guide**](docs/testing.md): Running Pytest and writing test modules.
- [**Extending Autotune**](docs/extending-autotune.md): Adding passes, validators, or performance backends.
- [**Contributing Guidelines**](docs/contributing.md): Pull request guidelines and standards.
- [**Scientific Validation Summary**](docs/scientific-validation.md): Empirical evidence manifest.
- [**Known Limitations**](docs/limitations.md): Explicit scope boundaries and scientific rules.

---

## Community, Security & License

- **Contributing**: Please review [`CONTRIBUTING.md`](CONTRIBUTING.md) before submitting pull requests.
- **Security & Responsible Use**: Please review [`SECURITY.md`](SECURITY.md) for credential safety guidelines.
- **Code of Conduct**: Please adhere to our [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
- **License**: Distributed under the Apache 2.0 License. See [`LICENSE`](LICENSE) for details.
