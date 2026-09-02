# Autotune Architecture & System Design

Autotune is an AI-guided LLVM phase-ordering optimization engine designed to systematically explore, evaluate, and prove workload-specific compiler optimization pipelines.

---

## 1. High-Level Architecture

```text
                                +---------------------------+
                                |  C / C++ Source (.c/.cpp) |
                                +---------------------------+
                                              |
                                              v
+-----------------------+       +---------------------------+
|  Environment Analysis | ----> |  AST Feature Extraction   |
| (Triple, CPU, Clang)  |       | (Loops, Ops, Memory/Math) |
+-----------------------+       +---------------------------+
                                              |
                                              v
                                +---------------------------+
                                |   -O3 Baseline Benchmark  |
                                | (Warmup, Timed, Stdev/CV) |
                                +---------------------------+
                                              |
                                              v
        +-------------------------------------------------------------+
        |                 Candidate Generation & Seeding              |
        |                                                             |
        |  * LLM-Guided Seeding (DeepSeek, OpenAI, Anthropic, Gemini) |
        |  * AST Heuristic Seeding (100% Offline Domain Rules)         |
        +-------------------------------------------------------------+
                                              |
                                              v
        +-------------------------------------------------------------+
        |              Genetic Algorithm (GA) Search Engine           |
        |                                                             |
        |  * Pass Mutations (Insertion, Deletion, Swap, Replacement)  |
        |  * Multi-Fidelity Timing Evaluation                         |
        |  * UCB1 Pass Family Bandit Scoring                          |
        |  * Deduplication & Candidate Caching                        |
        +-------------------------------------------------------------+
                                              |
                                              v
        +-------------------------------------------------------------+
        |                 Validation & Statistical Rigor              |
        |                                                             |
        |  * Pluggable Correctness Validators (Exact, Checksum, Tol)  |
        |  * Fresh Multi-Sample Confirmation Run                      |
        |  * Welch's t-test (p-value) & Mann-Whitney U Test           |
        |  * Cohen's d Effect Size & Evidence Grading (A/B/C/D/F)     |
        +-------------------------------------------------------------+
                                              |
                                              v
        +-------------------------------------------------------------+
        |                 Prescription & Delivery                     |
        |                                                             |
        |  * Standalone Glassmorphic HTML & Structured JSON Reports   |
        |  * autotune explain (Observed, Inferred, Hypothesized)      |
        |  * autotune apply (Raw IR, Optimized IR, Assembly, Bin)     |
        |  * autotune export (CMake, Make, Shell, Meson, Ninja)       |
        |  * autotune guard (CI Regression Gate & Exit Codes)         |
        +-------------------------------------------------------------+
```

---

## 2. Core Subsystems

### A. Workload Analysis (`src/autotune/analysis/`)
* Runs `clang -Xclang -ast-dump=json` (or resilient regex fallbacks) to inspect loop nesting depth, array indexing density, pointer dereference counts, floating-point arithmetic ratios, and branch counts.
* Computes normalized `memory_intensity` and `compute_intensity` indices used to seed optimization pass families.

### B. LLVM Compiler Pipeline Driver (`src/autotune/llvm/`)
* Manages the lowering of user C/C++ code to LLVM IR:
  ```bash
  clang -O0 -Xclang -disable-O0-optnone -emit-llvm -S source.c -o raw.ll
  opt -passes="pass1,pass2,..." raw.ll -S -o optimized.ll
  clang optimized.ll -o native.bin
  ```
* Supports cross-platform toolchain discovery across macOS (`/opt/homebrew`, Xcode) and Linux (`/usr/bin/clang-[14-19]`).

### C. Search & Exploration Engine (`src/autotune/search/`)
* **Genetic Algorithm**: Maintains a population of pass pipelines. Evaluates fitness via speedup ratio relative to baseline `-O3`.
* **Pass Taxonomy**: Enforces pass ordering validity (e.g. module passes before function passes, avoiding illegal combinations).
* **Multi-Armed Bandit (UCB1)**: Balances exploration of under-tested pass families with exploitation of passes that historically produced significant speedups.
* **Persistent Cache**: Cryptographically hashes source code, compiler flags, and target architecture to prevent redundant compilations.

### D. Correctness & Benchmarking (`src/autotune/benchmark/`)
* Executes binaries inside an isolated subprocess sandbox with configurable timeouts and resource limits.
* Verifies correctness using pluggable strategies: `ExactOutputValidator`, `NumericToleranceValidator`, `ChecksumValidator`, `FileDigestValidator`, and `CompositeValidator`.
* Benchmarking incorporates warmup runs, CPU frequency stabilization pauses, and coefficient of variation (`CV%`) tracking to flag noisy environments.

### E. Evidence & Statistical Rigor (`src/autotune/reporting/evidence.py`)
* Computes two-tailed **Welch's t-test** for unequal variances.
* Calculates non-parametric **Mann-Whitney U rank-sum test** to withstand timing distribution outliers.
* Calculates **Cohen's d**:
  $$d = \frac{\bar{x}_{\text{baseline}} - \bar{x}_{\text{candidate}}}{s_{\text{pooled}}}$$
* Grades optimizations into `Grade A` ($\ge 1.05\times$, statistically significant), `Grade B`, `Grade C` (noisy), `Grade D` (parity), and `Grade F` (regression/failure).

---

## 3. Storage & Artifacts

All operational state is managed under `.autotune/` in the project root:
* `.autotune/runs/<run_id>/`: Contains `report.json`, `report.html`, and raw execution traces.
* `.autotune/history/`: Indexed JSON ledger of all past experiments.
* `.autotune/artifacts/<run_id>/`: Created by `autotune apply` with `.ll`, `.s`, `.bin`, and `manifest.json`.
* `.autotune/cache.db`: SQLite cache for evaluation memoization.
