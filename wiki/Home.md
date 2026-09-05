# Autotune Documentation Wiki

Welcome to the Autotune technical documentation wiki. Autotune is an automated phase-ordering compiler optimization framework and continuous integration performance guard for LLVM, C, and C++ workloads.

---

## Overview

Modern compilers such as Clang apply a fixed sequence of optimization passes when invoked with `-O3` or `-O2`. While these standard pipelines provide reasonable average performance across arbitrary codebases, they are inherently sub-optimal for specific computational kernels such as matrix operations, stencil computations, tensor contractions, and image filters. Certain pass orderings can inadvertently destroy loop properties before vectorization or fail to expose memory access patterns needed by downstream optimization phases.

Autotune addresses this limitation through:

1. **Phase-Ordering Exploration**: Exploring the combinatorial space of LLVM transformations using multi-fidelity genetic search and microarchitecture-aware seeds.
2. **Empirical Verification**: Directly executing candidate binaries under isolated, high-resolution timing harnesses rather than relying on analytical heuristics.
3. **Statistical Rigor**: Enforcing hypothesis testing (Mann-Whitney U test, p < 0.01) and effect size measurements (Cohen's d >= 0.8) to eliminate noise-induced false positives.
4. **Continuous Integration Performance Guarding**: Automated GitHub Action integration to detect performance regressions in pull requests before merging.

---

## Quick Navigation

- [[Architecture and Design]]: Technical internals of the pass manager, genetic algorithm, and execution harness.
- [[CLI Reference and Workflow]]: Detailed command-line interface documentation for all subcommands.
- [[LLVM Phase Ordering Guide]]: Theoretical background on compiler optimization ordering and phase interactions.
- [[CI CD Performance Guard Action]]: Guide to configuring and running the GitHub Action in CI/CD pipelines.

---

## Installation

Autotune requires Python 3.11 or 3.12 and an LLVM toolchain with `clang` and `opt` installed (versions 14 through 22 supported).

```bash
pip install autotune-doctor
```

Or install from source:

```bash
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor
pip install -e ".[dev]"
```

Verify the local toolchain:

```bash
autotune doctor
```
