# Extending Autotune

This guide explains how to extend Autotune's LLVM pass vocabulary, correctness strategy validators, performance runners, and fitness evaluators.

---

## 1. Adding New LLVM Passes

Pass vocabulary is managed in [`src/autotune/llvm/passes.py`](../src/autotune/llvm/passes.py).

To register a new LLVM pass:
1. Add the pass name to `KNOWN_LLVM_PASSES`:
   ```python
   KNOWN_LLVM_PASSES = [
       "mem2reg", "sccp", "gvn", "licm", "loop-unroll", "new-pass-name", ...
   ]
   ```
2. If the pass requires specific NPM nesting (e.g., `function(...)` or `loop(...)`), update `CanonicalPassNormalizer`.

---

## 2. Adding a New Correctness Validator

To implement a custom output validator:
1. Subclass `CorrectnessStrategy` in [`src/autotune/benchmark/correctness.py`](../src/autotune/benchmark/correctness.py):
   ```python
   class MyCustomValidator(CorrectnessStrategy):
       def verify(
           self, baseline_res: SandboxExecutionResult, candidate_res: SandboxExecutionResult
       ) -> CorrectnessResult:
           # Perform custom validation logic
           is_ok = (candidate_res.stdout.strip() == baseline_res.stdout.strip())
           return CorrectnessResult(is_correct=is_ok, reason="Custom verification passed")
   ```
2. Pass instance to `CorrectnessValidator(strategy=MyCustomValidator())`.

---

## 3. Adding a Custom Performance Runner

Subclass `PerformanceRunner` in [`src/autotune/benchmark/base.py`](../src/autotune/benchmark/base.py) to add support for new hardware profiling backends (e.g., Linux `perf_event_open`).
