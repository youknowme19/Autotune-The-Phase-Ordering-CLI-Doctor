# Autotune Documentation Library

Welcome to the complete technical documentation for **Autotune — The Phase-Ordering CLI Doctor**.

This documentation hierarchy provides comprehensive references, architectural guides, CLI specifications, and reproducibility protocols for developers, compiler engineers, and researchers.

---

## 📚 Documentation Index

### 🚀 Getting Started & Basics
- [**Getting Started**](getting-started.md): Overview, core concepts, and project philosophy.
- [**Installation Guide**](installation.md): Requirements, Python virtual environment, Homebrew LLVM/Clang setup, and verification.
- [**Quickstart Guide**](quickstart.md): Copy-pasteable 5-minute tutorial running your first optimization search.
- [**Usage Workflows**](usage.md): Command-line workflows, tri-state execution modes, and batch benchmarking.

### 🛠️ CLI & Configuration Reference
- [**CLI Command Reference**](cli-reference.md): Full reference for `doctor`, `diagnose`, `search`, `bench-suite`, and `config`.
- [**Configuration Guide**](configuration.md): Complete list of parameters, environment variables, and keyring options.

### 🏗️ Architecture & Core Engine
- [**System Architecture**](architecture.md): Full end-to-end component data flow and source file mapping.
- [**Pipeline Search Engine**](pipeline-search.md): LLVM NPM pass representation, canonicalization, GA operators, and selection.
- [**Fitness & Evaluation System**](fitness-and-evaluation.md): Baseline-normalized fitness formula ($\text{normalized\_speed}$) and failure handling.
- [**Multi-Fidelity & Baseline Gate**](multi-fidelity.md): `LOW`/`MEDIUM`/`HIGH` screening levels and baseline-gated candidate pruning.
- [**Persistent Cache Architecture**](caching.md): Disaggregated metrics, atomic writes (`tempfile` + `fsync` + `os.replace`), and corruption recovery.
- [**Correctness Validation**](correctness.md): Verification strategies (exact byte diffs, numeric tolerance $\epsilon$, SHA-256 digests).
- [**LLM-Guided Seeding**](llm-seeding.md): AST feature extraction, LLM client prompts, offline fallback, and `--no-llm` mode.
- [**Final Confirmation Protocol**](confirmation.md): `run_final_confirmation()` protocol and search vs. confirmation separation.

### 🔬 Science, Reproducibility & Benchmarking
- [**Reproducibility Guide**](reproducibility.md): Deterministic random seeding (`--seed 42`), hardware/toolchain requirements, and manifests.
- [**Benchmarking Methodology**](benchmarking.md): In-process high-precision timing (`__AUTOTUNE_TIME_NS__`), macOS vs. Linux perf counters.
- [**Scientific Validation Results**](scientific-validation.md): Empirical evidence, matrix_transpose 1.26x speedup, Phase G confirmation, and PolyBench results.
- [**Known Limitations & Scope**](limitations.md): Workload dependence, small search budgets, LLVM/arch dependencies, and non-overclaiming rules.

### 💻 Development & Contributions
- [**Development Guide**](development.md): Development environment setup, codebase organization, and CI/CD pipelines.
- [**Testing Guide**](testing.md): Running Pytest, writing unit/integration tests, and coverage enforcement.
- [**Extending Autotune**](extending-autotune.md): Adding passes, correctness validators, benchmark runners, or fitness functions.
- [**Contributing Guidelines**](contributing.md): Contribution rules, PR standards, issue reporting, and evidence requirements.
- [**Release Checklist**](release-checklist.md): Step-by-step pre-release verification checklist.
- [**Troubleshooting Guide**](troubleshooting.md): Common errors, symptoms, root causes, and verified solutions.
- [**Changelog**](changelog.md): Complete version history and release notes.

---

## 🎯 Documentation Navigation Map

```text
                     README.md
                        │
       ┌────────────────┴────────────────┐
       ▼                                 ▼
Getting Started                    Architecture
       │                                 │
  Installation                      Core Systems
       │                           (Cache, GA, Fitness)
   Quickstart                            │
       │                         Scientific Validation
 CLI Reference                           │
       │                            Reproducibility
  Troubleshooting                        │
                                   Contributing
```
