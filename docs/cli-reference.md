# CLI Command Reference

Autotune provides a unified command-line interface powered by [Typer](https://typer.tiangolo.com/).

---

## 📋 Command Overview

```bash
autotune [COMMAND] [ARGS] [OPTIONS]
```

Available commands:
- `doctor`: Run system diagnostics for LLVM, Clang, Opt, Python, and hardware backend.
- `diagnose`: Inspect baseline `-O3` performance and correctness for a workload.
- `search`: Run genetic algorithm phase-ordering optimization search on a target C file.
- `bench-suite`: Run batch optimization search across a directory of benchmark files.
- `config`: Manage API keys in OS Keychain.

---

## 1. `autotune doctor`

Runs system environment diagnostics and verifies dependencies.

### Syntax
```bash
autotune doctor
```

### Output
Prints Python version, OS architecture, Clang binary path/version, Opt binary path/version, measurement backend status, and diagnostic warnings/errors.

---

## 2. `autotune diagnose`

Compiles baseline `-O3`, executes program, measures timing, and verifies correctness.

### Syntax
```bash
autotune diagnose SOURCE [OPTIONS]
```

### Arguments
- `SOURCE` *(required, string)*: Path to target C/C++ source file (e.g., `./examples/matrix_transpose/kernel.c`).

### Options
- `-w, --workload PATH` *(optional, string)*: Path to input workload file (e.g., `./examples/matrix_transpose/input.txt`).

---

## 3. `autotune search`

Executes phase-ordering optimization search on a target C/C++ file.

### Syntax
```bash
autotune search SOURCE [OPTIONS]
```

### Arguments
- `SOURCE` *(required, string)*: Path to target C/C++ source file.

### Options
| Flag / Option | Type | Default | Description |
|---|---|---|---|
| `-w, --workload` | `PATH` | `None` | Path to workload input file. |
| `-o, --output-binary` | `PATH` | `optimized_kernel.bin` | Output path for compiled binary. |
| `-p-seq, --pass-sequence` | `TEXT` | `None` | Initial pass sequence string. |
| `-p, --population` | `INT` | `10` | GA population size. |
| `-g, --generations` | `INT` | `5` | GA generation count. |
| `-s, --seed` | `INT` | `42` | Random seed for deterministic search. |
| `-w-num, --workers` | `INT` | `4` | Number of parallel evaluation workers. |
| `--fidelity` | `TEXT` | `LOW` | Measurement fidelity level (`LOW`, `MEDIUM`, `HIGH`). |
| `--screen-runs` | `INT` | `3` | Number of measurement runs during screening stage. |
| `--confirm-runs` | `INT` | `20` | Number of measurement runs during final confirmation stage. |
| `--baseline-gate / --no-baseline-gate` | `BOOL` | `True` | Enable/disable baseline gate pruning ($\text{normalized\_speed} < 0.80$). |
| `--gate-threshold` | `FLOAT` | `0.80` | Speedup cutoff threshold for baseline gate screening. |
| `--fail-on-regression / --no-fail-on-regression` | `BOOL` | `False` | Exit CLI with code 1 if confirmed result regresses. |
| `--regression-threshold` | `FLOAT` | `0.05` | Maximum allowable regression threshold before failure. |
| `--llm / --no-llm` | `BOOL` | `Auto` | Enable/disable LLM proposal generation. |
| `--llm-provider` | `TEXT` | `Auto` | LLM provider (`openai`, `anthropic`, `gemini`). |
| `--fresh-benchmark / --no-fresh-benchmark` | `BOOL` | `False` | Bypass performance timing cache for fresh timing measurements. |
| `--output-json` | `PATH` | `None` | Export structured search report JSON to path. |

---

## 4. `autotune bench-suite`

Runs batch optimization search across a directory of benchmark kernels.

### Syntax
```bash
autotune bench-suite SUITE_DIR [OPTIONS]
```

### Arguments
- `SUITE_DIR` *(required, string)*: Path to directory containing benchmark kernels (e.g., `./polybench/`).

### Options
| Flag / Option | Type | Default | Description |
|---|---|---|---|
| `-p, --population` | `INT` | `10` | GA population size per workload. |
| `-g, --generations` | `INT` | `5` | GA generation count per workload. |
| `-s, --seed` | `INT` | `42` | Random seed for deterministic search. |
| `-w, --workers` | `INT` | `4` | Number of parallel workers. |
| `--llm / --no-llm` | `BOOL` | `False` | Enable/disable LLM seeding. |
| `--fresh-benchmark / --no-fresh-benchmark` | `BOOL` | `False` | Bypass performance timing cache. |
| `-r, --runs` | `INT` | `10` | Number of measurement repetitions. |
| `-wm, --warmup` | `INT` | `3` | Number of warmup runs. |
| `-o, --output-report` | `PATH` | `None` | Path to save summary report JSON. |

---

## 5. `autotune config`

Manages credentials stored in OS Keychain.

### Syntax
```bash
autotune config --provider PROVIDER [--key KEY]
```

### Options
- `--provider` *(required, text)*: Provider name (`openai`, `anthropic`, `gemini`).
- `--key` *(optional, text)*: API key string. If omitted, prompts interactively.
