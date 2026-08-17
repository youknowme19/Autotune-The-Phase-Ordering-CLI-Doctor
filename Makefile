.PHONY: install dev-install test doctor diagnose clean help

PYTHON ?= python3

help:
	@echo "Autotune Makefile"
	@echo ""
	@echo "  install      Install package in production mode"
	@echo "  dev-install  Install package in editable mode with dev dependencies"
	@echo "  test         Run unit and integration tests"
	@echo "  doctor       Run environment toolchain diagnostic"
	@echo "  diagnose     Run baseline diagnosis on example kernel"
	@echo "  clean        Remove build artifacts and cache files"

install:
	$(PYTHON) -m pip install .

dev-install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	pytest -v tests/

doctor:
	autotune doctor

diagnose:
	autotune diagnose ./examples/simple_loop/kernel.c --workload ./examples/simple_loop/input.txt

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .coverage tmp/ .autotune_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
