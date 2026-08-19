# Matrix Transpose Example Workload

This directory contains a standalone C matrix transpose kernel (`kernel.c`) and sample input file (`input.txt`).

---

## 📄 Workload Overview

- **`kernel.c`**: Performs a 2D matrix transpose ($512 \times 512$) for $N$ iterations read from `input.txt` (or stdin). Prints checksum `Matrix Transpose Check B[256][256]: <value>`.
- **`input.txt`**: Contains iteration count (`100`).

---

## 🛠️ Usage with Autotune

### 1. Diagnose Baseline Performance (-O3)
```bash
autotune diagnose ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt
```

### 2. Search for Optimal Pass Sequence
```bash
autotune search ./examples/matrix_transpose/kernel.c \
  -w ./examples/matrix_transpose/input.txt \
  --no-llm \
  -p 10 \
  -g 5 \
  -s 42 \
  --fresh-benchmark
```
