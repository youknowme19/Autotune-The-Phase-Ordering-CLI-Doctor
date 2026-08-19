# Known Limitations & Scope

This document explicitly outlines the technical, architectural, and scientific scope boundaries of the Autotune project.

---

## ⚠️ Explicit Limitations

1. **Workload-Specific Scope**: Autotune discovers custom LLVM pass prescriptions that yield strong speedups on specific kernels (e.g., **1.26x speedup** on `matrix_transpose`), but it does **NOT** universally outperform Clang `-O3` across all C programs.
2. **PolyBench Search Budget Limitations**: Under small offline GA budgets ($P=10, G=5$, `--no-llm`), Autotune produced performance regressions ($0.13x - 0.77x$) on dense linear algebra PolyBench workloads (`2mm`, `cholesky`, `atax`, `gemm`, `bicg`).
3. **Compiler Toolchain & LLVM Version Dependence**: Pass pipeline execution depends on LLVM NPM semantics. Pass options and NPM canonical strings are tailored to Homebrew LLVM 22.1.8 / Clang 22.1.8.
4. **Hardware Architecture Dependence**: Optimization speedups observed on Apple Silicon ARM64 (M4) reflect ARM64 memory subsystem and cache characteristics and may vary on x86_64 architectures.
5. **No Claim of Universal Optimization Superiority**: We explicitly reject claims that Autotune "universally beats `-O3`" or "generalizes across all benchmark suites".

---

## 🔒 Scientific Integrity Commitment

Autotune's reporting architecture strictly adheres to three principles:
- **Never claim a speedup unless final confirmation independently verifies it.**
- **Always report correctness failures and regressions transparently.**
- **Preserve raw timing sample data without trimming or smoothing in primary reports.**
