# Scientific Validation Summary

This document summarizes the official, frozen empirical validation findings of the Autotune project.

---

## 🧪 Validated Primary Result (`matrix_transpose`)

- **Workload**: [`examples/matrix_transpose/kernel.c`](../examples/matrix_transpose/kernel.c) ($N=512$, $100$ iterations)
- **Winning Pass Sequence**: `['gvn', 'mem2reg', 'invalidate<all>', 'gvn', 'gvn-hoist']`
- **Canonical NPM Pipeline**: `function(gvn,mem2reg,invalidate<all>,gvn,gvn-hoist)`
- **Phase G Confirmation Protocol**: 100 warmups per binary, 100 baseline + 100 candidate fresh timing measurements with deterministic random interleaving (seed 42).
- **Baseline (`-O3`) Median**: **70.446 ms** (StdDev: 3.009 ms, CV: 0.0418)
- **Candidate Median**: **55.858 ms** (StdDev: 4.738 ms, CV: 0.0829)
- **Confirmed Speedup**: **1.26x** (**20.7% Runtime Reduction**)
- **Welch $p$-value**: $1.18 \times 10^{-152}$
- **Mann-Whitney $U$ $p$-value**: $2.47 \times 10^{-33}$
- **Bootstrap 95% Confidence Interval (10,000 Iterations)**: **$[1.25x, 1.32x]$**
- **Cohen's $d$ Effect Size**: **3.72** (Extremely Large Effect)
- **Correctness Status**: **PASS** (`Matrix Transpose Check B[256][256]: 1313.2899`)

---

## 📊 PolyBench/C Generalization Summary

All workloads evaluated under `--no-llm -p 10 -g 5 -s 42 --confirm-runs 20`:

| Benchmark | Baseline `-O3` Median | Candidate Best Median | Confirmed Speedup | Correctness Output | Classification |
|---|---|---|---|---|---|
| `2mm` | 22.409 ms | 86.923 ms | **0.26x** | `2mm Check D[64][64]: 1038.6074` | **`STATISTICAL_REGRESSION`** |
| `cholesky` | 5.194 ms | 9.949 ms | **0.52x** | `Cholesky Check A[64][64]: 136728277...` | **`STATISTICAL_REGRESSION`** |
| `atax` | 3.486 ms | 5.838 ms | **0.60x** | `Atax Check y[128]: 974.3183` | **`STATISTICAL_REGRESSION`** |
| `gemm` | 5.959 ms | 45.592 ms | **0.13x** | `GEMM Check C[64][64]: 4767.7063` | **`STATISTICAL_REGRESSION`** |
| `bicg` | 3.022 ms | 3.930 ms | **0.77x** | `BiCG Check s[128]: 68.8340...` | **`STATISTICAL_REGRESSION`** |

> **Scientific Finding**: Autotune demonstrates that automated phase-order search can discover statistically robust workload-specific improvements beyond `-O3`, but the current evidence does not establish universal optimization superiority or broad cross-workload generalization.
