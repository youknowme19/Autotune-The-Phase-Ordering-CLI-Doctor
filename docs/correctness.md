# Correctness Validation Architecture

This document explains Autotune's pluggable correctness validation architecture and output matching strategies.

---

## 🛡️ Correctness Principles

Performance optimization is useless if it alters program behavior. Autotune enforces program correctness by comparing candidate executable output against trusted baseline `-O3` output under sandbox execution.

---

## 🔌 Pluggable Correctness Strategies ([`src/autotune/benchmark/correctness.py`](../src/autotune/benchmark/correctness.py))

Autotune delegates output validation to implementations of `CorrectnessStrategy`:

```python
class CorrectnessStrategy(ABC):
    @abstractmethod
    def verify(
        self, baseline_res: SandboxExecutionResult, candidate_res: SandboxExecutionResult
    ) -> CorrectnessResult:
        pass
```

### Supported Strategies:

1. **`ExitCodeAndStdoutStderrValidator` (Default)**:
   - Strips timing markers (`__AUTOTUNE_TIME_NS__`).
   - Verifies candidate exit code equals baseline exit code.
   - Performs exact string matching on stdout and stderr.
2. **`NumericToleranceValidator`**:
   - Extracts floating-point values from stdout.
   - Verifies $|y_{\text{baseline}} - y_{\text{candidate}}| \le \epsilon$ for configurable epsilon tolerance (default $\epsilon = 10^{-6}$).
3. **`FileDigestValidator`**:
   - Computes SHA-256 digests across output artifact files written to disk.
4. **`CustomScriptValidator`**:
   - Invokes an external verification script `./verify.sh <baseline_out> <candidate_out>`.

---

## 🚫 Rejection Workflow

If a candidate fails correctness verification:
1. `is_correct = False` and the failure reason (e.g., `Stdout divergence from baseline`) are recorded.
2. Correctness result is saved to persistent correctness cache.
3. Candidate is assigned `fitness = float("-inf")` and `normalized_speed = 0.0`.
4. Performance timing measurements for the candidate are safely skipped.
