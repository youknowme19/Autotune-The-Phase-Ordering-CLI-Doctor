"""
Unit tests for Phase 18: Evidence Evaluator deterministic boundary conditions.
Tests exact half-open intervals for speedup ratios, p-values, CV%, Cohen's d effect sizes, and correctness failures.
"""

import pytest
from autotune.reporting.evidence import EvidenceEvaluator, EvidenceGrade


def test_speedup_ratio_exact_boundaries():
    b_ref = [100000000] * 10  # 100ms baseline

    # Speedup < 0.98x -> Grade F (0.95x, 0.97x)
    assert EvidenceEvaluator.evaluate(b_ref, [105263157] * 10).grade == EvidenceGrade.GRADE_F  # 0.95x
    assert EvidenceEvaluator.evaluate(b_ref, [103092783] * 10).grade == EvidenceGrade.GRADE_F  # 0.97x

    # 0.98x <= Speedup < 1.02x -> Grade D (0.98x, 0.99x, 1.00x, 1.01x)
    assert EvidenceEvaluator.evaluate(b_ref, [102040816] * 10).grade == EvidenceGrade.GRADE_D  # 0.98x
    assert EvidenceEvaluator.evaluate(b_ref, [101010101] * 10).grade == EvidenceGrade.GRADE_D  # 0.99x
    assert EvidenceEvaluator.evaluate(b_ref, [100000000] * 10).grade == EvidenceGrade.GRADE_D  # 1.00x
    assert EvidenceEvaluator.evaluate(b_ref, [99009900] * 10).grade == EvidenceGrade.GRADE_D   # 1.01x

    # Realistic sample distributions with variance
    b_var = [100000, 100100, 99900, 100050, 99950]
    c_102 = [98000, 98100, 97900, 98050, 97950]  # 1.02x speedup
    c_105 = [95000, 95100, 94900, 95050, 94950]  # 1.05x speedup

    assert EvidenceEvaluator.evaluate(b_var, c_102, fresh_confirmation=True).grade in (EvidenceGrade.GRADE_B, EvidenceGrade.GRADE_A)
    assert EvidenceEvaluator.evaluate(b_var, c_105, fresh_confirmation=True).grade in (EvidenceGrade.GRADE_B, EvidenceGrade.GRADE_A)


def test_correctness_failure_always_yields_grade_f():
    b_ref = [100000000] * 10
    c_fast = [50000000] * 10  # 2.0x speedup but correctness failed

    score = EvidenceEvaluator.evaluate(
        baseline_samples_ns=b_ref,
        candidate_samples_ns=c_fast,
        correctness_pass=False,
        fresh_confirmation=True,
    )
    assert score.grade == EvidenceGrade.GRADE_F
    assert score.correctness_pass is False


def test_p_value_and_cv_noise_boundaries():
    # Stable baseline
    b_stable = [100000, 100100, 99900, 100050, 99950]
    
    # Low noise candidate, significant speedup (1.04x)
    c_low_noise = [96153, 96253, 96053, 96203, 96103]
    score_b = EvidenceEvaluator.evaluate(b_stable, c_low_noise, fresh_confirmation=True)
    assert score_b.grade == EvidenceGrade.GRADE_B

    # High noise candidate (CV > 15%) -> Grade C (not Grade F!)
    c_high_noise = [120000, 70000, 130000, 60000, 95000]
    score_c = EvidenceEvaluator.evaluate(b_stable, c_high_noise, fresh_confirmation=True)
    assert score_c.grade == EvidenceGrade.GRADE_C
