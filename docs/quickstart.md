# Quickstart Guide

Get up and running with Autotune in under 5 minutes using the included `matrix_transpose` example workload.

---

## 🚀 5-Minute Copy-Paste Walkthrough

### 1. Clone the Repository & Setup Environment
```bash
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor

python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Verify System Readiness
```bash
autotune doctor
```

### 3. Run Diagnostic Check on Target Kernel
Analyze baseline `-O3` performance and correctness before initiating optimization search:

```bash
autotune diagnose ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt
```

Expected diagnostic output:
```text
Diagnosing ./examples/matrix_transpose/kernel.c...
Baseline (-O3) Latency: 72.41 ms
Correctness Output:     Matrix Transpose Check B[256][256]: 1313.2899
Status: READY FOR SEARCH
```

---

### 4. Execute Optimization Search
Run an offline phase-ordering search using 10 individuals over 5 generations with random seed 42:

```bash
autotune search ./examples/matrix_transpose/kernel.c \
  -w ./examples/matrix_transpose/input.txt \
  --no-llm \
  -p 10 \
  -g 5 \
  -s 42 \
  --fresh-benchmark \
  --output-json my_search_report.json
```

---

### 5. Inspect Results & Prescriptions

During search, Autotune displays a dynamic terminal dashboard:

```text
Optimization Search Complete!
Best Pass Sequence: ['gvn', 'sccp', 'mem2reg', 'lower-atomic', 'mem2reg']
Speedup: 1.25x (19.8% improvement over -O3)

Baseline (-O3):   73.29 ms
Candidate Best:   58.78 ms

Reproducible Compiler Command:
/opt/homebrew/opt/llvm/bin/clang -O0 -Xclang -disable-O0-optnone -emit-llvm -S 
./examples/matrix_transpose/kernel.c -o - | /opt/homebrew/opt/llvm/bin/opt 
-passes='gvn,sccp,mem2reg,lower-atomic,mem2reg' -S -o - | 
/opt/homebrew/opt/llvm/bin/clang -x assembler - -o optimized_kernel.bin
```

---

### 6. Inspect Generated Run Artifacts

Autotune creates a structured run directory under `.autotune_runs/run_<timestamp>/`:

```bash
ls -la .autotune_runs/run_*/
```

Run directory structure:
- `manifest.json`: Full environment and run metadata.
- `search_history.jsonl`: Line-by-line log of every evaluated candidate sequence.
- `best_pipeline.json`: Winning sequence, raw timing metrics, and p-value.
- `prescription.txt`: Reproducible shell command to build the optimized binary.
- `benchmark_diff.svg`: Graphical representation of timing baseline vs candidate.

View your exported JSON report:
```bash
cat my_search_report.json
```
