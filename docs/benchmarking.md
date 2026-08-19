# Benchmarking Methodology

This document details Autotune's latency measurement mechanics, timing backends, and noise analysis protocols.

---

## ⏱️ In-Process High-Precision Monotonic Timing

Autotune measures execution latency using in-process monotonic timing markers ([`src/autotune/sandbox/executor.py`](file:///Volumes/SSD/autotune/src/autotune/sandbox/executor.py) & [`src/autotune/benchmark/macos.py`](file:///Volumes/SSD/autotune/src/autotune/benchmark/macos.py)).

### Microsecond Marker Injection:
The benchmark harness wraps workload execution loops with microsecond timing probes:
```c
uint64_t start_ns = get_monotonic_time_ns();
// Workload loop
uint64_t elapsed_ns = get_monotonic_time_ns() - start_ns;
printf("__AUTOTUNE_TIME_NS__:%llu\n", elapsed_ns);
```

Before output validation or diffing, `strip_autotune_time_markers()` filters timing lines from `stdout` to prevent false correctness divergences.

---

## 📊 Summary Statistics & Noise Analysis

For every benchmark execution ($N$ measured repetitions), Autotune computes:
- **Median ($M$)**: Robust central tendency measure (primary metric for fitness evaluation).
- **Mean ($\mu$)**: Arithmetic average latency.
- **Standard Deviation ($\sigma$)**: Sample standard deviation.
- **Coefficient of Variation (CV)**: $CV = \frac{\sigma}{\mu}$. If $CV > 0.15$, Autotune flags `timing_stability_warning = True`.
- **Interquartile Range (IQR)**: $IQR = Q_{75} - Q_{25}$.
- **Median Absolute Deviation (MAD)**: $MAD = \text{median}(|x_i - M|)$.

---

## 💻 Backend Differences: macOS vs. Linux

- **macOS (Apple Silicon ARM64)**: Uses high-precision `mach_absolute_time()` fallback timing backend because Linux `perf_event_open` hardware performance counters are unavailable.
- **Linux (x86_64)**: Integrates Linux `perf` subsystem for cycle counting and hardware counter profiling when available.
