#!/usr/bin/env bash
set -e

echo "=== 1. Cleaning AppleDouble metadata and build artifacts ==="
find . -name "._*" -delete
rm -rf dist/ build/ *.egg-info src/*.egg-info

echo "=== 2. Building source distribution and wheel ==="
python3.11 -m pip install --upgrade pip build twine
python3.11 -m build

echo "=== 3. Running twine check on distribution metadata ==="
python3.11 -m twine check dist/*

echo "=== 4. Testing wheel installation inside temporary virtualenv ==="
TMP_VENV=$(mktemp -d)
python3.11 -m venv "$TMP_VENV"
source "$TMP_VENV/bin/activate"

WHEEL_FILE=$(ls dist/*.whl | head -n 1)
pip install --upgrade pip
pip install "$WHEEL_FILE"

echo "=== 5. Verifying autotune CLI execution ==="
autotune --help
autotune doctor

echo "=== 6. Cleanup temporary virtualenv ==="
deactivate
rm -rf "$TMP_VENV"

echo "=========================================================="
echo " SUCCESS: Release distribution build and validation passed!"
echo "=========================================================="
