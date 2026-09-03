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
    from autotune import __version__
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"autotune {__version__}" in result.stdout


def test_cli_version_short_flag():
    from autotune import __version__
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert f"autotune {__version__}" in result.stdout


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


def test_cli_version_subcommand():
    from autotune import __version__
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Autotune System & Toolchain Diagnostics" in result.stdout
    assert __version__ in result.stdout


def test_cli_version_json():
    import json
    result = runner.invoke(app, ["version", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "autotune_version" in data
    assert "python_version" in data


def test_cli_history_markdown():
    result = runner.invoke(app, ["history", "--markdown"])
    assert result.exit_code == 0
    assert "Autotune Optimization History" in result.stdout or "Run ID" in result.stdout
