# Autotune Benchmarking & Measurement Specification

Autotune emphasizes honest, reproducible performance measurements across platforms.

## Measurement Backends

```text
PerformanceRunner (Abstract Base)
├── MacOSPerformanceRunner (High-precision CPU timing backend)
└── LinuxPerformanceRunner (perf_event_open hardware performance counter backend)
```

## Platform Measurement Policies

1. **No Fake Hardware Counters**: If hardware counters (`perf_event_open`) are unavailable (e.g., native macOS), Autotune MUST NOT output fake cycle counts or pseudo-counter metrics.
2. **Transparent Diagnostic Warnings**: When running on macOS, Autotune reports `[WARN] E-01: Hardware performance counters unavailable. Using macOS timing backend.`
3. **Statistical Sample Hygiene**:
   - Runs candidate binaries $N$ times (default: 10).
   - Computes median execution time, standard deviation, and relative noise fraction ($\frac{\text{stddev}}{\text{median}}$).
   - Flags measurement noise above threshold (default: 5%) with `E-05`.

## Result Metadata Schema

Every benchmark result captures comprehensive environment metadata:
```json
{
  "platform": "Darwin",
  "architecture": "arm64",
  "compiler_version": "Homebrew LLVM 22.1.8",
  "measurement_backend": "macOS fallback timing",
  "cpu_info": "Apple M4",
  "sample_count": 10,
  "median_time_ns": 4210050,
  "noise_ratio": 0.012
}
```
