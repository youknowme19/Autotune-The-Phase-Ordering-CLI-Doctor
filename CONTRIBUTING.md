# Contributing to Autotune

Thank you for your interest in contributing to **Autotune**! We are building the open-source, AI-guided compiler optimization and LLVM phase-ordering doctor for high-performance C/C++ workloads.

Whether you are fixing a compiler edge case, adding a new heuristic seeding algorithm, enhancing statistical evaluation, or writing documentation, your contribution is welcomed and valued.

---

## 🧭 Core Philosophy & Rules of Engagement

1. **Empirical Evidence Over Intuition**:
   The LLM or heuristic proposer is never the final authority. Only empirical execution, repeated multi-sample benchmarking, and rigorous correctness checking decide if an optimization is accepted.
2. **Zero Fabrication**:
   Never hardcode speedups, mock benchmarks in core paths, or weaken correctness validators.
3. **Zero Secret Leakage**:
   API keys and tokens must strictly go through OS keyrings or standard environment variables, and must never appear in logs, traces, or exported reports.
4. **Cross-Platform Compatibility**:
   Autotune must run smoothly on macOS (Apple Silicon & Intel) and modern Linux distributions (x86_64 and AArch64).

---

## 🛠️ Development Environment Setup

### 1. Prerequisites
- **Python**: 3.11 or higher
- **LLVM / Clang**: Version 14+ (Clang and `opt` must be discoverable in `PATH` or configured via `autotune config`)
  - **macOS**: `brew install llvm`
  - **Ubuntu / Debian**: `sudo apt install clang llvm llvm-dev`
  - **Fedora / RHEL**: `sudo dnf install clang llvm llvm-devel`

### 2. Clone and Install
```bash
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor

# Create and activate virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### 3. Verify Toolchain
Run the built-in diagnostic doctor:
```bash
autotune doctor
```

---

## 🧪 Testing Guidelines

We take automated testing very seriously. Every PR must maintain 100% passing tests and high coverage.

```bash
# Run the full test suite
pytest -v

# Run with coverage report
pytest -v --cov=src/autotune --cov-report=term-missing

# Run specific test modules
pytest tests/unit/test_validation_strategies.py -v
pytest tests/unit/test_statistics_robustness.py -v
```

---

## 📐 Project Structure

```text
src/autotune/
├── analysis/         # AST parsing, loop depth, memory vs compute intensity
├── benchmark/        # Execution harness, timing stability, correctness validators
├── doctor/           # Diagnostics, toolchain discovery, error categorizations
├── environment/      # Target CPU, triple, and environment fingerprinting
├── knowledge/        # Persistent optimization taxonomy and SQLite knowledge store
├── llm/              # API key handling (Keyring), prompt templates, LLM clients
├── llvm/             # Clang compiler drivers, opt pass sequence manipulation
├── reporting/        # Welch's t-test, Mann-Whitney U, Cohen's d, HTML/JSON reports
├── sandbox/          # Process isolation, timeouts, and resource limits
├── search/           # Genetic algorithm, multi-armed bandits, candidate cache
└── services/         # Orchestration layer (Doctor, Profile, Explain, Apply, Export, Guard)
```

---

## 🚀 Submitting a Pull Request (PR)

1. **Fork the repo** and create your feature branch:
   ```bash
   git checkout -b feat/my-new-pass-heuristic
   ```
2. **Commit your changes**:
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat(...)`: New feature or capability
   - `fix(...)`: Bug fix
   - `docs(...)`: Documentation updates
   - `test(...)`: Adding or updating tests
   - `chore(...)`: Maintenance or CI updates
3. **Ensure all tests pass**:
   ```bash
   pytest -v
   ```
4. **Open a PR**:
   Fill out the PR template completely with details of what was changed and how it was verified.

---

## 💬 Community & Questions

- **Issues**: Use [GitHub Issues](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/issues) for bug reports and feature proposals.
- **Discussions**: Share benchmark findings, new pass sequences, or architecture ideas in GitHub Discussions.
