# Installation Guide

This document details the system requirements, environment setup, and installation options for Autotune.

---

## 📋 Requirements

| Component | Minimum Version | Recommended / Tested |
|---|---|---|
| **Python** | 3.11+ | Python 3.11.15 |
| **LLVM / Clang** | LLVM 15.0+ | LLVM / Clang 22.1.8 (Homebrew) |
| **Operating System** | macOS 12+ (ARM64 / x86_64) or Linux (x86_64) | macOS ARM64 (Apple Silicon) / Linux x86_64 |
| **Build Tools** | `make`, `gcc` / `clang`, `git` | Standard build-essential |

---

## 🛠️ Step 1: Install LLVM / Clang

Autotune requires both `clang` and `opt` binaries available on your system `PATH`.

### macOS (via Homebrew)
```bash
brew install llvm
```

Add Homebrew LLVM to your PATH in `~/.zshrc` or `~/.bash_profile`:
```bash
export PATH="/opt/homebrew/opt/llvm/bin:$PATH"
```

Verify `clang` and `opt` installations:
```bash
clang --version
opt --version
```

---

## 🐍 Step 2: Set Up Python Virtual Environment

Create a dedicated Python 3.11 virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Upgrade core package tools:
```bash
pip install --upgrade pip setuptools wheel
```

---

## 📦 Step 3: Install Autotune

### Option A: Editable Development Installation (Recommended from Source)
```bash
git clone https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git
cd Autotune-The-Phase-Ordering-CLI-Doctor

source .venv/bin/activate
pip install -e ".[dev]"
```

### Option B: PyPI Package Installation
```bash
pip install autotune-doctor
```

---

## ✅ Step 4: Verify Installation

Run Autotune's system doctor diagnostic to check environment readiness:

```bash
autotune doctor
```

Expected output:
```text
Autotune v0.1.0
Phase-Ordering CLI Doctor

Diagnostics Summary:
  Python Version: 3.11.15 (OK)
  OS / Arch:      Darwin / arm64 (OK)
  Clang Path:     /opt/homebrew/opt/llvm/bin/clang (OK)
  Opt Path:       /opt/homebrew/opt/llvm/bin/opt (OK)
  LLVM Version:   Homebrew LLVM version 22.1.8 (OK)
  Backend:        macOS high-precision timing (OK)

Status: READY FOR SEARCH
```

Run the complete unit and integration test suite:
```bash
.venv/bin/pytest -v
```
All 51 tests should pass cleanly.
