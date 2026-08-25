# Contributing to Autotune

Thank you for your interest in contributing to **Autotune** — the AI-guided compiler optimization and phase-ordering doctor.

## Principles

1. **Empirical Rigor**: Never accept optimization claims based solely on LLM suggestions. Every candidate pipeline must be compiled, executed, verified for correctness, and benchmarked.
2. **Platform Independence**: Ensure measurement runner abstractions support both macOS high-precision CPU timing and Linux hardware performance counters (`perf_event_open`).
3. **Modularity**: Maintain clean separation between analysis, LLVM driver, GA search, benchmarking, and UI components.

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
   cd Autotune-The-Phase-Ordering-CLI-Doctor
   ```

2. Create virtual environment and install dev dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. Run the environment doctor:
   ```bash
   autotune doctor
   ```

4. Run unit and integration tests:
   ```bash
   pytest -v
   ```

## Pull Request Guidelines

- Ensure unit tests pass for all pass sequence operations, GA mutations, and correctness validators.
- **Scientific Integrity**: Do not submit benchmark claims without reproducible empirical evidence (raw samples, $p$-value, $CV\%$, and Cohen's $d$).
- Do not commit API keys, absolute local system paths, or sensitive credentials.
- Write descriptive commit messages.
