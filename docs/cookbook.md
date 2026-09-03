# Autotune Cookbook: Real-World Recipes & Enterprise Integration

Practical recipes for integrating Autotune into existing C/C++ projects, build systems, CI/CD pipelines, and high-performance production workloads.

---

## Recipe 1: Optimizing an Individual Compute Kernel

When you have a critical hotspot (e.g. matrix routine, image processing filter, neural net forward pass):

```bash
# 1. Profile the kernel's AST and structure
autotune profile src/kernel.c

# 2. Run Autotune Doctor to find an optimal pipeline
autotune doctor src/kernel.c --preset balanced -o report.json

# 3. Explain why the winning pipeline improves performance
autotune explain report.json

# 4. Generate production LLVM IR, assembly, and binary without touching source code
autotune apply report.json --output-dir ./build/optimized/
```

---

## Recipe 2: Integrating with CMake Projects

Autotune exports CMake snippets that plug directly into standard `CMakeLists.txt`:

```bash
# Export CMake module for your winning report
autotune export report.json --format cmake -o autotune_kernel.cmake
```

In your `CMakeLists.txt`:
```cmake
include(autotune_kernel.cmake)

# Automatically lowers kernel.c with clang -> opt (winning pipeline) -> target
add_autotune_executable(my_optimized_app src/kernel.c)
```

---

## Recipe 3: Integrating with Makefiles

Export a clean Makefile snippet:

```bash
autotune export report.json --format make -o Makefile.autotune
```

Include it in your top-level `Makefile`:
```makefile
include Makefile.autotune

all: my_app.opt.bin
```

---

## Recipe 4: Performance Regression Guard in GitHub Actions

Add Autotune to your GitHub CI pipeline to prevent performance regressions on pull requests:

```yaml
name: Performance Guard

on: [pull_request]

jobs:
  benchmark-guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python & Clang
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: sudo apt-get install -y clang llvm
      - run: pip install autotune-doctor
      - name: Run Guard against Reference Report
        run: |
          autotune guard src/hotspot.c --reference .autotune/reference_report.json --threshold 0.05 --ci
```

**Guard Exit Codes:**
- `0`: Success (performance verified within 5% tolerance).
- `1`: Performance regression detected (candidate slower than threshold).
- `2`: Correctness failure (output mismatch).
- `3`: Toolchain or environment error.

---

## Recipe 5: 100% Air-Gapped & Offline Compilation

For air-gapped workstations or CI machines without Internet access:

```bash
# Explicitly disable all LLM calls and rely purely on deterministic AST heuristics
autotune doctor src/kernel.c --no-llm --preset aggressive
```

---

## Recipe 6: Benchmarking Entire Benchmark Suites

To stress-test and batch-optimize an entire directory of benchmark kernels (e.g. PolyBench or internal kernels):

```bash
autotune bench-suite ./benchmarks/ --population 20 --generations 10 --workers 4 --csv benchmark_matrix.csv -o stress_report.json
```

---

## Recipe 7: Automated GitHub PR Benchmark Commenting

Add automated PR comments with beautiful markdown summary tables:

```yaml
- name: Guard and Comment
  run: |
    autotune guard src/hotspot.c --reference .autotune/ref.json --comment-markdown pr_comment.md
- name: Post Comment to PR
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const body = fs.readFileSync('pr_comment.md', 'utf8');
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: body
      });
```

---

## Recipe 8: Meson and Ninja Build System Export

Export native build files for Ninja and Meson projects:

```bash
# Export Ninja build rules
autotune export report.json --format ninja -o build.ninja

# Export Meson build definition
autotune export report.json --format meson -o meson.build
```

---

## Recipe 9: Integrating with Google Bazel

Export native `genrule` definitions directly for monorepos using Bazel:

```bash
autotune export report.json --format bazel -o BUILD.bazel
```

Build the optimized target hermetically with Bazel:
```bash
bazel build //:kernel_opt_bin
```

---

## Recipe 10: Hermetic Docker Container Benchmarking

Generate a reproducible Dockerfile for containerized cloud benchmarking:

```bash
autotune export report.json --format docker -o Dockerfile
docker build -t autotune-benchmark .
docker run --rm autotune-benchmark
```

---

## Recipe 11: Side-by-Side Experiment Report Diffing

When evaluating two different compiler versions or optimization presets, compare results directly:

```bash
autotune diff run_quick_report.json run_aggressive_report.json
```
