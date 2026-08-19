# System Architecture & Component Reference

This document details Autotune's end-to-end data flow, module architecture, and component responsibility map.

---

## 🏗️ End-to-End Data Flow

```text
               C/C++ Source Code
                      │
                      ▼
         [ FeatureExtractor (Clang AST) ]  (src/autotune/analysis/features.py)
                      │
                      ▼ (Compact Structural JSON)
           [ LLM / Heuristic Client ]      (src/autotune/llm/client.py)
                      │
                      ▼ (Proposed Pass Pipelines)
            [ PassValidator Gate ]         (src/autotune/llvm/passes.py)
                      │
                      ▼ (Valid Generation 0 Population)
       [ GeneticAlgorithmEngine (GA) ]     (src/autotune/search/genetic.py)
                      │
                      ├──────────────────────────────────────┐
                      ▼                                      ▼
       [ PersistentCacheManager (Cache) ]     [ CompilerDriver (LLVM Clang/Opt) ]
       (src/autotune/search/cache.py)         (src/autotune/llvm/compiler.py)
                      │                                      │
                      └──────────────────┬───────────────────┘
                                         ▼ (Compiled Candidate Binary)
                                [ SandboxExecutor ]
                                (src/autotune/sandbox/executor.py)
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
            [ CorrectnessValidator ]         [ PerformanceRunner ]
            (src/autotune/benchmark/)        (src/autotune/benchmark/macos.py)
                         │                               │
                         └───────────────┬───────────────┘
                                         ▼
                             [ FitnessEvaluator ]
                             (src/autotune/search/fitness.py)
                                         │
                                         ▼
                            [ FinalConfirmation Protocol ]
                            (src/autotune/search/genetic.py)
                                         │
                                         ▼
                       [ ExperimentManifestExporter ]
                       (src/autotune/reporting/manifest.py)
```

---

## 🧩 Component Responsibility Map

### 1. CLI Entry Point (`src/autotune/cli.py`)
- **Responsibility**: Provides Typer CLI application (`doctor`, `diagnose`, `search`, `bench-suite`, `config`).
- **Key Functions**: `doctor()`, `diagnose()`, `search()`, `bench_suite()`, `config()`.

### 2. AST Feature Extractor (`src/autotune/analysis/features.py`)
- **Responsibility**: Invokes `clang -ast-dump=json` to analyze AST nodes, loop depth, memory operations, and arithmetic complexity.
- **Key Class**: `FeatureExtractor`.

### 3. LLVM Pass Management (`src/autotune/llvm/passes.py` & `pipeline.py`)
- **Responsibility**: Parses, validates, and canonicalizes LLVM New Pass Manager (NPM) pass sequences.
- **Key Classes**: `PassSequence`, `PassValidator`, `CanonicalPassNormalizer`, `PipelineBuilder`.

### 4. Compiler Driver (`src/autotune/llvm/compiler.py`)
- **Responsibility**: Executes 3-step bitcode lowering (`clang -O0 -Xclang -disable-O0-optnone -emit-llvm`), pass transformation (`opt -passes=...`), and native binary assembly.
- **Key Class**: `CompilerDriver`.

### 5. Genetic Algorithm Engine (`src/autotune/search/genetic.py`)
- **Responsibility**: Manages population evolution, tournament selection, single-point crossover, pass mutators, multi-fidelity evaluation, baseline gate pruning, and final confirmation.
- **Key Class**: `GeneticAlgorithmEngine`.

### 6. Fitness Evaluator (`src/autotune/search/fitness.py` & `individual.py`)
- **Responsibility**: Computes baseline-normalized speedup ($\text{normalized\_speed} = \frac{\text{baseline\_median\_ns}}{\text{candidate\_median\_ns}}$) and manages candidate individual properties.
- **Key Classes**: `Individual`, `FitnessEvaluator`.

### 7. Persistent Cache Manager (`src/autotune/search/persistent_cache.py`)
- **Responsibility**: Manages multi-layer persistent compilation, correctness, performance, and fitness caching with atomic file operations (`tempfile` + `fsync` + `os.replace`) and corruption recovery.
- **Key Classes**: `PersistentCacheManager`, `CacheMetrics`.

### 8. Seed Archive Manager (`src/autotune/search/seeds.py`)
- **Responsibility**: Stores confirmed speedup pass pipelines into `.autotune/seeds/` and loads seeds into initial populations.
- **Key Class**: `SeedArchiveManager`.

### 9. Correctness Verification (`src/autotune/benchmark/correctness.py`)
- **Responsibility**: Compares candidate stdout, stderr, and exit codes against baseline output using pluggable strategy validators.
- **Key Classes**: `CorrectnessValidator`, `CorrectnessStrategy`, `ExitCodeAndStdoutStderrValidator`.

### 10. Performance Runner (`src/autotune/benchmark/macos.py` & `models.py`)
- **Responsibility**: Measures execution latency using high-precision monotonic timing (`__AUTOTUNE_TIME_NS__`), computing median, mean, stddev, CV, and IQR metrics.
- **Key Classes**: `MacOSPerformanceRunner`, `ExecutionMetrics`, `BenchmarkResult`.
