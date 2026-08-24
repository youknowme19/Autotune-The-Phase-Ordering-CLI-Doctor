"""
Unit tests for Phase 3 Research-Grade Engineering & Product Upgrades.
"""

import json
import pytest
from typer.testing import CliRunner

from autotune.cli import app
from autotune.llvm.passes import PassSequence
from autotune.reporting.explain import PipelineInspector
from autotune.reporting.prescription import CompilerPrescription
from autotune.reporting.report import SearchReport
from autotune.doctor.checks import DoctorReport
from autotune.sandbox.executor import SandboxExecutor

runner = CliRunner()


def test_sandbox_executor_binary_args(tmp_path):
    executor = SandboxExecutor()
    sh_script = tmp_path / "echo_args.sh"
    sh_script.write_text("#!/bin/sh\necho \"ARGS: $@\"\n")
    sh_script.chmod(0o755)

    res = executor.execute(binary_path=str(sh_script), binary_args=["arg1", "arg2"])
    assert res.success is True
    assert "ARGS: arg1 arg2" in res.stdout


def test_pipeline_inspector_explain():
    seq = PassSequence(passes=["mem2reg", "sroa", "gvn", "loop-vectorize"])
    inspector = PipelineInspector()
    explanations = inspector.explain(seq)

    assert len(explanations) == 4
    domains = [exp.domain for exp in explanations]
    assert "SSA Transformation" in domains
    assert "Vectorization" in domains


def test_search_report_export_markdown(tmp_path):
    doc_report = DoctorReport(
        clang_ok=True,
        clang_path="clang",
        clang_version="Clang 22.1",
        python_version="3.11",
        python_ok=True,
        arch="arm64",
        os_name="Darwin",
        cpu_info="Apple Silicon",
        measurement_backend="macOS high-precision timing",
    )
    p = CompilerPrescription(
        pass_sequence=PassSequence(passes=["gvn", "mem2reg"]),
        reproducible_clang_command="clang -O0 kernel.c -o opt.bin",
        baseline_time_ms=100.0,
        candidate_time_ms=70.0,
        speedup_ratio=1.43,
    )
    report = SearchReport(
        source_path="kernel.c",
        doctor_report=doc_report,
        prescription=p,
        generations_searched=5,
        population_size=10,
    )

    md_path = tmp_path / "summary.md"
    report.export_markdown(str(md_path))

    assert md_path.exists()
    content = md_path.read_text()
    assert "# Autotune Optimization Search Report" in content
    assert "Confirmed Speedup:** **1.43x**" in content
    assert "gvn -> mem2reg" in content


def test_cli_explain_command():
    res = runner.invoke(app, ["explain", "mem2reg,sroa,gvn,licm"])
    assert res.exit_code == 0
    assert "LLVM Pass Pipeline Explanation" in res.output
    assert "mem2reg" in res.output
    assert "SSA Transformation" in res.output
