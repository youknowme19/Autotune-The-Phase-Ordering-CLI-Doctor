# Scientific Benchmark Evidence & Empirical Manifest

Autotune v0.2.1 evaluates custom LLVM pass sequences against the standard Clang `-O3` compiler pipeline. Every candidate evaluated undergoes strict **sandbox output correctness verification** (stdout checksumming and exit code validation) and **baseline gating** to prune performance regressions.

---

## 1. Flagship Confirmed Win: C Matrix Transpose

- **Target Source**: [`examples/matrix_transpose/kernel.c`](../examples/matrix_transpose/kernel.c) ($N=512$, $100$ iterations)
- **Baseline Compiler (`clang -O3`)**: **70.446 ms** (StdDev: 3.009 ms)
- **Winning Pass Pipeline**: `function(gvn,mem2reg,invalidate<all>,gvn,gvn-hoist)`
- **Autotune Candidate Latency**: **55.858 ms** (StdDev: 4.738 ms)
- **Confirmed Speedup**: **1.26x** (**20.7% Runtime Reduction**)
- **Statistical Significance**: Welch $t$-test $p = 1.18 \times 10^{-152}$, Mann-Whitney $U$ $p = 2.47 \times 10^{-33}$, Bootstrap 95% CI **$[1.25x, 1.32x]$**, Cohen's $d = 3.72$.
- **Correctness Verification**: **PASS** (`Matrix Transpose Check B[256][256]: 1313.2899`).
- **Reproducibility**: Confirmed under deterministic random seed (`--seed 42`).

---

## 2. Multi-Workload Empirical Matrix (Small-to-Medium Search Budgets)

Under short offline evaluation budgets ($P=10, G=5$ to $P=20, G=10$, 50 to 200 candidate evaluations), standard Clang `-O3` on LLVM 22 is an extremely competitive baseline. Autotune's baseline gating mechanism safely prunes regressions, ensuring that 100% of accepted candidate prescriptions match reference output and meet or exceed baseline performance:

| Workload Category | Target Kernel | Baseline `-O3` Latency (ms) | Best Autotune Latency (ms) | Confirmed Speedup | Search Budget | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Matrix Operations** | `matrix_transpose.c` | 70.45 ms | **55.86 ms** | **1.26x** | $P=20, G=10$ | **PROVEN WIN** |
| | `matrix_mult.c` | 14.39 ms | 14.39 ms | **1.00x** | $P=10, G=5$ | **TIE** |
| **PolyBench/C** | `2mm.c` | 24.30 ms | 24.30 ms | **1.00x** | $P=10, G=5$ | **TIE** |
| | `atax.c` | 6.82 ms | 6.82 ms | **1.00x** | $P=10, G=5$ | **TIE** |
| | `bicg.c` | 4.85 ms | 4.85 ms | **1.00x** | $P=10, G=5$ | **TIE** |
| | `cholesky.c` | 6.05 ms | 6.05 ms | **1.00x** | $P=10, G=5$ | **TIE** |
| | `gemm.c` | 7.53 ms | 7.53 ms | **1.00x** | $P=10, G=5$ | **TIE** |
| **Cryptographic** | `sha256.c` | 5.59 ms | 5.59 ms | **1.00x** | $P=10, G=5$ | **TIE** |
| **Loops & Vectorization**| `simple_loop.c` | 2.58 ms | 2.58 ms | **1.00x** | $P=10, G=5$ | **TIE** |
| | `vector_sum.c` | 3.21 ms | 3.21 ms | **1.00x** | $P=10, G=5$ | **TIE** |

---

## 3. Factors Influencing Optimization Search

Performance measurements and pass ordering effectiveness depend on:
1. **CPU Microarchitecture**: Hardware vector units, L1/L2 cache sizes, and memory prefetchers (e.g. Apple Silicon ARM64 vs x86_64 AVX-512).
2. **LLVM Toolchain Version**: LLVM New Pass Manager (NPM) pass interactions (tested under Homebrew Clang version 22.1.8).
3. **Phase-Ordering Sensitivity**: Codebases where standard pass sequences execute unrolling before vectorization or hoist invariant code late.
4. **Thermal & System Noise**: High-precision nanosecond timing measurements require multiple repetitions (`--confirm-runs 20`) to eliminate system scheduling noise.
