# Autotune — The LLVM Phase-Ordering CLI Doctor

**An AI-guided compiler optimization doctor that searches, validates, and proves workload-specific LLVM pass sequences for C/C++ programs to outperform standard `-O3`.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PyPI Package](https://img.shields.io/badge/PyPI-autotune--doctor-blue.svg)](https://pypi.org/project/autotune-doctor/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![LLVM](https://img.shields.io/badge/LLVM-15%2B-orange.svg)](https://llvm.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey.svg)](docs/benchmarking.md)

---

## ⚡ What is Autotune?

**Autotune** is an open-source, production-grade command-line tool for developers, performance engineers, and compiler researchers who want to extract maximum performance from C and C++ programs.

Instead of relying on fixed, one-size-fits-all optimization levels like `-O2` or `-O3`, Autotune systematically searches the phase-ordering space of **LLVM passes**, empirically validates every candidate's output correctness, collects repeated high-precision benchmark samples, calculates statistical significance, and generates reproducible optimization prescriptions and standalone HTML reports.

```bash
pip install autotune-doctor

autotune doctor kernel.c
```

---

## 🎯 Why Phase Ordering Matters

### The Fixed `-O3` Problem
When you compile with `clang -O3`, the compiler executes a predefined, monolithic pipeline of over 100 optimization passes in a predetermined order. While tuned as a general compromise for millions of diverse programs, a static pass ordering is rarely optimal for compute-heavy loops, matrix routines, or numerical kernels.

### Phase Ordering Dynamics
Compiler optimization passes interact non-linearly:
* **Enabling Transformations:** One pass (e.g., `mem2reg`) promotes stack allocations into SSA registers, exposing opportunities for `gvn` (Global Value Numbering) or `licm` (Loop-Invariant Code Motion).
* **Premature Canonicalization:** A pass executed too early can canonicalize IR into a shape that obscures loop structures needed by vectorizers.
* **Workload Specialization:** Compute-bound and memory-bound kernels benefit from distinct pass orderings and loop transformation depths.

Autotune automates the exploration of this combinatorial phase-ordering space using AST feature extraction, AI/heuristic candidate seeding, and a multi-fidelity Genetic Algorithm (GA).

---

## 🔬 How Autotune Works

```text
               C/C++ Source (.c / .cpp)
                          ↓
              AST & Workload Profiling
                          ↓
              Baseline -O3 Compilation
                          ↓
              Baseline Benchmark (Repeated Samples)
                          ↓
         Candidate Seeding (LLM or AST Heuristic)
                          ↓
          Genetic Algorithm Phase-Order Search
                          ↓
        Candidate Compilation (clang → opt → bin)
                          ↓
          Correctness Verification (100% Oracle)
                          ↓
            Multi-Sample Fresh Confirmation
                          ↓
       Statistical Rigor (Welch's t-test & Cohen's d)
                          ↓
        Decide Winner & Evidence Grade (A/B/C/D/F)
                          ↓
        Prescription, JSON Report, & Standalone HTML
```

---

## 🚀 Quick Start

### 1. Install via pip
```bash
pip install autotune-doctor
```

### 2. Optimize a Kernel (Flagship Entrypoint)
```bash
autotune doctor examples/matrix_transpose/kernel.c
```

Output:
```text
╭──────────────────────────────────────────────╮
│               AUTOTUNE DOCTOR                │
│      LLVM Phase-Ordering Optimization        │
╰──────────────────────────────────────────────╯

Analyzing kernel.c                         ✓
Extracting workload features              ✓
Building -O3 baseline                     ✓

Baseline:
  Execution time: 71.655 ms

Searching phase-order space...
  Generation        4 / 5
  Candidates        40
  Valid candidates  37
  Best candidate    60.231 ms

Validating winner...
  Correctness        ✓ PASS
  Benchmark          ✓ PASS
  Statistical test   ✓ PASS (p < 0.001)

🏆 OPTIMIZATION FOUND

  -O3 Baseline:   71.655 ms
  Autotune Best:  60.231 ms
  Confirmed Gain: 1.19× (Grade A — IMPROVED)

Winning pipeline:
  reassociate → mem2reg → inline → instcombine → loop-simplify → indvars

Artifacts:
  - JSON Report: .autotune/runs/run_.../report.json
  - HTML Report: .autotune/runs/run_.../report.html

Reproduce:
  autotune reproduce .autotune/runs/run_.../report.json
```

---

## 🎛️ Optimization Presets

Autotune provides built-in presets designed for different developer workflows:

| Preset | Command | Search Budget | Recommended For |
| :--- | :--- | :--- | :--- |
| **quick** | `autotune doctor kernel.c --preset quick` | ~15s (8 pop, 4 gen) | Fast local exploration and rapid iteration |
| **balanced** | `autotune doctor kernel.c --preset balanced` | ~30s (12 pop, 8 gen) | Default recommended mode for general optimization |
| **aggressive** | `autotune doctor kernel.c --preset aggressive` | ~60s (20 pop, 15 gen) | Deep search with high confirmation sample count |

Advanced users can override individual parameters:
```bash
autotune doctor kernel.c --population 25 --generations 20 --seed 42 --workers 8 --time-budget 90
```

---

## 🔒 Security & Offline Mode

Autotune features a strict **tri-state execution model**:

1. **Auto-Detection (Default):** If an API key is configured, Autotune uses LLM candidate seeding. If no key is found, it automatically runs in offline heuristic mode.
2. **Explicit Offline (`--no-llm`):** Makes zero network requests, ignores API keys, uses offline AST heuristics, and works in air-gapped CI environments.
3. **Explicit LLM (`--llm`):** Requests LLM candidate generation and produces a clear error if no key is configured.

### Secure Credential Storage
Store your API key securely in the OS keyring:
```bash
autotune config --provider openai
```
Or export the standard environment variable:
```bash
export OPENAI_API_KEY="sk-..."
```
> **Security Guarantee:** API keys are never printed to terminal logs, never written to JSON manifests, never included in HTML reports, and never exposed in error exceptions.

---

## 📊 Scientific Benchmark Methodology

Autotune adheres to strict experimental standards:
1. **Repeated Measurements:** Never relies on a single timing run. Collects repeated warmup and benchmark runs.
2. **Robust Statistics:** Reports median, mean, standard deviation, interquartile range (IQR), and coefficient of variation (CV%).
3. **Hypothesis Testing:** Evaluates speedup significance using two-tailed Welch's $t$-test ($p < 0.05$).
4. **Effect Size:** Computes Cohen's $d$ effect size to verify meaningful differences beyond system noise.
5. **Confidence Intervals:** Calculates 95% Confidence Intervals for performance delta.
6. **Evidence Grading System:**
   * **Grade A:** Confirmed statistically significant speedup ($p < 0.05$, Cohen's $d \ge 0.8$, speedup $\ge 1.05\times$, low noise).
   * **Grade B:** Confirmed statistically significant speedup ($p < 0.05$, speedup $\ge 1.02\times$).
   * **Grade C:** Marginal or noisy speedup (insufficient statistical confidence).
   * **Grade D:** Baseline parity (equivalent to `-O3`).
   * **Grade F:** Confirmed regression, compilation failure, or output mismatch.

---

## 🛡️ Failure Safety & Correctness

Autotune enforces a multi-layer correctness and isolation gate:
* **Output Validation Oracle:** Validates stdout, stderr, and exit codes of every candidate against the trusted baseline run.
* **Automatic Disqualification:** Any candidate producing invalid output, crashes, or timeouts is assigned infinite penalty fitness and permanently rejected.
* **Fault Isolation:** Compiler crashes or pass timeouts in one candidate are isolated in a sandbox and do not terminate the search.

---

## 🔄 Experiment Reproduction (`autotune reproduce`)

Every completed optimization experiment can be reproduced with a single command:
```bash
autotune reproduce .autotune/runs/run_20260830_abcd1234/report.json
```

Verdicts returned:
* `REPRODUCED`: Observed performance matches recorded speedup within tolerance.
* `NOT_REPRODUCED`: Performance deviated beyond expected tolerance.
* `INCONCLUSIVE`: High environmental measurement noise detected (CV > 20%).

---

## 🛡️ CI/CD Performance Guard (`autotune guard`)

Prevent performance regressions in continuous integration workflows:
```bash
autotune guard src/kernel.c --reference .autotune/runs/baseline_report.json --threshold 0.05 --ci
```

Deterministic exit codes:
* `0`: **PASS** — Performance within tolerance.
* `1`: **PERFORMANCE REGRESSION** — Latency degraded beyond threshold.
* `2`: **CORRECTNESS FAILURE** — Output mismatch against baseline.
* `3`: **INFRASTRUCTURE ERROR** — Missing source or compiler error.

---

## ⚖️ Heuristic vs LLM Comparison (`autotune compare`)

Compare search efficacy between offline heuristic seeding and AI-guided seeding on the same source kernel:
```bash
autotune compare examples/matrix_transpose/kernel.c --preset quick
```

Or compare two JSON search reports side-by-side:
```bash
autotune compare report_run_a.json report_run_b.json
```

---

## 🔍 IR & Assembly Inspection (`autotune inspect`)

Inspect LLVM IR transformations, structural IR diffs, and assembly metrics:
```bash
autotune inspect examples/matrix_transpose/kernel.c
```
Or inspect assembly during doctor optimization:
```bash
autotune doctor examples/matrix_transpose/kernel.c --assembly
```

Computes and displays:
* Total instruction count differences
* SIMD / Vector instruction count gains (NEON / AVX / SSE)
* Branch and loop structure changes
* Unified LLVM IR diff (Baseline vs Optimized)

---

## 📜 Full Command Reference

| Command | Description |
| :--- | :--- |
| `autotune doctor <source>` | Flagship entrypoint: profile, search, validate, and export reports |
| `autotune doctor` | Run system and toolchain diagnostic checks |
| `autotune reproduce <report.json>` | Verify and reproduce a recorded optimization report |
| `autotune guard <source>` | Performance regression guard for CI pipelines |
| `autotune compare <source>` | Run controlled A/B search comparing Heuristic vs LLM seeding |
| `autotune compare <rep_a> <rep_b>` | Compare two experiment reports side-by-side |
| `autotune inspect <source>` | Inspect LLVM IR diffs and assembly metrics |
| `autotune diff-ir <report.json>` | View structural IR differences from a search report |
| `autotune history [source]` | View past optimization experiment history |
| `autotune resume <id>` | Resume an interrupted GA search from snapshot |
| `autotune search <source>` | Low-level Genetic Algorithm pass search |
| `autotune diagnose <source>` | Profile source AST and measure baseline `-O3` |
| `autotune bench-suite <dir>` | Batch stress-testing across multiple benchmark kernels |
| `autotune explain <pipeline>` | Explain compiler optimization semantics of LLVM passes |
| `autotune config` | Securely store LLM provider API credentials |
| `autotune status` | Display toolchain availability, cache stats, and memory records |
| `autotune cache [status\|clear]` | Inspect or clear persistent compilation and benchmark caches |
| `autotune bundle <report.json>` | Export a self-contained research reproduction bundle |
| `autotune runs [list\|clean]` | Manage local experiment run directories |

---

## 🏛️ Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                       AUTOTUNE CLI                          │
│   doctor | reproduce | guard | compare | inspect | history   │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    ┌──────────────────────┐        ┌──────────────────────┐
    │ Workload Profiler    │        │ Toolchain & Hardware │
    │ AST Feature Extractor│        │ Diagnostic Checks    │
    └──────────┬───────────┘        └──────────┬───────────┘
               │                               │
               └───────────────┬───────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────┐
    │                 CANDIDATE SEEDING                       │
    │   LLM Client (OpenAI/Anthropic/Gemini) OR AST Heuristic │
    └──────────────────────────┬──────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────┐
    │             GENETIC ALGORITHM SEARCH ENGINE             │
    │   Mutation | Crossover | Selection | Multi-Fidelity GA  │
    └──────────────────────────┬──────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────┐
    │                   COMPILER DRIVER                       │
    │      Clang (-O0) → Opt (-passes=...) → Native Emit      │
    └──────────────────────────┬──────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────┐
    │                EXECUTION & VALIDATION                   │
    │    Sandbox Executor → Correctness Validator Oracle      │
    │    Multi-Sample Benchmark Runner → Stability Analyzer   │
    └──────────────────────────┬──────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────┐
    │                EVIDENCE & REPORTING                     │
    │   Welch's t-test | Cohen's d | 95% CI | Evidence Grade   │
    │   JSON Manifest | Standalone HTML | History Store       │
    └─────────────────────────────────────────────────────────┘
```

---

## 🧪 PolyBench/C Multi-Workload Benchmarks

Autotune supports standard compute benchmark suites including PolyBench/C:
```bash
autotune bench-suite polybench/ --generations 5 --population 10
```

Supported workloads:
* `matrix_transpose`
* `2mm` (Two Matrix Multiplications)
* `gemm` (General Matrix Multiply)
* `atax` (Matrix Transpose and Vector Multiplication)
* `bicg` (BiCG Subkernel)
* `cholesky` (Cholesky Decomposition)

---

## 🔬 Research Direction: AI as Guidance, Measurement as Authority

Autotune embodies a core scientific principle:
> **LLMs are generative seed accelerators; empirical measurement remains the sole authority.**

Large Language Models analyze AST and code semantics to propose intelligent initial pass sequences. However, every optimization claim is strictly validated by compiling bitcode, proving exact correctness, and running statistically confirmed physical hardware benchmarks.

---

## 📄 License

Autotune is licensed under the [Apache 2.0 License](LICENSE).
