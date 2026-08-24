"""
Unit tests for Final Productization, UX, and Cross-Platform Overhaul.
"""

import json
import pytest
from typer.testing import CliRunner

from autotune.cli import app
from autotune.doctor.checks import find_tool, run_doctor_checks

runner = CliRunner()


def test_doctor_toolchain_discovery():
    report = run_doctor_checks()
    assert report.python_ok is True
    assert report.arch in ("arm64", "x86_64", "aarch64", "x86")


def test_cli_all_subcommands_help():
    commands = ["doctor", "diagnose", "search", "export", "explain", "knowledge", "bundle", "bench-suite", "config"]
    for cmd in commands:
        res = runner.invoke(app, [cmd, "--help"])
        assert res.exit_code == 0
        assert "Usage:" in res.output


def test_end_to_end_product_workflow(tmp_path):
    # 1. Doctor
    res_doc = runner.invoke(app, ["doctor"])
    assert res_doc.exit_code == 0

    # 2. Diagnose
    src = tmp_path / "kernel.c"
    src.write_text("int main() { volatile int sum = 0; for(int i=0; i<100; i++) sum += i; return 0; }")

    res_diag = runner.invoke(app, ["diagnose", str(src)])
    assert res_diag.exit_code == 0
    assert "READY FOR SEARCH" in res_diag.output

    # 3. Search (Quiet Mode)
    out_json = tmp_path / "report.json"
    res_search = runner.invoke(
        app,
        ["search", str(src), "--no-llm", "-p", "2", "-g", "1", "-s", "42", "-o", str(out_json), "--quiet"]
    )
    assert res_search.exit_code == 0
    assert out_json.exists()

    # 4. Explain
    res_explain = runner.invoke(app, ["explain", str(out_json)])
    assert res_explain.exit_code == 0

    # 5. Export
    out_export = tmp_path / "prescription_out"
    res_export = runner.invoke(app, ["export", str(out_json), "-o", str(out_export)])
    assert res_export.exit_code == 0
    assert (out_export / "reproduce.sh").exists()

    # 6. Bundle
    out_bundle = tmp_path / "bundle_out"
    res_bundle = runner.invoke(app, ["bundle", str(out_json), "-b", str(out_bundle)])
    assert res_bundle.exit_code == 0
    assert (out_bundle / "manifest.json").exists()
