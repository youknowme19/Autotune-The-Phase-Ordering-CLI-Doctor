# Multi-Fidelity Screening & Baseline Gate

This document details Autotune's multi-fidelity measurement system and baseline gate candidate pruning.

---

## 🚦 Measurement Fidelity Stages

To optimize evaluation efficiency, Autotune evaluates candidate pass sequences across three fidelity stages:

| Fidelity Stage | Warmup Runs | Measured Timing Repetitions | Purpose |
|---|---|---|---|
| **`LOW`** | 2 | 2–3 (`--screen-runs`) | Rapid screening of new candidate proposals |
| **`MEDIUM`** | 3 | 7 | Intermediate population refinement |
| **`HIGH`** | 5 | 20 (`--confirm-runs`) | High-precision candidate confirmation |

---

## 🚧 Baseline Gate Screening (`--baseline-gate`)

Measuring every candidate proposal across 20 repetitions is computationally expensive. Autotune implements a **Baseline Gate** during `LOW` fidelity screening:

```python
if self.baseline_gate and evaluated.normalized_speed is not None:
    if evaluated.normalized_speed < self.baseline_gate_threshold:  # default 0.80
        evaluated.screened = True
```

### Pruning Mechanics:
- If a candidate achieves $\text{normalized\_speed} < 0.80$ at `LOW` fidelity ($20\%$ slower than `-O3`), it is marked as `screened = True` and rejected from promotion to `MEDIUM` or `HIGH` fidelity.
- **Computation Savings**: Baseline gate pruning prunes $>64\%$ of non-improving proposals at `LOW` fidelity, saving over $80\%$ of repetition timing overhead during search.
