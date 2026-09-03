# Changelog

All notable changes to the **Autotune** project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] - 2026-09-03 — Compiler Intelligence & Integration Release

### Added
- **Toolchain Diagnostics & System Matrix**: Added `autotune version` command and `--json` export displaying platform, compiler, target triple, and timing calibration status.
- **Side-by-Side Experiment Diffing**: Added `autotune diff <report_a> <report_b>` command for comparative delta analysis of search runs.
- **Graphviz DOT Control Flow Graph**: Added `--export-dot` to `autotune inspect` for exporting basic block flowcharts into Graphviz DOT format.
- **Basic Block Heatmap Visualization**: Added instruction density bars (`████░░░░`) inside ASCII CFG terminal inspection.
- **Simulated Annealing Mutation Scheduling**: Integrated adaptive temperature decay into GA mutation rate schedule for balanced exploration and exploitation.
- **Selection Pressure & Rank Selection**: Added probabilistic selection pressure and rank-proportional selection operators in `Selector`.
- **Occam Parsimony Penalty**: Applied subtle pipeline length penalty in `FitnessEvaluator` to favor simpler, cleaner pass sequences.
- **Google Bazel Build Exporter**: Added native Bazel `genrule` export format to `autotune export --format bazel`.
- **Hermetic Dockerfile Container Export**: Added Dockerfile generator to `autotune export --format docker` for containerized benchmarking.
- **Chrome Tracing / Perfetto Event Traces**: Added event trace export in `autotune export --format trace`.
- **Benchmark Kernels Suite Expansion**: Added 4 new high-performance benchmark kernels:
  - BLAS-2 Dense Matrix-Vector Multiplication (`examples/gemv/kernel.c`)
  - Cooley-Tukey Radix-2 Fast Fourier Transform (`examples/fft/kernel.c`)
  - N-Body Gravitational Simulation (`examples/nbody/kernel.c`)
  - Compressed Sparse Row Matrix-Vector Multiplication (`examples/spmv/kernel.c`)
- **Peak Resident Memory (RSS) Tracking**: Integrated `ru_maxrss` child process memory tracking in `SandboxExecutor` and `PerformanceRunner`.
- **LRU Cache Quota & Selective Invalidation**: Added `enforce_lru_quota()` and `autotune cache clear-benchmarks` to selectively clear timing without losing bitcodes.
- **Jaccard Sequence Similarity Metric**: Added `similarity_to()` to `Individual` candidate model for provenance tracking.
- **Markdown History Export**: Added `autotune history --markdown` table output.
- **Automated Shell Benchmark Exporter**: Added `--export-sh` flag to `autotune doctor`.

### Changed
- **CI/CD Reliability**: Added multi-version LLVM search paths and GITHUB_PATH exports for Ubuntu and macOS runners.
- **Statistical Significance Guarding**: Added `--min-samples` threshold enforcement in `autotune guard`.

---

## [0.4.0] - 2026-09-02 — Enterprise Open-Source Edition

### Added
- **ASCII Control Flow Graph (CFG) Visualizer**: Added `--cfg` option to `autotune inspect` to render basic block flowcharts and instruction counts in the terminal.
- **Interactive Project Initialization**: Added `autotune init` to scan projects, write `.autotune.yml`, and configure `.gitignore`.
- **Shell Autocompletion**: Added `autotune completion [bash|zsh|fish]` generator for instant tab completion in developer terminals.
- **Pass DAG Optimizer**: Added `PassDAGOptimizer` to prune redundant consecutive idempotent passes in the genetic search loop.
- **Modern Build System Exporters**: Extended `autotune export` with native `ninja` build rules and `meson` build scripts.
- **CMake Drop-In Integration**: Added `cmake/Autotune.cmake` with `autotune_optimize_target()` macro for CMake build integration.
- **Reusable GitHub Action**: Added `action.yml` for turnkey CI performance regression guarding on pull requests.
- **Automated PR Markdown Tables**: Added `autotune markdown` and `autotune guard --comment-markdown` for GitHub CI PR commenting.
- **Team Cache Distribution**: Added `autotune cache export` and `autotune cache import` for sharing warm compilation caches.
- **CSV Matrix Export**: Added `autotune bench-suite --csv <path>` for spreadsheet benchmark analysis across whole suites.
- **Modern C++20 Standard Support**: Added automatic `-std=c++20` flags and C++ standard library routing.
- **Link-Time Optimization (LTO)**: Added full LTO and ThinLTO compilation support (`-flto`, `-flto=thin`).
- **Sanitizer Verification**: Added memory sanitizer verification (`-fsanitize`) during native binary generation.
- **Microarchitecture-Aware Pass Biasing**: Added target-specific seeds for Apple Silicon NEON and x86-64 AVX2/AVX-512 architectures.
- **New Benchmark Kernel**: Added 2D Image Convolution (`examples/conv2d/kernel.c`) with nested spatial filter operations.
- **Open-Source Community Governance**: Added `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1), and `SECURITY.md`.
- **Automated Issue & PR Templates**: Added GitHub YAML forms for bug reports, feature requests, and benchmark submissions.

### Changed
- **Interactive Progress Bar**: Upgraded `autotune doctor` search UI with Unicode progress bars, real-time speedup tracking, and diversity metrics.
- **HTML Report Generator**: Added dark-mode glassmorphic styling, responsive layout, and one-click copy-to-clipboard buttons.
- **GitHub Actions CI**: Upgraded matrix across Ubuntu and macOS on Python 3.11 and 3.12 with automated profile and lint checks.

---

## [0.3.0] - 2026-08-30
- Initial production release with LLVM Pass Registry, Genetic Algorithm search, AST heuristic profiling, and statistical verification.
