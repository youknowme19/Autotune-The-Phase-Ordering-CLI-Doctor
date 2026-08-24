"""
Unit tests for Final Scientific Audit Phase: Grade A requirement violation edge cases, speedup direction math, and CI performance gate evidence requirements.
"""

import json
import pytest
from typer.testing import CliRunner

from autotune.cli import app
from autotune.reporting.evidence import EvidenceEvaluator, EvidenceGrade

runner = CliRunner()


def test_grade_a_requires_all_criteria():
    base_stable = [1000000, 1000500, 999500, 1000100, 1000200]
    cand_fast = [800000, 800500, 799500, 800100, 800200]

    # 1. Standard Grade A
    score_a = EvidenceEvaluator.evaluate(
        baseline_samples_ns=base_stable, candidate_samples_ns=cand_fast, correctness_pass=True, fresh_confirmation=True
    )
    assert score_a.grade == EvidenceGrade.GRADE_A

    # 2. Violation: No fresh confirmation -> Degrades to Grade B / C
    score_unconfirmed = EvidenceEvaluator.evaluate(
        baseline_samples_ns=base_stable, candidate_samples_ns=cand_fast, correctness_pass=True, fresh_confirmation=False
    )
    assert score_unconfirmed.grade != EvidenceGrade.GRADE_A

    # 3. Violation: Correctness failure -> Hard Grade F
    score_fail = EvidenceEvaluator.evaluate(
        baseline_samples_ns=base_stable, candidate_samples_ns=cand_fast, correctness_pass=False, fresh_confirmation=True
    )
    assert score_fail.grade == EvidenceGrade.GRADE_F


def test_speedup_direction_math():
    # Candidate faster -> speedup > 1.0
    b_fast = [100000000]  # 100ms
    c_fast = [50000000]   # 50ms
    s_fast = EvidenceEvaluator.evaluate(baseline_samples_ns=b_fast, candidate_samples_ns=c_fast)
    assert s_fast.speedup_ratio == 2.0

    # Candidate slower -> speedup < 1.0
    b_slow = [100000000]  # 100ms
    c_slow = [200000000]  # 200ms
    s_slow = EvidenceEvaluator.evaluate(baseline_samples_ns=b_slow, candidate_samples_ns=c_slow)
    assert s_slow.speedup_ratio == 0.5
    assert s_slow.grade == EvidenceGrade.GRADE_F


def test_ci_gate_fails_on_untrusted_evidence_grade(tmp_path):
    rep_noisy = tmp_path / "noisy_report.json"
    rep_noisy.write_text(json.dumps({
        "prescription": {
            "speedup_ratio": 1.10,
            "classification": "IMPROVED",
            "evidence_grade": "C"  # Noisy / unconfirmed
        }
    }))

    res = runner.invoke(app, ["gate", str(rep_noisy), "--min-speedup", "1.05"])
    assert res.exit_code == 1
    assert "CI PERFORMANCE GATE FAILED" in res.output
