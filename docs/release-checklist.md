# Release Checklist

This document provides a step-by-step checklist to verify repository readiness prior to a public release or PyPI package publish.

---

## 📋 Release Verification Checklist

### 1. Environment & Setup
- [ ] Clean repository clone (`git clone ...`)
- [ ] Python virtual environment initialized (`python3.11 -m venv .venv`)
- [ ] Editable package installation succeeds (`pip install -e ".[dev]"`)
- [ ] LLVM binaries (`clang`, `opt`) verified (`clang --version`, `opt --version`)

### 2. CLI Diagnostics & Operations
- [ ] System doctor passes cleanly (`autotune doctor`)
- [ ] CLI help displays all options correctly (`autotune --help`)
- [ ] Workload diagnostic executes (`autotune diagnose ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt`)
- [ ] Offline search executes without errors (`autotune search ./examples/matrix_transpose/kernel.c -w ./examples/matrix_transpose/input.txt --no-llm -p 4 -g 2 -s 42 --fresh-benchmark`)

### 3. Testing & Hygiene
- [ ] Pytest test suite passes 100% (`.venv/bin/pytest -v`)
- [ ] Zero hardcoded secrets, API keys, or `.env` files in git status
- [ ] Git status clean of untracked build artifacts (`.autotune`, `*.bin`, `*.dot`)
- [ ] `.gitignore` covers `.venv/`, `build/`, `dist/`, `*.egg-info/`, `.pytest_cache/`

### 4. Documentation & Community Health
- [ ] `README.md` complete and links verified
- [ ] `docs/` library complete (25 files indexed in `docs/README.md`)
- [ ] `LICENSE` file present (Apache-2.0)
- [ ] `CONTRIBUTING.md` present
- [ ] `SECURITY.md` present
- [ ] `CODE_OF_CONDUCT.md` present
- [ ] `CHANGELOG.md` updated for version 0.1.0

### 5. Packaging & Distribution
- [ ] Package build succeeds (`python -m build`)
- [ ] PyPI metadata validation passes (`twine check dist/*`)
