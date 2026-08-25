# Changelog

All notable changes to the **Autotune** project are documented in this file.

---

## [0.3.0] - 2026-08-25

### 🚀 Open-Source Release, Scientific Rigor & Hardening
- **Search vs. Confirmation Separation**: Explicitly decoupled exploratory `Search Best` from authoritative `Confirmed Speedup` across CLI, JSON, HTML, Prescription, KnowledgeStore, and CI Gate layers.
- **Evidence Grading Decision Gate**: Enforced deterministic decision tree for Evidence Grades A, B, C, D, and F with comprehensive half-open boundary test coverage.
- **Empirical Raw Timing Statistics**: Computed all $p$-values (Welch's $t$-test), $CV\%$, and Cohen's $d$ effect sizes from raw nanosecond timing sample arrays with zero production fallback defaults.
- **KnowledgeStore Memory Filtering**: SQLite knowledge storage strictly persists Grade A and Grade B confirmed optimizations while rejecting unconfirmed Grade C, D, and F candidates.
- **CI Performance Gate**: `autotune gate` evaluates BOTH required speedup threshold AND evidence grade quality (`Grade A` or `Grade B`).
- **Subprocess Security Isolation**: Shell-safe process execution (`shell=False`) with explicit argument arrays, POSIX signal timeouts (`SIGTERM`/`SIGKILL`), and 10MB stream truncation limits.
- **HTML XSS Sanitization**: HTML entity escaping enforced across `HTMLReportGenerator` for source paths, pass names, and user-controlled strings.
- **Path Link Hygiene**: Sanitized documentation tree by converting absolute local machine file links to repository-relative Markdown links.

---

## [0.2.1] - 2026-08-19

### 🛠️ Runtime Diagnostics, UX, & UI Fixes
- **Process Exit & Signal Error Propagation**: Subprocess non-zero exit codes now explicitly format signal names (`SIGSEGV`, `SIGABRT`, `SIGTRAP`, `SIGBUS`, `SIGILL`, `SIGFPE`) and captured `stderr` instead of returning `Warmup execution failed: None`.
- **Top-Level CLI Version Flag**: Added `autotune --version` and `autotune -V` returning authoritative version string with exit code 0.
- **Single Banner Rendering**: Restructured CLI subcommands (`doctor`, `diagnose`, `search`) to print banner exactly once per invocation.
- **Search Dashboard Missing Timing Fix**: Explicitly format missing or unmeasurable candidate timing as `Current Best: N/A (Speedup: N/A)` instead of falsy `0.0 ms` conversion.
- **Accurate `--no-llm` Dashboard Status**: Explicitly render `Stage 1 LLM Seeding Skipped (--no-llm)` when `--no-llm` is specified.

---

## [0.2.0] - 2026-08-19 (Release Candidate)

### 🚀 Hardened Engine & Performance Search Features
- **Disaggregated Persistent Cache Architecture**: Implemented multi-layer persistent caching with distinct SHA-256 identities for compilation, correctness, and performance. Added atomic storage safety (`tempfile.NamedTemporaryFile` + `fsync` + `os.replace`) and automatic corruption recovery (`cache_corruption_recovered = True`).
- **Baseline-Normalized Fitness Engine**: Implemented $\text{normalized\_speed} = \frac{\text{baseline\_median\_ns}}{\text{candidate\_median\_ns}}$, prioritizing candidates with higher normalized speed and assigning $float("-inf")$ to invalid candidates.
- **Multi-Fidelity Screening & Baseline Gate**: Implemented `LOW` ($2, 2/3$), `MEDIUM` ($3, 7$), and `HIGH` ($5, 20$) measurement stages. Added baseline gate screening to prune non-promising candidates ($\text{normalized\_speed} < 0.80$) at `LOW` fidelity.
- **Independent Final Confirmation Protocol**: Added `run_final_confirmation()` post-GA search re-measuring baseline and winner independently under high repetition counts.
- **Cross-Workload Seed Archive**: Implemented `SeedArchiveManager` to persist confirmed speedup pass sequences in `.autotune/seeds/`.
- **Typer CLI Enhancements**: Added CLI flags `--fidelity`, `--screen-runs`, `--confirm-runs`, `--baseline-gate`, `--fail-on-regression`, and `--regression-threshold`.

### 🔬 Empirical Scientific Validation
- **Phase G Interleaved Confirmation**: Confirmed **1.26x speedup** ($20.7\%$ runtime reduction, $70.446\text{ ms} \rightarrow 55.858\text{ ms}$, $p = 2.47 \times 10^{-33}$, Bootstrap 95% CI $[1.25x, 1.32x]$) for `matrix_transpose` under 100-sample interleaved measurement protocol with 100% program correctness.
- **PolyBench/C Generalization Evaluation**: Completed 5-workload validation across `2mm`, `cholesky`, `atax`, `gemm`, and `bicg`, transparently documenting performance regressions under small offline search budgets.

### 🧪 Test Suite & Release Hygiene
- Expanded test suite to **51/51 passing tests** ($100\%$ pass rate), including end-to-end multi-layer cache integration tests (`test_cache_end_to_end.py`) and unit tests for hardened search features (`test_hardened_features.py`).

---

## [0.1.0] - 2026-08-19 (Initial Baseline Release)
- Initial PyPI release of `autotune-doctor` providing core `doctor`, `config`, `diagnose`, `search`, and `bench-suite` commands.
