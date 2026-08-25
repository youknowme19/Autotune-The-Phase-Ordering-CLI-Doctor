"""
Unit tests for v0.3.0 Product Feature Enhancements:
1. PipelineInspector explain_report rationale generation.
2. CompareService search vs confirmed metric separation.
3. Reproduction bundle README search vs confirmed summary formatting.
4. Validation summary aggregate counts.
5. Cache status multi-layer observability table.
"""

import json
import pytest
from typer.testing import CliRunner

from autotune.cli import app
from autotune.reporting.explain import PipelineInspector
from autotune.services.compare import CompareService

runner = CliRunner()


def test_pipeline_inspector_explain_report():
    report_data = {
        "search_speedup": 1.25,
        "confirmed_speedup": 1.10,
        "prescription": {
            "speedup_ratio": 1.10,
            "classification": "IMPROVED",
            "evidence_grade": "A",
            "pass_sequence": {"passes": ["mem2reg", "gvn"]},
        },
        "evidence_score": {
            "p_value": 0.001,
            "cohens_d_effect_size": 1.45,
            "correctness_pass": True,
        },
    }

    lines = PipelineInspector.explain_report(report_data)
    assert len(lines) == 6
    assert "Search Phase: Discovered candidate pipeline with best exploratory speedup of 1.25x." in lines[0]
    assert "Confirmation Phase: Fresh independent benchmarking measured 1.10x speedup." in lines[1]
    assert "Grade A" in lines[4]
    assert "Action Recommendation: Prescribed candidate pipeline is eligible" in lines[5]


def test_compare_service_search_vs_confirmed_metrics(tmp_path):
    rep_a = tmp_path / "rep_a.json"
    rep_a.write_text(
        json.dumps({
            "search_speedup": 1.15,
            "confirmed_speedup": 1.05,
            "prescription": {
                "speedup_ratio": 1.05,
                "classification": "IMPROVED",
                "evidence_grade": "B",
                "pass_sequence": {"passes": ["mem2reg"]},
            },
            "evidence_score": {"p_value": 0.02, "candidate_cv_pct": 8.5, "cohens_d_effect_size": 0.95},
        })
    )

    rep_b = tmp_path / "rep_b.json"
    rep_b.write_text(
        json.dumps({
            "search_speedup": 1.30,
            "confirmed_speedup": 1.20,
            "prescription": {
                "speedup_ratio": 1.20,
                "classification": "IMPROVED",
                "evidence_grade": "A",
                "pass_sequence": {"passes": ["mem2reg", "gvn"]},
            },
            "evidence_score": {"p_value": 0.0001, "candidate_cv_pct": 5.1, "cohens_d_effect_size": 2.10},
        })
    )

    res = CompareService.compare_reports(str(rep_a), str(rep_b))
    assert res.search_speedup_a == 1.15
    assert res.search_speedup_b == 1.30
    assert res.confirmed_speedup_a == 1.05
    assert res.confirmed_speedup_b == 1.20
    assert res.speedup_diff == 0.15
    assert res.p_value_a == 0.02
    assert res.p_value_b == 0.0001
    assert res.cohens_d_a == 0.95
    assert res.cohens_d_b == 2.10
    assert "Report B confirmed speedup (1.20x) outperformed Report A (1.05x) by +0.15x gain." in res.summary


def test_cli_explain_command_json_report(tmp_path):
    rep = tmp_path / "report.json"
    rep.write_text(
        json.dumps({
            "search_speedup": 1.18,
            "confirmed_speedup": 0.95,
            "prescription": {
                "speedup_ratio": 0.95,
                "classification": "REGRESSION",
                "evidence_grade": "F",
                "pass_sequence": {"passes": ["mem2reg"]},
            },
            "evidence_score": {"p_value": 0.04, "cohens_d_effect_size": -0.80, "correctness_pass": True},
        })
    )

    result = runner.invoke(app, ["explain", str(rep)])
    assert result.exit_code == 0
    assert "Decision Rationale" in result.stdout
    assert "Discovered candidate pipeline" in result.stdout
    assert "Fresh independent benchmarking" in result.stdout
    assert "Grade F" in result.stdout


def test_cli_cache_status_command():
    result = runner.invoke(app, ["cache", "status"])
    assert result.exit_code == 0
    assert "Persistent Cache" in result.stdout
    assert "Compilation" in result.stdout
    assert "Performance" in result.stdout
