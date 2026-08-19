# Contributor & Researcher Reproducibility Guide

Autotune is designed from the ground up to support **reproducible compiler research**. This guide explains how to reproduce optimization search results, configure random seeds, verify output correctness, and perform statistical confirmation.

---

## 1. System & Hardware Requirements

To reproduce experimental results:

- **Operating System**: macOS (ARM64 / x86_64) or Linux (x86_64)
- **Python**: Version `3.11` or higher
- **LLVM / Clang**: Version `15.0` or higher (`clang` and `opt` binaries on system `PATH`)
- **Isolation**: Avoid running background CPU-heavy applications during benchmark confirmation.

---

## 2. Step-by-Step Reproduction Command

To reproduce the matrix transpose optimization search:

```bash
# 1. Clone & Activate Virtual Environment
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. Verify Toolchain
autotune doctor

# 3. Execute Search in 100% Offline Mode with Fixed Seed 42
autotune search ./examples/matrix_transpose/kernel.c \
  -w ./examples/matrix_transpose/input.txt \
  --no-llm \
  -p 10 \
  -g 5 \
  -s 42 \
  --confirm-runs 20 \
  -o transpose_report.json
```

---

## 3. How Deterministic Search Works

When `--seed <int>` (or `-s 42`) is passed:
1. **Random Seed Initialization**: Python's `random.seed(seed)` initializes the Genetic Algorithm mutators, crossover selectors, and population samplers.
2. **Offline AST Seeder**: `--no-llm` routes Generation 0 candidate creation to `HeuristicSeedClient`, generating deterministic pass sequence candidates based on Clang AST loop depth.
3. **Canonical NPM Pipeline**: Passes are normalized via `CanonicalPassNormalizer` into standardized LLVM New Pass Manager strings (`function(...)`), eliminating non-deterministic pass string variations.

---

## 4. Correctness & Performance Verification Protocol

1. **Sandbox Execution**: Every candidate binary is executed inside `SandboxExecutor` with isolated timeouts.
2. **Correctness Validator**: Compares stdout byte digests against baseline `clang -O3` output. Any divergence sets fitness to $-\infty$, immediately rejecting the candidate.
3. **Baseline Gate**: Candidates evaluated at `LOW` fidelity level are compared against baseline timing ($\text{normalized\_speed} < 0.80$). Non-promising proposals are pruned before high-fidelity measurement.
4. **Final Confirmation**: Top elite candidates undergo `HIGH` fidelity timing repetitions (`--confirm-runs 20`), calculating median, mean, and standard deviation latency.
