# LLVM Phase-Ordering Guide

This guide details the phase-ordering problem in compiler optimization and explains why custom pass sequences frequently outperform fixed compiler heuristics like `-O3`.

---

## The Phase-Ordering Problem

A modern optimizing compiler consists of dozens of independent transformation passes:
- Canonicalization and dead-code elimination (`mem2reg`, `sroa`, `dce`, `simplifycfg`)
- Redundancy elimination (`gvn`, `early-cse`, `sccp`)
- Loop restructuring (`loop-rotate`, `loop-unroll`, `loop-flatten`, `loop-interchange`)
- Vectorization (`loop-vectorize`, `slp-vectorizer`, `vector-combine`)

Each transformation modifies the control-flow graph (CFG) or intermediate representation (IR) instructions. As a consequence:
1. **Pass Enabling**: Pass A may transform code in a way that creates the exact patterns required for Pass B to trigger.
2. **Pass Disabling**: Pass A may rewrite code in a way that obscures loop trip counts, aliases pointers, or introduces phi nodes that prevent Pass B from triggering.

### Why Standard `-O3` Misses Peak Performance

Standard Clang `-O3` uses an engineered, fixed sequence designed to work acceptably across millions of disparate C and C++ programs. In order to avoid excessive compile times and code bloat, standard heuristics make conservative assumptions:

1. **Premature Loop Unrolling**: In standard pipelines, partial unrolling may occur before vector analysis can discern SIMD opportunities, resulting in fragmented vector lanes and missed SIMD execution.
2. **Missing Inter-Pass Synergies**: Special computational kernels (e.g., matrix transpositions, 2D convolutions) often require iterative canonicalization (`mem2reg` -> `sccp` -> `instcombine`) interspersed between loop rotation and vector combining passes.
3. **Overly Conservative Inlining**: Generic inline heuristics often avoid inlining math functions that would otherwise enable complete constant folding across loop boundaries.

---

## Supported LLVM Passes in Autotune

Autotune supports and validates passes across LLVM 14 through 22, including:

| Pass Name | Pass Type | Primary Function |
| :--- | :--- | :--- |
| `mem2reg` | FunctionPass | Promotes alloca memory references to SSA registers |
| `sroa` | FunctionPass | Scalar Replacement of Aggregates; decomposes structs/arrays |
| `gvn` | FunctionPass | Global Value Numbering; eliminates redundant expressions |
| `early-cse` | FunctionPass | Fast, basic Common Subexpression Elimination |
| `instcombine` | FunctionPass | Peephole instruction combining and algebraic simplification |
| `aggressive-instcombine` | FunctionPass | Advanced instruction simplification (e.g., truncations, shifts) |
| `simplifycfg` | FunctionPass | Control flow graph cleanup and branch elimination |
| `sccp` | FunctionPass | Sparse Conditional Constant Propagation |
| `loop-rotate` | FunctionPass | Transforms while-loops into do-while loops with guards |
| `loop-unroll` | FunctionPass | Fully or partially unrolls loop iterations |
| `loop-vectorize` | FunctionPass | Vectorizes loop iterations using hardware SIMD registers |
| `slp-vectorizer` | FunctionPass | Superword-Level Parallelism vectorizer for straight-line code |
| `vector-combine` | FunctionPass | Combines scalar and vector operations into vector instructions |
| `loop-flatten` | FunctionPass | Flattens nested loops into single loops to expose parallelism |
| `loop-interchange` | FunctionPass | Exchanges loop nesting order to improve cache locality |
| `licm` | LoopPass | Loop-Invariant Code Motion; hoists invariants outside loops |
| `inline` | ModulePass | Inter-procedural function inlining |
| `globalopt` | ModulePass | Optimizes global variables and constant data structures |

---

## Preserving Pipeline Correctness

Autotune enforces semantic correctness during search:
- If any candidate pass sequence causes `opt` to exit with a non-zero code, the sequence is assigned zero fitness and discarded.
- Every compiled candidate executable is run with identical inputs to the baseline.
- If the binary produces an incorrect exit code or mismatched output checksum, it is marked `FAILED` and eliminated from the evolutionary pool.
