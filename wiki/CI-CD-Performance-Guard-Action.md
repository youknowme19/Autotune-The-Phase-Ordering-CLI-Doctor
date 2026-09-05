# CI/CD Performance Guard Action

The Autotune Performance Guard Action enables automated performance regression testing for C and C++ codebases directly within GitHub Actions workflows.

---

## Action Overview

When software engineers modify low-level compute kernels, algorithms, or systems code, subtle changes can inadvertently degrade instruction-level parallelism, disable vectorization, or increase cache misses. Standard unit and integration tests only verify functional correctness, allowing major performance regressions to slip into production undetected.

The Autotune Performance Guard Action continuously benchmarks designated kernels against an authorized baseline report and fails the CI build if execution time regresses beyond an allowed threshold.

---

## Action Specification (`action.yml`)

### Inputs

| Input | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `source` | **Yes** | — | Relative path to the C/C++ source kernel file to guard |
| `reference` | **Yes** | — | Path to the reference benchmark report JSON from previous release or baseline |
| `threshold` | No | `"0.05"` | Maximum allowable runtime regression fraction (e.g. `0.05` for 5%) |
| `strict-env` | No | `"false"` | If `"true"`, enforces identical host CPU architecture and compiler version match |

---

## Workflow Example

Below is a complete GitHub Actions workflow configuration:

```yaml
name: Performance Guard

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  performance-gate:
    name: Guard Hot Kernels
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Guard Matrix Transpose Kernel
        uses: youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor@v0.5.0
        with:
          source: "./examples/matrix_transpose/kernel.c"
          reference: "./benchmarks/matrix_transpose_ref.json"
          threshold: "0.05"
```

---

## Generating Reference Reports

To generate the reference benchmark report to commit into your repository:

```bash
# Run Autotune search to produce reference report
autotune search ./examples/matrix_transpose/kernel.c \
  -w ./examples/matrix_transpose/input.txt \
  -p 12 \
  -g 8 \
  --output-json ./benchmarks/matrix_transpose_ref.json
```

Commit `./benchmarks/matrix_transpose_ref.json` alongside your project tests.

---

## CI Failure Behavior

If a pull request introduces changes that cause the kernel's median runtime to exceed `reference_latency * (1.0 + threshold)`:
- The action terminates with exit status `1`.
- A GitHub workflow error annotation is placed on the build.
- The pull request is blocked from merging until performance is restored or the threshold is adjusted.
