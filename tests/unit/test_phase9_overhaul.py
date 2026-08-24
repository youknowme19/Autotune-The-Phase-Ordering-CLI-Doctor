"""
Unit tests for Final Product Overhaul: HTML Report Generator, AutotuneRun abstraction, autotune compare, and autotune report commands.
"""

import json
import pytest
from typer.testing import CliRunner

from autotune.cli import app
from autotune.reporting.html import HTMLReportGenerator
from autotune.pipeline.run import AutotuneRun, RunStatus

runner = CliRunner()


def test_html_report_generator():
    report_data = {
        "source_path": "kernel.c",
        "generations_searched": 10,
        "population_size": 20,
        "prescription": {
            "speedup_ratio": 1.18,
            "classification": "IMPROVED",
            "evidence_grade": "A",
            "pass_sequence": {"passes": ["mem2reg", "sroa", "gvn"]},
            "reproducible_clang_command": "clang -O3 kernel.c -o opt.bin"
        },
        "workload_profile": {
            "loop_count": 3,
            "max_loop_depth": 2,
            "memory_intensity": 0.5,
            "compute_intensity": 0.8
        },
        "doctor_report": {
            "arch": "arm64",
            "clang_version": "Clang 22.1"
        }
    }

    html = HTMLReportGenerator.generate_html(report_data)
    assert "<!DOCTYPE html>" in html
    assert "1.18x" in html
    assert "Grade A" in html
    assert "mem2reg" in html


def test_autotune_run_lifecycle(tmp_path):
    run = AutotuneRun(run_id="run_001", source_path="matrix.c", source_hash="abcd1234")
    assert run.status == RunStatus.CREATED

    run.start()
    assert run.status == RunStatus.INITIALIZING
    assert run.start_time != ""

    run.complete(speedup=1.22, winning_passes=["mem2reg", "sroa"])
    assert run.status == RunStatus.COMPLETED
    assert run.speedup_ratio == 1.22

    run_dir = tmp_path / "runs"
    saved_file = run.save(str(run_dir))
    assert (run_dir / "run_001.json").exists()

    loaded = AutotuneRun.load(saved_file)
    assert loaded.run_id == "run_001"
    assert loaded.speedup_ratio == 1.22


def test_cli_compare_command(tmp_path):
    rep_a = tmp_path / "rep_a.json"
    rep_a.write_text(json.dumps({
        "prescription": {"speedup_ratio": 1.10, "classification": "IMPROVED", "evidence_grade": "B", "pass_sequence": {"passes": ["gvn"]}}
    }))

    rep_b = tmp_path / "rep_b.json"
    rep_b.write_text(json.dumps({
        "prescription": {"speedup_ratio": 1.25, "classification": "IMPROVED", "evidence_grade": "A", "pass_sequence": {"passes": ["mem2reg", "sroa", "gvn"]}}
    }))

    res = runner.invoke(app, ["compare", str(rep_a), str(rep_b)])
    assert res.exit_code == 0
    assert "Report B outperformed Report A" in res.output


def test_cli_report_html_command(tmp_path):
    rep_json = tmp_path / "search_report.json"
    rep_json.write_text(json.dumps({
        "source_path": "examples/matrix/matrix_mul.c",
        "prescription": {"speedup_ratio": 1.12, "classification": "IMPROVED", "evidence_grade": "B"}
    }))

    out_html = tmp_path / "report.html"
    res = runner.invoke(app, ["report", str(rep_json), "--html", str(out_html)])

    assert res.exit_code == 0
    assert out_html.exists()
    assert "<!DOCTYPE html>" in out_html.read_text()
