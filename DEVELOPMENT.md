# Autotune Development & Contribution Guide

This guide provides instructions for setting up your local environment, running the test suite, and contributing to Autotune.

## Quickstart Development Setup

```bash
# Clone the repository
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install editable package with development dependencies
pip install -e ".[dev]"

# Run full test suite
pytest -v
```

## Running Example Workloads Locally

```bash
# Run toolchain diagnostic doctor
autotune doctor

# Profile example matrix multiplication kernel
autotune diagnose examples/matrix/matrix_mul.c

# Search optimization pass sequences for 10 seconds
autotune search examples/matrix/matrix_mul.c --time-budget 10 --seed 42 -o report.json

# Inspect and explain winning pass sequence
autotune explain report.json

# Generate standalone offline HTML report
autotune report report.json --html report.html

# Export executable reproduction script
autotune export report.json -o ./prescription_out
```

## Repository Structure

- `src/autotune/analysis`: AST parsing via Clang JSON AST and structural profiling (`WorkloadProfiler`).
- `src/autotune/llvm`: Pass taxonomy (`PassFamily`, `PassMetadata`) and pipeline strings (`PassSequence`).
- `src/autotune/search`: Genetic algorithm (`GeneticAlgorithmEngine`), UCB1 bandit (`UCB1PassFamilyBandit`), and strategy policies (`SearchSpacePolicy`).
- `src/autotune/sandbox`: Subprocess compilation, lowering, stream caps, and signal handling (`SandboxExecutor`).
- `src/autotune/benchmark`: Non-parametric stability analysis (`StabilityAnalyzer`) and randomized A/B trial interleaving (`MeasurementPolicy`).
- `src/autotune/reporting`: Evidence decision gate (`EvidenceEvaluator`), prescriptions (`CompilerPrescription`), and standalone HTML report generator (`HTMLReportGenerator`).
- `src/autotune/knowledge`: Cross-run optimization memory stored in SQLite database (`KnowledgeStore`).
