"""
Unit tests for Final Productization Pass: Application Services (OptimizeService, ValidateService, CompareService, ReportService), runs subcommand group, and HTML security escaping.
"""

import json
import pytest
from typer.testing import CliRunner

from autotune.cli import app
from autotune.services import OptimizeService, ValidateService, CompareService, ReportService
from autotune.reporting.html import HTMLReportGenerator

runner = CliRunner()


def test_optimize_service_run(tmp_path):
    src = tmp_path / "kernel.c"
    src.write_text("int main() { volatile int sum = 0; for(int i=0; i<50; i++) sum += i; return 0; }")

    out_dir = tmp_path / "runs" / "test_run_01"
    res = OptimizeService.run(source=str(src), time_budget=5, output_dir=str(out_dir), quiet=True)

    assert res.run_id != ""
    assert res.speedup_ratio >= 0.0
    assert (out_dir / "report.json").exists()
    assert (out_dir / "report.html").exists()


def test_compare_service(tmp_path):
    rep_a = tmp_path / "rep_a.json"
    rep_a.write_text(json.dumps({
        "search_speedup": 1.05,
        "confirmed_speedup": 1.05,
        "prescription": {"speedup_ratio": 1.05, "classification": "IMPROVED", "evidence_grade": "B", "pass_sequence": {"passes": ["mem2reg"]}}
    }))

    rep_b = tmp_path / "rep_b.json"
    rep_b.write_text(json.dumps({
        "search_speedup": 1.15,
        "confirmed_speedup": 1.15,
        "prescription": {"speedup_ratio": 1.15, "classification": "IMPROVED", "evidence_grade": "A", "pass_sequence": {"passes": ["mem2reg", "sroa"]}}
    }))

    res = CompareService.compare_reports(str(rep_a), str(rep_b))
    assert res.confirmed_speedup_a == 1.05
    assert res.confirmed_speedup_b == 1.15
    assert res.speedup_diff == 0.1
    assert "Report B confirmed speedup" in res.summary


def test_report_service(tmp_path):
    rep_json = tmp_path / "report.json"
    rep_json.write_text(json.dumps({
        "source_path": "<script>alert('xss')</script>",
        "prescription": {"speedup_ratio": 1.10, "classification": "IMPROVED", "evidence_grade": "A"}
    }))

    out_html = tmp_path / "report.html"
    rendered = ReportService.render_html_report(str(rep_json), str(out_html))
    assert out_html.exists()

    html_code = out_html.read_text()
    assert "&lt;script&gt;" in html_code
    assert "<script>" not in html_code


def test_cli_runs_subcommands(tmp_path):
    res_list = runner.invoke(app, ["runs", "list"])
    assert res_list.exit_code == 0

    res_clean = runner.invoke(app, ["runs", "clean"])
    assert res_clean.exit_code == 0
