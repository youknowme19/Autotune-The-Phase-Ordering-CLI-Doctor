# Pipeline Search & Genetic Algorithm Engine

This document describes Autotune's LLVM pass sequence representation, canonicalization pipeline, and Genetic Algorithm (GA) search operators.

---

## 🧬 Pass Sequence & NPM Canonicalization

LLVM's New Pass Manager (NPM) structures transformations into pass pipelines passed to `opt -passes='...'`.

### Pipeline Representation ([`src/autotune/llvm/passes.py`](file:///Volumes/SSD/autotune/src/autotune/llvm/passes.py))
A candidate pipeline is represented by `PassSequence(passes=[...])`.

Example pass list:
`['gvn', 'sccp', 'mem2reg', 'lower-atomic', 'mem2reg']`

### Canonicalization ([`CanonicalPassNormalizer`](file:///Volumes/SSD/autotune/src/autotune/llvm/passes.py))
`CanonicalPassNormalizer.normalize()` converts pass lists into NPM pipeline strings:
`function(gvn,sccp,mem2reg,lower-atomic,mem2reg)`

Syntactic canonicalization includes:
- Whitespace normalization and stable formatting.
- Deterministic representation of known pass aliases.
- Preserving pass ordering without aggressive semantic pass deletion.

---

## ⚙️ Genetic Algorithm Evolution Lifecycle

```text
               Generation 0 Initialization
            (20% Seeds, 20% Defaults, 20% Heuristics, 20% Conservative, 20% Random)
                             │
                             ▼
                    Multi-Fidelity Evaluation
                (LOW Screening + Baseline Gate)
                             │
                             ▼
                     Tournament Selection (k=3)
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
    Pass Crossover (Single-Point)     Pass Mutation Operators
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                    Duplicate Suppression
              (In-Memory Sequence Hash Check)
                             │
                             ▼
                 Elitism Preservation (Top N)
                             │
                             ▼
                   Next Generation Cycle
```

### 1. Hybrid Population Initialization
Initial populations are constructed using a 5-way hybrid split:
- **20% Seed Archive**: High-performing pass pipelines loaded from `.autotune/seeds/`.
- **20% Standard LLVM Defaults**: Sequences derived from default LLVM pipeline structures.
- **20% Heuristic Proposals**: Sequences generated from AST feature analysis.
- **20% Conservative Sequences**: Short 2–3 pass sequences (`mem2reg`, `sccp`, `instcombine`).
- **20% Random Pass Sequences**: Randomly sampled valid LLVM passes.

### 2. Mutation Operators
- **Insertion**: Inserts a randomly sampled valid LLVM pass at a random position.
- **Deletion**: Removes a pass from the sequence (maintaining minimum length 1).
- **Swap**: Swaps the positions of two adjacent passes.
- **Substitution**: Replaces a pass with another valid LLVM pass.

### 3. Duplicate Suppression & Memoization
Prior to evaluation, candidate sequence hashes (`SHA256(canonical_pipeline)`) are checked against:
- `self.session_eval_cache`: Session memory cache. Returns cached `Individual` instantly, incrementing `metrics.in_memory_memoization_hits`.
- `seen_hashes`: Prevents duplicate proposals from entering the evaluation queue, incrementing `metrics.duplicate_proposals_suppressed`.
