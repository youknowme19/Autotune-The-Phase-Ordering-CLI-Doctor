"""
Unit tests for full productization and engineering upgrades.
"""

import json
import os
import pytest
from typer.testing import CliRunner

from autotune.benchmark.models import ResultClassification
from autotune.cli import app
from autotune.llvm.passes import PassSequence
from autotune.reporting.prescription import PrescriptionBuilder, CompilerPrescription
from autotune.sandbox.executor import SandboxExecutor

runner = CliRunner()


def test_result_classification_logic():
    seq = PassSequence(passes=["gvn", "mem2reg"])

    # Improved (> 1.02x)
    p_improved = PrescriptionBuilder.build(
        source_path="test.c",
        output_binary="opt.bin",
        pass_sequence=seq,
        clang_path="clang",
        opt_path="opt",
        baseline_time_ns=100000000.0,
        candidate_time_ns=70000000.0,
    )
    assert p_improved.classification == ResultClassification.IMPROVED
    assert p_improved.speedup_ratio == 1.43

    # Parity / Tie (0.98x - 1.02x)
    p_tie = PrescriptionBuilder.build(
        source_path="test.c",
        output_binary="opt.bin",
        pass_sequence=seq,
        clang_path="clang",
        opt_path="opt",
        baseline_time_ns=100000000.0,
        candidate_time_ns=100000000.0,
    )
    assert p_tie.classification == ResultClassification.TIE
    assert p_tie.speedup_ratio == 1.0

    # Regression (< 0.98x)
    p_reg = PrescriptionBuilder.build(
        source_path="test.c",
        output_binary="opt.bin",
        pass_sequence=seq,
        clang_path="clang",
        opt_path="opt",
        baseline_time_ns=100000000.0,
        candidate_time_ns=120000000.0,
    )
    assert p_reg.classification == ResultClassification.REGRESSION
    assert p_reg.speedup_ratio == 0.83


def test_export_subcommand(tmp_path):
    report_file = tmp_path / "search_report.json"
    report_data = {
        "source_path": "examples/matrix_transpose/kernel.c",
        "prescription": {
            "pass_sequence": {"passes": ["gvn", "mem2reg"]},
            "reproducible_clang_command": "clang -O0 kernel.c -o opt.bin",
            "baseline_time_ms": 70.45,
            "candidate_time_ms": 55.86,
            "speedup_ratio": 1.26,
            "classification": "IMPROVED"
        }
    }
    report_file.write_text(json.dumps(report_data))

    output_dir = tmp_path / "prescription_out"
    res = runner.invoke(app, ["export", str(report_file), "-o", str(output_dir)])

    assert res.exit_code == 0
    assert (output_dir / "prescription.txt").exists()
    assert (output_dir / "reproduce.sh").exists()
    assert (output_dir / "prescription.json").exists()

    # Verify reproduce.sh has executable permission
    assert os.access(output_dir / "reproduce.sh", os.X_OK)

    # Verify prescription.txt contents
    txt_content = (output_dir / "prescription.txt").read_text()
    assert "AUTOTUNE COMPILER PRESCRIPTION" in txt_content
    assert "Speedup Ratio:   1.26x" in txt_content


def test_sandbox_executor_stream_truncation(tmp_path):
    executor = SandboxExecutor()

    # Create a script generating huge output (>10MB)
    script_file = tmp_path / "huge_output.py"
    script_file.write_text("import sys\nsys.stdout.write('A' * (11 * 1024 * 1024))\n")

    res = executor.execute(binary_path=str(script_file))
    # Python script won't be executable unless called with python or chmod +x with shebang
    # Let's test with sh script on Unix
    sh_script = tmp_path / "huge_output.sh"
    sh_script.write_text("#!/bin/sh\npython3 -c \"import sys; sys.stdout.write('A' * (11 * 1024 * 1024))\"\n")
    sh_script.chmod(0o755)

    res_sh = executor.execute(binary_path=str(sh_script))
    assert res_sh.success is True
    assert "[TRUNCATED: stdout exceeded 10MB limit]" in res_sh.stdout


def test_cli_search_quiet_mode():
    res = runner.invoke(app, ["search", "examples/matrix_transpose/kernel.c", "-w", "examples/matrix_transpose/input.txt", "--no-llm", "-p", "2", "-g", "1", "-s", "42", "--quiet"])
    assert res.exit_code == 0
    assert "[Generation 1/1]" in res.output
    assert "AUTOTUNE PRESCRIPTION" in res.output
