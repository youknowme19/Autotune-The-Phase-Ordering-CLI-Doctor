"""
Unit tests for statistical robustness and Mann-Whitney U non-parametric tests (Phase 10).
"""

from autotune.reporting.evidence import EvidenceEvaluator, EvidenceGrade


def test_mann_whitney_u_separation():
    # Baseline consistently slower (35-40ms) than candidate (25-30ms)
    b_samples = [int(x * 1e6) for x in [35.0, 36.0, 37.0, 38.0, 39.0, 40.0]]
    c_samples = [int(x * 1e6) for x in [25.0, 26.0, 27.0, 28.0, 29.0, 30.0]]

    u_stat, u_pval = EvidenceEvaluator.compute_mann_whitney_u(b_samples, c_samples)
    assert u_stat == 36.0  # Max separation: 6 x 6 = 36
    assert u_pval < 0.01

    score = EvidenceEvaluator.evaluate(b_samples, c_samples)
    assert score.grade in (EvidenceGrade.GRADE_A, EvidenceGrade.GRADE_B)
    assert score.mann_whitney_p_value < 0.01
    assert score.cohens_d_effect_size > 2.0


def test_mann_whitney_u_tied_samples():
    b_samples = [int(x * 1e6) for x in [30.0, 30.0, 30.0]]
    c_samples = [int(x * 1e6) for x in [30.0, 30.0, 30.0]]

    u_stat, u_pval = EvidenceEvaluator.compute_mann_whitney_u(b_samples, c_samples)
    assert u_stat == 4.5  # Mean rank
    score = EvidenceEvaluator.evaluate(b_samples, c_samples)
    assert score.grade == EvidenceGrade.GRADE_D  # Parity
