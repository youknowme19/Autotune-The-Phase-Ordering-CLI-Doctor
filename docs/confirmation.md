# Final Confirmation Protocol

This document explains why search-time observations are separated from final confirmation results, and details the `run_final_confirmation()` execution protocol.

---

## 🔬 Search Result vs. Confirmed Result

During Genetic Algorithm search, candidates are evaluated using small repetition counts ($N=2-3$ at `LOW` fidelity) to maintain search speed. Search-time measurements contain ambient system noise and transient OS background scheduling fluctuations.

> **Rule of Scientific Integrity**: Search-time timing measurements must NEVER be treated as final scientific performance claims.

---

## 🏃 Final Confirmation Workflow (`run_final_confirmation()`)

After the Genetic Algorithm completes:

1. **Fresh Binary Recompilation**: Re-compiles both the baseline `-O3` binary and the winning candidate binary from scratch.
2. **Fresh Timing Execution**: Performs `--confirm-runs` (default 20) fresh timing repetitions for both binaries with `--fresh-benchmark` enabled (bypassing performance timing cache).
3. **Statistical Hypothesis Testing**:
   - Calculates median, mean, stddev, CV, IQR, and MAD metrics.
   - Computes Welch's two-sample $t$-test ($t, df, p$).
   - Computes Mann-Whitney $U$ test ($U, z, p$).
   - Computes Cohen's $d$ effect size.
4. **Final Classification Assignment**:
   - `REPRODUCED_SPEEDUP`: Confirmed speedup $> 1.0$ and $p < 0.05$.
   - `PARITY`: Confirmed speedup $\approx 1.0$ or $p \ge 0.05$.
   - `STATISTICAL_REGRESSION`: Confirmed speedup $< 1.0$ ($p < 0.05$).
