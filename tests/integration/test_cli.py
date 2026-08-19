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
    # Verify banner is printed exactly once
    assert result.stdout.count("Phase-Ordering CLI Doctor") == 1


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "autotune 0.2.0" in result.stdout


def test_cli_version_short_flag():
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert "autotune 0.2.0" in result.stdout


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


def test_cli_diagnose_failing_binary_error_propagation(tmp_path):
    failing_c = tmp_path / "failing_kernel.c"
    failing_c.write_text("#include <stdlib.h>\nint main() { abort(); }\n")

    result = runner.invoke(app, ["diagnose", str(failing_c)])
    assert result.exit_code != 0
    assert "Warmup execution failed" in result.stdout
    assert "None" not in result.stdout
    assert "non-zero return code" in result.stdout or "exited" in result.stdout
