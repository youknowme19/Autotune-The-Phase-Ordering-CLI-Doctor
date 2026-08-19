# Getting Started with Autotune

**Autotune — The Phase-Ordering CLI Doctor** is an automated compiler optimization system designed to explore, evaluate, and verify custom LLVM pass sequences for C/C++ workloads.

---

## 🎯 What is Autotune?

Standard C/C++ compilers like Clang use fixed, hardcoded optimization pipeline sequences when passed flags like `-O2` or `-O3`. However, the optimal ordering of compiler transformations depends heavily on the specific structure of the source code. A phase-ordering sequence tailored to a specific kernel can often outperform standard compiler flags.

Autotune automates the discovery of these custom LLVM pass sequences using a **multi-fidelity Genetic Algorithm (GA)** guided by optional **LLM seed proposals**.

---

## 💡 Core Capabilities

1. **AST Structural Feature Extraction**: Analyzes C/C++ source code via Clang AST dumps to extract loop depth, memory access patterns, floating-point operations, and branching complexity.
2. **LLVM Pass Pipeline Canonicalization**: Normalizes proposed pass sequences into modern LLVM New Pass Manager (NPM) syntax, deduplicating pass combinations and establishing deterministic cache identities.
3. **Multi-Fidelity Search & Baseline Gate**: Evaluates candidates across `LOW`, `MEDIUM`, and `HIGH` measurement fidelities, pruning non-promising candidates ($\text{normalized\_speed} < 0.80$) early to save runtime overhead.
4. **Disaggregated Atomic Cache**: Prevents redundant compilations and executions across runs using SHA-256 cache keys, atomic file writes (`tempfile` + `fsync` + `os.replace`), and automatic corruption recovery.
5. **Program Correctness Verification**: Enforces output equivalence against trusted `-O3` baseline runs using pluggable validators (exact byte diffs, numeric tolerance $\epsilon = 10^{-6}$, SHA-256 digests).
6. **Independent Final Confirmation**: Re-measures winning candidates independently post-search using high-repetition fresh timing executions to ensure statistical rigor.

---

## 🔬 Core Engineering Philosophy

> **"Autotune does not ask the AI whether an optimization is better. It experimentally proves it."**

AI models (OpenAI, Anthropic, Gemini, or offline AST heuristics) act strictly as **seed generators** for Generation 0 proposals. They **never** directly decide the winner. Every candidate pipeline must experimentally demonstrate program correctness and statistical speedup under sandbox execution.

---

## 📍 Next Steps

- Proceed to the [**Installation Guide**](installation.md) to set up Autotune and LLVM.
- Jump straight to the [**Quickstart Guide**](quickstart.md) to optimize your first C workload.
