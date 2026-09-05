# Architecture and Design

Autotune is structured as a modular compiler optimization engine consisting of five core subsystems:

1. **LLVM Pipeline Subsystem**: Pass representation, NPM nesting, and validation.
2. **Search Engine Subsystem**: Genetic algorithm, mutation operators, and population management.
3. **Execution and Measurement Subsystem**: Sandboxed timing harness, CPU affinity, and warmup controls.
4. **Statistical Verification Subsystem**: Multi-fidelity screening, Mann-Whitney U testing, and effect size calculation.
5. **Persistence and Artifact Subsystem**: Cache management, run manifests, and report generation.

---

## 1. LLVM Pipeline Subsystem

Autotune interfaces directly with LLVM's New Pass Manager (NPM). Candidate pass sequences are represented as an ordered list of pass identifiers.

### Type-Aware NPM Pass Classification

LLVM passes operate at different granularities within the intermediate representation:
- **ModulePass**: Operates over the entire translation unit (e.g., `inline`, `always-inline`, `globalopt`).
- **FunctionPass**: Operates over individual function bodies (e.g., `sroa`, `gvn`, `instcombine`, `sccp`).
- **LoopPass**: Operates over natural loops, requiring loop-mssa adaptors in NPM (e.g., `licm`).

The `LLVMPassRegistry` automatically organizes candidate sequences into syntactically valid NPM pipeline expressions:

```text
Input: ['inline', 'mem2reg', 'licm', 'gvn']
NPM Output: inline,function(mem2reg,loop-mssa(licm),gvn)
```

This prevents pass manager nesting crashes while preserving the requested relative pass ordering.

---

## 2. Search Engine Subsystem

Autotune employs an elitist genetic algorithm designed specifically for compiler phase-ordering problems.

### Population Initialization

Generation 0 is constructed using a balanced five-component distribution:
- **20% Seed Archive**: Microarchitecture-biased sequences proven effective on common computational kernels (e.g., SIMD vectorization sequences, loop unrolling seeds).
- **20% Standard Compiler Defaults**: Sequences derived from default `-O2` and `-O3` pipeline templates.
- **20% Heuristic Proposals**: Sequences generated from target source AST analysis (e.g., detecting nested loops, floating-point reductions, or memory copies).
- **20% Conservative Sequences**: Minimal 2–3 pass sequences focused on canonicalization (`mem2reg`, `sccp`, `instcombine`).
- **20% Uniform Random Sequences**: Randomly sampled valid passes to preserve genetic diversity.

### Genetic Operators

- **Tournament Selection (k=3)**: Selects parent individuals based on empirical fitness while maintaining selection pressure.
- **Single-Point Crossover**: Combines pass prefix from Parent A with pass suffix from Parent B.
- **Mutation Operators**: Insertion, deletion, adjacent swap, and substitution of valid passes.
- **Duplicate Suppression**: Memoization table keyed by canonical pipeline SHA256 ensures identical pass sequences are never redundantly executed.

---

## 3. Execution and Measurement Subsystem

To ensure timing accuracy:
- **Warmup Iterations**: A configurable number of initial runs are executed and discarded to allow CPU frequency scaling and instruction cache warm-up.
- **Microsecond Clock**: Measurements utilize monotonic high-precision timing interfaces (`clock_gettime` with `CLOCK_MONOTONIC_RAW` on Linux, `mach_absolute_time` on macOS).
- **Correctness Verification**: The output of every candidate binary is verified against the baseline execution output to prevent semantic divergence or miscompilations.

---

## 4. Statistical Verification Subsystem

Autotune uses a two-tier multi-fidelity evaluation protocol:

1. **Screening Phase (Low Fidelity)**: All candidates in a generation are evaluated with a small sample size (e.g., 3–5 runs). Candidates that do not demonstrate a baseline threshold improvement are discarded immediately.
2. **Confirmation Phase (High Fidelity)**: Top-performing candidates undergo rigorous testing with larger sample sizes (e.g., 10–20 runs).

### Statistical Criteria for Speedup Acceptance

A candidate is only classified as a confirmed improvement if:
- The speedup ratio exceeds the required threshold (default: >= 1.05x).
- The non-parametric Mann-Whitney U test confirms that candidate execution times are strictly smaller than the baseline with significance level `p < 0.01`.
- The effect size satisfies Cohen's `d >= 0.8` (large effect).
- The coefficient of variation (CV) for candidate execution samples does not exceed 0.20 (20%), ensuring the result was not an artifact of system noise.
