# Autotune Architecture & System Design

Autotune is an AI/heuristic + Genetic Algorithm guided compiler optimization engine designed to discover workload-specific LLVM phase-ordering pipelines for C/C++ programs.

## 1. System Topology

```text
SOURCE CODE
     │
     ▼
WorkloadProfiler ──> SearchSpacePolicy ──> OptimizationStrategy
     │                                            │
     ▼                                            ▼
DoctorChecks ──────────────────────────> GeneticAlgorithmEngine <── UCB1Bandit
                                                  │
                                                  ▼
                                         SandboxExecutor
                                                  │
                                                  ▼
                                         StabilityAnalyzer
                                                  │
                                                  ▼
                                         EvidenceEvaluator
                                                  │
                                                  ▼
                                       SQLite KnowledgeStore
                                                  │
                                                  ▼
                                         SearchReport & Prescriptions
```

## 2. Key Subsystems

- **`autotune.analysis`**: AST parsing via Clang JSON AST and structural profiling (`WorkloadProfile`, `WorkloadProfiler`).
- **`autotune.llvm`**: LLVM pass taxonomy (`PassFamily`, `PassMetadata`) and New Pass Manager pipeline strings (`PassSequence`).
- **`autotune.search`**: Genetic algorithm (`GeneticAlgorithmEngine`), UCB1 multi-armed bandit (`UCB1PassFamilyBandit`), and strategy policies (`SearchSpacePolicy`).
- **`autotune.sandbox`**: Isolated subprocess compilation, execution, bitcode lowering, stream truncation caps, and signal handling (`SandboxExecutor`).
- **`autotune.benchmark`**: Non-parametric stability analysis (`StabilityAnalyzer`), randomized A/B trial interleaving (`MeasurementPolicy`), and macOS/Linux high-precision timing runners.
- **`autotune.reporting`**: Evidence decision gate (`EvidenceEvaluator`), reproducible compiler prescriptions (`CompilerPrescription`), research export (`SearchReport`), and bundle generators (`bundle`).
- **`autotune.knowledge`**: Cross-run optimization memory stored in SQLite database (`KnowledgeStore`).
