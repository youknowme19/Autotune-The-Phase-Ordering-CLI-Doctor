# CLI Reference and Workflow Guide

Autotune provides a unified command-line tool `autotune` with subcommands covering the entire optimization and continuous verification lifecycle.

---

## Command Reference

### `autotune doctor`
Inspects the local compiler toolchain, validates availability of `clang`, `clang++`, and `opt`, and reports the measurement backend and CPU capabilities.

```bash
autotune doctor
```

Options:
- `--json`: Output machine-readable JSON format instead of human-readable terminal output.

---

### `autotune diagnose`
Performs an initial sanity check and baseline performance characterization of a target source kernel before launching a search.

```bash
autotune diagnose <source_path> -w <workload_args_or_file>
```

Options:
- `-w, --workload`: Path to an input workload file or inline command-line arguments.
- `-b, --baseline`: Baseline optimization level to test against (`-O0`, `-O1`, `-O2`, `-O3`). Default: `-O3`.
- `--runs`: Number of benchmark measurement samples (default: 5).

---

### `autotune search`
Executes the genetic algorithm search engine to find the optimal LLVM pass sequence for the specified kernel.

```bash
autotune search <source_path> -w <workload> [options]
```

Options:
- `-b, --baseline`: Compiler baseline level (`-O0`, `-O1`, `-O2`, `-O3`). Default: `-O3`.
- `-p, --population`: Population size per generation (default: 10).
- `-g, --generations`: Maximum generation count (default: 5).
- `-s, --seed`: Random seed for deterministic reproducibility.
- `--screen`: Number of screening runs in low-fidelity evaluation (default: 3).
- `--confirm`: Number of confirmation runs in high-fidelity evaluation (default: 10).
- `--output-json`: File path to save the structured JSON optimization report.
- `--no-llm`: Disable LLM-assisted pass seeding and rely purely on AST analysis and heuristics.

---

### `autotune reproduce`
Takes a generated Autotune JSON report and attempts to reproduce the reported speedup on the current machine under identical or calibrated conditions.

```bash
autotune reproduce <report_json_path> [options]
```

Options:
- `--tolerance`: Maximum allowable deviation in speedup percentage before flagging non-reproduction (default: 0.15 for 15%).
- `--runs`: Number of validation executions.

Exit codes:
- `0`: Reproduced successfully within tolerance.
- `1`: Validation failed or severe environmental noise detected.

---

### `autotune guard`
Used primarily in continuous integration environments to verify that performance on a target kernel has not regressed relative to a reference report.

```bash
autotune guard <source_path> --reference <reference_report_json> [options]
```

Options:
- `--reference`: Path to reference benchmark report JSON.
- `--threshold`: Allowed regression threshold as a fraction (default: 0.05 for 5% regression limit).
- `--strict-env`: Require identical LLVM version and host microarchitecture.
- `--ci`: Emit GitHub Actions workflow output commands (`::error::`, `::notice::`) and concise CI summaries.

---

### `autotune apply`
Applies the winning pass pipeline from an optimization report and emits compiled build artifacts (optimized LLVM IR `.optimized.ll`, assembly `.s`, and native binary `.bin`).

```bash
autotune apply <report_json_path> --output-dir <artifacts_directory>
```

Options:
- `-o, --output-dir`: Output directory path where compiled artifacts and build manifests are saved.
- `--no-binary`: Emit only LLVM IR and assembly files without linking a native executable.

---

### `autotune profile`
Analyzes assembly features and code metrics of a source file across different optimization levels (`-O0`, `-O3`, and custom pass sequences).

```bash
autotune profile <source_path> [options]
```

Options:
- `--json`: Output metrics as structured JSON.
- `--baseline`: Target optimization level to profile against.
