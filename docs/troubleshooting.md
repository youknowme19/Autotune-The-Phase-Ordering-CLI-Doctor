# Troubleshooting Guide

Solutions for common issues, toolchain configuration problems, and error messages.

---

## 🛠️ Common Errors & Solutions

### 1. `Clang / Opt Binary Not Found`
- **Symptom**: `autotune doctor` reports `clang_ok = False` or `opt_ok = False`.
- **Cause**: LLVM binaries are missing from system `PATH`.
- **Solution**:
  - macOS: Install LLVM via Homebrew: `brew install llvm` and export PATH:
    ```bash
    export PATH="/opt/homebrew/opt/llvm/bin:$PATH"
    ```
  - Verify with `which clang` and `which opt`.

---

### 2. `ModuleNotFoundError: No module named 'autotune'`
- **Symptom**: Importing `autotune` fails when running scripts.
- **Cause**: Package not installed in current virtual environment.
- **Solution**:
  ```bash
  source .venv/bin/activate
  pip install -e ".[dev]"
  ```

---

### 3. `API Key Not Configured`
- **Symptom**: Running `--llm` mode raises credential error.
- **Cause**: No API key found in OS Keychain or environment variables.
- **Solution**:
  - Run interactive keyring setup: `autotune config --provider openai`
  - Or pass `--no-llm` for 100% offline heuristic search.

---

### 4. `Timing Instability Warning (CV > 0.15)`
- **Symptom**: Benchmark report shows `timing_stability_warning = True`.
- **Cause**: Background CPU load, power throttling, or dynamic frequency scaling during timing.
- **Solution**:
  - Close background applications.
  - Increase warmup runs (`--warmup 5`) and confirmation repetitions (`--confirm-runs 20`).
  - Use deterministic interleaving (as in Phase G protocol).

---

### 5. `Cache Corruption Warning`
- **Symptom**: Logs display `quarantining corrupted cache file`.
- **Cause**: Interrupted write process or manually modified cache JSON file.
- **Solution**:
  - Autotune automatically quarantines corrupt files and recovers (`cache_corruption_recovered = True`).
  - To wipe the cache manually, delete `.autotune/cache/`.
