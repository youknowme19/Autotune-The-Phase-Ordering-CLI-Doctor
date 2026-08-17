"""
Integration tests invoking Typer CLI commands.
"""

from typer.testing import CliRunner
from autotune.cli import app

runner = CliRunner()


def test_cli_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Autotune" in result.stdout
    assert "Diagnostics" in result.stdout or "Python Version" in result.stdout


def test_cli_diagnose():
    result = runner.invoke(
        app,
        [
            "diagnose",
            "./examples/simple_loop/kernel.c",
            "--workload",
            "./examples/simple_loop/input.txt",
        ],
    )
    assert result.exit_code == 0
    assert "Baseline" in result.stdout
    assert "READY FOR SEARCH" in result.stdout
