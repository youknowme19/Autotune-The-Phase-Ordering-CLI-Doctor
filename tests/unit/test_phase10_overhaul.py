"""
Unit tests for Final Product Overhaul: autotune optimize, autotune status, and autotune validate commands.
"""

import os
import pytest
from typer.testing import CliRunner

from autotune.cli import app

runner = CliRunner()


def test_cli_status_command():
    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert "Autotune System & Environment Status" in res.output
    assert "Autotune Version" in res.output


def test_cli_optimize_command(tmp_path):
    src = tmp_path / "kernel.c"
    src.write_text("int main() { volatile int sum = 0; for(int i=0; i<100; i++) sum += i; return 0; }")

    out_dir = tmp_path / "opt_out"
    res = runner.invoke(app, ["optimize", str(src), "-o", str(out_dir), "-t", "5", "--quiet"])

    assert res.exit_code == 0
    assert (out_dir / "report.json").exists()
    assert (out_dir / "report.html").exists()


def test_cli_validate_command():
    res = runner.invoke(app, ["validate", "--quick"])
    assert res.exit_code == 0
    assert "Autotune Curated Benchmark Validation Harness" in res.output
