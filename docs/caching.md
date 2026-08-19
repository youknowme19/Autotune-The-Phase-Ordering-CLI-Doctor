# Persistent Cache Architecture

This document describes Autotune's multi-layer persistent cache system, atomic storage mechanics, corruption recovery protocols, and metrics accounting.

---

## 🗄️ Multi-Layer Cache Structure

Autotune implements four distinct cache layers:

```text
                               Candidate Proposal
                                       │
                                       ▼
                       [ Session Memory Cache ]  (session_eval_cache)
                                       │
                                       ▼ (Miss)
                   [ Compilation Cache Layer ]   (compilation_key)
                   (Reuses compiled .bin files)
                                       │
                                       ▼ (Hit / Miss)
                   [ Correctness Cache Layer ]   (correctness_key)
                   (Reuses is_correct results)
                                       │
                                       ▼ (Hit / Miss)
                   [ Performance Cache Layer ]   (performance_key)
                   (Reuses timing metrics / Bypassed via --fresh-benchmark)
```

---

## 🔑 Cache Key Disaggregation

Cache identities are strictly disaggregated to prevent invalidation cascades:

1. **Compilation Key (`compilation_key`)**:
   - `SHA256(source_content + canonical_pipeline + clang_path + clang_ver + opt_ver + arch + os_name + flags + schema_ver)`
   - **Independence**: Independent of `--runs` or benchmark timing repetitions. Changing `--runs` reuses compiled binary artifacts without recompiling.
2. **Correctness Key (`correctness_key`)**:
   - `SHA256(compilation_key + correctness_strategy_name + workload_content)`
3. **Performance Key (`performance_key`)**:
   - `SHA256(compilation_key + workload_content + measurement_backend + warmup_runs + repetitions)`
   - Changing `--runs` or setting `--fresh-benchmark` invalidates the performance key while preserving compilation cache hits.

---

## 🔒 Atomic Storage Safety & Worker Concurrency

When running parallel search workers (`--workers 4`), non-atomic file writes can cause race conditions or truncated JSON reads.

Autotune enforces **atomic file operations** across all cache publications ([`src/autotune/search/persistent_cache.py`](file:///Volumes/SSD/autotune/src/autotune/search/persistent_cache.py)):

```python
def _atomic_write_json(filepath: str, data: Dict[str, Any]) -> None:
    dirname = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile("w", dir=dirname, delete=False, encoding="utf-8") as tf:
        json.dump(data, tf, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
        tmp_name = tf.name
    os.replace(tmp_name, filepath)
```

1. Data is written to a temporary file (`tempfile.NamedTemporaryFile`) in the destination directory.
2. Data is flushed to disk via `os.fsync()`.
3. The temporary file is atomically renamed over the target cache path using `os.replace()`.

---

## 🛡️ Corruption Recovery & Quarantine Protocol

If a cache file is corrupted (e.g., interrupted process or manual editing), `PersistentCacheManager` handles recovery transparently:

1. On `json.JSONDecodeError` or zero-byte file detection:
   - Removes/quarantines the corrupted file.
   - Logs a warning diagnostic.
   - Increments `self.metrics.cache_corruption_recovered = True`.
   - Returns `None`, causing the engine to gracefully recompute the entry.

---

## 📊 Disaggregated Cache Metrics (`CacheMetrics`)

| Metric Field | Meaning |
|---|---|
| `duplicate_proposals_suppressed` | Duplicate sequences blocked in memory before proposal scheduling. |
| `in_memory_memoization_hits` | Candidates served directly from `session_eval_cache`. |
| `persistent_compilation_cache_hits` | Reused compiled binary artifacts from `.autotune/cache/compilation/`. |
| `persistent_correctness_cache_hits` | Reused correctness validation results. |
| `persistent_performance_cache_hits` | Reused performance timing measurements. |
| `actual_compilations` | Number of physical Clang/Opt compilation invocations performed. |
| `actual_benchmark_executions` | Number of physical benchmark executable executions performed. |
| `cache_corruption_recovered` | Boolean flag indicating whether corrupt cache artifacts were safely quarantined. |
