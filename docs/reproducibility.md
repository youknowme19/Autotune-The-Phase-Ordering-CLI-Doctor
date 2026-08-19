# Reproducibility Guide

This guide documents the environmental conditions, random seeds, and artifact manifests required to reproduce Autotune's experimental findings.

---

## 🛠️ Hardware & Toolchain Environment

All official scientific validation experiments were executed under the following hardware and software environment:

- **Processor**: Apple Silicon M4 (ARM64, 10 CPU Cores)
- **Operating System**: macOS Darwin 25.1.0 (`arm64`)
- **LLVM Compiler**: Homebrew LLVM / Clang version 22.1.8 (`/opt/homebrew/opt/llvm/bin/clang`)
- **LLVM Optimizer**: Homebrew LLVM `opt` version 22.1.8 (`/opt/homebrew/opt/llvm/bin/opt`)
- **Python Runtime**: Python 3.11.15

---

## 🎯 Reproducing the Validated Result (`matrix_transpose`)

To reproduce the confirmed **1.26x speedup** on `matrix_transpose`:

```bash
autotune search ./examples/matrix_transpose/kernel.c \
  -w ./examples/matrix_transpose/input.txt \
  --no-llm \
  -p 10 \
  -g 5 \
  -s 42 \
  --fresh-benchmark \
  --confirm-runs 20 \
  --output-json repro_matrix_transpose.json
```

### Protocol Standards:
- `--seed 42`: Fixes random number generator seed for deterministic population initialization and mutation.
- `--no-llm`: Forces 100% offline AST heuristic seeding (zero network dependency).
- `--fresh-benchmark`: Bypasses performance timing cache.

---

## 📄 Exported Manifest Artifacts

All benchmark runs save structured JSON reports containing exact raw sample arrays, environmental metadata, compiler paths, and statistical test outputs:
- [`matrix_transpose_phase_g_confirmation_report.json`](file:///Volumes/SSD/autotune/matrix_transpose_phase_g_confirmation_report.json)
- [`matrix_transpose_scaling_summary.json`](file:///Volumes/SSD/autotune/matrix_transpose_scaling_summary.json)
- [`polybench_generalization_summary.json`](file:///Volumes/SSD/autotune/polybench_generalization_summary.json)
