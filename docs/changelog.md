# Changelog

All notable changes to the **Autotune** project are documented in this file.

---

## [0.1.0] - 2026-08-19

### 🚀 Hardened Engine Features
- **Disaggregated Persistent Cache Architecture**: Implemented multi-layer caching with distinct SHA-256 identities for compilation, correctness, and performance. Added atomic storage safety (`tempfile.NamedTemporaryFile` + `fsync` + `os.replace`) and automatic corruption recovery (`cache_corruption_recovered = True`).
- **Baseline-Normalized Fitness Formula**: Implemented $\text{normalized\_speed} = \frac{\text{baseline\_median\_ns}}{\text{candidate\_median\_ns}}$, prioritizing candidates with higher normalized speed and assigning $float("-inf")$ to invalid candidates.
- **Multi-Fidelity Screening & Baseline Gate**: Implemented `LOW` ($2, 2/3$), `MEDIUM` ($3, 7$), and `HIGH` ($5, 20$) measurement stages. Added baseline gate screening to prune non-promising candidates ($\text{normalized\_speed} < 0.80$) at `LOW` fidelity.
- **Independent Final Confirmation Protocol**: Added `run_final_confirmation()` post-GA search re-measuring baseline and winner independently under high repetition counts.
- **Cross-Workload Seed Archive**: Implemented `SeedArchiveManager` to persist confirmed speedup pass sequences in `.autotune/seeds/`.
- **Typer CLI Enhancements**: Added flags `--fidelity`, `--screen-runs`, `--confirm-runs`, `--baseline-gate`, `--fail-on-regression`, and `--regression-threshold`.

### 🔬 Empirical Scientific Validation
- **Phase G Interleaved Confirmation**: Confirmed **1.26x speedup** ($20.7\%$ runtime reduction, $70.446\text{ ms} \rightarrow 55.858\text{ ms}$, $p = 2.47 \times 10^{-33}$, Bootstrap 95% CI $[1.25x, 1.32x]$) for `matrix_transpose` under 100-sample interleaved measurement protocol with 100% program correctness.
- **PolyBench/C Generalization Evaluation**: Completed 5-workload validation across `2mm`, `cholesky`, `atax`, `gemm`, and `bicg`, transparently documenting performance regressions under small offline search budgets.

### 🧪 Test Suite Hardening
- Expanded test suite to **51/51 passing tests** ($100\%$ pass rate), including end-to-end multi-layer cache integration tests (`test_cache_end_to_end.py`) and unit tests for hardened search features (`test_hardened_features.py`).
