# Fitness & Evaluation System

This document explains Autotune's baseline-normalized fitness formulation, correctness gating, and failure handling.

---

## 📐 Baseline-Normalized Fitness Formula

Autotune evaluates candidate pass sequences relative to the baseline `-O3` execution latency:

$$\text{normalized\_speed} = \frac{\text{baseline\_median\_ns}}{\text{candidate\_median\_ns}}$$

### Interpretation Scale:
- **$\text{normalized\_speed} > 1.0$**: Performance improvement over `-O3` (e.g., $1.25x = 20\%$ speedup).
- **$\text{normalized\_speed} \approx 1.0$**: Performance parity with `-O3`.
- **$\text{normalized\_speed} < 1.0$**: Performance regression against `-O3`.
- **$\text{normalized\_speed} = 0.0$**: Invalid candidate (failed compilation or correctness check).

---

## 🚫 Failure Handling & Negative Fitness

Candidates that fail any stage of compilation or execution are strictly isolated and assigned negative infinite fitness:

```python
if not compile_success or not is_correct:
    individual.compilation_success = False (or correctness_success = False)
    individual.fitness = float("-inf")
    individual.normalized_speed = 0.0
    individual.is_valid = False
```

Invalid candidates sort after all valid candidates in GA selection (`individual_a < individual_b` checks `normalized_speed` for valid candidates, prioritizing higher normalized speed).

---

## 🎯 Why Baseline Normalization?

1. **Hardware-Independent Objective Function**: Raw nanosecond latencies vary across hardware platforms and CPU clock frequencies. Normalizing against baseline `-O3` yields a dimensionless optimization ratio.
2. **Direct Parity Boundary**: $1.0$ represents the exact boundary between speedup and regression, simplifying baseline gate pruning.
