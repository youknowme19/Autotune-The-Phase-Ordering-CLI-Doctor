# Contributing Guidelines

Thank you for contributing to Autotune! This document outlines our contribution standards, pull request workflow, and scientific claim verification requirements.

---

## 📜 Principles & Guidelines

1. **Maintain Architectural Integrity**: Do not weaken correctness validation checks, skip timing warmups, or bypass atomic cache writes.
2. **Preserve Benchmark Source Files**: Benchmark source code files (`matrix_transpose/kernel.c`, `polybench/*.c`) must NEVER be altered to manufacture speedups.
3. **Scientific Claims Rule**: Any new performance claim in documentation or pull requests MUST be backed by reproducible empirical measurement reports (e.g., raw sample arrays, Welch's t-test p-values, and bootstrap confidence intervals).

---

## 🔀 Pull Request Workflow

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/your-username/Autotune-The-Phase-Ordering-CLI-Doctor.git
   cd Autotune-The-Phase-Ordering-CLI-Doctor
   ```
2. **Create Feature Branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```
3. **Run Test Suite**:
   Ensure all 51 tests pass cleanly before submitting:
   ```bash
   .venv/bin/pytest -v
   ```
4. **Format & Lint**:
   ```bash
   black src/ tests/
   isort src/ tests/
   ```
5. **Submit Pull Request**: Include a clear summary of changes, motivation, and verification steps.
